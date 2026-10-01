[English](README.md) | **Русский**

# День 23 — Фильтрация релевантности и query rewrite

Продолжаем [RAG Дня 22](../day-22-first-rag/README.ru.md) на [общем SQLite-индексе Дня 21](../day-21-document-indexing/README.ru.md). Второй этап после поиска — **включительный фильтр по исходной cosine similarity**. Это разрешённая заданием альтернатива reranker; дополнительная модель cross-encoder или новый Python-пакет не нужны.

Исходный вопрос → необязательный rewrite поискового запроса → embedding → top-K кандидатов → необязательный cosine-фильтр → итоговый top-K → исходный вопрос + выбранный контекст → LLM.

| Режим | Rewrite | Фильтр |
|---|---|---|
| `baseline` | Нет | Нет |
| `filter` | Нет | Да |
| `rewrite` | Да | Нет |
| `rewrite_filter` | Да | Да |

`baseline` также использует RAG: контекст ищется, но без rewrite и фильтра. Это не режим «без RAG» из Дня 22.

## Настройки и правила отбора

| Глобальный параметр | Кодовый default | Назначение |
|---|---|---|
| `--model` | `bge-m3` | Embedding запроса; модель должна совпадать с индексом |
| `--answer-model` | `llama3.2` | Генерация ответа и модельного rewrite |
| `--strategy` | `structural` | Индекс `fixed` или `structural` |
| `--candidate-k` | `20` | Максимум кандидатов поиска |
| `--final-k` | `5` | Максимум чанков в контексте |
| `--min-similarity` | `0.35` | Включительный порог raw cosine |
| `--rewrite-method` | `heuristic` | `heuristic` или `llm` |
| `--db` | `knowledge.db` Дня 21 | Общая локальная база |
| `--url` | `http://127.0.0.1:11434` | Сервис Ollama |

Требуются целые `candidate_k >= final_k >= 1` и конечный порог в `[-1, 1]`. Фильтр использует `Hit.score`, а не отображаемое в Дне 21 `(cosine+1)/2`. Similarity не является вероятностью релевантности или правильного ответа.

Кандидаты сортируются по cosine; при равенстве — по chunk ID. В фильтруемых режимах проходят значения **больше или равные** порогу, затем выбирается не более final-K. Может остаться меньше K или ни одного источника. Отброшенные кандидаты не восстанавливаются. Пустой выбранный контекст даёт постоянный отказ, пустые источники/контекст и не вызывает генерацию ответа. `abstained` означает пустой retrieval, а не любой текстовый отказ модели.

## Подготовка

