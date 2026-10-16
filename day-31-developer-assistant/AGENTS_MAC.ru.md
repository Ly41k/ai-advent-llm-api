# Этап 4 — реальный runtime задач, v0.3.0

Добавлены отдельные TaskEnvelope/ContextEnvelope для Documentation, Git и
Verification. Dispatcher проверяет роли, входы, project/request IDs, зависимости
и бюджеты до выполнения. Ошибка зависимости блокирует проверку и не превращает
непроверенный результат в итоговый факт.

## Что выполняется

1. Main создаёт отдельные задачи с разными task IDs и sealed contexts.
2. Documentation получает только question и запускает реальный FTS по текущему
   project index. Git получает operation/arguments и вызывает настоящий MCP.
3. Независимые задачи работают конкурентно. Verification ждёт обе задачи,
   получает только их bounded results и сверяет source/index versions, точные
   цитаты и координаты, либо schema GitReply.
4. Main объединяет только результаты, перечисленные успешной Verification.
   Lifecycle и context audit возвращаются в JSON-отчёте.

Documentation и Verification исполняются в отдельных owned Python workers,
MCP использует свой stdio server. Root/state/source selection задаёт приложение;
из task context их переопределить нельзя. Код/плагины из анализируемого проекта
не загружаются. Это прикладная граница полномочий, не OS sandbox для враждебного
Python-кода того же пользователя.

В trace есть SPAWN, EXECUTE, WORKER_REAPED, REPORT и MERGE. Audit фиксирует
фактический digest и ключи каждого контекста, не копируя историю Main в другие
роли. Verification context строится после готовности зависимостей.

Ограничения: до 4 tasks/request и до 4 активных tasks, до 8 capability calls,
task deadline до 300 s, общий request deadline до 300 s; CLI demo использует
30 s/task. Context/result snapshots до 24 KB, worker input до 32 KB, stdout
до 26 KB, stderr до 4 KB. Слишком большой результат даёт явную ошибку.
Worker groups завершаются при overflow/timeout/cancel, pipes закрываются,
прямой worker ожидается до выхода. Неудачи не повторяются автоматически.

## Проверка на Mac

Установить полный комплект из корня репозитория:

```bash
unzip -o ~/Downloads/day31-stage4-v030.zip -d "$PWD"
python day-31-developer-assistant/main.py agents demo --question "Как устроена память Бублика?"
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage4.py --output /tmp/day31-stage4-mac-v030.json
```

Не пересобирать существующий hybrid index: demo использует его FTS-часть.
Ожидается completed, три success results, два merged blocks и llm_calls=0.
Verification check `fresh_exact_source_provenance` и MCP Git observation
должны пройти. Suite: 94 tests, OK, status=passed в новом JSON.
check_stage4 создаёт отдельный temporary FTS index для smoke и удаляет его;
производственный index не заменяется.

Дополнительные отдельные роли:

```bash
python day-31-developer-assistant/main.py agents docs --question "What is the API prefix?"
python day-31-developer-assistant/main.py agents git --git-operation branch
```

Stage 4 не запускает модели и не требует резервирования новой Ollama сессии.
Day 30 остаётся отключённым для следующего этапа генерации.

## Доказательства и ограничения

94 tests на Linux/Python 3.13.16 и actual-project runtime smoke прошли;
report: reports/verified/stage4-linux.json. Fault tests используют явно
контролируемые sleeper/overflow workers, подменённую цитату и изменённый source.
Реальные FTS/MCP/worker процессы не заменены моками в успешном smoke.

Canary tests проверяют, что свой вопрос Documentation не попадает в Git или
Verification; caller mutation не меняет sealed context. Capability tests
отклоняют Main/write/extra-history/project/request/dependency нарушения до
execute. Проверены общий budget, successful insufficient_evidence, stale/tamper
refusal, task timeout, request deadline/cancel, worker descendant cleanup и
лимит stdout во время чтения. Запись существующего calibration output теперь
отклоняется до открытия workspace/индекса и любых embeddings.

Verification подтверждает происхождение, точную цитату и schema. Она не
доказывает смысл ответа; Git snapshot сохраняет исходное observed_at и не
снимается заново этой ролью. Results — диагностические результаты задач,
merged содержит только проверенные. Изменение файлов после проверки по-прежнему
требует freshness проверки на следующей границе pipeline.

Независимость LLM contexts пока не проверена: llm_calls=0. Следующий этап
подключит отдельные Qwen requests для Documentation/Main, Router/Chain/Fan-Out,
структурированные claims/evidence IDs и проверку финального синтеза.

## Приёмка поиска перед runtime

Mac v0.2.3: 78/78 tests; real bge-m3 index и 12-case RU/EN comparison на прежнем
корпусе/index UUID. FTS 10/10 hit@5 / MRR .90 / median .084 s; dense 9/10 / .85 /
1.936 s; hybrid 10/10 / .85 / 1.935 s. По 2/2 пустых отрицательных queries.
Dense MRR вырос с .80 до .85 после фильтра заголовков; FTS/hybrid сохранили
показатели. На этом calibration set FTS принят исходным режимом следующего
этапа. Это не универсальная победа FTS и не held-out answer benchmark.
