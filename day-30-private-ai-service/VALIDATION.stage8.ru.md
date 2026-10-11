# Этап 8 — состояние проверок

Текущий runtime **0.8.0**, schema2, private-chat-v2; предыдущие baseline/recovery/compare ниже выполнены с runtime0.7.0/v1. Старые JSON не изменены.
Текущий полный source manifest=67 files, offline suite143/143.
Новый Mac API baseline v2: technical259/259, quality13/13, 16/16 completed;
v1→v2 history upgrade30/30. Исторический baseline v1 quality12/13 сохранён.
Реальная interruption/recovery цепочка прошла21/21 → 9/9 → 15/15.
После v2 history11/11 и LAN6/6 пользователь11 октября подтвердил финальный
phone mobile/Tailscale off/on сценарий: доступ без Tailscale пропал, затем
восстановился; это manual declaration, не новый CLI policy audit. Этап9 оформлен:
[FINAL_REPORT.ru.md](FINAL_REPORT.ru.md). Исторические шаги: [STAGE8.ru.md](STAGE8.ru.md).

## Проверенная реализация

| Проверка | Результат | Граница доказательства |
|---|---|---|
| Исторический `reports/verified/stage8-prompt-experiment-offline.json` | **140/140**, 45.364 s; then66 sources unchanged, failures/errors/skipped=0 | Полный suite после prompt experiment; synthetic model, не real candidate improvement proof |
| Исторический `reports/verified/stage8-recovery-checker-fix-offline.json` (до prompt experiment) | **136/136**, 46.589 s; failures/errors/skipped=0, current sources unchanged | Полный suite после recovery checker fix; real SQLite/ASGI/TLS, synthetic model; не live forest-story-v2/Qwen proof |
| Исторический `reports/verified/stage8-offline.json` (до checker fix) | **135/135**, 43.135 s; failures/errors/skipped=0, sources unchanged | SQLite, ASGI и реальные certificate-verified HTTPS sockets, protocol/security/history/queue и новые observers; inference/OS counters synthetic |
| Исторический `reports/verified/stage8-package.json` (до checker fix) | **10/10**, packaged runtime files=27 | Wheel 0.7.0 в отдельном runtime-only venv вне checkout; все runtime hashes и packaged UI через ASGI |
| Stage7 Chromium UI / PWA | Исторические **26/26 и 11/11**; относятся к runtime0.7.0 | Исторические результаты; новые UI/PWA reports для0.8.0 приведены ниже |

CPython **3.13.16**, SQLite **3.53.1**, Linux x86_64.
Первый suite с `-W error::ResourceWarning`; verifier source=true до checker fix.
Это не пользовательский Mac/Python3.13.3 и не реальная Qwen.
Исторический wheel0.7.0 был проверен против64-file manifest до checker fix.
Текущий0.8.0 меняет runtime; его отдельная проверка приведена ниже. Новых dependencies нет.

До окончательного source guard suite тоже прошёл 135/135; исходные reports
сохранены как `stage8-offline-before-final-source-guard.json` и
`stage8-package-before-final-source-guard.json`. Финальный guard не допускает
status=passed при изменении sources между последними наблюдениями.
Другие исторические JSON, включая failed reboot, не переписаны.

## Новые tests

1. Полный workload на SQLite/ASGI: 16 terminal generations, 7 chats/32 messages,
   replay/overflow/quota, max worker active=1 и persisted interval overlap=1.
   Отдельный прогон намеренно возвращает lantern вместо OK и русский+CJK:
   quality_status=failed при сохранённых технических результатах.
2. Неоднозначный POST transport failure не вызывает повтор. Явный 429 повторяет
   ровно тот же body/key, ожидания ограничены. Квота в fixture использует virtual
   clock; это не измерение времени live quota на Mac.
3. Resource observer failure не становится technical success.
4. Тот же workload через настоящий Uvicorn/HTTPS socket с проверкой CA/hostname;
   engine/observer synthetic. Независимые старые seed chats в report не включаются.
