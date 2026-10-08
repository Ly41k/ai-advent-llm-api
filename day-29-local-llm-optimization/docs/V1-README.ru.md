**Русский** | [English](README.md)

# День 29 — оптимизация локальной LLM / V1

Первая версия эксперимента для локального RAG Бублика: Qwen2.5 14B через Ollama, индекс Дня 21 и retrieval Дня 23/28. Сравниваются параметры, prompt и варианты квантования. Облачный провайдер не создаётся, ключи не читаются, cloud fallback отсутствует.

**V1 — готовая реализация эксперимента, а не уже измеренное улучшение модели.** Живые качество, скорость и ресурсы нужно измерить на Mac. Профили `candidate-*` — кандидаты; они не объявлены победителями заранее. Обучения или fine-tuning весов здесь нет.

## Установка

Распакуй архив **в корень существующего репозитория** `ai-advent-llm-api`. Получится соседний каталог `day-29-local-llm-optimization/`. Архив не заменяет дни 21–28, root README, индекс или `.env` и не содержит модели. Основа проверена с коммитом `3d2e9616dc2fd857a918606f1cb371045ef48cd4`.

Команды ниже выполняются из корня репозитория, в твоём существующем venv:

```bash
source .venv/bin/activate
python -m pip install -r day-29-local-llm-optimization/requirements.txt
python -m unittest discover -s day-29-local-llm-optimization -p 'test_day29.py' -v
python day-29-local-llm-optimization/main.py doctor --profiles baseline
```

Нужны запущенная Ollama, скачанные `qwen2.5:14b` и `bge-m3`, существующий `day-21-document-indexing/knowledge.db`. Python 3.13 — окружение автора; offline-проверки V1 выполнены на Python 3.12. Если doctor сообщает об изменении корпуса или отсутствии индекса, выполни существующие команды Дня 21 `build`, затем `verify`. Добавление только Дня 29 не меняет индексируемый корпус.

## Сначала один вопрос ×3

Посмотри план — он делает **ноль HTTP/embedding/generation-вызовов**:

```bash
python day-29-local-llm-optimization/main.py plan \
  --profiles baseline --case base-07 --repeats 3
```

Затем собери исходные три ответа:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline --case base-07 --repeats 3 \
  --output day-29-local-llm-optimization/reports/check/baseline-worker-v1.json
```

`base-07`: Which process periodically collects GitHub repository snapshots into SQLite on Day 18?

JSON содержит исходный вывод модели, источники, цитаты, параметры и замеры. Рядом создаётся Markdown с ответами и полями для ручного ревью. При ошибке отчёт всё равно сохраняется. После трёх завершённых валидных ответов повтор этой команды **не задаёт вопрос модели снова**. Не удаляй каталог `cache/`.

Добавь кандидата на том же вопросе — baseline будет переиспользован:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline candidate-q4 --case base-07 --repeats 3 \
  --output day-29-local-llm-optimization/reports/check/worker-pair-v1.json
```

Это три новых ответа кандидата, если baseline уже завершён и identity совпадает. Прогрев и подсчёт входных токенов — дополнительные короткие служебные генерации, отдельно показанные в отчёте. Они не выдаются за ответы или качество.

## Главное правило: не повторять полученные ответы

По умолчанию cache: `day-29-local-llm-optimization/cache/experiments.sqlite3`. Каждая попытка записывается отдельной SQLite-транзакцией; JSON/Markdown обновляются после наблюдения. Повтор команды продолжает недостающие слоты 1/2/3. `Ctrl+C` сохраняет уже завершённые результаты. Для технической ошибки следующая команда повторяет только неготовые слоты; скрытых автоматических повторов HTTP нет.

Для переиспользования должны совпадать:

- вопрос и оценочная рубрика;
- модель, digest её весов и модельный chat template;
- temperature, лимит ответа, окно контекста и task prompt;
- найденные источники, цитаты, индекс, embedding-модель;
- runtime-код, версия Ollama, Python, машина и режим измерений;
- серия и seed schedule.

**Три валидных, но слабых по смыслу ответа тоже сохраняются и не запускаются бесконечно до PASS.** Они остаются FAIL в оценке. Повторять ответы после изменения параметров или prompt нужно для нового сравнения: старые ответы не представляются как результат новых настроек. Невалидный JSON, обрыв ответа и неподтверждённая локальная генерация не считаются готовым ответом.

`--repeats 1` затем `--repeats 3` добавляет только недостающие два слота. При полном кеше нет новых ответов, token probes или warmups; live-команда всё ещё проверяет готовность моделей и индекса. `plan` использует последнюю сохранённую среду и помечает оценку переиспользования как предварительную: установка новой модели или изменение индекса проверяются только live-командой.

Для ограниченной порции работы:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline candidate-q4 --split calibration \
  --max-new-observations 3 \
  --output day-29-local-llm-optimization/reports/check/calibration-v1.json
