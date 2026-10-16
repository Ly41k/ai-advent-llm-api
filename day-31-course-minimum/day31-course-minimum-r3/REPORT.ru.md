# Course Minimum r3 — исправление Mac preflight

16.10.2026. **32/32 локальных tests passed, Linux/Python3.12.14, 18.162s; 0 Qwen, 0 embeddings, 0 index builds.** Mac preflight r3 пока не выполнялся. Day31 course minimum not_accepted; extended Stage7 paused/incomplete; Stage8 not_started.

## Дефект и минимальное исправление

В r2 `entry.main` оборачивал `prepare` в `no_network`. Внутри `prepare` реальный `ModelSession.status()` вызывает исходный `check_day30_off()`; его `port_check(8000)` выполняет TCP handshakes к literal IPv4/IPv6 loopback. Network guard останавливал этот обязательный safety probe до targeted tests. Прежние session tests мокировали status целиком и не обнаружили интеграционную ошибку.

Присланный Mac bundle фиксирует общий отказ `No model/network calls in offline checks.`, без stack locations. Он содержит 64 reports и 0 новых dispatch/reservation/terminal calls. Причина установлена по последовательности существующего кода; новый regression test использует настоящие ModelSession.status/check_day30_off/port_check. OS witnesses и socket outcomes в нём синтетические, что отдельно указано в witness.

Исправлен только внешний network guard: в пределах вызова неизменённого доверенного `port_check(8000)` разрешены TCP handshakes строго к `127.0.0.1:8000` и `[::1]:8000`. Это не HTTP/LLM request; исходный port_check не отправляет payload. Прямой connect вне функции остаётся запрещён, даже к8000. ContextVar capability сбрасывается после normal return/exception и корректно работает с вложенными guards. Другие hosts/ports, включая Ollama11434, запрещены и внутри этого scope. Активность Day30/неопределённость по-прежнему дают прежний строгий отказ.

Дополнительно r3 сохраняет тип исключения и stack file/line/function, без locals. Это предотвращает повторение непрозрачной диагностики r2. Новый work отдельный, старые не удаляются.

## Изменённые файлы относительно r2

- `course_runtime.py`: узкий scoped Day30 probe и метка версии r3.
- `test_course.py`: 8 новых регрессионных тестов; export test дополнен проверкой сохранности всех64 reports.
- `entry.py`: версия/work r3, сохранение прежних64 reports, stack locations при preflight failure.
- `dependency-pins.json`, `manifest.json`, `inputs/r2-mac-preflight-stopped.json`: фиксация точного предыдущего отказа и новых файлов.
- `README.ru.md`, `REPORT.ru.md`, `reports/`: команды, результаты и доказательства.

`bootstrap_course.py`, `check_local.py`, fixture/synthetic workers, весь vendored Publication Gate v104-r2, исходные v103/v104 packages и original App0.7.29 не изменены. `main.py` установленного приложения не заменяется. Prompt, retrieval, source-anchor limits, критерии semantic gate и questions прежние. Backlog неизменён.

## Проверки

Прежние 24 целевые проверки r2 повторены из-за изменения guard вокруг всего preflight; passed. Это не новая полная исследовательская регрессия. Mac83 и native276 не повторялись.

8 новых tests подтверждают:

1. Настоящий port_check8000 допускает только два ожидаемых handshakes с синтетическим ConnectionRefusedError.
2. Прямые connect к8000, Ollama11434, внешнему адресу и другому порту блокируются до transport.
3. Scoped probe нельзя использовать для Ollama/другого probe port.
4. Настоящий ModelSession.status с original Day30 probe проходит при подтверждённом synthetic epoch и выключенном service; inference/session_modified=false.
5. Активный Day30 сохраняет `day30_service_active`.
6. Неопределённая проверка сохраняет `day30_isolation_unverified`.
7. Exception не оставляет сетевое разрешение активным.
8. Вложенные offline guards сохраняют scoped probe и запрет прямого connect.

Прежние checks по настоящим MCP/orchestrator/owned FTS/Verification workers на временном публичном repo, exact claims/anchors, needs_review gate, synthetic human positive path, runtime refusal, immutable audit, foreign/stale evidence, replay protection, cleanup и preflight receipts остаются PASS. В model-path tests transport синтетический; реального human approval и fresh generation нет.

Первый локальный r3 test run сохранён: 1 failure +3 errors из-за неверной сигнатуры mock connect (unbound method получает socket+address). Исправлены fixture arguments/assertions и ожидаемые названия error codes; runtime guard между этим и окончательным PASS не менялся. Этот промежуточный report не скрыт и не считается успешным.

## Сохранность и bundle

Точная копия присланного r2 bundle — `inputs/r2-mac-preflight-stopped.json`, SHA256 `eb1eed17118ef1ced938e168388d9b15e3a3064f34600eee4609f7b58828492b`. Все64 reports, включая исходные61, включаются в r3 bundle без изменения data/SHA. Исторический отказ r2 не переписывается в PASS.

`reports/preservation.json` подтверждает source hashes60 до/после, неизменные v103/v104 manifest files и Publication Gate, прежние44/54 SQLite hashes. Индексы не создавались/не перестраивались. Добавление штатных новых research traces не заменяет старые данные. Новые work/artifacts публикуются exclusive, r2-work не используется.

`reports/local-checks.json` содержит test log и witnesses, в том числе реальный MCP/lifecycle trace, synthetic worker/publication audit и новый session-port-probe regression witness. `reports/local-bundle.json` — совместимый единый offline bundle. Он не является Mac preflight receipt.

## Следующий шаг и граница

Выполнить только r3 Mac preflight по README. PASS ожидает tests_run32/qwen_calls0/embedding_calls0 и настоящий smoke на пользовательском repo. При ошибке остановиться и передать bundle; stack поможет локализовать оставшееся различие Mac окружения.

Никакой команды live сейчас не выполнять. После успешного Mac preflight остаётся отдельное согласование одного RU1/Multi Qwen call, проверка фактов/полноты/exact anchors, явное human review новых immutable bindings и положительная публикация. EN3, full Chain и Research backlog не менялись и не объявлены завершёнными.
