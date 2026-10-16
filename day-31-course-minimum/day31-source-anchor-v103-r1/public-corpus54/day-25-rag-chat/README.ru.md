[English](README.md) | **Русский**

# День 25 — постоянный RAG-чат с источниками и памятью задачи

День 25 превращает grounded RAG-пайплайн дней 21–24 в постоянный локальный чат Бублика.

Финальная реализация **v24** сохраняет полную историю и подтверждаемую пользовательским текстом task memory в SQLite, разрешает короткие продолжения через ограниченный recent context, делает новый retrieval на каждый обычный вопрос, публикует дословные источники и поддерживает надёжную проверку длинных диалогов через process ownership, checkpoint и resume.

## Финальный статус v24

Приёмка описанных случаев v24 завершена.

- **181 тест Дня 25 — PASS**.
- **169 regression-тестов Days 21–24 — PASS**.
- Финальный live 12+12: **24/24 ответов прошли ручное ревью**.
- **47 точных цитат** сверены с файлами репозитория и диапазонами строк.
- 24 живых вопроса выполнили **48 embedding и 48 search вызовов**.
- `--process-per-turn` использовал **24 отдельных процесса/request ID**.
- Два дополнительных negative-control завершились ожидаемым `unknown`.
- Во всех 26 live-случаях вместе: 24 grounded-ответа, 2 ожидаемых отказа, 51 embedding и 51 search вызов.

Доказательства и подробное ревью:

- [аудит v24](AUDIT_V24.ru.md)
- [установка и короткая проверка v24](RELEASE_V24.ru.md)
- [финальная приёмка v24](ACCEPTANCE_V24.ru.md)
- [ручное ревью 12+12](reports/live/live-long-scenarios-v24-review.ru.md)
- [ревью negative-control](reports/live/negative-controls-v24-review.ru.md)

Эти результаты подтверждают описанные сценарии, но не означают безошибочность модели на любых будущих запросах.

## Архитектура

Путь запроса:

```text
сообщение
  → последние завершённые ходы + task state
  → самостоятельный/resolved вопрос
  → новый embedding
  → scoped candidate retrieval
  → inclusive cosine filter
  → выбор точных доказательств
  → проверка цитат/источников
  → coverage validation
  → ответ + явные источники
  → надёжное сохранение хода
```

День 25 переиспользует текущий Python-код предыдущих этапов:

- **День 21:** корпус, chunking, embeddings, SQLite knowledge base;
- **День 22:** первый полный question → retrieval → context → answer RAG-флоу;
- **День 23:** query rewrite, candidate retrieval, cosine filtering;
- **День 24:** exact quote selection, app-owned citations, strict coverage validation.

День 25 добавляет persistence, conversation planner, task memory, lesson-scoped retrieval, восстановление после сбоев и надёжную evaluation.

Чат **не использует старые ответы ассистента или task memory как доказательство фактов репозитория**. Они помогают разрешать намерение и релевантность; фактический ответ всё равно должен происходить из нового retrieval.

## Требования

- Целевая версия Python **3.13**.
- macOS/Linux и локальная файловая система для v24 ownership (`fcntl` / POSIX advisory locks).
- Локальный Ollama для живого чата/evaluation.
- Groq key для Дня 25 не нужен.
- Базовая реализация Дня 25 использует стандартную библиотеку Python.

Текущий live-профиль:

```text
embedding model: bge-m3
answer model: qwen2.5:14b
strategy: fixed
candidate K: 20
final K: 5
raw cosine threshold: >= 0.50
rewrite: heuristic
coverage: strict
Ollama context: 32768
recent completed history: 4 хода / 2400 символов
task state budget: 6000 символов
```

Символьные лимиты приложения не равны точному числу model tokens.

## Быстрый запуск

Из корня репозитория:

```bash
source .venv/bin/activate

python day-25-rag-chat/test_day25.py -v
python day-25-rag-chat/main.py offline-demo

ollama pull bge-m3
ollama pull qwen2.5:14b

python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify

python day-25-rag-chat/main.py chat
```

Смена answer-модели не требует пересчёта embeddings. Смена embedding-модели требует rebuild.

Индекс Дня 21 содержит корневые README, README дней 1–20 и Python-файлы дней 16–20 без тестов. README дней 21–25 по умолчанию в корпус не входят.

