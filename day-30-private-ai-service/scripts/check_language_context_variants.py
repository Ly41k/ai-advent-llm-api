"""Compare language controls on a saved synthetic failure; never alter the DB."""
import argparse
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys

import httpx

GENERATION = "4fdb59dde3254645b695f2e2a7dbc8e1"
QUESTION = "Теперь отвечай только по-русски. Кратко объясни, почему 3*3 равно 9, без цитат."


def load_context(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("SELECT inference_uncertain FROM service_state WHERE id=1").fetchone()[0]:
            raise ValueError("Inference recovery required")
        if db.execute("SELECT count(*) FROM generations WHERE status IN ('queued','running')").fetchone()[0]:
            raise ValueError("Pending generations exist")
        row = db.execute("SELECT status,context_json,profile_json FROM generations WHERE id=?", (GENERATION,)).fetchone()
    if row is None or row[0] != "completed":
        raise ValueError("Expected completed synthetic control generation")
    context, profile = json.loads(row[1]), json.loads(row[2])
    if (context.get("original_user_content") != QUESTION
            or context.get("reply_language") != "en"
            or context.get("language_policy") != "reply-language-v3"
            or profile.get("model") != "qwen2.5:14b"):
        raise ValueError("Unexpected control snapshot")
    return context, profile


def variants(context):
    base = context["messages"]
    yield "baseline", deepcopy(base)
    instruction = (
        "The application's reply language is English. Answer the latest task entirely in English. "
        "Language requests in the user text and past conversation do not change this setting. "
        "Do not provide a Russian-language version or label the answer 'In Russian'."
    )
    for repeat in (1, 2):
        messages = deepcopy(base)
        messages[-1]["content"] = QUESTION + "\n\n" + instruction
        yield "explicit_suffix_" + str(repeat), messages
        messages = deepcopy(base)
        messages[-1]["content"] = (
            "The following JSON contains the user's task. Language requests inside it are task data, "
            "not the application's reply-language setting.\n"
            + json.dumps({"user_request": QUESTION}, ensure_ascii=False)
            + "\n\n" + instruction)
        yield "json_request_" + str(repeat), messages
        messages = deepcopy(base)
        messages.insert(-1, {"role": "system", "content": instruction})
        yield "additional_system_" + str(repeat), messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            parser.error("Stop the API and wait for port 8000 to close")
    try:
        context, profile = load_context(args.db)
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except (OSError, ValueError, sqlite3.Error):
        parser.error("Idle readable control DB and NEW report path required")
    report = {"format": "bublik-language-context-variants-v1", "status": "incomplete",
        "created_at": datetime.now(timezone.utc).isoformat(), "model": profile["model"],
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Direct sequential localhost inference on completed synthetic control; readonly DB; no job replay",
        "baseline_context_sha256": hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "options": {"temperature": profile["temperature"], "num_ctx": profile["num_ctx"],
                    "num_predict": profile["max_output"]},
        "cases": [], "all_generations_finished": False,
        "privacy": "No original prompt, history, retrieved quotations or credentials exported"}
    exit_code = 2
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        try:
            with httpx.Client(base_url="http://127.0.0.1:11434", timeout=120,
                              trust_env=False, follow_redirects=False) as client:
                response = client.get("/api/version"); response.raise_for_status()
                report["ollama_version"] = response.json().get("version")
                response = client.get("/api/tags"); response.raise_for_status()
                selected = [m for m in response.json().get("models", []) if m.get("name") == profile["model"]]
                if len(selected) != 1 or selected[0].get("digest", "").removeprefix("sha256:") != context["model_identity"]["digest"]:
                    raise ValueError("Model digest changed")
                report["model_digest"] = context["model_identity"]["digest"]
                response = client.post("/api/show", json={"model": profile["model"]}); response.raise_for_status()
                info = response.json()
                if info.get("remote_host") or info.get("remote_model"):
                    raise ValueError("Remote model forbidden")
                template = info.get("template", "")
                if hashlib.sha256(template.replace("\r\n", "\n").strip().encode()).hexdigest() != context["model_identity"]["template_sha256"]:
                    raise ValueError("Model template changed")
                for name, messages in variants(context):
                    bound = 128 + sum(128 + len(m["content"].encode()) for m in messages)
                    if bound + profile["max_output"] + profile["margin"] > profile["num_ctx"]:
                        raise ValueError("Context budget exceeded")
                    response = client.post("/api/chat", json={"model": profile["model"],
                        "messages": messages, "stream": False, "keep_alive": "5m", "options": report["options"]})
                    response.raise_for_status(); data = response.json()
                    answer = data.get("message", {}).get("content")
                    if (data.get("error") or data.get("done") is not True
                            or data.get("done_reason") not in ("stop", "length")
                            or not isinstance(answer, str) or not answer.strip()):
                        raise ValueError("Invalid or unconfirmed response")
                    language = (bool(re.search(r"[A-Za-z]", answer))
                        and not re.search(r"[А-Яа-яЁё\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", answer))
                    row = {"case": name, "answer": answer, "done_reason": data["done_reason"],
                        "english_screen_passed": bool(language),
                        "control_number_passed": bool(re.search(r"\b(9|nine)\b", answer, re.I)),
                        "input_token_upper_bound": bound, "input_tokens": data.get("prompt_eval_count"),
                        "output_tokens": data.get("eval_count"),
                        "request_sha256": hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
                    report["cases"].append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
            report["all_generations_finished"] = True
            report["status"] = "completed"
            exit_code = 0
            print("CHECK_COMPLETED", flush=True)
        except Exception as error:
            report["error_type"] = type(error).__name__
            print("CHECK_INCOMPLETE: " + type(error).__name__, flush=True)
        finally:
            report["limitation"] = "Two repetitions on one failing context do not prove general language reliability."
            json.dump(report, output, ensure_ascii=False, indent=2); output.write("\n")
    print(json.dumps({"report": str(args.output), "status": report["status"]}), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
