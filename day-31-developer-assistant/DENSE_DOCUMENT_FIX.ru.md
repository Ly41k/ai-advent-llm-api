# v0.3.2 — отдельный фрагмент о состоянии Ollama

Статус: corpus improvement candidate. Dense 10/10 ещё не подтверждён.
Полный комплект; требуется пересборка hybrid index.

## Что установлено по Mac v0.3.1

| Режим | Hit@5 | MRR |
|---|---:|---:|
| FTS | 10/10 | .90 |
| Dense vocabulary | 9/10 | .85 |
| Dense raw | 9/10 | .80 |
| Hybrid vocabulary | 10/10 | .85 |
| Hybrid raw | 10/10 | .95 |

Все negative controls: 2/2 пустых в каждой группе. 60 observations,
48 completed embedding calls, error=null, но quality_acceptance=failed.
Отчёт и неуспех сохранены: reports/verified/retrieval-paired-mac-v031-r2.json.

Для session-en ожидаемый chunk tooling.md имел rank 13 / cosine .493027
в vocabulary и rank 6 / .528144 в raw. Raw поднял источник и провёл его через
порог .5, но пяти более высоких результатов было достаточно для промаха hit@5.
Из одного отчёта нельзя доказать причину ранжирования всей embedding-модели.

## Изменение

tooling.md раньше объединял остановку day30, `/api/ps`, epochs, recovery и
model ownership в одном разделе. Теперь это отдельные структурные разделы.
Объяснение model residency/request completion стало отдельной цитируемой единицей
с точными line spans. Смысл опирается на прежнюю project policy и официальный
endpoint contract https://docs.ollama.com/api/ps (проверен 13 октября 2026).
API возвращает загруженные модели; требование не считать это idle witness —
политика проекта. Никаких обещаний универсального API proof checker.

Также устранено устаревшее утверждение architecture.md, будто task runtime
ещё отсутствует. Документ различает готовые worker/task contexts и будущие
независимые Qwen contexts. Evaluation questions, допустимые источники, keywords,
порог .5, candidate K=20, final K=5, RRF=60 и acceptance не менялись.
Raw остаётся проверяемым кандидатом; vocabulary доступен для сравнения.

Это изменение корпуса: historical v0.3.1 и rebuilt v0.3.2 имеют разные fingerprints.
Внутри v0.3.2 raw/vocabulary используют один и тот же новый индекс. Изменение
документов основано на открытом calibration case, не считается held-out результатом.
Дополнительные paraphrases также известны при разработке; полноценный held-out
golden evaluation остаётся этапом 7.

## Mac-проверка

Из корня repo, с существующим Python 3.13 venv:

```bash
unzip -o ~/Downloads/day31-stage4-v032.zip -d "$PWD"
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage4.py --output /tmp/day31-stage4-mac-v032.json
python day-31-developer-assistant/main.py index build --mode hybrid
python day-31-developer-assistant/main.py index verify
python day-31-developer-assistant/scripts/compare_project_retrieval.py --modes all --dense-query both --diagnostics --output /tmp/day31-retrieval-paired-mac-v032.json
```

102 tests ожидаются в full suite. Hybrid build использует bge-m3 и сохраняет
новую версию без удаления прежнего индекса. Число chunks и build calls может
измениться; новые размеры брать из отчёта, не обещать прежние 376.
Сравнение: 12 cases / 60 observations / 48 query embedding calls.
Qwen не вызывается. Day30/Revik/другие клиенты должны оставаться отключёнными
в выделенной подтверждённой сессии. Если процесс изменился, модели потребуют
явного models confirm; при uncertain/session-required см. RAG_MAC.ru.md.
Автоматических повторов/restart нет. Existing output не перезаписывается.

Приёмка прежняя: все raw positive hits, все пустые negative controls, raw MRR
не хуже vocabulary. Если источники найдены 10/10, но MRR raw ниже vocabulary,
отчёт всё равно сохраняет failed: выбор лучшего query policy потребует отдельного
решения по реальным measurements, а не удаления сравнения из критериев.

Дополнительный RU/EN контроль после основной проверки:

```bash
python day-31-developer-assistant/scripts/compare_project_retrieval.py --modes all --dense-query both --diagnostics --cases day-31-developer-assistant/evaluation/retrieval_paraphrases.json --output /tmp/day31-retrieval-paraphrases-mac-v032.json
```

Нужны JSON stage4, основного comparison и paraphrases; build/verify output также
показывает новую corpus/index identity. Не считать старый Mac report проверкой
новой версии. Исправление не объявляется принятым до реального запуска.
