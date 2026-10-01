[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до MCP-инструментов и RAG-ответов

Практический проект на Python и Groq API. Сначала задания посвящены промптам, моделям, токенам и контексту. Затем развивается **BublikAgent**: диалоги с сохранением в SQLite, слои памяти, персонализация, проверки состояния задачи, эксперименты с MCP, общая локальная база знаний, полноценный RAG-флоу, переписывание поискового запроса и фильтрация релевантности. **Чебуратор** — капитан исследовательского корабля, **Бублик** — помощник, который развивается по ходу курса.

Каждая папка `day-XX-...` — самостоятельный учебный этап с английской и русской инструкциями. Сейчас в репозитории **дни 1–23**. Это последовательные версии и эксперименты: новые этапы переиспользуют нужные части предыдущих дней, но не объединяют автоматически все версии агента в одно приложение.

## Путь проекта

| День | Тема | Результат |
|---|---|---|
| [01](day-01-first-api-request/README.ru.md) | Первый запрос | Консольный чат через Groq с историей сеанса |
| [02](day-02-response-control/README.ru.md) | Управление ответом | Структура, длина и правила ответа |
| [03](day-03-reasoning-methods/README.ru.md) | Способы рассуждения | Сравнение четырёх подходов к одной задаче |
| [04](day-04-temperature/README.ru.md) | Температура | Сравнение точности, креативности и вариативности |
| [05](day-05-model-versions/README.ru.md) | Сравнение моделей | Качество, задержка, токены и оценка стоимости |
| [06](day-06-first-agent/README.ru.md) | Первый агент | `BublikAgent`, CLI и SQLite-память |
| [07](day-07-context-persistence/README.ru.md) | Сохранение контекста | Независимые диалоги после перезапуска |
| [08](day-08-token-usage/README.ru.md) | Токены | Локальная оценка, фактический расход и стоимость запроса |
| [09](day-09-context-compression/README.ru.md) | Сжатие | Сохранённая сводка и последние полные сообщения |
| [10](day-10-context-strategies/README.ru.md) | Стратегии контекста | Sliding Window, Sticky Facts и Branching |
| [11](day-11-memory-layers/README.ru.md) | Модель памяти | Краткосрочная, рабочая и долговременная память |
| [12](day-12-personalization/README.ru.md) | Персонализация | Профили пользователей и разделение их контекста |
| [13](day-13-task-state-machine/README.ru.md) | Состояние задачи | Сохраняемые этап, прогресс, ожидаемое действие и пауза |
| [14](day-14-invariants/README.ru.md) | Инварианты | Версионируемая политика и проверки до/после ответа |
| [15](day-15-controlled-transitions/README.ru.md) | Переходы задачи | Утверждение плана, guards, валидация и возобновление |
| [16](day-16-mcp-connection/README.ru.md) | Подключение MCP | Локальный сервер и клиент, stdio, обнаружение инструментов |
| [17](day-17-first-mcp-tool/README.ru.md) | Первый MCP-инструмент | GitHub-инструмент в цикле вызова инструментов моделью |
| [18](day-18-scheduled-mcp/README.ru.md) | Фоновые задачи | SQLite-расписание, отдельный worker и агрегированная сводка |
| [19](day-19-mcp-composition/README.ru.md) | Композиция инструментов | Три MCP-вызова: получить → обработать → сохранить Markdown |
| [20](day-20-mcp-orchestration/README.ru.md) | Оркестрация MCP | Пять выбранных моделью вызовов на трёх серверах с проверкой файла |
| [21](day-21-document-indexing/README.ru.md) | Индексация документов | Общая SQLite-база знаний, два способа разбиения, локальные эмбеддинги и сравнение поиска |
| [22](day-22-first-rag/README.ru.md) | Первый RAG-запрос | Сравнение без RAG/с RAG, найденный контекст, источники и набор из 10 контрольных вопросов |
| [23](day-23-reranking-filtering/README.ru.md) | Фильтрация и query rewrite | Top-K до и после фильтра, порог raw cosine, эвристический/модельный rewrite, калибровка и сравнение четырёх режимов |

## Как развивается архитектура

- **Дни 1–5:** исследование API-параметров, промптов, моделей и измеримых результатов.
- **Дни 6–10:** отделение логики агента от CLI, SQLite-диалоги и управление бюджетом контекста.
- **Дни 11–15:** слои памяти, профили, автомат состояний задачи, инварианты и контролируемые переходы. В Дне 15 выполнение требует утверждённого плана, а `done` — успешной валидации.
- **День 16:** Python MCP SDK, локальный stdio-сервер и обнаружение `ping` и `add`.
- **День 17:** инструмент `get_github_repo(owner, repo)`. Отдельный `BublikMcpAgent` передаёт его схему модели Groq, выполняет запрошенный MCP-вызов и возвращает результат модели.
- **День 18:** MCP-инструмент записывает периодическое GitHub-задание в SQLite. Отдельный worker запускает просроченные задания, сохраняет снимки, а другой инструмент возвращает агрегированную сводку.
- **День 19:** `BublikPipelineAgent` последовательно вызывает `search_repository`, `summarize_repository`, `save_report`. Полный результат каждого MCP-вызова передаётся следующему; при ошибке цепочка останавливается. Текст сводки формируется по правилам, без вызова LLM.
- **День 20:** три MCP-сервера публикуют пять инструментов; модель выбирает вызовы, агент проверяет порядок и аргументы, затем повторно читает и проверяет отчёт.
- **День 21:** индексируем README и код локальной embedding-моделью в SQLite, сравниваем фиксированные и структурные чанки на одних вопросах. На этой базе можно проверять поиск, переранжирование и локальные ответы.
- **День 22:** переиспользуем индекс Дня 21 для первого полного RAG-запроса. Одна и та же generation-модель отвечает на один вопрос без retrieval и с найденными чанками; provenance источников и 10 контрольных вопросов делают сравнение воспроизводимым.

- **День 23:** используем общий индекс и адаптер Ollama, расширяем поисковый запрос, отсекаем кандидатов включительным порогом raw cosine и ограничиваем итоговый контекст. Сравниваем `baseline`, `filter`, `rewrite`, `rewrite_filter`; подбираем порог на calibration и проверяем отдельную evaluation-группу.

Серверы MCP в днях 16–20 общаются с локальными клиентами через **stdio**. В днях 17–20 для получения живых данных используется публичный GitHub REST API. Для постоянного наблюдения отдельный непрерывно работающий процесс нужен только worker Дня 18. Дни 21–23 по умолчанию работают локально через Ollama: `bge-m3` строит эмбеддинги, а `llama3.2` генерирует ответы.

## Требования и установка

- Целевая версия проекта — Python **3.13**.
- Ключ Groq нужен для интерактивных примеров с моделью, включая агентские приложения дней 17–18. Для подключения Дня 16, пайплайна Дня 19, offline-проверок Дня 20 и локального Ollama-флоу дней 21–23 ключ Groq не нужен.
- Интернет нужен для запросов к Groq и получения живых данных GitHub. `GITHUB_TOKEN` необязателен для публичных репозиториев, но помогает при ограничениях API.
- Для дней 21–23 по умолчанию нужен локальный Ollama. Перед живой проверкой retrieval/RAG загрузите `bge-m3` и `llama3.2`. В исследовательском профиле Дня 23 используется `qwen2.5:7b`, явно переданный через `--answer-model`; кодовый default остаётся `llama3.2`. Базовый код этих трёх дней использует стандартную библиотеку Python; дополнительный cross-encoder требует `sentence-transformers`.

Команды из корня проекта:

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

На Windows окружение активируется командой `.venv\Scripts\activate`. Если команда Python 3.13 называется иначе, подставьте её имя.

Корневой `requirements.txt` содержит Groq, dotenv и токенизатор для ранних этапов. Перед запуском MCP-этапа установите **зависимости нужного дня**:

```bash
python -m pip install -r day-19-mcp-composition/requirements.txt
```

Для других этапов замените папку на `day-16-mcp-connection`, `day-17-first-mcp-tool`, `day-18-scheduled-mcp` или `day-20-mcp-orchestration`.

Для локальных retrieval/RAG-этапов установите Ollama и загрузите модели по умолчанию:

```bash
ollama pull bge-m3
ollama pull llama3.2
# Дополнительная модель из реальных экспериментов Дня 23:
ollama pull qwen2.5:7b
```

Если приложение Ollama уже запущено и обслуживает локальный API, отдельный `ollama serve` не нужен.

Для программ с Groq скопируйте `.env.example` в корневой `.env` и укажите `GROQ_API_KEY`. Файл `.env` исключён из Git; не показывайте ключ в коммитах и видеозаписях.

## Запуск

У дней 1–15 есть собственные `main.py`. Например, из корня репозитория:

```bash
python day-01-first-api-request/main.py
python day-15-controlled-transitions/main.py
```

В следующих этапах точки входа различаются:

| День | Команда из корня репозитория | Что произойдёт |
|---|---|---|
| 16 | `python day-16-mcp-connection/client.py` | Обнаружение `ping` и `add` без ключа и сети |
| 17 | `python day-17-first-mcp-tool/demo.py` | Живой запрос GitHub и детерминированная демонстрация без Groq |
| 17 | `python day-17-first-mcp-tool/main.py` | Интерактивный выбор MCP-инструмента моделью Groq |
| 18 | `python day-18-scheduled-mcp/worker.py` и `python day-18-scheduled-mcp/main.py` в разных терминалах | Периодический worker и интерактивный Groq-агент |
| 19 | `python day-19-mcp-composition/main.py Ly41k ai-advent-llm-api` | Одна команда запускает три MCP-инструмента и сохраняет отчёт |
| 20 | `python day-20-mcp-orchestration/main.py Ly41k ai-advent-llm-api --offline` | Пять вызовов на трёх серверах без Groq |
| 21 | `python day-21-document-indexing/main.py corpus`, затем `build` | Локальные эмбеддинги Ollama, два индекса SQLite, общая база знаний |
| 22 | `python day-22-first-rag/main.py compare "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"` | Один вопрос без RAG и с контекстом из индекса Дня 21 |
| 22 | `python day-22-first-rag/main.py evaluate` | Прогон 10 контрольных вопросов и запись `evaluation_results.json` |
| 23 | `python day-23-reranking-filtering/main.py questions` | 20 размеченных вопросов: 8 calibration и 12 evaluation |
| 23 | `python day-23-reranking-filtering/main.py compare "How does the Day 18 worker run?" --retrieval-only` | Четыре режима поиска с кодовыми defaults |

**Проверка Дня 18 без Groq**: создайте расписание через `mcp_cli.py`, один раз обработайте задания и прочитайте сохранённую сводку:

```bash
python day-18-scheduled-mcp/mcp_cli.py schedule Ly41k ai-advent-llm-api 60
python day-18-scheduled-mcp/worker.py --once
python day-18-scheduled-mcp/mcp_cli.py summary Ly41k ai-advent-llm-api
```

После запуска Дня 19 откройте `day-19-mcp-composition/reports/Ly41k-ai-advent-llm-api-summary.md`. Для другой папки отчётов задайте `BUBLIK_REPORT_DIR`. [Проверка Дня 18](day-18-scheduled-mcp/VERIFY.ru.md) описывает worker и VPS; [инструкция Дня 19](day-19-mcp-composition/README.ru.md) — автоматическую цепочку.

Для Дня 22 сначала один раз постройте базу знаний Дня 21, если `day-21-document-indexing/knowledge.db` ещё отсутствует:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-22-first-rag/main.py questions
python day-22-first-rag/main.py compare \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
python day-22-first-rag/main.py evaluate
```

## День 23: поиск, фильтр, rewrite и ответ

Все глобальные параметры Дня 23 стоят **до** подкоманды. Пример явно задаёт исследовательский профиль вместо кодовых defaults:

```bash
python day-23-reranking-filtering/main.py \
  --model bge-m3 --answer-model qwen2.5:7b \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --min-similarity 0.50 --rewrite-method heuristic \
  compare "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --output day-23-reranking-filtering/reports/check/compare.json
```

Для поиска без генерации добавьте `--retrieval-only` после вопроса. `search` также не формирует финальный ответ; `ask --mode rewrite_filter` запускает один режим. При `--rewrite-method llm` модель всё равно вызывается для rewrite, даже в retrieval-only. Пустой выбранный контекст даёт детерминированный отказ без вызова answer-модели.

На новом индексе сначала подберите порог, затем явно передайте результат:

```bash
python day-23-reranking-filtering/main.py \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --rewrite-method heuristic \
  calibrate --thresholds 0.15 0.25 0.35 0.45 0.50 0.55 0.65 \
  --output day-23-reranking-filtering/reports/check/calibrate.json

# Только пример: замените 0.55 на selected_threshold своей калибровки.
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 20 --final-k 5 --min-similarity 0.55 \
  --rewrite-method heuristic \
  evaluate --split evaluation \
  --output day-23-reranking-filtering/reports/check/evaluate.json
```

`evaluate` сохраняет JSON с полными traces и Markdown-сводку для четырёх режимов. В зафиксированном эксперименте fixed/20/5/0.50 точность размеченных источников выросла с 28.0% до 37.3%, средний контекст сократился с 2007.8 до 1393.3 слова, нужный документ найден на 10/10 положительных вопросов. Это исследовательский результат на уже просмотренном evaluation-наборе: ошибки генерации остаются, а rewrite не улучшил все метрики. Подробнее — в [README Дня 23](day-23-reranking-filtering/README.ru.md): defaults, метрики, публикация отчётов и ограничения.

## Тесты

Перед тестами установите зависимости соответствующего этапа. Локальные тесты используют заглушки или локальный HTTP-сервер: **они не расходуют токены Groq и не делают живых запросов к GitHub**.

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
```

Тесты Дня 19 проверяют обнаружение инструментов, порядок вызовов, **точную передачу данных** между обеими парами, содержимое файла, повторную запись и остановку при ошибках. Есть проверка всей команды `main.py`. Отдельно можно выполнить живой запуск с GitHub API. Тесты Дня 20 запускают три реальных MCP-сервера и проверяют маршрутизацию, порядок, передачу данных, повторное чтение и обработку ошибок. Offline-тесты Дня 22 проверяют, что NO RAG не вызывает retrieval, RAG выполняет `вопрос → поиск → контекст → LLM`, оба режима получают один и тот же вопрос, а контрольный набор содержит ровно 10 полноценных записей.

В проверенной версии у дней 21–23 соответственно 7, 6 и 21 тест — всего 34. Тесты Дня 23 проверяют включительный порог до final-K, общие candidate pools, пустой контекст без генерации, rewrite/fallback, разделение calibration/evaluation и путь CLI/HTTP/SQLite/отчёт. Локальная HTTP-заглушка проверяет контракт Ollama; тесты не доказывают качество ответов реальной модели.

## Данные и ограничения

- SQLite-данные ранних этапов и расписания/снимки Дня 18 хранятся локально. База Дня 18 по умолчанию: `day-18-scheduled-mcp/schedule.db`. Через `BUBLIK_DB_PATH` worker и клиент можно направить к одной другой базе.
- Worker Дня 18 пишет результаты в stdout или журнал сервиса; автоматическую отправку в чат этот пример не реализует. Для непрерывного запуска на VPS приведён образец systemd unit.
- День 19 сохраняет текущий снимок метаданных репозитория в игнорируемой Git папке `reports/`. Он не работает по расписанию и не требует VPS.
- День 20 сохраняет и перечитывает отчёт в `reports/`; работает по запросу без VPS. Для реальной Groq-модели нужен ключ.
- Дни 21–23 используют общий игнорируемый `day-21-document-indexing/knowledge.db`. В корпус входят корневые README, README уроков 1–20 и Python-файлы дней 16–20 без `test_*`. README уроков 21–23 и отчёты исключены, но **изменения корневых README меняют корпус**. `verify` сравнивает Git HEAD и отпечаток содержимого, поэтому новый коммит также может потребовать пересборки. Для строгой проверки постройте обе стратегии в окончательной версии checkout.
- День 22 переиспользует индекс Дня 21 и не создаёт вторую базу знаний. Команда `evaluate` сохраняет игнорируемый `day-22-first-rag/evaluation_results.json` с обоими ответами, источниками RAG, покрытием ожидаемых терминов и диагностикой попадания ожидаемых источников. Эти метрики помогают сравнивать режимы, но не заменяют ручную проверку смысловой правильности ответа.
- Метрики Дня 23 основаны на размеченных документах, а не семантической оценке каждого пассажа. `negative_abstention_rate` считает пустой контекст, а не любой текстовый отказ модели; покрытие терминов не является точностью ответа.
- В Дне 23 `reports/check/` и `reports/video/` игнорируются. Итоговые доказательства сохраняйте в `reports/live/` с именами вроде `evaluate_050.json` и `.md`. Текущие правила `*_results.json` / `*_results.md` работают и во вложенных папках. В проверенном коммите опубликованы сводки живых проверок, provenance и обзор ответов ассистентом, но исходные live-файлы `*_results` отсутствуют.
- Ответы модели, доступные модели Groq/Ollama, лимиты и оценки стоимости могут меняться. Перед использованием проверяйте актуальную документацию соответствующего провайдера.

## Полезные ссылки

- [Groq Console](https://console.groq.com/)
- [Ollama](https://ollama.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Документация GitHub REST API](https://docs.github.com/en/rest)
