# Этап 6 — домашняя сеть и приватный мобильный доступ

Версия 0.5.0. Этап 5 на вашем Mac: Web UI + настоящая Qwen, 19/19 checks.

Исправление ложного `engine_process_unverified` при большом списке процессов
на Mac: [ENGINE_PROCESS_FIX.ru.md](ENGINE_PROCESS_FIX.ru.md). Новый offline report
— `stage6-engine-fix-offline.json`; прежние reports остаются историческими.
Здесь настраиваются реальные сетевые пути. В среде разработки проверен Caddy,
TLS, HTTP и Chromium с synthetic inference; ваш LAN/телефон/Tailscale ещё not_run.

| Путь | Адрес | Что нужно на клиенте |
|---|---|---|
| Домашний Wi-Fi/LAN | `https://LAN_IP:8443/` | Один раз доверить домашнему root CA; Tailscale не обязателен |
| Вне дома / мобильный интернет | `https://NODE.TAILNET.ts.net/` | Tailscale на Mac и телефоне; публично доверенный HTTPS-сертификат |

Оба пути ведут в один API, одну базу и один owner. Cookie у LAN IP и tailnet
hostname отдельные: войдите тем же `yuriy`, затем откройте прежний chat ID.
Полная история остаётся общей. Ollama/Qwen вычисляет на Mac, cloud LLM нет.
Tailscale — сеть/координация и при необходимости зашифрованный relay, не inference.
Mac должен быть включён, бодрствовать, API/Caddy/Ollama работать. Автозапуск — этап 7.

## 1. Обновить код

Остановите API через Ctrl-C, дождитесь завершения shutdown. Не запускайте два
сервиса с одной рабочей базой. В активном `.venv`:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
BUBLIK_UPDATE_DIR="$(mktemp -d)"
unzip "$HOME/Downloads/day30-stage6.zip" -d "$BUBLIK_UPDATE_DIR"
ditto "$BUBLIK_UPDATE_DIR/day-30-private-ai-service" .
python -m pip install -e .
python -c 'import bublik_service; print(bublik_service.__version__)'
```

Ожидается `0.5.0`. Архив полный; каталог дня не удаляйте. Рабочая база, токен и
сертификаты вне репозитория сохраняются, SQL schema=2, миграций здесь нет.
Backup/restore и перенос этапа 3 по вашему решению остаются после полной реализации.

## 2. Установить Caddy и определить LAN IP

Если Homebrew уже установлен:

```bash
brew install caddy
caddy version
networksetup -listallhardwareports
ipconfig getifaddr en0
```

У Wi-Fi интерфейс может быть `en1`: используйте имя из `networksetup`.
IP должен быть адресом Mac в домашней сети: 192.168.x.x / 10.x.x.x / 172.16–31.x.x.
Не используйте 127.0.0.1, 0.0.0.0 или Tailscale IP. Желательно закрепить DHCP lease
Mac в роутере. Port forwarding на роутере для этого сценария не требуется.
Не включайте `brew services start caddy`: сейчас запускается наш явный config.

В том же терминале задайте IP через фактический интерфейс и убедитесь, что он не пуст:

```bash
BUBLIK_LAN_IP="$(ipconfig getifaddr en0)"
printf '%s\n' "$BUBLIK_LAN_IP"
BUBLIK_LAN_URL="https://$BUBLIK_LAN_IP:8443"
BUBLIK_STAGE4_DIR="/Users/litdi/bublik-day30-stage4.V1EM3F"
BUBLIK_STAGE6_DIR="$HOME/bublik-day30-stage6"
python scripts/configure_network.py \
  --lan-ip "$BUBLIK_LAN_IP" --output "$BUBLIK_STAGE6_DIR"
printf '%s\n' "$BUBLIK_STAGE6_DIR"
```

Постоянный путь на вашем Mac: `/Users/litdi/bublik-day30-stage6`.
Новый терминал не наследует локальные shell variables другого окна. В каждом
следующем окне снова задавайте `BUBLIK_STAGE6_DIR="$HOME/bublik-day30-stage6"` и IP.
Generator создаёт НОВЫЙ каталог, отказывается перезаписывать существующий config/CA,
валидирует значения до подстановки, создаёт каталоги 0700 и config 0600.
Если каталог уже существует после предыдущего запуска, не генерируйте его заново:
используйте созданный Caddyfile/CA. Не удаляйте его, чтобы «исправить» existing output.
Если tailnet hostname уже известен, можно добавить `--tailnet-host HOST.ts.net` с
полным именем из шага 9; для первого LAN запуска это не требуется.

## 3. Запустить API — терминал A

Используется прежняя рабочая база. Подставьте фактический LAN IP из шага 2:

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
BUBLIK_STAGE4_DIR="/Users/litdi/bublik-day30-stage4.V1EM3F"
BUBLIK_LAN_IP="$(ipconfig getifaddr en0)"
BUBLIK_LAN_URL="https://$BUBLIK_LAN_IP:8443"
python -m bublik_service --db "$BUBLIK_STAGE4_DIR/chats.sqlite3" \
  serve --port 8000 --trusted-loopback-proxy --origin "$BUBLIK_LAN_URL"
```

