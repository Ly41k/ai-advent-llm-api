"""Day 26 CLI. Options follow the subcommand; no implicit cloud fallback."""

import argparse
import json
import math
import os
from pathlib import Path
import sys

from examples import load_examples
from providers import GroqProvider, OllamaProvider, ProviderError
from runner import new_report, run_provider, save_report, summarize

DAY_DIR = Path(__file__).resolve().parent


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Must be greater than zero")
    return number


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Must be finite and greater than zero")
    return number


def temperature(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 2:
        raise argparse.ArgumentTypeError("Must be finite and between 0 and 2")
    return number


def cloud_key():
    if os.getenv("GROQ_API_KEY"):
        return os.environ["GROQ_API_KEY"]
    # Existing course .env is reused. The dependency is only needed for .env loading.
    paths = [DAY_DIR / ".env", DAY_DIR.parent / ".env"]
    if any(p.is_file() for p in paths):
        try:
            from dotenv import load_dotenv
        except ImportError:
            raise ProviderError("Install python-dotenv with the Day 26 requirements or export GROQ_API_KEY.") from None
        for path in paths:
            load_dotenv(path, override=False)
    return os.getenv("GROQ_API_KEY")


def factories(args):
    result = {}
    if args.provider in {"local", "both"}:
        result["local"] = lambda: OllamaProvider(args.local_model, args.url, args.timeout,
                                                  args.temperature, args.max_tokens, args.num_ctx)
    if args.provider in {"cloud", "both"}:
        result["cloud"] = lambda: GroqProvider(cloud_key(), args.cloud_model, args.timeout,
                                                args.temperature, args.max_tokens)
    return result


def parser():
    root = argparse.ArgumentParser(description="Day 26 — local Ollama and cloud Groq")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("doctor", "demo", "compare", "ask"):
        cmd = commands.add_parser(name)
        if name == "ask":
            cmd.add_argument("prompt")
        if name != "compare":
            cmd.add_argument("--provider", choices=("local", "cloud", "both"), default="local")
        else:
            cmd.set_defaults(provider="both")
        cmd.add_argument("--local-model", default=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"))
        cmd.add_argument("--cloud-model", default=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"))
        cmd.add_argument("--url", default="http://127.0.0.1:11434")
        cmd.add_argument("--timeout", type=positive_float, default=180)
        cmd.add_argument("--temperature", type=temperature, default=0)
        cmd.add_argument("--max-tokens", type=positive_int, default=2048)
        cmd.add_argument("--num-ctx", type=positive_int, default=8192)
        cmd.add_argument("--output", help="Save JSON and a sibling Markdown report")
    commands.add_parser("examples", help="Print the three prompts without any network calls")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "examples":
        print(json.dumps(load_examples(), ensure_ascii=False, indent=2))
        return 0
    if args.output and Path(args.output).suffix.lower() != ".json":
        parser().error("--output must end in .json")
    providers = factories(args)
    if args.command == "doctor":
        rows = []
        for name, factory in providers.items():
            try:
                rows.append({"ready": True, **factory().doctor()})
            except ProviderError as error:
                rows.append({"provider": name, "ready": False, "error": str(error)})
        result = {"mode": "live", "providers": rows,
                  "note": "doctor does not generate answers; run demo to verify inference."}
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if all(x["ready"] for x in rows) else 1
    examples = load_examples() if args.command != "ask" else [
        {"id": "custom", "difficulty": "custom", "title": "Custom prompt", "prompt": args.prompt, "source": None}]
    if args.command == "ask" and not args.prompt.strip():
        parser().error("prompt must not be empty")
    report = new_report(args.command, args)
    for name, factory in providers.items():
        print(f"Running {name}: {len(examples)} request(s)...", flush=True)
        run_provider(report, factory, name, examples)
    summarize(report)
    if args.output:
        save_report(report, args.output)
    for row in report["results"]:
        print(f"\n[{row['provider']} / {row['example_id']}] {row['status']} — "
              f"{'PASS' if row['check']['passed'] else 'FAIL'}")
        print(row.get("answer", row.get("error", "")))
        if row["check"]["errors"]:
            print("Checks: " + "; ".join(row["check"]["errors"]))
    print("\n" + json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.output:
        print(f"Saved: {args.output} and {Path(args.output).with_suffix('.md')}")
    return 0 if report["summary"]["all_checks_passed"] and (
        "local" not in providers or report["summary"]["local_launch_verified"]) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted; no successful live run is claimed.", file=sys.stderr)
        raise SystemExit(130)
    except (OSError, ValueError) as error:
        print(f"Cannot complete the command: {error}", file=sys.stderr)
        raise SystemExit(1)
