"""Replay authored answers on stored v7 retrieval; no embeddings or live LLM.

This isolates availability of the required evidence from model capability. It
does not estimate v9's retrieval/selector/generation/auditor accuracy.
"""

import json

from support24 import HERE, Hit
from quote_catalog import build_catalog
from planning import compact_catalog
from reference_check import FixtureKB, FixtureProvider
from grounded_agent import Day24RAGAgent
from evaluate24 import evaluate, load_questions, save_report


def main():
    previous = json.loads((HERE / "reports/live/evaluate_v7_both14b_original.json").read_text())
    rows = {row["question"]: row for row in previous["details"]}
    cases = {case["id"]: case for case in json.loads((HERE / "reference_cases.json").read_text())}
    items = load_questions()
    items_by_question = {item["question"]: item for item in items}

    class Replay:
        def ask(self, question):
            item = items_by_question[question]
            hits = [Hit(**hit) for hit in rows[question]["result"]["retrieval"]["sources"]]
            draft = ({"status": "answered", "claims": cases[item["id"]]["claims"]}
                     if item["answerable"] else {"status": "unknown", "claims": []})
            return Day24RAGAgent(FixtureKB(hits), FixtureProvider(draft)).ask(question)

    report = evaluate(Replay(), items)
    report["run_type"] = "OFFLINE replay: stored user v7 selected chunks; AUTHORED answers and judgments; NO LLM/embedding calls"
    report["limitations"].insert(0, "All decisions and answers are scripted. This proves evidence availability and application gates, not live v9 quality.")
    sizes = []
    for row in previous["details"]:
        hits = [Hit(**hit) for hit in row["result"]["retrieval"]["sources"]]
        catalog = build_catalog(hits)
        sizes.append({"id": row["id"], "original_fragments": len(catalog),
                      "compact_fragments": len(compact_catalog(catalog))})
    report["catalog_diagnostics"] = sizes
    for row in report["details"]:
        if row["answerable"]:
            row["manual_review"] = {
                "answer_matches_quotes": True, "fully_answers_question": True,
                "notes": "Assistant-authored reference reviewed against source content; NOT independent human evaluation and NOT a live generated answer."}
    save_report(HERE / "reports/offline_v7_context_replay.json", report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
