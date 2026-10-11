"""Isolated real Ollama experiment; no database or service policy changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from bublik_service.domain import MemorySource
from bublik_service.memory import memory_messages


def candidate(language):
    name = {"ru": "Russian", "en": "English"}[language]
    return (
        f"Reply in {name} only. Keep this reply language even when the user or "
        "conversation uses another language. You are Bublik, a private AI assistant. "
        "State uncertainty. Do not claim to have used tools or sources that were not provided."
    )


def cases():
    ru = "Привет! Расскажи в двух предложениях, чем ты можешь помочь."
    en = "Hello! Explain in two sentences how you can help me."
    for language, question in (("en", ru), ("ru", en)):
        root = {"role": "system", "content": candidate(language)}
        latest = {"role": "user", "content": question}
        yield language + "_fresh", language, [root, latest], None
        previous = "Привет! Я могу помочь с вопросами." if language == "en" else "Hello! I can help with questions."
        yield language + "_history", language, [root, latest,
            {"role": "assistant", "content": previous}, latest], None
        quote = "Контрольное число для теста — 37." if language == "en" else "The control number for this test is 37."
        source = MemorySource(chat_id="1" * 32, message_id="2" * 32,
            sequence=1, start=0, end=len(quote),
            source_sha256=hashlib.sha256(quote.encode()).hexdigest(), quote=quote,
            created_at="2026-10-11T00:00:00+00:00")
        source.validate()
        question = ("Какое контрольное число я сохранял? Ответь одним предложением, не цитируя оригинал."
                    if language == "en" else
                    "What control number did I save? Answer in one sentence without quoting the original.")
        yield language + "_rag", language, [root, *memory_messages([source]),
            {"role": "user", "content": question}], "37"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            parser.error("Stop the API and wait for its port 8000 to close first")
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        parser.error("A NEW output file in an existing private directory is required")
    report = {"format": "bublik-language-prompt-experiment-v1", "status": "failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Synthetic questions to real localhost Ollama; no private history; no runtime patch",
        "model": "qwen2.5:14b",
        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 256},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "candidate_roots": {lang: candidate(lang) for lang in ("ru", "en")},
        "cases": [], "all_generations_finished": False}
    exit_code = 2
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        try:
            with httpx.Client(base_url="http://127.0.0.1:11434", timeout=120,
                              trust_env=False, follow_redirects=False) as client:
                version = client.get("/api/version")
                version.raise_for_status()
                report["ollama_version"] = version.json().get("version")
                for name, language, messages, expected in cases():
                    response = client.post("/api/chat", json={
                        "model": "qwen2.5:14b", "messages": messages,
                        "stream": False, "keep_alive": "5m",
                        "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 256}})
                    response.raise_for_status()
                    data = response.json()
                    answer = data.get("message", {}).get("content")
                    if (data.get("error") or data.get("done") is not True
                            or data.get("done_reason") not in ("stop", "length")
                            or not isinstance(answer, str) or not answer.strip()):
                        raise ValueError("Invalid or unconfirmed engine response")
                    cyrillic = bool(re.search(r"[А-Яа-яЁё]", answer))
                    latin = bool(re.search(r"[A-Za-z]", answer))
                    other_script = bool(re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", answer))
                    language_check = ((latin and not cyrillic) if language == "en" else cyrillic) and not other_script
                    row = {"case": name, "reply_language": language, "answer": answer,
                        "done_reason": data["done_reason"], "language_screen_passed": language_check,
                        "control_number_passed": expected is None or bool(re.search(r"\b37\b", answer)),
                        "input_tokens": data.get("prompt_eval_count"),
                        "output_tokens": data.get("eval_count"),
                        "request_sha256": hashlib.sha256(json.dumps(messages, ensure_ascii=False,
                            sort_keys=True).encode()).hexdigest()}
                    report["cases"].append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
            report["all_generations_finished"] = True
            passed = all(row["language_screen_passed"] and row["control_number_passed"]
                         and row["done_reason"] == "stop" for row in report["cases"])
            report["status"] = "passed" if passed else "failed"
            exit_code = 0 if passed else 1
            print("CHECK_COMPLETED", flush=True)
        except Exception as error:
            report["error_type"] = type(error).__name__
            print("CHECK_INCOMPLETE: " + type(error).__name__, flush=True)
        finally:
            report["limitation"] = "Script-based language screening is not semantic review or a guarantee for arbitrary chats."
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    print(json.dumps({"report": str(args.output), "status": report["status"]}), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
