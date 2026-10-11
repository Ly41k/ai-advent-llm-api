# Этап 7 — автозапуск на Mac и PWA

Runtime 0.7.0, прежняя schema=2. База, owners, сообщения, токены и модельный
профиль не мигрируют. Backup/restore и перенос истории этапа 3 отложены по
решению пользователя. Это не подтверждение полной приёмки дня 30.

## 1. Что меняется

Пользовательский LaunchAgent запускает API после входа в macOS и перезапускает
его после выхода процесса. Он не работает до входа пользователя / после logout;
FileVault после reboot требует обычной разблокировки. Это не LaunchDaemon/root.
API остаётся на 127.0.0.1:8000, один worker. Существующий Caddy при необходимости
получает отдельный LaunchAgent с прежними CA/config directories; новый CA не создаём.
Tailscale и Ollama запускаются их приложениями, не вторым `ollama serve`.

KeepAlive=true, RunAtLoad=true, ThrottleInterval=30 s, ExitTimeOut=60 s,
Umask=0077. Интерпретатор .venv записывается абсолютным путём с сохранением
venv symlink, параметры передаются как argv без shell. PATH включает стандартные
macOS и Homebrew directories для engine witness (`ps`, `lsof`). stdout/stderr
идут в /dev/null: нет растущих файлов с traceback/секретами. Диагностика —
launchctl state/exit code, authenticated readiness, doctor/storage-status.
Более удобная ограниченная диагностика остаётся будущим улучшением.

PWA имеет same-origin manifest, standalone display и PNG icons 192/512/180.
Service worker, Cache Storage и offline replay отсутствуют; CSP запрещает workers,
все ответы остаются no-store. Установленный чат требует сеть и работающий сервер.
Пароль/токены/история не записываются в web storage. Cookie остаётся защищённой;
браузер и установленное приложение могут иметь разные cookie sessions.

## 2. Обновление

Дождитесь завершения всех генераций. Остановите прежний API через Ctrl+C; если
переводите Caddy под launchd — также остановите его foreground terminal. Ollama
и Tailscale оставьте включёнными. Не закрывайте процесс во время генерации для
обычного обновления. Распакуйте архив в корень репозитория:

```bash
unzip -o "$HOME/Downloads/day30-stage7.zip" -d "/Users/litdi/AI/ai-advent-llm-api"
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
source ../.venv/bin/activate
python -m pip install --no-deps -e .
python -m bublik_service --db "/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3" storage-status
python scripts/verify_report.py reports/verified/stage7-offline.json
```

Integrity=ok, queued=running=0, recovery_required=false. При gate=true не снимайте
его автоматически: см. раздел recovery ниже. Последняя команда сверяет hashes
с готовым offline report, не доказывает macOS/network/model acceptance.

## 3. Создание и просмотр конфигурации

Начните с NEW каталога; если он уже существует, используйте другое имя и
сохраните его для проверок после reboot. Никаких token/password в plist.

```bash
BUBLIK_STAGE7_DIR="$HOME/bublik-day30-stage7"
mkdir -m 700 "$BUBLIK_STAGE7_DIR"
mkdir -p "$HOME/bublik-day30-stage6/caddy-config"

python scripts/configure_launchd.py \
  --repo "$PWD" \
  --db "/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3" \
  --origin "https://192.168.0.247:8443" \
  --origin "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --caddy "$(command -v caddy)" \
  --caddy-config "$HOME/bublik-day30-stage6/Caddyfile" \
  --caddy-data "$HOME/bublik-day30-stage6/caddy-data" \
  --caddy-state "$HOME/bublik-day30-stage6/caddy-config" \
  --output "$BUBLIK_STAGE7_DIR/launchd"

plutil -lint "$BUBLIK_STAGE7_DIR/launchd/local.bublik.private-ai.api.plist"
plutil -lint "$BUBLIK_STAGE7_DIR/launchd/local.bublik.private-ai.caddy.plist"
plutil -p "$BUBLIK_STAGE7_DIR/launchd/local.bublik.private-ai.api.plist"
plutil -p "$BUBLIK_STAGE7_DIR/launchd/local.bublik.private-ai.caddy.plist"
```

Если выбран только Tailscale и прямой LAN пока не нужен, уберите все четыре
`--caddy*` параметра; Caddy plist тогда не создаётся. Существующий LAN origin
можно сохранить. Это не удаляет CA и не отключает работающий Caddy самостоятельно.
Для автоматического LAN сохраните IP Mac DHCP reservation на роутере: при
смене 192.168.0.247 Caddy/Origin требуют явного обновления конфигурации.

