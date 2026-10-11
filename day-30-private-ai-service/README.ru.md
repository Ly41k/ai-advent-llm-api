# День 30 — Bublik Private AI Service

Приватный AI-чат с локальной Qwen: MacBook выполняет inference и хранит историю,
Mac, Android и iPhone продолжают одни и те же диалоги. Другие приложения используют
версионированный HTTP API. Облачных LLM и автоматического fallback нет.

**Реализованы этапы 1–9.** Базовый runtime **0.8.0**, SQLite schema **2**, инструкция
**private-chat-v2**. На MacBook Pro M1 / 32 GB новый baseline прошёл **259/259
технических проверок и 13/13 проверок качества**; история после рестарта —
**11/11**, текущий LAN HTTPS/launchd — **6/6**. Синхронизация трёх устройств,
мобильный интернет и восстановление доступа после включения Tailscale подтверждены
пользователем. Результаты и границы доказательств: [FINAL_REPORT.ru.md](FINAL_REPORT.ru.md).

После курса оператор проверил archive/restore рабочей истории на том же Mac.
Физический перенос на другое оборудование и история старого console owner ещё не проверены. Сохранённая tailnet policy не прошла
независимый аудит; установка LAN CA на телефоны отложена. Это не скрытые PASS.

## Перенос истории после дня 30

Первое дополнение добавляет проверяемые SQLite-архивы и восстановление в новую
приватную базу с сохранением IDs диалогов, исходных сообщений и snapshots.
В восстановленной копии browser sessions удаляются, API tokens отзываются.
Runtime/API и поведение модели не меняются. Команды, ограничения и репетиция
переноса: [MEMORY_PORTABILITY.ru.md](MEMORY_PORTABILITY.ru.md). Архивы пока не
зашифрованы; снимки с queued/running или неопределённым inference не восстанавливаются
этим первым инструментом. Версионируемая память фактов ещё не реализована. Поиск обеих сторон сохранённой
переписки добавлен как отдельное расширение ниже.

## RAG по истории после курса — 0.9.1

Переключатель **«Искать в прошлых разговорах»** добавляет локальный FTS5-поиск
по всем сохранённым сообщениям пользователя и непустым terminal ответам Бублика
текущего владельца. Роль и статус сохраняются в источнике. До трёх
точных фрагментов с датой, IDs и SHA-256 сохраняются в snapshot генерации и
отображаются под ответом. Источник и окружающий разговор можно открыть на любом устройстве.

Индекс `memory-index/` — приватный восстановимый cache рядом с рабочей базой;
при добавлении RAG основная схема оставалась **2**. SQLite archive переносит историю и RAG snapshots,
индекс строится заново. Embeddings и дополнительные модели не используются;
поиск по словам не гарантирует нахождение перефразировок. В Web UI поиск включён
по умолчанию и может быть отключён вручную. API v1 без поля use_memory сохраняет
прежнее false для совместимости. При ошибке поиска RAG-запрос получает 503 без скрытого fallback.

[Установка и Mac-проверка](RAG_MEMORY.ru.md). Результаты дня 30 выше относятся к
0.8.0; реальные Qwen/телефоны на 0.9.1 проверяются отдельно. Источники в UI —
фрагменты, переданные модели, не автоматическое доказательство каждого её утверждения.

[Контракт непрерывной памяти](MEMORY_ARCHITECTURE.ru.md): оригиналы не заменяются
обобщениями и не удаляются по возрасту; summaries/facts — будущие слои.

## Русский и английский — 0.10.3

Две независимые настройки задают язык интерфейса и новых ответов. Они хранятся
на сервере у владельца и загружаются на всех устройствах. Принимаются только
`ru` и `en`; исходные сообщения и цитаты памяти сохраняют прежний текст.
Web UI явно передаёт язык ответа; он фиксируется в snapshot генерации.
API без нового поля сохраняет прежнее поведение.

