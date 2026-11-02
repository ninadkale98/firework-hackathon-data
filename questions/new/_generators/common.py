"""Shared helpers for writing the local interview-question fixtures."""
import json
from pathlib import Path

OUT = Path("/Users/ninad/codepraxis/fullstack_v2/hackathon/fireworks-distill/questions/new")
TEMPLATE = Path("/Users/ninad/codepraxis/fullstack_v2/hackathon/fireworks-distill/questions/templates/q533.json")
EXCLUDED = {"id", "company_id", "created_at", "updated_at", "generated_for_assignment_id"}


def repo_form(files: dict) -> str:
    paths = sorted(files)
    head = [f"Repository, {len(paths)} files:"] + [f"  {p}" for p in paths]
    body = []
    for p in paths:
        body.append(f"--- {p} ---\n{files[p].rstrip()}\n")
    return "\n".join(head) + "\n\n" + "\n".join(body)


def repo_entity(eid, name, files):
    text_bytes = sum(len(v.encode()) for v in files.values())
    return {"id": eid, "type": "repo", "source": "author",
            "meta": {"files": len(files), "filename": name, "text_bytes": text_bytes},
            "normalized_form": repo_form(files)}


def code_entity(eid, filename, text):
    text = text.strip("\n") + "\n"
    return {"id": eid, "type": "code", "source": "author",
            "meta": {"lines": text.count("\n"), "filename": filename},
            "normalized_form": text}


def md_entity(eid, filename, text):
    return {"id": eid, "type": "markdown", "source": "author",
            "meta": {"filename": filename}, "normalized_form": text.strip("\n") + "\n"}


def image_entity(eid, filename, text):
    return {"id": eid, "type": "image", "source": "author",
            "meta": {"filename": filename, "content_type": "image/png", "normalized_by": "author"},
            "normalized_form": text.strip("\n") + "\n"}


def excalidraw_entity(eid, filename, text):
    return {"id": eid, "type": "excalidraw", "source": "author",
            "meta": {"filename": filename}, "normalized_form": text.strip("\n") + "\n"}


def line_of(text: str, needle: str) -> int:
    hits = [i + 1 for i, line in enumerate(text.split("\n")) if needle in line]
    assert len(hits) == 1, (needle, hits)
    return hits[0]


def probe(pid, description, solution, withheld, hints, duration, entities, editable=(), highlights=(), nxt=()):
    return {"id": pid, "next": list(nxt),
            "hints": [{"id": i + 1, "text": h, "entities": []} for i, h in enumerate(hints)],
            "duration": duration, "editable": list(editable), "entities": list(entities),
            "run": [], "solution": solution, "highlights": list(highlights),
            "description": description, "withheld_solution_parts": list(withheld)}


def hints(texts):
    return [{"id": i + 1, "text": t, "entities": []} for i, t in enumerate(texts)]


def check_and_write(slug, question, entities):
    tmpl = json.loads(TEMPLATE.read_text())
    need = set(tmpl) - EXCLUDED
    missing = need - set(question)
    assert not missing, missing
    extra = set(question) - need
    assert not extra, extra
    ids = {e["id"] for e in entities}
    used = {r["id"] for r in question["entity_refs"]}

    def low(s):
        return s.lower()

    # seed-level withheld phrases
    seed_text = question["seed_question"] + " ".join(h["text"] for h in question["seed_hints"])
    key_text = json.dumps(question["answer_key"]).lower()
    for w in question["withheld_solution_parts"]:
        assert low(w) not in low(seed_text), ("seed leaks", w)
        assert low(w) in key_text, ("seed withheld not in answer key", w)

    depth = 0
    total = question["seed_duration"]
    node = question["probes"]
    while node:
        assert len(node) == 1
        p = node[0]
        depth += 1
        total += p["duration"]
        stage = p["description"] + " ".join(h["text"] for h in p["hints"])
        for w in p["withheld_solution_parts"]:
            assert low(w) not in low(stage), ("probe leaks", p["description"][:40], w)
            assert low(w) in low(p["solution"]), ("withheld not in solution", w)
            # no later stage prompt reveals an earlier withheld phrase either
        for e in p["entities"]:
            assert e in ids, e
            used.add(e)
        for e in p["editable"]:
            assert e in p["entities"], e
        for h in p["highlights"]:
            assert h["entity_id"] in used
        node = p["next"]
    assert depth == question["max_probes"] == 3, depth
    assert total == question["duration"], (total, question["duration"])
    assert used == ids, (used, ids)
    for h in question["seed_highlights"]:
        assert h["entity_id"] in {r["id"] for r in question["entity_refs"]}
    assert len(question["name"]) <= 80
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{slug}.json"
    path.write_text(json.dumps({"question": question, "entities": entities}, indent=2, ensure_ascii=False) + "\n")
    json.loads(path.read_text())
    print("wrote", path, path.stat().st_size, "bytes")
