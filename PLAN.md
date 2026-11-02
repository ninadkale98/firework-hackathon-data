# Make our own frontier: an 8B model for AI interviews and Learn

Fireworks × Microsoft × NVIDIA hackathon, SF, 2026-11-02. Plan written 2026-11-01, revision 2.

## The challenge, and our entry

> Pick a task, deploy a model that serves it in production, build an eval, measure the tradeoffs (quality vs efficiency, accuracy vs latency, pass rate vs cost), tune at least one dimension against the baseline, show the business value, and show how far you pushed it.

**Our task** is the turn-by-turn agent behind CodePraxis AI interviews and the Learn tutor. Each turn the agent:
- reads a long, structured prompt: the question, stage, clocks, files, chat so far;
- returns one JSON move: follow up, hint, clarify, redirect, go deeper (probe), close the question, or a tutor move in Learn.

| Task | What the agent does | Model in production today |
|---|---|---|
| **Interview** | live technical interview, six moves | `claude-opus-5`, effort medium |
| **Learn: Assess** | the same six moves plus a grade per stage | `claude-sonnet-5-5`, effort medium |
| **Learn: Study** | tutor moves: EXPLAIN, POINT, TRY, CHECK_ME, REDIRECT, SUGGEST_ASSESS, ADD_NOTE | `claude-sonnet-5-5`, effort low |

**What we train for** is quality on this task: the right move, no leaked answers, a good follow-up.

**The dimension we push** is **cost and latency at equal quality**.

| Measure | Baseline | Target |
|---|---|---|
| Quality score (our eval) | base Qwen3-8B, far below Claude | tuned 8B ≥ 90% of Claude's score |
| Cost per 30-min interview | Opus 5: ~$1.00–1.90 | under $0.05 |
| Round 1 of a 50K-student hackathon (2 days) | Opus 5: $50–94K · Sonnet 5.5: $20–37K | ~$1–3K of H100 time |
| Latency per turn, p50 / p95 | Opus 5: ~12 s | under 5 s (estimate, to be measured) |
| Leak rate | base 8B leaks (seen in the smoke test) | at or below Claude's |

**Business value:** one 2-day screening round for 50K students goes from about $50K of API spend to about $2K, at the same interview quality.

**Deliverable charts:**
1. Quality vs $ per interview.
2. Quality vs p50 latency.

One point per model: Claude Opus, Claude Haiku, GPT-5.4, open teacher, base 8B, tuned v1, tuned v2, tuned + DPO, FP8, 4B.

**How far we push it:**
1. SFT
2. More data on the weakest slices
3. DPO against leaks and wrong moves
4. FP8 serving and a smaller 4B
5. Stretch: routing. The 8B takes most turns and hands uncertain Assess grades to a bigger model.

---

## 1. Who does what

**Rules (revised 2026-11-01, the user has no OpenAI training permission):**
- **Training data comes only from open-weight models** whose licences allow training on their output (DeepSeek: MIT · Qwen: Apache 2.0 · gpt-oss: Apache 2.0 · Kimi: modified MIT). No Llama: its licence adds conditions on derived models.
- **Claude never produces anything that ends up in training data.** GPT plays the candidate and judges in both training and test; the user accepted that on 2026-11-01.
- Every record stores which model wrote each part.

| Role | Model | Where | Notes |
|---|---|---|---|
| **Test set: interviewer and reference** | **Claude Opus 5 for all three tasks** (interview, Assess, Study), for consistency | Anthropic | Opus runs the test sessions end to end, so the history inside each test turn is frontier behaviour too. Study is stricter than production (Sonnet there) |
| **Teacher** (writes training answers) | **one open model, picked by bake-off** (option A, decided 2026-11-01): DeepSeek V4 Pro, Kimi, Qwen3-235B, gpt-oss-120B | Fireworks | Bake-off: 150 Opus test turns, ~$10, ~45 min. All 9K training turns then come from the winner only |
| **Candidate / learner simulator** | **`gpt-5.4` for training and test** | OpenAI | User's decision (2026-11-01): GPT text inside training prompts is acceptable to them |
| **Messy variants** | simulator rewrites + the rule-based corrupter | Fireworks / local | Clean/messy pairs |
| **Judge** (criteria pass/fail + 1–5, and head-to-head win rate) | **`gpt-5.4` for training and test** | OpenAI | Training: drops bad teacher answers. Test: scores every model. Checked against ~30 hand labels |
| **Comparison dots** | Opus 5, Haiku 5.5, `gpt-5.4` (test only), the open teacher, base Qwen, tuned Qwen | Anthropic / OpenAI / Fireworks | All on the same test turns |
| **Student** | **Qwen3.5-9B** (`qwen3p5-9b`, decided 2026-11-01; Qwen3-8B as a backup) | base: Fireworks pay per token + local Ollama · tuned: Fireworks dedicated deployment | |

