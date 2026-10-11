# Проверка этапа 6 — LAN и приватная сеть

Версия runtime 0.5.0, Python 3.13+, schema=2. LAN и tailnet API reports прошли;
общая история Android/iPhone/Mac и mobile chat подтверждены вручную. Tailnet
browser+Qwen report прошёл 19/19; device prepare прошёл 6/6, повторная
проверка phone handoff прошла 8/8; повтор после контролируемого API restart
также прошёл 8/8 с идентичными history hash и generation snapshot.
Приёмка этапа 6 продолжается.

После доставки пользователь вручную подтвердил на Mac LAN HTTPS через Caddy:
`https://192.168.0.247:8443`, verified `curl --cacert`, live=200, chats без
авторизации=401. Это запрос с самого Mac, не доказательство другого устройства.
Ollama 0.34.4 слушает 127.0.0.1:11434 под тем же UID; здоровая база schema=2.
Doctor обнаружил ложный отказ из-за process table 66 366 символов / 688 строк
при старом лимите 65 536; ps exit=0, elapsed=0.042 s. Наблюдения из терминала
пользователя; JSON-подтверждения этой диагностики не приложены.

## Уже полученные доказательства на Mac

Этап 5: оригинальный `web-ui-live-20261010-152509.json` сохранён побайтно,
19/19 checks, три completed Qwen turn, две Chromium-сессии на одном Mac,
reload/context/sync/SSE. До этапа 6 сверены все 41 source hash, ответы совпали с
«принято», «мандарин», «OK». Python 3.13.3 / Darwin arm64 / Qwen2.5:14b Q4_K_M /
Ollama 0.34.4. Это не физический телефон и не LAN/mobile. После изменений этапа 6
runtime manifest другой; прежний live report остаётся историческим.

Этап 4: Mac HTTP+Qwen 65/65, API restart/history 7/7, verified HTTPS/auth 14/14,
Ollama off/on подтверждён вручную. Исходные JSON не переписаны.

## Проверка до исправления process table — 2026-10-10

- `reports/verified/stage6-offline.json`: **119/119 passed**, failures/errors/skipped=0,
  **73.896 s**. Включены прежние 112 tests и 7 новых: явный raw-peer proxy trust,
  default forwarded distrust, header ambiguity/host conflict, same-origin CSRF,
  spoofed identity/XFF rate-key isolation, config injection/overwrite/symlink
  prevention, CLI TLS/proxy mismatch и handoff controls/negative cases.
- `reports/verified/stage6-proxy.json`: **48/48 passed**, **13.637 s**. Настоящий
  Caddy 2.10.2, internal CA/leaf chain, TLS socket → plain loopback Uvicorn →
  SQLite, Chromium 140.0.7339.16 desktop/mobile viewport, synthetic engine.
  Проверены exact bind/no admin/no HTTP redirects, verified CA, незнакомый CA
  отклонён, подмена Forwarded/XFP/XFH нейтрализуется Caddy, auth/CSRF/logout,
  SSE и два browser profiles, три контрольных ответа, prepare/verify handoff
  harness с неизменностью seed history/count/hash и context bound.

CPython 3.13.16, Linux x86_64, Playwright 1.55.0. У обоих final reports полный
manifest из **50 файлов** совпал с checkout, source_unchanged=true.
Offline hash verifier=true; это не подпись и не live-доказательство сети.
Первые отчёты до завершения policy/config сохранены с суффиксом `-before-policy`,
файлы без этого суффикса относятся к финальной ревизии этапа 6 до исправления
process table. После исправления их hashes исторические; JSON не переписаны.

Caddy binary скачан из official release 2.10.2; архив совпал с опубликованным
SHA-512 checksums. Это зафиксированная версия fixture, не утверждение о latest
production version. На Mac используется установленный Caddy; `caddy version`
сохраните с live-отчётом. Для config использованы official docs (ссылки STAGE6.ru.md).

`stage6-package.json`: wheel 0.5.0 установлен в чистый runtime-only Python 3.13.16
venv вне checkout. **6/6 checks**: три packaged UI ресурса через proxy boundary,
raw HTTP UI denied, версия и совпадение всех **23 runtime hashes**. ASGI smoke не
выдаётся за сеть. Backend dependency lock не изменён; Playwright только optional.

## Проверка после исправления process table — 2026-10-10

