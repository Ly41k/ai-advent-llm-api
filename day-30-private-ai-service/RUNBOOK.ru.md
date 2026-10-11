# Bublik — запуск и эксплуатация на MacBook

Актуально для runtime0.8.0/schema2/private-chat-v2 и проверенной конфигурации
MacBook M1. Рабочая установка уже использует launchd; команды новой установки
ниже не выполняйте поверх неё. Во время обновления кода остановите API и дождитесь
shutdown: загруженные Python modules не обновляются вместе с файлами на диске.

## Уже установленный сервис Юрия

В новом терминале заново задайте переменные — другое окно их не наследует:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
source ../.venv/bin/activate
BUBLIK_DB="/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3"
BUBLIK_TOKEN_FILE="/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json"
BUBLIK_TAIL_URL="https://yuriys-macbook-pro.tail893c10.ts.net"
BUBLIK_TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
python -c 'from bublik_service import __version__; print(__version__)'
launchctl print "gui/$(id -u)/local.bublik.private-ai.api"
"$BUBLIK_TS_CLI" serve status
curl --max-time 10 "$BUBLIK_TAIL_URL/api/v1/health/live"
```

Ожидается 0.8.0, state=running, Serve tailnet only и `{"status":"alive"}`.
Mac Wi-Fi/интернет и Tailscale должны оставаться включёнными. Приложение Ollama
должно работать. Не запускайте дополнительный API, Caddy или `ollama serve`.
LaunchAgents работают в сессии пользователя после login: это не сервер до входа
в macOS, не обещание работы при sleep, выключенном Mac или отключённом FileVault.

Для проверки readiness без вывода секретов и личной переписки:

```bash
python - <<'PY'
import json
import sys
from pathlib import Path
import httpx
sys.path.insert(0, "scripts")
from check_http_live import read_token
from bublik_service.http_api import runtime_manifest
token = read_token(Path("/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json"))
with httpx.Client(base_url="https://yuriys-macbook-pro.tail893c10.ts.net",
                  headers={"Authorization": "Bearer " + token},
                  timeout=15, trust_env=False, follow_redirects=False) as client:
    response = client.get("/api/v1/health/ready")
    data = response.json()
print(json.dumps({"http_status": response.status_code,
    **{key: data.get(key) for key in ("status", "model_ready", "profile",
       "inference_recovery_required", "queued", "running", "runtime_source_unchanged")},
    "runtime_matches_local": data.get("runtime_source_sha256") == runtime_manifest()
}, ensure_ascii=False, indent=2))
PY
```

Норма: 200/ready, profile private-chat-v2, model_ready=true, runtime matches/unchanged=true.
При idle queued=running=0 и recovery_required=false. Readiness требует service:read;
истёкший токен даст401, это не недоступность модели. Создание/отзыв токенов — CLI.

## Перед закрытием крышки и после пробуждения

При установленном launchd откройте URL чата после подключения Mac и телефона к
Tailscale; второй ручной `serve` не нужен. Дождитесь **«Ответ сохранён»** и
проверьте тот же диалог на другом устройстве. Готовность модели и доступность
истории проверяются отдельно: при недоступной Ollama история остаётся доступной.

Перед отключением интернета на Mac или закрытием крышки дождитесь сохранения всех
ответов и прекратите новые отправки. Для штатной остановки установленного API:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
/usr/sbin/lsof -nP -a -iTCP:8000 -sTCP:LISTEN
```

Дождитесь пустого вывода проверки listener. После пробуждения восстановите сеть и
Tailscale на Mac, откройте Ollama, если закрывали её, затем запустите API:

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Если перед сном API не останавливали, сначала проверьте `launchctl print` и откройте
чат; уже работающий сервис повторно не загружайте. Используйте прежнюю базу.
При спящем или отключённом от сети Mac чат недоступен. Если генерация была
прервана, используйте раздел «Restart и recovery» ниже.

## Подключить телефон

1. На Mac оставьте сеть, Tailscale, API и Ollama включёнными.
2. На Android/iPhone подключите Tailscale к тому же tailnet. Откройте
   `https://yuriys-macbook-pro.tail893c10.ts.net` и войдите тем же username Бублика.
3. Откройте нужный чат. Отправьте вопрос, дождитесь «Ответ сохранён», проверьте
   этот диалог на Mac. Пароль Бублика и учётная запись Tailscale — разные механизмы.