Python 3.13, активированное окружение, команды из корня проекта. Если `.venv` отсутствует, выполните [корневую инструкцию](../README.ru.md#требования-и-установка). Базовый код использует стандартную библиотеку Python и локальный Ollama; ключ Groq не нужен.

```bash
source .venv/bin/activate
ollama pull bge-m3
ollama pull llama3.2
# Модель из описанного исследовательского профиля:
ollama pull qwen2.5:7b
python day-23-reranking-filtering/test_day23.py -v
```

Запустите Ollama, если приложение/сервис ещё не обслуживает API. При отсутствующем или устаревшем индексе:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

Корпус: корневые README, README уроков 1–20 и Python-файлы дней 16–20 без `test_*`. README уроков 21–23 и отчёты исключены, но изменение корневых README меняет корпус. Strict revision также включает Git HEAD; выполняйте build/verify в окончательной версии checkout. День 23 проверяет совместимость модели, размерности и векторов, но не сверяет полный source revision при каждом запросе. Индекс и модели не хранятся в Git.

## Полный флоу

Глобальные параметры ставятся **до** подкоманды. Этот пример явно задаёт исторический исследовательский профиль fixed/20/5/0.50/Qwen, а не defaults:

```bash
python day-23-reranking-filtering/main.py \
  --model bge-m3 --answer-model qwen2.5:7b \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --min-similarity 0.50 --rewrite-method heuristic \
  compare "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --retrieval-only \
  --output day-23-reranking-filtering/reports/check/compare_20_5.json
```

Уберите `--retrieval-only`, чтобы получить четыре ответа. В JSON проверьте `rewrite`, `settings`, `candidate_count`, `eligible_count`, `selected_count`, `candidates`, `sources`, `context`, `answer`. Без фильтра `eligible_count` означает всех найденных кандидатов. Для каждого записано решение: `selected`, `below_threshold`, `final_k_limit`. Выбранные источники содержат текст и provenance; диагностика кандидатов содержит raw `cosine`.

Парные режимы получают одинаковых кандидатов: baseline/filter — для исходного запроса, rewrite/rewrite_filter — для расширенного. `compare` делает rewrite один раз и ищет один раз для каждого различающегося запроса. Во всех режимах один prompt ответа, провайдер и temperature=0. Ответ формируется на исходный вопрос. Дополнительный cross-encoder и повтор ответа по лучшему чанку Дня 21 не используются.

Один режим и другая конфигурация K:

```bash
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 12 --final-k 3 --min-similarity 0.50 \
  ask "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --mode rewrite_filter
```

`search` принимает тот же вопрос/режим и пропускает финальный ответ. Для демонстрации полного отсечения на этом вопросе задайте `--min-similarity 1.0`: ожидаются `selected_count: 0`, `abstained: true`, `sources: []`, `context: ""`. Это диагностический порог, а не рабочая рекомендация. Для другого индекса задайте `--strategy structural`.

## Query rewrite

`heuristic` дополняет вопрос общим словарём поисковой лексики, сохраняя исходную строку, номера дней, идентификаторы и отрицания. Он не читает ожидаемые ответы или разметку источников. Если словарь не сработал, запрос не меняется.

`llm` добавляет поисковую формулировку выбранной answer-модели:

```bash
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 20 --final-k 5 --min-similarity 0.50 \
  --rewrite-method llm \
  search "На 18 дне кто выполняет фоновые джобы по расписанию?" \
  --mode rewrite_filter \
  --output day-23-reranking-filtering/reports/check/llm_rewrite.json
```

Проверьте `method: llm`, `reason: llm_expansion`. При пустом или слишком длинном ответе сохраняется исходный запрос, причина — `invalid_output_fallback`; ошибки соединения/модели передаются наружу. Сохранение исходной строки не гарантирует точность добавленного моделью текста: его нужно просмотреть. `--retrieval-only` и `search` отключают финальный ответ, но **LLM rewrite всё равно вызывает модель**. Для полностью отсутствующей генерации используйте `heuristic`.

## Калибровка и оценка

В `questions.json` 20 вопросов: 10 контролей Дня 22, шесть разговорных и четыре вне корпуса. Восемь — calibration (шесть положительных/два отрицательных), двенадцать — evaluation (десять положительных/два отрицательных). Разметка используется оценкой и калибровкой, а не поиском или rewrite.

```bash
python day-23-reranking-filtering/main.py \
  --strategy fixed --candidate-k 20 --final-k 5 \
  --rewrite-method heuristic \
  calibrate --thresholds 0.15 0.25 0.35 0.45 0.50 0.55 0.65 \
  --output day-23-reranking-filtering/reports/check/calibrate.json
```

Результат подбора — `selected_threshold`; `settings.min_similarity` показывает исходную настройку. Полный перебор находится в файловом `sweep`, который не печатается в краткой консольной сводке. Калибровка кеширует кандидатов и не генерирует ответы; при LLM rewrite вызовы для переписывания запросов всё же выполняются.

Сначала сохраняются source-hit и positive-empty rates режима без фильтра `rewrite` на calibration, затем выбирается лучший баланс positive-source-hit/negative-empty-context для `rewrite_filter`. При равенстве — precision, затем меньший порог. Правило оптимизирует комбинированный режим, а не каждый режим отдельно. Если все пороги теряют evidence, добавьте меньшие значения. Evaluation-разметка не участвует в выборе.

```bash
# Замените 0.55 на selected_threshold своей калибровки.
python day-23-reranking-filtering/main.py \
  --answer-model qwen2.5:7b --strategy fixed \
  --candidate-k 20 --final-k 5 --min-similarity 0.55 \
  --rewrite-method heuristic \
  evaluate --split evaluation \
  --output day-23-reranking-filtering/reports/check/evaluate.json
```

Запускаются 12 вопросов × четыре режима. JSON сохраняет настройки, revision/модель индекса, запросы, решения по всем кандидатам, тексты выбранных чанков, полный контекст, ответы, диагностику, дельты и пустые поля `human_review`. Рядом создаётся `.md`. Добавьте `--retrieval-only` для проверки без ответов. `--split all` смешивает calibration/evaluation и не является независимой оценкой. После смены embedding-модели, корпуса, стратегии, K или rewrite-метода выполните новую калибровку.

Метрики основаны на размеченных **документах**: source hit, source precision, MRR, пустые отрицательные/положительные результаты, размер контекста, покрытие терминов. Разметка может не перечислять другие подходящие документы. `negative_abstention_rate` — пустой контекст, а не смысловой отказ; term coverage — не точность ответа. Вручную проверяйте релевантность фрагментов, подтверждение утверждений, правильность и ссылки.

## Реальные результаты и публикация отчётов

[Английская сводка](LIVE_VERIFICATION.md) и [подробный русский обзор](LIVE_VERIFICATION.ru.md) описывают пользовательские Ollama-прогоны 30 сентября — 1 октября 2026 года. Они относятся к прежнему индексу (`7e5cc6d6...@350a65b38804aaa6`); после обновления root README число чанков и scores могут измениться.

Исторический fixed/20/5/0.50, `bge-m3` + `qwen2.5:7b`, heuristic, 12 evaluation-вопросов:

| Метрика | baseline | filter | rewrite | rewrite_filter |
|---|---:|---:|---:|---:|
| Нужный документ на 10 положительных вопросах | 10/10 | 10/10 | 10/10 | 10/10 |
| Средняя точность размеченных источников | 28.0% | 30.3% | 30.0% | 37.3% |
| MRR | 0.791667 | 0.791667 | 0.766667 | 0.766667 |
| Пустой контекст на положительных вопросах | 0/10 | 0/10 | 0/10 | 0/10 |
| Пустой контекст на отрицательных вопросах | 0/2 | 1/2 | 0/2 | 1/2 |
| Средний контекст, слов на всех 12 вопросах | 2007.8 | 1592.8 | 1851.8 | 1393.3 |

Комбинированный режим против baseline: precision +9.3 процентного пункта, контекст −30.6%, попадание документов сохранено. Rewrite снизил MRR и term coverage; ошибки генерации остались, в том числе про VPS и проверку отчёта Дня 20. Найденный документ не равен правильному ответу. Калибровка выбрала 0.55, но этот порог потерял полезный контекст на evaluation. **0.50 исследовали после просмотра evaluation**: это не подтверждение на новом независимом holdout и не универсально лучший порог.

Уточнение для коммита `05d23cd9`: в `reports/live/` есть [provenance](reports/live/PROVENANCE.json) и [обзор ассистентом](reports/live/assistant_review_050.json), но исходные live-файлы `*_results.json`/`.md`, упомянутые в старой сводке, отсутствуют. Хеши и обзор не заменяют raw traces или независимую ручную оценку. Часть утверждений прежних verification-документов относится к архиву или более раннему этапу проверки, а не к содержимому этого Git checkout.

Промежуточные результаты сохраняйте в игнорируемых `reports/check/`, `reports/video/`. Для итоговых доказательств используйте имена `reports/live/calibrate.json`, `reports/live/evaluate_050.json` и `.md`: текущие правила `*_results.json`/`*_results.md` действуют и во вложенных папках. Перед коммитом проверьте `git status`. Команды воспроизведения создают новые отчёты, а не исторические байты.

## Offline-демонстрация и тесты

```bash
python day-23-reranking-filtering/offline_demo.py
python day-21-document-indexing/test_day21.py -v
python day-22-first-rag/test_day22.py -v
python day-23-reranking-filtering/test_day23.py -v
```

`offline_demo.py` строит временный реальный SQLite-индекс по текущему корпусу через лексический TF-IDF hash embedder, калибрует и записывает `reports/offline_*`. Он не генерирует и не имитирует ответы LLM и не измеряет качество `bge-m3`/Qwen. Его порог нельзя переносить на Ollama embeddings; повторный запуск может изменить отслеживаемые offline-примеры.

В проверенной версии 7 + 6 + 21 = 34 теста. День 23 проверяет включительный raw cosine до final-K, общие candidate pools, пустой контекст без генерации, стабильные ties, rewrite/fallback, разделение calibration/evaluation и CLI → локальную HTTP-заглушку Ollama → SQLite → контекст → JSON/Markdown. Это проверка функциональности, а не качества реальных моделей.

Для видео: verify индекса → четыре retrieval-режима → смена 20/5 на 12/3 → ответы и подтверждение источниками → LLM rewrite → пустой контекст → отчёты calibration/evaluation → structural-индекс → тесты.

[Чек-лист задания](ASSIGNMENT_CHECKLIST.ru.md) · [Техническая проверка](VERIFICATION.ru.md)
