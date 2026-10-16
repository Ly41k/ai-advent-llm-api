# День 31 — Bublik Developer Assistant

**Course Minimum — Accepted.** Рабочий developer assistant сочетает Project RAG, read-only Git через настоящий MCP, делегацию задач и локальную Qwen. Учебная приёмка ограничена конфигурацией ниже; расширенный Research Stage7 остаётся **paused/incomplete**. Видео записано пользователем. Подготовка файлов к Git выполняется отдельно от commit/push.

## Проверенная конфигурация

| Компонент | Фактический scope |
|---|---|
| Базовое приложение | App0.7.29, установленный `main.py` сохранён |
| Безопасная модельная публикация | Отдельная копия + Publication Gate v104-r2; launcher Course Minimum r3 |
| RAG | Существующий research FTS54: 54 документа/510 chunks; закреплённый RU1 context и v103 selector/producer |
| Production state | Отдельный production44: 44 документа/405 chunks, не заменён research54 |
| Генерация | Qwen2.5:14b Q4_K_M, Ollama loopback; temperature0, seed31, context8192, output1024 |
| Демонстрационный ответ | RU-1 / Multi Documentation: один реальный Qwen call; это не два независимых LLM contexts |
| Допуск | Runtime validation + exact claim/anchor binding + явное human review текущего результата |

В scope RU1 объясняются pending/completed/failed и восстановление истории. Пользователь подтвердил обе claims и принял пропуск расширенного защитного причинного объяснения. Общая точность модели и остальные вопросы этим не приняты.

## Архитектура

| Роль | Обязанности и возможности |
|---|---|
| Main | Детерминированные routing, budgets, постановка tasks, merge/final validation; в выбранном model case отдельного Main LLM call нет |
| Documentation | Реальный локальный FTS retrieval в owned worker; затем отдельный локальный model task по ограниченному evidence context |
| Git | MCP stdio: branch/status/files/diff; без commit/push и произвольного shell |
| Verification | Owned worker проверяет источник/provenance/формат делегированных результатов; не заменяет semantic review |

В `agents demo` Documentation и Git — отдельные tasks; Verification зависит от них, Main объединяет результат. В RU1 live сначала свежая acquisition Documentation/Verification, затем snapshot с тем же frozen context и один Documentation Qwen worker. Snapshot replay не выдаётся за полный dependent model Chain. Подробности: [ARCHITECTURE.ru.md](ARCHITECTURE.ru.md).

## Установка и сохранённое окружение

Mac/Python3.13+, Git и прежний venv с зависимостями `requirements.lock`. Из корня repo. Если окружение уже работает, повторная установка не нужна. Только для новой .venv при её отсутствии:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r day-31-developer-assistant/requirements.lock
```

Нужны сохранённые source/Git/corpus pins, native276 receipt `/tmp/day31-stage7-v099-work/native-preflight.json`, исходная подготовка `/tmp/day31-independent-v098-r1-work/preparation-bundle.json`, original production44, research54 и course r3 work с результатом. Это воспроизведение подготовленного состояния, **не standalone installer**: одних requirements/ZIP недостаточно после утраты state. Восстановление из резервной копии — отдельно; missing/stale данные дают STOP, не silent rebuild/fallback.

Проверенные runner/producer/adapter теперь хранятся исходниками в соседней папке `day-31-course-minimum/`. Внутрь `day-31-developer-assistant` дополнительные Python-файлы не помещаются: исходный binding ожидает ровно 60 файлов. Main, prompt и retrieval не заменяются. Сохранённые work/state/receipts остаются внешними; не удалять прежние папки `/tmp` до отдельного резервного копирования.

```bash
source .venv/bin/activate
python --version

export DAY31_COURSE="$PWD/day-31-course-minimum"
day31_entry="$DAY31_COURSE/day31-course-minimum-r3/entry.py"
day31_v103="$DAY31_COURSE/day31-source-anchor-v103-r1"
day31_v104="$DAY31_COURSE/day31-anchor-persistence-v104-r1"
day31_overlay=/private/tmp/day31-course-minimum-r3-work/isolated-app
day31_state54=/private/tmp/day31-independent-v098-r1-work/isolated-fts-state

python "$DAY31_COURSE/verify_delivery.py" --root "$PWD"
```

Размещение исходников не восстанавливает остальные state/receipts. Остаться на той же Git branch/HEAD, документах и закреплённых исходниках. Индексы в этом сценарии не строятся; Day30 выключен, Ollama session confirmed с совпадающим process epoch. Session status использует OS witness и TCP handshake к loopback8000 для проверки Day30, без HTTP к модели.

После нового commit Git HEAD изменится. Прежний frozen preflight привязан к старому HEAD: его STOP в новой ревизии ожидаем и не исправляется переписыванием pins. Сохранённая приёмка относится к прежнему результату. `verify_delivery.py` проверяет целостность поставки и не является повторной E2E-приёмкой; `publish` проверяет прежние bindings без новой генерации.

## Preflight без Qwen

```bash
python "$day31_entry" preflight --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"
```

Ожидается `preflight_passed`, tests_run32, qwen_calls0/embedding_calls0. На уже принятом r3 work проверяется и переиспользуется существующий receipt: число32 не означает новый suite run. При ошибке остановиться и сохранить bundle; не перестраивать индексы, не перезапускать модель и не удалять reservation ради PASS.

## Реальные инструменты без генерации

Сериализовать прежний manifest54 в формат существующего CLI, вне repo. Sources не добавляются, index/selector/producer не изменяются:

```bash
export DAY31_DEMO_DIR=$(mktemp -d /tmp/day31-demo.XXXXXX)
python - <<'PY'
import json, os
from pathlib import Path
frozen = json.loads((Path(os.environ['DAY31_COURSE']) / 'day31-source-anchor-v103-r1/source-freeze.json').read_text())
rows = frozen['source_manifest']
assert len(rows) == 54
selection = {'schema_version': 1, 'sources': [
    {'path': row['source'], 'kind': row['kind']} for row in rows
]}
path = Path(os.environ['DAY31_DEMO_DIR']) / 'sources54.json'
with path.open('x', encoding='utf-8') as stream:
    json.dump(selection, stream, ensure_ascii=False, indent=2)