Не добавляйте старые `--tls-cert/--tls-key`: TLS завершается в Caddy/Serve.
API жёстко слушает 127.0.0.1:8000, Uvicorn proxy_headers=False. Explicit proxy mode
принимает только raw loopback peer + один `X-Forwarded-Proto: https`; Host allowlist
и same-origin CSRF сохраняются. XFF и Tailscale identity не авторизуют пользователя.
Незащищённый прямой вход на `http://127.0.0.1:8000/` теперь корректно отклоняется.

## 4. Запустить LAN HTTPS — терминал B

В этом новом окне задайте постоянный каталог явно:

```bash
BUBLIK_STAGE6_DIR="$HOME/bublik-day30-stage6"
XDG_DATA_HOME="$BUBLIK_STAGE6_DIR/caddy-data" \
XDG_CONFIG_HOME="$BUBLIK_STAGE6_DIR/caddy-config" \
  caddy validate --config "$BUBLIK_STAGE6_DIR/Caddyfile"

XDG_DATA_HOME="$BUBLIK_STAGE6_DIR/caddy-data" \
XDG_CONFIG_HOME="$BUBLIK_STAGE6_DIR/caddy-config" \
  caddy run --config "$BUBLIK_STAGE6_DIR/Caddyfile"
```

Сначала явно задайте переменную в этом окне, иначе получится путь `/Caddyfile`.
Config: только конкретный LAN IP:8443, HTTP/1.1+HTTP/2, admin off, HTTP redirect
listener отключён, TLS internal. Access logs не включены; runtime logger discard
исключает личные URL/headers из proxy logs. При ошибках используйте health probes,
`caddy validate` и статус процесса. Сохранять подробные debug logs по умолчанию нельзя.
Caddy сам выпускает/обновляет короткоживущие LAN leaf certificates. Его каталог
данных с CA/private keys постоянный: не удаляйте его при обновлении кода.

## 5. Доверить LAN сертификату на Mac — терминал C

После старта Caddy в этом окне заново задайте пути/IP (замените en0, если Wi-Fi
у вас на другом интерфейсе):

```bash
BUBLIK_STAGE6_DIR="$HOME/bublik-day30-stage6"
BUBLIK_STAGE4_DIR="/Users/litdi/bublik-day30-stage4.V1EM3F"
BUBLIK_LAN_IP="$(ipconfig getifaddr en0)"
BUBLIK_LAN_URL="https://$BUBLIK_LAN_IP:8443"
BUBLIK_LAN_CA="$BUBLIK_STAGE6_DIR/caddy-data/caddy/pki/authorities/local/root.crt"
ls -l "$BUBLIK_LAN_CA"
openssl x509 -in "$BUBLIK_LAN_CA" -noout -fingerprint -sha256
security add-trusted-cert -r trustRoot \
  -k "$HOME/Library/Keychains/login.keychain-db" "$BUBLIK_LAN_CA"
curl --cacert "$BUBLIK_LAN_CA" "$BUBLIK_LAN_URL/api/v1/health/live"
curl --cacert "$BUBLIK_LAN_CA" -i "$BUBLIK_LAN_URL/api/v1/chats"
```

Ожидается live 200/alive и chats 401 без логина. Импортируется ваш root.crt,
не чужой сертификат, не private key. macOS может запросить подтверждение.
Полностью завершите Chrome через Cmd-Q и откройте заново **LAN URL**, войдите `yuriy`.
Ожидается HTTPS без certificate warning. Все ресурсы UI локальные, HTTP/mixed content
не нужен. Если warning остаётся: DevTools → Security покажет причину; проверьте
hostname/SAN, дату, цепочку и доверие CA, а не обходите предупреждение.
На скриншоте этапа 5 «Certificate is valid» само по себе не объясняет общий warning.

