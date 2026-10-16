"""Validate provenance and coordinates; do NOT claim semantic proof of a defect."""
from common import MAX_FINDINGS, SECRET, ReviewError, fail, safe_path, strict_json

FIELDS = {"severity", "path", "side", "start_line", "end_line", "title", "reason", "suggestion", "evidence"}


def validate(raw, catalog):
    value = strict_json(raw)
    if not isinstance(value, dict) or set(value) != {"findings"}:
        fail("invalid_review_schema")
    rows = value["findings"]
    if not isinstance(rows, list) or len(rows) > MAX_FINDINGS:
        fail("findings_limit")
    accepted, rejected, seen = [], [], set()
    for index, row in enumerate(rows, 1):
        try:
            if not isinstance(row, dict) or set(row) != FIELDS:
                fail("invalid_finding_schema")
            path = safe_path(row["path"])
            if (not isinstance(row["severity"], str) or not isinstance(row["side"], str)
                    or row["severity"] not in {"high", "medium", "low"} or row["side"] not in {"LEFT", "RIGHT"}):
                fail("invalid_finding_enum")
            start, end = row["start_line"], row["end_line"]
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= start + 10:
                fail("invalid_finding_range")
            anchors = [entry for entry in catalog.values() if entry["kind"] == "diff" and entry["path"] == path
                       and entry["side"] == row["side"] and entry["changed"] and start <= entry["line"] <= end]
            if {entry["line"] for entry in anchors} != set(range(start, end + 1)) or len({e["hunk"] for e in anchors}) != 1:
                fail("line_outside_selected_changes")
            for field, limit in (("title", 160), ("reason", 600), ("suggestion", 600)):
                text = row[field]
                if (not isinstance(text, str) or not text.strip() or len(text) > limit or SECRET.search(text)
                        or any(ord(c) < 32 and c not in "\n\t" for c in text)):
                    fail("invalid_finding_text")
            refs = row["evidence"]
            if (not isinstance(refs, list) or not 1 <= len(refs) <= 4
                    or any(not isinstance(ref, str) or ref not in catalog for ref in refs)
                    or len(set(refs)) != len(refs)):
                fail("invalid_evidence")
            if not set(refs) & {entry["id"] for entry in anchors}:
                fail("missing_diff_anchor_evidence")
            if any(catalog[ref]["kind"] == "diff" and catalog[ref]["path"] != path for ref in refs):
                fail("cross_file_evidence")
            identity = (path, row["side"], start, end, row["title"])
            if identity in seen:
                fail("duplicate_finding")
            seen.add(identity)
            accepted.append({**row, "evidence": [catalog[ref] for ref in refs]})
        except ReviewError as error:
            # Never copy rejected raw model content into reports.
            rejected.append({"finding_index": index, "reason": str(error)})
    return accepted, rejected
