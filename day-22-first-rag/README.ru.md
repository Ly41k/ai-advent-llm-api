[English](README.md) | **Русский**

# День 22 — Первый RAG-запрос

День 22 переиспользует [SQLite-базу знаний Дня 21](../day-21-document-indexing/README.ru.md) и сравнивает два режима:

| Режим | Поток |
|---|---|
| `no-rag` | Исходный вопрос → LLM |
| `rag` | Вопрос → embedding запроса → поиск чанков → вопрос + найденный контекст → LLM |

В обоих режимах `Day22RAGAgent` использует одну generation-модель. Ветка без RAG не вызывает поиск; RAG использует `retrieve()` и `answer_question()` Дня 21. Если общий helper распознал отказ, он повторяет генерацию один раз по лучшему фрагменту. Поэтому RAG может сделать два generation-вызова. Промпты также различаются по смыслу режимов: сравнение не обещает одинаковый prompt или одинаковое число вызовов.

## Подготовка и общий индекс

Команды выполняются из корня проекта, Python 3.13, активированное виртуальное окружение. Базовый флоу не требует новых Python-пакетов или ключа Groq. Запустите Ollama и загрузите модели:

```bash
source .venv/bin/activate
ollama pull bge-m3
ollama pull llama3.2
python day-22-first-rag/test_day22.py -v
```

Если `.venv` отсутствует, выполните [корневую инструкцию установки](../README.ru.md#требования-и-установка). Если приложение Ollama уже обслуживает локальный API, отдельный `ollama serve` не нужен.

Если индекс отсутствует или устарел, постройте его и проверьте:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

База по умолчанию — `day-21-document-indexing/knowledge.db`. В корпус входят корневые README, README уроков 1–20 и Python-файлы дней 16–20 без `test_*`. README уроков начиная с Дня 21 и отчёты исключены. Корневые README всё равно индексируются: их изменения меняют корпус. Строгий `verify` сравнивает Git HEAD и отпечаток содержимого; после соответствующих изменений или нового коммита пересоберите индекс в окончательной версии checkout. RAG CLI сам не выполняет эту полную проверку актуальности.

## Запуск двух режимов

```bash
python day-22-first-rag/main.py questions

python day-22-first-rag/main.py ask \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --mode no-rag

python day-22-first-rag/main.py ask \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --mode rag

python day-22-first-rag/main.py compare \
  "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
```

`compare` возвращает `without_rag` и `with_rag` для одного исходного вопроса. У RAG сохраняются chunk ID, путь файла, секция, диапазон строк и raw cosine. Без RAG найденных источников нет. В отличие от Дня 23, отчёт Дня 22 не экспортирует полный контекст и тексты чанков; для подробной проверки откройте указанные строки исходника или используйте `review` Дня 21.

Для другой модели генерации или стратегии индекса глобальные параметры ставятся **до** подкоманды:

```bash
ollama pull qwen2.5:7b
python day-22-first-rag/main.py \
  --model bge-m3 --answer-model qwen2.5:7b --strategy fixed --top-k 5 \
  compare "На 18 дне кто выполняет фоновые задачи?"
```

Defaults: `--model bge-m3`, `--answer-model llama3.2`, `--strategy structural`, `--top-k 5`, `--url http://127.0.0.1:11434`. Через `--db` можно выбрать другую общую базу. Дополнительный `--rerank-model` использует cross-encoder Дня 21 и требует `sentence-transformers`.

`questions` работает без индекса и Ollama. Для остальных команд текущий CLI проверяет наличие базы и стратегии даже при `ask --mode no-rag`; сам метод агента без RAG не обращается к retrieval. При поиске несовпадение embedding-модели с моделью индекса вызывает ошибку. Смена только `--answer-model` не требует переиндексации.

## Оценка на десяти вопросах

```bash
python day-22-first-rag/main.py evaluate
```

В `questions.json` ровно десять контрольных вопросов. Каждый содержит `question`, `expectation`, `expected_terms`, `expected_sources`. `evaluate` получает два ответа на каждый вопрос и записывает игнорируемый файл `evaluation_results.json`.

В отчёте — оба ответа, provenance источников RAG, совпадения ожидаемых терминов, попадание источников, разница term coverage для каждого вопроса и общая A/B-сводка. Полная revision индекса и настройки в отчёте не фиксируются: сохраняйте команду запуска и результат проверки индекса при сравнении экспериментов.

Для совместимого пользовательского набора и другого файла:

```bash
python day-22-first-rag/main.py \
  --answer-model qwen2.5:7b --strategy fixed --top-k 5 \
  evaluate --questions day-22-first-rag/questions.json \
  --output day-22-first-rag/evaluation_qwen_results.json
```

Пользовательский набор также должен содержать ровно десять полных записей. Покрытие терминов — поиск строковых совпадений, а не оценка смысловой правильности. Попадание документа не гарантирует, что выбранный фрагмент отвечает на вопрос. Просматривайте ответы по ожиданиям и содержимому источников.

## Проверка и переход к Дню 23

Шесть локальных тестов работают без реальной модели. Проверяются разделение режимов, вопрос → поиск → контекст → генерация, парное сравнение, контракт десяти вопросов и сохранение оценки.

Для видео покажите `verify`, `test_day22.py -v`, `questions`, один `compare`, затем `evaluate` и его `summary`/`details`.

[День 23](../day-23-reranking-filtering/README.ru.md) добавляет независимые rewrite/filter-режимы, candidate/final top-K, включительный raw cosine-порог, calibration/evaluation и полные traces контекста. Он использует единый prompt ответа и не вызывает повтор генерации по одному чанку Дня 21.

[Чек-лист задания](ASSIGNMENT_CHECKLIST.ru.md) · [Инструкция проверки](VERIFICATION.ru.md)
