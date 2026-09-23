[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до агента с состоянием

Практический проект по работе с LLM API. Каждый день добавляет один новый механизм: управление ответом, сравнение моделей, постоянную историю, подсчёт токенов, сжатие и стратегии контекста, явные слои памяти, персонализацию, формальное состояние задачи, неизменяемые инварианты, контролируемый жизненный цикл, подключение MCP и вызов MCP-инструмента вокруг реального API.

Все задания объединены одной историей. **Чебуратор** — капитан исследовательского корабля, а **Бублик** постепенно развивается из простого консольного помощника в персонализированного автономного агента.

## Выполненные задания

| День | Тема | Результат |
|---|---|---|
| [День 1](day-01-first-api-request/README.ru.md) | Первый API-запрос | Консольный чат с историей текущего сеанса |
| [День 2](day-02-response-control/README.ru.md) | Управление ответом | Контроль структуры, длины и правил ответа |
| [День 3](day-03-reasoning-methods/README.ru.md) | Способы рассуждения | Сравнение четырёх подходов к одной задаче |
| [День 4](day-04-temperature/README.ru.md) | Температура | Сравнение точности, креативности и вариативности |
| [День 5](day-05-model-versions/README.ru.md) | Версии моделей | Сравнение качества, скорости, токенов и стоимости |
| [День 6](day-06-first-agent/README.ru.md) | Первый агент | `BublikAgent`, тонкий CLI и постоянная SQLite-память |
| [День 7](day-07-context-persistence/README.ru.md) | Сохранение контекста | Независимые диалоги с восстановлением после перезапуска |
| [День 8](day-08-token-usage/README.ru.md) | Работа с токенами | Локальная оценка, фактический usage и стоимость запросов |
| [День 9](day-09-context-compression/README.ru.md) | Сжатие контекста | Persistent summary и последние сообщения без изменений |
| [День 10](day-10-context-strategies/README.ru.md) | Стратегии контекста | Sliding Window, Sticky Facts и Branching |
| [День 11](day-11-memory-layers/README.ru.md) | Модель памяти | Short-term, working и long-term memory |
| [День 12](day-12-personalization/README.ru.md) | Персонализация | Профили со стилем, форматом и ограничениями в каждом запросе |
| [День 13](day-13-task-state-machine/README.ru.md) | Task State Machine | Сохраняемые этап, текущий шаг, ожидаемое действие, пауза и продолжение |
| [День 14](day-14-invariants/README.ru.md) | Инварианты и ограничения состояния | Отдельная policy, семантические preflight/postflight-проверки и объяснимые отказы |
| [День 15](day-15-controlled-transitions/README.ru.md) | Контролируемые переходы состояний | Guard-aware переходы, явное утверждение плана, lifecycle-проверка и безопасные pause/resume |
| [День 16](day-16-mcp-connection/README.ru.md) | Подключение MCP | Локальный MCP-сервер, stdio-соединение, инициализация и получение списка инструментов |
| [День 17](day-17-first-mcp-tool/README.ru.md) | Первый MCP-инструмент | Инструмент вокруг GitHub REST API, вызов агентом и использование полученного результата |
| [День 18](day-18-scheduled-mcp/README.ru.md) | Планировщик и фоновые задачи | MCP-расписание, worker, SQLite и агрегированная сводка |

## Эволюция архитектуры

```text
простой API-вызов
    ↓
управляемый prompt и параметры модели
    ↓
BublikAgent + тонкий CLI
    ↓
SQLite + независимые диалоги
    ↓
измерение и сжатие контекста
    ↓
стратегии контекста
    ↓
явные слои памяти + state machine
    ↓
персонализация каждого запроса
    ↓
формальное состояние задачи + pause/resume
    ↓
invariant policy + semantic guard
    ↓
guard-aware lifecycle + явное утверждение плана
    ↓
MCP-соединение + обнаружение инструментов
    ↓
GitHub REST API + первый MCP-инструмент + tool-calling цикл агента
```

День 16 проверяет жизненный цикл MCP-протокола изолированно. День 17 развивает эту основу: отдельный `BublikMcpAgent` обнаруживает зарегистрированный GitHub-инструмент, позволяет модели запросить его, выполняет MCP-вызов и возвращает результат модели для финального ответа.

## Технологии

- Python 3.13;
- [Groq API](https://console.groq.com/);
- GPT-OSS 20B и 120B;
- Qwen 3.6 27B;
- SQLite;
- `groq`;
- `python-dotenv`;
- `tiktoken` с кодировкой `o200k_harmony`;
- Python MCP SDK;
- GitHub REST API;
- `httpx`;
- стандартный `unittest`.

## Структура репозитория

```text
ai-advent-llm-api/
├── day-01-first-api-request/
├── day-02-response-control/
├── day-03-reasoning-methods/
├── day-04-temperature/
├── day-05-model-versions/
├── day-06-first-agent/
├── day-07-context-persistence/
├── day-08-token-usage/
├── day-09-context-compression/
├── day-10-context-strategies/
├── day-11-memory-layers/
├── day-12-personalization/
├── day-13-task-state-machine/
├── day-14-invariants/
├── day-15-controlled-transitions/
├── day-16-mcp-connection/
├── day-17-first-mcp-tool/
├── day-18-scheduled-mcp/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── README.ru.md
```

Каждая директория является самостоятельным примером и содержит собственную документацию на английском и русском языках.

## Подготовка проекта

### 1. Клонирование

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
```

### 2. Виртуальное окружение

```bash
python3 -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows:

```text
.venv\Scripts\activate
```

### 3. Зависимости

```bash
python3 -m pip install -r requirements.txt
```

Для Дней 16 и 17 используются изолированные MCP-зависимости:

```bash
python3 -m pip install -r day-16-mcp-connection/requirements.txt
python3 -m pip install -r day-17-first-mcp-tool/requirements.txt
python3 -m pip install -r day-18-scheduled-mcp/requirements.txt
```

### 4. API-ключ

Создайте `.env` в корне проекта на основе `.env.example`:

```env
GROQ_API_KEY=your_api_key_here
```

Получить ключ можно в [Groq Console](https://console.groq.com/keys). `.env` исключён из Git — не публикуйте ключ в репозитории, логах или скриншотах.

Для примера Дня 16 и детерминированной демонстрации Дня 17 ключ Groq не нужен. `main.py` Дня 17 использует Groq для настоящего выбора инструмента моделью. `GITHUB_TOKEN` необязателен для публичных репозиториев и нужен только для увеличения лимита GitHub API.

## Запуск заданий

Все команды выполняются из корня репозитория.

| День | Основной запуск | Эксперимент / проверка |
|---|---|---|
| 1 | `python3 day-01-first-api-request/main.py` | — |
| 2 | `python3 day-02-response-control/main.py` | — |
| 3 | `python3 day-03-reasoning-methods/main.py` | — |
| 4 | `python3 day-04-temperature/main.py` | — |
| 5 | `python3 day-05-model-versions/main.py` | — |
| 6 | `python3 day-06-first-agent/main.py` | — |
| 7 | `python3 day-07-context-persistence/main.py` | — |
| 8 | `python3 day-08-token-usage/main.py` | `python3 day-08-token-usage/experiment.py` |
| 9 | `python3 day-09-context-compression/main.py` | `python3 day-09-context-compression/experiment.py` |
| 10 | `python3 day-10-context-strategies/main.py` | `python3 day-10-context-strategies/experiment.py` |
| 11 | `python3 day-11-memory-layers/main.py` | `python3 day-11-memory-layers/experiment.py` |
| 12 | `python3 day-12-personalization/main.py` | `python3 day-12-personalization/experiment.py` |
| 13 | `python3 day-13-task-state-machine/main.py` | `python3 day-13-task-state-machine/experiment.py` |
| 14 | `python3 day-14-invariants/main.py` | `python3 day-14-invariants/experiment.py` |
| 15 | `python3 day-15-controlled-transitions/main.py` | `python3 day-15-controlled-transitions/experiment.py` |
| 16 | `python3 day-16-mcp-connection/client.py` | `python3 day-16-mcp-connection/test_mcp_connection.py` |
| 17 | `python3 day-17-first-mcp-tool/main.py` | `python3 day-17-first-mcp-tool/demo.py` / `python3 day-17-first-mcp-tool/test_day17.py` |
| 18 | `python3 day-18-scheduled-mcp/main.py` + `python3 day-18-scheduled-mcp/worker.py` | `python3 day-18-scheduled-mcp/test_day18.py` |

Интерактивные приложения поддерживают `выход` или `/exit`. Точный список команд указан в README соответствующего дня.

## Локальные тесты

Тесты не обращаются к Groq API и не расходуют токены.

```bash
python3 -m unittest discover -s day-10-context-strategies -p "test_*.py" -v
python3 -m unittest discover -s day-11-memory-layers -p "test_*.py" -v
python3 -m unittest discover -s day-12-personalization -p "test_*.py" -v
python3 -m unittest discover -s day-13-task-state-machine -p "test_*.py" -v
python3 -m unittest discover -s day-14-invariants -p "test_*.py" -v
python3 -m unittest discover -s day-15-controlled-transitions -p "test_*.py" -v
python3 day-16-mcp-connection/test_mcp_connection.py
python3 day-17-first-mcp-tool/test_day17.py
python3 day-18-scheduled-mcp/test_day18.py
```

Дни 10–15 проверяют архитектуру агента, память, профили, state machine, invariants и контролируемый lifecycle. В Дне 16 отдельный smoke-тест проверяет инициализацию MCP-сессии и обнаружение инструментов. В Дне 17 проверяются преобразование ответа GitHub, сгенерированная схема входных параметров MCP, запрос инструмента агентом, сам MCP-вызов и использование результата в финальном ответе без расходования токенов Groq и лимита GitHub API.

## Возможности актуального агента

К Дню 15 Бублик умеет работать с независимыми диалогами, явными слоями памяти, персонализацией, формальным состоянием задачи, invariants, semantic guards и контролируемыми переходами задачи.

День 16 намеренно оставляет MCP отдельно от Бублика. Новый эксперимент подтверждает, что MCP-клиент может:

- запустить локальный MCP-сервер через `stdio`;
- установить `ClientSession`;
- выполнить `session.initialize()`;
- запросить инструменты через `session.list_tools()`;
- получить и вывести доступные инструменты сервера.

В День 17 добавляется недостающий цикл выполнения. Отдельный `BublikMcpAgent`:

- преобразует описания и входные схемы MCP-инструментов в tools модели;
- получает сформированный моделью запрос `get_github_repo(owner, repo)`;
- выполняет его через `ClientSession.call_tool()`;
- добавляет полученные данные как сообщение `tool`;
- запрашивает у модели финальный ответ, основанный на результате GitHub.

## Персонализация Дня 12

Профиль пользователя содержит:

```text
name + role
language
detail_level
style
response_format
constraints
```

Перед каждым запросом `MemoryPromptBuilder` формирует контекст в фиксированном порядке:

```text
assistant identity + invariants
user profile
profile-scoped long-term memory
dialogue-scoped working memory
last 6 completed short-term messages
current user request
```

## Task State Machine Дня 13

Task context формально содержит этап, текущий шаг, вычисляемое ожидаемое действие и флаг паузы. SQLite восстанавливает исходные поля после перезапуска, а недопустимые переходы и любой прогресс во время паузы блокируются кодом.

## Инварианты и ограничения состояния Дня 14

В День 14 добавлена отдельная версионируемая invariant policy. Локальные и семантические preflight/postflight-проверки не позволяют запросам и сгенерированным ответам нарушать формализованные ограничения архитектуры, стека, бизнес-правил и безопасности.

## Контролируемые переходы состояний Дня 15

В День 15 жизненный цикл задачи становится явным контрактом. План нужно явно утвердить перед execution, validation требует завершённых execution-шагов, а `done` — успешной проверки. Pause/resume сохраняет точное положение задачи.

## Подключение MCP Дня 16

В День 16 появляется **Model Context Protocol (MCP)** в виде минимального локального примера.

`server.py` предоставляет два инструмента:

- `ping` — возвращает сообщение;
- `add` — складывает два целых числа.

`client.py` запускает сервер через транспорт `stdio` и устанавливает MCP-сессию:

```text
MCP client
    ↓
stdio transport
    ↓
локальный MCP server
    ↓
initialize()
    ↓
list_tools()
    ↓
ping + add
```

Клиент выполняет MCP initialization handshake через `session.initialize()`, а затем запрашивает возможности сервера через `session.list_tools()`. Каждый полученный инструмент выводится в консоль.

Запуск:

```bash
python3 -m pip install -r day-16-mcp-connection/requirements.txt
python3 day-16-mcp-connection/client.py
```

Проверка:

```bash
python3 day-16-mcp-connection/test_mcp_connection.py
```

Smoke-тест проверяет оба требования задания: MCP-соединение успешно инициализируется, а полученный список инструментов содержит ожидаемые `ping` и `add`.

Для этого локального эксперимента не нужны VPS, запрос к Groq, API-ключ или внешний MCP-сервис.

## Первый MCP-инструмент Дня 17

В День 17 проект переходит от обнаружения инструментов к их выполнению. `server.py` регистрирует типизированный инструмент `get_github_repo(owner, repo)` через `@mcp.tool()`. Аннотации и docstring становятся описанием и входной JSON Schema MCP-инструмента.

Полный путь выполнения:

```text
запрос пользователя
    ↓
BublikMcpAgent + tools модели
    ↓
get_github_repo(owner, repo)
    ↓
MCP-вызов через stdio
    ↓
GitHub REST API
    ↓
результат инструмента возвращается модели
    ↓
финальный ответ на основе полученных данных
```

Инструмент возвращает нормализованные данные репозитория: название, владельца, описание, stars, forks, количество открытых issues, основную ветку и URL.

Установка и проверка:

```bash
python3 -m pip install -r day-17-first-mcp-tool/requirements.txt
python3 day-17-first-mcp-tool/test_day17.py
```

Детерминированная end-to-end демонстрация без Groq API key:

```bash
python3 day-17-first-mcp-tool/demo.py
```

Интерактивный запуск с настоящим выбором инструмента моделью Groq:

```bash
python3 day-17-first-mcp-tool/main.py
```

MCP-сервер и клиент остаются локальными и взаимодействуют через `stdio`; за пределы процесса уходит только запрос к GitHub REST API. VPS, открытый порт, домен, Nginx и SSL-сертификат не требуются.

## Ограничения экспериментов

- Скорость, TPM/TPD и доступность моделей зависят от текущего тарифа Groq.
- Ответы могут отличаться между запусками даже при одинаковых параметрах.
- Локальная оценка токенов может незначительно отличаться от фактического usage API.
- Семантическая классификация invariants зависит от guard-модели и работает в fail-closed режиме, если результат невозможно проверить.
- День 16 проверяет только локальное MCP-соединение и обнаружение инструментов; День 17 добавляет выполнение инструмента через отдельный агентский цикл.
- Для живой демонстрации Дня 17 нужен интернет. Неавторизованные запросы ограничены публичными лимитами GitHub API; `GITHUB_TOKEN` необязателен.

## Цель проекта

Репозиторий показывает не набор изолированных API-примеров, а последовательную эволюцию LLM-приложения. Каждый новый механизм можно запустить, измерить, сравнить с предыдущим подходом и проверить отдельно.

## Полезные ссылки

- [Groq Console](https://console.groq.com/)
- [Groq Documentation](https://console.groq.com/docs)
- [GPT-OSS Documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [tiktoken](https://github.com/openai/tiktoken)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## День 18 — Планировщик и фоновые задачи

День 18 добавляет сохранённое расписание GitHub-наблюдений и отдельный worker. Инструмент MCP возвращает изменения по сохранённым снимкам; описание запуска на VPS находится в [инструкции Дня 18](day-18-scheduled-mcp/README.ru.md).
