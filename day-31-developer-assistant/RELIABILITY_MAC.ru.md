# Этап 6 — Reliability, v0.5.0

Этап 5 принят по Mac v0.4.1: 131/131 tests, actual MCP/FTS smoke и три настоящих
Qwen calls. RU history answer и EN API-prefix/branch answer поддерживаются
приведёнными цитатами и Git observation. На mixed request Documentation/Main
имеют отдельные task IDs, message/context digests. Hidden retries/cloud fallback
отсутствуют. Это smoke, не held-out оценка общего качества.

Этап 6 подготовлен и требует Mac-проверки. Полный suite содержит 154 tests.
Здесь прошли 130 разных локальных checks: 75 Foundation/RAG, 27 pipeline,
23 reliability и 5 ранее существовавших owned-process checks. Новый native
MCP/Qwen/M1 запуск здесь не выполнен. Источник: reports/verified/stage6-v050-offline.json.
В Qwen/Git fault fixtures ответы синтетические; реальные SQLite/FTS, процессы,
kill/reap, lock files и uncertain checkpoint проверяются отдельно от модели.

## Запуск на Mac

Из корня repo в вашей существующей Python 3.13 .venv. Dependencies прежние.
Day30, Revik и другие Ollama clients выключены в выделенной сессии.

```bash
unzip -o ~/Downloads/day31-stage6-v050.zip -d "$PWD"
python day-31-developer-assistant/main.py --version
python day-31-developer-assistant/main.py index verify
python day-31-developer-assistant/main.py models status
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage6.py --live --output /tmp/day31-stage6-mac-v050.json
```

Версия 0.5.0. Индекс НЕ пересобирать после проверенного v0.4.0/v0.4.1:
project/docs совпадают побайтно, текущий корпус 40 docs / 380 chunks. README
дня31, reports и инструкции harness не входят в project corpus.
Output должен быть новым файлом. Пришлите JSON и вывод models status/index verify.
Неудачу не обходить повторными запусками до PASS.

check_stage6 сначала запускает весь suite и temporary-index actual-project smoke
с real MCP branch/unknown, без модели. Только после успеха при --live проверяет
session gate и запускает два прежних RU/EN requests — максимум три генерации.
В новом report FORMAT stage6-v1 есть retry_policy, model_session_status,
stage/task timings, raw model tokens и http_events. Fault injection из unit suite
не выдаётся за реальные сбои Ollama. Без --live модель не запускается.

## Ошибки и повтор

- Только transport/IO failure на /api/tags, /api/show или /api/ps ДО dispatch:
  один metadata retry на весь model task, задержка 0.05 s, повторная проверка
  lease/epoch, всё входит в существующий deadline. Каждая HTTP-попытка учтена.
- HTTP status error, malformed metadata, wrong profile, schema/output/evidence,
  permission, stale и no-evidence не повторяются.
- /api/chat и /api/embed никогда автоматически не повторяются. Если dispatch
  мог состояться и terminal response не подтверждён, checkpoint остаётся uncertain.
- MCP tool replay/reconnect — 0. При обрыве owned server закрывается средствами
  прежнего MCP adapter; новое соединение возникает только в новом пользовательском
  запросе. Автоматический reconnect не добавлен как обязательная возможность.
- Qwen client single-use. Новая попытка пользователя — новый request/task и report.
  Перезапуск сервиса/модели, облачный fallback и repair-until-PASS отсутствуют.

Metadata retries показаны отдельно от model_retries=0. Число физического HTTP
доступа нельзя путать с capability_calls (лимит 8 включает role/task capabilities).
Raw counts Ollama не заменяются оценками UTF-8 bytes. Потерянный worker reply
оставляет неизвестное количество inference, а не рисует ноль. Неверные bool/string/
negative/nonfinite telemetry не становятся доверенными tokens/call counts.

## Дедлайн и отмена

Общий absolute deadline применяется ко всем runtime stages и model tasks.
Поглощённая Dispatcher cancellation передаётся Pipeline; после неё модель и
следующие задачи не запускаются. Финальная проверка источников повторно проверяет
deadline, поэтому после истечения verified claims/facts не публикуются.
Cleanup owned processes обязан завершиться даже при повторной cancellation.
Время cleanup может увеличить wall time сверх рабочего deadline; это не разрешение
продолжать модельные задачи. SIGKILL worker не обещает остановку внешнего Ollama.

Unknown по слабым источникам остаётся successful unknown. Technical failure
имеет отдельный execution_status, diagnostics, recovery. При доступных свежих
excerpts и недоступной модели ответ сообщает о них явно; excerpts не становятся
сгенерированными claims. Неудача финальной проверки не скрывается model unknown.
Ошибка записи trace не маскируется как MCP: private_state_unavailable без exception
body; trace_persistence=failed. Traces сохраняются с fsync вне repo.

## models status и recovery

Команда не делает HTTP/model requests и не меняет SESSION.json. Она использует
private lock и существующий OS process witness, проверяет отключение Day30.
Busy gate имеет отдельный model_session_busy, без ожидания или изменения checkpoint.

| Состояние | Действие оператора |
|---|---|
| confirmed, gate_open=true | Можно продолжать в выделенной сессии; это не Qwen generation proof |
| not_confirmed | models prepare → самостоятельно restart Ollama → models confirm |
| prepared / uncertain при том же epoch | Самостоятельно restart Ollama → models confirm |
| epoch_changed | models confirm проверит новый epoch и допустимую topology |
| model_session_busy | Дождаться текущего запроса; затем models status |

/api/ps не idle witness. Recovery после реального обрыва зависит от нового
проверяемого процесса Ollama; фальшивый status или ручная правка SESSION.json
не применяются. Широкие реальные interruption/stress, RAM/swap и held-out semantic
quality остаются открытыми для этапа Research. Дни1–30 и их private DB не менялись.
