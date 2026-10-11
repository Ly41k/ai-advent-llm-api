# Проверка этапа 7 — launchd и PWA

Runtime 0.7.0, schema=2, Python 3.13+. Реализация и автоматические проверки
готовы; **реальный API launchd initial на Mac прошёл 6/6**.
Автоматическое восстановление API после SIGTERM прошло 11/11; повторная reboot
проверка подтверждает API/HTTPS и прежнюю историю, но status=failed: версия
Ollama изменилась 0.34.4 → 0.40.2, строгое сравнение model_identity не прошло.
Android/iOS home-screen запуск вручную подтверждён пользователем.
Не выдаём Linux fixture за пользовательский Mac.
Этап 8 / итоговая приёмка не начаты. Шаги на Mac: [STAGE7.ru.md](STAGE7.ru.md).

## Финальная ревизия, 2026-10-10

Все перечисленные reports совпали с полным manifest из **59 файлов**.
JSON originals не переписаны. Runtime manifest содержит **27 файлов**, включая
manifest.webmanifest и PNG icons; hash coverage расширено на эти ресурсы.

| Отчёт | Результат | Что доказывает |
|---|---|---|
| `reports/verified/stage7-offline.json` | **128/128**, 28.463 s, failures/errors/skipped=0 | SQLite/ASGI/protocol/security, supervisor generation/install guards, restart/boot witnesses, PWA headers/assets, настоящий процесс SIGTERM/restart |
| `reports/verified/stage7-web-ui.json` | **26/26**, 25.087 s | Chromium desktop/mobile viewport, auth, history, SSE, lost-response idempotent replay, isolation, logout; synthetic engine |
| `reports/verified/stage7-pwa.json` | **11/11**, 2.446 s | Manifest/PNG decoding, no worker/cache/web storage, offline private API unavailable, online reopen server history, logout/privacy |
| `reports/verified/stage7-package.json` | **10/10**, runtime files=27 | Wheel 0.7.0 в чистом runtime-only venv вне checkout, полные runtime hashes и 7 packaged UI resources через ASGI |

CPython 3.13.16 / Linux x86_64 / Playwright 1.55.0 / Chromium 140.0.7339.16.
Offline tests запущены с `-W error::ResourceWarning`; source unchanged=true.
Hash verifier для текущего offline report=true; это не подпись или live network proof.
Колесо py3-none-any собрано setuptools/uv (build environment Python 3.14.8),
вне checkout установлено и проверено на Python 3.13.16 с requirements.lock.
Оно включает все 27 runtime files; no browser dependencies in runtime-only venv.

Во browser fixtures сначала обычный HTTPS preflight проверяет CA/hostname
через реальный сокет, Chromium доверяет только SPKI конкретного временного leaf.
Это не normal phone/Keychain certificate trust. Физическое добавление на домашний
экран и standalone session storage isolation требуется вручную на Android/iPhone.
В PWA fixture inference не вызывался: reopened seed history=120, API pagination
учтена, UI latest page=50. Full UI fixture проверяет synthetic генерации отдельно.

## Lifecycle и границы доказательства

Новый test поднимает настоящий отдельный Uvicorn process на loopback с
synthetic unavailable adapter, посылает SIGTERM, ждёт завершения, сверяет
полную завершённую историю и освобождение worker lease, запускает снова на
той же базе и повторяет. Он не запускает macOS launchd, Ollama или Qwen.
Существующий cancellation test сохраняет interrupted и persistent recovery gate.
Автоматического восстановления неизвестного engine state и replay inference нет.
Реальный interrupted Qwen / forced crash во время ответа остаётся проверкой этапа 8.

Генератор plists не открывает БД и не запускает процессы; installer лишь копирует
NEW private owned files и не вызывает launchctl. Перезапись/подмена symlink
существующего output отвергается. .venv interpreter symlink сохраняется без
resolve, argv не передаётся через shell. API bound localhost, один worker;
launchd grace=60 s, restart throttle=30 s. stdout/stderr=/dev/null; ограничения
операционной диагностики описаны в STAGE7/backlog. Caddy optional, прежние XDG
directories/CA сохраняются. Tailscale/Ollama apps управляются пользователем.

`check_launchd_live.py` на Mac делает только чтение: private installed plist,
launchctl state/PID, соответствующий localhost8000 listener, OS boot epoch fields,
verified HTTPS/current runtime/model, idle/gate и полная постраничная history hash.
Restart требует нового API PID при прежнем boot epoch; reboot — нового boot epoch,
а не обязательно нового PID. Профиль, URL, chat/config и history не меняются.
Производственный process supervision и физические устройства этим offline report
не доказаны. После Mac проверок сохраняются initial/after-restart/after-reboot JSON.

## Диагностика проверок до финальной ревизии

