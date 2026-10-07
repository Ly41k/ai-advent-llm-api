[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до MCP, подтверждённого RAG и локальных приложений

Практический проект на Python, который начинается с прямых запросов к LLM API и постепенно приходит к агентам, сохраняемому состоянию, MCP-инструментам, индексации документов, RAG, подтверждённым цитатам постоянному RAG-чату с памятью задачи и локальному приложению проверки Kotlin перед коммитом.

**Чебуратор** — капитан исследовательского корабля, **Бублик** — помощник, который развивается по ходу курса. **Ревик**, добавленный на Дне 27, — отдельный локальный помощник проверки Kotlin-кода.

Сейчас репозиторий содержит **дни 1–28**. Каждая папка `day-XX-...` — самостоятельный учебный этап с английской и русской документацией. Поздние этапы переиспользуют нужные компоненты предыдущих дней, но не объединяют автоматически все исторические версии агента в одно приложение.

## Путь проекта

| День | Тема | Что добавлено |
|---|---|---|
| [01](day-01-first-api-request/README.ru.md) | Первый запрос | Интерактивный Groq-чат с историей сеанса |
| [02](day-02-response-control/README.ru.md) | Управление ответом | Структура, длина и явные правила ответа |
| [03](day-03-reasoning-methods/README.ru.md) | Способы рассуждения | Сравнение четырёх подходов к одной задаче |
| [04](day-04-temperature/README.ru.md) | Температура | Точность, креативность и вариативность |
| [05](day-05-model-versions/README.ru.md) | Сравнение моделей | Качество, задержка, токены и оценка стоимости |
| [06](day-06-first-agent/README.ru.md) | Первый агент | `BublikAgent`, CLI и SQLite-память |
| [07](day-07-context-persistence/README.ru.md) | Сохранение контекста | Независимые диалоги после перезапуска |
| [08](day-08-token-usage/README.ru.md) | Токены | Оценка и фактический расход |
| [09](day-09-context-compression/README.ru.md) | Сжатие контекста | Сохранённая сводка + последние полные сообщения |
| [10](day-10-context-strategies/README.ru.md) | Стратегии контекста | Sliding Window, Sticky Facts и Branching |
| [11](day-11-memory-layers/README.ru.md) | Модель памяти | Краткосрочная, рабочая и долговременная память |
| [12](day-12-personalization/README.ru.md) | Персонализация | Профили пользователей и раздельный контекст |
| [13](day-13-task-state-machine/README.ru.md) | Состояние задачи | Этап, прогресс, ожидаемое действие и пауза |
| [14](day-14-invariants/README.ru.md) | Инварианты | Версионируемая политика и semantic pre/post checks |
| [15](day-15-controlled-transitions/README.ru.md) | Контролируемые переходы | Утверждение плана, guards, validation и resume |
| [16](day-16-mcp-connection/README.ru.md) | Подключение MCP | Локальный stdio-сервер/клиент и discovery |
| [17](day-17-first-mcp-tool/README.ru.md) | Первый MCP-инструмент | GitHub tool в модельном tool-calling loop |
| [18](day-18-scheduled-mcp/README.ru.md) | Фоновые задачи | SQLite-расписание, отдельный worker, snapshots |
| [19](day-19-mcp-composition/README.ru.md) | Композиция инструментов | Получить → обработать → сохранить |
| [20](day-20-mcp-orchestration/README.ru.md) | Оркестрация MCP | Пять вызовов на трёх MCP-серверах |
| [21](day-21-document-indexing/README.ru.md) | Индексация документов | Общий SQLite-индекс, два chunking-подхода, embeddings |
| [22](day-22-first-rag/README.ru.md) | Первый RAG | NO RAG vs RAG, context, provenance, evaluation |
| [23](day-23-reranking-filtering/README.ru.md) | Фильтрация и query rewrite | Candidate/final top-K, cosine threshold, rewrite, calibration |
| [24](day-24-citations-grounding/README.ru.md) | Цитаты и grounding | Дословные источники, app-owned citations, coverage validation |
| [25](day-25-rag-chat/README.ru.md) | Постоянный RAG-чат | SQLite-сессии, task memory, свежий retrieval и long-dialogue evaluation |
| [26](day-26-local-llm/README.ru.md) | Запуск локальной LLM | Три запроса через Ollama, сравнение с Groq, проверка JSON и локальной загрузки |
| [27](day-27-local-llm-integration/README.ru.md) | Интеграция локальной LLM — Ревик | Проверка staged Kotlin, Detekt gate, локальные объяснения, ссылки и стили комментариев |
| [28](day-28-local-rag/README.ru.md) | Локальная LLM + RAG | Индекс Недели 6, локальные embedding/search/generation, сравнение с облаком и повторные прогоны |

## Как развивается архитектура

- **Дни 1–5:** промпты, параметры моделей, способы рассуждения, токены, задержка и стоимость.
- **Дни 6–10:** логика агента отделяется от CLI, диалоги сохраняются в SQLite, появляется управление размером контекста.
- **Дни 11–15:** слои памяти, профили, автомат состояний задачи, инварианты и контролируемые переходы.
- **Дни 16–20:** появляется MCP — от локального stdio handshake до GitHub-инструмента, фоновых задач, composition и orchestration нескольких серверов.
- **День 21:** создаётся переиспользуемая локальная база знаний на `bge-m3` + SQLite с fixed/structural chunking.
- **День 22:** retrieval соединяется с генерацией; один вопрос сравнивается без RAG и с RAG.
- **День 23:** добавляются query rewrite, фильтрация кандидатов, калибруемый cosine threshold и четыре режима retrieval.
- **День 24:** ответы становятся evidence-bound: приложение публикует точные фрагменты источников и отдельно проверяет полноту.
- **День 25:** grounded RAG превращается в постоянный локальный чат. История и память задачи переживают перезапуск, каждый обычный вопрос делает новый поиск, а длинные диалоги проверяются через checkpoint/resume и per-turn provenance.
- **День 26:** отдельный модуль проверяет запуск скачанной модели Ollama и выполняет три запроса разной сложности. Те же входы можно отправить в Groq; приложение проверяет ответы и сохраняет JSON/Markdown-отчёты.
- **День 27:** локальная LLM интегрируется в Ревика — CLI для рабочего Kotlin/KMP-проекта. Detekt проверяет staged-код по настройкам проекта, Qwen объясняет нарушения, а pre-commit hook разрешает или блокирует коммит. Добавлены отчёты со ссылками, два языка и три стиля комментариев.
- **День 28:** индекс Недели 6 используется для локального RAG. Local/cloud получают одинаковый контекст; повторные прогоны фиксируют проверки цитат/качества, скорость и стабильность. Живые метрики требуют запуска Ollama.

MCP-серверы дней 16–20 общаются с локальными клиентами через **stdio**. Дни 17–20 могут получать живые данные через публичный GitHub REST API. Для постоянного выполнения расписания непрерывный процесс требуется только worker Дня 18.

Дни 21–25 и День 28 используют общий индекс Дня 21. В Дне 25 предыдущие ответы ассистента и сохранённая task memory помогают понять намерение, но **не считаются доказательством фактов репозитория**: каждый текущий ответ подтверждается новым retrieval.

## Требования

- Целевая версия — Python **3.13**.
- Groq key нужен только тем этапам, которые явно вызывают Groq.
- Интернет требуется для Groq и живых GitHub API-вызовов.
- Retrieval/RAG-этапы и Дни 26–28 используют локальный **Ollama**.
- Дню 27 также нужны Git, совместимый JDK и Detekt CLI; дополнительных pip-зависимостей у его Python-модуля нет. Документированный hook-флоу рассчитан на macOS/Linux.
- `GITHUB_TOKEN` необязателен для публичных GitHub-репозиториев, но помогает с rate limits.

### Локальные модели

| Этапы | Embeddings | Generation |
|---|---|---|
| 21–22 | `bge-m3` | `llama3.2` в базовом документированном флоу |
| 23 | `bge-m3` | `llama3.2` по умолчанию; `qwen2.5:7b` в зафиксированных экспериментах |
| 24–25 | `bge-m3` | `qwen2.5:14b` в текущем grounded/live профиле |
| 26 | Не требуются | `qwen2.5:7b` по умолчанию; `qwen2.5:14b` в проверенном запуске |
| 27 | Не требуются | `qwen2.5:14b` по умолчанию; настраиваемая скачанная локальная модель |
| 28 | `bge-m3` | `qwen2.5:14b` по умолчанию; опциональное сравнение с Groq |

Загружайте только те модели, которые нужны конкретному этапу.

## Установка

Из корня репозитория:

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

На Windows:

```text
.venv\Scripts\activate
```

У MCP-этапов есть собственные зависимости. Например:

```bash
python -m pip install -r day-20-mcp-orchestration/requirements.txt
```

Для локального RAG:

```bash
ollama pull bge-m3
ollama pull llama3.2
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b
```

Все answer-модели одновременно не обязательны: эти команды покрывают документированные профили до Дня 28.

Если приложение Ollama уже обслуживает локальный API, отдельный `ollama serve` не требуется.

Для программ с Groq скопируйте `.env.example` в `.env`, укажите `GROQ_API_KEY` и не коммитьте секреты.

## Запуск этапов

У дней 1–15 есть собственный `main.py`. Например:

```bash
python day-01-first-api-request/main.py
python day-15-controlled-transitions/main.py
```

Поздние этапы используют отдельные точки входа:

| День | Команда из корня | Результат |
|---|---|---|
| 16 | `python day-16-mcp-connection/client.py` | Discovery локальных `ping` и `add` |
| 17 | `python day-17-first-mcp-tool/demo.py` | Детерминированная демонстрация GitHub tool |
| 17 | `python day-17-first-mcp-tool/main.py` | Интерактивный model-driven MCP |
| 18 | `python day-18-scheduled-mcp/worker.py` + `python day-18-scheduled-mcp/main.py` | Scheduler/worker и агент |
| 19 | `python day-19-mcp-composition/main.py Ly41k ai-advent-llm-api` | Три MCP-вызова и Markdown-отчёт |
| 20 | `python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline` | Пять вызовов на трёх серверах |
| 21 | `python day-21-document-indexing/main.py build` | Построить локальные индексы |
| 21 | `python day-21-document-indexing/main.py verify` | Проверить revision и fingerprint корпуса |
| 22 | `python day-22-first-rag/main.py evaluate` | Проверить первый RAG-флоу |
| 23 | `python day-23-reranking-filtering/main.py questions` | Показать calibration/evaluation questions |
| 24 | `python day-24-citations-grounding/main.py evaluate --output day-24-citations-grounding/reports/check/evaluate.json` | Grounded answers с точными цитатами |
| 25 | `python day-25-rag-chat/main.py chat` | Постоянный локальный RAG-чат |
| 25 | `python day-25-rag-chat/main.py evaluate --process-per-turn --output day-25-rag-chat/reports/check/live.json` | Долгий live-тест с checkpoint/resume |
| 26 | `python day-26-local-llm/main.py demo --local-model qwen2.5:14b` | Три реальных локальных запроса |
| 26 | `python day-26-local-llm/main.py compare --local-model qwen2.5:14b` | Те же запросы локально и в Groq |
| 27 | `python day-27-local-llm-integration/live_demo.py --detekt-bin /absolute/path/to/detekt` | Два реальных коммита во временном репозитории и ответы локальной LLM |
| 28 | `python day-28-local-rag/main.py evaluate --repeats 3` | Отчёты качества, скорости и стабильности локального RAG |

## Общий индекс Дня 21

Дни 21–25 и День 28 используют:

```text
day-21-document-indexing/knowledge.db
```

Правило корпуса остаётся намеренно ограниченным:

- корневые `README.md` и `README.ru.md`;
- README этапов 1–20;
- Python-файлы дней 16–20, кроме тестов.

README дней 21–28 автоматически в индекс не добавляются. Дни 26–27 не используют этот индекс.

Индекс хранит revision репозитория/корпуса. Новый commit или изменение **корневых README** может сделать существующий индекс stale. После обновления root README перед strict verify или живым запуском Days 24–25/28 выполните:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

## День 24 — grounded answers

День 24 публикует точные фрагменты источников вместо свободно синтезированного фактического ответа. Приложение управляет identity цитат и проверяет source/section/chunk metadata и coverage.

Текущий grounded-профиль:

```text
fixed
candidate K = 20
final K = 5
raw cosine >= 0.50
heuristic rewrite
bge-m3
qwen2.5:14b
strict coverage
```

Запуск:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-24-citations-grounding/main.py evaluate \
  --output day-24-citations-grounding/reports/check/evaluate.json
```

Semantic validators остаются модельными компонентами: точная цитата и положительный verdict не заменяют ручную проверку источника.

## День 25 — постоянный RAG-чат с памятью задачи

День 25 переиспользует extractive/grounded протокол Дня 24 и добавляет:

- изолированные SQLite-сессии в `day-25-rag-chat/chats.db`;
- полную сохранённую историю + ограниченный recent context для модели;
- task memory: цель, ограничения, уточнения, термины;
- новый retrieval на каждый обычный вопрос;
- строгий контракт источников/цитат;
- безопасное восстановление прерванных ходов;
- compare-and-set защиту обновлений памяти;
- атомарную запись JSON report/export;
- ownership live-turn через POSIX advisory locks;
- checkpoint/resume длинной evaluation;
- реальные embedding/search traces с request/session/turn identity.

Быстрый запуск:

```bash
python day-25-rag-chat/test_day25.py -v
python day-25-rag-chat/main.py offline-demo
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-25-rag-chat/main.py chat
```

Финальная проверка v24, сохранённая в репозитории:

- **181 тест Дня 25 — PASS**;
- **169 regression-тестов Days 21–24 — PASS**;
- финальный live 12+12: **24/24 ответов прошли ручное ревью**;
- **47 точных цитат**;
- **48 embedding + 48 search вызовов**;
- **24 отдельных процесса/request ID**;
- два дополнительных negative-control завершились ожидаемым `unknown`.

Подробнее: [README Дня 25](day-25-rag-chat/README.ru.md), [аудит v24](day-25-rag-chat/AUDIT_V24.ru.md), [финальная приёмка](day-25-rag-chat/ACCEPTANCE_V24.ru.md).

## День 26 — локальная LLM и сравнение с облачной

Самостоятельный модуль `day-26-local-llm/` обращается к скачанной модели через Ollama HTTP API. Для задания достаточно локального режима; Groq добавлен для сравнения с облачной LLM.

Три примера: короткий ответ `2 + 2`, JSON по результату Python-калькулятора и извлечение пяти полей с точной цитатой из фрагмента README Дня 18. Калькулятор вызывается приложением заранее; модель оформляет его результат. Здесь нет модельного выбора инструмента, MCP-вызовов или RAG-поиска.

Для уже установленной Qwen 14B:

```bash
python day-26-local-llm/test_day26.py -v
python day-26-local-llm/main.py doctor --local-model qwen2.5:14b
python day-26-local-llm/main.py demo --local-model qwen2.5:14b \
  --output day-26-local-llm/reports/check/local.json
ollama ps

# Нужен GROQ_API_KEY; отправляет три дополнительных запроса в Groq.
python day-26-local-llm/main.py compare --local-model qwen2.5:14b \
  --output day-26-local-llm/reports/check/compare.json
```

В предоставленном автором отчёте `compare-v1.3.json` от 2026-10-06: Python 3.13.3, Ollama 0.34.4, `qwen2.5:14b` Q4_K_M и Groq `openai/gpt-oss-20b`. Локально **3/3** и в облаке **3/3** ответов прошли проверки; локальная модель осталась загруженной после генерации. 38 offline-тестов также прошли на Python 3.12.

Это результат трёх примеров с инструментом в среднем запросе, а не гарантия точности любых ответов. Отобранные live-отчёты сохраняйте в `reports/live/`; временные `reports/check/` и `reports/video/` игнорируются Git.

Подробнее: [README Дня 26](day-26-local-llm/README.ru.md).

## День 27 — Ревик, локальный агент проверки Kotlin перед коммитом

Ревик — отдельная Python CLI-утилита для реального KMP-флоу разработки. Он читает staged `.kt`/`.kts`, запускает Detekt с `detekt/detekt.yml`, запрашивает объяснение у скачанной Qwen через Ollama и показывает нарушения со ссылками на файлы и строки. Git hook разрешает или отклоняет коммит через exit code.

Конфигурация и Kotlin-исходники берутся из Git index, включая частично добавленные изменения. Изменение конфигурации/baseline запускает проверку всего staged Kotlin-дерева. Если конфигурации нет или нет выбранных Kotlin-файлов, проверка пропускается. Нарушения и технические ошибки блокируют коммит; LLM не переопределяет Detekt. По умолчанию недоступный/неполный ответ модели тоже блокирует коммит.

Поддерживаются `language=ru|en` и `tone=professional|light_troll|hard_troll`. Облачных API-ключей и fallback нет. JSON/Markdown/HTML-отчёты сохраняются в служебном каталоге Git. Анализ AST выполняется без type resolution, поэтому платформенные Gradle/CI-проверки остаются нужны.

Из корня репозитория курса:

```bash
python -m unittest discover -s day-27-local-llm-integration/tests -v

# Нужны установленный Detekt CLI, Ollama и скачанная qwen2.5:14b.
python day-27-local-llm-integration/live_demo.py \
  --detekt-bin /absolute/path/to/detekt \
  --language ru --tone light_troll \
  --output day-27-local-llm-integration/revik-live.json
```

Demo создаёт временный репозиторий и проверяет отказ плохому коммиту и успешный исправленный коммит. Hook в учебный репозиторий не устанавливается. В [README Дня 27](day-27-local-llm-integration/README.ru.md) есть установка отдельного JAR и инструкция переноса в `tools/revik-agent/` рабочего проекта.

На текущем коде Дня 27 **28 интеграционных тестов проходят**. Модель и Detekt в этих тестах scripted; отдельный smoke check настоящего Detekt 1.23.8 проверяет bad/clean входы demo. Живые объяснения Qwen требуют просмотра. Подробнее: [валидация](day-27-local-llm-integration/VALIDATION.md).

В репозиторий курса добавляются исходники Ревика, примеры и шаблон настроек. В рабочем KMP-проекте каталог агента и `.revik.json` могут оставаться локальными и игнорироваться. Скачанные JAR и временные отчёты не относятся к исходникам задания.

## День 28 — локальная LLM + RAG

[Модуль Day 28](day-28-local-rag/README.ru.md) открывает индекс Day 21 только для чтения, переиспользует фильтрацию Day 23 и HTTP-клиенты Day 26. `ask` и `evaluate` используют скачанные локальные модели без облачного ключа; `compare` добавляет Groq при доступности с одинаковыми prompt/фрагментами для каждой пары. Отчёты сохраняют точные цитаты, эвристические проверки качества, retrieval/generation latency и стабильность повторных ответов.

```bash
python day-28-local-rag/test_day28.py -v
python day-28-local-rag/main.py doctor
python day-28-local-rag/main.py evaluate --repeats 3
python day-28-local-rag/main.py compare --repeats 3
```

Offline-тесты проверяют реализацию. Реальные качество/скорость/стабильность и работу без интернета ещё нужно подтвердить живым прогоном с Ollama и `knowledge.db`; live-бенчмарк Day 28 здесь не заявлен. См. [чек-лист проверки](day-28-local-rag/VALIDATION.ru.md).

## Тесты

Локальные тесты используют fake/scripted HTTP, SQLite, локальные MCP-серверы или fixtures. Они не расходуют Groq-токены, если команда явно не запускает живую модель/API.

```bash
python -m unittest discover -s day-10-context-strategies -p 'test_*.py' -v
python -m unittest discover -s day-11-memory-layers -p 'test_*.py' -v
python -m unittest discover -s day-12-personalization -p 'test_*.py' -v
python -m unittest discover -s day-13-task-state-machine -p 'test_*.py' -v
python -m unittest discover -s day-14-invariants -p 'test_*.py' -v
python -m unittest discover -s day-15-controlled-transitions -p 'test_*.py' -v
python day-16-mcp-connection/test_mcp_connection.py
python day-17-first-mcp-tool/test_day17.py -v
python day-18-scheduled-mcp/test_day18.py -v
python day-19-mcp-composition/test_day19.py -v
python day-20-mcp-orchestration/test_day20.py -v
python day-21-document-indexing/test_day21.py -v
python day-22-first-rag/test_day22.py -v
python day-23-reranking-filtering/test_day23.py -v
python day-24-citations-grounding/test_day24.py -v
python day-25-rag-chat/test_day25.py -v
python day-26-local-llm/test_day26.py -v
python -m unittest discover -s day-27-local-llm-integration/tests -v
```

## Данные и ограничения

- День 27 — локальная pre-commit проверка, которую можно обойти. Она анализирует изменённые файлы целиком без type resolution и не заменяет компиляцию KMP, Android Lint или CI. Стиль комментариев влияет только на объяснения.
- Сгенерированные SQLite-базы, временные отчёты, ответы моделей и доступность провайдеров зависят от окружения.
- Worker Дня 18 пишет результат в stdout или service journal и сам не отправляет сообщение обратно в чат.
- Дни 21–25 — локальные RAG-эксперименты, а не hosted multi-user service.
- День 25 — локальный single-user CLI; он не выполняет произвольный пользовательский код и не вызывает внешние MCP-инструменты из чата.
- Task memory сохраняет буквальное происхождение из пользовательского текста, но это само по себе не гарантирует правильность модельной интерпретации.
- Точные цитаты подтверждают provenance, а не автоматически семантическую полноту. Поэтому live-отчёты сохраняют требование ручного review.
- Названия моделей, лимиты провайдеров и цены могут меняться; для воспроизведения старых этапов проверяйте актуальную документацию.

## Полезные ссылки

- [Groq Console](https://console.groq.com/)
- [Ollama](https://ollama.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Документация GitHub REST API](https://docs.github.com/en/rest)
