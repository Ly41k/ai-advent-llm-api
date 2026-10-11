"""Check a storage report against this checkout, without rerunning tests."""
import argparse
import json
from pathlib import Path
import sys

from check_storage import manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        records = report["tests"]
        valid = (report["format"] in {"bublik-storage-check-v1", "bublik-offline-check-v2", "bublik-rag-live-v1"}
                 and report["status"] == "passed"
                 and report["source"]["unchanged_during_run"] is True
                 and report["source"]["source_sha256"] == manifest()
                 and report["summary"]["tests"] == len(records) > 0
                 and len({r["id"] for r in records}) == len(records)
                 and all(r["status"] == "passed" for r in records)
                 and all(report["summary"][key] == 0 for key in ("failures", "errors", "skipped")))
    except (OSError, ValueError, KeyError, TypeError):
        valid = False
    print(json.dumps({"report_matches_sources_and_passed": valid,
                      "note": "Hash comparison only; not a signature or live network/model proof"}))
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