```

Повторяй ту же команду для следующих недостающих наблюдений. Лимит относится к новым наблюдениям, включая отказы и ошибки; служебные probes/warmups учтены отдельно. Для минимального первого запуска выбирай один вопрос: подготовка общего retrieval производится для всего выбранного набора до генераций.

Перенос результатов из предыдущего **Day 29** JSON в новый cache:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline candidate-q4 --case base-07 \
  --retry-from day-29-local-llm-optimization/reports/check/baseline-worker-v1.json \
  --output day-29-local-llm-optimization/reports/check/imported-pair-v1.json
```

Обычно `--retry-from` не нужен: автоматический SQLite-cache уже хранит результат. Импорт проверяет checksum, исходный JSON модели, доказательства, контракт и identity. Чужой профиль не переиспользуется. Day 28 V2/V11/V16 не импортируются в Day 29 baseline: у них другой контракт измерения и отсутствует нужная provenance ресурсов. Исторические файлы остаются нетронутыми.

Для намеренно свежего замера существует `--series fresh-02`. Он создаёт новую identity и запускает новые ответы. Не меняй series при обычном продолжении. Checksum подтверждает внутреннюю согласованность файла, а не подлинность внешней генерации.

## Профили и последовательные эксперименты

Параметры задаются в `profiles.json` и реально передаются в Ollama `options`. `max_tokens` означает Ollama `num_predict`, `num_ctx` — окно входа и генерации. Параметры локальной генерации уже были настроены на Дне 28, поэтому baseline намеренно сохраняет temperature=0.

| Профиль | Temperature | Max tokens | Context | Prompt | Модель |
|---|---:|---:|---:|---|---|
| baseline | 0 | 2048 | 16384 | Day 28 baseline | Qwen 14B |
| temperature-01 | 0.1 | 2048 | 16384 | baseline | Qwen 14B |
| temperature-02 | 0.2 | 2048 | 16384 | baseline | Qwen 14B |
| tokens-1024 | 0 | 1024 | 16384 | baseline | Qwen 14B |
| tokens-512 | 0 | 512 | 16384 | baseline | Qwen 14B |
| context-8192 | 0 | 2048 | 8192 | baseline | Qwen 14B |
| prompt-compact | 0 | 2048 | 16384 | компактный | Qwen 14B |
| candidate-q4 | 0 | 1024 | 8192 | компактный | Qwen 14B, текущий тег |
| candidate-q5 | 0 | 1024 | 8192 | компактный | Qwen 14B Instruct Q5_K_M |

Уменьшение лимита не гарантирует ускорения, если ответы и раньше завершались раньше лимита. Уменьшение контекста не должно выкидывать доказательства. Три повтора используют seeds 42/43/44 по умолчанию; у сравниваемых профилей один seed на соответствующий повтор. Это контролируемый эксперимент, а не гарантия дословной детерминированности.

Начни с calibration-вопросов, добавляя по одному изменению:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline temperature-01 temperature-02 --split calibration
python day-29-local-llm-optimization/main.py run \
  --profiles baseline tokens-1024 tokens-512 --split calibration
python day-29-local-llm-optimization/main.py run \
  --profiles baseline context-8192 prompt-compact --split calibration
```

Успешно завершённые baseline-наблюдения из первой команды сохраняются для следующих. Есть восемь calibration-вопросов (шесть фактических + два отрицательных контроля) и двенадцать evaluation. При полном новом calibration для трёх профилей: 72 наблюдения; ответов модели может быть меньше из-за пустого retrieval. Выбирай `--case` и `--max-new-observations`, если не хочешь запускать весь набор сразу.

После сравнения выбери параметры по качеству/скорости/памяти и создай отдельный профиль `selected` в JSON с теми же пятью полями. Вынеси выигравшие значения явно. Затем оцени baseline и selected на evaluation-вопросах без дальнейшей настройки по ним:

```bash
python day-29-local-llm-optimization/main.py run \
  --profiles baseline selected --split evaluation --repeats 3
```

Это 72 наблюдения для двух профилей. Вся смешанная выборка: `--split all`, 20 ×3 ×2 =120 наблюдений. Вопросы курса уже известны, поэтому evaluation — отложенная часть этого эксперимента, не полностью независимый unseen benchmark.

## Квантование на Mac M1 / 32 GB

Текущий уровень подтверждает doctor через `/api/show`; тег сам по себе не доказывает Q4. В истории Дня 26 он был Q4_K_M. Чтобы честно сравнить квантование, проверь, что Q4 и Q5 — Qwen2.5 14B Instruct с одинаковым назначением/размером, и что детали действительно показывают Q4_K_M и Q5_K_M.

Скачивание требуется только один раз:

```bash
ollama pull qwen2.5:14b-instruct-q5_K_M
python day-29-local-llm-optimization/main.py doctor --profiles candidate-q4 candidate-q5
python day-29-local-llm-optimization/main.py run \
  --profiles candidate-q4 candidate-q5 --case base-07 --repeats 3 \
  --output day-29-local-llm-optimization/reports/check/quant-worker-v1.json
