[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до персонализированного агента

Практический проект по работе с LLM API. Каждый день добавляет один новый механизм: управление ответом, сравнение моделей, постоянную историю, подсчёт токенов, сжатие и стратегии контекста, явные слои памяти и персонализацию.

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
```

В последних заданиях основной поток выглядит так:

```text
CLI
  → BublikAgent
    → профиль пользователя
    → long-term memory
    → working memory
    → recent short-term messages
    → Groq API
    → проверка ответа
    → SQLite
```

## Технологии

- Python 3.13;
- [Groq API](https://console.groq.com/);
- GPT-OSS 20B и 120B;
- Qwen 3.6 27B;
- SQLite;
- `groq`;
- `python-dotenv`;
- `tiktoken` с кодировкой `o200k_harmony`;
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

### 4. API-ключ

Создайте `.env` в корне проекта на основе `.env.example`:

```env
GROQ_API_KEY=your_api_key_here
```

Получить ключ можно в [Groq Console](https://console.groq.com/keys). `.env` исключён из Git — не публикуйте ключ в репозитории, логах или скриншотах.

## Запуск заданий

Все команды выполняются из корня репозитория.

| День | Основной запуск | Эксперимент |
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

Интерактивные приложения поддерживают `выход` или `/exit`. Точный список команд указан в README соответствующего дня.

## Локальные тесты

Тесты не обращаются к Groq API и не расходуют токены.

```bash
python3 -m unittest discover -s day-10-context-strategies -p "test_*.py" -v
python3 -m unittest discover -s day-11-memory-layers -p "test_*.py" -v
python3 -m unittest discover -s day-12-personalization -p "test_*.py" -v
```

Они проверяют:

- размер Sliding Window, обновление facts и изоляцию веток;
- разделение short-term, working и long-term memory;
- допустимые переходы state machine;
- формирование полного prompt;
- подключение профиля к каждому запросу;
- различия между профилями;
- восстановление профиля и изоляцию пользовательской long-term memory.

## Возможности актуального агента

В Дне 12 Бублик умеет:

- работать с несколькими независимыми диалогами;
- восстанавливать историю после перезапуска;
- хранить последние сообщения отдельно от состояния задачи;
- явно сохранять решения и знания;
- контролировать задачу через `planning → execution → validation → done`;
- применять язык, детализацию, стиль, формат и ограничения пользователя;
- изолировать долговременную память разных профилей;
- показывать точный контекст до отправки в модель;
- отклонять ответы, нарушающие формализованные invariants.

Основные команды:

| Команда | Назначение |
|---|---|
| `/dialogs` | Переключить или создать диалог |
| `/history` | Показать полную завершённую историю |
| `/context` | Показать prompt, который получит модель |
| `/memory short\|working\|long` | Показать выбранный слой памяти |
| `/remember working KEY VALUE` | Сохранить данные текущей задачи |
| `/remember long decision\|knowledge KEY VALUE` | Сохранить решение или знание |
| `/task ...` | Управлять состоянием текущей задачи |
| `/profile` | Показать активный профиль |
| `/profile PROFILE_ID` | Сменить профиль пустого диалога |
| `/exit` | Завершить программу |

Значения с пробелами нужно заключать в кавычки.

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
dialog-scoped working memory
last 6 completed short-term messages
current user request
```

В репозитории есть два контрастных профиля: краткий `cheburator` и подробный научный `scientist`. `experiment.py` задаёт им одинаковый вопрос с одинаковой working memory, чтобы различия ответа зависели именно от персонализации.

## Ограничения экспериментов

- Скорость, TPM/TPD и доступность моделей зависят от текущего тарифа Groq.
- Ответы могут отличаться между запусками даже при одинаковых параметрах.
- Локальная оценка токенов может незначительно отличаться от фактического usage API.
- Summary и Sticky Facts зависят от качества модели и могут потерять важную деталь.
- Автоматические тесты проверяют архитектуру и состав prompt, а качество реального ответа оценивается в экспериментах.

## Цель проекта

Репозиторий показывает не набор изолированных API-примеров, а последовательную эволюцию LLM-приложения. Каждый новый механизм можно запустить, измерить, сравнить с предыдущим подходом и проверить отдельно.

## Полезные ссылки

- [Groq Console](https://console.groq.com/)
- [Groq Documentation](https://console.groq.com/docs)
- [GPT-OSS Documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [tiktoken](https://github.com/openai/tiktoken)