5. Partial commit → failed/uncertain gate → новый engine epoch → явный recovery;
   seed/prefix/full terminal history неизменны, old generation не повторяется,
   новая явная генерация в новом чате. Здесь epoch и сбой synthetic.
6. macOS-format parsers: CPU time, RSS KiB→bytes, 16 KiB VM pages, swap units,
   выбранная process topology, отказ при orphan/чужой модели, другие имена не
   попадают в output. Это fixtures формата; реальные counters получены отдельно
   в Mac baseline ниже.
7. p95/median с n, русский+CJK screen и negative overlap witness.

Первый synthetic recovery attempt не получил partial: fixture отправляла менее
256 chars без повторного checkpoint после .25 s. Production coordinator корректно
не записал его до своего threshold. Fixture исправлена на >256 chars; runtime
не менялся. Финальные tests прошли после исправления. Synthetic успех не выдаётся
за настоящее прерывание Ollama или forced API crash.

## Mac evidence предыдущего этапа

Initial launchd6/6 и restart11/11 сохранены с оригинальными hashes. После reboot
отдельно совпали полная история4, config/URL/chat, Qwen digest/template/profile;
OS boot изменился, API PID868 владел только loopback8000, HTTPS/model ready.
Strict reboot report failed из-за Ollama **0.34.4 → 0.40.2**; это изменение
не скрыто и не объявлено 11/11. Пользователь подтвердил новый сохранённый ответ
на телефоне, его видимость на Mac, sync всех трёх устройств и Android/iPhone
Home Screen. Этап 8 разрешён явно. Отдельный Caddy/LAN после reboot остаётся открыт.

## Реальный Mac baseline — 2026-10-10 20:20 UTC

Исходный [JSON](reports/verified/acceptance-baseline-20261010-202012.json)
сохранён побайтно; SHA-256
`5bbc3c5a5899f29fd2bea7c59d4bf8566da1b9ad4796db9fa9165a1a81104653`.
Все **64 source hashes и 27 runtime hashes** совпали с файлами до checker fix;
source_unchanged=true. Общий status **failed**, technical_status **passed**,
quality_status **failed**. Исходный отчёт не исправлялся.

- **259/259 technical checks**, **16/16 completed**, 7 chats/32 messages;
  10 sequential, 3 greetings и 3 simultaneous admissions. Queue max=2,
  persisted generation interval overlap max=1. Concurrent queue waits:
  0.021 / 2.137 / 4.247 s. Нет failed/interrupted/truncated в этом наборе.
- Auth 401, context 422, body 413, idempotent replay без дублей, неизменная
  история при отказах. HTTP owner limit: 429 с Retry-After=49 s после
  101 read requests; предыдущие запросы также расходовали общее окно.
- Реальные counts в budget. long_a upper bound=6613 при budget=6656,
  actual input=1542; omitted=0. long_b upper bound=3664, actual input=1271,
  omitted=9. Полная сохранённая история=20 messages, inference history короче.
- **12/13 quality controls**: long_a получил `lantern` вместо `OK`.
  Повтор ранее наблюдавшегося сбоя следования текущей инструкции; причина
  не установлена. По counters переполнения контекста здесь нет. long_b=`OK`.
  Recall/correction/math/continuity/queue controls правильны. Все три greeting
  ответа одинаковы, полностью на русском и уместны для приветствия, без CJK.
  Screen не гарантирует отсутствия смешения языка в других запросах.
- **106 macOS samples**, errors=[]; API RSS sampled max=66,355,200 bytes
  (**63.28 MiB**), сумма RSS Ollama и descendants max=10,845,061,120 bytes
  (**10.10 GiB**). Ollama size_vram max=10,383,418,981 bytes (**9.67 GiB**).
  Swap used max/change=0. RSS и size_vram не складываются; это не physical
  unified-memory peak. Низкий free counter не равен доступной памяти macOS.
