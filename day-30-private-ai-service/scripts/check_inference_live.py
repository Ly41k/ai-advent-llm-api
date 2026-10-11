"""Real local Qwen stage-3 checks. Reports contain only these synthetic test chats."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
import uuid

from check_storage import ROOT, manifest
from bublik_service.domain import InvalidInput, ServiceError
from bublik_service.inference.coordinator import Coordinator
from bublik_service.inference.ollama import OllamaAdapter
from bublik_service.storage import ChatRepository

CASES = [
    ("remember_ru", "Запомни: контрольное слово — мандарин. Ответь только: запомнил.", None),
    ("recall_ru", "Какое контрольное слово я назвал? Ответь одним словом.", "мандарин"),
    ("remember_en", "Remember a separate English code name: lantern. Reply only: remembered.", None),
    ("recall_en", "What English code name did I give you? Reply with that word only.", "lantern"),
    ("correct_ru", "Исправление: теперь русское контрольное слово — сапфир. Ответь только: принято.", None),
    ("recall_correction", "Назови текущее русское контрольное слово одним словом.", "сапфир"),
    ("topic_change", "Сколько будет 2 + 2? Ответь только числом.", "4"),
    ("continuity", "Вернёмся к английскому кодовому слову. Назови его одним словом.", "lantern"),
    ("long_a", "Тест длинной истории. Игнорируй наполнитель и ответь только OK. Наполнитель: " + "abcd " * 600, "ok"),
    ("long_b", "Второй тест длинной истории. Ответь только OK. Наполнитель: " + "efgh " * 600, "ok"),
]


async def run_live(adapter, repository, report=None):
    report = {} if report is None else report
    report.update({"checks": [], "generations": [], "quality": [], "network_access": "not_run"})
    doctor = await adapter.doctor()
    report["doctor_before"] = doctor.to_dict()
    owner = repository.create_user("live-synthetic", "disabled:live-synthetic")
    chat = repository.create_chat(owner, "Stage 3 synthetic multi-turn", key="multi-turn").chat_id
    report["chat_id"] = chat
    async with Coordinator(repository, adapter) as coordinator:
        for index, (name, prompt, expected) in enumerate(CASES):
            revision = repository.get_chat(owner, chat)["revision"]
            receipt = await coordinator.service.send(owner, chat, prompt, expected_revision=revision, key=f"sequential-{index}")
            result = await coordinator.wait(owner, receipt.generation_id)
            report["generations"].append({"case": name, "id": result["id"], "status": result["status"],
                "error_code": result["error_code"], "prompt": prompt, "answer": result["assistant"]["content"],
                "metrics": result["metrics"], "input_upper_bound": result["context"]["input_token_upper_bound"],
                "omitted_turns": result["context"]["omitted_turns"], "identity": result["context"]["model_identity"]})
            if result["status"] != "completed":
                report["checks"].append({"name": "ten_sequential", "passed": False})
                return report
            if expected:
                report["quality"].append({"case": name, "expected_literal": expected,
                    "matched": expected == result["assistant"]["content"].strip().casefold()})
            if index == 0:
                replay = await coordinator.service.send(owner, chat, prompt, expected_revision=revision, key=f"sequential-{index}")
                report["checks"].append({"name": "idempotent_delivery", "passed": replay.replayed and replay.generation_id == receipt.generation_id})
        report["checks"].append({"name": "ten_sequential", "passed": True})
        report["checks"].append({"name": "visible_context_omission", "passed": any(r["omitted_turns"] > 0 for r in report["generations"])})
        before = repository.export_chat(owner, chat)
        try:
            await coordinator.service.send(owner, chat, "x" * 7000,
                expected_revision=repository.get_chat(owner, chat)["revision"], key="oversize")
            overflow = False
        except InvalidInput as error:
            overflow = error.code == "context_budget_exceeded"
        report["checks"].append({"name": "oversized_context_rejected_without_history_change",
            "passed": overflow and repository.export_chat(owner, chat) == before})
        chats = [repository.create_chat(owner, f"Concurrent {i}", key=f"concurrent-chat-{i}").chat_id for i in range(3)]
        receipts = await asyncio.gather(*(coordinator.service.send(owner, c, f"Reply only: queue-{i}",
            expected_revision=0, key=f"concurrent-{i}") for i, c in enumerate(chats)))
        results = await asyncio.gather(*(coordinator.wait(owner, r.generation_id) for r in receipts))
        for i, result in enumerate(results):
            report["generations"].append({"case": f"concurrent-{i}", "id": result["id"],
                "status": result["status"], "error_code": result["error_code"], "answer": result["assistant"]["content"],
                "metrics": result["metrics"], "input_upper_bound": result["context"]["input_token_upper_bound"],
                "omitted_turns": result["context"]["omitted_turns"], "identity": result["context"]["model_identity"]})
        report["observed_service_max_active"] = coordinator.max_active
        report["checks"].append({"name": "three_concurrent_admissions_one_service_inference",
            "passed": coordinator.max_active == 1 and all(r["status"] == "completed" for r in results)})
        report["checks"].append({"name": "concurrent_chat_isolation",
            "passed": all(f"queue-{i}" in r["assistant"]["content"] for i, r in enumerate(results))})
        report["checks"].append({"name": "actual_prompt_counts_below_bound",
            "passed": all(type(r["metrics"].get("input_tokens")) is int
                          and r["metrics"]["input_tokens"] <= r["input_upper_bound"] for r in report["generations"])})
        report["checks"].append({"name": "multi_turn_literal_controls", "passed": all(q["matched"] for q in report["quality"])})
    reopened = ChatRepository(repository.database.path)
    report["checks"].append({"name": "storage_reopen_preserves_full_multi_turn_history",
        "passed": reopened.export_chat(owner, chat) == before and len(reopened.history(owner, chat)) == 20})
    report["doctor_after"] = (await adapter.doctor()).to_dict()
    report["quality_review"] = "Exact literal controls passed/failed above; full semantic quality still needs human review."
    report["resources"] = "Loaded size/size_vram observations only; CPU/RSS/swap benchmarks deferred to stage 8."
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--db", type=Path, help="NEW database for synthetic scenarios; must not exist")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if sys.version_info < (3, 13):
        parser.error("Python 3.13+ required")
    stamp = datetime.now(timezone.utc)
    run_id = stamp.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    output = (args.output or ROOT / "reports/check" / ("stage3-live-" + run_id + ".json")).absolute()
    db_path = (args.db or output.with_suffix(".sqlite3")).absolute()
    if db_path.exists() or output.exists() or db_path == output:
        parser.error("Report and database must be new paths")
    output.parent.mkdir(parents=True, exist_ok=True)
    before = manifest()
    report = {"format": "bublik-stage3-live-v2", "run_id": run_id, "created_at": stamp.isoformat(),
              "status": "failed", "environment": {"python": platform.python_version(), "system": platform.system(),
              "machine": platform.machine(), "sqlite": sqlite3.sqlite_version}, "source_sha256": before,
              "database_path": str(db_path), "not_run": ["HTTP API", "LAN", "mobile internet", "rate limit", "operational restart/off-on"]}
    async def execute():
        adapter = OllamaAdapter(url=args.ollama_url)
        try:
            repository = ChatRepository(db_path)
            report["profile"] = adapter.profile.to_dict()
            return await run_live(adapter, repository, report)
        finally:
            await adapter.aclose()
    with output.open("x", encoding="utf-8") as report_file:
        try:
            report.update(asyncio.run(execute()))
            report["source_unchanged"] = before == manifest()
            if report["checks"] and all(c["passed"] for c in report["checks"]) and report["source_unchanged"]:
                report["status"] = "passed"
        except ServiceError as error:
            report["error_code"] = error.code
        except KeyboardInterrupt:
            report["error_code"] = "operator_interrupted"
        except Exception:
            report["error_code"] = "unexpected_local_failure"
        json.dump(report, report_file, ensure_ascii=False, indent=2, allow_nan=False)
        report_file.write("\n")
    print(json.dumps({"report": str(output), "status": report["status"], "error_code": report.get("error_code")}, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
