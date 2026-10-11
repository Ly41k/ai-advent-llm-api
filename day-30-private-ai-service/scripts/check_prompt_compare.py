"""Frozen synthetic contexts: local Qwen prompt experiment, no service/DB changes."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import stat
import sys
import time
import uuid

import httpx

from check_storage import manifest
from check_http_live import CheckFailed, fingerprint
from acceptance_support import distribution, literal, new_report, russian_only
from check_inference_live import CASES
from bublik_service.domain import DEFAULT_SYSTEM_PROMPT, ModelIdentity, ModelProfile, ServiceError
from bublik_service.http_api import runtime_manifest
from bublik_service.inference.context import ContextBuilder, upper_bound
from bublik_service.inference.ollama import OllamaAdapter, nonnegative
from bublik_service.storage.repository import MAX_RESPONSE_BYTES

FORMAT = "bublik-stage8-prompt-experiment-v1"
CANDIDATE_VERSION = "candidate-latest-request-v1"
CANDIDATE_PROMPT = (
    "You are Bublik, a private local AI assistant. Follow the latest user request "
    "and its output format; use history as context. Reply in the user's language. "
    "State uncertainty; don't claim unprovided tools or sources."
)
VARIANTS = {"private-chat-v1": DEFAULT_SYSTEM_PROMPT, CANDIDATE_VERSION: CANDIDATE_PROMPT}


def check(report, name, passed):
    report.setdefault("checks", []).append({"name": name, "passed": bool(passed)})
    if not passed:
        raise CheckFailed(name)


def api_stopped():
    """Require refusal at the known API listener; a timeout is not proof."""
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            return False
    except ConnectionRefusedError:
        return True
    except OSError:
        return False


def load_baseline(path):
    info = path.stat()
    if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or info.st_size > 2 * 1024 * 1024):
        raise ValueError()
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def frozen_cases(baseline):
    """Reconstruct the original ten contexts, not generated candidate history."""
    if (baseline.get("format") != "bublik-stage8-acceptance-live-v1"
            or baseline.get("technical_status") != "passed"
            or baseline["server_before"]["runtime_source_sha256"] != runtime_manifest()
            or baseline["source_sha256"].get("scripts/check_inference_live.py")
               != manifest()["scripts/check_inference_live.py"]):
        raise CheckFailed("reference_baseline_not_matching_runtime_and_cases")
    profile = ModelProfile(prompt_version="private-chat-v1")
    if baseline["server_before"]["profile"] != profile.to_dict():
        raise CheckFailed("reference_profile_changed")
    identity = ModelIdentity(**baseline["server_before"]["model"]["identity"])
    builder = ContextBuilder(profile, identity)
    generations = baseline["generations"]
    if len(generations) != 16 or len({g["case"] for g in generations}) != 16:
        raise CheckFailed("reference_generations_incomplete")
    rows = {g["case"]: g for g in generations}
    result, history = [], []
    for index, (name, prompt, expected) in enumerate(CASES):
        row = rows[name]
        if row["status"] != "completed" or not isinstance(row["answer"], str):
            raise CheckFailed("reference_generation_not_completed")
        plan = builder.build({"messages": history}, prompt)
        selected = [m for m in history if m["id"] in plan.history_message_ids]
        messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                    *[{"role": m["role"], "content": m["content"]} for m in selected],
                    {"role": "user", "content": prompt}]
        if (upper_bound(messages) != row["context"]["input_token_upper_bound"]
                or (len(history)-len(selected))//2 != row["context"]["omitted_turns"]):
            raise CheckFailed("reference_context_reconstruction_mismatch")
        result.append({"case": name, "messages": messages, "expected": expected,
                       "method": "exact_literal" if expected is not None else "human_review",
                       "omitted_turns": row["context"]["omitted_turns"]})
        history.extend([{"id": f"u{index}", "role": "user", "content": prompt},
                        {"id": f"a{index}", "role": "assistant", "content": row["answer"]}])
    for index in range(3):
        for name, prompt, method, expected in [
            (f"russian-greeting-{index}", "Привет! Как у тебя дела? Чем ты можешь мне помочь?",
             "cyrillic_present_no_CJK_screen", None),
            (f"concurrent-{index}", f"Reply only: queue-{index}", "exact_literal", f"queue-{index}"),
        ]:
            if name not in rows or rows[name]["status"] != "completed":
                raise CheckFailed("reference_generations_incomplete")
            result.append({"case": name, "messages": [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                                                       {"role": "user", "content": prompt}],
                           "expected": expected, "method": method, "omitted_turns": 0})
    return result


async def generate(client, profile, messages, record):
    """Bounded non-streaming experiment; never persist a service profile snapshot."""
    bound = upper_bound(messages)
    if bound+profile.max_output+profile.margin > profile.num_ctx:
        raise CheckFailed("experiment_context_budget_exceeded")
    record["input_upper_bound"] = bound
    body = {"model": profile.model, "messages": messages, "stream": False, "keep_alive": "5m",
            "options": {"temperature": profile.temperature, "num_predict": profile.max_output,
                        "num_ctx": profile.num_ctx}}
    started = time.perf_counter()
    record.update(dispatched=True, terminal_seen=False)
    async with asyncio.timeout(300):
        async with client.stream("POST", "/api/chat", json=body,
                                 timeout=httpx.Timeout(300, connect=3)) as response:
            record["http_status"] = response.status_code
            if response.status_code != 200:
                raise CheckFailed("experiment_http_not_200")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 2 * 1024 * 1024:
                    raise CheckFailed("experiment_response_too_large")
    value = json.loads(data)
    record["terminal_seen"] = isinstance(value, dict) and value.get("done") is True
    if (not record["terminal_seen"] or value.get("model") != profile.model
            or value.get("done_reason") not in {"stop", "length"}
            or value.get("message", {}).get("role") != "assistant"
            or value["message"].get("tool_calls") or value["message"].get("thinking")):
        raise CheckFailed("experiment_invalid_terminal")
    answer = value["message"]["content"]
    if not isinstance(answer, str) or len(answer.encode()) > MAX_RESPONSE_BYTES:
        raise CheckFailed("experiment_invalid_answer")
    inputs = nonnegative(value.get("prompt_eval_count"), integer=True)
    outputs = nonnegative(value.get("eval_count"), integer=True)
    duration = nonnegative(value.get("eval_duration"), integer=True)/1e9
    load = nonnegative(value.get("load_duration"), integer=True)/1e9
    if inputs > bound or outputs > profile.max_output:
        raise CheckFailed("experiment_model_counter_overflow")
    record.update(answer=answer, status="completed" if value["done_reason"] == "stop" else "truncated",
                  metrics={"input_tokens": inputs, "output_tokens": outputs,
                           "inference_seconds": duration, "load_seconds": load,
                           "tokens_per_second": outputs/duration if duration else None,
                           "client_total_seconds": time.perf_counter()-started})


async def run(adapter, client, baseline, report, *, stopped_probe=api_stopped):
    cases = frozen_cases(baseline)
    report["frozen_cases"] = [{"case": c["case"], "reference_context_sha256": fingerprint(c["messages"]),
                               "omitted_turns": c["omitted_turns"]} for c in cases]
    report["variants"] = {k: {"system_prompt": v, "sha256": hashlib.sha256(v.encode()).hexdigest()}
                          for k, v in VARIANTS.items()}
    report["records"] = []
    profile = ModelProfile(prompt_version="private-chat-v1")
    report["inference_settings"] = {k: v for k, v in profile.to_dict().items() if k != "prompt_version"}
    report["reference_context_profile"] = profile.to_dict()
    check(report, "api_stopped_before_experiment", stopped_probe())
    doctor = await adapter.doctor()
    report["doctor_before"] = doctor.to_dict()
    check(report, "same_reference_model_identity",
          doctor.to_dict()["identity"] == baseline["server_before"]["model"]["identity"])
    # ABBA balances variant order. Each case uses the SAME frozen role/content
    # history; a candidate answer never becomes a later input in this experiment.
    order = ["private-chat-v1", CANDIDATE_VERSION, CANDIDATE_VERSION, "private-chat-v1"]
    report["variant_order"] = order
    for block, variant in enumerate(order):
        for case in cases:
            check(report, "api_stopped_before_request", stopped_probe())
            messages = [{"role": "system", "content": VARIANTS[variant]}, *case["messages"][1:]]
            record = {"block": block, "variant": variant, "case": case["case"], "method": case["method"],
                      "expected": case["expected"], "context_sha256": fingerprint(messages),
                      "history_and_request_sha256": fingerprint(messages[1:])}
            report["records"].append(record)
            await generate(client, profile, messages, record)
            check(report, "control_response_completed", record["status"] == "completed")
            record["matched"] = (literal(record["answer"], case["expected"]) if case["method"] == "exact_literal"
                                 else russian_only(record["answer"]) if case["method"] == "cyrillic_present_no_CJK_screen"
                                 else None)
            print(json.dumps({"block": block, "variant": variant, "case": case["case"],
                              "matched": record["matched"]}), flush=True)
        after = await adapter.doctor()
        check(report, "same_model_and_engine_epoch", after.identity == doctor.identity
              and after.engine_epoch == doctor.engine_epoch)
    report["doctor_after"] = after.to_dict()
    check(report, "api_still_stopped", stopped_probe())
    report["technical_status"] = "passed"


def summarize(report):
    records = report.get("records", [])
    result = {}
    for variant in VARIANTS:
        rows = [r for r in records if r["variant"] == variant]
        controls = [r for r in rows if r.get("matched") is not None]
        result[variant] = {"completed": sum(r.get("status") == "completed" for r in rows),
                           "controls": len(controls), "passed_controls": sum(r["matched"] for r in controls),
                           "failed_cases": sorted({r["case"] for r in controls if not r["matched"]}),
                           "client_total_seconds": distribution([r["metrics"]["client_total_seconds"] for r in rows if "metrics" in r]),
                           "tokens_per_second": distribution([r["metrics"]["tokens_per_second"] for r in rows if "metrics" in r and r["metrics"]["tokens_per_second"] is not None])}
    report["comparison"] = result
    report["improvement_observed_cases"] = sorted({r["case"] for r in records if r.get("matched") is False
        and r["variant"] == "private-chat-v1"
        and len([c for c in records if c["variant"] == CANDIDATE_VERSION and c["case"] == r["case"]
                 and c.get("matched") is True]) == 2})
    candidate = result[CANDIDATE_VERSION]
    report["candidate_quality_status"] = ("incomplete" if candidate["controls"] != 26 else
                                           "passed" if candidate["passed_controls"] == 26 else "failed")
    report["inference_outcome_unknown"] = any(r.get("dispatched") and not r.get("terminal_seen") for r in records)
    report["service_prompt_changed"] = False
    report["semantic_review"] = "pending_human_review"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-exclusive-engine-use", action="store_true", required=True)
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 13) or sys.platform != "darwin": raise ValueError()
        baseline, baseline_hash = load_baseline(args.baseline.expanduser())
        frozen_cases(baseline)
    except (ValueError, OSError, KeyError, TypeError, ServiceError):
        parser.error("macOS/Python3.13 and private original stage8 baseline of this runtime required")
    report = {"format": FORMAT, "run_id": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
              "status": "failed", "technical_status": "failed", "source_sha256": manifest(), "checks": [],
              "baseline_sha256": baseline_hash, "operator_exclusive_use_confirmed": True,
              "environment": {"python": platform.python_version(), "system": platform.system(), "machine": platform.machine()},
              "evidence": "Actual local Ollama responses to frozen SYNTHETIC contexts; no API/working DB writes or cloud fallback",
              "not_run": ["candidate as deployed API prompt", "dynamic candidate multi-turn history", "concurrent inference",
                          "physical device observation", "RSS/CPU/GPU measurements", "first-token timing", "forced cold eviction"]}
    with new_report(parser, args.output) as stream:
        started = time.perf_counter()
        async def execute():
            adapter = OllamaAdapter()
            try:
                async with httpx.AsyncClient(base_url=adapter.url, trust_env=False, follow_redirects=False) as client:
                    await run(adapter, client, baseline, report)
            finally:
                await adapter.aclose()
        try:
            asyncio.run(execute())
        except CheckFailed as error: report["failed_check"] = error.name
        except ServiceError as error: report["error_code"] = error.code
        except KeyboardInterrupt: report["error_code"] = "operator_interrupted"
        except Exception: report["error_code"] = "prompt_experiment_failed"
        finally:
            summarize(report)
            report["source_unchanged"] = report["source_sha256"] == manifest()
            if (report["technical_status"] == "passed" and report["candidate_quality_status"] == "passed"
                    and report["source_unchanged"]): report["status"] = "passed"
            report["elapsed_seconds"] = time.perf_counter()-started
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write("\n")
    print(json.dumps({"report": str(args.output), "status": report["status"],
                      "inference_outcome_unknown": report["inference_outcome_unknown"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__": sys.exit(main())