- Первый запрос: модель до него не загружена, load=2.586 s, first token=3.468 s.
  Subsequent sequential first-token median=0.478 s, nearest-rank p95=11.445 s
  (n=9, длинные prompts входят в группу). Counters из generation metrics,
  не самостоятельный end-to-end замер телефона. Forced cold eviction не было.
- Direct tailnet host ports 8000/11434 refused с самого Mac: не отдельный
  remote probe телефона и не аудит сохранённой grants policy.

Human review синтетических ответов записан здесь отдельно; исходное поле JSON
`semantic_review=pending_human_review` не менялось. Качество пока не принято.
На этом историческом baseline качество не было принято. Последующие recovery
и prompt experiment описаны ниже; новый API baseline ещё требуется. Старые
snapshots, история и JSON сохраняются. Backup/restore остаётся deferred.

## Первый live interruption attempt — 2026-10-10 20:30 UTC

Исходные [prepare](reports/verified/recovery-prepare-20261010-203034.json)
и [interrupted](reports/verified/recovery-interrupted-20261010-203121.json)
сохранены побайтно; все 64 source hashes текущие.

Prepare **19/19**, status=passed: seed completed, control generation
`cf841a43a1da4489a384378e64ffdad3` наблюдалась running с 21 сохранённым
символом. Это доказательство начала ответа и partial checkpoint, не прерывания.
Interruption report **failed** на `interrupted_terminal_status` (1/2 checks):
при следующем чтении status не был failed/interrupted. Сам status/metrics
checker не записал до fail-fast, поэтому completed, truncated и ещё running
нельзя различить по этому JSON. Prefix/history/gate/outage проверки не выполнены.
После prepare прошло примерно 37 секунд до следующей проверки; ответ мог
закончиться до выхода Ollama, но это пока гипотеза. Нужна read-only диагностика
только этой контрольной generation и readiness; повтор prepare или recovery
не назначается на основании неизвестного состояния. Исходный failed не заменяется.

Prepare SHA-256: `dcd1922865af35fa870c75e2000f979294b4ec94313b66599d7781d75017a571`.
Interrupted SHA-256: `8148dd467035b2079b384973d7cca303a7683afed43fdf10eecc8c5c9b4b4cca`.
Restored phase не запускалась; реальное прерывание пока не доказано.

Read-only диагностика пользователя 2026-10-10 20:34 UTC уточнила состояние:
контрольная generation completed, error_code=null, saved_characters=279,
output_tokens=80, inference_seconds=6.313754, total_seconds=7.195825333999892;
finished_at=2026-10-10T20:30:50.516269+00:00. Это примерно 6.3 s после
окончания prepare. READY HTTP200/ready, model_ready=true, gate=false,
queued=running=0. Успешный terminal status подтверждён; фактический момент
Quit по этим данным неизвестен. Recovery не требуется. Повтор проверки
делается в новом каталоге без изменения источников/профиля/старых отчётов;
оператору надо заранее подготовить Quit и выйти сразу после сигнала.


## Второй live interruption attempt — 2026-10-10 20:36 UTC

Исходные [prepare](reports/verified/recovery-prepare-20261010-203648.json)
и [interrupted](reports/verified/recovery-interrupted-20261010-203739.json)
сохранены побайтно, 64 source hashes совпадают. Prepare 19/19 passed,
контрольная generation `463f8f9abc8847cd9a40ce45a7ea5d36` running с
21 сохранённым символом. Interrupted снова failed на interrupted_terminal_status,
1/2 checks; следующий actual status и answer не записаны fail-fast checker.
По JSON неизвестны время фактического Quit и состояние engine после него;
старый engine epoch в challenge скопирован из prepare и не является наблюдением
после Quit. Нужны read-only actual generation/ready/listener observations;
третье повторение того же короткого сценария пока не назначено. Restored и
реальное прерывание всё ещё не доказаны.