Новый Git commit или изменение корневых README может сделать revision индекса stale. Перед strict live-прогоном выполните build/verify. `--allow-stale-index` существует только как явный override и сохраняет provenance старого индекса в traces.

## CLI

Глобальные параметры должны стоять **до** подкоманды.

Примеры:

```bash
python day-25-rag-chat/main.py --answer-model qwen2.5:7b chat
python day-25-rag-chat/main.py chat --session <ID>
python day-25-rag-chat/main.py ask "А где это хранится?" --session <ID> --output answer.json

python day-25-rag-chat/main.py sessions
python day-25-rag-chat/main.py state <ID>
python day-25-rag-chat/main.py history <ID>
python day-25-rag-chat/main.py export <ID> --output dialogue.json
```

Основные global options:

```text
--db
--chat-db
--url
--model
--answer-model
--verifier-model
--num-ctx
--num-predict
--timeout
--strategy
--candidate-k
--final-k
--min-similarity
--rewrite-method
--history-turns
--coverage-policy
--allow-stale-index
```

## Команды чата

Интерактивный CLI печатает `session=<ID>`. Этот ID можно использовать для продолжения после перезапуска.

| Команда | Действие |
|---|---|
| `/new [title]` | Создать изолированную сессию |
| `/use ID` | Переключиться на сессию |
| `/sessions` | Показать список сессий |
| `/state` | Показать task memory |
| `/history` | Показать полную сохранённую историю, источники и ошибки |
| `/goal TEXT` | Установить или явно изменить цель |
| `/constraint TEXT` | Добавить ограничение |
| `/clarify TEXT` | Добавить пользовательское уточнение |
| `/term NAME=DEFINITION` | Установить/исправить термин |
| `/forget goal` | Очистить цель |
| `/forget constraints KEY` | Удалить одно ограничение |
| `/forget clarifications KEY` | Удалить одно уточнение |
| `/forget terms KEY` | Удалить один термин |
| `/export PATH.json` | Экспортировать history, responses, provenance, state, traces и edit events |
| `/recover` | Восстановить pending-ход после завершения owning process |
| `/help` | Показать помощь |
| `/quit` | Выйти, сохранив сессию |

Пример:

```text
/goal Подготовить проверку планировщика дня 18.
/constraint Используем SQLite.
/clarify Речь о расписании дня 18.
/term снимок=сохранённое состояние GitHub-репозитория
Какой процесс выполняет фоновые задания?
А где это хранится?
/state
/history
/quit
```

## Память задачи

Task state хранится отдельно от обычной истории:

```text
goal
constraints
clarifications
terms
```

Память обновляется как явными командами, так и обычными сообщениями. Поддерживаются размеченные строки `Цель:`, `Ограничение:`, `Уточнение:` и `Термин:`.

Каждое принятое значение памяти должно иметь буквальное evidence в текущем сообщении пользователя. Для записи сохраняются value, evidence, turn и origin.

Основные guards:

- случайный следующий вопрос не заменяет существующую цель;
- stale planner update не может затереть параллельное изменение памяти;
- фрагмент вопроса и сразу же отменённое отрицанием утверждение не становятся memory facts;
- `/forget` — явный путь удаления;
- переполнение task-state budget отклоняет новое обновление видимо, а не удаляет старую информацию.

Literal provenance показывает происхождение текста, но не гарантирует правильность его модельной интерпретации. Для контроля используйте `/state`.

## История, прерывание и восстановление

Полная история хранится в:

```text
day-25-rag-chat/chats.db
```

Planner получает только ограниченное окно последних **завершённых** ходов. Error/pending retries не вытесняют нормальную историю из этого окна.

Сообщение пользователя резервируется в SQLite до model/network work. Обычная техническая ошибка сохраняется как `error`, а не как выдуманный ответ модели.

v24 добавляет ownership live-turn на macOS/Linux:

- два параллельных хода одной сессии блокируются;
- `/recover` не отменяет запрос, пока owning process удерживает OS-lock;
- после crash и освобождения lock recovery помечает pending-ход как error и записывает событие восстановления;
- разные сессии остаются независимыми.

## Ответы и источники

День 25 сохраняет extractive-протокол Дня 24.

Модель выбирает quote IDs из найденных данных; приложение копирует точный текст источника и само назначает:

- номер source;
- путь файла;
- section;
- chunk ID;
- диапазон строк;
- связь claim/quote.

