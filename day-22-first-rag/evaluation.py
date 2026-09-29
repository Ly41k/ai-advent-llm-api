"""Evaluation helpers for the ten Day 22 control questions."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean


QUESTIONS = Path(__file__).with_name("questions.json")


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    if len(items) != 10:
        raise ValueError("Day 22 requires exactly 10 control questions")
    required = {"question", "expectation", "expected_terms", "expected_sources"}
    for number, item in enumerate(items, 1):
        if not required.issubset(item):
            raise ValueError(f"Question {number} is missing required fields")
        if not item["question"] or not item["expectation"]:
            raise ValueError(f"Question {number} has an empty question or expectation")
        if not isinstance(item["expected_terms"], list) or not item["expected_terms"]:
            raise ValueError(f"Question {number} needs expected_terms")
        if not isinstance(item["expected_sources"], list):
            raise ValueError(f"Question {number} expected_sources must be a list")
    return items


def _term_diagnostics(answer: str, terms: list[str]) -> dict:
    folded = answer.casefold()
    checks = {term: term.casefold() in folded for term in terms}
    coverage = sum(checks.values()) / len(checks) if checks else 1.0
    return {"checks": checks, "coverage": round(coverage, 4)}


def _source_diagnostics(actual: list[str], expected: list[str]) -> dict:
    expected_set = set(expected)
    matched = [source for source in actual if source in expected_set]
    return {
        "expected": expected,
        "actual": actual,
        "matched": matched,
        "all_expected_found": expected_set.issubset(set(actual)) if expected else True,
        "any_expected_found": bool(matched) if expected else True,
    }


def evaluate_questions(agent, questions: list[dict]) -> dict:
    details = []
    for number, item in enumerate(questions, 1):
        comparison = agent.compare(item["question"])
        no_rag_terms = _term_diagnostics(
            comparison.without_rag.answer, item["expected_terms"]
        )
        rag_terms = _term_diagnostics(
            comparison.with_rag.answer, item["expected_terms"]
        )
        rag_sources = [hit.source for hit in comparison.with_rag.sources]
        source_check = _source_diagnostics(rag_sources, item["expected_sources"])
        delta = round(rag_terms["coverage"] - no_rag_terms["coverage"], 4)
        details.append(
            {
                "number": number,
                "question": item["question"],
                "expectation": item["expectation"],
                "expected_terms": item["expected_terms"],
                "expected_sources": item["expected_sources"],
                "without_rag": {
                    "answer": comparison.without_rag.answer,
                    "expected_terms": no_rag_terms,
                },
                "with_rag": {
                    "answer": comparison.with_rag.answer,
                    "expected_terms": rag_terms,
                    "sources": [
                        {
                            "source": hit.source,
                            "section": hit.section,
                            "start_line": hit.start_line,
                            "end_line": hit.end_line,
                            "cosine": round(hit.score, 6),
                        }
                        for hit in comparison.with_rag.sources
                    ],
                    "expected_source_check": source_check,
                },
                "comparison": {
                    "term_coverage_delta_rag_minus_no_rag": delta,
                    "rag_has_higher_term_coverage": delta > 0,
                    "same_term_coverage": delta == 0,
                },
            }
        )

    no_rag_coverages = [d["without_rag"]["expected_terms"]["coverage"] for d in details]
    rag_coverages = [d["with_rag"]["expected_terms"]["coverage"] for d in details]
    expected_source_checks = [
        d["with_rag"]["expected_source_check"]["any_expected_found"]
        for d in details
        if d["expected_sources"]
    ]
    summary = {
        "questions": len(details),
        "no_rag_mean_expected_term_coverage": round(mean(no_rag_coverages), 4),
        "rag_mean_expected_term_coverage": round(mean(rag_coverages), 4),
        "rag_minus_no_rag_mean_term_coverage": round(
            mean(rag_coverages) - mean(no_rag_coverages), 4
        ),
        "rag_expected_source_hit_rate": round(
            sum(expected_source_checks) / len(expected_source_checks), 4
        ) if expected_source_checks else None,
        "rag_higher_term_coverage_count": sum(
            d["comparison"]["rag_has_higher_term_coverage"] for d in details
        ),
        "same_term_coverage_count": sum(
            d["comparison"]["same_term_coverage"] for d in details
        ),
        "note": (
            "Expected-term coverage and source hits are reproducible diagnostics, "
            "not a substitute for human semantic review of answer correctness."
        ),
    }
    return {"summary": summary, "details": details}