Prepare SHA-256: `6228e3fa94052fa46c48fbaf7533b03f154ab343f0b258a1f53e4606683fb385`.
Interrupted SHA-256: `2d96316a3dc1806bb1b5af5417f727d49c97270f95eed8cf9779ef17d7fd5044`.

## Recovery checker fix после двух коротких ответов

Диагностика пользователя 2026-10-10 20:39 UTC: второй control completed,
error_code=null, 80 output tokens, 7.209 s total, finished_at=20:37:04.527486 UTC.
Текст — отказ писать 500 предложений и предложение согласовать десять.
READY200/ready, gate=false, queued=running=0, Ollama listener PID13487,
только 127.0.0.1:11434. Точное время Quit неизвестно; новый PID не доказывает
interruption во время control. Recover-inference при таком ready state не нужен.

Исправлены только `scripts/check_recovery_live.py` и `tests/test_acceptance.py`:
вместо запроса на 500 предложений — рассказ в восемь развёрнутых абзацев
(`forest-story-v2`), точный control prompt хранится в challenge. До каждого
fail-fast сохраняются actual status, control answer, metrics и timestamps.
Это диагностический synthetic текст специально созданного чата, не личные chats.
Есть ранняя подсказка подготовить Quit; время генерации не гарантируется.
Completed/truncated не принимаются за interrupted. Финальный source guard
также не допускает passed при изменении источников.

Runtime 0.7.0, все 27 runtime hashes, default prompt private-chat-v1, профиль,
schema и storage неизменны. Полный manifest остаётся 64 файлами, но два hashes
изменились: прежние baseline/recovery/offline/package JSON — исторические.
Их исходные полные sources совпадали до этого изменения; нельзя утверждать,
что полный старый manifest совпадает с новым checkout. Старый Mac baseline
доказывает прежнюю нагрузку того же runtime, не новый prompt control.
Strict `--history-from` старого baseline требует прежний checkout; новый набор
baseline/history следует выполнить после согласованного quality experiment.
Первоначальная quality проблема long_a этим исправлением не решается.

Новый negative regression test использует actual SQLite/ASGI: control завершается
completed после saved partial, checker правильно падает и сохраняет статус,
текст и output_tokens=80 без секретов и без ложной recovery gate. Успешный
synthetic partial/gate/epoch test сохраняется; реальный forest-story-v2/Ollama
interruption ещё требует новой проверки на Mac.

## Реальное прерывание после checker fix — 2026-10-10 20:47 UTC

Исходные [prepare](reports/verified/recovery-prepare-20261010-204716.json)
и [interrupted](reports/verified/recovery-interrupted-20261010-204758.json)
сохранены побайтно. Оба passed: **21/21 prepare и 9/9 interrupted**, 64 source hashes на версии до prompt
experiment совпадают, sources unchanged, baseline SHA связывает пару.
Runtime 0.7.0, Ollama0.40.2/Qwen digest/template и профиль private-chat-v1 прежние.

Generation `ccf9cddbaae248e88f3dcceec337cb6e` в новом synthetic control chat
`41a996cc53464e2e8199efe8731cfc43` сначала running с 23 сохранёнными символами,
после остановки Ollama — failed/invalid_model_response с **707 сохранёнными
символами**. Начальный prefix сохранён. started_at=20:47:24.069628,
finished_at=20:47:47.388948 UTC. Прерванный поток не завершился корректным
model terminal frame; код invalid_model_response здесь не ошибка credentials
или переполнение context. Метрики неполного inference отсутствуют ({}),
throughput/token total не выдумываются.

Live/history доступны, ready503/model_ready=false, recovery gate=true,
queued=running=0. Seed history hash неизменен, full history=4 messages,
SHA `5df444bca7c40b463959261e037d0fda70fd714f15189c6bfcc6ebc8817d06ee`.
Новый admission503 не добавил сообщений. Это настоящие HTTP observations
реального Ollama stream interruption; forced API SIGKILL/backup не выполнялись.