`reports/verified/stage6-engine-fix-offline.json`: **122/122 passed**, failures /
errors / skipped = 0, **30.887 s**, CPython 3.13.16 / Linux x86_64.
Три новые regression tests проверяют полный список больше 64 KiB, orphan runner
после прежней границы и сохранение finite output/timeout/command failure limits.
Полный manifest из 50 файлов совпадает с исправленной ревизией,
unchanged_during_run=true. Это synthetic engine tests и реальная SQLite/HTTP
инфраструктура; исправленный doctor на Mac, Qwen через LAN и телефон
не подтверждены этим offline report. Caddy/browser fixture 48 checks и wheel
smoke 6 checks выше не
перезапускались: proxy/UI/packaging не менялись; их source manifests исторические.
Подробности причины и установки: ENGINE_PROCESS_FIX.ru.md.

## Реальный LAN API на Mac — 2026-10-10, 19:06 Europe/Kiev

Оригинальный `reports/verified/lan-api-20261010-190613.json` сохранён побайтно.
SHA-256: `f0752c6dbc13378edd31e17fdf805a330786858758475bd9de6a6c8f5b1ecbca`.
**20/20 passed**, 8.622 s, Python 3.13.3 / Darwin arm64,
`https://192.168.0.247:8443`. Все 50 source hashes совпали с checkout после engine
fix; source_unchanged=true. Runtime hashes работающего API совпали с исходниками.
Verified certificate/hostname/live (22.079 ms), local assets/no-store,
unauthorized rejection, Secure/HttpOnly/SameSite cookie, login CSRF/session
rotation, authenticated chat listing, mutation CSRF/Origin, authorized chat creation,
ambiguous credentials denial, logout/revocation. LAN-IP probes TCP 8000 и 11434
получили connection refused (3.580 и 0.435 ms). Клиент — сам Mac, не другое устройство.
matching_runtime допускает readiness 200 или 503; этот check сам по себе не
доказывает model_ready. В отчёте нет inference, browser/phone или CPU/RAM.

После исправления пользователь сообщил UI «qwen2.5:14b · локальная модель · готова»,
затем подтвердил общие сообщения и диалог на двух устройствах Mac/телефон.
Это ручное подтверждение; точное контрольное слово, Android browser certificate
warning, phone network conditions и автоматический handoff report отдельно пока
не подтверждены этой LAN API проверкой.

## Ручной mobile check — 2026-10-10, 19:26 Europe/Kiev

Пользователь подтвердил вход в чат через мобильный интернет после настройки
Tailscale. Получен ответ модели с русским началом и продолжением на китайском.
Содержимое личного диалога не копируется в этот отчёт. Это зарегистрированный
дефект языковой устойчивости: текущий system prompt уже требует отвечать на
языке пользователя, но этот ответ инструкции не выполнил. Готовность сетевого
доступа не равна качеству ответа. Исправление и реальные сравнительные RU/EN /
explicit translation / multi-turn language checks нужны до итоговой приёмки,
в рамках этапа 8. Не объявляем изменение prompt доказанным решением без Qwen tests.

В 19:31 пользователь подтвердил положительный контроль в новом диалоге:
после явной просьбы отвечать полностью на русском оба ответа были русскими,
а продолжение с арифметическим выражением 2+2*2 дало 6 с правильным объяснением
порядка операций. Это ручной two-turn quality check после user instruction,
не автоматический отчёт и не доказательство исправления языка по умолчанию.
System prompt и runtime не изменены; исходный дефект остаётся открытым до
сопоставимых обычных RU/EN/multi-turn/translation checks этапа 8.

В 19:38 пользователь подтвердил успешную проверку отключения/включения Tailscale
на телефоне по предыдущей инструкции: после восстановления подключения чат
снова доступен. Результат ручной; отдельные сетевые observations/JSON не приложены.
Переход к этапу 7 пользователем прямо отложен. Вопрос о Tailscale как основном
режиме и переносе direct-LAN CA setup обсуждается; Caddy/origins/certificates не
удалены, режимы и API ещё не изменены.

Tailscale client 1.104.1 и DNSName Mac получены из CLI пользователя. Serve status,
Funnel disabled, ограниченная access policy и normal browser trust
ещё требуют отдельного подтверждения; device handoff report не приложен.
Tailnet API report получен позднее (следующий раздел). Ручной mobile success
не заменяет эти проверки. Runtime/profile/source не изменены из-за этой заметки.

## Реальный tailnet API и Android/iPhone sync — 2026-10-10

