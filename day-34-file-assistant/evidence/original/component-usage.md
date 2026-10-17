# Отчёт по fetch_context в Day 33

Ниже перечислены все места использования `fetch_context` в модуле Day 33.

1. Импорт в CLI/HTTP точке входа `main.py`.
2. Ветка `prepare` в `main.py`: при наличии `--ticket` вызывает `asyncio.run(fetch_context(args.ticket))`, затем валидирует контекст и передаёт его в `prepare`.
3. Определение самой функции в `mcp_client.py`.
4. Импорт в `retry_acceptance.py`.
5. В `retry_acceptance.py` в `preview_request()` вызывается `asyncio.run(fetch_context('T-101'))` для подготовки запроса через реальный MCP.
6. Импорт в `support_agent.py`.
7. В `support_agent.py` в `answer_async()` вызывается `await fetch_context(request['ticket_id'], mcp_command)` перед `validate_context(...)` и `prepare(...)`.
8. Импорт в `tests/test_support.py`.
9. В `tests/test_support.py` два прямых вызова `asyncio.run(fetch_context('T-101'))` в тестах привязки тикета и пользователя.

Коротко по поведению:
- `fetch_context` сначала получает тикет через `get_ticket`, затем берёт только `user_id` из тикета и запрашивает пользователя через `get_user`.
- В `main.py` это используется только для режима `prepare` с тикетом.
- В `support_agent.py` это обязательный шаг для ответа по тикету.
- В тестах и acceptance-раннерах функция проверяется как реальная MCP-интеграция.

## Evidence
- `day-33-support-assistant/main.py:11` — `from mcp_client import fetch_context`
- `day-33-support-assistant/main.py:115` — `                ticket,user=asyncio.run(fetch_context(args.ticket))`
- `day-33-support-assistant/mcp_client.py:57` — `async def fetch_context(ticket_id, command=None):`
- `day-33-support-assistant/retry_acceptance.py:20` — `from mcp_client import fetch_context`
- `day-33-support-assistant/retry_acceptance.py:152` — `    ticket,user = asyncio.run(fetch_context('T-101'))`
- `day-33-support-assistant/support_agent.py:5` — `from mcp_client import fetch_context`
- `day-33-support-assistant/support_agent.py:148` — `        ticket,user=await fetch_context(request['ticket_id'],mcp_command)`
- `day-33-support-assistant/tests/test_support.py:20` — `from mcp_client import connect, call, fetch_context`
- `day-33-support-assistant/tests/test_support.py:121` — `        ticket,user=asyncio.run(fetch_context('T-101'))`
- `day-33-support-assistant/tests/test_support.py:138` — `        ticket,user=asyncio.run(fetch_context('T-101'))`
