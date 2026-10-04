"""Replay ten assistant-authored cases against real corpus chunks; NOT a model run.

Retrieval is a controlled fixture, generation is scripted, and semantic verdicts
are pre-authored. This checks the contract, not bge-m3/Qwen answer quality.
"""

import json

from support24 import HERE, ROOT, Hit
from chunking import chunk_documents
from corpus import load_documents, revision
from evaluate24 import evaluate, load_questions, save_report
from grounded_agent import Day24RAGAgent


def with_coverage(verdict):
    """Upgrade AUTHOR-WRITTEN fixtures only; production never fills missing verdict fields."""
    value = json.loads(json.dumps(verdict))
    complete = value.get("answers_question") is True
    value.setdefault("coverage_reason", "Scripted complete reference answer." if complete else
                     "Scripted reference does not answer every requested fact.")
    value.setdefault("missing_information", [] if complete else ["The requested fact is missing."])
    return value


def scope_fixture(claims):
    """Author-scripted approvals for offline contract checks, never production evidence."""
    return {"claims": [{"id": i, "reason": "Author-scripted scope fixture; NOT an LLM judgment",
                        "unsupported_spans": [], "supported": True}
                       for i in range(1, len(claims) + 1)]}


def with_quote_ids(draft, prompt):
    """Adapt legacy authored fixtures to the new ID contract, without fabricating evidence."""
    draft = json.loads(json.dumps(draft))
    data, _ = json.JSONDecoder().raw_decode(prompt.split("DATA:\n", 1)[1])
    for claim in draft.get("claims", []):
        for ref in claim.get("citations", []):
            if set(ref) != {"chunk_id", "quote"}:
                continue
            if not isinstance(ref["quote"], str) or len(ref["quote"].strip()) < 12:
                continue
            matches = [(len(row["text"]), row["quote_id"])
                       for chunk in data["chunks"] if chunk["chunk_id"] == ref["chunk_id"]
                       for row in chunk["quotes"] if ref["quote"] in row["text"]]
            if matches:
                ref["quote_id"] = min(matches)[1]
                del ref["quote"]
    return draft


def with_group_ids(draft, prompt):
    """Offline fixtures only. Production accepts group IDs directly from the model."""
    data, _ = json.JSONDecoder().raw_decode(prompt.split("DATA:\n", 1)[1])
    mapped = with_quote_ids(draft, prompt)
    if mapped.get("status") != "answered":
        return mapped
    groups = data.get("evidence_groups", [])
    if set(mapped) != {"status", "claims"}:
        return mapped
    quote_chunks = {row["quote_id"]: chunk["chunk_id"]
                    for chunk in data["chunks"] for row in chunk["quotes"]}
    result = []
    for claim in mapped.get("claims", []):
        if set(claim) != {"text", "citations"}:
            return mapped
        refs = claim.get("citations", [])
        if not refs or any(set(r) != {"chunk_id", "quote_id"} for r in refs):
            return mapped  # Invalid fixtures remain invalid, never repaired with new facts.
        if any(quote_chunks.get(r["quote_id"]) != r["chunk_id"] for r in refs):
            return mapped
        ids = {r["quote_id"] for r in refs}
        matching = [g for g in groups if ids <= set(g["quote_ids"])]
        if not matching:
            return mapped
        group = min(matching, key=lambda g: len(g["quote_ids"]))
        result.append({"text": claim["text"], "evidence_group": group["id"]})
    return {"status": "answered", "claims": result}


class FixtureKB:
    def __init__(self, hits):
        self.hits = hits

    def info(self, strategy):
        return {"model": "controlled-fixture", "dimension": 2, "strategy": strategy,
                "revision": "fixture; real chunks from current corpus"}

    def search(self, strategy, vector, top_k):
        return self.hits[:top_k]


