"""Gold source retrieval metrics, plus an explicitly separate answer review."""

import json
from pathlib import Path

from retrieval import answer_question, context_for, retrieve


QUESTIONS = Path(__file__).with_name("questions.json")


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    items = json.loads(path.read_text(encoding="utf-8"))
    if not items or any(not q.get("question") or not q.get("source") for q in items):
        raise ValueError("Each gold question needs a question and source")
    return items


def evaluate_retrieval(kb, provider, strategy: str, questions: list[dict],
                       top_k: int = 5, rerank_model: str | None = None) -> dict:
    details = []
    for item in questions:
        hits = retrieve(kb, provider, strategy, item["question"], top_k, rerank_model)
        rank = next((i for i, hit in enumerate(hits, 1)
                     if hit.source == item["source"]), None)
        details.append({"question": item["question"], "expected_source": item["source"],
                        "rank": rank, "top_sources": [h.source for h in hits]})
    total = len(details)
    return {"strategy": strategy, "queries": total, "recall_at_1":
            sum(x["rank"] == 1 for x in details) / total,
            "recall_at_k": sum(x["rank"] is not None for x in details) / total,
            "mrr_at_k": sum(1 / x["rank"] for x in details
                            if x["rank"] is not None) / total,
            "details": details}


def answer_review(kb, provider, strategy: str, item: dict,
                  rerank_model: str | None = None) -> dict:
    """Produce evidence for human review; lexical checks are diagnostic only."""
    hits = retrieve(kb, provider, strategy, item["question"], rerank_model=rerank_model)
    answer = answer_question(provider, item["question"], hits)
    expected = item.get("expected_terms", [])
    return {"question": item["question"], "answer": answer,
            "expected_terms_present": {term: term.casefold() in answer.casefold()
                                       for term in expected},
            "context": context_for(hits),
            "review": {"retrieval_relevant": None, "claims_supported_by_context": None,
                       "answer_correct_against_reference": None,
                       "notes": "Fill these fields after inspecting source and answer."}}