Первые browser attempts сохранены в reports/check (ignored временные результаты).
Сначала отсутствовал установленный Chromium; после установки fixture обнаружил
ошибки самого harness: history default limit=100 при seed=120 и попытка нажать
Logout в закрытом mobile drawer. Исправлены pagination и открытие меню, продуктовый
UI не менялся. Результаты перед последним исправлением сохранены отдельно с
`-before-pwa-navigation-fix`, включая failed PWA report; их manifests исторические.
Финальные 128/26/11 и package 10 проверены после исправления harness.

## Предыдущие доказательства и открытые вопросы

Stage6 Mac LAN/tailnet/browser+Qwen/Android handoff/restart originals сохранены
побайтно; новая ревизия имеет другой source/runtime manifest. Синхронизация
Mac/Android/iPhone после restart подтверждена пользователем. Действующий endpoint
tailnet only; API checker не читает deployed Tailscale grants policy / editor Save.

База schema=2, stored messages/owner IDs/generation/context/profile snapshots,
security tokens/sessions, очередь и inference параметры не изменены. Root README
и реализации предыдущих дней не менялись. Cloud LLM, Rust, RAG, агенты/голос/MCP
не добавлены. Operational backup/restore и перенос старой owner history отложены
до полной реализации по решению пользователя.

Peak RAM/CPU/swap, качество длинной истории, русский/китайский language mixing,
реальный load/recovery и полный финальный checklist остаются этапом 8.
Без обновления ready/source runtime reports от старой версии нельзя считать
проверкой новой версии. Сервер не работает до login или во время sleep;
экран может быть заблокирован, но Mac должен бодрствовать и иметь сеть.

## Первая настройка на Mac — 2026-10-10, 21:46 Europe/Kiev

Генератор отказался до записи plists: инструкция указывала
`day-30-private-ai-service/.venv/bin/python`, но активная .venv пользователя
находится в корне репозитория. Диагностика пользователя: настоящий interpreter
`/Users/litdi/AI/ai-advent-llm-api/.venv/bin/python`; код/DB/Caddyfile/XDG directories
существуют, Caddy executable=/opt/homebrew/bin/caddy, NEW output отсутствует.
Инструкция исправлена: используется default sys.executable активного окружения,
source ../.venv/bin/activate для известного расположения. Runtime/scripts не
менялись, все четыре готовых reports по-прежнему относятся к текущим sources.
Сохранённые отчёты не переписаны. Mac launchd acceptance ещё ожидается.

## Реальный launchd initial на Mac — 2026-10-10, 21:56 Europe/Kiev

Оригинальный `reports/verified/launchd-initial-20261010-215614.json` сохранён
побайтно, SHA-256 `da41f5b4f0a04526ccc66b968d7e387f71da8fd6634d93584c4211444b17bd48`.
**6/6 passed**, 0.707 s. Все 59 source hashes совпадают, source_unchanged=true.
API LaunchAgent private owned, expected supervisor config, PID=49748 владеет
только loopback8000 listener; verified tailnet HTTPS/current runtime/model ready.
queued=running=0, recovery gate отсутствует. Полная история=4 messages, history
hash совпал с stage6 after-restart; chat/model/profile прежние. JSON checker
не выполняет генерацию и не устанавливает приложение на телефон.
Installer с явным source path ранее сообщил installed_not_loaded для API/Caddy;
данный initial подтверждает running API, но отдельного Caddy running report не
содержит. Restart/reboot и physical PWA acceptance ещё ожидаются.

## Реальный launchd restart на Mac — 2026-10-10, 22:00 Europe/Kiev

Оригинальный `reports/verified/launchd-after-restart-20261010-220026.json` сохранён
побайтно; SHA-256 `ed549697aa245d2db0d4c9a1676d53dbd2c87d4763501985d3bb49d2900ce696`.
**11/11 passed**, 0.772 s. Все 59 source hashes совпали, source_unchanged=true;
baseline SHA совпал с original initial. API PID изменился 49748 → 51760 при
том же OS boot witness; plist configuration, URL/chat, model/profile и полный
history hash/count=4 совпали. PID принадлежит LaunchAgent и владеет только
loopback8000. Verified HTTPS/ready, idle/gate healthy. Проверка выполнена по
инструкции SIGTERM и восстановления supervisor; checker только читает состояние,
не создаёт inference. Это не reboot и не forced crash во время active Qwen.
Следующие пункты: user login/reboot, Caddy/LAN после reboot при использовании
этого пути, реальные PWA на Android/iPhone.

## Первая reboot проверка на Mac — 2026-10-10, 22:08 Europe/Kiev

Оригинальный `reports/verified/launchd-after-reboot-20261010-220819.json` сохранён
побайтно; SHA-256 `2442d228b9c954caf16c4bc887881e11da8cc3e097948ff80f93baee0c28df2f`.
Status=failed, 0.056 s; два checks прошли: private owned plist и expected supervisor
configuration. Все 59 source hashes совпадают с текущим кодом; plist hash прежний.
LaunchAgent был наблюдён в state=running, PID=868. Следующая операция checker —
lsof для loopback8000 — выбросила ValueError до записи listener check. По коду
это ненулевой exit status или превышение лимита вывода команды; отчёт не содержит
точную причину. Ранний запуск checker до появления listener возможен, но не доказан.
OS boot witness, HTTPS readiness и история ещё не проверены. Нельзя считать этот
отчёт доказательством успешного reboot или потери данных. Нужны read-only
launchctl/lsof/live diagnostics и повторная проверка с NEW output path без ручного serve.