**Agreement (level 3) is reported twice:** against Opus (the target) and against the open teacher (how well the student copied its teacher). The teacher's own agreement with Opus is the student's ceiling.

All open models go through one OpenAI-style client. Only the endpoint address, key and model id change.

### Local smoke test (2026-11-01, done)

Replay of production trace 416, run on the Mac only. The candidate wrote "I dont know this, move on".

| | Opus 5 (production) | Qwen3-8B local, base |
|---|---|---|
| Valid JSON, legal move | yes | **yes** (Ollama enforced the schema) |
| Move | FOLLOW_UP ("Let's not move on yet…") | **PROBE**, skipped ahead |
| Leak | none | **gave away the answer path** |
| Latency / tokens | ~12 s | **42 s**, 3,202 in / 303 out |

The format comes free; the judgement is what training has to teach.

**Second turn: trace 418, after one hint and repeated refusals.**
- Opus closed the diagnosis and moved the candidate on to writing code.
- Local Qwen chose HINT and **wrote out the whole diagnosis itself**: the 08:02 list vs the 09:15 revoke vs the 11:40 approval. That is a full leak.
- It took 56 s for 4,178 tokens in.

**Gotcha:** Ollama's default context is 4,096 tokens and it silently cuts longer prompts. Use `qwen3-8b-32k` (`local/Modelfile.qwen3-8b-32k`, `num_ctx 32768`).

---

## 2. Dataset: 10,000 turns

| Task | Train | Validation | Test (held-out questions) |
|---|---|---|---|
| Interview | 4,000 | 400 | 500 |
| Assess | 1,600 | 150 | 250 |
| Study | 2,400 | 200 | 300 |
| **Total** | **8,000** | **750** | **1,050** |

Plus **100 hand-reviewed gold turns** taken from the test set.

**Rules:**
- **Split by question, never by turn.** Test questions never appear in training.
- Also keep `test_in_dist`: unseen turns from training questions.
- **Every bucket in section 3 has at least 30 test cases**, so every slice score is meaningful.
- **No single question supplies more than 8% of a task's training data.**
- Near-duplicate filter on the candidate message plus the state signature.

**Questions needed** (more questions = more variety in the question fields):

| Group | Count |
|---|---|
| Interview | 5 per track × 4 tracks (embedded, frontend, backend, AI/agent engineering) = **20**. 1 per track held out for test |
| Learn | **6–8 sub-modules** (Rust curriculum and others). 2 held out |

---

## 3. Variety: every field the model sees

Each turn's prompt is built from fixed fields. **Each field gets a list of buckets (the values or ranges we cover), and the generator fills them.** It uses all-pairs sampling: every pair of buckets across the main dimensions appears at least a few times.

A coverage report in the dashboard shows the count for each bucket and each pair. Generation keeps topping up until every bucket meets its minimum.

**States must be legal.** We drive the real engine (driver, cursor, `shapes.build_turn`) to reach each state, then vary only true inputs (clock, history, notes, message). No impossible state is hand-built.

### 3.1 Interview prompt (`interview/runtime/agent.py`)