Параметр `--python` здесь опущен: генератор сохраняет `sys.executable`
активного окружения. У пользователя .venv находится в корне репозитория,
а не внутри day-30-private-ai-service. Если окружение размещено иначе,
активируйте именно его перед командой.

Генератор лишь создаёт файлы; БД не открывает, процессы не запускает. NEW output
не перезаписывается. Installer также сохраняет уже существующие plists.

## 4. Установка и запуск

Убедитесь, что прежние foreground API/Caddy остановлены. Нельзя одновременно
вручную запускать serve и его LaunchAgent для одной базы/порта.

```bash
python scripts/install_launchd.py --from "$BUBLIK_STAGE7_DIR/launchd"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.bublik.private-ai.caddy.plist"
launchctl print "gui/$(id -u)/local.bublik.private-ai.api"
launchctl print "gui/$(id -u)/local.bublik.private-ai.caddy"
```

Для Tailscale-only пропустите Caddy bootstrap/print. Ожидается state=running и
PID. При duplicate/bootstrap error не повторяйте запуск другого API поверх
этого; проверьте launchctl и listeners. /dev/null не содержит журнал для tail.
Обычный curl без proxy headers к backend в этом режиме может получить 400;
live проверяется через настоящий HTTPS proxy:

```bash
curl --max-time 10 "https://yuriys-macbook-pro.tail893c10.ts.net/api/v1/health/live"
lsof -nP +c 0 -a -iTCP:8000 -sTCP:LISTEN
lsof -nP +c 0 -a -iTCP:11434 -sTCP:LISTEN
```

8000 и 11434 — только loopback. История доступна при недоступной модели; ready
может стать готовым чуть позже запуска API. Открытие терминала больше не нужно.

## 5. Tailscale, Ollama и питание

В System Settings → General → Login Items добавьте Ollama.app и Tailscale.app
в Open at Login / включите соответствующие настройки приложений. Если они уже
автоматически запускаются, не создавайте второй механизм. В macOS background
settings разрешите работу необходимых компонентов. Проверьте после login.

```bash
BUBLIK_TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
"$BUBLIK_TS_CLI" serve --bg --https=443 http://127.0.0.1:8000
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" funnel status
```

Тот же private endpoint, только tailnet; Funnel не включать. --bg сохраняет
Serve configuration, но не запускает Python/Ollama. Действующую grants policy
и её Save проверяйте отдельно — API checker не читает policy editor.
На телефоне Tailscale нужен и дома при использовании .ts.net URL. Пользовательский
LAN CA для этого URL не требуется; direct LAN URL требует установленного CA.

Mac должен бодрствовать и иметь сеть. На питании включите Battery → Options →
Prevent automatic sleeping on power adapter when the display is off. Экран
можно гасить, блокировку отключать не нужно. LaunchAgent не отменяет sleep,
закрытие крышки и отключение питания; не обещает серверную доступность 24/7.

## 6. Проверяемый restart без изменения истории

Используем существующий синтетический контрольный чат этапа 6. Не добавляйте в
него сообщения между initial/restart/reboot. Checker read-only, token остаётся
на Mac, содержимое диалога в JSON не записывается. NEW reports не перезаписываются.

```bash
python scripts/check_launchd_live.py \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --chat-id a13531f84dd941d3acbebd1d40cf1a63 \
  --output "$BUBLIK_STAGE7_DIR/initial.json"
```

Initial должен быть passed: private plist, state/PID owns localhost8000,
verified HTTPS/current runtime, ready/idle без gate, полная terminal history.
Только после passed и при отсутствии новых запросов с других устройств:

```bash
launchctl kill SIGTERM "gui/$(id -u)/local.bublik.private-ai.api"
```

Подождите восстановления live/ready, обычно несколько секунд; throttle может
задержать быстрые повторные старты примерно на 30 s. Не используйте kill -9 или
kickstart -k для обычного рестарта. Убедитесь, что state=running снова, затем:

```bash
python scripts/check_launchd_live.py \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --chat-id a13531f84dd941d3acbebd1d40cf1a63 \
  --kind restart --baseline "$BUBLIK_STAGE7_DIR/initial.json" \
  --output "$BUBLIK_STAGE7_DIR/after-restart.json"
```

Passed требует нового API PID при том же OS boot, той же конфигурации и
полного history hash/count, model/profile/source. Это не новая генерация.
Обновите чат на Mac/Android/iPhone, затем закройте терминалы: доступ остаётся.

## 7. Reboot

