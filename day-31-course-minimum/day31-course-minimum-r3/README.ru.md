# Course Minimum r3 — исправление offline preflight

r3 исправляет конфликт r2: общий network guard блокировал обязательный Day30 OFF port probe внутри `ModelSession.status`. Qwen в остановленном r2 не вызывался: 0 dispatch, 0 reservations, 0 terminal calls. Исходный присланный bundle сохранён побайтно в `inputs/r2-mac-preflight-stopped.json`; все его 64 reports продолжаются в новом bundle.

**Сейчас разрешён только preflight, не live.** Stage7 Research остаётся paused/incomplete. Учебный Day31 ещё не принят, Stage8 не начат.

## Команды Mac

Из корня repo в прежнем Python3.13+ venv:

```bash
day31_course_r3_dir=$(mktemp -d /tmp/day31-course-minimum-r3.XXXXXX)
unzip -n ~/Downloads/day31-course-minimum-r3.zip -d "$day31_course_r3_dir"
python "$day31_course_r3_dir/day31-course-minimum-r3/entry.py" preflight --root "$PWD"
```

Старый `/tmp/day31-course-minimum-r2-work` не удалять и не переиспользовать. r3 по умолчанию работает отдельно: `/private/tmp/day31-course-minimum-r3-work`. Установленный `main.py` не меняется. Новых dependencies нет.

Как прежде, нужны неизменённые App0.7.29, v103 `/tmp/day31-source-anchor-v103-r1`, persistence `/tmp/day31-anchor-persistence-v104-r1`, native276 `/tmp/day31-stage7-v099-work/native-preflight.json`, preparation `/tmp/day31-independent-v098-r1-work/preparation-bundle.json`, прежние production44/research54 states и закреплённые Git/source/corpus условия. Для первых двух каталогов есть `--v103`/`--v104`; остальные исторические pins не переписывать.

Ожидается выделенная Ollama session с прежним confirmed epoch, Day30 выключен. Не нужно автоматически перезапускать Ollama, перестраивать индекс или восстанавливать данные другими версиями ради PASS.

## Граница исправления

Network guard сохраняется. Единственное исключение — вызов **существующего** синхронного `preflight.port_check(8000)`: TCP handshake только с `127.0.0.1:8000` и `[::1]:8000`, без отправки HTTP/application payload. Прямое обращение к этим же адресам вне port_check запрещено. Ollama:11434, другие порты/адреса по-прежнему запрещены; AF_UNIX для локального event loop сохранён.

Проверки Day30 processes/launchd/ports и engine epoch не отключаются. Активный Day30 или неопределённый результат проверки по-прежнему останавливают запуск. Ошибки r3 дополнительно сохраняют тип и stack locations без locals.

## Результат preflight

Запускаются 32 целевых локальных теста, затем настоящий smoke на вашем repo: MCP Git/branch, существующий orchestrator Documentation/Git/Verification, owned FTS/Verification workers, no-evidence refusal, role/path/tool ограничения, исходные RU1 selection/context/anchors, неизменность CURRENT/SQLite и cleanup. Модельный transport/human approval в тестах синтетические. Сам smoke не использует inference. Новые индексы не создаются; штатные новые research traces допустимы, старые не переписываются.

PASS: exit0, `status=preflight_passed`, `tests_run=32`, `qwen_calls=0`, `embedding_calls=0`; `mandatory-checks.status=passed`, одинаковые index digests и нет lingering workers. Это техническая готовность узкого launcher, не semantic acceptance.

FAIL: exit2, `status=stopped`; остановиться и передать напечатанный bundle, не удаляя work. Никакого auto retry или model dispatch. Повтор успешного preflight переиспользует receipt только с теми же bindings. Прежние 83/276 тестов заново не запускаются.

Первый новый bundle:

```text
/private/tmp/day31-course-minimum-r3-work/exports/bundle-0001.json
```

Он сохраняет прежние 64 reports, включая отказ r2, и добавляет отдельные r3 reports в совместимом `day31-evidence-bundle-v1`. Для дополнительного экспорта без тестов/модели:

```bash
python "$day31_course_r3_dir/day31-course-minimum-r3/entry.py" export --root "$PWD"
```

## После preflight

Остановиться и проверить bundle. Подготовленный будущий вопрос остаётся RU1/Multi Documentation: различие pending/completed/failed и явное добавление pending в запрос против восстановления истории. Только после отдельного согласования — максимум один Qwen-вызов с прежним producer/options, без повторов. Затем факты/полнота/exact anchors и явное human review новых bindings. Без него `needs_review`, `answer_accepted=false`; unsupported и runtime refusal не становятся ответами.

См. `REPORT.ru.md`, `BACKLOG_AFTER_COURSE.ru.md`, `reports/local-checks.json`, `reports/local-bundle.json`. Локальные Linux results не являются Mac preflight receipt.