## 6. Подключить настоящий телефон через домашний Wi-Fi

Телефон и Mac должны быть в одной доступной LAN (guest Wi-Fi/client isolation могут
блокировать связь). Отключите Tailscale на телефоне для чистой LAN проверки.
Передайте только публичный root certificate через AirDrop/USB/личный доверенный
канал; закрытые `root.key`, `intermediate.key`, `key.pem`, API token не передавайте.

Для удобства передачи на iPhone создайте DER certificate:

```bash
openssl x509 -in "$BUBLIK_LAN_CA" -outform DER \
  -out "$BUBLIK_STAGE6_DIR/bublik-lan-root.cer"
```

- **iOS:** установите certificate profile, затем Settings → General → About →
  Certificate Trust Settings → включите полное доверие вашему CA. Самой установки
  профиля недостаточно. Сверьте отпечаток/имя с созданным на Mac сертификатом.
- **Android:** Settings → Security & privacy → дополнительные security settings →
  Encryption & credentials / Install certificate → **CA certificate**. Названия
  отличаются у производителей; нужен именно CA для браузерного HTTPS, не Wi-Fi
  client certificate. Сверьте отпечаток. Проверка нужна в реальном Chrome.

Откройте на телефоне LAN URL из шага 2: `https://IP_MAC:8443/`.
`localhost` на телефоне означает сам телефон. Войдите тем же `yuriy`, откройте
существующий диалог, отправьте уточнение; на Mac обновите историю ↻ и продолжите.
Проверьте клавиатуру, кнопку отправки, список чатов, длинный текст без горизонтальной
прокрутки, возврат из фона и logout. После настройки CA нет необходимости обходить
HTTPS warning. На OS может отображаться факт установки пользовательского CA;
это отличается от ошибки сертификата сайта.

## 7. Автоматические проверки LAN

В окне C, в активном venv, задайте пути/IP из предыдущих шагов:

```bash
python scripts/check_network_live.py \
  --network lan --url "$BUBLIK_LAN_URL" --username yuriy \
  --ca-file "$BUBLIK_LAN_CA" \
  --output "$BUBLIK_STAGE6_DIR/lan-api-$(date +%Y%m%d-%H%M%S).json"
```

Пароль запрашивается скрыто. Проверяются verified TLS, assets, auth/CSRF/history,
runtime manifest, недоступность портов API/Ollama по указанному адресу.
Запуск на Mac доказывает доступ Mac к LAN listener, **не другое устройство**.
Если есть второй компьютер, запустите этот же checker там с копией исходников и
публичным root.crt, паролем через getpass. Checker использует Python 3.13+ и зависимости
проекта на Mac/Linux (POSIX), а сам HTTP API доступен любому стандартному HTTPS
клиенту на Windows/Android/iOS. На телефоне Python/Playwright не требуется.
Это отдельное реальное API испытание.

Если optional Playwright ещё не установлен:

```bash
python -m pip install -r requirements.browser.lock
python -m playwright install chromium
```

```bash
python scripts/check_network_ui_live.py \
  --network lan --url "$BUBLIK_LAN_URL" --username yuriy \
  --ca-file "$BUBLIK_LAN_CA" \
  --output "$BUBLIK_STAGE6_DIR/lan-ui-$(date +%Y%m%d-%H%M%S).json"
```

Три реальные Qwen turn через Caddy, две browser sessions, обычное browser TLS trust
(без `ignoreHTTPS`/pin), SSE/sync/reload. Обе сессии на компьютере: это не телефон.
HTTP generation quota=10/min, login=5/min. Между несколькими проверками/логинами
при 429 выдержите Retry-After; не ослабляйте production quota ради теста.

## 8. Сохранить проверяемый отчёт Mac → настоящий телефон

Старый private API token остаётся на Mac. Подготовьте отдельный контрольный диалог:

```bash
python scripts/check_device_handoff.py prepare \
  --network lan --url "$BUBLIK_LAN_URL" \
  --ca-file "$BUBLIK_LAN_CA" \
  --token-file "$BUBLIK_STAGE4_DIR/check-token.json" \
  --output "$BUBLIK_STAGE6_DIR/lan-phone-prepare.json"
```

Скрипт выдаст `open_on_phone` и `send_on_phone`. На настоящем телефоне откройте эту
ссылку, войдите `yuriy` и отправьте **ровно указанную контрольную фразу**. Дождитесь
ответа, затем на Mac откройте тот же chat и обновите историю. Не добавляйте других
сообщений в этот контрольный диалог до verify. После этого:

