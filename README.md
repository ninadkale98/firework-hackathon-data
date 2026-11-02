# firework-hackathon-data

The data behind [firework-hackathon](https://github.com/ninadkale98/firework-hackathon), published for the hackathon. It contains CodePraxis interview questions with their answer keys, rubrics and withheld parts, so these questions are no longer secret.

## What is here

| Path | What | Unpacked size |
|---|---|---|
| `data/distill.db.zst` | SQLite database (WAL checkpointed via `VACUUM INTO`). It holds every record:<br>• the frozen test set: 1,525 turns, Opus as reference;<br>• the training set: 9,577 turns, DeepSeek V4.1 Flash as teacher;<br>• every model's outputs (`runs`);<br>• every score and judge verdict (`scores`);<br>• the spend log | 675 MB |
| `data/export/dpo.jsonl` | DPO preference pairs, Fireworks format (`input.messages` system+user, `preferred_output`, `non_preferred_output`): 1,223 pairs. Preferred = DeepSeek V4.1 Flash teacher answer that passed the judge; non-preferred = **base Qwen3.5-9B**'s answer to the same training prompt, judged bad by DeepSeek V4.1 Flash (872 much worse than the teacher, 180 fail safety, 167 give the answer away, 4 invalid). Training split only, SFT validation sessions excluded. Uploaded on our account as `codepraxis-dpo-opta-v1`. For another student (e.g. Muse), regenerate the rejected side with its own answers: `python -m distill.dpo run --student <model> && python -m distill.dpo export --student <model>` | 39 MB |
| `data/dpo_prompts.json` | the 2,500 training-prompt ids the DPO pairs were drawn from | small |
| `data/export/test_eval.jsonl` | the frozen test set as one file for evaluating any model: 1,525 lines, each with `id`, `task`, `in_shared_sample` (the 300-turn judge sample), `messages` (system + user), `response_format` (the turn's JSON schema) and `reference_opus` | 47 MB |
| `data/export/train.jsonl.zst`, `val.jsonl.zst` | Fireworks SFT files: 8,361 + 682 lines, filtered by the GPT-5.4 judge | 261 MB + 22 MB |
| `data/bank.tar.zst` | the local question bank: 45 production rows + entities, plus the entity blobs | 21 MB |
| `data/board_site.json`, `coverage_*.html` | leaderboard aggregates, coverage reports | small |
| `questions/` | the production templates and the 4 new local questions (`new-fe-1..3`, `new-be-1`), with their generators | small |
| `PLAN.md` | the full plan and every decision made | |
| `logs/` | generation, judging and overnight logs | |

## Restore on a new machine

```bash
# 1. Code: the public repo, plus the private CodePraxis backend at the commit the data was made with
git clone https://github.com/ninadkale98/firework-hackathon.git fireworks-distill
git clone https://github.com/codepraxis-org/backend.git
(cd backend && git checkout ccee1c5 && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt \
   && .venv/bin/pip install jsonschema zstandard)

# 2. Data: this repo, unpacked into the code folder
git clone https://github.com/ninadkale98/firework-hackathon-data.git
cd fireworks-distill
mkdir -p data/export
zstd -d ../firework-hackathon-data/data/distill.db.zst -o data/distill.db
zstd -d ../firework-hackathon-data/data/export/train.jsonl.zst -o data/export/train.jsonl
zstd -d ../firework-hackathon-data/data/export/val.jsonl.zst -o data/export/val.jsonl
zstd -dc ../firework-hackathon-data/data/bank.tar.zst | tar -xf -        # -> data/bank/
cp ../firework-hackathon-data/data/*.json ../firework-hackathon-data/data/*.html data/
cp -R ../firework-hackathon-data/questions ../firework-hackathon-data/PLAN.md .

# 3. Keys (never committed): create .env in this folder
cat > .env <<'EOF'
FIREWORKS_API_KEY=...
DISTILL_OPENAI_API_KEY=...
EOF
# Claude runs use ANTHROPIC_API_KEY from ../backend/.env (or export it)

# 4. firectl (Fireworks CLI)
mkdir -p bin && curl -sS https://storage.googleapis.com/fireworks-public/firectl/stable/darwin-arm64.gz -o bin/firectl.gz \
  && gzip -df bin/firectl.gz && chmod +x bin/firectl
# bin/fw is in the code repo's .gitignore: recreate it (it adds --api-key from .env):
printf '#!/bin/sh\nDIR="$(cd "$(dirname "$0")/.." && pwd)"\nKEY="$(grep "^FIREWORKS_API_KEY=" "$DIR/.env" | cut -d= -f2-)"\nexec "$DIR/bin/firectl" --api-key "$KEY" "$@"\n' > bin/fw && chmod +x bin/fw

# 5. Check
PYTHONPATH=../backend:. ../backend/.venv/bin/python -m distill.coverage --split test
```

The code repo's paths assume `backend/` sits two levels above `fireworks-distill/` (`../../backend`). Either keep that layout (`fullstack_v2/backend` and `fullstack_v2/hackathon/fireworks-distill`), or set `PYTHONPATH` to wherever the backend lives.

## Where things stand (2026-11-02, 13:30)

- Baseline and leaderboard: done, see the public repo's `EVALUATION.md` and its GitHub Pages site.
- Training data: uploaded to Fireworks as `codepraxis-distill-train-v1` / `codepraxis-distill-val-v1`.
- SFT: LoRA on Qwen3.5-9B, 2 epochs, running (job `codepraxis-interviewer-sft-v1`, output model `codepraxis-interviewer-v1`).
- DPO pairs: base Qwen's answers to 2,500 risky training prompts, judged by DeepSeek V4.1 Flash, in progress.
- Final evaluation judge: DeepSeek V4.1 Flash (OpenAI credit ran out).