Каждый успешный ответ печатает явный блок `Источники / Sources`.

Если ссылка неоднозначна, retrieval недостаточен, модель вернула unknown или strict validation не прошла, пользователь получает явный отказ/уточнение и **без выдуманного подтверждённого источника**.

Старые ответы и task memory могут помогать понять текущий запрос, но не становятся proof для repository facts.

### Coverage policy

По умолчанию:

```text
--coverage-policy strict
```

Отрицательный coverage блокирует публикацию.

Опционально:

```text
--coverage-policy diagnostic
```

Diagnostic может показать точные фрагменты с явным manual-review warning, сохраняя отрицательный verdict. Такой ход не проходит `coverage_pass` в evaluation Дня 25.

## Lesson-scoped retrieval

Если resolved question явно относится к одному дню, День 25 ограничивает retrieval namespace этого дня **до** candidate/final limits.

При наличии заголовков документов выполняются две свежие dense-ветки:

1. rewritten/current query;
2. тот же query + индексированные заголовки документов выбранного дня.

Для каждого кандидата сохраняется максимальный **реальный cosine** среди веток. Обе ветки и оценки записываются в trace. Порог не снижается.

Исторические assistant answers, task-memory facts, canned answers и synthetic similarity в evidence не добавляются.

## Offline demo

Запуск:

```bash
python day-25-rag-chat/main.py offline-demo
```

Offline demo использует:

- настоящий корпус репозитория;
- настоящий chunker;
- SQLite cosine search;
- контракт настоящего Ollama HTTP client;
- настоящие citation/source validators;
- постоянный chat state и реальный evaluation path.

Заменяется только поведение моделей:

- lexical hash-256 вместо BGE-M3;
- scripted planner/selector/coverage JSON вместо Qwen.

Fixture-параметры retrieval намеренно отличаются от production: `40/20/cosine0.0`.

24 scripted-хода выполняют **48 embedding и 48 search вызовов**, потому что lesson-scoped retrieval использует две свежие query-ветки для каждого scoped turn. Это проверка программных контрактов, а не качества live-модели.

## Два длинных сценария

`scenarios.json` содержит два диалога по 12 user turns:

1. планировщик Дня 18;
2. MCP orchestration Дня 20.

Всего это 24 пользовательских вопроса / 48 сообщений при успешных ответах.

Сценарии проверяют:

- goal;
- constraints;
- clarifications;
- terms;
- короткие follow-up;
- временный detour;
- возвращение к сохранённой цели;
- persistent history и task state.

## Надёжный live-прогон v24

Рекомендуемая финальная команда:

```bash
python day-25-rag-chat/main.py evaluate \
  --process-per-turn \
  --output day-25-rag-chat/reports/check/live-long-scenarios-v24.json
```

`--process-per-turn` запускает каждый вопрос в отдельном CLI-процессе.

После каждого хода evaluator делает checkpoint JSON. Незавершённый отчёт имеет:

```text
run_status=running
```

Продолжение той же проверки с теми же настройками:

```bash
python day-25-rag-chat/main.py evaluate \
  --process-per-turn \
  --resume \
  --output day-25-rag-chat/reports/check/live-long-scenarios-v24.json
```

Resume проверяет scenarios, configuration, index revision, persistent history и сохранённые ответы. Уже завершённые вопросы не вызывают модель повторно. Один ход, успевший commit в SQLite между последним checkpoint и остановкой, может быть восстановлен из authoritative history.

Восстановленный technical error остаётся FAIL. Resume нужен для надёжности и диагностики, а не для превращения прерванного запуска в чистый PASS.

Ожидаемый clean summary:

```text
run_status=completed
user_turns=24
messages_including_answers=48
restart_kind=process_per_turn
all_checks_pass=true
model_quality_verified=false
manual_source_review_required=true
```

Последние два значения намеренно остаются false/true после автоматического PASS: программная проверка не равна человеческому semantic review.

## Финальный live v24

Сохранённый финальный прогон был вручную сверён с acceptance checklist.

Для двух диалогов 12+12 подтверждено:

- 24 ответа;
- 0 отказов;
- 0 technical errors/planner warnings;
- 47 буквальных цитат совпали с файлами и строками;
- 48 embedding вызовов;
- 48 search вызовов;
- 24 разных process ID и request ID;
- в каждой финальной task state сохранены goal, два constraints, clarification и term;
- detour не перезаписал цель Дня 20;
- return-to-goal снова направил retrieval на День 20.