Оригинальный `reports/verified/tailnet-api-20261010-193244.json` сохранён побайтно,
SHA-256: `b09249ae241e76ea6ddc19e4d7715c1a0450737ef002f84ec5f81d3c1970f751`.
Run timestamp: 19:32:45 Europe/Kiev. **20/20 passed**, 8.361 s,
Python 3.13.3 / Darwin arm64. Все 50 source hashes совпали с engine-fix checkout,
source_unchanged=true, runtime hashes API совпали с исходниками.
Verified HTTPS certificate/hostname, live (38.759 ms), assets, auth/cookies/CSRF/
Origin, authenticated chat listing и chat creation, logout/revocation прошли через
tailnet endpoint. TCP 8000 / 11434 недоступны на адресе endpoint: connection refused
(3.451 / 1.794 ms). Клиент — Mac; этот JSON не доказывает physical phone, inference,
browser trust, тип сети или действующую tailnet policy/Funnel status.

В 19:59 пользователь отдельно подтвердил синхронизированные чаты на Android и
iPhone. Ручное подтверждение физического использования; модель iPhone/браузер,
Wi-Fi/mobile условия каждого устройства и normal TLS warning не уточнялись.
Автоматическая проверка two-context browser+Qwen, mobile device handoff с IDs/hashes,
повторное открытие после API restart и security policy/status остаются ожидаемыми.
Переход к этапу 7 по-прежнему не разрешён пользователем.

## Границы TLS/browser доказательств

Оригинальный `reports/verified/tailnet-ui-20261010-200618.json` сохранён побайтно,
SHA-256: `c4fd7e772fb7027ddd9fbd6739318e24c2b811746e7cba7be93a0b2cd5d96798`.
Run timestamp: 20:06:18 Europe/Kiev. **19/19 passed**, 19.902 s,
Darwin arm64 / Python 3.13.3 / Playwright 1.55.0 / Chromium 140.0.7339.16.
Все 50 source hashes совпали с checkout, source_unchanged=true.
Browser использовал обычный TLS trust без bypass/pin. Model readiness/runtime,
Secure cookie, SSE, reload, две независимые browser sessions одного owner,
синхронизация шести сохранённых сообщений, отсутствие browser storage/external
requests/JS errors и logout clearing проверены через tailnet endpoint.

Три реальные Qwen2.5:14b Q4_K_M / Ollama 0.34.4 generations completed, error=null.
Хеши соответствуют точным controls «принято», «мандарин», «OK».
Input tokens 72/108/128 <= bounds 662/1061/1362, omitted_turns=0,
profile=temperature 0 / num_ctx 8192 / max_output 1024 / margin 512.
TTFT 3.161 / 0.331 / 0.343 s; total engine duration 3.480 / 0.657 / 0.426 s.
Это короткие controls, не quality/performance benchmark и не закрытие RU/Chinese
или long_a defects. Две browser sessions запускались на одном Mac, не на телефонах.
В 20:07 пользователь отдельно подтвердил работу и синхронизацию с Mac вместе
с ранее подтверждёнными Android/iPhone. Device handoff/restart и Serve/Funnel
status/access policy ещё не представлены. К этапу 7 не переходим.

В 20:10 пользователь представил CLI Serve/Funnel status: единственный показанный
HTTPS endpoint помечен `(tailnet only)`, `/` проксируется на
`http://127.0.0.1:8000`; оба status вывода показывают приватный маршрут.
Публичный Funnel для этого endpoint не включён в показанной конфигурации.
Tailscale IPv4 Mac: 100.65.246.78. Это ручной CLI transcript, не подписанный JSON.
Приёмка configuration/status выполнена для показанного endpoint; действующая
access policy, handoff и API restart остаются открытыми.

В 20:16 пользователь предоставил фрагмент policy с единственным показанным grant
личного account к Mac 100.65.246.78 TCP:443; фрагмент обрывался до конца документа.
Подготовлен полный минимальный personal-tailnet вариант с tests accept 443 и
deny 22/8000/8443/11434. Успешное сохранение полного policy и editor tests отдельно
не подтверждены; конкретный login пользователя в репозиторий не переносится.

`reports/verified/tailnet-api-policy-20261010-202114.json` сохранён побайтно,
SHA-256: `90f9fc155e579bc73ac2ba7f2b9f9c80817e927197ed4a127b1d3b8107045aea`.
Run timestamp 20:21:14 Europe/Kiev, **20/20 passed**, 7.290 s,
Python 3.13.3 / Darwin arm64. Все 50 source hashes совпали, source_unchanged=true.
HTTPS/auth/CSRF/chat listing+creation/logout/runtime matching прошли; TCP 8000 /
11434 на tailnet endpoint refused (4.447 / 2.043 ms), live latency 42.934 ms.
Запущен пользователем по инструкции после изменения policy, но checker не читает
действующую policy и не проверяет Tailscale editor tests / другого principal.
Он подтверждает работоспособность endpoint и calling-Mac port probes, а не
независимое доказательство точного deployed grant. Handoff/restart ожидаются.

