"""Strict JSON, verbatim quotes, trusted provenance and claim-level validation."""

import json
import re


class EvidenceError(ValueError):
    pass


MAX_CLAIMS = 3


def requires_russian(question):
    return len(re.findall(r"[А-Яа-яЁё]", question)) >= 4


def validate_answer_language(claims, question):
    """Catch an entirely English answer to a Russian question; not a language classifier."""
    if not requires_russian(question):
        return
    for claim in claims:
        prose = re.sub(r"`[^`]*`", "", claim["text"])
        if not re.search(r"[А-Яа-яЁё]", prose):
            raise EvidenceError(
                f"Claim {claim['id']} has no Russian explanation for a Russian question. "
                "Write the answer in Russian; preserve code names and commands literally. "
                "Do not translate source quotations: choose their existing quote_ids.")


def python_filenames(value):
    """Literal Python file names, not inference about their runtime behavior."""
    return set(re.findall(r"(?<![\w.-])([A-Za-z_][A-Za-z0-9_.-]*\.py)(?![\w-]|\.[\w-])", value))


def marked_identifiers(value):
    """Simple ASCII code names explicitly marked with backticks, not free prose."""
    return set(re.findall(r"(?<!`)`([A-Za-z_][A-Za-z0-9_.-]*(?:\(\))?)`(?!`)", value))


def marked_commands(value):
    """Multiword inline ASCII code must be quoted literally, not inferred."""
    return {part for part in re.findall(r"(?<!`)`([^`\n]+)`(?!`)", value)
            if part.isascii() and " " in part and part.strip() == part}


def literal_identifier(name, value):
    # Bare code names are lexical components of a qualified route (both the
    # namespace and the method). Dots remain part of file/service/dotted names.
    suffix = r"(?![\w-])" if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else r"(?![\w.-])"
    return re.search(r"(?<![\w-])" + re.escape(name) + suffix, value) is not None


def repair_evidence_options(raw, catalog):
    """Repeat short retrieved fragments naming draft identifiers; never supply gold facts."""
    try:
        value = parse_json(raw)
    except EvidenceError:
        return []
    claims = value.get("claims")
    if not isinstance(claims, list):
        return []
    names = set()
    for claim in claims[:MAX_CLAIMS]:
        if isinstance(claim, dict) and isinstance(claim.get("text"), str):
            names.update(marked_identifiers(claim["text"]) | python_filenames(claim["text"]) |
                         marked_commands(claim["text"]))
    options, chars = [], 0
    for name in sorted(names)[:12]:
        matches = [(quote_id, row) for quote_id, row in catalog.items()
                   if literal_identifier(name, row["quote"])]
        matches.sort(key=lambda pair: (len(pair[1]["quote"]), pair[0]))
        for quote_id, row in matches[:2]:
            if chars + len(row["quote"]) > 4000:
                continue
            chars += len(row["quote"])
            options.append({"identifier": name, "quote_id": quote_id, **row})
    return options


def state_enums(value):
    """Recognize explicit Markdown field enumerations; never infer states from arrows."""
    values = set()
    for line in value.splitlines():
        cells = line.strip().strip("|").split("|")
        if len(cells) < 2 or cells[0].strip().strip("`").casefold() not in {"state", "stage"}:
            continue
        members = re.findall(r"`([A-Za-z_][A-Za-z0-9_-]*)`", cells[1])
        if len(members) >= 2 and ("," in cells[1] or " or " in cells[1] or " или " in cells[1]):
            values.update(members)
    return values


def declared_diagram_states(statement, citations):
    """A narrow contradiction check for a diagram label called a state in the answer."""
    names = set(re.findall(r"\b(?:a|an)\s+`?([A-Za-z_][A-Za-z0-9_-]*)`?\s+(?:state|stage)\b", statement))
    diagram_words = set()
    for ref in citations:
        quote = ref["quote"]
        if "```" in quote and ("→" in quote or "-->" in quote):
            diagram_words.update(re.findall(r"[A-Za-z_][A-Za-z0-9_-]*", quote))
    return names & diagram_words


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw):
    if not isinstance(raw, str) or len(raw) > 40000:
        raise EvidenceError("Expected bounded JSON text")
    def invalid_constant(value):
        raise EvidenceError(f"Invalid JSON constant: {value}")
    try:
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=invalid_constant)
    except (ValueError, RecursionError) as error:
        raise EvidenceError("Response must be one strict JSON object") from error
    if not isinstance(value, dict):
        raise EvidenceError("Response must be a JSON object")
    return value