| Section | Field | Buckets |
|---|---|---|
| Brief | `mode_brief` | interview brief (fixed) |
| FINISHED QUESTIONS | `global_interview_context` | none (first question) · 1 · 2–3 · with strong / weak / disengaged summaries |
| THIS QUESTION | `name`, `topics` | 20 questions · 1 / 2–3 / 4+ topics |
| | `seniority` | junior · mid · senior · unspecified |
| | `question_prompt` (brief) | present · "(none)" |
| THE CLOCK | `time_left_in_stage_s` | >600 · 240–600 · 60–240 · 1–59 · 0 |
| | `time_left_in_question_s` | plenty · at or under `CLOSING_UNLOCKED_UNDER_QUESTION_TIME_S` · 0 (forced close) |
| | `question_position` | 1 of 1 · 1 of 3 · middle · last |
| | `stage_position` | 1 of 4 … 4 of 4 |
| DIRECTIONS | `probe_options` | 0 (dead end) · 1 · 2–3 |
| HINTS | `available_hints` | 0 · 1 · 2+ · with files attached vs text only |
| DECIDE | **set of moves offered** | **all 11 sets the engine can produce** (2 always-on moves × closing available × stage open × hints × probes, plus forced QUESTION_DONE). **≥ 200 training turns per set** |
| CLOSED STAGES | `stages_so_far` | 0 · 1 · 2–3 · strong / weak `last_stage_performance` |
| STAGE BEING ANSWERED | `level` | 0 · 1 · 2 · 3 |
| | stage files | none · 1 · several · every type: code, repo, markdown, image, Excalidraw, PDF/doc, video/audio |
| RUNNING CODE | `runnable_files` | none · runnable · runnable + hidden tests |
| SINCE IT WAS ASKED | `stage_history` length | 0 (first reply) · 1–2 · 3–6 · 7+ |
| | earlier notes/gaps from the AI | none · present |
| | files in the history | none · candidate drawing · edited file revisions |
| EXPECTED ANSWER | `expected_current_solution` | authored · "(none authored)" |
| WITHHELD | `withheld_solution_parts` | none · 1–2 · 3+ |
| **Candidate message** | candidate type | strong · partial · confident but wrong · "I don't know" · asks for the answer · off-topic · prompt injection · terse · pastes code · silent/slow |
| | writing style | clean ~60% · messy ~40% (typos, no punctuation, SMS short forms, vague words, dictated speech, rambling) · **Hinglish 5–10%** |
| | length | 1–5 words · a sentence · a paragraph · 300+ words |
| | channels | text only · drawing only · text + drawing · selected lines · edited file · combinations |
| | code runs since the last message | none · pass · fail · compile error · timeout · several runs · Submit with hidden-test results |

### 3.2 Assess prompt (`learn/tutor/agent.py`, Assess branch)

All the interview fields above that Assess shares (clock, probes, hints, closed stages, current stage, history, rubric, candidate message), plus:

| Field | Buckets |
|---|---|
| `stage_kind` | opening · every probe kind used in the sub-modules (predict, explain, write, fix…) |
| `stage_skills` | 1 · 2–3 skills |
| `child` (next stage for PROBE) | present · none |
| `study_topics` | none · a few · many |
| `notes` | empty · short · long (up to the 20k-char cap) · **injection inside notes** |
| `weak_skills` | none · some (context only, never evidence) |
| `turns_here` vs `turn_cap` | 0 · middle · at cap |
| `gap_check` | false · true (Fix my gaps) |
| Grade targets | every level the rubric allows, including downgrades after a follow-up |

### 3.3 Study prompt (`learn/tutor/agent.py`, Study branch; `inputs.py`)

| Field | Buckets |
|---|---|
| Sub-module status | first visit · some done · all but one done |
| Files | lesson HTML · code with line numbers · runnable · diagram · video · PDF |
| `notes` | empty · short · long · injection inside |
| `prior_gaps` | 0 · 1–3 · up to the cap of 10 |
| Memory (`doubts`, `confusions`, `weak_skills`) | empty · some · full |
| Evidence on a skill from last time | none · present |
| `study_summary` (earlier chat, one line each) | none · 3 · 10+ |
| Recent chat (`study_history`) | first message · 2–4 · 8+ |
| `last_tutor_line` | none · was a question · was a TRY · was a CHECK_ME |
| Contents ticks (`steps`) | none · some · all |
| `gap_skill` (Fix my gaps) | off · on |
| `runs` | none · pass · fail · compile error |
| **Learner message** | asks a concept · quotes lesson text ("Ask Tutor") · asks to add to notes / summarise to notes · "check my code" · confused · asks for the answer · off-topic · wants to go to Assess · prompt injection · same styles and Hinglish share as 3.1 |