Добавленная миграция переводит SQLite **2 → 3**. Archive/restore принимает обе
схемы; новые архивы включают языковые настройки. Перед обновлением нужен backup;
старый runtime не открывает schema 3. [Обновление и проверки](LANGUAGES.ru.md).
Инструкция направляет Qwen, но не гарантирует язык произвольного ответа.
FTS5 остаётся лексическим: semantic multilingual retrieval не добавлен.

0.10.3 усиливает языковую подсказку с явным приоритетом над языковыми пожеланиями вопроса к последнему вопросу только для inference.
Исходные сообщения не изменяются; подсказка сохраняется в snapshot и входит в
бюджет контекста. [Установка и проверка](LANGUAGE_EXPLICIT_HINT_FIX.ru.md).

## Устройство сервиса

| Компонент | Назначение |
|---|---|
| FastAPI / Uvicorn | API v1, browser sessions, авторизация, CSRF и лимиты; один процесс |
| SQLite WAL / FULL | Полная история, owners, задания, receipts, snapshots и миграции |
| Generation coordinator | Durable очередь, одна активная генерация, partial/terminal state |
| Ollama на `127.0.0.1:11434` | Qwen2.5:14b Q4_K_M; модель не загружается в Python API |
| Web UI / PWA manifest | Адаптивный чат, SSE/polling, установка на домашний экран |
| Tailscale Serve | Основной приватный HTTPS-доступ, включая мобильную сеть |
| Caddy LAN HTTPS | Дополнительный домашний путь с доверенным локальным CA |
| launchd LaunchAgents | Автозапуск API/Caddy после входа пользователя на Mac |

Телефон → HTTPS proxy → API/auth → транзакция SQLite → очередь → ContextBuilder
→ локальная Ollama → сохранённый ответ → SSE/polling на устройствах.
Компоненты и границы доверия: [ARCHITECTURE.ru.md](ARCHITECTURE.ru.md).

## Запуск на MacBook

В репозитории находится полная реализация. Команды ниже предназначены для новой
установки. У существующего сервиса сохраняйте рабочую базу и владельцев диалогов.
Обновление только Markdown-документации не требует рестарта API.

Python **3.13+**, macOS/POSIX, локальная Ollama с загруженной `qwen2.5:14b`.
Из корня checkout, для новой установки:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
cd day-30-private-ai-service
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -c 'from bublik_service import __version__; print(__version__)'
```

Если корневой `.venv` уже существует, используйте его; из каталога дня:
`source ../.venv/bin/activate`. Отдельный `.venv` внутри дня 30 не требуется.
Не запускайте второй `ollama serve`, если приложение Ollama уже слушает localhost.
Подготовка и эксплуатация: **[RUNBOOK.ru.md](RUNBOOK.ru.md)**.

Для новой установки создайте отдельную базу и пользователя:

```bash
BUBLIK_DATA_DIR="$HOME/bublik-private-ai"
BUBLIK_DB="$BUBLIK_DATA_DIR/chats.sqlite3"
python -m bublik_service --db "$BUBLIK_DB" init-db
python -m bublik_service --db "$BUBLIK_DB" user-add operator
python -m bublik_service --db "$BUBLIK_DB" doctor
```

Пароль вводится через getpass, минимум 12 символов. `.env` не читается автоматически.
`--db` ставится перед подкомандой. Без `--db` на macOS используется
`~/Library/Application Support/BublikPrivateAI/chats.sqlite3`;
`BUBLIK_DATA_DIR` меняет каталог по умолчанию.

Подключите Tailscale на Mac и телефонах к одному tailnet. Для проверенного macOS
приложения получите свой HTTPS hostname:

```bash
BUBLIK_TS_CLI="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
"$BUBLIK_TS_CLI" status
BUBLIK_TAIL_HOST="$("$BUBLIK_TS_CLI" status --json | python -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
BUBLIK_TAIL_URL="https://$BUBLIK_TAIL_HOST"
"$BUBLIK_TS_CLI" serve status
```

Включите MagicDNS/HTTPS certificates и задайте минимальные права доступа к Mac
TCP:443 по [RUNBOOK](RUNBOOK.ru.md). Сначала проверьте текущие routes. Если
443/root свободен, настройте Serve и запустите API:

```bash
"$BUBLIK_TS_CLI" serve --bg --https=443 http://127.0.0.1:8000
"$BUBLIK_TS_CLI" serve status
"$BUBLIK_TS_CLI" funnel status
python -m bublik_service --db "$BUBLIK_DB" serve --port 8000 \
  --trusted-loopback-proxy --origin "$BUBLIK_TAIL_URL"