Два дополнительных negative-control тоже прошли:

1. неоднозначное «А где это хранится?» в новой сессии → `unknown / ambiguous_reference`;
2. запрос точного числа строк в локальной `schedule.db` пользователя → `unknown / insufficient_context`.

Во всех 26 проверенных live-случаях: **24 grounded-ответа + 2 ожидаемых unknown, 51 embedding и 51 search вызов**.

Точное ожидаемое содержание каждого хода находится в `ACCEPTANCE_V24.ru.md`.

## Что добавил v24 для надёжности

v24 в основном усиливает честность и durability проверки, а не добавляет новый RAG-функционал.

Добавлено/усилено:

- POSIX lock владельца live-turn;
- корректный recovery после crash;
- один SQLite snapshot для export;
- atomic JSON output;
- защита output-path от chat/index database и SQLite sidecars;
- строгий JSON parser для planner/intermediate model replies;
- запрет duplicate keys и non-finite constants;
- реальные `retrieval_trace`;
- per-turn process evaluation;
- checkpoint после каждого хода;
- безопасный `--resume`;
- reconciliation одного committed-but-uncheckpointed turn;
- повторное вычисление checks из authoritative persistent data;
- независимая проверка quote offsets, source identity, claims и полного rendered answer.

## Файлы

| Файл | Назначение |
|---|---|
| `main.py` | CLI, настройки, Ollama, index revision, evaluation subprocesses |
| `chat_agent.py` | Один ход, свежий retrieval, grounded answer, sources |
| `chat_store.py` | SQLite sessions/history/state, snapshots и turn persistence |
| `lease25.py` | POSIX ownership и защита recovery |
| `conversation.py` | Structured planner, follow-up resolution, bounded context, evidence helpers |
| `memory.py` | Evidence-bound task memory |
| `retrieval25.py` | Lesson namespace retrieval и две query-ветки |
| `requirements25.py` | Intent-aware coverage requirements Дня 25 |
| `io25.py` | Protected/atomic JSON output |
| `evaluate25.py` | Long-scenario evaluator, checkpoint/resume, source checks |
| `scenarios.json` | Два сценария по 12 ходов |
| `offline_demo.py` | Scripted HTTP/SQLite contract fixture |
| `test_day25.py` | Contract/failure/persistence/integration/regression tests |
| `support25.py` | Переиспользование модулей дней 21/23/24 |

## Ограничения

- Локальный single-user CLI, без web-auth и multi-user server.
- Чат не выполняет произвольный пользовательский код.
- Чат не вызывает внешние MCP tools.
- Полная история хранится без потерь, но model context намеренно ограничен.
- Старые детали вне task state и recent completed history могут потребовать уточнения.
- Planner может ошибочно интерпретировать намерение даже при корректном literal provenance.
- Точная цитата доказывает provenance, но не автоматически полноту смысла.
- Live-model quality относится к проверенным prompts/models/settings.
- POSIX ownership рассчитан и проверен для macOS/Linux на локальной файловой системе.

## Исторические документы

Основной README теперь описывает финальное поведение v24. Подробности промежуточных исправлений остаются в репозитории для аудита:

`LONG_SCENARIO_FIX.ru.md`, `TABLE_AUDIT_FIX.ru.md`, `MIXED_PROOF_FIX.ru.md`,
`SELECTION_FIX.ru.md`, `FRAGMENT_QUALITY_FIX.ru.md`, `PROCESS_SCOPE_FIX.ru.md`,
`DRAFT_FRAGMENT_FIX.ru.md`, `PYTHON_FRAGMENT_FIX.ru.md`,
`SELECTION_DOMAIN_FIX.ru.md`, `CONDITIONAL_AUDIT_FIX.ru.md`,
`REQUIREMENTS_INTENT_FIX.ru.md`, `SOURCE_UNIT_FIX.ru.md`,
`RELEASE_V22.ru.md`, `RELEASE_V23.ru.md`, `RELEASE_V24.ru.md` и
`AUDIT_V24.ru.md`.

Для финального состояния сдачи начинайте с `AUDIT_V24.ru.md` и `ACCEPTANCE_V24.ru.md`.
