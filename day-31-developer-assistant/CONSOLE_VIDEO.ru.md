# Сценарий видео — только терминал, без новой генерации

Ориентир6–8минут. Записывается окно Terminal вашим средством записи; сама демонстрация использует только команды ниже. Запись текста terminal session сама по себе не объявляется видео. Никаких новых recorder/framework dependencies здесь нет.

Сценарий показывает работающие MCP/FTS/workers и реальную публикацию уже полученного ответа. **Qwen работала один раз до записи**; historical trace показан с этой подписью. Новых Qwen calls для видео не разрешено. Это содержательная демонстрация ассистента, а не запуск test suite.

## До записи

Видео уже записано пользователем. Ниже сохранён сценарий демонстрации с командами из постоянного размещения исходников. Повторять запись или генерацию для подготовки Git не требуется.

Из корня repo, в прежнем окружении. Work/state остаются внешними. Не менять corpus/source files и не строить индекс.

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

Нужны прежние v103/v104, native276/preparation/state, Mac r3 work и применённый human review. Подготовить manifest с теми же54 sources; это только сериализация для существующего CLI:

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
set -o pipefail
python "$day31_entry" preflight --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"
```

PASS должен reuse существующий receipt: tests_run32, qwen_calls0. Это подготовительный check, не новая регрессия. При mismatch/ошибке остановиться; не удалять work/reservation и не запускать live. Все шаги выполнять последовательно, по одному, проверяя exit/output. В дальнейшем ненулевая ошибка не является PASS даже при красивом последующем выводе.

## 1. Граница и версия — 30 секунд

Сказать: «Учебный минимум принят. Приложение0.7.29 работает в отдельной копии с gate. Расширенное исследование не завершено; сейчас дополнительных генераций нет».

```bash
python "$day31_overlay/main.py" --version
```

Показать0.7.29. Имя версии относится к базовому приложению, не означает, что gate установлен в original main.py.

## 2. Настоящий MCP Git — 45–60 секунд

```bash
python "$day31_overlay/main.py" --root "$PWD" git branch | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" git status | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" git diff --scope unstaged | python -m json.tool --no-ensure-ascii
```

Показать transport=mcp_stdio, discovered_tools/tool_events, branch=main и llm_calls0. Это фактический MCP server/client call, не обычный Git output под чужой подписью. При желании отдельно `git branch --show-current` как независимое сравнение; это уже обычный Git, не MCP. Пустой diff корректен — специально создавать изменение запрещено этим сценарием.

## 3. Настоящий локальный RAG — 45–60 секунд

```bash
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" index verify | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" search 'pending completed failed' --mode fts --final-k 3 --source day-07-context-persistence/README.ru.md | python -m json.tool --no-ensure-ascii
```

Показать54/510, source/section/строки/digests и FTS excerpt. Embedding events должны быть пустыми. Это свежий поиск по существующему research54; production44 не используется и не заменяется. Source filter относится только к этому инструментальному показу; frozen RU1 model evidence не меняется.

## 4. Делегация — около минуты

```bash
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" agents demo --question 'Чем отличаются pending, completed и failed?' | python -m json.tool --no-ensure-ascii
```

Показать completed, Documentation/Git/Verification, разные task IDs/context digests, trace lifecycle и llm_calls0. Documentation/Verification запускаются owned workers, Git обращается к MCP; это реальные задачи. Не говорить, что здесь работают три модели или полный model Chain.

## 5. Отсутствие evidence — 40–50 секунд

```bash
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" agents docs --question qxzvnonexistentmodule7319 | python -m json.tool --no-ensure-ascii
```

В Documentation result показать outcome=insufficient_evidence и пустые sources; model calls0. Это свежий реальный Documentation/Verification путь; у `agents docs` вообще нет generation capability. Полный Pipeline refusal уже сохранён в реальном Mac preflight и показывается отдельно как сохранённый результат:

```bash
python - <<'PY'
import json
from pathlib import Path
check = json.loads(Path('/private/tmp/day31-course-minimum-r3-work/mandatory-checks.json').read_text())
r = check['no_evidence_result']
assert r['answer_status'] == 'unknown' and r['claims'] == []
assert r['metrics']['llm_calls'] == 0
print(json.dumps({'scope': 'SAVED REAL MAC PREFLIGHT; not a fresh model request',
                  'answer': r['answer'], 'answer_status': r['answer_status'],
                  'claims': r['claims'], 'model_http_attempts': r['metrics']['model_http_attempts']},
                 ensure_ascii=False, indent=2))