После успешного initial/restart и завершённых генераций перезагрузите Mac
обычным способом, войдите в аккаунт litdi. Не вводите serve вручную. Дождитесь
запуска Ollama/Tailscale и model readiness. После reboot shell variables пропали:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
source ../.venv/bin/activate
BUBLIK_STAGE7_DIR="$HOME/bublik-day30-stage7"
python scripts/check_launchd_live.py \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --chat-id a13531f84dd941d3acbebd1d40cf1a63 \
  --kind reboot --baseline "$BUBLIK_STAGE7_DIR/initial.json" \
  --output "$BUBLIK_STAGE7_DIR/after-reboot.json"
```

Passed требует нового kern.boottime epoch, того же полного history hash и
конфигурации. Повторённый PID после reboot допустим: PID не является boot witness.
Откройте контрольный чат на телефоне с mobile+Tailscale, убедитесь в истории.
После сохранения всех трёх reports можно отправить новое сообщение в другом
диалоге и проверить завершение/синхронизацию. Передайте три JSON и ручной результат.

## 8. Установка на домашний экран

Используйте один .ts.net URL с включённым Tailscale:

`https://yuriys-macbook-pro.tail893c10.ts.net/`

- Android / Chrome: меню ⋮ → «Установить приложение» или «Добавить на главный
  экран». Формулировка/тип установки зависит от версии браузера; automatic
  install prompt не гарантируется. Откройте значок, войдите при необходимости.
- iPhone / Safari: Share → Add to Home Screen; включите Open as Web App,
  если такой переключатель доступен. Откройте значок, войдите тем же username.
- Mac: установка из поддерживаемого браузера необязательна; обычная вкладка
  сохраняет все функции. Native Android/iOS app не создаём.

На каждом физическом телефоне проверьте: отдельный запуск с домашнего экрана,
история того же owner, один новый вопрос/сохранённый ответ, закрытие/reopen,
переключение Wi-Fi → mobile, возврат из background, logout/login и синхронизацию
с Mac. Укажите OS/browser versions и выглядит ли окно как standalone.
Off-line генерации нет; при Tailscale off на mobile endpoint недоступен.
Offline page не показывает кешированную историю после новой загрузки.
Данные браузера не следует считать резервной копией серверной базы.

## 9. Shutdown и recovery

Для обслуживания остановите supervisor, иначе KeepAlive снова запустит API:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
```

Plist остаётся для следующего login. Для временного Caddy stop используйте его
label. Для удаления автозапуска сначала bootout, затем удалите только соответствующий
plist в ~/Library/LaunchAgents; не удаляйте DB, CA/state или token files.

Текущий lifecycle ждёт завершения HTTP connections до 15 s, coordinator затем
даёт активной генерации 5 s и сохраняет interrupted/partial при отмене. Launchd
даёт процессу 60 s перед SIGKILL; это запас для обычного shutdown, не абсолютная
гарантия при OS/дисковом зависании. Неизвестное dispatch состояние сохраняет gate.
Reboot/crash не превращает interrupted ответ в completed, автоматического replay нет.
Запросы, ещё оставшиеся queued до dispatch, имеют прежнюю семантику durable queue.

Если ready сообщает inference_recovery_required, сначала bootout API, явно
перезапустите Ollama.app, выполните:

```bash
python -m bublik_service --db "/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3" recover-inference
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Gate снимается только при проверяемом OS engine epoch / no-dispatch, не по
одному /api/ps. Не создавайте новый DB и не удаляйте gate вручную. Реальный
active inference interruption — отдельная проверка этапа 8, не доказана idle restart.

## 10. Автоматические проверки и источники

```bash
python scripts/check_storage.py --output "$BUBLIK_STAGE7_DIR/offline.json"
python -m pip install -r requirements.browser.lock
python -m playwright install chromium
python scripts/check_pwa.py --output "$BUBLIK_STAGE7_DIR/pwa-fixture.json"
```

Fixture проверяет настоящий Chromium/TLS/SQLite, но synthetic engine и Linux
не доказывают physical installation, Mac launchd или reboot. Подробности и
проверенные результаты: [VALIDATION.stage7.ru.md](VALIDATION.stage7.ru.md).

Официальные источники, проверены 2026-10-10:

- [Apple: launchd user agents/lifecycle](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- [Apple: launchd.plist keys](https://github.com/apple-oss-distributions/launchd/blob/main/man/launchd.plist.5)
- [Tailscale: Serve / --bg](https://tailscale.com/docs/reference/tailscale-cli/serve)
- [web.dev: PWA installation](https://web.dev/learn/pwa/installation)
- [Apple: iPhone home-screen web app](https://support.apple.com/en-eg/guide/iphone/iphea86e5236/ios)
- [Apple: sleep settings](https://support.apple.com/en-gb/guide/mac-help/mchle41a6ccd/mac)
