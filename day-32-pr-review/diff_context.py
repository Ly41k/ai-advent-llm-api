"""Parse API patches as DATA. Preserve LEFT/base and RIGHT/head coordinates."""
import re

from common import MAX_PATCH_BYTES, MAX_FILE_BYTES, SECRET, ReviewError, fail, safe_path

HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)")
STATUSES = {"added", "modified", "removed", "renamed"}
SUFFIXES = (".py", ".kt", ".kts", ".md", ".txt", ".json", ".yml", ".yaml", ".toml")


def parse_patch(patch, path, file_id):
    hunks, current = [], None
    old_line = new_line = old_seen = new_seen = old_count = new_count = 0
    def finish():
        if current is not None and (old_seen != old_count or new_seen != new_count):
            fail("incomplete_patch")
    for line in patch.splitlines():
        match = HUNK.fullmatch(line)
        if match:
            finish()
            old_line, old_count, new_line, new_count = (
                int(match[1]), int(match[2] if match[2] is not None else 1),
                int(match[3]), int(match[4] if match[4] is not None else 1))
            if ((old_count and old_line < 1) or (new_count and new_line < 1)
                    or max(old_line, new_line, old_count, new_count) > 10000000):
                fail("invalid_hunk")
            old_seen = new_seen = 0
            current = {"id": f"F{file_id}H{len(hunks) + 1}", "path": path, "header": line, "lines": []}
            hunks.append(current)
            continue
        if line == "\\ No newline at end of file":
            continue
        if current is None or not line or line[0] not in " +-":
            fail("invalid_patch")
        prefix, text = line[0], line[1:]
        if "\x00" in text:
            fail("binary_patch")
        if prefix in " -":
            current["lines"].append({"id": f"{current['id']}L{old_line}", "side": "LEFT", "line": old_line,
                                     "text": text, "changed": prefix == "-"})
            old_line += 1
            old_seen += 1
        if prefix in " +":
            current["lines"].append({"id": f"{current['id']}R{new_line}", "side": "RIGHT", "line": new_line,
                                     "text": text, "changed": prefix == "+"})
            new_line += 1
            new_seen += 1
    finish()
    if not hunks:
        fail("missing_hunks")
    return hunks


def prepare_files(rows):
    files, omissions, seen = [], [], set()
    total = 0
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            fail("invalid_file")
        path = safe_path(row.get("filename"))
        if path in seen:
            fail("duplicate_file")
        seen.add(path)
        if row.get("previous_filename") is not None:
            safe_path(row["previous_filename"])
        status = row.get("status")
        reason = None
        if status not in STATUSES:
            reason = "unsupported_status"
        elif not path.endswith(SUFFIXES) or path.startswith((".git/", ".env")):
            reason = "unsupported_or_sensitive_file"
        patch = row.get("patch")
        if reason is None and (not isinstance(patch, str) or not patch):
            reason = "missing_patch_or_binary"
        if reason is None and SECRET.search(patch):
            reason = "secret_like_content"
        if reason is None:
            size = len(patch.encode())
            if size > MAX_FILE_BYTES or total + size > MAX_PATCH_BYTES:
                reason = "patch_size_limit"
            else:
                try:
                    hunks = parse_patch(patch, path, index)
                    changed = [line for h in hunks for line in h["lines"] if line["changed"]]
                    additions = sum(line["side"] == "RIGHT" for line in changed)
                    deletions = sum(line["side"] == "LEFT" for line in changed)
                    if additions != row.get("additions") or deletions != row.get("deletions"):
                        fail("patch_stats_mismatch")
                    if not changed:
                        fail("no_changed_lines")
                    total += size
                    files.append({"path": path, "previous_path": row.get("previous_filename"),
                                  "status": status, "hunks": hunks})
                except ReviewError as error:
                    reason = str(error)
        if reason:
            omissions.append({"path": path, "reason": reason})
    return files, omissions


def evidence_catalog(files, documents):
    catalog = {}
    for file in files:
        for hunk in file["hunks"]:
            for line in hunk["lines"]:
                if line["id"] in catalog:
                    fail("overlapping_hunks")
                catalog[line["id"]] = {"kind": "diff", "path": file["path"], "hunk": hunk["id"], **line}
    for document in documents:
        catalog[document["id"]] = {"kind": "document", **document}
    return catalog
