"""Scripted extractive selection/coverage on real corpus; NOT a live model run."""

import json

from support24 import HERE, Hit
from fixture_proofs import scripted_proof_response
from strict_agent import StrictRAGAgent
from reference_check import FixtureKB, FixtureProvider, reference_inputs
from evaluate24 import load_questions, evaluate, save_report


class ExtractiveFixtureProvider(FixtureProvider):
    answer_model = "scripted-extractive-fixture; NOT an LLM"

    def structured(self, prompt, schema):
        if "covered" in schema["properties"]:
            self.calls.append(prompt)
            data, _ = json.JSONDecoder().raw_decode(prompt.split("DATA:\n", 1)[1])
            requirement = data["coverage_requirement"]
            answer = "\n".join(p["text"] for p in data["proof_units"])
            # AUTHOR-SCRIPTED passages for fixture coverage, never production rules.
            candidates = {
                "verification-action": [
                    "The final verification compares the report read from disk with the original summary.",
                    "journalctl -u bublik-day18 -f",
                    "Проверяйте `journalctl` и запрашивайте свежую сводку через агента."],
                "verification-observation": [
                    "the agent only reports success after `verified=true`.",
                    "печатает агрегированную сводку в журнал после каждого запуска.",
                    "writes an aggregate summary to stdout after each run."]}
            excerpt = next((c for c in candidates.get(requirement["id"], []) if c in answer),
                           answer.split("\n", 1)[0][:800])
            complete = self.verdict is None or self.verdict.get("answers_question") is True
            return json.dumps(scripted_proof_response(data, {"reason": "AUTHOR-SCRIPTED criterion coverage, NOT an LLM judgment",
                               "answer_excerpt": excerpt if complete else "", "covered": complete}))
        if "quote_ids" not in schema["properties"]:
            return super().structured(prompt, schema)
        self.calls.append(prompt)
        data, _ = json.JSONDecoder().raw_decode(prompt.split("DATA:\n", 1)[1])
        if self.draft.get("status") == "unknown":
            return json.dumps({"status": "unknown", "quote_ids": []})
        ids = []
        for claim in self.draft.get("claims", []):
            for ref in claim["citations"]:
                matches = [(len(q["text"]), q["quote_id"])
                           for h in data["chunks"] if h["chunk_id"] == ref["chunk_id"]
                           for q in h["quotes"] if ref["quote"] in q["text"]]
                if not matches:
                    raise ValueError("A reference quotation is unavailable in this context")
                qid = min(matches)[1]
                if qid not in ids:
                    ids.append(qid)
        return json.dumps({"status": "answered", "quote_ids": ids})


def main():
    inputs = reference_inputs()
    items = load_questions()
    by_question = {q["question"]: q for q in items}

    class Reference:
        def ask(self, question):
            item = by_question[question]
            if item["answerable"]:
                hits, authored = inputs[item["id"]]
            else:
                score = .8 if item["id"] == "negative-01" else .49
                hits = [Hit("negative", "README.md", "Course", "This course explains public GitHub snapshots.", score, 1, 1)]
                authored = {"status": "unknown", "claims": []}
            return StrictRAGAgent(FixtureKB(hits), ExtractiveFixtureProvider(authored)).ask(question)

    report = evaluate(Reference(), items)
    report["run_type"] = "OFFLINE: exact source answers; AUTHORED selection/coverage; NO live LLM or embedding"
    report["limitations"].insert(0, "Selection and coverage verdicts are scripted; this does not measure Qwen or bge-m3 quality.")
    save_report(HERE / "reports/offline_strict_reference.json", report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
