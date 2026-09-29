# День 22 — Первый RAG-запрос

Day 22 переиспользует локальный индекс из `day-21-document-indexing/knowledge.db` и добавляет два явно разделённых режима ответа:

- **без RAG**: `вопрос → LLM`;
- **с RAG**: `вопрос → embedding запроса → поиск релевантных чанков → вопрос + найденный контекст → LLM`.

Для честного A/B-сравнения оба режима используют **одну и ту же модель генерации** (`llama3.2` по умолчанию, temperature=0 в адаптере Day 21). RAG использует тот же embedding-провайдер и тот же индекс Day 21 (`bge-m3`, `structural` по умолчанию). Источники сохраняются вместе с RAG-ответом: `source`, `section`, диапазон строк и cosine score.

## Что реализовано

`rag_agent.py` содержит `Day22RAGAgent` с методами `answer_without_rag`, `answer_with_rag`, `answer` и `compare`. RAG-ветка напрямую переиспользует проверенный Day 21 retrieval: `retrieve(...)`, затем `answer_question(...)`, где найденные чанки объединяются с исходным вопросом перед вызовом LLM.

`questions.json` содержит **ровно 10 контрольных вопросов** по базе Day 21. Для каждого зафиксированы:

- `expectation` — что должно быть в ответе;
- `expected_terms` — диагностические термины;
- `expected_sources` — какие документы должны попасть в retrieval, если применимо.

`evaluation.py` запускает оба режима на всех десяти вопросах и сохраняет ответы, найденные источники, term coverage и source-hit diagnostics. Эти метрики нужны для воспроизводимого сравнения, но сами по себе не доказывают смысловую правильность ответа — итоговые ответы всё равно следует просмотреть глазами.

## Проверка по шагам на macOS

Из корня репозитория:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python day-22-first-rag/test_day22.py -v
```

Offline-тесты не требуют Ollama и проверяют главный контракт Day 22: NO RAG не вызывает retrieval, RAG делает `question → search → context → LLM`, сравнение использует один и тот же вопрос, а контрольный набор содержит ровно 10 полноценных записей.

Если индекс Day 21 ещё не построен:

```bash
ollama pull bge-m3
ollama pull llama3.2
# Если приложение Ollama уже запущено, отдельный `ollama serve` не нужен.
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

Посмотреть контрольные вопросы без обращения к модели:

```bash
python day-22-first-rag/main.py questions
```

Один вопрос без RAG:

```bash
python day-22-first-rag/main.py ask \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --mode no-rag
```

Тот же вопрос с RAG:

```bash
python day-22-first-rag/main.py ask \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --mode rag
```

Сразу A/B на одном вопросе:

```bash
python day-22-first-rag/main.py compare \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
```

Полный прогон десяти контрольных вопросов:

```bash
python day-22-first-rag/main.py evaluate
```

Команда печатает отчёт и записывает его в игнорируемый файл `day-22-first-rag/evaluation_results.json`. В summary сравниваются среднее покрытие ожидаемых терминов без RAG и с RAG, дельта между режимами и доля вопросов, где retrieval нашёл ожидаемый источник.

## Критерии задания — финальная сверка

- ✅ `вопрос → поиск релевантных чанков → объединение с вопросом → запрос к LLM` — `answer_with_rag()`.
- ✅ ответ модели без RAG — `answer_without_rag()`.
- ✅ ответ модели с RAG — `answer_with_rag()`.
- ✅ два режима агента — `ask --mode no-rag|rag`.
- ✅ прямое A/B-сравнение — `compare` запускает один вопрос в двух режимах на одной generation-модели.
- ✅ мини-набор из 10 контрольных вопросов — `questions.json` содержит ровно 10 записей.
- ✅ ожидание по каждому вопросу — поле `expectation`.
- ✅ ожидаемые источники — поле `expected_sources`.
- ✅ сравнение качества — `evaluate` фиксирует оба ответа, term coverage, retrieval sources и агрегированную дельту.
- ✅ воспроизводимость — temperature=0, единый Day 21 index/model contract, JSON-отчёт сохраняется на диск.

## Важные нюансы

Глобальные параметры (`--db`, `--model`, `--answer-model`, `--url`, `--strategy`, `--top-k`) ставятся **до** подкоманды. Если `knowledge.db` отсутствует, CLI не создаёт молча пустую базу, а просит сначала выполнить Day 21 `build`. Если embedding-модель отличается от модели, которой построен индекс, Day 21 retrieval останавливается с ошибкой — это защищает сравнение от несовместимых векторов.

Для видео достаточно показать: `test_day22.py -v` → `questions` → `compare` на одном вопросе → `evaluate` → открыть `evaluation_results.json` и показать два ответа плюс `with_rag.sources`.

Примечание о shared corpus: Day 21 собирает `README*.md` и из будущих day-папок. Поэтому после добавления Day 22 старый `knowledge.db` остаётся пригодным для retrieval, но `day-21-document-indexing/main.py verify` может потребовать rebuild из-за изменившегося corpus revision. Если хотите строгий `verify`, просто пересоберите Day 21 индекс один раз после добавления нового дня.
