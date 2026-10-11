# Этап 4 — HTTP API, аутентификация и ограничения

Этап 4 принят на Mac: HTTP+Qwen 65/65, restart history 7/7, HTTPS/CSRF 14/14;
operational Ollama off/on подтверждён пользователем вручную. Оригинальные JSON
сохранены в reports/verified. Web UI — STAGE5.ru.md; LAN/мобильная сеть — этап 6.
Сейчас API слушает **только 127.0.0.1**. Облачных LLM/fallback нет.

## 1. Обновление и offline-проверка

Остановите прежний terminal chat/API. Перед обновлением рабочей базы сделайте
backup **командой предыдущей версии**, в новый файл. Конструктор новой версии
применяет миграцию 002 автоматически, поэтому её `backup` уже копирует схему 2.
Для проверки ниже используем отдельную базу и не меняем рабочую историю.

В активном Python 3.13 venv, из `day-30-private-ai-service/`:

```bash
python --version
python -m pip install -r requirements.lock
python -W error::ResourceWarning scripts/check_storage.py
python scripts/verify_report.py reports/verified/stage4-quota-fix-offline.json
```

Второй вызов сравнивает сохранённый Linux-отчёт с исходниками. Для своего Mac-отчёта
передайте путь, который вывел `check_storage.py`. Все тесты должны пройти;
проверка хешей не является подписью или доказательством real Qwen/телефона.
Нужен `openssl` для автоматического теста настоящего HTTPS-сокета.

## 2. Отдельная база и пользователь

В первом терминале:

```bash
BUBLIK_STAGE4_DIR=$(mktemp -d "$HOME/bublik-day30-stage4.XXXXXX")
BUBLIK_STAGE4_DB="$BUBLIK_STAGE4_DIR/chats.sqlite3"
python -m bublik_service --db "$BUBLIK_STAGE4_DB" init-db
python -m bublik_service --db "$BUBLIK_STAGE4_DB" storage-status
python -m bublik_service --db "$BUBLIK_STAGE4_DB" user-add yuriy
python -m bublik_service --db "$BUBLIK_STAGE4_DB" token-create yuriy \
  --label stage4-check --output "$BUBLIK_STAGE4_DIR/check-token.json"
echo "$BUBLIK_STAGE4_DIR"
```

Пароль вводится через getpass дважды, минимум 12 символов; не передавайте его
аргументом CLI. Ожидается schema_version=2, WAL, FULL/2, integrity=ok, ноль FK
violations. `token-create --output` создаёт новый файл 0600, не перезаписывает
существующий и не печатает секрет. Не включайте token JSON в отчёт или git.

CLI также поддерживает `token-list USER`, `token-revoke USER TOKEN_ID`,
`password-set USER`. Смена пароля отзывает все browser sessions и API tokens
этого пользователя. По умолчанию токен действует 30 суток; доступны `--days`
1–365 и `--scopes chats:read,chats:write,chats:export,service:read`.

## 3. Запуск HTTP API с Qwen

Ollama должна быть запущена локально с `qwen2.5:14b` Q4_K_M. Не запускайте
параллельно другие Ollama-клиенты/модели во время приёмки. Проверка остаётся
такой же, как на этапе 3: literal loopback, version/digest/template/OS epoch,
без cloud-моделей и без скрытого перезапуска Ollama.

В первом терминале:

```bash
python -m bublik_service --db "$BUBLIK_STAGE4_DB" doctor
python -m bublik_service --db "$BUBLIK_STAGE4_DB" serve
```

Один процесс/worker, порт 8000, без reload и без доверия к forwarded headers.
Второй экземпляр/terminal chat с той же базой не получит worker lease.

Во втором терминале активируйте тот же venv и перейдите в каталог дня 30.
Подставьте **фактический путь**, выведенный `echo` в предыдущем шаге:

```bash
BUBLIK_STAGE4_DIR="/Users/ВАШ_ПОЛЬЗОВАТЕЛЬ/bublik-day30-stage4.XXXXXX"
curl -i http://127.0.0.1:8000/api/v1/health/live
curl -i http://127.0.0.1:8000/api/v1/chats
python scripts/check_http_live.py \
  --token-file "$BUBLIK_STAGE4_DIR/check-token.json" \
  --output "$BUBLIK_STAGE4_DIR/http-live.json"
```

Ожидается live=200, protected chats без auth=401, JSON-отчёт status=passed.
Скрипт создаёт только синтетические чаты; проверяет 10 последовательных
multi-turn запросов, строгие контрольные ответы, free idempotent replay,
context overflow без записи, 429 с Retry-After и три конкурентных admission
после ожидания полного скользящего окна (не менее 61 s после 429). Проверяет server/runtime hashes, model identity, actual
prompt counts <= bound; сохраняет ответы, статусы, queue/TTFT/latency/token
metrics и контрольные хеши истории. Пароли/токены не сохраняются в отчёте.

Лимит — 10 **успешных admission** за скользящие 60 секунд. Если первые 10
генераций заняли больше минуты, rate-check может не получить 429: скрипт
запишет failed, а не выдаст это за доказательство лимита. Это отдельное
ограничение сценария измерения; сведения о пройденных случаях сохраняются.
Новый отчёт всегда требует нового имени, перезаписи нет.

## 4. Сохранение после рестарта

Дождитесь завершения проверок, остановите `serve` через Ctrl-C в первом
терминале и запустите ту же команду с **той же базой** снова. Во втором:

```bash
python scripts/check_http_live.py \
  --token-file "$BUBLIK_STAGE4_DIR/check-token.json" \
  --history-from "$BUBLIK_STAGE4_DIR/http-live.json" \
  --output "$BUBLIK_STAGE4_DIR/http-after-restart.json"
```

Ожидается passed: все четыре chat ID и полные страницы сохранённой истории
совпали по хешам. Токен переживает restart. Проверка предполагает, что между
отчётом и сравнением вы не добавляли сообщения в синтетические чаты.
Не копируйте живой sqlite3 вручную вместо backup API.

## 5. Реальный HTTPS-вход и CSRF

Browser session не разрешается через plain HTTP даже на localhost. Secure cookie
не отключается для development. Для локальной проверки сертификата создаём
частный временный сертификат; доверять ему на телефоне сейчас не требуется.

Во втором терминале, с установленным BUBLIK_STAGE4_DIR:

```bash
umask 077
mkdir "$BUBLIK_STAGE4_DIR/tls"
cat > "$BUBLIK_STAGE4_DIR/tls/localhost.cnf" <<'CONFIG'
[req]
distinguished_name=dn
x509_extensions=ext
prompt=no
[dn]
CN=localhost
[ext]
subjectAltName=DNS:localhost,IP:127.0.0.1
basicConstraints=critical,CA:TRUE
keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign
extendedKeyUsage=serverAuth
CONFIG
openssl req -x509 -nodes -newkey rsa:2048 -days 7 \
  -config "$BUBLIK_STAGE4_DIR/tls/localhost.cnf" \
  -keyout "$BUBLIK_STAGE4_DIR/tls/key.pem" \
  -out "$BUBLIK_STAGE4_DIR/tls/cert.pem"
```

Остановите plain HTTP сервер в первом терминале, запустите HTTPS:

```bash
python -m bublik_service --db "$BUBLIK_STAGE4_DB" serve --port 8443 \
  --tls-cert "$BUBLIK_STAGE4_DIR/tls/cert.pem" \
  --tls-key "$BUBLIK_STAGE4_DIR/tls/key.pem"
```

Во втором терминале:

```bash
python scripts/check_browser_https.py --username yuriy \
  --ca-file "$BUBLIK_STAGE4_DIR/tls/cert.pem" \
  --output "$BUBLIK_STAGE4_DIR/https-auth.json"
```