### 3.4 Clocks without waiting

The schema and prompt depend only on `current_state`. So every timing bucket is reached by:
1. A **fake clock** in the driver during simulated runs, advancing by each candidate type's typical thinking time.
2. **Clock edits**: re-ask the teacher on a recorded turn with the clock set to edge values. About 15% of the data.

---

## 4. How data is generated

| Method | What it gives | Share |
|---|---|---|
| A. Simulated runs | simulator × real engine × fake clock, full sessions | ~55% |
| B. Forking | at chosen turns, 2–3 alternative replies from the same state | ~25% |
| C. Clock and field edits | the same state with edge clocks, longer or shorter history, notes injected | ~20% |

### 4.1 Simulator
- One prompt per candidate type, plus a writing style.
- A **hidden knowledge level** per question, so answers are believably right, partly right or wrong.
- **Never sees the rubric.**
- Drawings come out as a small graph spec → we build a real Excalidraw scene → the real `normalize_excalidraw` converts it. Selected lines and edited files go through the real `ModalityIngestor`.

### 4.2 Text corrupter
- A fixed function that makes **clean/messy pairs** of the same answer (typos, case, punctuation, SMS short forms, fillers). These pairs measure robustness.
- Hinglish comes from the simulator, not the corrupter.

### 4.3 Teacher call
- Exactly the production prompt and per-turn schema, sent through the OpenAI-style client with the schema wrapped (`wrap`/`widen` in `openai_schema_client.py`).
- **Fireworks note:** "Using `response_format` with `json_schema` disables reasoning output." So the bake-off compares:
  - (a) schema enforced, no reasoning;
  - (b) reasoning on, JSON validated by us, one retry.

### 4.4 Teacher bake-off (first, ~1 hour, ~$10)
1. Opus runs ~150 test turns first. Those are the reference.
2. Score DeepSeek V4 Pro, Kimi, Qwen3-235B and gpt-oss-120B on the same turns with the section 5 metrics.
3. For reasoning models, try both: schema enforced (Fireworks turns reasoning off) vs reasoning on plus our own JSON check.
4. Pick the closest to Opus per dollar. If two are close, split the answers between them for variety.

### 4.4b Saving money
- Forks and edits don't wait on the reply, so they can go in batches where the endpoint offers it (Fireworks batch is 50% off).
- Prompts put the stable part first, so prefix caching applies where the endpoint has it.
- Price 20 turns per role before the full run; the generator stops at the cap.

### 4.5 Cost

The open-model prices are estimates and need confirming in the Fireworks console. DeepSeek V4.1 Flash is $0.30 / $1.20 per 1M tokens (official). DeepSeek V4 Pro is ~$1.74 / $3.48 (third-party).

| Item | Cost |
|---|---|
| Opus test set: ~1,050 turns, all three tasks, sessions run by Opus | ~$55 (Anthropic) |
| Haiku on the test set | ~$2 (Anthropic) |
| `gpt-5.4` judge: criteria + head-to-head, ~400 test turns × every model | ~$70 (OpenAI) |
| `gpt-5.4` test-set simulator | ~$10 (OpenAI) |
| `gpt-5.4` on the test set (a comparison dot only) | ~$25 (OpenAI credits) |
| Bake-off | ~$10 (Fireworks) |
| Teacher, ~9K training turns on DeepSeek V4 Pro (cheaper if Kimi, Qwen or gpt-oss wins) | ~$130 (Fireworks) |
| Simulator, ~10K turns, V4.1 Flash | ~$20 (Fireworks) |
| **Tonight** | **Fireworks ~$160 · Anthropic ~$60 · OpenAI ~$105 (of $200)** |
| Tomorrow on hackathon credits: SFT ~$50 per run, H100 serving ~$50–100 | Fireworks credits |

**Time:** 10K teacher turns at 30 in parallel is about 1–2 hours, depending on OpenAI rate limits. Batch jobs finish within 24 h, usually much sooner.

---

## 5. Evaluation

