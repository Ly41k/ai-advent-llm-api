# День 33 — видео в Mac Terminal, 4–6 минут

Показываем уже принятый Day 33: настоящий MCP, FAQ/FTS5 и сохранённый ответ Groq.
**Во время записи нет новой генерации.** Все команды — из корня репозитория.
Они не требуют GROQ_API_KEY и не печатают ключи. Не запускайте live/retry/final
acceptance runners и не удаляйте markers. Технический PASS уже получен в attempt-03.

## До записи

Откройте два Terminal tab. В первом активируйте среду и проверьте поставку:

```bash
source "$HOME/.venvs/bublik-day33/bin/activate"
python day-33-support-assistant/verify_delivery.py
```

Ожидается `status: passed`, `runtime_source_files_verified: 19`,
`new_generation_calls: 0`, `new_provider_posts: 0`.
Это проверка сохранённого доказательства; новый live она не выполняет.

## 0:00–0:40 — продукт и принятый результат

Первый tab:

```bash
python - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('day-33-support-assistant/reports/accepted.json').read_text())
print('Day 33:', r['overall_status'], '|', r['attempt_id'])
print('Scope:', r['scope'])
print('Mac offline:', r['mac_offline']['tests_run'], 'PASS')
print('Original receipt SHA256:', r['original_receipt_sha256'])
PY
```

Скажите: «Поддерживаем Bublik Day 30. CRM синтетическая; работающий Day 30 не
меняем. Ниже покажу текущий MCP/RAG без модели, затем сохранённый настоящий ответ».

## 0:40–1:40 — настоящий MCP и три источника без генерации

```bash
python day-33-support-assistant/main.py prepare \
  --ticket T-101 --question 'Почему не работает авторизация?' \
  | python -c 'import json,sys; r=json.load(sys.stdin); p=r["payload"]; print("Mode:",r["mode"],"generation_calls:",r["generation_calls"]); print("Ticket:",p["ticket_id"],"User:",p["context"]["user.user_id"]); print("Session:",p["context"]["ticket.session_state"]); print("RAG:",p["retrieval"]["method"]); print("Sources:",[s["id"] for s in p["sources"]])'
```

Ожидается T-101, U-001, expired, SQLite FTS5/BM25, DOC-ERRORS / FAQ-AUTH /
DOC-AUTH, generation_calls=0. Это реальный SDK stdio subprocess, не вызов Python
функции вместо MCP. ID пользователя взят из найденного тикета.

Для сравнения покажите общий FAQ-ответ без тикета:

```bash
python day-33-support-assistant/main.py answer \
  --question 'Почему не работает авторизация?' \
  | python -c 'import json,sys; r=json.load(sys.stdin); print("Mode:",r["llm"]["mode"]); print("Context used:",r["context_used"]); print("Assessment:",r["assessment"]); print("Gaps:",r["evidence_gaps"])'
```

Объясните: без контекста точную причину не называем; в T-101 есть явный expired.
Этот сравнительный ответ — mock, он не выдаётся за дополнительную генерацию Groq.

## 1:40–2:30 — минимальный HTTP-сервис

Первый tab:

```bash
python day-33-support-assistant/main.py serve --port 8033
```

Второй tab, из корня репозитория (Python parser использует явный путь среды):

```bash
curl --fail-with-body --max-time 10 http://127.0.0.1:8033/health
curl --fail-with-body --max-time 30 http://127.0.0.1:8033/support/answer \
  -H 'Content-Type: application/json' \
  --data '{"ticket_id":"T-101","question":"Почему не работает авторизация?"}' \
  | "$HOME/.venvs/bublik-day33/bin/python" -c 'import json,sys; r=json.load(sys.stdin); print("HTTP demo:",r["llm"]["mode"]); print("Ticket:",r["ticket_id"],"assessment:",r["assessment"]); print("Context:",r["context_user_id"])'
```

Скажите: «HTTP слушает только loopback и использует mock. Настоящий Groq принят
отдельным CLI». В первом tab остановите сервер Ctrl+C; среда остаётся активной.
Если порт занят другим процессом, используйте только CLI-часть; не останавливайте
чужой процесс и не меняйте сервис Day 30.

## 2:30–3:40 — сохранённый реальный ответ Groq

Первый tab:

```bash
python - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('day-33-support-assistant/reports/accepted.json').read_text())
print('Saved REAL Groq call:', r['attempt_id'])
print('HTTP:', r['http']['status'], 'POSTs:', r['http']['post_attempts'])
print('Usage:', r['http']['usage'])
print('Request ID:', r['http']['request_id'])
print('Actual MCP trace:', r['mcp_calls'])
print('Technical checks:', r['technical_checks'])
print('\nSAVED REAL ANSWER:\n'+r['result']['answer'])
PY
```

На экране: HTTP 200; 1370 input / 233 completion; явный expired; повторный вход.
Объясните, что тело ответа прочитано из сохранённого результата attempt-03.
Новая модель не вызывалась. Истечение не выводится из одного кода HTTP 401.

## 3:40–4:40 — evidence и честная история попыток

```bash
python - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('day-33-support-assistant/reports/accepted.json').read_text())
print('Model citations:', r['model_plan']['document_facts'])
print('Application evidence:', r['result']['application_evidence'])
print('Semantic review:', r['semantic_review']['status'], r['semantic_review']['reviewer'])
for a in r['prior_attempts']:
    print(a['attempt_id'], a['http_status'], a['error'], a['full_E2E'])
print('Accepted:', r['attempt_id'], r['full_live_E2E'])
print('Estimated list cost:', r['estimated_list_cost_usd'])
print('Actual billing:', r['actual_billed_usd'])
PY
```

Скажите: «Первый 403 и второй отказ валидатора сохранены. Исправление проверили
offline, затем выполнили новый настоящий E2E. Каталог приложения прикладывает свои
проверенные источники и не приписывает их модели. Расчёт стоимости не равен billing».

## 4:40–5:10 — проверка сохранённой поставки и завершение

```bash
python day-33-support-assistant/verify_delivery.py
```

Скажите: «Day 33 принят как PASS для Course Minimum. Остальные обязательные
сценарии прошли offline; реальная модель проверена на T-101. Публичный deployment,
настоящая CRM и общий live HTTP оставлены после курса. На видео новых генераций нет».

Если преподавателю нужен вывод 25 тестов, вне основного хронометража безопасно:

```bash
python -W error::ResourceWarning -m unittest discover -s day-33-support-assistant/tests -v
```

Это offline suite с настоящими локальными MCP subprocesses и mock LLM; provider
POST нет. Видео записывает владелец самостоятельно; данный документ — сценарий.