```bash
python scripts/check_device_handoff.py verify \
  --network lan --url "$BUBLIK_LAN_URL" --ca-file "$BUBLIK_LAN_CA" \
  --token-file "$BUBLIK_STAGE4_DIR/check-token.json" \
  --challenge "$BUBLIK_STAGE6_DIR/lan-phone-prepare.json" \
  --device android --connection wifi --confirm-physical-device \
  --output "$BUBLIK_STAGE6_DIR/lan-phone-verify.json"
```

Для iPhone замените `--device android` на `--device ios`.
Verify ничего не генерирует: проверяет неизменность seed IDs/content hash, ровно
один дополнительный user/assistant turn, точное слово из контекста, completed и
context bounds. Это объективная серверная часть. Физический телефон/тип сети —
отдельное ручное подтверждение; CLI flag не считается независимым измерением.
Сохраните скриншот контрольного диалога и сообщите модель телефона/браузер.
Отчёты не содержат паролей/токенов/личных диалогов; только контрольные данные.

## 9. Настроить Tailscale для доступа вне дома

Установите официальный Tailscale на Mac и телефон, войдите в свой личный tailnet,
подключите оба устройства. На Mac предпочтительно official standalone app;
существующий App Store вариант для Serve ports тоже поддерживается. Не устанавливайте
второй конкурирующий tailscaled поверх уже работающего приложения.
В терминале команды доступны через встроенный executable:

```bash
BUBLIK_TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
"$BUBLIK_TS_CLI" version
"$BUBLIK_TS_CLI" status
BUBLIK_TAIL_HOST="$("$BUBLIK_TS_CLI" status --json | python -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
printf '%s\n' "$BUBLIK_TAIL_HOST"
BUBLIK_TAIL_URL="https://$BUBLIK_TAIL_HOST"
```

Нужен полный `node.tailnet.ts.net`, не короткое имя и не IP. Если есть рабочая
команда `tailscale` в PATH вместо приложения, используйте её реальный путь.
Откройте Tailscale admin → DNS: MagicDNS и HTTPS Certificates. Для выпуска публичного
сертификата имя node/tailnet попадает в Certificate Transparency; назовите node
нейтрально, например `bublik`, без личных данных. Чаты туда не публикуются.

В Access controls ограничьте доступ своими устройствами/user к Mac TCP:443.
Пример с policy tests: `deploy/tailnet-policy.example.jsonc`. Замените placeholders
на свой login и Mac Tailscale IPv4, проверьте editor tests перед сохранением.
Grants additive: старые broad allow rules могут разрешать больше; приведённый
fragment сам по себе их не отменяет. Не перезаписывайте чужую/рабочую policy.
Бублик по-прежнему требует собственный логин и owner authorization.

## 10. Добавить tailnet origin и включить Serve

Остановите API в окне A. Задайте там реальные LAN URL и tailnet URL из шагов 2/9;
запустите с той же базой и двумя разрешёнными адресами:

```bash
python -m bublik_service --db "$BUBLIK_STAGE4_DIR/chats.sqlite3" \
  serve --port 8000 --trusted-loopback-proxy \
  --origin "$BUBLIK_LAN_URL" --origin "$BUBLIK_TAIL_URL"
```

Caddy продолжает работать со старым постоянным каталогом. Ничего не нужно заново
генерировать, удалять или переносить. В окне C, где задан BUBLIK_TS_CLI:

```bash
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" serve --bg --https=443 http://127.0.0.1:8000
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" funnel status
```

Сначала убедитесь, что 443/root не занят другим Serve service. Если занят, остановитесь
и согласуйте другой port/config, не перезаписывайте чужой сервис. Не используйте Funnel:
он публичный; нужен Serve для вашего tailnet. `--bg` сохраняет Serve config в daemon,
но не запускает API/Ollama автоматически. Serve сам управляет HTTPS-сертификатом.
Если Funnel уже включён для этого endpoint, отключите его отдельно до испытаний.

Откройте `BUBLIK_TAIL_URL` на Mac и телефоне: публично доверенный HTTPS без установки
домашнего CA для этого адреса. Войдите `yuriy`, история та же. LAN origin cookie
не переносится в tailnet origin, но данные остаются общими на сервере.

## 11. Реальный телефон через мобильный интернет