| Level | Check | How |
|---|---|---|
| 1. Format | valid JSON for the schema · move was offered · probe/hint/entity ids exist · `topic` is the exact required string | code |
| 2. Rules | **no leak** (word overlap with rubric, withheld parts, reference answer) · forced close at question time 0 · no new probe when time is nearly out · asks for the answer → no answer · prompt injection (in message or notes) → REDIRECT · vague answer → CLARIFY usually · Study: ADD_NOTE only when asked | code |
| 3. Agreement | same move · same probe · same hint · same grade (Assess) **as Claude** (the bar) and **as the teacher** | code |
| 4. Message quality, 1–5 | responds to what was actually said · one question at a time · right length · tone · no spoon-feeding | `gpt-5.4` judge: criteria pass/fail with quoted evidence, plus head-to-head win rate. Checked against 30 hand labels |
| 5. Robustness | same move on clean vs messy pairs; score by writing style (incl. Hinglish) | code |
| 6. Running cost | latency p50/p95 · tokens · $/1k turns · $/30-min interview · $/50K-student round | logged |

**Headline score per task:** mean of format pass, rules pass, move agreement with Claude, and judge score / 5. Every part is shown, sliced by every bucket in section 3.

**Gold set:** 100 test turns where a person marks Claude's and the teacher's answers ok / fix / bad. So neither one is assumed to be 100%.

---

## 6. Storage

One SQLite file holds records, runs and scores; JSONL files are exported for training.

**Master record** (one per turn):

```json
{
  "id": "intv-embedded-q561-p1-wrongbelief-hinglish-t3",
  "task": "interview", "track": "embedded", "split": "train",
  "source": "sim|fork|edit", "question_id": 561, "stage_level": 1,
  "buckets": {"stage_clock": "1-59", "question_clock": "plenty", "offered_set": "CL,FU,HI,PR,RE",
              "history_len": "3-6", "persona": "wrong_belief", "style": "hinglish",
              "channels": ["text","whiteboard"], "runs": "fail", "withheld": "1-2"},
  "pair_id": null,
  "system": "<exact system prompt>", "user": "<exact user message>", "schema": {},
  "teacher": {"model": "deepseek-v4-pro", "mode": "schema|reason", "output": {},
              "latency_ms": 0, "tokens": {"in": 0, "out": 0}},
  "labels": {"move": "FOLLOW_UP", "probe_id": null, "hint_id": null, "level": null},
  "secrets": ["<rubric>", "<withheld>", "<reference answer>"],
  "gold": null
}
```

**Training line (Fireworks format):**

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"<teacher JSON>"}]}
```

**Runs table:** one row per (model, record): output, scores, latency, tokens, cost.

### 6.1 Files and where they live

| File | Format | Where | Purpose |
|---|---|---|---|
| `data/distill.db` | SQLite: `records` (master records), `runs` (one model's output on one record), `scores` | **local** (git-ignored), copied to cloud storage after each batch | the source of truth; the dashboard reads it |
| `data/export/train.jsonl`, `val.jsonl` | Fireworks chat JSONL | local + **uploaded as Fireworks datasets** | SFT input; `val` is passed as `--evaluation-dataset` |
| `data/export/test.jsonl` | the same format | local + Fireworks | the frozen test set (prompts + Opus answers); one file every model runs on |

### 6.2 The training line, checked against Fireworks docs (2026-11-01)

Per the Fireworks docs:
- JSONL with one object per line, 3 to 3M lines.
- Each object has `messages` with roles `system`, `user`, `assistant` and `tool`; `tools` is optional.
- A per-message `weight: 0` keeps that message out of the loss.

Ours:

```json
{"messages":[
  {"role":"system","content":"<the full prompt: stable prefix + volatile tail>"},
  {"role":"user","content":"<the candidate's message, files, runs>"},
  {"role":"assistant","content":"{\"move_object\":{\"move\":\"FOLLOW_UP\", ...}}"}]}
