[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до агента с состоянием

Практический проект по работе с LLM API. Каждый день добавляет один новый механизм: управление ответом, сравнение моделей, постоянную историю, подсчёт токенов, сжатие и стратегии контекста, явные слои памяти, персонализацию, формальное состояние задачи, неизменяемые инварианты, контролируемый жизненный цикл и подключение MCP.

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
```

День 16 намеренно реализован как отдельный MCP-эксперимент. MCP пока не интегрируется в `BublikAgent`: сначала проверяется базовый жизненный цикл протокола.

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

Для Дня 16 используется отдельная MCP-зависимость:

```bash
python3 -m pip install -r day-16-mcp-connection/requirements.txt
```

### 4. API-ключ

Создайте `.env` в корне проекта на основе `.env.example`:

```env
GROQ_API_KEY=your_api_key_here
```

Получить ключ можно в [Groq Console](https://console.groq.com/keys). `.env` исключён из Git — не публикуйте ключ в репозитории, логах или скриншотах.

Для локального MCP-примера Дня 16 ключ Groq не нужен.

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
```

Дни 10–15 проверяют архитектуру агента, память, профили, state machine, invariants и контролируемый lifecycle. В Дне 16 отдельный smoke-тест проверяет инициализацию MCP-сессии и наличие ожидаемых инструментов.

## Возможности актуального агента

К Дню 15 Бублик умеет работать с независимыми диалогами, явными слоями памяти, персонализацией, формальным состоянием задачи, invariants, semantic guards и контролируемыми переходами задачи.

День 16 намеренно оставляет MCP отдельно от Бублика. Новый эксперимент подтверждает, что MCP-клиент может:

- запустить локальный MCP-сервер через `stdio`;
- установить `ClientSession`;
- выполнить `session.initialize()`;
- запросить инструменты через `session.list_tools()`;
- получить и вывести доступные инструменты сервера.

Такое разделение сохраняет фокус задания на MCP-соединении до появления вызова инструментов или интеграции с агентом.

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

## Ограничения экспериментов

- Скорость, TPM/TPD и доступность моделей зависят от текущего тарифа Groq.
- Ответы могут отличаться между запусками даже при одинаковых параметрах.
- Локальная оценка токенов может незначительно отличаться от фактического usage API.
- Семантическая классификация invariants зависит от guard-модели и работает в fail-closed режиме, если результат невозможно проверить.
- День 16 проверяет только локальное MCP-соединение и обнаружение инструментов; выполнение MCP tools и интеграция в `BublikAgent` не входят в текущее задание.

## Цель проекта

Репозиторий показывает не набор изолированных API-примеров, а последовательную эволюцию LLM-приложения. Каждый новый механизм можно запустить, измерить, сравнить с предыдущим подходом и проверить отдельно.

## Полезные ссылки

- [Groq Console](https://console.groq.com/)
- [Groq Documentation](https://console.groq.com/docs)
- [GPT-OSS Documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [tiktoken](https://github.com/openai/tiktoken)
- [Model Context Protocol](https://modelcontextprotocol.io/)