Prepare SHA-256: `e8632f0d944efc44c38116f12424738684aa18d8ccdcc076449b3960728c1e45`.
Interrupted SHA-256: `e918f31496c94ea17d870dbbcd02a91d4c031493cd5b54d3cd17d158f182598a`.

Следующий шаг — operator открывает новый Ollama process, останавливает API
LaunchAgent, выполняет recover-inference и после успеха bootstrap API. Restored
пока ожидается: новый verified epoch, terminal history без изменения/replay,
новый отдельный 2+2 control. Long_a quality остаётся открытой.

## Реальное восстановление — 2026-10-10 20:51 UTC

[restored JSON](reports/verified/recovery-restored-20261010-205125.json)
сохранён побайтно, SHA-256
`a8fa4735be55b0b4aaa9c4489ed210153a1d00be025fdb4d1721d44d5b4211e5`.
**15/15 passed**, 64 sources unchanged на версии до prompt experiment. SHA связывает его с исходным
interrupted; вновь загруженные prepare/interrupted побайтно те же, не новый запуск.
Новый verified engine epoch подтверждён checker, ready/idle/gate=false;
Qwen identity/Ollama0.40.2/profile совпали. Сам новый epoch не записан в JSON,
поэтому это результат проверенного сравнения, не отдельный raw epoch snapshot.
Полная terminal history4 имеет прежний hash, старый ID/status не replayed,
707 saved characters сохраняются в неизменной history. Новый явный запрос
в отдельном чате: generation `d576d92e0021459d8faa4afc4fad7d51`, completed,
ответ `4`, input/output=67/2, first_token=2.434 s, total=2.526 s.
History прерванного control не изменилась после новой генерации.

Цепочка real interruption/recovery принята **21/21 → 9/9 → 15/15**.
Это не forced API SIGKILL, не новый reboot и не backup. Long_a quality,
следующий baseline/history на текущем checkout и оставшаяся network matrix
по-прежнему открыты. Stage9 не начат.

## Историческая подготовка frozen-context prompt experiment (runtime0.7.0)

Новый checker + четыре tests добавляют два файла: manifest66, runtime27 без
изменений. Input — исходный technical-passed Mac baseline; его runtime/profile/
CASES и reconstructed bounds/omissions проверены. Все **16 контекстов исходного
Mac baseline восстановлены**, long_a bounds6613/6653 для A/B, оба fit budget6656.
Working DB, default prompt и server snapshots не меняются; новые экспериментальные
ответы не становятся later inputs. ABBA64 direct sequential generations на Mac
ещё не запускались. Ни исправление long_a, ни выигрыш latency пока не заявлены.

Четыре synthetic tests: paired frozen histories/order/settings/candidate failure;
отказ от dispatch при активном API и неподходящем baseline; ambiguous POST
one call/no retry/unknown; invalid counters или missing terminal не становятся
успехом. Первый targeted attempt выявил ошибку fixture: long_b omits все9 history
pairs, поэтому там нет предыдущего lantern; проверка исправлена на frozen recall
acknowledgement. Runtime ContextBuilder не менялся. Клиент fixture также получил
trust_env=false вместо SOCKS env. Финальные targeted tests4/4 прошли.

Инструкция [PROMPT_EXPERIMENT.ru.md](PROMPT_EXPERIMENT.ru.md). После live результата
и human review — отдельное внедрение новой versioned server instruction, затем
новый API baseline/history и remaining network matrix. Stage9 не начат.

## Live prompt comparison — 2026-10-10 21:10 UTC