```

- **The same two messages production sends** (`system` + `user`): the training input matches serving exactly.
- **The assistant text is exactly what the served model must output**: compact JSON in the wrapped shape `{"move_object": …}`, because our OpenAI-style client sends `wrap(schema)`. One shape for training, serving and scoring.
- **No thinking text in the target.** Serve Qwen3 with thinking off (`enable_thinking=false` / `/no_think`) so its output matches the training targets.
- **Size:** ~20 KB per line × 9K lines ≈ 180 MB. Upload with `firectl` (the web UI tops out around 500 MB).
- **Length:** Study prompts may be long. Measure them (D7) and set `--max-context-length` to fit; anything longer is cut off.

### 6.3 Fireworks commands (from their docs)

```bash
firectl dataset create distill-train data/export/train.jsonl
firectl dataset create distill-val   data/export/val.jsonl
firectl sftj create --base-model accounts/fireworks/models/qwen3-8b \
  --dataset distill-train --evaluation-dataset distill-val \
  --output-model codepraxis-interviewer-v1 \
  --lora-rank 16 --epochs 2 --max-context-length 32768
firectl deployment create codepraxis-interviewer-v1 --deployment-shape default
```

### 6.4 Evaluation: run by us, calling Fireworks

- **Our scorer runs locally** and calls every model through its API: Fireworks for the open models and Qwen, plus Anthropic and OpenAI. We have to compare across providers anyway, and the leak, rule and robustness checks are our own code.
- **Fireworks Evaluators / Eval Protocol** (their scoring SDK, used for evaluation jobs and reinforcement fine-tuning) are not needed for SFT. Our rule checks can be ported to it later if we try reinforcement fine-tuning as a stretch goal.

---

## 7. Dashboard: "Model Lab"

Built on `interview-lab/`.

| Tab | What you do |
|---|---|
| Dataset | browse and filter by any bucket; see the prompt, teacher output and secrets |
| **Coverage** | count for each bucket and each pair; gaps shown in red |
| Run | pick models × split → run them all; progress and cost so far |
| Compare | score table per model × slice; the two charts (quality vs $, quality vs latency); any turn with all models side by side, leaks highlighted |
| Playground | one prompt, every model |

---

## 7b. Baseline before the hackathon (tonight)

**Goal:** walk in with baseline numbers already on the dashboard.

| # | Step | Needs |
|---|---|---|
| 1 | `FIREWORKS_API_KEY` in `backend/.env` + `firectl` installed | user: key and ~$160 credit |
| 2 | Build: fake clock, simulator, generator, scorer, dashboard (B2–B8) | — |
| 3 | Pick the questions (D1) | user's OK |
| 4 | **Test set:** ~1,050 turns, sessions run by Opus, candidates played by `gpt-5.4` | Anthropic ~$55, OpenAI ~$10 |
| 5 | **Baselines on the test set:** Haiku 5.5, `gpt-5.4`, 3–4 open teacher candidates (this is also the teacher bake-off), base Qwen3-8B on Fireworks, local Qwen3-8B on a subset | Fireworks ~$15 (more if Qwen3-8B isn't serverless: then an on-demand H100 for ~1 h, $8) |
| 6 | **Judge + scores → dashboard = the baseline** | OpenAI ~$70 |
| 7 | **Overnight:** the bake-off winner generates the 9K training turns; GPT judge drops bad answers; export + upload to Fireworks | Fireworks ~$130, OpenAI ~$60 |

**Tomorrow at the hackathon:** start the SFT job straight away.

## 8. Training (tomorrow)

| Step | Method | Settings |
|---|---|---|
| 0 | base Qwen3-8B, our prompt + schema | baseline |
| 1 | **LoRA SFT** on teacher answers | rank 16–32, 2 epochs, context 32k, batch 32 |
| 2 | more data on the weakest slices → SFT v2 | same |
| 3 | DPO: teacher answer = chosen; leaking or wrong-move answer (from base / v1) = rejected | stretch |
| 4 | FP8 serving; 4B student | efficiency points for the charts |

**Fireworks facts (checked 2026-11-01):**
- Training: LoRA SFT on models up to 16B costs $0.50 per 1M training tokens; DPO $1.00.
- Serving: a fine-tune needs a **dedicated deployment** (H100 $8/hr; H200 $8; B200 $13).
- Base 4B–16B pay-per-token: $0.20 per 1M tokens.
- Dataset: 3 to 3M lines. Context default ≥ 32k; longer examples are cut off, so **check Study prompt lengths**.
- JSON-schema output on dedicated deployments isn't confirmed in the docs; test with base Qwen3-8B tonight.

---

## 9. To-dos

### Tonight: build
- [x] **B1** One client for open models. `OpenAISchemaCompleter` now takes `base_url` and `reasoning_effort`; existing tests pass (129). Model registry in `distill/models.py`. Checked live: GPT (`gpt-5.4`) and local Qwen. Fireworks waits for the key.
- [ ] **B2** Fake clock that can be swapped into the interview and Learn drivers.
- [ ] **B3** Simulator: candidate-type, style and Hinglish prompts, hidden knowledge, drawing graph → Excalidraw.
- [ ] **B4** Generator: bucket definitions (section 3), all-pairs sampler, forking, field edits, minimum-count top-up. Resumable, parallel, stops at the budget cap.
- [ ] **B5** Text corrupter for clean/messy pairs.
- [ ] **B6** SQLite store, JSONL export, split by question, near-duplicate filter, 8% per-question cap.
- [ ] **B7** Scorer (levels 1–6) and the judge prompt.
- [ ] **B8** Model Lab, including the Coverage tab and the two charts.

### Tonight: data
- [ ] **D1** Pick 20 interview questions (5 per track) and 6–8 Learn sub-modules; check file-type coverage. Backend track: check what exists.
- [ ] **D2** Teacher bake-off (section 4.4) → pick the teacher.
- [ ] **D3** Price 20 turns → full 10K run → coverage report → top up the gaps.
- [ ] **D4** Hand-label 100 gold turns and 30 judge-calibration cases (team).
- [ ] **D5** Baselines on the test set tonight: Opus test set, Haiku, GPT-5.4, open teacher, local Qwen3-8B on ~150 turns (~2 h). Full base Qwen3-8B and 4B runs move to tomorrow morning on Fireworks.
- [ ] **D6** (tomorrow) Check JSON-schema output on a Fireworks deployment of base Qwen3-8B.
- [ ] **D7** Check Study prompt lengths against 32k.

### Tomorrow
- [ ] **T1** SFT v1 → deploy → score.
- [ ] **T2** Weakest slices → more data → SFT v2.
- [ ] **T3** DPO (stretch).
- [ ] **T4** FP8 and 4B points.
- [ ] **T5** Demo: the charts, side-by-side turns, round-1 cost at 50K students.

### Done
- [x] Local Ollama `qwen3:8b`; one real turn replayed.
- [x] Pricing: Anthropic, Fireworks.
- [x] Decided: open-model teacher and training simulator on Fireworks; Claude Opus builds the test set for all three tasks; `gpt-5.4` is the test simulator, the judge and a comparison dot. Neither Claude nor GPT feeds training.
- [x] Decided: 10K dataset; variety across every field of the prompt.
- [x] Decided: Hinglish at 5–10%.

---

## 10. Needed from the user

| # | What | Why |
|---|---|---|
| 1 | **`FIREWORKS_API_KEY` tonight**, with ~$160 of your own credit (hackathon credits arrive too late for data) | open teacher and simulator run on Fireworks |
| 2 | Spend caps: Fireworks ~$180, Anthropic ~$70, OpenAI ~$120 (test simulator, judge, comparison dot) | the generator stops at the cap |
| 3 | At the hackathon: ask Fireworks for GPU quota (8 × H100) | serving the tuned model |
| 4 | — | (DeepSeek dropped) |
| 5 | 1–2 teammates for an hour of hand labelling (D4) | gold set and judge calibration |
| 6 | OK the 20 questions and 6–8 sub-modules I propose (D1) | content variety |

---

### 10b. Budget as it stands (2026-11-01): Fireworks $150 · OpenAI $200 · Anthropic as needed

| Account | Item | Cost |
|---|---|---|
| Fireworks | bake-off: 4 models × 100 turns | ~$8 |
| | base Qwen3-8B on the test set | ~$2 (+$8/h if it needs an on-demand H100) |
| | teacher, training turns: **fill up to the cap** (~9K if a cheap model wins; ~8K on V4 Pro); hackathon credits top up the rest tomorrow | ≤ $135 |
| | **cap** | **$145** |
| OpenAI | candidate, test + training: **`gpt-5.4-mini`** (~10K turns) | ~$20 |
| | judge, test set (~400 turns × every model): `gpt-5.4` | ~$70 |
| | judge, training filter: `gpt-5.4-mini` | ~$20 |
| | `gpt-5.4` as a test-set comparison dot | ~$25 |
| | **cap** | **$190** |
| Anthropic | Opus test set (~1,050 turns) + Haiku | ~$60 |

Keys live in `hackathon/fireworks-distill/.env` (git-ignored, mode 600): `FIREWORKS_API_KEY`, `DISTILL_OPENAI_API_KEY`. The user writes them, not Claude. Rotate both after the hackathon: they were pasted in chat.

### 10c. Checked on the account (2026-11-01, 21:30)

**Keys and tools**
- Both keys work.
- `firectl` 1.8.22 lives in `bin/` and runs through `bin/fw`, which reads the key from `.env`. Nothing is written to `~/.fireworks`.

**Teacher candidates (serverless; $ per 1M tokens, input / cached / output)**

| Model | Price |
|---|---|
| Kimi K3 | $3.00 / $0.30 / $15.00 |
| GLM 5.3 | $1.40 / $0.26 / $4.40 |
| Qwen 3.8 Max | $2.00 / $0.25 / $6.00 |
| DeepSeek V4.1 Flash | $0.30 / $0.006 / $1.20 |
| gpt-oss-120b | $0.15 / $0.015 / $0.60 |

- **DeepSeek V4 Pro is not serverless on this account**, so it's out.
- **Check each winner's licence before generating** (Qwen "Max" may not be open-weight).

**Student**
- `qwen3-8b`: tunable, LoRA, 40,960 context, **not serverless**. Its baseline needs an on-demand H100 (~$8/h, about 1 h).
- `qwen3p5-9b`: supervised-LoRA tunable, 131k training context. A newer alternative.

**OpenAI:** `gpt-5.5` is also available.

### 10d. Decided 2026-11-01 (late)
- **Student: Qwen3.5-9B.** Training costs the same (the ≤16B tier).
- **Question list approved; more questions are fine.** Add 2 frontend questions and 1 web-backend question, kept as local fixtures (`questions/new/`). Nothing is written to the production bank.

| Track | Train | Test (2 held out per track) |
|---|---|---|
| Embedded | 561, 562, 563, 565, 566, 584, 586 | 568, 567 |
| Frontend | 533, 534, 518, new-fe-1, new-fe-2 | 535, new-fe-3 |
| Backend | 611, 426, 589, 588, new-be-1 | 427, 490, 517 (drawing) |
| AI / agents | 493, 494, 496, 498, 501, 507, 514 | 502, 503, 606 (drawing) |
| Learn (Rust; Study + Assess) | 614, 615, 616, 617, 618, 620, 621, 622, 624, 626, 627, 628 | 619, 623, 625 |

New questions to write as local fixtures: **3 frontend + 1 web-backend.**

### 10e. How the teacher is picked (fixed before any results)

The **frontier we compare against is always Opus**; it is never "picked". This rule only chooses which open model writes the training data:

1. **Licence gate:** the licence must allow training on its outputs. Otherwise the model is a comparison dot only.
2. **Hard gates on the full test set:** valid format ≥ 98%; leak rate ≤ Opus's + 2 points.
3. **Rank by headline score vs Opus, per task** (Interview, Assess, Study), with 95% bootstrap confidence intervals.
4. **One teacher per task is allowed.** Training examples are independent, so different tasks can come from different teachers if different models win.
5. **Ties** (overlapping confidence intervals): pick the cheaper one, since more data fits the budget, or split the turns between the tied models.
6. **The user signs off:** leaderboard with intervals, plus 20 random turns side by side (Opus vs the top 2). Generation starts only after the OK.

## 11. Risks

| Risk | Mitigation |
|---|---|
| The open teacher is clearly below Opus | report the gap honestly; the student is judged against both; pick the best teacher in the bake-off |
| The tuned model still leaks | DPO; more data on that slice; a code-level leak check in production |
| JSON schema not enforced on the deployment | validate and retry once; SFT makes the format reliable |
| Study prompts over 32k | trim files to what the turn needs, or a longer context |
| Rate limits slow the 10K run | start tonight; top up overnight; the generator resumes |
| Simulated candidates aren't realistic | candidate-type and style mix, gold review, a local comparison with the 323 production traces |
| Judge bias | calibrate against 30 hand labels; lead with the code-checked scores |