Введите пароль аккаунта. Ожидается passed: сертификат проверен, bootstrap/login,
Secure/HttpOnly/SameSite cookie, rotation, обязательный CSRF и Origin, отказ
при ambiguous credentials, logout/revocation. Скрипт создаёт один пустой
синтетический чат и не делает inference. Секреты не пишет в отчёт.
Это настоящий HTTPS-клиент, но **не тест браузерного движка/Web UI**.
`curl -k`, `verify=False` и отключение Secure cookie не используются.

## 6. Недоступная Ollama и recovery

После завершённых генераций остановите Ollama обычным способом. API live
остаётся 200; authenticated history — 200; ready становится 503 максимум
через 5 секунд, новая генерация — 503 model_unavailable без вставки сообщений.
После восстановления Ollama readiness обновится, новые запросы снова доступны.
Операционное off/on на Mac проверяется вручную, не доказано synthetic fixture.

Если ответ был оборван во время вычисления, сохраняются partial text и terminal
status, а неизвестное состояние engine блокирует новые admission. В этом
случае остановите API, выполните явный restart Ollama, затем:

```bash
python -m bublik_service --db "$BUBLIK_STAGE4_DB" recover-inference
python -m bublik_service --db "$BUBLIK_STAGE4_DB" serve
```

Gate снимается только по проверенному новому OS epoch/отсутствию orphan runners
или подтверждённому отсутствию dispatch. Один `/api/ps` не доказывает idle.
Никаких автоматических replay inference/cloud fallback нет. Подробности — STAGE3.ru.md.

## 7. Перенос реальной истории этапа 3

Этот необязательный пункт и operational backup отложены пользователем до полной
реализации дня 30. Для текущих проверок отдельной базы этапа 4 он не нужен.

История привязана к owner ID. После предварительного backup предыдущей версией,
остановки terminal chat и миграции той же рабочей базы включите пароль
**существующему владельцу**, например:

```bash
python -m bublik_service --db "/ПУТЬ/К/РАБОЧЕЙ/chats.sqlite3" password-set local-stage3-operator
```

Затем создайте ему токен или войдите этим username. Если создать отдельного
`yuriy`, старые чаты другого owner не станут его чатами автоматически.
Owner IDs, chat/message/generation IDs и прежние context/profile snapshots
не переписываются. Старую версию сервиса к схеме 2 не подключайте: она
корректно откажется открывать более новую схему.

## 8. Что отправить для приёмки

Mac offline JSON, `http-live.json`, `http-after-restart.json`, `https-auth.json`.
Не отправляйте рабочую базу, private token JSON, cookie jar, пароль или TLS key.
LAN, телефон через мобильную сеть, Web UI/PWA, launchd/reboot и физические
замеры ресурсов всё ещё not_run. Rust не внедряется; видео — после завершения.


## Исправление ожидания квоты (после Mac-проверки этапа 4)

106/106 offline tests прошли на MacBook (исходный Mac JSON сохранён отдельно).
В live checker обнаружен дефект: Retry-After сообщает время до освобождения
первого слота, а не всей квоты. При последовательных admission старый скрипт
после этого отправлял три запроса и мог получить [202,429,429].

Исправленный checker ждёт полное окно: max(61, Retry-After+1) секунд после
контрольного 429. API rate limit и история не менялись, сервер перезапускать
для этого исправления не требуется. Три регрессионных теста используют реальную
SQLite quota и виртуальное время; они не являются live-доказательством Qwen.

Теперь отчёт также содержит concurrent_admissions с HTTP status каждого запроса
и безопасным error code, а при failed — имя failed_check. Тексты upstream
ошибок и секреты не сохраняются. Запустите повторно с новым именем отчёта:

```bash
python scripts/check_http_live.py \
  --token-file "$BUBLIK_STAGE4_DIR/check-token.json" \
  --output "$BUBLIK_STAGE4_DIR/http-live-v2.json"
```

Старый failed http-live.json сохраняйте без изменения: он нужен для подтверждения
точной причины предыдущего прогона. После passed используйте http-live-v2.json
как --history-from в проверке после restart и новое имя результата.
