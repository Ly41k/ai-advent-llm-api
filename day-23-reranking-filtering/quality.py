"""Labeled retrieval diagnostics, answer review, and calibration/holdout separation."""

from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import re
from statistics import mean

from rag23 import MODES, Settings, select_hits


QUESTIONS = Path(__file__).with_name("questions.json")


def load_questions(path: Path = QUESTIONS):
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise ValueError("Question set must be a non-empty list")
    ids = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Every question must be an object")
        required = {"id", "question", "expectation", "expected_terms", "expected_sources",
                    "answerable", "split"}
        if not required <= item.keys():
            raise ValueError("Question lacks required labels")
        if any(not isinstance(item[k], str) or not item[k].strip()
               for k in ("id", "question", "expectation")) or item["id"] in ids:
            raise ValueError("Question IDs must be unique; text fields must be non-empty")
        ids.add(item["id"])
        for key in ("expected_sources", "expected_terms"):
            if (not isinstance(item[key], list) or
                    any(not isinstance(v, str) or not v.strip() for v in item[key])):
                raise ValueError(f"Invalid {key}")
        if type(item["answerable"]) is not bool or item["split"] not in ("calibration", "evaluation"):
            raise ValueError("Invalid answerability or split")
        if item["answerable"] != bool(item["expected_sources"]):
            raise ValueError("Positive questions need sources; negative questions must have none")
    return items


def metrics(hits, item):
    expected = set(item["expected_sources"])
    ranks = [i for i, hit in enumerate(hits, 1) if hit.source in expected]
    return {"source_hit": bool(ranks) if expected else None,
            "source_precision": len(ranks) / len(hits) if hits else 0.0,
            "reciprocal_rank": 1 / ranks[0] if ranks else 0.0,
            "abstained": not hits, "selected_count": len(hits),
            "negative_abstention": not hits if not item["answerable"] else None}


def _average(values):
    return round(mean(values), 6) if values else None


def summarize(rows):
    positives = [r for r in rows if r["source_hit"] is not None]
    negatives = [r for r in rows if r["negative_abstention"] is not None]
    return {"questions": len(rows), "positive_questions": len(positives),
            "negative_questions": len(negatives),
            "source_hit_rate": _average([r["source_hit"] for r in positives]),
            "mean_source_precision": _average([r["source_precision"] for r in positives]),
            "mrr": _average([r["reciprocal_rank"] for r in positives]),
            "negative_abstention_rate": _average([r["negative_abstention"] for r in negatives]),
            "positive_empty_rate": _average([r["abstained"] for r in positives]),
            "mean_selected_count": _average([r["selected_count"] for r in rows]),
            "mean_context_words": _average([r["context_words"] for r in rows
                                            if "context_words" in r]),
            "mean_expected_term_coverage": _average([r["term_coverage"] for r in positives
                                                     if r.get("term_coverage") is not None])}


def evaluate(agent, questions, generate=True, progress=None):
    details, by_mode = [], {mode: [] for mode in MODES}
    for number, item in enumerate(questions, 1):
        if progress:
            progress(f"Question {number}/{len(questions)}: {item['id']}")
        results = agent.compare(item["question"], generate=generate)
        record = {**item, "modes": {}}
        for mode, result in results.items():
            checks = metrics(result.sources, item)
            checks["context_words"] = sum(len(hit.text.split()) for hit in result.sources)
            terms = item["expected_terms"]
            checks["term_coverage"] = (sum(t.casefold() in result.answer.casefold() for t in terms) /
                                       len(terms)) if result.answer is not None and terms else None
            # This records refusal language only, not whether a refusal is semantically justified.
            checks["answer_refusal_detected"] = bool(re.search(
                r"do not know|don't know|no relevant context|не знаю|недостаточно",
                result.answer or "", re.IGNORECASE)) if generate else None
            by_mode[mode].append(checks)
            record["modes"][mode] = {**result.to_dict(), "diagnostics": checks,
                                    "human_review": {"retrieval_relevance_0_2": None,
                                                     "answer_supported_0_2": None,
                                                     "answer_correctness_0_2": None,
                                                     "notes": ""}}
        details.append(record)
    summaries = {mode: summarize(rows) for mode, rows in by_mode.items()}
    deltas = {}
    for treatment, control in (("filter", "baseline"), ("rewrite", "baseline"),
                               ("rewrite_filter", "baseline"), ("rewrite_filter", "rewrite")):
        deltas[f"{treatment}_minus_{control}"] = {
            key: round(summaries[treatment][key] - summaries[control][key], 6)
            for key in summaries[treatment]
            if key not in ("questions", "positive_questions", "negative_questions")
            and summaries[treatment][key] is not None and summaries[control][key] is not None}
    return {"settings": asdict(agent.settings), "index": agent.kb.info(agent.settings.strategy),
            "embedding_model": agent.provider.model,
            "answer_model": getattr(agent.provider, "answer_model", None) if generate else None,
            "generated_answers": generate, "splits": sorted({q['split'] for q in questions}),
            "summary": summaries, "deltas": deltas, "details": details,
            "limitations": [
                "Source precision/hit/MRR use labeled source documents, not passage-level semantic judgments.",
                "Labels may omit other valid sources. Expected-term coverage is not answer correctness.",
                "A threshold can discard correct evidence; inspect positive_empty_rate and the full context.",
                "Human review fields are intentionally unfilled. Improvements are not guaranteed."]}