4. Для mobile data выключите Wi-Fi **только на телефоне**, оставьте мобильный
   интернет и Tailscale включёнными. Команды в терминале телефона не нужны.
5. Для отрицательной проверки выключите Tailscale **только на телефоне** при
   выключенном Wi-Fi. Новая приватная вкладка с URL должна не получить доступ.
   Затем включите Tailscale обратно — чат открывается, история остаётся.

`.ts.net` использует сертификат Serve, ручная установка LAN CA не нужна. Телефон
дома также может пользоваться этим URL через Wi-Fi + Tailscale. Настройка CA для
прямого LAN URL отдельно отложена. В браузере нет серверных API tokens.
Android: меню браузера → Установить/Добавить на главный экран. iPhone: Safari →
Поделиться → На экран «Домой». После смены URL/origin может потребоваться новый login;
чаты совпадут при том же владельце.

## Новая установка с отдельной базой

Используйте инструкции установки dependencies в README. Активный Python берите
из `sys.executable`, не предполагайте `.venv` внутри каталога дня.

```bash
BUBLIK_DB="$HOME/bublik-private-ai/chats.sqlite3"
python -m bublik_service --db "$BUBLIK_DB" init-db
python -m bublik_service --db "$BUBLIK_DB" user-add operator
python -m bublik_service --db "$BUBLIK_DB" doctor
```

Doctor проверяет Ollama listener/процессы/model/template без генерации ответа.
Не заменяйте рабочую базу новой, если нужны прежние чаты. Создание другого owner
не переносит историю. Зафиксированный проверенный профиль требует Qwen2.5:14b
Q4_K_M и поддерживаемый template; произвольная другая модель не обещается.

Подключите Tailscale на Mac и телефоне; установите HTTPS Certificates/MagicDNS и
сохраните минимальные access controls своего tailnet. Сначала проверьте текущий
Serve route, чтобы не заменить чужой service:

```bash
BUBLIK_TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
"$BUBLIK_TS_CLI" status
BUBLIK_TAIL_HOST="$("$BUBLIK_TS_CLI" status --json | python -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
BUBLIK_TAIL_URL="https://$BUBLIK_TAIL_HOST"
printf '%s\n' "$BUBLIK_TAIL_URL"
"$BUBLIK_TS_CLI" serve status
```

Если 443/root свободен, настройте private Serve и запустите API в foreground:

```bash
"$BUBLIK_TS_CLI" serve --bg --https=443 http://127.0.0.1:8000
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" funnel status
python -m bublik_service --db "$BUBLIK_DB" serve --port 8000 \
  --trusted-loopback-proxy --origin "$BUBLIK_TAIL_URL"
```

Сетевой endpoint должен быть tailnet only. Public Funnel и port forwarding не
нужны. Пример access controls: `deploy/tailnet-policy.example.jsonc`; замените
placeholders своими значениями, проверьте и сохраните policy. Narrow grant не
отменяет broad grants/legacy ACLs. Serve status не доказывает содержание policy.
HTTPS certificate публикует hostname в Certificate Transparency, а не сообщения
чата; для нового хоста можно выбрать нейтральное имя. Inference остаётся на Mac.

Прямой LAN/Caddy и trust собственного CA: [STAGE6.ru.md](STAGE6.ru.md), разделы2–8.
Эта историческая инструкция содержит старую версию архива: текущую0.8.0 не заменяйте
архивом0.5.0. Добавьте LAN origin вторым `--origin`; Caddy и API используют одну базу.
Закрепите LAN DHCP lease: смена IP требует согласованного изменения Caddy/origins.

Для нового tailnet-only LaunchAgent, после остановки foreground API:

```bash
BUBLIK_LAUNCH_DIR="$(mktemp -d "$HOME/bublik-launchd.XXXXXX")"
BUBLIK_PYTHON="$(python -c 'import sys; print(sys.executable)')"
python scripts/configure_launchd.py --python "$BUBLIK_PYTHON" --repo "$PWD" \
  --db "$BUBLIK_DB" --origin "$BUBLIK_TAIL_URL" --output "$BUBLIK_LAUNCH_DIR/generated"
plutil -lint "$BUBLIK_LAUNCH_DIR/generated/local.bublik.private-ai.api.plist"
plutil -p "$BUBLIK_LAUNCH_DIR/generated/local.bublik.private-ai.api.plist"
python scripts/install_launchd.py --from "$BUBLIK_LAUNCH_DIR/generated"
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Install не заменяет existing plist. Для уже установленного сервиса этот раздел
пропустите. Caddy LaunchAgent/оба origins: [STAGE7.ru.md](STAGE7.ru.md).
Serve и Ollama запускаются/подключаются отдельно; plist API их не поднимает.

## Диагностика

| Симптом | Проверка и действие |
|---|---|
| Tailscale is stopped | Открыть Tailscale **на Mac**, подключить; повторить Serve status |
| 502 от Serve | Проверить launchctl print и listener8000; TLS route есть, upstream API недоступен |
| Bare HTTP localhost даёт400 | В trusted proxy режиме это ожидаемая защита; проверять external HTTPS |
| live200, ready503, история работает | Проверить doctor/Ollama; live не доказывает готовность модели |
| runtime source unchanged=false | API работает со старым загруженным кодом; дождаться idle, остановить и отдельно запустить LaunchAgent |
| bootstrap error5 | Не запускать через sudo; проверить plist lint, python/cwd/DB paths, launchctl print и отсутствие старого listener |
| Report path already exists | Создать новый каталог/имя; исходный отчёт не удалять ради повторной проверки |
| 429 | Выдержать Retry-After; не ослаблять production quota для теста |
| Чаты отличаются | Проверить username/owner и выбранную DB; cookie разных origins отдельные |

Read-only проверки listener:

```bash
/usr/sbin/lsof -nP +c 0 -a -iTCP:8000 -sTCP:LISTEN
/usr/sbin/lsof -nP +c 0 -a -iTCP:11434 -sTCP:LISTEN
curl --max-time 5 http://127.0.0.1:11434/api/version
python -m bublik_service --db "$BUBLIK_DB" storage-status
```

Оба listener должны быть loopback, не `*`/LAN. Storage: schema2, WAL,
foreign_keys=true, synchronous2, integrity=ok, violations0. Не меняйте OLLAMA_HOST
на0.0.0.0, чтобы «починить» телефон: к модели обращается API на том же Mac.

## Restart и recovery

При обычном обновлении дождитесь terminal state всех генераций. Остановите только
API: `launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"`. После проверки
нового кода выполните bootstrap отдельной командой. Caddy/Serve и SQLite не удаляются.
Не используйте kill-9 ради обычного обновления. CLI recovery не запускайте поверх
живого worker. Queued v1 jobs после обновления требуют matching v1 profile для
дренирования, не перезаписи snapshots: [PROMPT_V2.ru.md](PROMPT_V2.ru.md), [API.md](API.md).

Если inference прерван и gate=true: остановите API, явно перезапустите Ollama,
дождитесь нового проверяемого engine epoch без orphan runners, затем:

```bash
python -m bublik_service --db "$BUBLIK_DB" recover-inference
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Снимать gate вручную в SQL нельзя. Один `/api/ps` показывает загрузку, не доказательство
idle. Новое поколение запускается явным новым запросом; old inference не replay.
Partial/failed/interrupted сообщения остаются в полной истории.

## Backup и перенос истории

Базовый SQLite backup API реализован и проверен тестами. После дня 30 добавлен
[инструмент переносимости истории](MEMORY_PORTABILITY.ru.md): verified archive
и restore в новую базу, с сохранением исходных данных и отзывом старых credentials.
Практический перенос личной базы, retention/off-host copies и перенос console
owner ещё не выполнялись. После
согласования проверяйте восстановление в отдельной базе, сохранность IDs/receipts,
состояние queued/running, auth/session policy и применимость миграций. Не копируйте
один живой sqlite3 без WAL и не восстанавливайте поверх работающего сервиса.

## Корпус дня 21

Изменены root README; день30 не использует RAG, но будущий strict RAG run увидит
другой corpus fingerprint. Из корня репозитория, отдельно от работающего чата:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

Build использует embedding bge-m3; не запускайте его одновременно с приёмкой Qwen
или на основании предположения, что в памяти останется только одна модель. Сам
индекс и старые отчёты на этапе9 не пересобирались/не переписывались.