Оригинал [prompt-compare-20261010-211034.json](reports/verified/prompt-compare-20261010-211034.json)
сохранён без изменения, SHA-256
`2981e322548805bcd894105cd548caa6be705f42563ad37e436e94800f5ea788`.
Все 66 source hashes совпали с checkout **до** внедрения v2, baseline SHA
совпал с исходным `5bbc3c5a...04653`. Это historical source manifest после upgrade.

Technical **135/135**, completed **64/64**, candidate **26/26** controls,
reference **24/26**; elapsed149.418 s, A→B→B→A. В обоих блоках v1 long_a=lantern,
в обоих candidate long_a=OK. История/запрос каждого case идентичны во всех блоках;
модель, template, параметры и engine epoch одинаковы до/после.
Приветствия полностью русские, без CJK; запоминание/исправление/смена темы
и queue literals прочитаны, новых ошибок не найдено. Исходный JSON semantic_review
не изменён: последующая проверка отражена здесь и в PROMPT_V2.ru.md.

Медианы client_total_seconds: v1=0.643475, candidate=0.643881 (по32 observations).
Не заявляем ускорение или экономию памяти: нет first-token/RAM/CPU/GPU,
stream:false, замороженные входы, последовательные запросы. Candidate inputs
не используют его предыдущие ответы. Dynamic multi-turn и deployed API
проверяются новым baseline отдельно, не подменяются этим экспериментом.

## Runtime0.8.0 / private-chat-v2 — подготовлен к Mac-проверке

Принятый текст candidate-latest-request-v1 добавлен побайтово как private-chat-v2;
immutable v1 сохранён. Новая default версия не переписывает snapshots,
ContextBuilder/storage используют одинаковый текст, adapter сверяет его до POST.
Upgrade guard сохраняет queued задания другого профиля до явного завершения
с прежним профилем. CLI поддерживает выбор v1/v2. Schema2/APIv1 прежние.

| Проверка текущих sources67 | Результат | Граница |
|---|---:|---|
| [stage8-prompt-v2-offline.json](reports/verified/stage8-prompt-v2-offline.json) | **143/143**, 46.719 s | CPython3.13.16, Linux, SQLite/ASGI/loopback TLS, synthetic inference; no errors/skips, sources unchanged |
| [stage8-prompt-v2-browser.json](reports/verified/stage8-prompt-v2-browser.json) | **26/26**, 24.394 s | Реальный Chromium с проверенным fixture TLS, synthetic model; не Safari/телефон/Qwen |
| [stage8-prompt-v2-pwa.json](reports/verified/stage8-prompt-v2-pwa.json) | **11/11**, 2.915 s | Chromium reopen/offline/logout/privacy; не OS install |
| [stage8-prompt-v2-package.json](reports/verified/stage8-prompt-v2-package.json) | **10/10**, runtime27 | Новый wheel0.8.0 в clean runtime-only venv вне checkout; все runtime hashes/UI assets совпадают |

Wheel SHA-256 `15a3233d48a8ac33a68a3b80b6822943e2755848f57f85e12bc667391254c80d`.
Verifier текущего offline report=true. Новые tests проверяют queued-v1 refusal
без claim/мутаций, выполнение v1 и последующий v2 в том же чате, idempotency
с прежним generation ID, одинаковые persisted/dispatched prompt bytes/bounds,
отказ до POST при подмене текста, read-only upgrade checker и ошибку сравнения
старого ответа. Старые reports не переписаны; предыдущие дни/root README прежние.
Mac upgrade.json/new baseline-v2.json/restart history ещё не получены.
Порядок установки: [PROMPT_V2.ru.md](PROMPT_V2.ru.md). Stage8 не завершён.

## Открытые финальные пункты

Первый Mac upgrade report, 2026-10-10 21:36 UTC:
[prompt-upgrade-20261010-213642.json](reports/verified/prompt-upgrade-20261010-213642.json),
SHA-256 `a091faec1be460d48bc88edccb09cf5845ab835fa4b076845126457aa8c1af68`.
Failed на самой первой `ready_current_runtime`, 0/1 passed; источники checker
совпадают с текущими67 и не менялись, original baseline SHA совпал.
Сохранность чатов/старых генераций ещё не проверялась. Ready body не был
записан до fail-fast; конкретное несоответствие runtime/status по JSON неизвестно.
Следующий шаг — read-only readiness/profile/runtime hash диагностика.

