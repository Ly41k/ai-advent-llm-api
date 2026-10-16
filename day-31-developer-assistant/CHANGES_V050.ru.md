# v0.5.0 — Stage 6 candidate

Stage 5 принят по сохранённому reports/verified/day31-stage5-mac-v041.json:
131 passed tests, offline/live passed, все 40 Python hashes совпали с v0.4.1.
RU answer 21.15 s (719/63 tokens, 1 call); EN mixed answer 24.38 s (1060/59 tokens,
2 calls). Три настоящие Qwen2.5:14b Q4_K_M генерации, не synthetic transport.
EN claim «The private service API prefix is /api/v1.» поддержан api.md. Предыдущий
failed v0.4.0 сохранён; его exact raw output неизвестен.

Изменены generation.py/rag/embeddings.py (классификация transport failure и один
pre-dispatch metadata retry), model_session.py (read-only status и typed busy),
agent_process.py (shielded owned cleanup), pipeline.py (absolute deadline,
cancellation propagation, truthful failure/excerpt messages и stage metrics),
inference_tasks.py (bounded telemetry validation и failure observations),
errors.py/cli.py/version. Добавлен reliability.py с фиксированными RU/EN recovery
messages без private bodies. Added tests/test_reliability.py: 23 methods.
Added scripts/check_stage6.py; check_stage5.py сохранён для исторических запусков.

Подтверждённые faults: malformed/IO metadata, исчерпанный retry/budget, unknown/
wrong-ID/invalid worker telemetry, cancel после persisted checkpoint, повторная
cancel во время cleanup, runtime swallowing cancel/deadline, slow final validation,
stale+unknown и private trace failure. Qwen/OS witnesses synthetic; actual child
processes/reap/private locks/checkpoint and SQLite/FTS real. Broad native Ollama
interruption и ресурсы пока не измерены.

Полный suite 154; локально 130 уникальных tests. После уточнения session lock
8 затронутых session checks повторно прошли. Mac/full MCP/new native Qwen pending.
project/docs не менялись; предыдущий 40/380 verified index остаётся актуальным.
Дни1–30, root README, private chat/history не менялись. Автоматических commit/push нет.