**На телефоне выключите Wi-Fi, оставьте мобильные данные и Tailscale connected.**
Откройте tailnet URL, войдите и продолжите прежний диалог. На Mac проверьте новую
реплику. Для отдельного сохраняемого контроля используйте prepare/verify из шага 8,
заменив `--network lan --url "$BUBLIK_LAN_URL" --ca-file "$BUBLIK_LAN_CA"` на
`--network tailnet --url "$BUBLIK_TAIL_URL"`, имена на `mobile-phone-prepare.json` /
`mobile-phone-verify.json` и `--connection mobile`. Проверьте этот контроль с
физического телефона; выполнение второго turn на Mac не считается mobile test.

Дополнительно на Mac:

```bash
python scripts/check_network_live.py \
  --network tailnet --url "$BUBLIK_TAIL_URL" --username yuriy \
  --output "$BUBLIK_STAGE6_DIR/tailnet-api-$(date +%Y%m%d-%H%M%S).json"
python scripts/check_network_ui_live.py \
  --network tailnet --url "$BUBLIK_TAIL_URL" --username yuriy \
  --output "$BUBLIK_STAGE6_DIR/tailnet-ui-$(date +%Y%m%d-%H%M%S).json"
```

Не добавляйте --ca-file старого localhost сертификата для публичного tailnet TLS.
Выйдите из Бублика, отключите Tailscale на телефоне при выключенном Wi-Fi: tailnet
чат должен стать недоступен. Это дополнительная ручная negative check.

## 12. Проверить изоляцию Ollama и приёмку

На Mac:

```bash
lsof -nP -iTCP:11434 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:8443 -sTCP:LISTEN
```

Ollama — только 127.0.0.1/::1; API — 127.0.0.1:8000; Caddy — выбранный LAN IP:8443.
`*:11434`, `0.0.0.0:11434`, `[::]:11434` — FAIL. Не расширяйте OLLAMA_HOST ради LAN.
Adapter doctor также проверяет loopback listener, но remote probe обязателен отдельно.
С другого устройства LAN/tailnet запросы к портам 8000 и 11434 должны быть недоступны;
HTTP API с другого компьютера можно проверить checker шага 7. Для телефона можно
использовать browser GET `http://IP_MAC:11434/api/tags` (в LAN) — не должен открыться;
приложите результат вместе с `lsof`. Не считайте один timeout достаточным доказательством
listener isolation: сопоставляйте positive HTTPS path + локальный listener + remote probe.

Приёмка: LAN API/браузер с другого устройства, настоящий телефон Wi-Fi без Tailscale,
настоящий телефон mobile+Tailscale, один диалог между Mac/телефоном, сертификат без
warning, UI keyboard/background/reopen, no-auth 401, port isolation. Приложите JSON из
шагов 7/8/11, ручное описание телефона/условий сети и control screenshots без секретов.
История после API restart уже проверялась на этапе 4; повторите в браузере обоих
сетевых путей. Reboot/autostart/PWA — этап 7, ресурсные измерения/качество — этап 8.

Остановить тестовый LAN proxy: Ctrl-C в окне B. Отключить только наш Serve endpoint:
`"$BUBLIK_TS_CLI" serve --https=443 off` после проверки status. Не вызывайте global
reset над shared config. Старый direct TLS запуск этапа 5 сохраняется без флага proxy.

## Источники и ограничения

Официальная документация: [Caddy TLS internal](https://caddyserver.com/docs/caddyfile/directives/tls),
[Caddy data directories](https://caddyserver.com/docs/conventions),
[Caddy options](https://caddyserver.com/docs/caddyfile/options),
[Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve),
[HTTPS/CT](https://tailscale.com/docs/how-to/set-up-https-certificates),
[Grants](https://tailscale.com/docs/reference/syntax/grants),
[macOS CLI](https://tailscale.com/docs/reference/tailscale-cli),
[iOS trust](https://support.apple.com/en-us/102390),
[Android certificates](https://support.google.com/pixelphone/answer/2844832).

Приватность предполагает доверенный Mac/OS и домашний CA. Local OS process может
обратиться к loopback proxy backend; это явная доверенная граница, не защита от
компрометации самого Mac. Login/bootstrap quota агрегируется по loopback proxy peer
и username/owner; XFF не используется для её обхода. Сеть и TLS не дают прав на чужие
чаты. Лишние модели не загружаются; параметры Qwen и context policy здесь не менялись.
Нет утверждений о снижении RAM. Полный результат: VALIDATION.stage6.ru.md.