### Исправленный Mac upgrade и новый API baseline v2

Диагностика пользователя показала: local_version0.8.0, server profilev1,
runtime_source_unchanged=false, runtime_matches_local=false, изменены11 runtime
files. API продолжал использовать старый код после замены файлов. После bootout
первый bootstrap вернул5; повторный запуск зарегистрировал running PID27580.
Это наблюдения пользователя, не отдельный автоматический launchd restart proof.

Оригинальные новые JSON сохранены побайтово:

| Report | SHA-256 | Результат |
|---|---|---|
| [prompt-upgrade-20261010-214330.json](reports/verified/prompt-upgrade-20261010-214330.json) | `49ad006feaef5801c2643bf9af2a336714a5dba7a2c89b89c183d6d6a2ef08a4` | **30/30**, passed, 1.095s |
| [acceptance-baseline-v2-20261010-214340.json](reports/verified/acceptance-baseline-v2-20261010-214340.json) | `2000a986072a3aab41e36de5f9d4b2cbd080020bd10f6584b32f0bdca0cf28b5` | **259/259 technical, 13/13 quality**, passed, 218.774s |

Оба manifest67 совпадают с текущим checkout, sources unchanged. Server runtime
hashes совпадают, profilev2 до/после одинаков, Ollama0.40.2/Qwen digest/template
прежние. Upgrade baseline SHA совпал с originalv1. Все7 прежних history hashes
совпадают; все16 old generation IDs присутствуют с прежними v1 профилями,
ответами/status/metrics/exposed context/timestamps. Это не полный internal DB
snapshot audit; он покрыт также отдельным SQLite test.

Новый baseline: 10 sequential, 3 русских приветствия и 3 concurrent admissions,
всего16 completed, 7 чатов/32 сообщения. Нулевые failed/truncated/interrupted.
long_a=OK, long_b=OK; bounds6653/3704, long_b omits9 прежних пар, fullhistory20
сохранена. Ответы прочитаны: три acknowledgement, контрольные слова/исправление,
смена темы и русский язык соответствуют запросам. Original semantic_review
остаётся pending_human_review; последующая проверка записана здесь.
Качество этого regression набора принято, не объявляется универсальной гарантией.

Queue observed max2, inference interval overlap1; все3 concurrent literals
верные. Queue seconds0.00624/2.065356/4.151466.
401, replay same IDs/no duplication, context/body overflow без вставки сообщений
и HTTP429 passed. HTTP owner120/min отказал на101-м read-only probe с RetryAfter48:
предыдущие обращения тоже расходуют квоту. Generation admission quota10/min
не выдаётся за проверенную этим отдельным HTTP screen.

Resources:106 samples через2s, ошибок0, API RSS max65,748,992 bytes,
Ollama family RSS sum max10,681,090,048 bytes, reported size_vram max10,269,113,711
bytes; swap max/change0. RSS и size_vram нельзя складывать; RSS sum может
повторно учитывать shared pages, это не physical unified-memory peak/GPU proof.
Warm subsequent first-token median0.423562s, n9, p95(max)11.118592s с длинными
входами. Первый запрос наблюдался с незагруженной моделью, load4.094559s,
first-token4.986452s; forced cold eviction не было. Не заявляется сопоставимый
выигрыш скорости/памяти относительно v1 на основании этого единственного baseline.
Tailnet ports8000/11434 refused с самого Mac; physical remote observation отдельно.

### V2 saved history после заявленного API restart

