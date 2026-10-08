**Русский** | [English](README.md)

# День 29 — оптимизация локальной LLM

Выбранный профиль предназначен для **коротких справочных RAG-ответов по
документации репозитория**: локальная Qwen2.5 14B Instruct Q4_K_M,
temperature=0, max_tokens=1024, num_ctx=8192 и фактический prompt V3 с примером
одного claim и null для ненужных слотов. Embeddings и retrieval локальны.
Дообучения весов нет; облачные модели не использовались.

Двенадцать ответов на четыре вопроса прошли ручную проверку. Каждый вопрос
повторён трижды. Процедура проверки VPS остаётся известным ограничением:
автоматические 15/15 V5 не подтверждают правильную привязку каждого факта.
V4/V5 сохранены как эксперименты, а не прошедшие ручное ревью процедуры.

Результат: [FINAL_REPORT.ru.md](FINAL_REPORT.ru.md). Конфигурация:
[SELECTED_PROFILE.json](SELECTED_PROFILE.json). Ручная оценка:
[manual-review.json](review/manual-review.json). Требования задания:
[ASSIGNMENT_CHECKLIST.ru.md](ASSIGNMENT_CHECKLIST.ru.md).

## Установка

Распакуй каталог в корень существующего ai-advent-llm-api. Другие дни,
корневые README и индекс не заменяются. Все ранее доставленные Python-файлы
измерителя и шаблонов сохранены побайтно. Кэш не удаляй. В архиве нет весов,
.env или локального SQLite-кэша; восемь исходных JSON-отчётов включены без изменений.
Для уже установленного окружения новые загрузки моделей и перестройка индекса
не требуются. Первоначальные подробные инструкции сохранены в
[V1 README](docs/V1-README.ru.md) как история эксперимента.

## Посмотреть отчёт без генерации

```bash
python day-29-local-llm-optimization/experiments/focused_v3/main.py verify \
  day-29-local-llm-optimization/reports/check/control-v5.json
```

Это offline-проверка целостности и контрактов. Она не заменяет ручное ревью.
Оригинальное optimization_verified=false не переписано; scoped-оценка хранится
отдельно в review/manual-review.json.

## Переиспользовать проверенные справочные ответы

```bash
python day-29-local-llm-optimization/experiments/focused_v3/main.py run \
  --profiles baseline focused-v3-q4 \
  --split all --case base-06 base-07 base-08 negative-03 --repeats 3 \
  --retry-from day-29-local-llm-optimization/reports/check/control-v5.json \
  --output day-29-local-llm-optimization/reports/check/factual-final.json
```

При прежних моделях, индексе, коде и окружении все 24 наблюдения берутся из
кэша или приложенного отчёта: нет новых ответов, token probes и прогревов.
Run всё ещё проверяет доступность Ollama и индекса. Plan вместо run делает
ноль HTTP-вызовов и даёт предварительную оценку. Изменённые вопросы или
условия требуют новых наблюдений; три готовых слабых ответа также сохраняются,
а не перезапрашиваются бесконечно до PASS.

Task-шаблон подключает именно experiments/focused_v3/main.py. Исходный main.py
использует исходные V1-шаблоны. Для новых вопросов качество ещё нужно проверять;
процедуры выходят за подтверждённую область выбранного профиля.
