"""Run isolated examples and preserve both successful and failed observations."""

from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import uuid

from examples import messages_for, validate
from providers import ProviderError, model_matches


def new_report(command, args):
    return {"schema_version": 1, "run_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(), "mode": "live",
            "command": command, "python": platform.python_version(),
            "settings": {"local_model": args.local_model, "cloud_model": args.cloud_model,
                         "temperature": args.temperature, "max_tokens": args.max_tokens,
                         "num_ctx": args.num_ctx, "timeout_seconds": args.timeout},
            "providers": [], "results": [], "summary": {}}


def run_provider(report, factory, name, examples):
    health = {"provider": name, "ready": False}
    report["providers"].append(health)
    try:
        provider = factory()
        health.update(provider.doctor())
        health["ready"] = True
    except ProviderError as error:
        health["error"] = str(error)
        for example in examples:
            report["results"].append({"provider": name, "example_id": example["id"],
                                      "status": "error", "error": str(error),
                                      "check": {"passed": False, "errors": ["Provider preflight failed."]}})
        return
    for example in examples:
        messages = messages_for(example["prompt"])
        row = {"provider": name, "example_id": example["id"],
               "difficulty": example["difficulty"], "title": example["title"],
               "messages": messages, "source": example["source"],
               "prompt_sha256": hashlib.sha256(json.dumps(messages, ensure_ascii=False,
                                                         sort_keys=True).encode()).hexdigest()}
        report["results"].append(row)
        try:
            generation = provider.generate(messages)
            row.update(generation.to_dict())
            row["status"] = "ok" if generation.complete else "incomplete"
            row["check"] = validate(example["id"], generation.answer) if example["id"] != "custom" else {
                "passed": generation.complete, "errors": [], "kind": "completion only; manual review required"}
            if not generation.complete:
                row["check"]["passed"] = False
                row["check"]["errors"].append("Generation did not finish normally (possibly token limit).")
        except ProviderError as error:
            row.update(status="error", error=str(error),
                       check={"passed": False, "errors": ["Generation failed."]})
    if name == "local":
        try:
            health["running_models_after"] = provider.running()
            health["model_loaded_after"] = any(model_matches(x.get("name") or x.get("model"), provider.model)
                                                 for x in health["running_models_after"])
        except ProviderError as error:
            health["running_check_error"] = str(error)
            health["model_loaded_after"] = False


def summarize(report):
    rows = report["results"]
    complete = [r for r in rows if r["status"] == "ok"]
    checked = [r for r in rows if r["check"]["passed"]]
    local = [r for r in complete if r["provider"] == "local"]
    loaded = any(p.get("model_loaded_after") for p in report["providers"] if p["provider"] == "local")
    report["summary"] = {"requests_planned": len(rows), "complete_answers": len(complete),
                         "checks_passed": len(checked), "all_checks_passed": bool(rows) and len(checked) == len(rows),
                         "local_launch_verified": bool(local) and loaded,
                         "day26_local_three_requests_verified": len({r["example_id"] for r in local
                             if r["example_id"] in {"simple", "calculation", "grounded_json"}}) == 3 and loaded}
    return report


def markdown(report):
    s = report["summary"]
    lines = ["# Day 26 — Local and cloud LLM observations", "", f"Run: `{report['run_id']}`",
             f"Mode: **{report['mode']}**", "",
             "| Provider | Example | Status | Check | Seconds | Input tokens | Output tokens |",
             "|---|---|---|---|---:|---:|---:|"]
    for row in report["results"]:
        latency = row.get("latency_seconds")
        lines.append(f"| {row['provider']} | {row['example_id']} | {row['status']} | "
                     f"{'PASS' if row['check']['passed'] else 'FAIL'} | "
                     f"{latency:.3f} | {row.get('input_tokens')} | {row.get('output_tokens')} |" if latency is not None else
                     f"| {row['provider']} | {row['example_id']} | {row['status']} | FAIL | — | — | — |")
    lines += ["", f"Complete answers: {s['complete_answers']}/{s['requests_planned']}.",
              f"Checks passed: {s['checks_passed']}/{s['requests_planned']}.",
              f"Local launch verified: {s['local_launch_verified']}.",
              f"Three local requests verified: {s['day26_local_three_requests_verified']}.", "",
              "Latency is the complete HTTP request, including loading/network overhead. Token counts use each provider's tokenizer.",
              "This is a small reproducibility exercise, not a general model ranking. Exact JSON/quote checks cover only these examples.", ""]
    for row in report["results"]:
        lines += [f"## {row['provider']} / {row['example_id']}", "", row.get("answer", row.get("error", "")), ""]
        if row["check"]["errors"]:
            lines += ["Checks: " + "; ".join(row["check"]["errors"]), ""]
    return "\n".join(lines)


def save_report(report, output):
    path = Path(output)
    if path.suffix.lower() != ".json":
        raise ValueError("--output must end in .json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
