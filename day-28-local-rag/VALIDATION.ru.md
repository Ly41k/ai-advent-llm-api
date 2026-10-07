# День 28 — повторная проверка требований

Актуальный итог после V11: [FINAL_REPORT.ru.md](FINAL_REPORT.ru.md), машинная перепроверка 12 живых отчётов — [final-audit-v11.json](reports/verified/final-audit-v11.json). Ниже сохранены исторические этапы проверки, включая их тогдашние pending. Последний local subset проходит 3/3; cloud retry не проходит строгую проверку из-за HTTP 429 и качества одного ответа.

Проверено на Python 3.12.14 в среде разработки; целевая версия проекта — Python 3.13. Дата: 2026-10-07. Предыдущие дни не изменены. Итог: **94 offline-теста прошли** (Day 28: 28, Day 21: 7, Day 23: 21, Day 26: 38). `compileall` и `git diff --check` также проверены.

## Аудит по заданию

| Пункт / нюанс | Что повторно проверено | Статус |
|---|---|---|
| Индекс Недели 6 | Day 21 схема/корпус; existing DB, read-only; нет создания пустой БД | Проверено кодом и тестами |
| Целостность индекса | Векторы обеих стратегий, fingerprint, document digests, тексты документов/чанков; полный текущий корпус проверен с тестовыми векторами | Проверено offline; тестовые векторы не являются bge-m3 |
| Совместимость embeddings | Имя модели, dimension, конечные значения, L2-нормализация; неправильный model/vector отклоняется | Проверено тестами |
| Retrieval локально | Loopback-only Ollama, proxy disabled, redirects rejected; поиск по SQLite в процессе Python | Проверено реализацией + регрессией HTTP Day 26 |
| Generation локально | Installed model / remote-host gate / cloud-tag gate, успешная генерация и `/api/ps` evidence нужны для флага | Проверено тестами; live pending |
| Одинаковые входы моделей | Один retrieval на пару; identical messages/hash; expected terms/sources не передаются; порядок чередуется | Проверено интеграционным тестом CLI |
| Облако необязательно | Нет ключа → явный skip; cloud failure не останавливает local, но сохраняется и делает compare неуспешным | Проверено тестами |
| Нет скрытого cloud fallback | Local-команды не читают cloud key и не создают Groq | Проверено тестом |
| Порог и контекст | Наследуется Day 23 inclusive raw cosine до final K; whole-chunk budget; no-context не вызывает LLM | Проверено регрессией Day 23 и тестами Day 28 |
| Качество | JSON, exact quote/ID, expected terms, expected cited sources, negative abstention; неполная/невалидная генерация проваливается | Проверено offline; реальная семантика pending |
| Скорость | Отдельные retrieval/generation/pipeline; median/p95; первый/последующие повторы; application refusals исключены | Формулы и учёт проверены; реальные значения pending |
| Стабильность | Повторы, failures, exact response identity; вопрос с проваленным повтором не считается стабильным | Проверено тестами; модельная стабильность pending |
| Сбой соединения | Connection reset / incomplete HTTP body превращаются в безопасную ProviderError без содержимого ответа | Проверено тестом |
| Прерывание / отчёты | Atomic replacement, partial observations, interrupted state, nonzero exit; нет fake success | Проверено тестами |
| Независимая перепроверка отчёта | Prompt pairing, actual/raw answer, цитаты/источники, пересчёт quality/summary, точный planned observation set | Проверено на корректном и повреждённых тестовых отчётах |
| Полностью локальная работа без интернета | Не требуется внешний endpoint/ключ в local-пути; модели нужно заранее скачать | Реальный disconnected run pending |

## Ограничение среды проверки

В этой среде нет `day-21-document-indexing/knowledge.db`; он намеренно исключён из Git. Живой preflight Ollama также вернул `Cannot reach the provider`. Самостоятельно выполнить живой запрос в этой среде нельзя. Пользователь предоставил doctor.json и первый ask.json: локальная модель загрузилась и ответила, но ответ провалил JSON/точные цитаты. Этот невалидный ответ сохранён в минимальной регрессионной фикстуре и не объявлен успешным результатом. Полное выполнение практической части задания пока нельзя объявить подтверждённым.

## Финальный live-прогон на Mac

После получения ветки, из корня репозитория и в активированном окружении:

```bash
python -m pip install -r day-28-local-rag/requirements.txt
python day-28-local-rag/test_day28.py -v
```

Запусти Ollama; `bge-m3` и `qwen2.5:14b` должны быть скачаны. `doctor` сообщит о недостающей модели/индексе. Корневые README в этом PR меняют корпус, поэтому старый индекс может потребовать пересборки:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
python day-28-local-rag/main.py doctor
python day-28-local-rag/main.py ask "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?"
python day-28-local-rag/main.py evaluate --repeats 3 \
  --output day-28-local-rag/reports/check/local.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local.json