[acceptance-history-v2-20261010-215306.json](reports/verified/acceptance-history-v2-20261010-215306.json)
сохранён побайтово, SHA-256
`7a0fefe15edfc057e449bd43f14b205f6ab294e15c44a248ea0770b34812e8e0`.
Passed **11/11**, 1.039s, baseline SHA совпал с original v2
`2000a986...cf28b5`, source67 текущий и unchanged, server current runtime matched.
Все7 history hashes/counts совпадают:32 сообщения с прежними IDs/status/text.
Model/profilev2 прежние, ready/idle без recovery gate. Read-only режим:
0 admissions/0 новых generations, quality/resources=not_run закономерно.
JSON history checker сам по себе не содержит процесса/OS epoch API.
Следующий LAN/launchd report подтверждает новый процесс относительно baseline.
Ports8000/11434 refused с Mac.

### V2 LAN HTTPS и новый процесс launchd

[launchd-lan-v2-20261010-215633.json](reports/verified/launchd-lan-v2-20261010-215633.json)
сохранён побайтово, SHA-256
`80b677a0c2fd0511d09ddfd30ab4c108bbab69f19baa65fac20f18c10ebeeafe`.
Passed **6/6**, 0.840s, HTTPS `https://192.168.0.247:8443`, kind=initial.
LaunchAgent running PID32253 владеет единственным listener `127.0.0.1:8000`;
baseline v2 наблюдал PID27580. Проверены private owned plist и ожидаемые настройки
supervisor. Ready/current runtime matched, source67 unchanged, profilev2 и
model identity прежние, queue/running=0, recovery gate=false.
Контрольный чат `6f0513265d2240d0b98ff91f9e804007` содержит прежние20 сообщений;
полный history hash `4c086cb4aafca505f771ca7b38829b993918982c846a67e0bb03fd0845871671`
совпадает с baseline. Вместе с history11/11 это подтверждает сохранность всех
семи контрольных диалогов после смены процесса API.
Caller — сам Mac через свой LAN IP: это проверенный маршрут Caddy/HTTPS,
не самостоятельное доказательство доступа другого физического LAN устройства.
Report не проверяет PID/KeepAlive Caddy LaunchAgent. OS boot witness baseline v2
отсутствует, поэтому сравнение этих двух отчётов не доказывает один OS epoch.

Новая runtime/Qwen recovery цепочка не
заявляется повторно выполненной: предыдущая real recovery относится к v1.

Current generation-admission 10/min независимо от скорости модели не проверяется
новым HTTP owner120/min screen: previous Mac + ASGI proofs сохраняются отдельно.
Exact deployed Tailscale policy/editor Save, direct LAN phone conditions и
независимые remote port observations требуют своих evidence. Текущий маршрут
Caddy/LAN HTTPS проверен отчётом6/6 выше; телефонные локальные сертификаты
отложены, основной мобильный путь — Tailscale Serve.
Home Screen installation вручную подтверждена, полный logout/background cycle
и версии физического OS/browser не представлены отдельно.
Logs content/secret regression покрыт suite; на Mac launchd stdout/stderr=/dev/null,
операционная диагностика ограничена. Forced API SIGKILL/soak и GPU/physical-footprint
измерения не выдаются за выполненные. Backup/restore и перенос owner history
отложены пользователем; Rust после курса, root README/финальный видео-сценарий —
этап 9/после полной реализации. Эти ограничения остаются видимыми.

## Финальное ручное подтверждение11 октября2026

Пользователь сообщил «все сработало» после уточнённой проверки: Mac сеть/Tailscale
включены; на телефоне Wi-Fi off/mobile on, chat через Tailscale работает, после
выключения Tailscale свежая вкладка недоступна, после включения доступ восстановлен.
Серверный CLI Serve/Funnel status и saved grants/ACL policy не приложены заново;
из manual confirmation не выводится аудит точных сетевых правил. Этап9 разрешён
пользователем отдельно утром11 октября. Backup/restore остаётся deferred.
