"""Safe reports, fixed filenames, SHA-bound links. No raw model HTML or URLs."""
import html
import json
from pathlib import Path
import re
from urllib.parse import quote

from common import REPOSITORY, SECRET, contains_secret, digest, dump, fail


def prose(text):
    text = re.sub(r"https?://\S+", "[external link omitted]", str(text))
    text = html.escape(text).replace("@", "@\u200b")
    return re.sub(r"([\\`*_[\]{}|])", r"\\\1", text)


def link(report, finding):
    revision = report["head_sha"] if finding["side"] == "RIGHT" else report["base_sha"]
    path = finding["path"]
    if finding["side"] == "LEFT":
        path = report.get("previous_paths", {}).get(path) or path
    return f"https://github.com/{REPOSITORY}/blob/{revision}/{quote(path, safe='/')}#L{finding['start_line']}-L{finding['end_line']}"


def markdown(report):
    lines = ["# Day 32 AI PR Review", "", f"Status: **{report['status']}**", "",
             f"PR #{report.get('pr_number', '?')} · head `{report.get('head_sha', '')}`",
             f"Base `{report.get('base_sha', '')}` · application `{report.get('source_revision', '')}`", "",
             "Mode: " + report["mode"] + ". Coordinate/evidence validation is not semantic proof.", ""]
    for finding in report.get("findings", []):
        lines += ["## " + prose(finding["severity"] + ": " + finding["title"]), "",
                  f"[{prose(finding['path'])}:{finding['start_line']} ({finding['side']})]({link(report, finding)})", "",
                  prose(finding["reason"]), "", "Suggested fix: " + prose(finding["suggestion"]), "",
                  "Evidence IDs: " + ", ".join(prose(e["id"]) for e in finding["evidence"]), ""]
    if report.get("status") in {"completed", "partial"} and not report.get("findings"):
        lines += ["No findings returned for the selected context. This is not a clean bill for the entire PR.", ""]
    if report.get("rejected_findings"):
        lines += ["Rejected findings: " + str(len(report["rejected_findings"])) + ". See JSON rejection codes.", ""]
    lines += ["Unreviewed regions:", ""]
    for omitted in report.get("omissions", []):
        lines.append("- " + prose(omitted["path"]) + ": " + prose(omitted["reason"]))
    if not report.get("omissions"):
        lines.append("- None among admitted text hunks; full-program behavior was not tested.")
    if report.get("error"):
        lines += ["", "Error: " + prose(report["error"])]
    return "\n".join(lines) + "\n"


def save(directory, report, summary):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        fail("unsafe_output_directory")
    report["integrity_sha256"] = digest({k: v for k, v in report.items() if k != "integrity_sha256"})
    outputs = {"review.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
               "review.md": markdown(report), "run-summary.json": json.dumps(summary, ensure_ascii=False, indent=2) + "\n"}
    if contains_secret(report) or contains_secret(summary) or any(SECRET.search(text) for text in outputs.values()):
        fail("unsafe_report")
    for name, content in outputs.items():
        destination = directory / name
        if destination.is_symlink():
            fail("unsafe_output_path")
        destination.write_text(content, encoding="utf-8")


def verify_report(report):
    expected = report.get("integrity_sha256")
    if expected != digest({k: v for k, v in report.items() if k != "integrity_sha256"}):
        fail("report_integrity")