def calibrate(agent, questions, thresholds):
    items = [q for q in questions if q["split"] == "calibration"]
    if not any(q["answerable"] for q in items) or not any(not q["answerable"] for q in items):
        raise ValueError("Calibration needs both positive and negative calibration questions")
    if not thresholds or any(not math.isfinite(t) or not -1 <= t <= 1 for t in thresholds):
        raise ValueError("Threshold grid must contain finite raw cosine values in [-1, 1]")
    # Cache candidates: threshold sweeps do not re-embed/rewrite or generate answers.
    pools = [(item, agent.compare(item["question"], generate=False)) for item in items]
    reference = summarize([metrics(results["rewrite"].sources, item) for item, results in pools])
    sweeps = []
    for threshold in sorted(set(thresholds)):
        setting = replace(agent.settings, min_similarity=threshold)
        reports = {}
        for mode, raw_mode in (("filter", "baseline"), ("rewrite_filter", "rewrite")):
            rows = []
            for item, results in pools:
                # Result.candidates includes candidates dropped by final_k; reconstruct
                # score/provenance without text, which is unnecessary for calibration.
                from bridge import Hit
                hits = [Hit(c["chunk_id"], c["source"], c["section"], "", c["cosine"],
                            c["start_line"], c["end_line"])
                        for c in results[raw_mode].candidates]
                chosen, _, _ = select_hits(hits, setting, True)
                rows.append(metrics(chosen, item))
            reports[mode] = summarize(rows)
        score = reports["rewrite_filter"]
        balanced = (score["source_hit_rate"] + score["negative_abstention_rate"]) / 2
        preserves_evidence = (score["source_hit_rate"] >= reference["source_hit_rate"] and
                              score["positive_empty_rate"] <= reference["positive_empty_rate"])
        sweeps.append({"threshold": threshold, "balanced_score": balanced,
                       "eligible_for_selection": preserves_evidence, "modes": reports})
    allowed = [row for row in sweeps if row["eligible_for_selection"]]
    if not allowed:
        raise ValueError("No threshold preserves calibration evidence. Add lower values to --thresholds")
    # Prefer source precision on ties, then the least aggressive threshold.
    best = max(allowed, key=lambda row: (row["balanced_score"],
               row["modes"]["rewrite_filter"]["mean_source_precision"], -row["threshold"]))
    return {"selected_threshold": best["threshold"], "calibration_ids": [q["id"] for q in items],
            "settings": asdict(agent.settings), "embedding_model": agent.provider.model,
            "index": agent.kb.info(agent.settings.strategy), "sweep": sweeps,
            "unfiltered_rewrite_reference": reference,
            "selection_rule": "Preserve unfiltered rewrite source-hit rate and positive-empty rate on calibration; "
                              "then max balanced(positive source hit, negative abstention) for rewrite_filter; "
                              "tie: source precision, then lower threshold. No evaluation labels used.",
            "note": "Apply the selected threshold explicitly, then evaluate on the evaluation split."}


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def markdown_report(report):
    lines = ["# Day 23 — Mode comparison", "",
             f"Generated answers: {report['generated_answers']}; embedding: {report['embedding_model']}",
             f"Settings: `{json.dumps(report['settings'])}`", "",
             "| Mode | Source hit | Source precision | MRR | Negative abstention | Empty positives | Mean chunks |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for mode, row in report["summary"].items():
        values = [row[k] for k in ("source_hit_rate", "mean_source_precision", "mrr",
                                   "negative_abstention_rate", "positive_empty_rate", "mean_selected_count")]
        lines.append("| " + mode + " | " + " | ".join("—" if v is None else f"{v:.4f}" for v in values) + " |")
    lines += ["", *["- " + note for note in report["limitations"]], "",
              "See the JSON for query rewrites, candidate decisions, contexts, answers and review fields."]
    return "\n".join(lines) + "\n"
