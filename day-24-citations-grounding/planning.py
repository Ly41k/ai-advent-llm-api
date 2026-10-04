"""Evidence selection and answer coverage are separate, strictly validated stages."""

import re

from evidence import EvidenceError, keys, parse_json, text

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["status", "parts"], "properties": {
        "status": {"type": "string", "enum": ["ready", "unknown"]},
        "parts": {"type": "array", "maxItems": 4, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["need", "quote_ids"], "properties": {
                "need": {"type": "string", "minLength": 1, "maxLength": 300},
                "quote_ids": {"type": "array", "minItems": 1, "maxItems": 4,
                              "items": {"type": "string"}}}}}}}

COVERAGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["checks"], "properties": {
        "checks": {"type": "array", "minItems": 1, "maxItems": 8, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "answer_excerpt", "reason", "covered"], "properties": {
                "id": {"type": "string"},
                "answer_excerpt": {"type": "string", "maxLength": 800},
                "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                "covered": {"type": "boolean"}}}}}}


def compact_catalog(catalog):
    """Suppress redundant subfragments, preserving exact text, IDs and source order.

    A whole Markdown list/table usually carries the condition that a lone row
    misses. The complete original catalog remains in the trace for inspection.
    """
    return {qid: row for qid, row in catalog.items()
            if not any(other["chunk_id"] == row["chunk_id"] and
                       len(other["quote"]) > len(row["quote"]) and
                       row["quote"] in other["quote"]
                       for other in catalog.values())}


def validate_plan(raw, catalog):
    value = parse_json(raw)
    keys(value, ("status", "parts"))
    if value["status"] == "unknown":
        if value["parts"] != []:
            raise EvidenceError("An unknown evidence plan must have no parts")
        return value, {}
    if value["status"] != "ready" or not isinstance(value["parts"], list) or not 1 <= len(value["parts"]) <= 4:
        raise EvidenceError("A ready evidence plan requires 1–4 requested parts")
    selected, needs = {}, set()
    for part in value["parts"]:
        keys(part, ("need", "quote_ids"))
        need = text(part["need"], 300)
        if need.casefold() in needs:
            raise EvidenceError("Duplicate requested part")
        needs.add(need.casefold())
        ids = part["quote_ids"]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 4:
            raise EvidenceError("Each requested part requires 1–4 quote IDs")
        seen = set()
        for qid in ids:
            text(qid, 128)
            if qid in seen or qid not in catalog:
                raise EvidenceError("Duplicate or unknown evidence quote ID")
            seen.add(qid)
            selected[qid] = catalog[qid]
    if len(selected) > 12 or sum(len(row["quote"]) for row in selected.values()) > 8000:
        raise EvidenceError("Select at most 12 quotations / 8000 characters of direct evidence")
    return value, selected


def coverage_requirements(question, plan):
    """Generic question criteria. No expected answers, question IDs or lesson rules."""
    result = [{"id": "question", "need": "Answer the original question in full, including every requested part."}]
    # Evidence-selection labels are not user requirements. A selector may
    # describe incidental source facts; coverage is derived only from the question.
    how = re.search(r"(?:\bhow\b|\bкак\b)", question, re.I)
    if re.search(r"\bhow\s+(?:many|much|long|far|often|old)\b|\bкак\s+(?:часто|называ|зовут)", question, re.I):
        how = None  # A count, frequency or name question need not explain a mechanism.
    verify = how and re.search(
        r"\b(?:verif(?:y|ied|ies|ication)|check(?:ed|ing)?|confirm(?:ed|ation)?|prov(?:e|en)|test(?:ed|ing)?)\b|провер|убед|подтверд",
        question, re.I)
    if verify:
        result.extend([
            {"id": "verification-action", "need": "Explain the actual checks/actions to perform."},
            {"id": "verification-observation", "need": "Explain the observable result that confirms the requested behavior. If recurring behavior is asked about, commands or process liveness alone do not demonstrate recurring outputs."},
        ])
    elif how:
        result.append({"id": "mechanism", "need": "Explain the requested mechanism or sequence; merely naming a feature, database or identifier is insufficient."})
    return result


def validate_coverage(raw, requirements, claims, *, disjoint_verification=False):
    value = parse_json(raw)
    keys(value, ("checks",))
    rows = value["checks"]
    if not isinstance(rows, list) or len(rows) != len(requirements):
        raise EvidenceError("Coverage must check every requirement exactly once")
    expected = {row["id"] for row in requirements}
    answer = "\n".join(claim["text"] for claim in claims)
    seen = set()
    for row in rows:
        keys(row, ("id", "answer_excerpt", "reason", "covered"))
        ident = text(row["id"], 128)
        if ident in seen or ident not in expected:
            raise EvidenceError("Invalid or duplicate coverage requirement ID")
        seen.add(ident)
        text(row["reason"], 500)
        if type(row["covered"]) is not bool:
            raise EvidenceError("Coverage covered must be boolean")
        excerpt = row["answer_excerpt"]
        if not isinstance(excerpt, str) or len(excerpt) > 800:
            raise EvidenceError("Coverage excerpt must be bounded text")
        if row["covered"]:
            if not excerpt.strip() or normalize_space(excerpt) not in normalize_space(answer):
                raise EvidenceError("A covered requirement needs the same words from answer text (whitespace may differ), not from quotations")
        elif excerpt != "":
            raise EvidenceError("An uncovered requirement must have an empty excerpt")
    # An observation cannot be justified by reusing the exact command/check
    # excerpt. This guards a concrete format error; entailment remains semantic.
    by_id = {row["id"]: row for row in rows}
    action, observation = by_id.get("verification-action"), by_id.get("verification-observation")
    if action and observation and action["covered"] and observation["covered"]:
        if normalize_space(action["answer_excerpt"]) == normalize_space(observation["answer_excerpt"]):
            raise EvidenceError("Verification needs separate action and observable-result excerpts")
        if disjoint_verification:
            a = normalize_space(action["answer_excerpt"])
            o = normalize_space(observation["answer_excerpt"])
            if a in o or o in a:
                raise EvidenceError("An observable-result excerpt must not contain or be contained in the action excerpt")
    return value, all(row["covered"] for row in rows)


def normalize_space(value):
    """For answer coverage ONLY. Source quotations remain byte-for-byte exact."""
    return " ".join(value.split())


def evidence_groups(plan):
    return [{"id": f"e{i}", "quote_ids": part["quote_ids"]}
            for i, part in enumerate(plan["parts"], 1)]


def bind_grouped_draft(raw, groups, selected):
    """Resolve selected evidence groups in application code; never invent facts.

    The generator cannot drop one fragment of a jointly selected proof. Its
    entire chosen group is cited, then checked by the ordinary draft/fact gates.
    This does NOT treat an evidence plan as a truthful answer.
    """
    from evidence import MAX_CLAIMS
    value = parse_json(raw)
    keys(value, ("status", "claims"))
    if value["status"] == "unknown":
        if value["claims"] != []:
            raise EvidenceError("Unknown responses cannot contain factual claims")
        return raw
    if value["status"] != "answered" or not isinstance(value["claims"], list) or not 1 <= len(value["claims"]) <= MAX_CLAIMS:
        raise EvidenceError("Require 1–3 grounded claims")
    by_id = {g["id"]: g for g in groups}
    claims = []
    for claim in value["claims"]:
        keys(claim, ("text", "evidence_group"))
        statement = text(claim["text"], 800)
        group_id = text(claim["evidence_group"], 128)
        if group_id not in by_id:
            raise EvidenceError("Unknown evidence_group; choose one supplied group")
        citations = []
        for qid in by_id[group_id]["quote_ids"]:
            if qid not in selected:
                raise EvidenceError("Evidence group contains an unselected quote")
            citations.append({"chunk_id": selected[qid]["chunk_id"], "quote_id": qid})
        claims.append({"text": statement, "citations": citations})
    import json
    return json.dumps({"status": "answered", "claims": claims}, ensure_ascii=False)