```

Если индекс уже соответствует изменённому корпусу, повторно строить его не нужно. Для демонстрации полной локальности отключи интернет после подготовки моделей и повтори `evaluate`, сохранив результат отдельно:

```bash
python day-28-local-rag/main.py evaluate --repeats 3 \
  --output day-28-local-rag/reports/check/local-disconnected.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/local-disconnected.json
```

Затем восстанови интернет. При доступном `GROQ_API_KEY`:

```bash
python day-28-local-rag/main.py compare --repeats 3 \
  --output day-28-local-rag/reports/check/compare.json
python day-28-local-rag/verify_report.py day-28-local-rag/reports/check/compare.json
```

## Как принять результаты

- Состояние `completed`, код выхода `0`, `local_rag_verified=true`, `all_checks_passed=true`.
- Есть реально сгенерированные local-ответы, установленная модель/digest, matching `/api/ps` evidence; одни отказы приложения недостаточны.
- Все planned cases × trials × выбранные providers представлены ровно один раз.
- В каждой паре local/cloud совпадают SHA prompt и фрагменты. Cloud skip допустим только при отсутствии доступа; настроенное, но неработающее облако остаётся failure.
- Просмотри каждый ответ рядом с цитатами и ожиданиями: точная цитата не доказывает корректность всей формулировки. Сравни полноту/точность local и cloud и отдельно отметь ошибочные отказы, выдумки и форматные ошибки.
- Сравни median/p95 generation и pipeline; проверь первый и последующие повторы, load duration и throughput. Не сравнивай напрямую токены разных токенизаторов.
- Оцени success/error rates и stable/repeated cases; отдельно прочитай отличающиеся ответы. Текстовое различие не обязательно означает смысловую нестабильность.
- Зафиксируй hardware, версии Ollama/моделей и условия сети в итоговом выводе. JSON уже содержит server version/model digest; описание hardware нужно добавить вручную.

`verify_report.py` проверяет внутреннюю согласованность отчёта, не удостоверяет подлинность серверного ответа и не заменяет семантическую проверку. Ошибка/невалидный ответ должны быть исправлены или честно отражены в результате задания, а не скрыты из статистики.

## Повторный аудит V2

- Первоначальный raw response воспроизведён тестом: лишняя завершающая кавычка отклоняется; даже после её диагностического удаления обе изменённые цитаты отклоняются.
- JSON Schema реально добавляется в запрос Ollama; enum содержит доступные quote IDs. Groq реально получает JSON object mode. Это проверено через настоящие адаптеры Day 26 с тестовым HTTP.
- Модели получают одинаковые сообщения; output controls явно различаются в отчёте.
- Точные цитаты подставляет приложение. Проверены обратные кавычки, отступы, unknown/duplicate IDs и канонический отказ.
- Проверка новых отчётов сверяет каталог с источниками и raw ID selection с опубликованными цитатами.
- Первый реальный запрос: retrieval 0.112 с; HTTP generation 88.403 с; загрузка Qwen 11.555 с; собственно output generation 17.194 с; 8.20 token/s. Это один неуспешный по контракту запрос, а не бенчмарк качества/стабильности.
- Полный прогон V2 ещё не выполнен на Mac. Повтори тот же RU-вопрос с `--output day-28-local-rag/reports/check/ask-v2.json` и затем `verify_report.py`.


## V3: выборочный прогон

- Сохранять исходные отчёты, выводить retry в новое имя.
- `--plan-only`: нет HTTP или generation; для compare-v2 ожидаются 9 local и 21 cloud.
- Успешные пары вопрос–провайдер исключены; переоценка критериев записана отдельно.
- Запустить retry и независимый verifier; проверить полноту SQLite/identity и preflight/postflight вручную.
- Убедиться, что Groq соблюдает strict schema и не выбирает более 12 IDs.
- HTTP 429: ограниченные прозрачные повторы, ошибки и ожидания сохранены; суммарная задержка включена в wall time.
- Успешный subset не объявлять полным новым benchmark; V2 timing/stability не смешивать с V3.
- Окончательный полный прогон отложен пользователем; без-интернет демонстрация по-прежнему требует отдельного локального запуска.


## V4

- Local-only план от retry-v3: 6 вызовов, base-01 не вызывается, Groq не используется.
- Слоты q1–q4 string/null, не более четырёх цитат; неправильные типы, дубли, неизвестные IDs и лишние свойства отклоняются.
- Целые абзацы/код — точные подстроки; старые line-каталоги проверяются прежним способом.
- Проверить BOTH preflight/postflight в тексте ответа, не только в цитате.
- Проверить SQLite/identity в выбранных доказательствах RU вопроса; headings/диаграммы не считать достаточным механизмом.
- Отдельный cloud-only прогон при доступной квоте: проверить fixed-slot schema; причина исходного HTTP 400 остаётся неизвестной.
- V4 live-результат ещё не подтверждён; старые успешные результаты остаются историческими.