def keys(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise EvidenceError(f"Require exactly these keys: {', '.join(required)}")


def text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise EvidenceError("Expected non-empty bounded text")
    return value


def validate_draft(raw, hits, catalog=None, *, max_claims=MAX_CLAIMS, statement_limit=800):
    """Do not trust model-produced paths, line numbers, IDs or quoted text."""
    value = parse_json(raw)
    if value.get("status") == "unknown":
        keys(value, ("status", "claims"))
        if value["claims"] != []:
            raise EvidenceError("Unknown responses cannot contain factual claims")
        return []
    keys(value, ("status", "claims"))
    if value["status"] != "answered":
        raise EvidenceError("Invalid response status")
    claims = value["claims"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= max_claims:
        raise EvidenceError(f"Require 1–{max_claims} concise supported claims; omit examples and unrelated facts")
    by_id = {hit.chunk_id: hit for hit in hits}
    validated, quote_chars = [], 0
    for index, claim in enumerate(claims, 1):
        keys(claim, ("text", "citations"))
        statement = text(claim["text"], statement_limit)
        refs = claim["citations"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 4:
            raise EvidenceError("Every claim requires 1–4 citations")
        citations, seen = [], set()
        for ref in refs:
            quote_id = None
            if catalog is not None:
                keys(ref, ("chunk_id", "quote_id"))
                quote_id = text(ref["quote_id"], 128)
                resolved = catalog.get(quote_id)
                if resolved is None:
                    raise EvidenceError("Unknown quote_id; select an ID from the supplied quote catalog")
                if resolved["chunk_id"] != ref["chunk_id"]:
                    raise EvidenceError("quote_id belongs to another chunk")
                ref = {"chunk_id": ref["chunk_id"], "quote": resolved["quote"]}
            else:
                # Offline legacy reference cases may still validate literal quotes.
                keys(ref, ("chunk_id", "quote"))
            chunk_id = text(ref["chunk_id"], 128)
            hit = by_id.get(chunk_id)
            if hit is None:
                raise EvidenceError("Citation references a chunk outside selected context")
            quote = text(ref["quote"], 1600)
            quote_chars += len(quote)
            if quote_chars > 8000:
                raise EvidenceError("Total quotations exceed 8000 characters; choose concise complete evidence")
            if len(quote.strip()) < 12 or quote not in hit.text:
                raise EvidenceError("Quote must be a verbatim contiguous chunk substring (12+ characters)")
            if (chunk_id, quote) in seen:
                raise EvidenceError("Duplicate citation within a claim")
            seen.add((chunk_id, quote))
            offset = hit.text.index(quote)
            start = hit.start_line + hit.text.count("\n", 0, offset)
            citations.append({"chunk_id": chunk_id, "quote": quote,
                              "source": hit.source, "section": hit.section,
                              "start_line": start, "end_line": start + quote.count("\n")})
            if quote_id is not None:
                citations[-1]["quote_id"] = quote_id
        cited_names = set().union(*(python_filenames(ref["quote"]) |
                                    python_filenames(ref["source"]) for ref in citations))
        missing_names = python_filenames(statement) - cited_names
        if missing_names:
            name = sorted(missing_names)[0]
            choices = [quote_id for quote_id, row in (catalog or {}).items()
                       if name in python_filenames(row["quote"])]
            raise EvidenceError(
                f"Claim {index} names {name}, absent from its cited quotations and source paths. "
                "Choose evidence that explicitly identifies this file as well as its behavior. "
                f"Available quote_ids naming the file (identity only, check behavior): {choices[:4]}. "
                "Do not use uncited context as proof; abstain if the claim cannot be supported.")
        for name in sorted(marked_identifiers(statement)):
            if any(literal_identifier(name, ref["quote"]) for ref in citations):
                continue
            if python_filenames(name) and any(name in ref["source"] for ref in citations):
                continue
            choices = [quote_id for quote_id, row in (catalog or {}).items()
                       if literal_identifier(name, row["quote"])]
            raise EvidenceError(
                f"Claim {index} names code identifier {name}, absent from its quoted evidence. "
                f"Available quote_ids containing it: {choices[:4]}. "
                "Cite the actual identifier and behavior, or remove the unsupported detail.")
        for command in sorted(marked_commands(statement)):
            if not any(command in ref["quote"] for ref in citations):
                choices = [qid for qid, row in (catalog or {}).items() if command in row["quote"]]
                raise EvidenceError(
                    f"Claim {index} includes inline code {command}, absent from its quoted evidence. "
                    f"Available quote_ids containing it: {choices[:4]}. "
                    "Cite the literal command AND evidence for its purpose, or remove it.")
        allowed_states = set().union(*(state_enums(by_id[ref["chunk_id"]].text) for ref in citations))
        contradicted = declared_diagram_states(statement, citations) - allowed_states
        if allowed_states and contradicted:
            raise EvidenceError(
                f"Claim {index} calls diagram label(s) {sorted(contradicted)} a state, but the "
                f"cited source explicitly enumerates states as {sorted(allowed_states)}. "
                "An arrow label describes a transition or condition, not an extra state. "
                "Remove the contradicted claim; cite the explicit state enumeration.")
        validated.append({"id": index, "text": statement, "citations": citations})
    return validated


def validate_verdict(raw, claims):
    value = parse_json(raw)
    keys(value, ("claims", "coverage_reason", "missing_information", "answers_question"))
    if type(value["answers_question"]) is not bool:
        raise EvidenceError("answers_question must be boolean")
    text(value["coverage_reason"], 800)
    missing = value["missing_information"]
    if not isinstance(missing, list) or len(missing) > 6:
        raise EvidenceError("missing_information must be an array of up to 6 missing requested facts")
    for item in missing:
        text(item, 400)
    if value["answers_question"] != (not missing):
        raise EvidenceError(
            "Inconsistent completeness verdict: answers_question must be true exactly when "
            "missing_information is empty. State the specific missing requested facts when "
            "rejecting completeness; keep claim grounding judgments independent.")
    rows = value["claims"]
    if not isinstance(rows, list) or len(rows) != len(claims):
        raise EvidenceError("Verifier must judge every claim exactly once")
    seen = set()
    for row in rows:
        keys(row, ("id", "supported", "reason"))
        if type(row["id"]) is not int or row["id"] in seen:
            raise EvidenceError("Invalid or duplicate verifier claim ID")
        seen.add(row["id"])
        if type(row["supported"]) is not bool:
            raise EvidenceError("supported must be boolean")
        text(row["reason"], 800)
    if seen != {claim["id"] for claim in claims}:
        raise EvidenceError("Verifier IDs differ from claim IDs")
    return value, value["answers_question"] and all(row["supported"] for row in rows)


def validate_claim_audit(raw, claim):
    """The caller binds one judgment to its claim; no model IDs or copied spans."""
    value = parse_json(raw)
    keys(value, ("reason", "supported"))
    text(value["reason"], 800)
    if type(value["supported"]) is not bool:
        raise EvidenceError("Scope-audit supported must be boolean")
    return {"id": claim["id"], **value,
            "unsupported_spans": [] if value["supported"] else [claim["text"]]}


def validate_scope_audit(raw, claims):
    """A second, narrower semantic gate; model approval remains fallible."""
    value = parse_json(raw)
    keys(value, ("claims",))
    rows = value["claims"]
    if not isinstance(rows, list) or len(rows) != len(claims):
        raise EvidenceError("Scope audit must check every claim exactly once")
    by_id = {claim["id"]: claim for claim in claims}
    seen = set()
    for row in rows:
        keys(row, ("id", "reason", "unsupported_spans", "supported"))
        claim_id = row["id"]
        if type(claim_id) is not int or claim_id not in by_id or claim_id in seen:
            raise EvidenceError("Invalid or duplicate scope-audit claim ID")
        seen.add(claim_id)
        text(row["reason"], 800)
        if type(row["supported"]) is not bool:
            raise EvidenceError("Scope-audit supported must be boolean")
        spans = row["unsupported_spans"]
        if not isinstance(spans, list) or len(spans) > 6:
            raise EvidenceError("unsupported_spans must be an array of up to 6 literal claim fragments")
        for span in spans:
            text(span, 800)
            if span not in by_id[claim_id]["text"]:
                raise EvidenceError("Unsupported span must be a literal fragment of its own claim")
        if row["supported"] != (not spans):
            raise EvidenceError("Scope audit must list unsupported spans exactly when rejecting a claim")
    return value, all(row["supported"] for row in rows)