class FixtureProvider:
    model = "controlled-fixture"
    answer_model = "scripted-reference; NOT an LLM"

    def __init__(self, draft, verdict=None):
        self.draft, self.verdict = draft, verdict
        self.calls = []

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def structured(self, prompt, schema):
        self.calls.append(prompt)
        data, _ = json.JSONDecoder().raw_decode(prompt.split("DATA:\n", 1)[1])
        if "parts" in schema["properties"]:
            if self.draft.get("status") == "unknown":
                return json.dumps({"status": "unknown", "parts": []})
            mapped = with_quote_ids(self.draft, prompt)
            parts = []
            for i, claim in enumerate(mapped.get("claims", []), 1):
                ids = list(dict.fromkeys(ref["quote_id"] for ref in claim.get("citations", []) if "quote_id" in ref))
                if not ids:
                    ids = [row["quote_id"] for chunk in data["chunks"] for row in chunk["quotes"]][:4]
                parts.append({"need": f"Author-scripted requested evidence {i}", "quote_ids": ids[:4]})
            return json.dumps({"status": "ready", "parts": parts})
        if "checks" in schema["properties"]:
            complete = self.verdict is None or self.verdict.get("answers_question") is True
            # This is an AUTHOR-WRITTEN judgment, not a coverage measurement.
            sentence = data["answer_text"].split("\n", 1)[0][:800]
            lines = data["answer_text"].split("\n")
            last = lines[-1][:800]
            action = lines[-2][:800] if len(lines) >= 3 else sentence
            return json.dumps({"checks": [{"id": row["id"],
                "answer_excerpt": (last if row["id"] == "verification-observation" else action if row["id"] == "verification-action" else sentence) if complete else "",
                "reason": "Author-scripted coverage fixture; NOT an LLM judgment", "covered": complete}
                for row in data["requirements"]]})
        if "supported" in schema["properties"]:
            rows = self.verdict.get("claims", []) if self.verdict else []
            verdict = next((r for r in rows if r.get("id") == data["claim_id"]), None)
            return json.dumps({"reason": verdict["reason"] if verdict else "Author-scripted fact fixture; NOT an LLM judgment",
                               "supported": verdict["supported"] if verdict else True})
        return json.dumps(with_group_ids(self.draft, prompt), ensure_ascii=False)


def reference_inputs():
    cases = json.loads((HERE / "reference_cases.json").read_text(encoding="utf-8"))
    by_id = {chunk.chunk_id: chunk for chunk in chunk_documents(load_documents(ROOT), "fixed")}
    inputs = {}
    for case in cases:
        ids = list(dict.fromkeys(ref["chunk_id"] for claim in case["claims"] for ref in claim["citations"]))
        hits = []
        for chunk_id in ids:
            chunk = by_id[chunk_id]
            hits.append(Hit(chunk.chunk_id, chunk.source, chunk.section, chunk.text,
                            0.8, chunk.start_line, chunk.end_line))
        inputs[case["id"]] = (hits, {"status": "answered", "claims": case["claims"]})
    return inputs


def main():
    items = load_questions()
    inputs = reference_inputs()
    by_question = {item["question"]: inputs.get(item["id"], ([], {"status": "unknown", "claims": []}))
                   for item in items}

    class Replay:
        def ask(self, question):
            hits, draft = by_question[question]
            return Day24RAGAgent(FixtureKB(hits), FixtureProvider(draft)).ask(question)

    report = evaluate(Replay(), items)
    report["run_type"] = "OFFLINE controlled reference replay; real corpus chunks; NO LLM and NO semantic retrieval"
    report["source_revision"] = revision(ROOT)
    report["limitations"].insert(0, "Retrieval pools and semantic verdicts are scripted fixtures, not model measurements.")
    for row in report["details"]:
        if row["answerable"]:
            row["manual_review"] = {
                "answer_matches_quotes": True, "fully_answers_question": True,
                "notes": "Assistant-authored reference answer reviewed against supplied repository passages; not independent human/model evaluation."}
    save_report(HERE / "reports/offline_reference.json", report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
