# Архитектура репозитория

## Локальные инструменты разработчика: день 31

День 31 — отдельный пакет bublik_developer в day-31-developer-assistant.
Точка входа main.py импортирует bublik_developer.cli. ProjectWorkspace закрепляет
корень локального Git-репозитория и логический project ID. Read-only данные Git
поступают через настоящий FastMCP stdio server с discovery и call_tool.

Индекс документации проекта отделён от Week 6 knowledge.db и личной базы
переписки дня 30. Project RAG использует SQLite FTS5, локальные bge-m3 embeddings
и hybrid RRF. Он возвращает точные выдержки с относительными путями, строками,
raw digests и версиями корпуса/индекса. Индекс хранится вне репозитория.
Личная история дня 30 не входит в корпус. Изменение документа делает старые
доказательства устаревшими; такие выдержки не публикуются.

## Задачи и независимые контексты дня 31

Runtime делегирует Documentation, Git и Verification отдельные TaskEnvelope
с запечатанными контекстами. Documentation и Verification используют owned
worker processes; Git использует настоящий MCP. Dispatcher проверяет зависимости,
capabilities ролей и общий budget вызовов. Documentation и Git могут выполняться
параллельно; Verification проверяет их результаты. Lifecycle содержит
SPAWN / EXECUTE / REPORT / MERGE.

Демонстрация agents demo не вызывает LLM. Команды /help question и ask используют
ограниченный RU/EN Router. Независимые вопросы о документации и Git идут через
fan-out. Поиск документации изменённых файлов зависит от результата Git status.
Несколько неоднозначных Git-намерений требуют уточнения.

## Генерация Documentation и сборка Main дня 31

Documentation получает отдельный вопрос и исходные выдержки источников.
Main получает полный вопрос, уже проверенные утверждения (checked claims)
и Git-факты, сформированные приложением. Исходные выдержки не входят в контекст
сборки Main. Git и Verification не имеют capability генерации.

Main может выбирать и упорядочивать существующие claim/fact IDs. Он не может
добавить новый текст, новые факты или переписать утверждения Documentation.
Модельные вызовы Qwen сериализованы через общую model lease. Перед публикацией
источники проверяются снова, а Git независимо наблюдается после генерации.
Проверка точного происхождения цитат не доказывает правильность смысла каждого
утверждения; формулировки требуют отдельного semantic human review.

Bare /help и Git-only запросы не требуют модели или индекса. Search возвращает
выдержки. Console помнит один предыдущий вопрос о документации в рамках project
identity и corpus revision; это не личная история. Реальные контексты Qwen
проверяются отдельными отчётами Mac.

## Более ранние MCP-компоненты: дни 16–20

День 16 устанавливает stdio-соединение, день 17 добавляет инструмент GitHub.
День 18 хранит scheduled jobs и выполняет их через worker.py. День 19 объединяет
вызовы инструментов в цепочку. День 20 использует ToolRegistry в
day-20-mcp-orchestration/mcp_registry.py для discovery namespaced catalog
серверов GitHub, analysis и storage. MCP server предоставляет инструменты;
он не становится независимым subagent автоматически.

## RAG-компоненты: дни 21–29

День 21 реализует corpus collection, fixed/structural chunking, embeddings,
SQLite vectors и cosine retrieval. Его общий корпус ограничен README дней 1–20
и выбранными Python sources дней 16–20. Дни 23–25 добавляют filtering, citations
и контекст разговора. День 28 соединяет retrieval с Ollama generation и открывает
существующий индекс read-only. День 29 добавляет измерения и task prompts:
temperature 0, num_ctx 8192, до 1024 output tokens в выбранном профиле Qwen.

## Приватный сервис: день 30

bublik_service предоставляет FastAPI HTTP API и Web UI. SQLite хранит owners,
chats, оригинальные сообщения, generation jobs и context snapshots. Coordinator
выполняет одну активную генерацию. Ollama предоставляет локальный
Qwen2.5:14b Q4_K_M. Browser clients используют одну серверную переписку через
authenticated HTTPS.

Источники: day-31-developer-assistant/bublik_developer/cli.py;
day-31-developer-assistant/bublik_developer/agent_runtime.py;
day-31-developer-assistant/bublik_developer/pipeline.py;
day-31-developer-assistant/bublik_developer/generation.py;
day-21-document-indexing/corpus.py;
day-29-local-llm-optimization/SELECTED_PROFILE.json;
day-30-private-ai-service/bublik_service/inference/coordinator.py.
