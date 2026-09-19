[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до агента с состоянием

Практический проект по работе с LLM API. Каждый день добавляет один новый механизм: управление ответом, сравнение моделей, постоянную историю, подсчёт токенов, сжатие и стратегии контекста, явные слои памяти, персонализацию, формальное состояние задачи и неизменяемые инварианты.

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
```

В последних заданиях основной поток выглядит так:

```text
CLI
  → BublikAgent
    → профиль пользователя
    → long-term memory
    → working memory
    → recent short-term messages
    → локальная preflight-проверка invariants
    → semantic request guard
    → Groq API
    → локальная и семантическая проверка ответа
    → детерминированный отказ или принятый ответ
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
├── day-13-task-state-machine/
├── day-14-invariants/
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
| 13 | `python3 day-13-task-state-machine/main.py` | `python3 day-13-task-state-machine/experiment.py` |
| 14 | `python3 day-14-invariants/main.py` | `python3 day-14-invariants/experiment.py` |

Интерактивные приложения поддерживают `выход` или `/exit`. Точный список команд указан в README соответствующего дня.

## Локальные тесты

Тесты не обращаются к Groq API и не расходуют токены.

```bash
python3 -m unittest discover -s day-10-context-strategies -p "test_*.py" -v
python3 -m unittest discover -s day-11-memory-layers -p "test_*.py" -v
python3 -m unittest discover -s day-12-personalization -p "test_*.py" -v
python3 -m unittest discover -s day-13-task-state-machine -p "test_*.py" -v
python3 -m unittest discover -s day-14-invariants -p "test_*.py" -v
```

Они проверяют:

- размер Sliding Window, обновление facts и изоляцию веток;
- разделение short-term, working и long-term memory;
- допустимые переходы state machine;
- формирование полного prompt;
- подключение профиля к каждому запросу;
- различия между профилями;
- восстановление профиля и изоляцию пользовательской long-term memory.
- pause/resume задачи и точное восстановление после перезапуска.
- категории invariant policy и её отдельное хранение;
- семантические проверки запроса и ответа, объяснимые отказы и исключение небезопасных ответов из истории.

## Возможности актуального агента

В Дне 14 Бублик умеет:

- работать с несколькими независимыми диалогами;
- восстанавливать историю после перезапуска;
- хранить последние сообщения отдельно от состояния задачи;
- явно сохранять решения и знания;
- контролировать задачу через `planning → execution → validation → done`;
- вычислять ожидаемое действие из формального состояния задачи;
- ставить любой незавершённый этап на паузу без потери прогресса;
- применять язык, детализацию, стиль, формат и ограничения пользователя;
- изолировать долговременную память разных профилей;
- показывать точный контекст до отправки в модель;
- отклонять ответы, нарушающие формализованные invariants.
- загружать версионируемую invariant policy вне базы диалога;
- блокировать явные конфликты до генерации локальной проверкой;
- обнаруживать перефразированные конфликты через semantic guard;
- проверять готовый ответ по всем invariants;
- заменять нарушающие ответы детерминированным объяснимым отказом;
- не сохранять небезопасный ответ модели в SQLite.

Основные команды:

| Команда | Назначение |
|---|---|
| `/dialogs` | Переключить или создать диалог |
| `/history` | Показать полную завершённую историю |
| `/context` | Показать prompt, который получит модель |
| `/invariants` | Показать активную policy и причины правил |
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

## Task State Machine Дня 13

Task context теперь формально содержит этап, текущий шаг, вычисляемое ожидаемое действие и флаг паузы. SQLite восстанавливает исходные поля после перезапуска, а prompt указывает модели продолжить с сохранённого места, не требуя повторного описания задачи. Недопустимые переходы и любой прогресс во время паузы блокируются кодом.

## Инварианты и ограничения состояния Дня 14

В День 14 добавлена отдельная версионируемая policy в `day-14-invariants/config/invariants.json`. Она формализует ограничения стека, архитектуры, технических решений, бизнес-правил и безопасности. Сообщения диалога не могут изменить или отменить эту policy.

Проверка выполняется в три слоя:

```text
user request
    ↓
локальная regex preflight-проверка
    ├── явный конфликт → детерминированный отказ
    └── pass → semantic request guard
                   ├── конфликт → детерминированный отказ
                   └── pass → генерация ответа
                                  ↓
                         локальная и semantic postflight-проверка
                                  ├── нарушение → объяснимый отказ
                                  └── pass → SQLite
```

Semantic guard возвращает строгий JSON только с допустимыми ID инвариантов. Поэтому перефразированный конфликт вроде «для новой версии лучше TypeScript» отклоняется даже без совпадения с локальным regex. Если готовый ответ нарушает архитектуру, стек, бизнес-правило или безопасность, он отбрасывается и заменяется объяснимым отказом до сохранения.

Запуск приложения:

```bash
python3 day-14-invariants/main.py
```

Запуск локальных тестов:

```bash
python3 -m unittest discover -s day-14-invariants -p "test_*.py" -v
```

Для совместимого запроса выполняются semantic preflight, генерация ответа и semantic postflight. Явные regex-конфликты блокируются локально без API-вызова.

## Ограничения экспериментов

- Скорость, TPM/TPD и доступность моделей зависят от текущего тарифа Groq.
- Ответы могут отличаться между запусками даже при одинаковых параметрах.
- Локальная оценка токенов может незначительно отличаться от фактического usage API.
- Summary и Sticky Facts зависят от качества модели и могут потерять важную деталь.
- Семантическая классификация invariants зависит от guard-модели; некорректный или неизвестный результат обрабатывается в fail-closed режиме.
- Совместимый запрос Дня 14 может использовать три API-вызова: semantic preflight, генерация ответа и semantic postflight.
- Автоматические тесты проверяют архитектуру и состав prompt, а качество реального ответа оценивается в экспериментах.

## Цель проекта

Репозиторий показывает не набор изолированных API-примеров, а последовательную эволюцию LLM-приложения. Каждый новый механизм можно запустить, измерить, сравнить с предыдущим подходом и проверить отдельно.

## Полезные ссылки

- [Groq Console](https://console.groq.com/)
- [Groq Documentation](https://console.groq.com/docs)
- [GPT-OSS Documentation](https://console.groq.com/docs/model/openai/gpt-oss-20b)
- [tiktoken](https://github.com/openai/tiktoken)