Fixture использует test-only loopback binding, временный CA и независимо проверяет
цепочку/hostname через httpx. Chromium разрешает только SPKI конкретного проверенного
временного leaf, не глобальный HTTPS bypass. Test CA в system trust store не ставится.
Это **не** обычное доверие Keychain/Android/iOS. Production network UI checker
использует обычный browser trust без bypass/pin; LAN root устанавливается вручную.

Tailscale Serve в среде разработки не запускался: нет вашего tailnet/Mac/телефона.
Документация и proxy header contract сверены с official docs/implementation;
tailnet API interoperability подтверждена отдельным Mac report выше, mobile access
подтверждён вручную. Точная Serve/Funnel configuration и policy ещё проверяются.
Во fixture реальные сокеты/Caddy/browser/storage, но ни настоящая Qwen, ни телефон.

## Новый runtime и неизменённые данные

FastAPI только 127.0.0.1; явный proxy flag и origins, backend TLS исключён в этом
режиме; raw peer сохраняется, Uvicorn generic proxy handling выключен. Только HTTPS
marker от loopback переводит scheme. Host/Origin, session/CSRF/owner authorization,
idempotency/body/queue/context/output quotas сохраняются. XFF/Tailscale identity
не заменяют principal и не обходят anonymous IP quotas. Local OS доверена.

LAN config слушает конкретный RFC1918 IPv4, admin/HTTP redirects выключены,
runtime proxy logs discard, API access logs off. CA/config directory постоянный.
Миграции 001/002, модельный профиль, storage и UI resources этапа 5 не изменялись.
Во время сетевой проверки изменён только лимит чтения process table в OS engine
witness: подробности ENGINE_PROCESS_FIX.ru.md. Inference dispatch/context/recovery
не менялись. 8192/1024/temperature=0/margin=512 остаются исходными.
Корневые README/прошлые дни не менялись. Cloud inference/fallback, Rust/PWA здесь нет.

## Что нужно для приёмки на Mac

1. LAN HTTPS без warning в обычном Chrome/Safari и на настоящем телефоне, Tailscale
   на LAN клиенте отключён. Доверие CA, клавиатура/touch/background/reopen отдельно.
2. API с другого устройства: `check_network_live.py` там, verified TLS/auth/CSRF/
   history + remote port probes. Mac → свой LAN IP не считается другим устройством.
3. `check_network_ui_live.py`: настоящая Qwen через LAN/Serve, strict answers,
   runtime/model/profile metadata, normal browser trust, SSE/sync/reload.
4. `check_device_handoff.py prepare/verify`: контрольный диалог продолжен физически
   на телефоне, затем проверены сохранённые seed IDs/hashes и одно новое completed
   turn с верным словом. Browser/hardware/сеть подтверждаются пользователем отдельно;
   CLI declaration не является независимым измерением физического устройства.
5. Mobile: Wi-Fi выключен, Tailscale connected, успешный чат и Mac sync. При
   отключении Tailscale вне LAN приватный endpoint недоступен. Funnel не включён.
6. Ollama loopback listener через `lsof`, healthy external HTTPS path и blocked
   8000/11434 с другого устройства LAN и tailnet. Network error ≠ passed isolation;
   refused/timeout сопоставляется с positive path и listener inspection.
7. История после API restart через оба сетевых UI. Прежние IDs/контекст сохраняются.

Пошаговые команды: STAGE6.ru.md. Отчёты NEW/exclusive, private token/пароль/cookie
не записываются. Phone prepare содержит только публичные синтетические controls;
verify хранит hashes/IDs/metrics и отдельно обозначенные manual declarations.

Реальные peak RAM/CPU/swap, длинные ответы/quality и итоговый load/recovery — этап 8.
long_a failure остаётся открытым; короткие controls его не закрывают. Backup/restore,
старый owner/history перенос — после полной реализации по решению пользователя.
Автозапуск, reboot/PWA — этап 7; Rust и Kerry memory — после курса.

## Контрольный handoff — 2026-10-10, 20:24–20:28 Europe/Kiev

Оригинальные отчёты сохранены побайтно:

- `reports/verified/device-prepare-20261010T172433-62e1dba4.json`: **6/6 passed**,
  2.051 s, контрольный диалог создан, seed completed, literal/context bound проверены.
  SHA-256: `0ab4d92c20e70b1e035b9ba046230594f153d8dd0218ee61fadc4459f570b15a`.
