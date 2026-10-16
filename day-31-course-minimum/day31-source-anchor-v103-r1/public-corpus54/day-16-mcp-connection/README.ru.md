# День 16 — Подключение MCP

Минимальная самостоятельная реализация задания курса.

## Что реализовано

- используется официальный Python MCP SDK;
- локальный MCP-сервер запускается через `stdio`;
- MCP-клиент устанавливает соединение с сервером;
- выполняется инициализация MCP-сессии;
- клиент получает список инструментов через `list_tools()`;
- полученные инструменты выводятся в консоль.

Для этого задания не нужны VPS, API-ключ, запрос к Groq или внешний MCP-сервис.

## Файлы

- `server.py` — минимальный MCP-сервер с инструментами `ping` и `add`;
- `client.py` — клиент, подключающийся к серверу и выводящий список tools;
- `test_mcp_connection.py` — smoke-тест соединения и получения tools;
- `requirements.txt` — зависимость MCP для этого дня.

## Запуск

Из корня проекта:

```bash
cd day-16-mcp-connection
python3 -m pip install -r requirements.txt
python3 client.py
```

Ожидаемый результат:

```text
Connecting to MCP server...
MCP connection established.
Server: Bublik Day 16 MCP Server ...
Available tools (2):
- ping: ...
- add: ...
```

## Проверка

```bash
python3 test_mcp_connection.py
```

Успешный результат:

```text
OK: MCP connection works and tools are returned correctly.
```

## Соответствие заданию

- MCP SDK подключён;
- MCP-соединение устанавливается;
- список доступных инструментов запрашивается;
- список корректно возвращается и выводится;
- отдельный тест проверяет оба требования.
