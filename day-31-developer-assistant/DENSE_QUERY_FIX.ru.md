# v0.3.1 — точный embedding запроса и проверка dense 9/10

Статус: изменение реализации подготовлено; результат 10/10 на реальном bge-m3
ещё не подтверждён. Архив является полным комплектом, а не патчем.

## Проблема и изменение

Mac calibration v0.2.3: dense пропускает `session-en` — «Why is Ollama API /ps
not an idle witness?». FTS находит tooling.md первым, hybrid — вторым.
Прежний dense embedding получал вопрос плюс `Search vocabulary` и лексические
слова для FTS. Причина промаха пока не доказана: сохранённый отчёт не содержал
полного ранга и cosine-score ожидаемого фрагмента.

В v0.3.1 dense по умолчанию получает исходный вопрос без лексического дополнения.
FTS сохраняет прежнее расширение. `--dense-query vocabulary` точно воспроизводит
старую строку embedding. Один query embedding на search, без скрытых повторов,
FTS fallback или смешивания режимов. Порог .5, K=20/5 и RRF k=60 сохранены.
Изменены только query policy, диагностика и evaluation; corpus, spans, vectors,
index format и model identity не меняются. Пересборка прежнего hybrid index
не требуется, если `index verify` подтверждает актуальность документов.

`--diagnostics` показывает первые 100 eligible dense чанков до порога:
rank/cosine/above_threshold/in_candidates. Это не дополнительные evidence.
Namespace и heading filter применяются до диагностики. Evaluation отдельно
сопоставляет готовые ранги с ожидаемыми source/keywords; эти labels не входят
в embedding или ranking. Отсутствие совпадения в окне 100 не означает, что
его вообще нет в индексе; отчёт указывает truncation.

## Проверка на Mac

Из корня репозитория, в существующем Python 3.13 окружении:

```bash
unzip -o ~/Downloads/day31-stage4-v031.zip -d "$PWD"
python day-31-developer-assistant/main.py --version
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage4.py --output /tmp/day31-stage4-mac-v031.json
python day-31-developer-assistant/main.py index verify
python day-31-developer-assistant/scripts/compare_project_retrieval.py --modes all --dense-query both --diagnostics --output /tmp/day31-retrieval-paired-mac-v031.json
```

Expected version: 0.3.1; полный suite содержит 102 теста. Для model calls нужна
прежняя выделенная подтверждённая Ollama session; day30/Revik/другие клиенты
должны оставаться отключёнными. Если session/epoch изменились — использовать
prepare → operator restart → confirm из RAG_MAC.ru.md. Автоматического restart
или retry нет. Существующий report не перезаписывается: выбрать новое имя.

Сравнение: 12 прежних cases × FTS + dense(vocabulary/raw) + hybrid(vocabulary/raw)
= 60 observations и 48 последовательных query embedding calls. Qwen не вызывается.
Исторический baseline сохранён; новая пара сравнивается на одном текущем индексе.

Приёмка `quality_acceptance.status=passed`: все positive source/keyword hits
FTS/dense raw/hybrid raw успешны, все negative controls пусты в обоих вариантах,
MRR raw не хуже vocabulary. `completed` означает завершение эксперимента,
а не качество 10/10. Quality failure сохраняется и даёт exit code 3; техническая
ошибка даёт 2. Неполный paired report не принимается. Отправить оба JSON.

После основного сравнения проверить RU/EN-перефразировки:

```bash
python day-31-developer-assistant/scripts/compare_project_retrieval.py --modes all --dense-query both --diagnostics --cases day-31-developer-assistant/evaluation/retrieval_paraphrases.json --output /tmp/day31-retrieval-paraphrases-mac-v031.json
```

Это 4 positive probes и 2 прежних negative controls, ещё 24 embedding calls.
Набор составлен при разработке изменения и не является held-out тестом.
Провалы сохраняются. Raw policy остаётся кандидатом до Mac-проверки: нельзя
объявлять качество улучшенным только по synthetic unit tests.

## Откат query policy

Для отдельного поиска старый режим доступен без отката индекса:

```bash
python day-31-developer-assistant/main.py search "Why is Ollama API /ps not an idle witness?" --mode dense --dense-query vocabulary --diagnostics
```

Проектные документы намеренно не менялись в этой версии, чтобы сравнить query
policy на прежнем корпусе. Известное устаревшее описание runtime в architecture.md
нужно обновить перед этапом 5 и затем явно пересобрать индекс. Полное задание
дня 31 ещё не завершено; Qwen/pipeline/reliability/research — следующие работы.