### Read-only диагностика — 2026-10-10, 22:15 Europe/Kiev

Вывод пользователя: LaunchAgent state=running, runs=1, PID=868, last exit never;
lsof подтверждает тот же PID и только 127.0.0.1:8000. Прямой HTTP live вернул
400 secure_transport_required. Это ожидаемо в trusted-loopback-proxy режиме:
middleware проверяет loopback peer и X-Forwarded-Proto=https до обработки live.
Предыдущая диагностическая инструкция ошибочно ожидала 200 по прямому HTTP;
для проверки соединения через прокси нужен настоящий tailnet HTTPS URL.
Слушатель теперь доступен, но причина первого lsof failure не установлена.
Повторный reboot report ещё ожидается; модель, boot witness и полная история
этим выводом не подтверждены. Изменений runtime или ослабления защиты не требуется.

## Повторная reboot проверка — 2026-10-10, 22:16 Europe/Kiev

Оригинальный `reports/verified/launchd-after-reboot-20261010-221644.json` сохранён
побайтно; SHA-256 `f5fcff07d48b509f4c2b5ef4536654d1feddc9150038a517ea107f4beb7fcf0a`.
Status=failed, 0.965 s; 9 checks прошли, десятый same_model_and_profile=false.
Все 59 source hashes совпали; source_unchanged и baseline_sha256 не записаны,
поскольку checker остановился на несовпадении до их записи. Сравнение с original
initial отдельно подтверждает прежние URL/chat/plist, model digest/template/
quantization/tokenizer/counter и полный profile. Единственное различие внутри
model_identity — server_version: Ollama 0.34.4 → 0.40.2. Причина обновления
(автоматическое или ручное) не установлена.

API PID=868 принадлежит LaunchAgent и слушает только loopback8000. Verified
tailnet HTTPS/current runtime ready, queued=running=0, recovery gate=false.
Полная history count=4 и hash совпали с initial. OS boot SHA теперь
581bbbceb2fec1af91c91f3a907170c9da8dfd666ff518a866393f0fc22444dd,
отличается от initial; reboot witness наблюдён и независимо сопоставлен, хотя
одиннадцатый check new_os_boot не выполнялся после fail-fast на десятом.

Операционные свидетельства подтверждают восстановление API и сохранённой истории
после смены OS boot, но этот оригинал нельзя объявлять 11/11 passed или проверкой
неизменной inference среды. Проверка read-only не генерирует ответ: нужна реальная
генерация на текущей Ollama и physical PWA checks. Старый baseline/отчёты не
редактируем и strict comparison не ослабляем ради зелёного статуса.

## Проверка физических телефонов — 2026-10-10, 22:23–22:25 Europe/Kiev

Пользователь создал новый диалог после reboot и подтвердил синхронизацию всех
трёх устройств. Android: запуск с домашнего экрана вручную подтверждён.
iPhone: работа через «закладку» подтверждена; пока не установлено, означает ли
это Safari bookmark или Home Screen web app. Полный цикл standalone reopen /
новая генерация / logout-login и OS/browser versions отдельно не представлены.
Это пользовательское свидетельство, не автоматическое наблюдение установки.
Physical iPhone PWA acceptance и отдельная Caddy/LAN проверка после reboot
остаются открытыми; этап 8 не начат.

### iPhone Home Screen — 2026-10-10, 22:40 Europe/Kiev

После инструкции Safari → На экран «Домой» → запуск через значок пользователь
сообщил «готово iPhone». Android и iPhone Home Screen запуск принимается как
ручное свидетельство. OS/browser versions, logout/login и отдельный standalone
reopen цикл этим кратким подтверждением не установлены; automated reports
содержат собственные границы доказательства и не изменены. После обновления
Ollama на тот момент требовалось подтверждение нового завершённого ответа; отдельный
Caddy/LAN health после reboot ещё не представлен. Этап 8 не начат.

### Переход к этапу 8 — 2026-10-10, 22:43 Europe/Kiev

Пользователь явно подтвердил новый ответ с отметкой «Ответ сохранён», видимый
на Mac, и разрешил этап 8. Основной Tailscale путь, launchd lifecycle/history,
Android/iPhone Home Screen и live generation после обновления Ollama приняты
по совокупности исходных reports и ручных свидетельств. Reboot original
status=failed сохраняется: strict identity изменился только по server_version.
Это не превращается в 11/11 и не доказывает неизменную inference среду.
Caddy/LAN после reboot перенесён в открытые пункты финальной матрицы этапа 8;
не считаем его проверенным на основании успешного Tailscale пути.
