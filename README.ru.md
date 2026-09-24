[English](README.md) | **Русский**

# AI Advent — от первого LLM-запроса до агента с MCP-инструментами

Практический проект на Python и Groq API. Сначала задания посвящены промптам, моделям, токенам и контексту. Затем развивается **BublikAgent**: диалоги с сохранением в SQLite, слои памяти, персонализация, проверки состояния задачи и отдельные эксперименты с MCP. **Чебуратор** — капитан исследовательского корабля, **Бублик** — помощник, который развивается по ходу курса.

Каждая папка `day-XX-...` — самостоятельный учебный этап с английской и русской инструкциями. Сейчас в репозитории **дни 1–19**. Это последовательные версии и эксперименты: инструменты Дня 19 не встроены автоматически в одну общую программу со всеми предыдущими версиями агента.

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

## Как развивается архитектура

- **Дни 1–5:** исследование API-параметров, промптов, моделей и измеримых результатов.
- **Дни 6–10:** отделение логики агента от CLI, SQLite-диалоги и управление бюджетом контекста.
- **Дни 11–15:** слои памяти, профили, автомат состояний задачи, инварианты и контролируемые переходы. В Дне 15 выполнение требует утверждённого плана, а `done` — успешной валидации.
- **День 16:** Python MCP SDK, локальный stdio-сервер и обнаружение `ping` и `add`.
- **День 17:** инструмент `get_github_repo(owner, repo)`. Отдельный `BublikMcpAgent` передаёт его схему модели Groq, выполняет запрошенный MCP-вызов и возвращает результат модели.
- **День 18:** MCP-инструмент записывает периодическое GitHub-задание в SQLite. Отдельный worker запускает просроченные задания, сохраняет снимки, а другой инструмент возвращает агрегированную сводку.
- **День 19:** `BublikPipelineAgent` последовательно вызывает `search_repository`, `summarize_repository`, `save_report`. Полный результат каждого MCP-вызова передаётся следующему; при ошибке цепочка останавливается. Текст сводки формируется по правилам, без вызова LLM.

Серверы MCP в днях 16–19 общаются с локальными клиентами через **stdio**. В днях 17–19 для получения живых данных используется публичный GitHub REST API. Для постоянного наблюдения отдельный непрерывно работающий процесс нужен только worker Дня 18; пайплайн Дня 19 запускается по команде.

## Требования и установка

- Целевая версия проекта — Python **3.13**.
- Ключ Groq нужен для интерактивных примеров с моделью, включая агентские приложения дней 17–18. Для подключения Дня 16, пайплайна Дня 19 и локальных тестов ключ не требуется.
- Интернет нужен для запросов к Groq и получения живых данных GitHub. `GITHUB_TOKEN` необязателен для публичных репозиториев, но помогает при ограничениях API.

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

Для других этапов замените папку на `day-16-mcp-connection`, `day-17-first-mcp-tool` или `day-18-scheduled-mcp`.

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

**Проверка Дня 18 без Groq**: создайте расписание через `mcp_cli.py`, один раз обработайте задания и прочитайте сохранённую сводку:

```bash
python day-18-scheduled-mcp/mcp_cli.py schedule Ly41k ai-advent-llm-api 60
python day-18-scheduled-mcp/worker.py --once
python day-18-scheduled-mcp/mcp_cli.py summary Ly41k ai-advent-llm-api
```

После запуска Дня 19 откройте `day-19-mcp-composition/reports/Ly41k-ai-advent-llm-api-summary.md`. Для другой папки отчётов задайте `BUBLIK_REPORT_DIR`. [Проверка Дня 18](day-18-scheduled-mcp/VERIFY.ru.md) описывает worker и VPS; [инструкция Дня 19](day-19-mcp-composition/README.ru.md) — автоматическую цепочку.

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
```

Тесты Дня 19 проверяют обнаружение инструментов, порядок вызовов, **точную передачу данных** между обеими парами, содержимое файла, повторную запись и остановку при ошибках. Есть проверка всей команды `main.py`. Отдельно можно выполнить живой запуск с GitHub API.

## Данные и ограничения

- SQLite-данные ранних этапов и расписания/снимки Дня 18 хранятся локально. База Дня 18 по умолчанию: `day-18-scheduled-mcp/schedule.db`. Через `BUBLIK_DB_PATH` worker и клиент можно направить к одной другой базе.
- Worker Дня 18 пишет результаты в stdout или журнал сервиса; автоматическую отправку в чат этот пример не реализует. Для непрерывного запуска на VPS приведён образец systemd unit.
- День 19 сохраняет текущий снимок метаданных репозитория в игнорируемой Git папке `reports/`. Он не работает по расписанию и не требует VPS.
- Ответы модели, доступные модели Groq, лимиты и оценки стоимости могут меняться. Актуальные названия и цены проверяйте в [документации Groq](https://console.groq.com/docs).

## Полезные ссылки

- [Groq Console](https://console.groq.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Документация GitHub REST API](https://docs.github.com/en/rest)
