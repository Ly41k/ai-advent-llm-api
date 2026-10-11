"""Read-only HTTPS verification of v1 history/snapshots after the v2 upgrade."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import ssl
import time
import uuid

import httpx

from acceptance_support import API, history_record, new_report
from check_http_live import CheckFailed, read_token
from check_storage import manifest
from network_common import private_origin
from bublik_service.domain import ModelProfile


def validate_baseline(value):
    old_profile = ModelProfile(prompt_version="private-chat-v1").to_dict()
    if (value.get("format") != "bublik-stage8-acceptance-live-v1"
            or value.get("technical_status") != "passed"
            or value["server_before"]["profile"] != old_profile
            or value["server_after"]["profile"] != old_profile
            or not 1 <= len(value["chats"]) <= 100
            or not 1 <= len(value["generations"]) <= 100
            or any(not re.fullmatch(r"[a-f0-9]{32}", row["id"])
                   for row in [*value["chats"], *value["generations"]])):
        raise ValueError("invalid_v1_baseline")


async def run(client, baseline, report, *, pause=asyncio.sleep):
    validate_baseline(baseline)
    api = API(client, report, quota_pause=pause)
    before = await api.ready()
    report["server_before"] = before
    api.check("new_profile_v2", before["profile"] == ModelProfile().to_dict()
              and before["profile"]["prompt_version"] == "private-chat-v2")
    api.check("same_model_identity", before["model"]["identity"] == baseline["server_after"]["model"]["identity"])
    api.check("idle_no_recovery_gate", before["queued"] == before["running"] == 0
              and not before["inference_recovery_required"])
    # Source differences are expected for this explicitly versioned upgrade;
    # ordinary same-version history checks retain their strict source check.
    report["baseline_sources_match_current"] = baseline.get("source_sha256") == manifest()
    report["chats"] = []
    for row in baseline["chats"]:
        current = history_record(row["id"], await api.history(row["id"]))
        api.check("saved_history_"+row["id"], current == row)
        report["chats"].append(current)
    report["old_generations"] = []
    for row in baseline["generations"]:
        current = await api.get("/generations/"+row["id"])
        unchanged = (current["profile"] == baseline["server_before"]["profile"]
                     and current["assistant"]["content"] == row["answer"]
                     and all(current[k] == row[k] for k in
                             ("status", "error_code", "metrics", "context", "started_at", "finished_at")))
        api.check("old_generation_unchanged_"+row["id"], unchanged)
        report["old_generations"].append({"id": row["id"], "unchanged": unchanged,
                                           "prompt_version": current["profile"]["prompt_version"]})
    after = await api.ready("ready_after")
    report["server_after"] = after
    api.check("current_profile_identity_stable", after["profile"] == before["profile"]
              and after["model"]["identity"] == before["model"]["identity"])
    api.check("still_idle_no_gate", after["queued"] == after["running"] == 0
              and not after["inference_recovery_required"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--network", choices=("lan", "tailnet"), required=True)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        private_origin(args.url, args.network)
        if args.network == "lan" and not args.ca_file:
            raise ValueError()
        token = read_token(args.token_file.expanduser())
        if args.baseline.is_symlink() or not args.baseline.is_file() or args.baseline.stat().st_size > 2*1024*1024:
            raise ValueError()
        raw = args.baseline.read_bytes()
        baseline = json.loads(raw)
        validate_baseline(baseline)
        tls = ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else ssl.create_default_context()
    except (ValueError, OSError, KeyError, TypeError):
        parser.error("Private HTTPS/token and original complete v1 baseline required; LAN needs CA")
    report = {"format": "bublik-stage8-prompt-upgrade-v1", "run_id": uuid.uuid4().hex,
              "created_at": datetime.now(timezone.utc).isoformat(), "status": "failed",
              "url": args.url, "network": args.network, "checks": [], "source_sha256": manifest(),
              "baseline_sha256": hashlib.sha256(raw).hexdigest(),
              "environment": {"python": platform.python_version(), "system": platform.system(), "machine": platform.machine()},
              "evidence": "Actual authenticated read-only HTTPS; old history hashes and exposed generation snapshots. No inference or phone observation.",
              "not_run": ["new v2 inference baseline", "physical device observation", "full internal DB snapshot audit"]}
    with new_report(parser, args.output) as stream:
        started = time.perf_counter()
        try:
            async def execute():
                async with httpx.AsyncClient(base_url=args.url, headers={"Authorization": "Bearer "+token},
                                            verify=tls, timeout=15, trust_env=False, follow_redirects=False) as client:
                    await run(client, baseline, report)
            asyncio.run(execute())
            report["status"] = "passed"
        except CheckFailed as error:
            report["failed_check"] = error.name
        except KeyboardInterrupt:
            report["error_code"] = "operator_interrupted"
        except Exception:
            report["error_code"] = "http_or_validation_failure"
        finally:
            report["source_unchanged"] = report["source_sha256"] == manifest()
            if not report["source_unchanged"]:
                report["status"] = "failed"
            report["elapsed_seconds"] = time.perf_counter()-started
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"report": str(args.output), "status": report["status"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
