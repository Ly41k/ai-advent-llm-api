# v0.3.3 — выбор query policy по измерениям

Dense 10/10 подтверждён на Mac в v0.3.2. Все пять вариантов поиска достигли
10/10 source/keyword hit@5; во всех случаях negative controls 2/2 пустых.
102/102 tests v0.3.2 прошли; Document/Git/Verification runtime completed,
model generation отсутствовала. Corpus 40 docs / 378 chunks.

| Выбранный режим | Query policy | Hit@5 | MRR |
|---|---|---:|---:|
| FTS | Прежнее лексическое расширение | 10/10 | .90 |
| Dense | vocabulary | 10/10 | .95 |
| Hybrid | raw | 10/10 | .95 |

v0.3.2 quality_acceptance=failed относится к uniform-raw гипотезе: dense raw
имеет MRR .90, меньше vocabulary .95. Hybrid наоборот лучше с raw: .95 против .90.
Необязательно использовать одинаковый query input для разных retrieval modes.
Исходный отчёт сохраняется неизменным. Порог/K, источники и вопросы не меняются.

`--dense-query auto` теперь default. Это фиксированная таблица defaults по mode,
не LLM routing и не подбор по конкретному вопросу/expected answer. Explicit raw
и vocabulary по-прежнему работают. Один embedding call на поиск. FTS не вызывает
модель. В settings указаны requested/effective policy и version. Нет скрытого
FTS fallback в dense или дополнительного candidate channel.

В paired отчётах quality_acceptance относится к этой выбранной таблице:
все selected positive hits, все пустые negative controls и MRR выбранного
варианта не ниже альтернативного. Uniform raw оценивается отдельно в
raw_query_acceptance с прежними условиями. Не считать failed raw гипотезу passed.
Неполное сравнение не принимается. Failure всё ещё даёт exit code 3.

Это selection на открытом calibration set. Не переносить 10/10 на произвольные
запросы, semantic answer quality или held-out golden. Дополнительные paraphrases
ещё не запускались. Qwen generation и этап 5 ещё не реализованы.

## Mac-проверка

Из корня repo, в прежнем Python 3.13 venv/выделенной Ollama session:

```bash
unzip -o ~/Downloads/day31-stage4-v033.zip -d "$PWD"
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage4.py --output /tmp/day31-stage4-mac-v033.json
python day-31-developer-assistant/main.py index verify
python day-31-developer-assistant/scripts/compare_project_retrieval.py --modes all --dense-query both --diagnostics --cases day-31-developer-assistant/evaluation/retrieval_paraphrases.json --output /tmp/day31-retrieval-paraphrases-mac-v033.json
```

Full suite: 104 tests. Локально прошли 75 Foundation/RAG tests на Python 3.12;
новый MCP/runtime Mac suite пока не запускался. Индекс после v0.3.2 остаётся
актуальным: project/docs и embedding identity не менялись. Если verify выявляет
другое изменение документов — не обходить stale проверку.
Paraphrases: 4 RU/EN positive probes + 2 negative controls, 30 observations и
24 query embedding calls. Это developer-known regression probes, не held-out.

Для повторения всего основного comparison (не требуется только ради selection):

```bash
python day-31-developer-assistant/scripts/compare_project_retrieval.py --modes all --dense-query both --diagnostics --output /tmp/day31-retrieval-paired-mac-v033.json
```

Повторный основной comparison: 60 observations / 48 embedding calls.
Models confirm требуется при изменении epoch; uncertain/session-required
восстанавливать по RAG_MAC.ru.md. Existing output нельзя перезаписывать.

Report selection-v033-from-mac-v032.json заново вычисляет summary из 60 rows
присланного Mac report и применяет выбранные criteria. Он помечен retrospective,
не является новым запуском bge-m3 и не подменяет исходные JSON.
После regression проверок продолжаем этап 5: Router/Chain/Fan-Out, Qwen, RU/EN
ответы, разные LLM contexts и проверка после финального синтеза.
