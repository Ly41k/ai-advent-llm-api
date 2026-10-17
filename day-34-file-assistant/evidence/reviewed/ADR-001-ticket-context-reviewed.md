# ADR-001: Контекст тикета через MCP в Day 33

> Редакционный вариант после независимой проверки. Уточнения CLI/HTTP и retrieval внесены рецензентом без LLM-вызовов. Исходный модельный Markdown сохранён отдельно.

## Решение
Day 33 получает контекст тикета только через MCP-клиент, который стартует отдельный stdio-процесс синтетического CRM и последовательно вызывает `get_ticket`, затем `get_user` по `user_id` из тикета.

## Архитектура
- Локальный HTTP-handler `/support/answer` в `main.py` всегда вызывает `answer(request, OfflineAdapter())`.
- `prepare --ticket` — CLI-команда: она вызывает `fetch_context` напрямую. Для ответов HTTP/CLI функция `answer` запускает `answer_async`; при наличии `ticket_id` та получает и проверяет MCP-контекст.
- `mcp_client.py` поднимает изолированный child-process CRM, делает `initialize`, проверяет каталог инструментов и затем читает данные.
- `mcp_server.py` публикует ровно два инструмента: `get_ticket` и `get_user`.
- `support_agent.py` валидирует, что тикет и пользователь синтетические, согласованы по `user_id` и `device`, а затем включает их в подготовку ответа и ограничения LLM.

## Как это работает
1. В CLI-команде `prepare` модуля `main.py` при наличии `--ticket` вызывается `fetch_context(args.ticket)`. В пути ответа получение контекста выполняет `answer_async`.
2. В `fetch_context` сначала вызывается `get_ticket`.
3. Из ответа берётся только `ticket.user_id`; вопрос пользователя не участвует в выборе ID.
4. Затем вызывается `get_user` с этим `user_id`.
5. После `validate_context` функция `prepare` вызывает `retrieve(question, ticket)` и объединяет найденные источники FAQ с контекстом тикета/пользователя в payload. Retrieval использует SQLite FTS5 и ранжирование BM25. В пути `answer_async` подготовленный payload передаётся адаптеру генерации, затем план проверяется и рендерится.

## Пример Day 33
Синтетический тикет `T-101` связан с `U-001`; это подтверждается тестом каталога MCP и фикстурами CRM.

## Поведение в особых случаях
- Если `ticket_id` не передан, контекст тикета не запрашивается и ответ строится как общий FAQ.
- Локальный HTTP-сервер офлайн; live-режим доступен только как явный one-shot CLI и не используется как сетевой backend.

## Evidence
- `day-33-support-assistant/main.py:11` — `from mcp_client import fetch_context`
- `day-33-support-assistant/main.py:115` — `                ticket,user=asyncio.run(fetch_context(args.ticket))`
- `day-33-support-assistant/mcp_client.py:57` — `async def fetch_context(ticket_id, command=None):`
- `day-33-support-assistant/mcp_client.py:59` — `        ticket = (await call(session, 'get_ticket', {'ticket_id': ticket_id})).get('ticket')`
- `day-33-support-assistant/mcp_client.py:65` — `        # This ID comes only from the MCP ticket. The question is never parsed for IDs.`
- `day-33-support-assistant/mcp_client.py:66` — `        user = (await call(session, 'get_user', {'user_id': user_id})).get('user')`
- `day-33-support-assistant/support_agent.py:35` — `def validate_context(ticket, user):`
- `day-33-support-assistant/support_agent.py:42` — `    require(ticket['user_id'] == user['user_id'] and ticket['device'] == user['device'], 'mcp_identity_mismatch', 502)`
- `day-33-support-assistant/mcp_server.py:16` — `def get_ticket(ticket_id: str) -> dict:`
- `day-33-support-assistant/mcp_server.py:22` — `def get_user(user_id: str) -> dict:`
- `day-33-support-assistant/data/tickets.json:2` — `  {"ticket_id":"T-101","user_id":"U-001","product":"Bublik Private AI Service","description":"Не работает авторизация в чате. Authentication session problem.","status":"open","device":"Android Chrome","observed_error":"HTTP 401 authentication_required","session_state":"expired","diagnostic":"Synthetic operator fixture explicitly records an expired authenticated browser session; this is not inferred from HTTP 401.","synthetic":true},`
- `day-33-support-assistant/data/users.json:2` — `  {"user_id":"U-001","display_name":"Demo One","product":"Bublik Private AI Service","device":"Android Chrome","access_route":"Tailscale HTTPS","synthetic":true},`
- `day-33-support-assistant/tests/test_support.py:96` — `                self.assertEqual({t.name for t in (await session.list_tools()).tools},{'get_ticket','get_user'})`
- `day-33-support-assistant/tests/test_support.py:97` — `                self.assertEqual((await call(session,'get_ticket',{'ticket_id':'T-101'}))['ticket']['user_id'],'U-001')`
- `day-33-support-assistant/tests/test_support.py:98` — `                self.assertEqual((await call(session,'get_user',{'user_id':'U-001'}))['user']['device'],'Android Chrome')`
- `day-33-support-assistant/support_agent.py:123` — `    if payload['ticket_id'] is None:`
- `day-33-support-assistant/main.py:107` — `            adapter=OfflineAdapter()`

## Дополнительные подтверждения редакционной проверки
- `day-33-support-assistant/main.py:59` — `            self.send_json(200,answer(request,OfflineAdapter()))`
- `day-33-support-assistant/support_agent.py:147` — `    if request.get('ticket_id'):`
- `day-33-support-assistant/support_agent.py:148` — `        ticket,user=await fetch_context(request['ticket_id'],mcp_command)`
- `day-33-support-assistant/support_agent.py:150` — `    payload=prepare(request['question'],ticket,user)`
- `day-33-support-assistant/support_agent.py:46` — `    sources, retrieval = retrieve(question, ticket)`
- `day-33-support-assistant/retrieval.py:39` — `        db.execute("CREATE VIRTUAL TABLE search USING fts5(title,text, tokenize='unicode61')")`
- `day-33-support-assistant/retrieval.py:45` — `        rows = db.execute('SELECT rowid FROM search WHERE search MATCH ? AND rowid IN (SELECT rowid FROM search WHERE search MATCH ?) ORDER BY bm25(search),rowid LIMIT 3', (query,question_query)).fetchall() if query and question_query else []`
- `day-33-support-assistant/mcp_client.py:31` — `                async with stdio_client(StdioServerParameters(command=cmd[0], args=cmd[1:], env=env), errlog=errors) as (read, write):`
- `day-33-support-assistant/mcp_client.py:33` — `                        await session.initialize()`
- `day-33-support-assistant/mcp_client.py:35` — `                        require(names == {'get_ticket', 'get_user'}, 'mcp_invalid_catalog', 502)`