```

Ожидается **tailnet only**, без публичного Funnel и проброса портов роутера.
Проверьте grants и legacy ACLs: узкое разрешение не отменяет широкое правило.
Подключение к tailnet не заменяет вход в приложение Бублика.

API слушает **только `127.0.0.1:8000`**, один worker, без reload. В proxy режиме
прямой plain HTTP корректно возвращает `secure_transport_required`.
Для установленного LaunchAgent второй ручной `serve` не запускайте.

## Телефон и домашняя сеть

На Android/iPhone подключите Tailscale к тому же tailnet, откройте HTTPS hostname
Mac и войдите тем же пользователем Бублика. API-ключ в браузер вводить не нужно.
Для `.ts.net` URL локальный CA не требуется. Tailscale нужен и дома, если используется
этот URL. Mac должен оставаться включённым, бодрствовать и быть подключённым к сети;
на телефоне можно отключить Wi-Fi и работать по мобильной сети.

Откройте тот же диалог — история хранится на сервере. Android: меню браузера →
установка/добавление на главный экран. iPhone: Safari → Поделиться → На экран «Домой».
PWA не делает inference или чтение личной истории офлайн: service worker и
persistent browser cache отсутствуют. На обоих телефонах установка подтверждена.

Прямой LAN путь `https://LAN_IP:8443` поддерживается Caddy. Для него нужны доверие
вашему CA на клиенте и согласованный LAN origin; Tailscale не обязателен.
Подробности: [STAGE6.ru.md](STAGE6.ru.md). Текущий Caddy/LAN путь проверен с Mac;
телефонные CA настройки отложены, основной путь — Serve.

## Повседневная работа и сон Mac

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
При спящем или отключённом от сети Mac чат недоступен. Подробности и recovery
прерванной генерации: [RUNBOOK.ru.md](RUNBOOK.ru.md).

## API, история и ограничения

[API.md](API.md) описывает `/api/v1`: live/ready, login/session/logout,
chats/history, send, generation status/SSE, retry, export и authenticated OpenAPI.
Прочим приложениям выдаются локальным CLI scoped, expiring, revocable Bearer tokens.
Браузер использует Secure/HttpOnly/SameSite=Strict cookie и exact Origin/CSRF.
Чужие chat/generation IDs возвращают 404; owner задаётся авторизацией.

| Ограничение | Значение |
|---|---:|
| Model context / max output / temperature | 8192 / 1024 / 0 |
| Запас контекста | 512; input upper bound ≤6656 |
| Одновременный inference / очередь | 1 / 8 ожидающих |
| Outstanding на owner | 3 |
| Принятые генерации / HTTP запросы на owner | 10 / 120 за скользящие 60 s |
| JSON body / текст пользователя | 32 KiB / 16 KiB UTF-8 |
| Срок queued задания | 600 s |

Полная история не обрезается при сокращении inference context. В модель передаётся
суффикс завершённых пар; исключённые ходы видны в metadata/UI. System prompt и новый
вопрос не обрезаются; oversize отклоняется до вставки сообщений. Счётчик — проверенная
консервативная byte-BPE верхняя граница, не точный tokenizer.

