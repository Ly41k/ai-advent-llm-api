[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до MCP, подтверждённого RAG и локальных приложений

Практический проект на Python, который начинается с прямых запросов к LLM API и постепенно приходит к агентам, сохраняемому состоянию, MCP-инструментам, индексации документов, RAG, подтверждённым цитатам, постоянному RAG-чату с памятью задачи, локальному приложению проверки Kotlin перед коммитом, приватному AI-чату с доступом с компьютера и телефонов, ассистенту разработчика с Project RAG, MCP Git и делегацией задач, а также AI-ревью Pull Request и ассистенту поддержки приватного AI-сервиса.

**Чебуратор** — капитан исследовательского корабля, **Бублик** — помощник, который развивается по ходу курса. **Ревик**, добавленный на Дне 27, — отдельный локальный помощник проверки Kotlin-кода.

Сейчас репозиторий содержит **дни 1–33**. Каждая папка `day-XX-...` — самостоятельный учебный этап с английской и русской документацией. Поздние этапы переиспользуют нужные компоненты предыдущих дней, но не объединяют автоматически все исторические версии агента в одно приложение.

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
| [29](day-29-local-llm-optimization/README.ru.md) | Оптимизация локальной LLM | Prompt и лимиты под задачу, замеры Q4/Q5 и ресурсов, frozen-проверка выбора доказательств V7 |
| [30](day-30-private-ai-service/README.ru.md) | Приватный AI-сервис | FastAPI, локальная Qwen, SQLite-история, Web UI/PWA, LAN/Tailscale HTTPS, очередь и лимиты |
| [31](day-31-developer-assistant/README.ru.md) | Ассистент разработчика | Project RAG, read-only MCP Git, делегация Main/Documentation/Git/Verification, локальная Qwen и публикация после human review; Course Minimum Accepted |
| [32](day-32-pr-review/README.ru.md) | AI-ревью Pull Request | Настоящий GitHub PR diff, FTS5 по доверенным README, Groq и проверенные отчёты; локальная интеграция PASS, качество PARTIAL, Actions live E2E FAIL |
| [33](day-33-support-assistant/README.ru.md) | AI-ассистент поддержки | Синтетическая CRM через настоящий MCP stdio, FAQ/FTS5, Groq, раздельные evidence; Mac 25/25, новый live E2E PASS |

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
- **День 28:** индекс Недели 6 используется для полностью локального RAG. Сохранены исходное парное сравнение с Groq и выборочные исправления local/OpenAI. Живые отчёты фиксируют качество, скорость, точную стабильность и ручную проверку цитат.
- **День 29:** оптимизация параметров и контрактов локальной Qwen, сравнение Q4/Q5 и ресурсов, проверка выбора доказательств V7 на зафиксированных новых RU/EN вопросах о процедуре.
- **День 30:** локальная Qwen становится приватным HTTP-сервисом. История хранится на Mac, чат продолжается на Android/iPhone, мобильный доступ идёт через Tailscale Serve. Cookie/CSRF, owners, idempotency, очередь, persistent quotas и launchd отделены от модели; курс использовал версию без RAG; последующий history RAG отключаемый, cloud fallback нет.
- **День 31:** Project RAG и настоящий MCP Git объединяются с делегацией Main/Documentation/Git/Verification. Один локальный RU-1 / Multi ответ принят через exact claim–anchor bindings и явное human review; расширенный Research Stage 7 остаётся незавершённым.
- **День 32:** появляется AI-ревью Pull Request: реальный diff из GitHub, доверенные README из base через SQLite FTS5, Groq и проверка JSON/строк/evidence. Локальная проверка обнаружила дефект (технически PASS, качество PARTIAL), а GitHub Actions live E2E завершился HTTP 403.
- **День 33:** отдельный ассистент поддержки Bublik Day 30: JSON users/tickets через настоящий MCP, FTS5/BM25 top-3, ограниченный Groq plan и проверенный ответ. Evidence модели и приложения разделены; Mac offline 25/25 и новая curl attempt-03 приняты как PASS.

MCP-серверы дней 16–20 общаются с локальными клиентами через **stdio**. Дни 17–20 могут получать живые данные через публичный GitHub REST API. Для постоянного выполнения расписания непрерывный процесс требуется только worker Дня 18.

Дни 21–25 и 28–29 используют общий индекс Дня 21. В Дне 25 предыдущие ответы ассистента и сохранённая task memory помогают понять намерение, но **не считаются доказательством фактов репозитория**: каждый текущий ответ подтверждается новым retrieval.

## Требования

- Целевая версия — Python **3.13**.
- Groq key нужен только тем этапам, которые явно вызывают Groq. Для необязательного OpenAI-сравнения Day 28 используется `OPENAI_API_KEY`; локальному режиму ключи не нужны.
- Интернет требуется для Groq, OpenAI и живых GitHub API-вызовов.
- Retrieval/RAG-этапы и Дни 26–31 используют локальный **Ollama**.
- Дню 27 также нужны Git, совместимый JDK и Detekt CLI; дополнительных pip-зависимостей у его Python-модуля нет. Документированный hook-флоу рассчитан на macOS/Linux.
- День 30 устанавливает собственный `requirements.lock` (FastAPI/httpx/Uvicorn/Argon2); основной Mac/phone путь требует Tailscale, прямой LAN — Caddy и trust собственного CA. Индекс/embedding model не нужны.
- День 31 использует собственный `requirements.lock`, Git и настоящий stdio MCP server. Принятый Documentation-сценарий использует FTS54 и Qwen2.5:14b без новых embeddings; его состояние и индексы хранятся вне repo. Проверка сохранённой поставки не требует Ollama.
- День 32 использует Python 3.12+, стандартную библиотеку и SQLite FTS5; offline-тестам не нужны Ollama или API-ключ. Реальные GitHub/Groq-запросы требуют сети и отдельно согласованных credentials; live-генерация остаётся выключенной.
- День 33: Python 3.12+, собственный MCP SDK requirements.txt и SQLite FTS5; для сохранённой приёмки не нужны API-ключ/Ollama. HTTP-демо всегда mock; реальный Groq принят отдельным CLI через curl.
- `GITHUB_TOKEN` необязателен для публичных GitHub-репозиториев, но помогает с rate limits.

### Локальные модели

| Этапы | Embeddings | Generation |
|---|---|---|
| 21–22 | `bge-m3` | `llama3.2` в базовом документированном флоу |
| 23 | `bge-m3` | `llama3.2` по умолчанию; `qwen2.5:7b` в зафиксированных экспериментах |
| 24–25 | `bge-m3` | `qwen2.5:14b` в текущем grounded/live профиле |
| 26 | Не требуются | `qwen2.5:7b` по умолчанию; `qwen2.5:14b` в проверенном запуске |
| 27 | Не требуются | `qwen2.5:14b` по умолчанию; настраиваемая скачанная локальная модель |
| 28 | `bge-m3` | `qwen2.5:14b` по умолчанию; опциональное сравнение с Groq/OpenAI |
| 29 | `bge-m3` | Выбрана `qwen2.5:14b` Q4_K_M; Q5_K_M сравнивалась на одном справочном кейсе |
| 30 | Не нужны | `qwen2.5:14b` Q4_K_M; private-chat-v2, context 8192 / output 1024 |
| 31 | Не требуются для принятого FTS-сценария | `qwen2.5:14b` Q4_K_M; один принятый RU-1 / Multi вызов, без cloud fallback |

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

Все answer-модели одновременно не обязательны: эти команды покрывают документированные профили до Дня 31.

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
| 28 | `python day-28-local-rag/main.py ask "Какой процесс выполняет фоновые задания на Day 18?"` | Один локальный RAG-ответ с цитатами источников |
| 29 | `python day-29-local-llm-optimization/experiments/quality_v7/main.py verify day-29-local-llm-optimization/reports/check/quality-transfer-v7.json` | Offline-проверка согласованности сохранённых доказательств V7 |
| 30 | `python day-30-private-ai-service/scripts/verify_report.py day-30-private-ai-service/reports/verified/languages-policy-v4-offline-20261011.json` | Сверить текущие 229/229 offline regression, RU/EN и RAG memory проверки; запуск сервера — README дня 30 |
| 31 | `python day-31-course-minimum/verify_delivery.py --root "$PWD"` | Проверить целостность сохранённой поставки, 60 Python-файлов и 79 Mac-отчётов без Qwen; это не новая runtime-приёмка |
| 32 | `python -m unittest discover -s day-32-pr-review/tests -v` | Запустить offline-тесты AI-ревью без облачной генерации; реальные доказательства и статус PARTIAL — в README Дня 32 |
| 33 | `python day-33-support-assistant/verify_delivery.py` | Проверить сохранённый real Groq PASS и runtime SHA без новой генерации; CLI/HTTP — в README Day 33 |

## Общий индекс Дня 21

Дни 21–25 и 28–29 используют:

```text
day-21-document-indexing/knowledge.db
```

Правило корпуса остаётся намеренно ограниченным:

- корневые `README.md` и `README.ru.md`;
- README этапов 1–20;
- Python-файлы дней 16–20, кроме тестов.

README дней 21–30 автоматически в индекс не добавляются. Дни 26–27 и 30 не используют этот индекс.

Индекс хранит digests документов и revision корпуса. Изменение **корневых README** меняет индексируемый текст. После установки этих обновлённых корневых README пересобери индекс перед следующей строгой проверкой или живым RAG-запросом Дня 24/25/28/29. Сохранённые исторические отчёты при этом не меняются. Day 28 допускает сам Git-коммит, если fingerprint индексируемого корпуса остался прежним:

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

[Модуль Day 28](day-28-local-rag/README.ru.md) открывает индекс Недели 6 / Дня 21 только для чтения, использует локальные embeddings bge-m3, retrieval/filter Дня 23 и скачанную Qwen через Ollama. `ask` и `evaluate` не требуют облачного ключа. `compare` дополнительно подключает Groq или OpenAI. В новой паре первый prompt и найденный контекст одинаковы; при двухэтапном синтезе итоговые доказательства/prompts провайдеров могут различаться.

Короткая локальная демонстрация:

```bash
python day-28-local-rag/main.py doctor
python day-28-local-rag/main.py ask \
  "Какой процесс выполняет фоновые задания на Day 18?" \
  --repeats 1 --max-tokens 512 \
  --output day-28-local-rag/reports/check/video-local.json
python day-28-local-rag/verify_report.py \
  day-28-local-rag/reports/check/video-local.json
```

`doctor` не генерирует ответ: ноль попыток и `local_rag_verified=false` в нём нормальны. Успешный локальный запрос сохраняет ответ/источники, подтверждение загрузки и `local_rag_verified=true`. Модели и индекс подготавливаются до отключения интернета. JSON фиксирует локальные адреса и генерацию; фактическое отключение сети подтверждается записью/окружением.

Исходные live-результаты сохранены в [reports/accepted](day-28-local-rag/reports/accepted/):

| Прогон | Зафиксированный результат | Медиана генерации |
|---|---|---:|
| Исходный V2, 20 вопросов ×3 на провайдера | Local: 60/60 валидных, эвристическое качество 48/60; Groq: 48/60 валидных, качество 38/48 | Local 54,53 с / Groq 0,82 с |
| V11, один исправленный local-вопрос об изоляции ×3 | Качество/ручной просмотр 3/3; точная стабильность ответа/цитат 1/1 группы; два вызова на пробу | 43,03 с, оба этапа |
| V12, три OpenAI-вопроса ×3 | 9/9 валидных без API-ошибок; исходное качество 5/9 | 2,94 с |
| V16, исправленный OpenAI-вопрос об инвариантах ×3 | Качество/ручной просмотр 3/3; цитаты одинаковые, формулировки различаются | 2,84 с |
| Опубликованный video-local, один пользовательский local-вопрос | Валидный ответ с цитатой; модель загружена; заданной эвристической рубрики нет | 20,03 с (pipeline 21,40 с) |

Оценки качества V2 исторические; валидность включает отказы приложения. Последующие выборочные успехи разных версий сохраняются без объединения в новый общий результат всего набора. Точная стабильность V16 — 0/1 группы; ручной просмотр подтверждает сохранение механизма и цитат во всех трёх ответах. Этот cloud-only прогон не является новым сравнением скорости с двухэтапным local V11.

На проверенном коде V16 прошёл **71 offline-тест**. [Локальные/парные результаты](day-28-local-rag/FINAL_REPORT.ru.md), [исходный OpenAI](day-28-local-rag/OPENAI_RESULTS.ru.md), [исправления качества](day-28-local-rag/QUALITY_RESULTS_V16.ru.md) и [итог стабильности](day-28-local-rag/STABILITY_RESULTS_V16.ru.md) раскрывают объём и ограничения. Локальный RAG, облачное сравнение и оценка качества/скорости/стабильности выполнены; полный повтор для сдачи не требуется.

Необязательное облачное сравнение: `compare --cloud-provider openai` с `OPENAI_API_KEY` или Groq по умолчанию с `GROQ_API_KEY`. Ключи могут находиться в существующем корневом `.env`; локальные команды их не загружают. Локальный режим по умолчанию — `baseline`; специализированный `phases` предназначен только для вопросов до/после. Команды и количество вызовов — в README Дня 28.

## День 29 — оптимизация локальной LLM под задачу

[Модуль Дня 29](day-29-local-llm-optimization/README.ru.md) оптимизирует локальную Qwen для справки по репозиторию, отказа без доказательств и источниковой проверки периодического VPS-worker Дня 18. Он переиспользует индекс Дня 21 и компоненты Дня 28; облачный ключ и fallback не нужны.

Выбраны **Qwen2.5 14B Instruct Q4_K_M**, локальные bge-m3, temperature=0, лимит ответа=1024 и контекст=8192. Замеры выполнены на MacBook Pro M1 / 32 GB. Исходные лимиты — 2048 / 16384. Prompt и лимиты менялись совместно; отдельный эффект температуры и дообучение весов в измеренный результат не входят.

V3 формирует короткую справку. V7 направляет поддерживаемые процедурные вопросы в выбор четырёх ролей доказательств: статус, журнал, выполнение и повторение. Приложение проверяет выбор и собирает процедуру из цитат. Сырые выборы и показанный ответ хранятся отдельно; законченные неудачные ответы кешируются без скрытых повторов. Текущий launcher — `experiments/quality_v7/main.py`, а не исходный корневой launcher экспериментов.

| Доказательство | Зафиксированный результат |
|---|---|
| Четыре справочных/отказных вопроса ×3 | 12/12 PASS содержательного ревью |
| Исходная периодическая процедура V7 ×3 | 3/3 PASS содержательного ревью |
| Frozen новые RU/EN формулировки ×3 каждая | 6/6 PASS; ответы одинаковы внутри каждой тройки |
| Факт о worker: baseline / Q4-V3 / Q5-V3 | Медиана генерации 26.281 / 6.091 / 7.665 с |
| Периодическая процедура: V6 / V7 | Медиана генерации 16.572 / 6.077 с при изменённом контракте ответа |
| Аллокация Q4 / Q5 на вопросе о worker | Максимальная Ollama `size_vram` 9.56 / 10.89 GiB |

Это 21 проверенное наблюдение выбранного профиля на семи вопросах, включая три формулировки одной процедуры. Содержательные оценки ассистента хранятся отдельно от автоматических аудитов. Q4/Q5 проверены только на одном справочном вопросе; универсального улучшения рассуждения не заявляется. 75 выходных токенов V7 — выборы, а не полный текст процедуры. На время влияют cache/prefill; RSS и `size_vram` не равны полной физической unified memory.

Проверить опубликованные доказательства без Ollama и исходной базы:

```bash
python day-29-local-llm-optimization/experiments/quality_v7/main.py verify \
  day-29-local-llm-optimization/reports/check/quality-transfer-v7.json
```

`consistent=true` проверяет согласованность отчёта; сохранённый автоматический `optimization_verified=false` по-прежнему требует отдельного содержательного ревью. Исходные отчёты опубликованы в `reports/check/` несмотря на правило игнорирования каталога; новые результаты и кеш остаются локальными. После изменения документации нужен rebuild индекса перед новым live-запуском, но не для проверки сохранённых отчётов.

Подробнее: [итоговые замеры](day-29-local-llm-optimization/FINAL_REPORT.ru.md), [выбранный профиль](day-29-local-llm-optimization/SELECTED_PROFILE.json), [приёмка задания](day-29-local-llm-optimization/ASSIGNMENT_CHECKLIST.ru.md) и [валидация](day-29-local-llm-optimization/VALIDATION.md). Задание выполнено в указанной области; новая генерация необязательна.

## День 30 — Bublik Private AI Service

**Текущее расширение: 0.10.3.** Язык интерфейса и ответов (русский/английский)
выбирается отдельно, сохраняется у владельца и загружается на всех устройствах.
Schema 3 добавляет настройки; archive/restore принимает схемы 2/3 без замены
оригиналов. [Обновление и языковые проверки](day-30-private-ai-service/LANGUAGES.ru.md).
Текущая проверка: [229/229 offline-тестов](day-30-private-ai-service/reports/verified/languages-policy-v4-offline-20261011.json)
и [33/33 live-проверок HTTPS/Qwen на Mac](day-30-private-ai-service/reports/verified/languages-policy-v4-live-mac-20261011.json).
Четыре реальные генерации проверили русский/английский ответ без RAG и с RAG в следующем
сообщении, включая просьбу пользователя отвечать на противоположном языке. Оператор
также подтвердил переключение языков через UI и работу на телефоне. Ручная проверка
отделена от JSON-отчёта; эти примеры не гарантируют язык любого возможного ответа.

После курса **0.9.1** добавляет включённый по умолчанию в Web UI RAG по обеим сторонам
сохранённой переписки: отдельный FTS5-индекс владельца, точные источники с ролями/статусами, исходный разговор и
неизменяемые RAG snapshots. В RAG 0.9.1 использовалась схема 2; текущая схема 3 описана выше. Embedding
модель и облачные LLM не используются. [Установка и проверки](day-30-private-ai-service/RAG_MEMORY.ru.md).
Live-результаты 0.8.0 ниже исторические и не доказывают качество 0.9.1.

[День 30](day-30-private-ai-service/README.ru.md) превращает локальную Qwen в
приватный HTTP-сервис: несколько диалогов, история в SQLite и адаптивный Web UI.
Mac, Android и iPhone открывают один диалог и продолжают переписку. PWA можно
добавить на домашний экран телефона.

Проверенный сервер — **MacBook Pro M1 с 32 GB unified memory**. Ollama выполняет
Qwen2.5:14b Q4_K_M на localhost; FastAPI отвечает за авторизацию, API v1, бюджет
контекста, лимиты и сохраняемую очередь. **Облачных LLM, автоматического cloud
fallback нет.** В принятой версии0.8.0 RAG не использовался; расширение0.9.1
включает поиск по истории в Web UI по умолчанию. Полная сохранённая история отделена от
ограниченного недавнего контекста, передаваемого модели.

**Tailscale Serve** — основной приватный HTTPS-доступ через домашний Wi-Fi и
мобильную сеть. Нужны Tailscale на клиенте, вход в приложение и бодрствующий Mac
с подключением к сети. Для `.ts.net` URL не требуется вручную устанавливать
локальный CA. Дополнительный путь через **Caddy** даёт прямой LAN HTTPS и требует
доверия собственному CA. Ollama и API слушают только localhost.

| Сохранённые проверки runtime 0.8.0 / private-chat-v2 | Результат |
|---|---|
| Реальный Mac API/Qwen, включая 10 последовательных и 3 конкурентных запроса | 259/259 технических проверок; 13/13 контрольных проверок качества |
| История после рестарта API | 11/11; семь чатов и 32 сообщения без изменений |
| Текущий LAN HTTPS / launchd с Mac | 6/6 |
| Offline / Chromium / PWA fixtures | 143/143; 26/26; 11/11 |
| Реальный телефон и повседневная работа | Android handoff 8/8; синхронизация Mac/Android/iPhone и мобильный доступ подтверждены вручную |

Конкурентные API-запросы ставятся в очередь; модель выполняет **одну генерацию
за раз**. Fixtures не доказывают реальную сетевую доступность или работу модели.
Проверки качества относятся к сохранённым примерам, а не любым возможным ответам.
Исходные успешные и неуспешные отчёты сохранены в
[итоговом отчёте](day-30-private-ai-service/FINAL_REPORT.ru.md).

Из корня, с активным Python 3.13 virtualenv:

```bash
python -m pip install -r day-30-private-ai-service/requirements.lock
python day-30-private-ai-service/scripts/verify_report.py \
  day-30-private-ai-service/reports/verified/languages-policy-v4-offline-20261011.json
```

Это сверка сохранённых доказательств с хешами исходников, а не запуск сервера.
Установку, безопасный вход, телефоны, launchd и остановку перед сном Mac описывают
[README дня](day-30-private-ai-service/README.ru.md) и
[инструкция эксплуатации](day-30-private-ai-service/RUNBOOK.ru.md).
Пользователь записал UI-видео с чатом на нескольких устройствах;
[консольный сценарий](day-30-private-ai-service/CONSOLE_VIDEO.ru.md) остаётся необязательным.

Восстановление рабочей истории в отдельную базу проверено оператором на том же Mac.
Перенос на другой хост, LAN CA на телефонах и независимый аудит сохранённой tailnet
policy остаются отдельными задачами. См.
[приёмку](day-30-private-ai-service/ACCEPTANCE.ru.md) и
[backlog](day-30-private-ai-service/BACKLOG.ru.md). Rust сейчас не внедряется;
сопоставимое исследование накладных расходов API отложено до окончания курса.

Изменение корневых README меняет fingerprint корпуса дня 21. Перед новым строгим
RAG live-запуском пересоберите индекс; день 30 и проверка сохранённых отчётов его
не используют. Реализации предыдущих дней и исторические JSON сохранены.

После дня 30 добавлен отдельный [этап переносимости истории](day-30-private-ai-service/MEMORY_PORTABILITY.ru.md):
проверяемый backup и восстановление в новую базу. Этот первый инструмент не менял
API runtime. Следующее расширение0.9.1 с lexical RAG описано выше; semantic retrieval
и версионируемые факты остаются в backlog. Исторический отчёт69/69 проверяет только
storage; исходные 143/143 model/API fixture остаются историческим результатом.

## День 31 — Bublik Developer Assistant

**Course Minimum — Accepted.** [Ассистент разработчика](day-31-developer-assistant/README.ru.md) работает с документацией проекта через отдельный Project RAG, получает branch/status/files/diff через настоящий read-only MCP Git и делегирует задачи ролям Main, Documentation, Git и Verification. Этот индекс отделён от базы знаний Дня 21 и личной истории Дня 30.

Базовое приложение App 0.7.29 сохранено в `day-31-developer-assistant/`. Проверенные producer, anchor persistence и launcher расположены отдельно в [`day-31-course-minimum/`](day-31-course-minimum/README.ru.md). Publication Gate v104-r2 работает в изолированной копии приложения; он не объявляется установленным в исходный `main.py`. Принятый сценарий использует FTS54 — 54 документа / 510 чанков; production44 — 44 документа / 405 чанков сохранён отдельно.

| Подтверждённые результаты | Область проверки |
|---|---|
| Mac preflight r3: 32/32 PASS | Реальные MCP Git, делегация, завершение workers и отказ `unknown` без evidence; 0 Qwen-вызовов |
| RU-1 / Multi: один реальный вызов Qwen2.5:14b Q4_K_M | 1109 input / 396 output tokens, 47.67 s chat; без повторов и cloud fallback; один замер, не benchmark |
| Human review + Publication Gate | c1/c2 supported; выбранные exact anchors и fingerprints сохранены; `answer_accepted=true` |
| Mac-проверка размещённой поставки | Три исходных пакета, 60 Python-файлов, 79 отчётов с SHA; обязательные inputs не скрыты Git ignore rules |

Проверить сохранённую поставку из корня repo без модели и сети:

```bash
python day-31-course-minimum/verify_delivery.py --root "$PWD"
```

`status=passed` подтверждает целостность сохранённых данных и human review, а не новую генерацию или semantic приёмку текущей ревизии. Реальные MCP-команды, публикация сохранённого ответа и зависимости рабочего окружения описаны в README дня 31. Видео через терминал записано; [сценарий](day-31-developer-assistant/CONSOLE_VIDEO.ru.md) сохранён как описание подготовленного окружения.

**Расширенный Research Stage 7 не завершён.** Полный multi-task Chain, EN-3 claim decomposition, общий human-review workflow, held-out, расширенная регрессия и исследования ресурсов перенесены в [BACKLOG_AFTER_COURSE.ru.md](day-31-developer-assistant/BACKLOG_AFTER_COURSE.ru.md). Один Documentation worker не выдаётся за несколько независимых LLM-контекстов. Тестовый транспорт модели отделён от реального Qwen-прогона; техническая проверка цитат не заменяет человеческую оценку смысла.

Исторические work/state остаются внешними; это не clean installer. Новый commit меняет закреплённый Git HEAD, а изменение этих корневых README делает прежние индексы Day 21 и Project RAG дня 31 stale относительно текущего корпуса. В этой ревизии индексы не перестраиваются. Старые frozen индексы, pins и результаты не переписываются; будущий live-поиск по обновлённой документации требует отдельной подготовки актуального индекса. Сохранённые evidence и human review от этого не меняются.

## День 32 — AI-ревью Pull Request: PARTIAL

[Модуль Дня 32](day-32-pr-review/README.ru.md) принят как **PARTIAL**. Настоящий GitHub [preflight](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38940777931) прошёл без генерации. Два Actions live-run ([38945811433](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38945811433), [38952494436](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38952494436)) завершились HTTP 403; GitHub Actions live E2E остаётся **FAIL**.

Отдельно разрешённое полное Groq review на Mac (`execution_environment=local_mac`) получило HTTP 200 за один POST: `openai/gpt-oss-120b`, 649 input / 284 completion tokens. Найдено деление на ноль в Draft [PR #2](https://github.com/Ly41k/ai-advent-llm-api/pull/2), `percentage.py:2`, предложено `/ 100`. Локальная техническая интеграция — **PASS**, качество review — **PARTIAL**: нет document evidence ID и необоснован дополнительный совет проверять нулевой input. Mac offline: исходная suite 53/53, внешний локальный helper 9/9; SQLite ResourceWarning сохранён.

[Итоговый отчёт](day-32-pr-review/FINAL_REPORT.ru.md) сохраняет SHA, request IDs, ссылки на runs/artifacts, отдельный Mac smoke-test 74/19 tokens и различие оценки стоимости и billing. Live выключен (`DAY32_LIVE_ENABLED=false`); демонстрационный [PR #2](https://github.com/Ly41k/ai-advent-llm-api/pull/2) закрыт без merge, документационный [PR #3](https://github.com/Ly41k/ai-advent-llm-api/pull/3) объединён с `main`. Сырые payload/response и приватные evidence не включаются в публичную поставку. Документация не разрешает новые генерации.

## День 33 — AI-ассистент поддержки: PASS

[Модуль Day 33](day-33-support-assistant/README.ru.md) принят как **PASS** в Course Minimum. Mac offline 25/25; новая attempt-03 выполнила настоящий MCP `get_ticket(T-101)` → `get_user(U-001)`, FTS5/BM25 top-3 и один Groq curl POST: HTTP 200, `openai/gpt-oss-120b`, **1370 input / 233 completion tokens**. Исправленный валидатор и смысл сохранённого ответа прошли проверку.

Истечение сессии явно задано синтетическим тикетом, а не выведено только из 401. Модельные цитаты отделены от `assigned_by: application`. Предыдущие 403 и evidence-отказ сохранены; replay не подменяет новый live. [Итоговый отчёт](day-33-support-assistant/FINAL_REPORT.ru.md) содержит SHA, request IDs, расчёт $0.0003453 и неизвестный billing. Реальная модель проверена на T-101; остальные обязательные сценарии — offline. HTTP-демо mock, настоящий Groq принят через CLI. База Day 30 не менялась. Видео Day 33 уже записано владельцем; его [сценарий для терминала](day-33-support-assistant/CONSOLE_VIDEO.ru.md) использует сохранённый ответ без новой генерации. [PR #5](https://github.com/Ly41k/ai-advent-llm-api/pull/5) объединён с `main` 17.10.2026.

## Тесты

Локальные тесты используют fake/scripted HTTP, SQLite, локальные MCP-серверы или fixtures. Они не вызывают платные облачные API, если команда явно не запускает живую модель/API.

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
python -m unittest discover -s day-28-local-rag -p 'test*28.py'
python day-29-local-llm-optimization/test_day29.py -v
python -m unittest discover -s day-29-local-llm-optimization/experiments/quality_v7 -p test_quality_v7.py -v
python -W error::ResourceWarning day-30-private-ai-service/scripts/check_storage.py
python -m unittest discover -s day-32-pr-review/tests -v
python -W error::ResourceWarning -m unittest discover -s day-33-support-assistant/tests -v
python day-33-support-assistant/verify_delivery.py
```

## Данные и ограничения

- День 31 принят в ограниченной конфигурации Course Minimum. Publication Gate требует явного human review текущих bindings; произвольные новые ответы, полный Chain и Research Stage 7 этой приёмкой не подтверждены.

- День 27 — локальная pre-commit проверка, которую можно обойти. Она анализирует изменённые файлы целиком без type resolution и не заменяет компиляцию KMP, Android Lint или CI. Стиль комментариев влияет только на объяснения.
- Сгенерированные SQLite-базы, временные отчёты, ответы моделей и доступность провайдеров зависят от окружения. В Day 28 отобранные исходные JSON сохраняются в `reports/accepted/`, аудиты — в `reports/verified/`; рабочие `reports/check/` и материалы `reports/video/` игнорируются Git.
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