- `reports/verified/device-verify-20261010T172523-56c6bb8c.json`: **failed**,
  HTTPS/ready/runtime, совпадение prepare sources и seed history прошли;
  `one_phone_turn_without_duplicates=false`. Проверка ожидает ровно четыре
  сообщения с ролями user/assistant для второго turn. Отчёт не содержит
  фактическую длину/роли истории: отсутствие phone turn, лишний turn или
  другая структура не различимы; дублирование этим результатом не доказано.
  SHA-256: `4e4d2633c1111ab254f0815cfe9376946eeb6b1232c53ef563d79889ec51ee73`.

Все 50 source hashes обоих отчётов совпадают с текущей исправленной ревизией.
Второй запуск verify с прежним output завершился FileExistsError до сетевой
проверки: exclusive open защищает первый отчёт от перезаписи. Нужно новое имя
отчёта, а не удаление прежнего. Пользователь подтвердил синхронизацию трёх
устройств, но также сообщил UI «Нет подтверждения от сервера». Это общее
сообщение для ошибок fetch/таймаута/разбора ответа; причина по этой строке
не установлена. При неизвестной доставке повторяют ту же операцию с её
idempotency key через кнопку UI, не создают новое одинаковое сообщение.
Handoff/restart пока не приняты; к этапу 7 не переходили.

## Повторный phone handoff — 2026-10-10, 21:06 Europe/Kiev

`reports/verified/device-verify-20261010T180635-1c0e31e2.json` сохранён побайтно,
SHA-256 `f4853836097a2104ca3eb19f7d99e7b85946347a5f00c691cee09ac3a39c3d84`.
**8/8 passed**, 0.300 s. Все 50 source hashes совпали, source_unchanged=true.
Chat ID и challenge SHA-256 совпали с исходным prepare; model identity и profile
совпали. Seed history не изменена, история содержит ровно четыре сообщения,
контрольный вопрос точный, ответ «мандарин», phone generation completed,
без лишних сообщений. Actual input=110 <= upper bound=1069;
1069+1024+512 <= 8192; omitted_turns=0. TTFT=4.203 s, generation total=4.528 s.
Physical Android/mobile — явно обозначенная декларация пользователя, не
независимое измерение устройства/сети сервером.

Перед успешным повтором пользователь получил HTTPS 502; curl к loopback8000
показал connection refused. Затем были даны инструкции запустить API с прежней
базой и origins. Успешный report подтверждает восстановление endpoint и
сохранение исходной seed history. Перезапуск после сохранения всех четырёх
сообщений ещё должен сравнить полный history hash
`a0d49d6b4da8250dc451b2719bfa138d5f70b9d0427b9b1c1eac79e2c4f91c10`
и generation ID `6b686cf393af4068978eb74424385c27`. Первый failed report
сохранён как историческое наблюдение. UI сообщение о неизвестной доставке
не доказывает конкретную причину; loopback refusal объясняет наблюдавшийся 502.
К этапу 7 не переходили; deployed policy Save confirmation ещё ожидается.

## Полная история после API restart — 2026-10-10, 21:09 Europe/Kiev

`reports/verified/device-verify-after-restart-20261010T180935-607caa57.json`
сохранён побайтно, SHA-256
`a7d126ed9297ff3c3d5276d05d522cf66fa3f41e98309a4197c3aaf82a623538`.
**8/8 passed**, 0.288 s; все 50 source hashes совпали с checkout,
source_unchanged=true. По сравнению с успешным report 21:06 совпали chat ID,
полный history SHA-256, challenge SHA-256, model identity, profile, generation
ID и весь сохранённый generation snapshot (status/metrics/context). История
четырёх сообщений сохранилась без изменений и дублей; verify делает только
чтение, новую генерацию не создаёт. Это API restart по инструкции пользователю,
не перезагрузка macOS и не независимое измерение physical/mobile условий.
Deployed policy Save confirmation ещё ожидается; переход к этапу 7 не выполнен.

## Переход к этапу 7 — 2026-10-10, 21:12 Europe/Kiev

Пользователь подтвердил синхронизацию и работу трёх устройств после restart,
отсутствие ошибок JSON-checker и явно разрешил этап 7. Точная deployed grants
policy не читается checker; сообщение о JSON без ошибок не является независимым
доказательством policy editor Save/tests. Эта граница доказательства сохраняется.
Исходные stage6 reports неизменны; после stage7 runtime/source manifest новый.
