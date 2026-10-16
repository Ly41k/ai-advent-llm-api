# Этап 5 — Router, Chain, Fan-Out и Qwen; v0.4.1

Статус: Stage 4 принят. Mac v0.4.0: 128/128 tests, build/verify и RU Qwen прошли;
EN Documentation отклонён до Main. Stage 5 ещё не принят. v0.4.1 исправляет
воспроизводимый дефект punctuation и добавляет output_validation_reason.
Точный ответ неуспешного v0.4.0 не сохранён; причина того запуска не установлена.

## Что добавлено

- Bare `/help` остаётся без Git, профиля и моделей. `/help вопрос` и `ask` идут
  в project pipeline; явные `git`/`search` команды сохранены.
- RU/EN Router выбирает documentation, Git metadata, независимый Fan-Out или
  changed-files Chain. Неоднозначные несколько Git intents возвращают unknown
  с diagnostic, без выбора случайного инструмента. Произвольного planner/tool
  executor нет; write intentions не получают executor даже через approval.
- Chain сначала получает Git status. Только затем Documentation получает
  до четырёх разрешённых относительных путей. Namespace состоит из docs,
  буквально упоминающих эти пути, или самих изменённых indexed docs.
  Совпадение basename не является association. Это mentions, не proof функции.
- Documentation Qwen получает scoped question и excerpts. Main Qwen получает
  полный вопрос, проверенные doc claims и application Git facts. Git/Verification
  не имеют inference. Model tasks имеют TaskEnvelope/ContextEnvelope, собственные
  IDs, workers, digests и lifecycle; общий lease сериализует model operations.
- Main может выбрать порядок существующих IDs; новые текст/факты ему запрещены.
  Неподдержанный ID/identifier блокируется. После Main проверяются fresh spans,
  source/index digests и повторное Git observation через собственную Git роль.
- Console хранит один предыдущий documentation question в памяти процесса.
  Project ID/corpus change сбрасывают его. Private chat/history DB не читается.

Default pipeline retrieval — FTS: это начальный измеряемый путь с одной Qwen
моделью. `--pipeline-mode hybrid` или dense перед command включает bge-m3 retrieval
в Documentation worker через тот же lease. Standalone search сохраняет defaults
dense vocabulary/hybrid raw. Новая corpus calibration относится к этапу Research.

## Проверить на Mac

Из корня репозитория, в существующем Python 3.13 venv. Dependencies прежние.
Day30/Revik/другие Ollama clients остаются выключенными в выделенной сессии.

```bash
unzip -o ~/Downloads/day31-stage5-v041.zip -d "$PWD"
python day-31-developer-assistant/main.py --version
python day-31-developer-assistant/main.py index verify
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage5.py --live --output /tmp/day31-stage5-mac-v041.json
```

После успешно проверенного v0.4.0 индекс НЕ пересобирать: project/docs не менялись.
Ожидаем текущий индекс 40 docs / 380 chunks; index verify проверит его freshness. Если epoch изменился,
выполнить `python day-31-developer-assistant/main.py models confirm` и проверить
confirmed. При session-required/uncertain — recovery из RAG_MAC.ru.md.
Автоматического restart, shutdown чужих сервисов или retry нет.

Script сначала запускает 131 tests и actual-project temporary-index smoke:
branch через MCP и empty retrieval без generation. После их успеха выполняет
два live requests на существующем индексе: RU history question (1 Qwen call)
и EN API-prefix + current-branch (Documentation + Main, 2 calls). Максимум
3 generation calls, никакой автоматической попытки починить неуспех до PASS.
Если первый live request не ответил полноценно, следующий не запускается.
Expected: status=passed, live_pipeline_smoke.status=passed, две разные Qwen
message/context digests на mixed request и independent_llm_contexts_verified=true.
Это проверка real contexts/structure/provenance, не held-out semantic quality.
Output file должен быть новым. Пришлите JSON и build/verify output.

Проверка без модели: убрать `--live`; live tests не будут объявлены пройденными.
Каждый pipeline сохраняет private trace вне repo; reports/traces не индексируются.

## Ручная демонстрация

```bash
python day-31-developer-assistant/main.py /help
python day-31-developer-assistant/main.py /help "Какая текущая ветка?"
python day-31-developer-assistant/main.py ask "Где хранится полная история переписки?"
python day-31-developer-assistant/main.py --language en ask "What is the private service API prefix and what is the current branch?"
python day-31-developer-assistant/main.py ask "Какие файлы изменены и где описана их функциональность?"
python day-31-developer-assistant/main.py ask "zxqv_unicorn_transducer_9988"
python day-31-developer-assistant/main.py console
```

Пустой retrieval — successful unknown, не transport failure. Chain при отсутствии
изменённых разрешённых файлов возвращает проверенный Git факт без inference/index.
При unlinked files/более четырёх paths показывает partial/diagnostic, а не выдумывает
описание всех изменений. Git facts включают время повторного наблюдения.

## Профиль и ограничения

Qwen2.5:14b, local Q4_K_M, family qwen2, temperature=0, num_ctx=8192,
num_predict=1024, seed=31. Model identity и loaded-model allowlist проверяются;
/api/ps не считается idle witness. Chat — loopback /api/chat, no proxies/redirects,
bounded response, schema format и stream=false. Документация API проверена:
https://docs.ollama.com/api/chat ; https://docs.ollama.com/capabilities/structured-outputs .

До dispatch применяется консервативная token upper-bound estimate по UTF-8 bytes
с отдельными output/reserve. Она не выдаётся за реальные tokens. prompt_eval_count
и eval_count фиксируются отдельно. Warmup/probe generation нет. Unknown lost-call
count остаётся null с known/unknown accounting; не изображается как zero calls.
После uncertain запроса следующий inference запрещён до проверяемого recovery.
8 capability calls/request, 300 s overall, 180 s per model worker. Cancellation
убирает owned worker, но не обещает остановку внешнего Ollama generation.

Semantic support остаётся false: exact provenance и ID/language/identifier checks
не доказывают смысл всех claims. Main ограничен assembly IDs, не свободным
переписыванием ответа. RU/EN language check — грубый script check; ручная оценка
качества остаётся необходимой. Broad retry/recovery/resource stress и single/multi
benchmark/held-out evaluation — этапы 6–7. ОС sandbox и защита от hostile Python
под тем же OS user не заявляются. Дни 1–30 и их private data не изменялись.

## Проверка исправления

Новые regression checks принимают `/api/v1.` как API-путь с точкой предложения;
точные inline-code tokens и неизвестные `/api/v2` / `/api/v1/evil` остаются запрещены.
При отказе смотрите inference_tasks[].output_validation_reason. Это фиксированный
код, без rejected model text; завершённый запрос сохраняет llm_calls=1 и реальные
tokens. Отказ не вызывает автоматический retry или uncertain recovery.
Локальные Qwen transport fixtures синтетические; новый real Mac/Qwen требует
приведённой выше проверки. Предыдущий failed Mac report сохранён неизменным в
reports/verified/day31-stage5-mac-v040.json.

В v0.4.1 здесь прошли 102 теста: 75 Foundation/RAG и 27 pipeline, Python 3.12.14.
Новый real Qwen/full MCP Mac запуск здесь не выполнялся. Report:
reports/verified/stage5-v041-offline.json.
