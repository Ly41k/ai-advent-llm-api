# День 25: два scripted диалога

Это воспроизводимый HTTP/SQLite-стенд, не живой Ollama. Hash embeddings и scripted coverage не подтверждают семантическое качество ответов.

## scheduler

После хода 6 обе базы переоткрыты.

### Ход 1

Пользователь: Цель: Разобраться в планировщике дня 18 и подготовить его проверку.
Ограничение: Используем SQLite.
Какой процесс выполняет фоновые задания на день 18?

Самостоятельный вопрос: День 18. Какой процесс выполняет фоновые задания на день 18?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

# День 18 — Планировщик и фоновые задачи [1]
- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
## Проверка пунктов задания [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5619

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 2

Пользователь: Ограничение: Worker должен работать отдельно от чата.
Какие поля GitHub сохраняет worker на день 18?

Самостоятельный вопрос: День 18. Какие поля GitHub сохраняет worker на день 18?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
Бублик через MCP ставит публичный GitHub-репозиторий на периодическое наблюдение. Отдельный worker постоянно проверяет расписание, сохраняет снимки в SQLite и печатает агрегированную сводку в журнал после каждого запуска. Агент по запросу читает сохранённую сводку через MCP и отвечает с её данными. [1]
Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему. [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5478

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 3

Пользователь: Термин: снимок = сохранённые данные GitHub
А где это хранится?

Самостоятельный вопрос: День 18. А где это хранится?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]
```bash
.venv/bin/python day-18-scheduled-mcp/main.py
```
[1]
```bash
.venv/bin/python day-18-scheduled-mcp/worker.py
```
[1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.4917

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 4

Пользователь: Уточнение: Речь о расписании дня 18.
Какой инструмент создаёт расписание?

Самостоятельный вопрос: День 18. Какой инструмент создаёт расписание?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
Бублик через MCP ставит публичный GitHub-репозиторий на периодическое наблюдение. Отдельный worker постоянно проверяет расписание, сохраняет снимки в SQLite и печатает агрегированную сводку в журнал после каждого запуска. Агент по запросу читает сохранённую сводку через MCP и отвечает с её данными. [1]
| Пункт | Реализация | Проверка |
|---|---|---|
| MCP-инструмент с периодическим выполнением | `schedule_github_summary` + `worker.py` | `McpTests`, `SchedulerTests` |
| Данные сохраняются | `jobs`, `snapshots`, `runs` в SQLite | восстановление после создания нового `Scheduler` |
| Выполняется по расписанию | `next_run`, периодический цикл, `Restart=always` в systemd | повторный сбор при сдвиге часов, отсутствие преждевременного повтора |
| Возвращает агрегированный результат | `get_github_summary`: latest, change, samples | проверка двух снимков и ответа агента |
| Работает [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5243

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 5

Пользователь: Когда назначается первый сбор на день 18?

Самостоятельный вопрос: День 18. Когда назначается первый сбор на день 18?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]
| Пункт | Реализация | Проверка |
|---|---|---|
| MCP-инструмент с периодическим выполнением | `schedule_github_summary` + `worker.py` | `McpTests`, `SchedulerTests` |
| Данные сохраняются | `jobs`, `snapshots`, `runs` в SQLite | восстановление после создания нового `Scheduler` |
| Выполняется по расписанию | `next_run`, периодический цикл, `Restart=always` в systemd | повторный сбор при сдвиге часов, отсутствие преждевременного повтора |
| Возвращает агрегированный результат | `get_github_summary`: latest, change, samples | проверка двух снимков и ответа агента |
| Работает [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5302

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 6

Пользователь: А какой у него допустимый интервал?

Самостоятельный вопрос: День 18. А какой у него допустимый интервал?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]
```bash
.venv/bin/python day-18-scheduled-mcp/main.py
```
[1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.4999

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 7

Пользователь: Что возвращает get_github_summary на день 18?

Самостоятельный вопрос: День 18. Что возвращает get_github_summary на день 18?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
| Пункт | Реализация | Проверка |
|---|---|---|
| MCP-инструмент с периодическим выполнением | `schedule_github_summary` + `worker.py` | `McpTests`, `SchedulerTests` |
| Данные сохраняются | `jobs`, `snapshots`, `runs` в SQLite | восстановление после создания нового `Scheduler` |
| Выполняется по расписанию | `next_run`, периодический цикл, `Restart=always` в systemd | повторный сбор при сдвиге часов, отсутствие преждевременного повтора |
| Возвращает агрегированный результат | `get_github_summary`: latest, change, samples | проверка двух снимков и ответа агента |
| Работает [1]
Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5370

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 8

Пользователь: Что возвращает list_scheduled_jobs на день 18?

Самостоятельный вопрос: День 18. Что возвращает list_scheduled_jobs на день 18?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
| Пункт | Реализация | Проверка |
|---|---|---|
| MCP-инструмент с периодическим выполнением | `schedule_github_summary` + `worker.py` | `McpTests`, `SchedulerTests` |
| Данные сохраняются | `jobs`, `snapshots`, `runs` в SQLite | восстановление после создания нового `Scheduler` |
| Выполняется по расписанию | `next_run`, периодический цикл, `Restart=always` в systemd | повторный сбор при сдвиге часов, отсутствие преждевременного повтора |
| Возвращает агрегированный результат | `get_github_summary`: latest, change, samples | проверка двух снимков и ответа агента |
| Работает [1]
Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5327

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 9

Пользователь: Что происходит с пропущенными заданиями после простоя worker на день 18?

Самостоятельный вопрос: День 18. Что происходит с пропущенными заданиями после простоя worker на день 18?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

Бублик через MCP ставит публичный GitHub-репозиторий на периодическое наблюдение. Отдельный worker постоянно проверяет расписание, сохраняет снимки в SQLite и печатает агрегированную сводку в журнал после каждого запуска. Агент по запросу читает сохранённую сводку через MCP и отвечает с её данными. [1]
| Пункт | Реализация | Проверка |
|---|---|---|
| MCP-инструмент с периодическим выполнением | `schedule_github_summary` + `worker.py` | `McpTests`, `SchedulerTests` |
| Данные сохраняются | `jobs`, `snapshots`, `runs` в SQLite | восстановление после создания нового `Scheduler` |
| Выполняется по расписанию | `next_run`, периодический цикл, `Restart=always` в systemd | повторный сбор при сдвиге часов, отсутствие преждевременного повтора |
| Возвращает агрегированный результат | `get_github_summary`: latest, change, samples | проверка двух снимков и ответа агента |
| Работает [1]
Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5715

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 10

Пользователь: Отправляет ли worker дня 18 результаты в чат автоматически?

Самостоятельный вопрос: День 18. Отправляет ли worker дня 18 результаты в чат автоматически?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]
Данные `schedule.db` сохраняются между перезапусками; файл исключён из Git. Временные метки — UTC. Пропущенные во время простоя запуски не воспроизводятся пачкой: после старта worker выполнит каждый просроченный job один раз. Рекомендуется один экземпляр worker. Сообщения о завершении worker печатает в stdout/systemd journal; автоматическая отправка сообщений в чат не реализована. [1]
Бублик через MCP ставит публичный GitHub-репозиторий на периодическое наблюдение. Отдельный worker постоянно проверяет расписание, сохраняет снимки в SQLite и печатает агрегированную сводку в журнал после каждого запуска. Агент по запросу читает сохранённую сводку через MCP и отвечает с её данными. [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5474

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 11

Пользователь: Нужен ли worker дня 18 ключ Groq?

Самостоятельный вопрос: День 18. Нужен ли worker дня 18 ключ Groq?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему. [1]
Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]
- `schedule_github_summary(owner, repo, interval_minutes)` создаёт или обновляет расписание (1–10080 минут); первый сбор назначается сразу.
- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.
- `get_github_summary(owner, repo, limit)` возвращает количество снимков, последнее состояние и изменения относительно самого старого из выбранных снимков.
- `list_scheduled_jobs()` возвращает текущее расписание, время следующего запуска и ошибку.
- `main.py` запускает интерактивного агента с Groq, который получает схемы MCP и использует результаты инструментов. [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5511

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 12

Пользователь: Где посмотреть журнал worker дня 18?

Самостоятельный вопрос: День 18. Где посмотреть журнал worker дня 18?

Цель: Разобраться в планировщике дня 18 и подготовить его проверку.

Бублик через MCP ставит публичный GitHub-репозиторий на периодическое наблюдение. Отдельный worker постоянно проверяет расписание, сохраняет снимки в SQLite и печатает агрегированную сводку в журнал после каждого запуска. Агент по запросу читает сохранённую сводку через MCP и отвечает с её данными. [1]
Скажите Бублику: «Каждые 60 минут собирай данные репозитория Ly41k/ai-advent-llm-api». Worker получит первый снимок не позднее 15 секунд после создания расписания. Затем спросите: «Покажи сводку Ly41k/ai-advent-llm-api». Без Groq можно проверить worker командой
`.venv/bin/python day-18-scheduled-mcp/worker.py --once` после создания расписания через MCP.. [1]
```bash
.venv/bin/python day-18-scheduled-mcp/worker.py
```
[1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5261

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

## orchestration

После хода 6 обе базы переоткрыты.

### Ход 1

Пользователь: Цель: Подготовить демонстрацию полного MCP-флоу дня 20.
Ограничение: Без VPS.
Какие MCP-серверы зарегистрированы на день 20?

Самостоятельный вопрос: День 20. Какие MCP-серверы зарегистрированы на день 20?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api
```
[1]
модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [1]
`mcp_registry.py` регистрирует серверы, формирует уникальные имена вида `github__get_repository_info` и маршрутизирует вызов к исходному имени инструмента в нужной сессии. Модель видит короткие коды операций `FETCH`, `SUMMARIZE`, `SAVE`, `READ`, `VERIFY` и предлагает следующий код в строгом JSON: `{"operation":"FETCH"}`. `BublikOrchestrator` сопоставляет код с найденным MCP-инструментом, проверяет порядок, подставляет данные предыдущих результатов и вызывает нужный сервер. Если модель предлагает шаг слишком рано, агент выбирает допустимый следующий шаг и отмечает `agent correction` в выводе. Модели не нужно формировать нативный `tool_call` Groq или копировать Markdown отчёта в аргументы. Реальные входные схемы MCP остаются в реестре; каждый сервер валидирует полученный вызов. При успешном запросе путь следующий: [2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4746
[2] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.6365

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 2

Пользователь: Ограничение: Проверяем сохранённый файл.
Какие инструменты публикует сервер storage на день 20?

Самостоятельный вопрос: День 20. Какие инструменты публикует сервер storage на день 20?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

| Сервер | Инструменты | Задача |
|---|---|---|
| `github` | `get_repository_info` | Получить метаданные GitHub |
| `analysis` | `summarize_repository`, `verify_report` | Подготовить сводку, затем проверить сохранённый текст |
| `storage` | `save_report`, `read_report` | Сохранить и перечитать файл | [1]
Бублик подключается к **трём независимым MCP-серверам** через stdio. Каждый сервер стартует отдельным процессом и публикует инструменты через `list_tools()`: [1]
| Пункт | Где реализован и чем проверен |
|---|---|
| Несколько зарегистрированных серверов | Три процесса в `connect_servers()`; тест проверяет пять инструментов в трёх сессиях |
| Агент выбирает инструмент | Выбор кода операции моделью или обозначенный в выводе выбор агентом при неправильном ответе модели; тест отдельно проверяет `info` (1 вызов), `summary` (2 вызова), `report` (5 вызовов) |
| Корректная маршрутизация | `ToolRegistry.call()` по пространству имён; тест проверяет принадлежность каждого шага серверу и отказ неизвестному имени |
| Длинный флоу | Пять последовательных вызовов и ответ; интеграционный и CLI-тесты |
| Инструменты разных серверов | Проверен порядок `github → analysis → storage → storage → analysis` |
| Выбор и порядок вызовов | Проверка `FLOW`, передачи точных данных между серверами, исправления преждевременного `VERIFY` и отказа при ответе, который не соответствует JSON-схеме | [2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.6301
[2] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4761

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 3

Пользователь: Термин: отчёт = сохранённая Markdown-сводка
А какие инструменты у analysis?

Самостоятельный вопрос: День 20. А какие инструменты у analysis?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

| Пункт | Где реализован и чем проверен |
|---|---|
| Несколько зарегистрированных серверов | Три процесса в `connect_servers()`; тест проверяет пять инструментов в трёх сессиях |
| Агент выбирает инструмент | Выбор кода операции моделью или обозначенный в выводе выбор агентом при неправильном ответе модели; тест отдельно проверяет `info` (1 вызов), `summary` (2 вызова), `report` (5 вызовов) |
| Корректная маршрутизация | `ToolRegistry.call()` по пространству имён; тест проверяет принадлежность каждого шага серверу и отказ неизвестному имени |
| Длинный флоу | Пять последовательных вызовов и ответ; интеграционный и CLI-тесты |
| Инструменты разных серверов | Проверен порядок `github → analysis → storage → storage → analysis` |
| Выбор и порядок вызовов | Проверка `FLOW`, передачи точных данных между серверами, исправления преждевременного `VERIFY` и отказа при ответе, который не соответствует JSON-схеме | [1]
| Сервер | Инструменты | Задача |
|---|---|---|
| `github` | `get_repository_info` | Получить метаданные GitHub |
| `analysis` | `summarize_repository`, `verify_report` | Подготовить сводку, затем проверить сохранённый текст |
| `storage` | `save_report`, `read_report` | Сохранить и перечитать файл | [2]
```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api
```
[1]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4508
[2] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.5769

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 4

Пользователь: Уточнение: Нужен полный маршрут report.
В каком порядке выполняется полный флоу дня 20?

Самостоятельный вопрос: День 20. В каком порядке выполняется полный флоу дня 20?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

| Пункт | Где реализован и чем проверен |
|---|---|
| Несколько зарегистрированных серверов | Три процесса в `connect_servers()`; тест проверяет пять инструментов в трёх сессиях |
| Агент выбирает инструмент | Выбор кода операции моделью или обозначенный в выводе выбор агентом при неправильном ответе модели; тест отдельно проверяет `info` (1 вызов), `summary` (2 вызова), `report` (5 вызовов) |
| Корректная маршрутизация | `ToolRegistry.call()` по пространству имён; тест проверяет принадлежность каждого шага серверу и отказ неизвестному имени |
| Длинный флоу | Пять последовательных вызовов и ответ; интеграционный и CLI-тесты |
| Инструменты разных серверов | Проверен порядок `github → analysis → storage → storage → analysis` |
| Выбор и порядок вызовов | Проверка `FLOW`, передачи точных данных между серверами, исправления преждевременного `VERIFY` и отказа при ответе, который не соответствует JSON-схеме | [1]
модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [1]
`--offline` заменяет выбор модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4541
[2] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.5804

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 5

Пользователь: Когда отчёт дня 20 считается завершённым?

Самостоятельный вопрос: День 20. Когда отчёт дня 20 считается завершённым?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

Последний шаг сравнивает сводку с прочитанным из файла текстом. Отчёт считается завершённым только при `verified=true`. Для выбора Groq получает `response_format` со строгой JSON-схемой и допустимыми кодами операций. При HTTP 400 `tool_use_failed` агент выбирает следующий шаг по проверенному порядку и пишет `selected by agent fallback`; при преждевременном выборе модели пишет `selected by agent correction`. Эти шаги нельзя выдавать за выбор модели. После проверки агент формирует ответ из MCP-результатов без шестого запроса к модели. День 19 использовал один MCP-сервер и фиксированные три вызова; здесь серверы и сессии отдельные, а задача выбирает один из трёх маршрутов. [1]
```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api
```
[2]
модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.6076
[2] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4558

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 6

Пользователь: А что именно сравнивает последний шаг?

Самостоятельный вопрос: День 20. А что именно сравнивает последний шаг?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

Последний шаг сравнивает сводку с прочитанным из файла текстом. Отчёт считается завершённым только при `verified=true`. Для выбора Groq получает `response_format` со строгой JSON-схемой и допустимыми кодами операций. При HTTP 400 `tool_use_failed` агент выбирает следующий шаг по проверенному порядку и пишет `selected by agent fallback`; при преждевременном выборе модели пишет `selected by agent correction`. Эти шаги нельзя выдавать за выбор модели. После проверки агент формирует ответ из MCP-результатов без шестого запроса к модели. День 19 использовал один MCP-сервер и фиксированные три вызова; здесь серверы и сессии отдельные, а задача выбирает один из трёх маршрутов. [1]
```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api
```
[2]
модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.5714
[2] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4342

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 7

Пользователь: Что делает агент дня 20 при преждевременном выборе VERIFY?

Самостоятельный вопрос: День 20. Что делает агент дня 20 при преждевременном выборе VERIFY?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

Последний шаг сравнивает сводку с прочитанным из файла текстом. Отчёт считается завершённым только при `verified=true`. Для выбора Groq получает `response_format` со строгой JSON-схемой и допустимыми кодами операций. При HTTP 400 `tool_use_failed` агент выбирает следующий шаг по проверенному порядку и пишет `selected by agent fallback`; при преждевременном выборе модели пишет `selected by agent correction`. Эти шаги нельзя выдавать за выбор модели. После проверки агент формирует ответ из MCP-результатов без шестого запроса к модели. День 19 использовал один MCP-сервер и фиксированные три вызова; здесь серверы и сессии отдельные, а задача выбирает один из трёх маршрутов. [1]
| Пункт | Где реализован и чем проверен |
|---|---|
| Несколько зарегистрированных серверов | Три процесса в `connect_servers()`; тест проверяет пять инструментов в трёх сессиях |
| Агент выбирает инструмент | Выбор кода операции моделью или обозначенный в выводе выбор агентом при неправильном ответе модели; тест отдельно проверяет `info` (1 вызов), `summary` (2 вызова), `report` (5 вызовов) |
| Корректная маршрутизация | `ToolRegistry.call()` по пространству имён; тест проверяет принадлежность каждого шага серверу и отказ неизвестному имени |
| Длинный флоу | Пять последовательных вызовов и ответ; интеграционный и CLI-тесты |
| Инструменты разных серверов | Проверен порядок `github → analysis → storage → storage → analysis` |
| Выбор и порядок вызовов | Проверка `FLOW`, передачи точных данных между серверами, исправления преждевременного `VERIFY` и отказа при ответе, который не соответствует JSON-схеме | [2]
Этот запуск обращается к Groq и GitHub. Модель `openai/gpt-oss-20b` может быть недоступна для конкретного аккаунта; значение `MODEL` задаётся в `agent.py`. При неверном выборе инструмента или неполном результате агент выдаст ошибку, а не заявит об успешном отчёте. Повторный запуск безопасно заменяет файл. VPS и worker для этого сценария не нужны. [2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.5997
[2] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4784

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 8

Пользователь: Какой маршрут выбирается для --task info на день 20?

Самостоятельный вопрос: День 20. Какой маршрут выбирается для --task info на день 20?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task info
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task summary
```
[1]
Агент также понимает два коротких запроса: `--task info` вызывает только GitHub, `--task summary` вызывает GitHub и analysis без сохранения файла. По умолчанию `--task report` запускает полный сценарий. Это позволяет проверить выбор *нужного набора* инструментов для разных пользовательских задач. [1]
```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task info
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task summary
```
[2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.6184
[2] day-20-mcp-orchestration/README.md:1-40 | section=README.md | chunk_id=d51bc9e2de0500131e22 | cosine=0.5448

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 9

Пользователь: Какой маршрут выбирается для --task summary на день 20?

Самостоятельный вопрос: День 20. Какой маршрут выбирается для --task summary на день 20?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [1]
`--offline` заменяет выбор модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [2]
```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task info
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline --task summary
```
[2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4794
[2] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.6184

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 10

Пользователь: Для сравнения: какой процесс дня 18 выполняет фоновые задачи?

Самостоятельный вопрос: День 18. Для сравнения: какой процесс дня 18 выполняет фоновые задачи?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

# День 18 — Планировщик и фоновые задачи [1]
Создайте расписание через `main.py` на том же VPS (или вызвав его MCP-сервер с тем же `BUBLIK_DB_PATH`). Для worker не требуется Groq key: нужен доступ к `api.github.com`; `GITHUB_TOKEN` для публичных репозиториев необязателен, но помогает с лимитами. Установите переменную окружения для обоих процессов, если база находится в другом месте. Проверяйте `journalctl` и запрашивайте свежую сводку через агента. Установить сервис на конкретном VPS можно только при наличии доступа к нему. [1]
**[Пошаговая проверка каждого пункта](VERIFY.ru.md)** — команды для локального запуска и отдельная проверка на VPS. [1]

Источники / Sources:
[1] day-18-scheduled-mcp/README.ru.md:1-67 | section=README.ru.md | chunk_id=b165333c1d1e56698605 | cosine=0.5546

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 11

Пользователь: Вернёмся к цели дня 20: что делает mcp_registry.py?

Самостоятельный вопрос: День 20. Вернёмся к цели дня 20: что делает mcp_registry.py?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

`mcp_registry.py` регистрирует серверы, формирует уникальные имена вида `github__get_repository_info` и маршрутизирует вызов к исходному имени инструмента в нужной сессии. Модель видит короткие коды операций `FETCH`, `SUMMARIZE`, `SAVE`, `READ`, `VERIFY` и предлагает следующий код в строгом JSON: `{"operation":"FETCH"}`. `BublikOrchestrator` сопоставляет код с найденным MCP-инструментом, проверяет порядок, подставляет данные предыдущих результатов и вызывает нужный сервер. Если модель предлагает шаг слишком рано, агент выбирает допустимый следующий шаг и отмечает `agent correction` в выводе. Модели не нужно формировать нативный `tool_call` Groq или копировать Markdown отчёта в аргументы. Реальные входные схемы MCP остаются в реестре; каждый сервер валидирует полученный вызов. При успешном запросе путь следующий: [1]
Этот запуск обращается к Groq и GitHub. Модель `openai/gpt-oss-20b` может быть недоступна для конкретного аккаунта; значение `MODEL` задаётся в `agent.py`. При неверном выборе инструмента или неполном результате агент выдаст ошибку, а не заявит об успешном отчёте. Повторный запуск безопасно заменяет файл. VPS и worker для этого сценария не нужны. [2]
```bash
.venv/bin/python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api
```
[2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.5826
[2] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4652

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}

### Ход 12

Пользователь: Требуются ли для сценария дня 20 VPS и worker?

Самостоятельный вопрос: День 20. Требуются ли для сценария дня 20 VPS и worker?

Цель: Подготовить демонстрацию полного MCP-флоу дня 20.

Этот запуск обращается к Groq и GitHub. Модель `openai/gpt-oss-20b` может быть недоступна для конкретного аккаунта; значение `MODEL` задаётся в `agent.py`. При неверном выборе инструмента или неполном результате агент выдаст ошибку, а не заявит об успешном отчёте. Повторный запуск безопасно заменяет файл. VPS и worker для этого сценария не нужны. [1]
модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [1]
`--offline` заменяет выбор модели воспроизводимым локальным планировщиком; при этом три настоящих MCP-сервера и GitHub API продолжают работать. В выводе будет пять нумерованных вызовов и подтверждение проверки файла `day-20-mcp-orchestration/reports/Ly41k-ai-advent-llm-api-summary.md`. Для публичного репозитория `GITHUB_TOKEN` необязателен, но помогает при ограничении числа запросов GitHub. [2]

Источники / Sources:
[1] day-20-mcp-orchestration/README.ru.md:42-63 | section=README.ru.md | chunk_id=f777f638ca3452e9cfc5 | cosine=0.4969
[2] day-20-mcp-orchestration/README.ru.md:1-50 | section=README.ru.md | chunk_id=7e5cad922782fa195336 | cosine=0.6058

Checks: {"answered": true, "fresh_retrieval": true, "source_contract": true, "expected_source": true, "goal_retained": true, "sources_rendered": true, "no_planning_warnings": true, "coverage_pass": true}
