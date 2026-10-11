# День 30 — сценарий видео через терминал

Сценарий для уже установленного сервиса Юрия: runtime0.8.0/private-chat-v2,
working schema2, Serve HTTPS, launchd. Пользователь уже записал UI-видео
с сообщениями с телефонов; этот консольный сценарий — необязательная альтернатива. Старые отчёты показывают
результаты прошлых runs; новый run создаёт отдельные синтетические чаты. Нельзя
объявлять терминальный запуск с Mac доказательством физического телефона.

Не выводите token JSON, environment dump, password, cookies, Authorization headers,
личные history/export или shell history. Здесь пароль нигде не передаётся CLI
аргументом, token читается из private file. Public URL/путь содержат имя владельца:
для публикации можно скрыть эту часть кадра. Не включайте `set -x` или curl verbose.

## 1. Подготовка — до записи

Mac включён и бодрствует, интернет/Tailscale/Ollama подключены. Подождите завершения
личных генераций; во время baseline не отправляйте вопросы с других устройств.
Не запускайте Revik, embedding/RAG или вторую модель параллельно. Существующие
API/Caddy LaunchAgents не заменяйте ручными серверами. В одном терминале:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
source ../.venv/bin/activate
BUBLIK_DB="/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3"
BUBLIK_TOKEN_FILE="/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json"
BUBLIK_TAIL_URL="https://yuriys-macbook-pro.tail893c10.ts.net"
BUBLIK_TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
BUBLIK_VIDEO_DIR="$(mktemp -d "$HOME/bublik-day30-video.XXXXXX")"
printf '%s\n' "$BUBLIK_VIDEO_DIR"
python --version
python -c 'from bublik_service import __version__; print(__version__)'
python scripts/verify_report.py reports/verified/stage8-prompt-v2-offline.json
```

Ожидается0.8.0 и report_matches_sources_and_passed=true. Verification — сравнение
исходников, не новый прогон143тестов и не proof network/model. Output directory новый.
Исторические baseline/recovery JSON не переписываем ради записи.

## 2. Запуск и сетевые границы — около минуты

Покажите состояние службы. Если она уже running, это проверка автозапуска:

```bash
launchctl print "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP +c 0 -a -iTCP:8000 -sTCP:LISTEN
/usr/sbin/lsof -nP +c 0 -a -iTCP:11434 -sTCP:LISTEN
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" funnel status
curl --max-time 10 -i "$BUBLIK_TAIL_URL/api/v1/health/live"
curl --max-time 10 -i "$BUBLIK_TAIL_URL/api/v1/chats"
```

Покажите loopback8000/11434, Serve tailnet only, live200 и chats401.
Если LaunchAgent намеренно не загружен и listener8000 отсутствует, для демонстрации
старта выполните отдельно:

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Если служба уже существует, повторный bootstrap не нужен. При error5 не применяйте
sudo: см. RUNBOOK. Bare localhost HTTP в proxy режиме даст400 — это ожидаемо.
Фраза для видео: «Открыт только приватный HTTPS entry point. Локальная Ollama не
выставлена в сеть. Состояние tailnet policy требует отдельной проверки».

## 3. Реальный чат/API, 10 sequential и 3 concurrent — 3–5 минут

Одним live checker выполняются реальные Qwen requests через HTTPS:

```bash
python scripts/check_acceptance_live.py \
  --network tailnet --url "$BUBLIK_TAIL_URL" \
  --token-file "$BUBLIK_TOKEN_FILE" \
  --output "$BUBLIK_VIDEO_DIR/baseline.json"