Idempotency сохраняет IDs при повторной доставке без дублирования сообщений или
новой inference quota. `202` означает сохранённое задание, а не готовый ответ.
Partial text и terminal status сохраняются; при недоступной модели история доступна.
Неизвестное состояние inference блокирует новые задания до явного проверенного
recovery. Старые v1 snapshots сохраняются при новых v2 ходах того же диалога.

UI не сохраняет API tokens, пароли, историю или черновики в localStorage/sessionStorage.
Ответы отображаются plain text; нет CDN/analytics. Access logs отключены, ошибки
не сериализуют личный input, секреты и upstream traceback. Launchd logs=/dev/null —
это ограничивает эксплуатационную диагностику. Backup API учитывает WAL и запрещает
перезапись файла. Restore в отдельную базу проверен оператором; retention и
off-host copies остаются отдельной задачей.

После запуска API, во втором терминале с заданным `BUBLIK_TAIL_URL`:

```bash
curl --max-time 10 "$BUBLIK_TAIL_URL/api/v1/health/live"
curl --max-time 10 -i "$BUBLIK_TAIL_URL/api/v1/chats"
```

Ожидается `200` / `{"status":"alive"}` и `401` без авторизации. Откройте тот же
HTTPS URL в браузере, войдите, создайте диалог и дождитесь сохранённого ответа.
Liveness сам по себе не доказывает готовность Qwen. Авторизованную readiness,
маршруты, коды ошибок и scopes токенов описывает [API.md](API.md).

## Проверки и документация

```bash
python scripts/verify_report.py reports/verified/languages-policy-v2-offline-20261011.json
python -W error::ResourceWarning scripts/check_storage.py
```

Первый вызов сверяет новые221/221 offline проверок с81 source files,
второй запускает полный текущий offline suite и создаёт новый отчёт. Прежние
RAG198/198, 143/143 и storage-only69/69 отчёты остаются историческими: новый RAG меняет runtime
и общий manifest. Хеши не являются подписью или доказательством сети/LLM.
Browser/PWA tests требуют `requirements.browser.lock` и Chromium. Исходные успешные
и неуспешные JSON в `reports/verified/` не перезаписаны.

Пользователь записал UI-видео с сообщениями на нескольких устройствах. Запись
не заменяет сохранённые отчёты технических и интеграционных проверок.

| Документ | Назначение |
|---|---|
| [RUNBOOK.ru.md](RUNBOOK.ru.md) | Установка, повседневный запуск, телефон, 502/recovery |
| [FINAL_REPORT.ru.md](FINAL_REPORT.ru.md), [ACCEPTANCE.ru.md](ACCEPTANCE.ru.md) | Итоговые результаты, критерии и ограничения |
| [API.md](API.md), [ARCHITECTURE.ru.md](ARCHITECTURE.ru.md) | Работающий контракт и устройство сервиса |
| [CONSOLE_VIDEO.ru.md](CONSOLE_VIDEO.ru.md) | Необязательная терминальная демонстрация; UI-видео записано пользователем |
| [VALIDATION.stage8.ru.md](VALIDATION.stage8.ru.md), [PROMPT_V2.ru.md](PROMPT_V2.ru.md) | Live evidence и переход v1→v2 |
| [STAGE7.ru.md](STAGE7.ru.md), [VALIDATION.stage7.ru.md](VALIDATION.stage7.ru.md) | launchd/PWA и исторический reboot identity mismatch |
| [PLAN.ru.md](PLAN.ru.md), [BACKLOG.ru.md](BACKLOG.ru.md) | Границы, отложенный backup и исследование Rust |

Корневые README обновлены на этапе 9. Это меняет корпус дня 21: перед следующим
строгим RAG live run пересоберите индекс. Сам день 30 индекс не использует;
предыдущие реализации, их базы и исторические отчёты не изменены.

[English](README.md)