```

Размер Q5 в каталоге Ollama около 11 GB — это не весь расход памяти. Профили запускаются последовательно; выбранная другая квантованная модель выгружается перед блоком. После общего retrieval выгружается bge-m3, чтобы её residency не меняла сравнение профилей. Остальные пользовательские модели автоматически не выгружаются. Перед измерениями закрой emulator/сборки и проверь Memory Pressure и swap. Q5 не обещает автоматического улучшения качества или скорости.

## Защита контекста и служебные вызовы

Для каждого точного prompt и digest модели выполняется **один кешируемый входной token probe**: тот же `/api/chat` и схема, но вывод ограничен одним токеном. Он не используется как ответ. Это нужно, чтобы знать число входных токенов до уменьшения окна; приблизительное число символов не подменяется точным токенизатором.

Проверка проводится с `--token-check-context 32768`: временно большее окно, которое тоже расходует память. V1 поддерживает Qwen2 byte-level BPE и ограничивает probe консервативной оценкой числа UTF-8 bytes плюс резерв. Также проверяется предел `/api/show`. Если проверяемый prompt не помещается даже в probe, выполнение останавливается; источники не обрезаются незаметно.

Кандидат допускается, если `input_tokens + max_tokens + 128 <= num_ctx`. После фактического ответа его входной token count должен совпасть с probe. Перед измеряемым блоком делается короткий warmup с целевым `num_ctx`; время загрузки и prompt-cache метрики сохраняются. Порядок профилей меняется между повторами. Probes выгружают модель, а служебные warmups отделены от измерений. Не делай вывод «весь кеш пустой» только из прогрева: сохраняй и анализируй `prompt_eval_cached_count`/`prompt_eval_duration`.

Если 8192 не хватает, профиль получает `context_overflow` без генерации ответа. Исправление — выбрать подходящее окно в новом профиле, а не скрыто выкинуть часть вопроса. Некоторые prompts могут потребовать большего окна и остаться за пределами V1 candidates.

## Как читать сравнение

- Качество: rubric terms/source/evidence, контракт JSON, точные IDs/цитаты; ручное ревью поддержки и полноты обязательно.
- Скорость: wall time получения и валидации ответа, Ollama input/output timings и decode tokens/s; отказы приложения не входят в скорость генерации.
- Ресурсы: sampled RSS/CPU процессов с Ollama в имени, отдельно Python RSS, доступная память и swap; `/api/ps` size/size_vram/context. GPU utilization недоступна и записывается как null.
- На Apple Silicon RAM/VRAM общие. Не складывай RSS и size_vram. Сумма RSS процессов может повторно учитывать общие mappings; sampled peak не является точным физическим пиком.
- Pipeline складывается из сохранённого общего retrieval и времени конкретной генерации: это reconstructed metric, не свежий end-to-end замер.
- Cached observations сохраняют оригинальные даты и замеры. Они не называются новыми измерениями. Новый отчёт явно показывает reused/new rows и дополнительные служебные вызовы.
- Ошибки входят в denominator полученных наблюдений; недостающие слоты показаны отдельно. Точная стабильность не доказывает правильность; semantic review оценивается вручную.

Проверка отчёта без модели:

```bash
python day-29-local-llm-optimization/main.py verify \
  day-29-local-llm-optimization/reports/check/worker-pair-v1.json
python day-29-local-llm-optimization/main.py summary \
  day-29-local-llm-optimization/reports/check/worker-pair-v1.json
```

`verify` проверяет внутреннюю структуру/контракт/bindings/checksum/summary; его exit 0 не означает семантический PASS. `run`: 0 — полный успешный по эвристике прогон либо добровольная пауза по лимиту; 1 — техническая/качественная проблема; 130 — Ctrl+C. Состояние `paused`/`completed` различается в JSON. Неудачные профили ожидаемы при оптимизации и не удаляются ради красивой сводки.

## Проверки поставки

Offline-тесты проверяют automatic resume, import, смену параметров/prompt/индекса/digest, raw-output validation, token guard, отказ без генерации, seed schedule, блокировку конкурирующих writers и отсутствие поддельных нулевых метрик. Транспорт scripted; это не доказательство скорости/качества Qwen.

Отобранные реальные JSON можно сохранить в `reports/accepted/`; промежуточные `reports/check/`, `reports/video/` и cache игнорируются Git. **Перед обновлением/переносом сохраняй cache и исходные JSON.** Смена runtime-кода может требовать новых наблюдений; старые файлы не удаляются и не переклеиваются к новому профилю.

Официальные справочники: [Ollama options/API](https://docs.ollama.com/api/chat), [метрики](https://docs.ollama.com/api/usage), [контекст](https://docs.ollama.com/context-length), [Q5_K_M](https://ollama.com/library/qwen2.5:14b-instruct-q5_K_M).