```

Checker создаёт10последовательных вопросов с динамической историей,
3RU greetings и3конкурентных requests. Проверяет replay, context/body overflow,
401, HTTP rate limit и resource counters. Не ослабляйте лимит ради видео; возможны
ожидания Retry-After. Три конкурентных HTTP admission означают bounded queue и
одну активную Qwen generation, не три параллельные модели.

После завершения выведите только контрольные данные отчёта:

```bash
python - "$BUBLIK_VIDEO_DIR/baseline.json" <<'PY'
import json
import sys
from pathlib import Path
d = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({key: d.get(key) for key in (
    "status", "technical_status", "quality_status", "quality",
    "latency", "resources", "source_unchanged"
)}, ensure_ascii=False, indent=2))
print("generations:", len(d.get("generations", [])))
print("technical checks:", len(d.get("checks", [])))
print("control chat ids:", [c["id"] for c in d.get("chats", [])])
PY
```

Ожидаются passed, technical259/259, quality13/13,16completed при тех жеconditions.
Числа нового run могут отличаться по timing/ресурсам; failed не скрывать и не
заменять historical report. `resources` — sampled RSS/CPU/allocation, не физическая
unified memory; API RSS и Ollama allocation не складываем.

Если нужна в кадре одна контрольная реплика, используйте сохранённый synthetic
generation из этого checker, а не личный чат. Raw baseline содержит только созданные
проверкой тексты; токен и личная переписка туда не записываются.

## 4. История после restart API — около минуты

Только после завершённого baseline и idle0/0. Не отправляйте новых сообщений в
контрольные чаты до read-only verification. Запомните текущий PID из launchctl print.

```bash
launchctl kill SIGTERM "gui/$(id -u)/local.bublik.private-ai.api"
```

Launchd KeepAlive запустит процесс снова; выдержите его throttle (до30s) и
дождитесь HTTPS live200/модель ready. Выполните отдельно:

```bash
launchctl print "gui/$(id -u)/local.bublik.private-ai.api"
curl --max-time 10 "$BUBLIK_TAIL_URL/api/v1/health/live"
python scripts/check_acceptance_live.py \
  --network tailnet --url "$BUBLIK_TAIL_URL" \
  --token-file "$BUBLIK_TOKEN_FILE" \
  --history-from "$BUBLIK_VIDEO_DIR/baseline.json" \
  --output "$BUBLIK_VIDEO_DIR/history-after-restart.json"
```

Ожидается новыйPID и passed11/11: все7syntheticчаты,32сообщения и full history hashes
прежние. History mode не запускает новую inference, quality/resources=not_run.
После обновления sources нужно создавать новый same-version baseline;
исторический v1 нельзя передавать как ordinary v2 `--history-from`.

## 5. Недоступная модель и восстановление — необязательный отдельный фрагмент

Уже сохранена реальная цепочка21/21→9/9→15/15 с partial707chars наv1. Можно показать
её в терминале без повторного прерывания рабочих запросов:

```bash
python - <<'PY'
import json
from pathlib import Path
for name in ("recovery-prepare-20261010-204716.json",
             "recovery-interrupted-20261010-204758.json",
             "recovery-restored-20261010-205125.json"):
    d = json.loads((Path("reports/verified") / name).read_text())
    print(name, "status:", d.get("status"), "checks:", len(d.get("checks", [])))
PY
```

Укажите version/date: это прошлый реальный run, не новая демонстрацияv2. Для новой
повторной interruption проверки используйте [STAGE8.ru.md](STAGE8.ru.md) и
check_recovery_live.py с NEW output paths; нельзя обещать, что просьба «500предложений»
заставит модель отвечать долго. Recovery не запускать автоматически в видео-script.
При обычном outage partial не обязателен: live/history доступны, ready503; после
restoration ready200. При uncertain inference нужен stopAPI + explicit restartOllama
+ recover-inference, без SQL обхода gate и скрытого replay.

## 6. Телефон и завершение

Только консольное видео показывает Mac caller, а не Android/iPhone по mobile data.
В кадре честно назовите уже подтверждённые physical handoff8/8 и manual three-device
sync/mobile/off-on. Если нужна новая независимая phone demonstration, это отдельная
запись устройства; локальный checker/viewport её не заменяет.

Назовите итог: HTTP API v1, локальная Qwen, сохранённая server-side история,
безопасная очередь и приватный HTTPS. Укажите ограничения: login/awakeMac,
saved policy audit/remote scan не представлены, backup/restore отдельно отложен.
Исследование Rust — backlog. Покажите FINAL_REPORT и BACKLOG.

Не запускайте Day21 build во время записи: новый rootREADME меняет corpus,
но rebuild bge-m3 может загрузить другую модель и испортить сопоставимость ресурсов.
Видео не требует нового Qwen benchmark или root-index rebuild для просмотра старых
отчётов. После записи сохраните новые JSON отдельно; не коммитьте token/DB/TLS keys.