PY
```

Не вызывать main.py ask для видео: произвольный pipeline request не нужен. Здесь fresh worker insufficient_evidence и сохранённый реальный Pipeline refusal явно различаются.

## 6. Показ фактического Qwen-вызова — около минуты

Ниже только чтение local artifacts, не model run. Сказать: «Этот RU1 ответ был действительно сгенерирован Qwen на Mac. Показываю сохранённый raw witness/trace; сейчас генерация не повторяется».

```bash
python - <<'PY'
import json
from pathlib import Path
work = Path('/private/tmp/day31-course-minimum-r3-work')
paths = list((work / 'publication').glob('*-audit.json'))
assert len(paths) == 1
r = json.loads(paths[0].read_text())
t = r['inference_tasks'][0]
w = json.loads((work / 'raw' / ('raw-' + t['task_id'] + '.json')).read_text())
assert t['transport'] == 'ollama_loopback_http' and t['llm_calls'] == 1
assert w['response']['done'] is True
print(json.dumps({'scope': 'SAVED REAL QWEN RUN; zero new generation in this command',
    'request_id': r['request_id'], 'model': t['model'], 'transport': t['transport'],
    'chat_events': [e for e in t['http_events'] if e['endpoint'] == '/api/chat'],
    'input_tokens': t['input_tokens'], 'output_tokens': t['output_tokens'],
    'runtime_validation': t['output_validation'], 'raw_sha256': w['content_sha256'],
    'worker_cleanup': [e for e in r['trace'] if e['event'] == 'WORKER_REAPED'],
    'before_review': r['semantic_acceptance']['status']}, ensure_ascii=False, indent=2))
PY
```

Показать один chat47.67s,1109/396tokens, output_validation passed, WORKER_REAPED и исходный needs_review. Семь HTTP events включают metadata — это не семь генераций. Синтетические unit fixtures этим реальным output не подменяются.

## 7. Positive publication — 1–2 минуты

Human review уже дано пользователем и применено на Mac. Команда использует ровно то же решение; новой оценки/генерации не производит:

```bash
python "$day31_entry" publish --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"   --review "$DAY31_COURSE/evidence/human-review.json" --reviewer-id yuriy   | python -m json.tool --no-ensure-ascii
```

Показать answer_accepted=true, semantic_acceptance.status=supported, reviewer.kind=human/id=yuriy, c1/c2 supported, точный текст ответа и обе citations. Это свежий вызов настоящего publisher на сохранённом модельном результате. Повтор review idempotent; исходные raw/audit/withheld остаются в истории, export получает новый номер.

При несовпадении binding остановиться: не редактировать result/anchor и не брать другой ответ. Отказ publish не исправляется генерацией. В native audit поля старого semantic_support_verified и needs_review остаются историческими; актуальное human decision — в derived review/public, как и предусмотрено gate.

## 8. Завершение — 20 секунд

Сказать: «Показаны реальные MCP Git, FTS и делегация; один сохранённый настоящий Qwen-ответ опубликован только после явного human review. Course Minimum принят. Research Stage7 не завершён: EN3, Chain, held-out и исследования ресурсов остаются в backlog. Новых Qwen calls за запись —0».

## Что является PASS

Git transport mcp_stdio; FTS54 verify; реальные roles/lifecycle и zero-model metrics; fresh docs insufficient_evidence; сохранённый Pipeline unknown без model attempts; один подтверждённый historical Qwen call; positive publisher с matching bindings и human reviewer. Нельзя сокращать доказательство до версии/скриншота tests32.

## Чего не делать

Не выполнять live/ask/console с новым вопросом, dense/hybrid, index build, models prepare/confirm или benchmark. Не создавать commit/diff для зрелищности. Не выдавать сохранённую генерацию за новую в кадре или три tasks за три модели. Commit/push не входят в демонстрацию.
