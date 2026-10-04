"""Ten positive questions plus separate negative controls, with auditable traces."""

import json
from pathlib import Path

from support24 import HERE

QUESTIONS = HERE / "questions.json"


def load_questions(path=QUESTIONS):
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("Questions must be a non-empty JSON array")
    ids = set()
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or
                item["id"] in ids or not isinstance(item.get("question"), str) or
                not item["question"].strip() or type(item.get("answerable")) is not bool):
            raise ValueError("Invalid question record or duplicate ID")
        ids.add(item["id"])
    return items


def evaluate(agent, items, progress=None):
    details = []
    for item in items:
        if progress:
            progress(f"{len(details) + 1}/{len(items)}: {item['id']}")
        result = agent.ask(item["question"]).to_dict()
        answered = result["status"] == "answered"
        sources_ok = bool(result["sources"]) and result["validation"]["sources_valid"]
        quotes_ok = bool(result["quotes"]) and result["validation"]["quotes_exact"]
        semantic_ok = answered and result["validation"]["semantic_supported"]
        extractive = result["validation"].get("proof_kind") == "verbatim_source_identity"
        verbatim_ok = (answered and extractive and result["validation"].get("verbatim_answer") is True
                       and all(len(c["citations"]) == 1 and c["text"] == c["citations"][0]["quote"]
                               for c in result["claims"]) and bool(result["claims"]))
        evidence_ok = (verbatim_ok and sources_ok and quotes_ok if extractive else semantic_ok and
                       result["validation"]["scope_supported"])
        diagnostic = extractive and result["validation"].get("coverage_policy") == "diagnostic"
        sources = {source["source"] for source in result["sources"]}
        expected = item.get("expected_sources", [])
        terms = item.get("expected_terms", [])
        well_formed_refusal = (not answered and bool(result["clarification"]) and
                               not result["sources"] and not result["quotes"])
        checks = {
            "contract_includes_model_coverage": not diagnostic,
            "has_sources": bool(result["sources"]), "has_quotes": bool(result["quotes"]),
            "sources_valid": sources_ok, "quotes_exact": quotes_ok,
            "semantic_supported_by_verifier": semantic_ok,
            "verbatim_answer": verbatim_ok,
            "answer_supported_by_evidence": evidence_ok,
            "scope_supported_by_auditor": answered and result["validation"]["scope_supported"],
            "coverage_supported_by_auditor": answered and result["validation"]["coverage_supported"],
            "expected_source_hit": bool(sources.intersection(expected)) if expected else None,
            "expected_term_coverage": (sum(term.casefold() in result["answer"].casefold()
                                            for term in terms) / len(terms)) if terms else None,
            "well_formed_refusal": well_formed_refusal,
            "correct_refusal": not item["answerable"] and well_formed_refusal,
        }
        passed = (answered and sources_ok and quotes_ok and evidence_ok and
                  (diagnostic or checks["coverage_supported_by_auditor"]) if item["answerable"]
                  else checks["correct_refusal"])
        details.append({"id": item["id"], "question": item["question"],
                        "answerable": item["answerable"],
                        "expectation": item.get("expectation", ""), "checks": checks,
                        "contract_pass": passed, "result": result,
                        "manual_review": {"answer_matches_quotes": None,
                                          "fully_answers_question": None, "notes": ""}})
    positives = [row for row in details if row["answerable"]]
    negatives = [row for row in details if not row["answerable"]]
    return {
        "run_type": ("live Ollama; exact extractive answers; model coverage is not independent human review"
                     if all(row["result"]["validation"].get("proof_kind") == "verbatim_source_identity"
                            for row in details) else
                     "live Ollama; model self-verification is not independent human review"),
        "summary": {"questions": len(details),
                    "diagnostic_positive_questions": sum(not row["checks"]["contract_includes_model_coverage"] for row in positives),
                    "positive_flagged_for_manual_review": sum(row["result"]["validation"].get("manual_review_required") is True for row in positives),
                    "assignment_complete": False, "positive_questions": len(positives),
                    "answered_positive": sum(row["result"]["status"] == "answered" for row in positives),
                    "positive_with_sources": sum(row["checks"]["has_sources"] for row in positives),
                    "positive_with_quotes": sum(row["checks"]["has_quotes"] for row in positives),
                    "positive_semantic_verifier_pass": sum(row["checks"]["semantic_supported_by_verifier"]
                                                           for row in positives),
                    "positive_evidence_support_pass": sum(row["checks"]["answer_supported_by_evidence"]
                                                           for row in positives),
                    "positive_verbatim_answer_pass": sum(row["checks"]["verbatim_answer"] for row in positives),
                    "positive_coverage_pass": sum(row["checks"]["coverage_supported_by_auditor"]
                                                  for row in positives),
                    "negative_questions": len(negatives),
                    "correct_negative_refusals": sum(row["checks"]["correct_refusal"] for row in negatives),
                    "contract_pass": sum(row["contract_pass"] for row in details),
                    "all_contract_checks_pass": all(row["contract_pass"] for row in details)},
        "limitations": ["Diagnostic coverage policy checks the source/quote contract only: a negative or failed coverage assessment remains visible and requires manual review. It is not an automatic quality pass.","In extractive mode each answer passage equals its citation; this is text identity, not an LLM semantic verdict.",
                        "Verbatim extraction does not establish source truth, relevance or answer completeness.",
                        "Paraphrase mode remains fallible: the model may incorrectly approve unsupported relationships.",
                        "Expected source/term diagnostics do not prove correctness or completeness.",
                        "Fill manual_review after inspecting every answer and quote; null means not reviewed."],
        "details": details,
    }


def markdown_report(report):
    lines = ["# Day 24 — citations and grounding", "", report["run_type"], "",
             "```json", json.dumps(report["summary"], ensure_ascii=False, indent=2), "```", ""]
    for row in report["details"]:
        result = row["result"]
        lines.extend([f"## {row['id']}", "", row["question"], "", result["answer"], ""])
        if result["validation"].get("manual_review_required"):
            lines.extend(["Coverage assessment requires manual review; its negative or failed judgment remains in the JSON trace.", ""])
        if result["clarification"]:
            lines.extend([result["clarification"], ""])
        for source in result["sources"]:
            lines.append(f"[{source['id']}] {source['source']} | {source['section']} | {source['chunk_id']}")
        for quote in result["quotes"]:
            lines.extend(["", f"Claim {quote['claim_id']}, source [{quote['source_id']}]:",
                          "", *["> " + line for line in quote["quote"].splitlines()]])
        lines.extend(["", "Checks: " + json.dumps(row["checks"], ensure_ascii=False), "",
                      "Review: " + json.dumps(row["manual_review"], ensure_ascii=False), ""])
    lines.extend(["## Limits", "", *["- " + value for value in report["limitations"]], ""])
    return "\n".join(lines)


def save_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    path.with_suffix(".md").write_text(markdown_report(report), encoding="utf-8")