print(path)
PY
day31_manifest="$DAY31_DEMO_DIR/sources54.json"
```

```bash
python "$day31_overlay/main.py" --version
python "$day31_overlay/main.py" --root "$PWD" git branch | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" git status | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" git diff --scope unstaged | python -m json.tool --no-ensure-ascii

python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" index verify | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" search 'pending completed failed' --mode fts --final-k 3 --source day-07-context-persistence/README.ru.md | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" agents demo --question 'Чем отличаются pending, completed и failed?' | python -m json.tool --no-ensure-ascii
```

`agents demo` — реальные FTS/MCP/workers, **0 LLM calls**. Generic FTS выдача в этом инструментальном показе не объявляется идентичной frozen v103 selection/context, использованной моделью. Diff может быть пустым; специально менять repo для видео не нужно. JSON tool делает русский текст читаемым и сохраняет JSON escaping управляющих символов.

## Запуск модели и публикация

Исторический порядок: `entry.py preflight` → `entry.py live` → аудит → явное human review → `entry.py publish`. Фактически выполненная live-команда:

```bash
python "$day31_entry" live --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"
```

**Это запись уже выполненной команды, не шаг Stage8. Сейчас её не запускать.** В текущем work reservation уже существует; повтор генерации запрещён. Launcher admits только RU1/Multi, cap1, фиксированные sources/context/schema/options, no model retry/cloud fallback. Installed `main.py ask` не является заменой этого проверенного publication route.

Human review уже сохранено на Mac и проверено по bundle0003: c1/c2 supported, answer_accepted=true, review SHA `7ed6948e516e35d077888b5e8ee34b4c3e24590a6d1011ffc4cf41ecb6674174`. При необходимости показать публикацию снова, без модели:

```bash
python "$day31_entry" publish --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"   --review "$DAY31_COURSE/evidence/human-review.json" --reviewer-id yuriy   | python -m json.tool --no-ensure-ascii
```

Publish idempotently читает исходный audit и то же user-approved review; claims/anchors/result bindings должны совпадать. Старый withheld result и raw сохраняются, reviewed audit/public хранятся отдельно; создаётся следующий numbered export, а не новая генерация. Без explicit human review статус needs_review и answer_accepted=false; unsupported/runtime refusal не публикуются. Простая проверка identifier/точности цитаты не доказывает смысловую поддержку.

## Подтверждённые результаты

- Mac r3: 32/32 technical tests, Python3.13.3; реальные MCP/delegation и unknown без evidence, zero model attempts.
- RU1: один настоящий Ollama chat, 1109 input/396 output tokens, chat47.67s; повторов и unknown attempts нет. Это один замер, не benchmark.
- Две claims, семь проверенных смысловых частей. Пользователь явно подтвердил текущие bindings и ограничение расширенной полноты.
- Mac publish: 79 report SHA проверены; исходные76 live reports неизменны; новый human review/current bindings совпадают, answer_accepted=true.
- Шесть дополнительных metadata HTTP events вокруг chat не являются генерациями. Публикация/review/Stage8 не добавили Qwen calls.

Положительный факт относится к одному known RU1 case, не held-out. Preflight model transport/human approvals в unit fixtures были синтетическими; текущая Qwen generation и финальное human approval — реальные. Full Chain, arbitrary contexts и независимые Main/Documentation LLM contexts этим не подтверждены.

## Ограничения и сдача

Это application capability isolation доверенного кода, не OS sandbox. Workspace/role/schema/budget/path guards сохраняются; secret/private DB/symlink/untracked content не выдаётся, содержимое diff требует явных paths. Нативные diagnostic audits не являются публичными ответами.

Research Stage7 **не завершён**. EN3 exact-anchor/claim decomposition, широкий Single/Multi benchmark, полноценный Chain/human workflow, held-out, repeatability/resource study и corpus44/54 calibration сохраняются в [BACKLOG_AFTER_COURSE.ru.md](BACKLOG_AFTER_COURSE.ru.md). Исторические known22 не приписываются текущему producer.

[Видео только через терминал](CONSOLE_VIDEO.ru.md). Показ включает новые реальные MCP/FTS/delegation operations, публикацию сохранённого реального ответа и отдельно обозначенный historical model trace — без нового Qwen. Перед commit/push требуется финальный просмотр staged diff и состава файлов. Запись видео подтверждена пользователем; файл/ссылка в этот пакет не добавлены.
