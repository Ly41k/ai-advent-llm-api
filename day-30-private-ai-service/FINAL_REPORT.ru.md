# День 30 — итоговый отчёт Bublik Private AI Service

Дата оформления: **2026-10-11**. Реализация и документация этапов1–9 готовы.
Основной сценарий приватного чата принят на MacBook/Android/iPhone в проверенной
конфигурации. Это повторно используемый фундамент приватного AI-чата;
автономные действия не входят в текущую реализацию.

Live evidence получены на Mac пользователя 9–11 октября; offline/browser/package
fixtures выполнены отдельно на Linux. Этап9 меняет документацию, а не runtime:
67 source files и 27 runtime files соответствуют сохранённым v2 отчётам.
Новые живые испытания с Mac из среды разработки не заявляются.

## Требования курса, расширения, отложенные задачи

| Область | Результат |
|---|---|
| Курс: домашний сервер, локальная модель, HTTP API, чат | MacBook + FastAPI + Ollama/Qwen, `/api/v1`, Web UI |
| Курс: сеть и несколько запросов | Телефон через mobile/Tailscale, 10 последовательных и 3 конкурентных API admission |
| Курс: rate limit / max context | 429/Retry-After, durable quotas, bounded inference suffix, omission и oversize rejection |
| Расширения | Owners, несколько диалогов, SQLite history, cross-device sync, auth/CSRF/TLS, idempotency, очередь, partial/recovery, launchd/PWA, отчёты |
| Отдельно после реализации | Operational backup/restore и перенос console-owner истории; телефонные LAN CA настройки |
| После курса | Сопоставимый Python→Rust benchmark; голос/tools/RAG только отдельными решениями |

Облачных LLM или cloud fallback нет. Tailscale — транспорт, включая возможный
зашифрованный relay; Qwen inference и SQLite история остаются на Mac. Доступ извне
требует tailnet, а приложение дополнительно требует собственную авторизацию.

## Проверенная конфигурация

| Параметр | Значение |
|---|---|
| Hardware / OS | MacBook Pro M1, 32 GB unified memory; macOS Darwin arm64 |
| Python / SQLite на Mac | 3.13.3 / 3.49.1 |
| Runtime / schema / API | 0.8.0 / 2 / v1 |
| Ollama в итоговом baseline | 0.40.2 |
| Model / quantization | qwen2.5:14b / Q4_K_M |
| Model digest | `7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6` |
| Template SHA-256 | `eb4402837c7829a690fa845de4d7f3fd842c2adee476d5341da8a46ea9255175` |
| Temperature / context / max output / margin | 0 / 8192 / 1024 / 512 |
| System prompt | private-chat-v2, 213 UTF-8 bytes; v1 snapshots сохранены |
| Network | API127.0.0.1:8000, Ollama127.0.0.1:11434, Serve HTTPS443, LAN Caddy HTTPS8443 |
| Persistence | SQLite WAL, synchronous=FULL, FK checks, private files, versioned migrations |

Одна активная генерация, восемь queued slots, три outstanding на owner. Квоты:
10 accepted generations/min/owner, 120 authenticated HTTP requests/min/owner.
Максимумы: body32KiB, user text16KiB UTF-8, output1024tokens/64KiB сохранённого текста.
Inference input upper bound≤6656, не точный tokenizer. Параметры дня29 оказались
пригодны для проверенных multi-turn сценариев; не заявляется универсальное качество
или способность помнить за пределами переданного суффикса.

## Итоговая матрица

| Проверка | Фактический результат | Evidence / предел |
|---|---|---|
| Реальный HTTP+Qwen baseline v2 | **259/259 technical**, **13/13 quality**, 16 completed | [baseline](reports/verified/acceptance-baseline-v2-20261010-214340.json); 218.774s |
| 10 sequential | Все10 completed, RU/EN references/correction/math, long_a/b=OK | Динамическая история, не mock |
| 3 concurrent HTTP requests | Три202/completed, max overlapping inference=1, queued max2 | Очередь сериализует Qwen, это не три parallel inference |
| Rate limit | HTTP429 на101-м read probe, Retry-After48, без изменения истории | Уже использованные requests входят в120/min; отдельную generation quota этот probe не доказывает |
| Generation admission quota | Earlier Mac stage4 + текущие ASGI transactional tests | [HTTP65/65](reports/verified/http-live-20261009-223827.json), offline suite; не новый независимый v2 live quota run |
| Max context / max request | Omission9 completed pairs в long_b; oversize422/body413 без вставки сообщений | long_a upper bound6653≤6656; actual prompt count≤bound |
| Без авторизации | 401 для protected routes | Реальный HTTPS/API baseline |
| Чужой owner / CSRF / secret handling | Repository/ASGI/TLS/browser isolation и rejection passed | Synthetic inference security regressions; не независимый внешний pentest |
| Idempotency / delivery retry | Replay возвращает те же IDs, нет дубликатов/новой генерации | Реальный API + offline races/process tests |
| Старые истории v1→v2 | **30/30**, семь чатов/16 старых generations unchanged | [upgrade](reports/verified/prompt-upgrade-20261010-214330.json), старые profile/exposed context metadata/answer/status/metrics/times |
| Новый history после API restart | **11/11**, семь чатов, 32 сообщения и полные hashes прежние | [history](reports/verified/acceptance-history-v2-20261010-215306.json) |
| Новый процесс + текущий LAN | **6/6**, API PID32253 вместо27580, listener только127.0.0.1:8000 | [launchd/LAN](reports/verified/launchd-lan-v2-20261010-215633.json); caller сам Mac, не телефон без Tailscale |
| Телефон через mobile internet | Android physical handoff **8/8**, после restart **8/8** | [handoff](reports/verified/device-verify-20261010T180635-1c0e31e2.json), [after restart](reports/verified/device-verify-after-restart-20261010T180935-607caa57.json); physical/network conditions declared вручную |
| Android/iPhone/Mac sync | Общие диалоги и сохранённые ответы подтверждены пользователем | Manual, не automated three-device measurement |
| Текущий mobile/Tailscale off/on | Пользователь11 октября подтвердил весь предложенный телефонный сценарий | После выключения доступ пропал, после включения восстановился; новый CLI status snapshot не приложен |
| PWA home screen | Android и iPhone установлены и новый сохранённый ответ виден на Mac | Manual; fixture **11/11** отдельно |
| Ollama off/on | Live остаётся200, history читается, ready/new inference безопасно unavailable, после восстановления работает | Operational Mac off/on вручную; stage4 |
| Реальный разрыв Ollama stream/recovery | **21/21 → 9/9 → 15/15**, partial707 chars сохранён | [prepare](reports/verified/recovery-prepare-20261010-204716.json), [interrupted](reports/verified/recovery-interrupted-20261010-204758.json), [restored](reports/verified/recovery-restored-20261010-205125.json); runtime0.7/v1 |
| Recovery без replay | Failed/invalid_model_response, persistent gate, новый verified OS engine epoch, новый explicit запрос completed | Эта live цепочка не повторялась на v2; stream/recovery logic не изменена |
| Ollama isolation | Literal loopback listener/OS witnesses, LAN/tailnet8000/11434 probes refused | Probes с самого Mac; independent physical remote port scan не представлен |
| launchd restart/reboot | Initial6/6, restart11/11, reboot API/history/new OS boot подтверждены | Strict reboot original failed: Ollama0.34.4→0.40.2, weights/template/profile прежние; не переписан как PASS |
| Offline current sources | **143/143**, 46.719s | [offline](reports/verified/stage8-prompt-v2-offline.json), Python3.13.16/Linux, synthetic inference |
| Chromium current sources | **26/26**, 24.394s | [browser](reports/verified/stage8-prompt-v2-browser.json), actual TLS/SQLite/browser, synthetic model |
| PWA fixture current sources | **11/11**, 2.915s | [PWA](reports/verified/stage8-prompt-v2-pwa.json), не Safari/физический телефон |
| Wheel installation | **10/10** | [package](reports/verified/stage8-prompt-v2-package.json), отдельный clean venv вне checkout, 27runtime hashes/7UI assets |

Полный API и истории отделены от краткосрочного inference context. Cookies разных
origins/устройств — разные browser sessions; общий owner видит одни chat IDs.
`202` подтверждает commit admission. «Ответ сохранён» появляется для persisted result;
несохранённые deltas не выдаются за durable history. Внешний inference exactly-once
при произвольном crash не обещается; uncertain gate предотвращает скрытый replay.

## Качество: исходная ошибка и проверенное исправление

Исходный v1 baseline technical259/259, quality**12/13**: long_a ответил `lantern`
вместо `OK`. Original JSON сохранён как есть. На одинаковых frozen inputs выполнили
ABBA:64 generations, candidate**26/26** против v1**24/26**, long_a исправлен дважды.
[Сравнение](reports/verified/prompt-compare-20261010-211034.json) не подменяло контекст
ответами кандидата. В инструкции нет hardcoded `OK`/`lantern`.

В runtime0.8.0 кандидат зарегистрирован как private-chat-v2. Новый API baseline
с динамической историей подтвердил**13/13**, RU greetings без CJK, correction/reference
и длинные кейсы верны. Ответы прочитаны и reviewed в [VALIDATION.stage8.ru.md](VALIDATION.stage8.ru.md).
Original JSON semantic_review=pending_human_review не переписан задним числом;
оценка оформлена в документации. Это узкий регрессионный набор, не общий benchmark
интеллекта и не гарантия следования любой инструкции. Temperature0 не гарантирует
битовую воспроизводимость.

Upgrade checker сверяет доступные через API context metadata и полные страницы
сообщений. Это не отдельный полный SQL-аудит внутренних context snapshots;
их immutable persistence дополнительно покрывается storage/runtime tests.

## Объективные метрики v2

| Метрика | Наблюдение | Метод / ограничение |
|---|---:|---|
| API RSS max | 65,748,992bytes ≈62.70MiB | macOS sampled process RSS |
| Ollama family RSS sum max | 10,681,090,048bytes ≈9.95GiB | Sum может повторно учитывать shared pages |
| Ollama reported size_vram max | 10,269,113,711bytes ≈9.56GiB | Reported allocation, не отдельная дискретная VRAM M1 |
| Swap max / change | 0 / 0bytes | Во время этого run |
| API CPU interval max | 38.94649% | 100%=один CPU core, sampled user+system |
| Ollama family CPU interval max | 66.95462% | GPU utilization не измерялась |
| Samples | 106, каждые2s, errors0 | Transient peaks между samples могут быть пропущены |
| Первый запрос load / TTFT | 4.094559s / 4.986452s | Model not loaded перед run; n1, forced eviction не было |
| Следующие sequential TTFT median / p95 | 0.423562s / 11.118592s | n9; nearest-rank p95=max, включает длинные inputs |
| Следующие sequential total median / p95 | 0.686142s / 11.19724s | Та же группаn9 |
| Три concurrent queue waits | 0.00624 / 2.065356 / 4.151466s | Observable serialized inference |

RSS и size_vram **нельзя складывать** в physical unified-memory peak. Free-page
counter не называется available RAM. Не заявляем GPU/physical footprint, controlled
cold/warm comparison или ускорение/экономию от prompt v2 по одному baseline.
Prompt ABBA client-time medians были близкими; там нет сопоставимого RSS/TTFT
исследования. Keep-alive модели5m; клиент/API не гарантирует отсутствие других
моделей, загруженных сторонними Ollama workflows. Ресурсные tests выполнялись без
параллельного RAG/Revik; bge-m3 здесь не нужен.

## Ограничения и задачи после этапа9

- Независимый аудит сохранённой Tailscale grants/ACL policy, policy tests и свежий
  Serve/Funnel status snapshot не приложены. Earlier status=tailnet only и ручной
  mobile off/on подтверждены; это не доказательство запрета любому другому tailnet owner.
- Прямой LAN HTTPS есть и проверен с Mac. Точный phone Wi-Fi без Tailscale/с LAN CA
  не зафиксирован отдельным актуальным отчётом; пользователь отложил CA setup.
- Нет независимого physical remote port scan или pentest. Listener isolation и
  Mac probes не выдаются за внешнее измерение firewall.
- LaunchAgents требуют user login, Mac awake и работающие Ollama/Tailscale. Strict
  reboot report с изменившейся engine version сохранён failed. Current LAN report
  подтверждает route/new API PID, не отдельный Caddy PID/KeepAlive audit.
- Operational backup/restore, retention/off-host copies и console-owner transfer
  отложены пользователем; storage backup API/tests есть. SQLite FULL не защищает
  от утраты диска или отсутствия резервной копии.
- Forced API SIGKILL, долгий soak, physical-footprint/GPU measurements, полный
  browser logout/background matrix и точные версии телефонных браузеров не выполнены.
- Export материализует snapshot в RAM; exact tokenizer и summary/retrieval старой
  истории — будущие улучшения. Нет Markdown renderer/voice/tools/RAG по умолчанию.
- Пользователь опубликовал поставку в main:
  `d6c651c75d8f44c99f4780a3dffb9f1c8c5ef348`, 11 октября 2026.
  UI-видео с сообщениями с телефонов записано по подтверждению пользователя;
  видеозапись здесь не анализировалась. Консольный сценарий остаётся необязательным.

Backlog: [BACKLOG.ru.md](BACKLOG.ru.md). Rust не внедряется; будущее сравнение
измеряет API overhead отдельно от Qwen/KV-cache. Исходная история и управляемые
миграции/backup должны сохранять данные при смене моделей и оборудования.

## Документы и индекс

RU/EN README дня и корня обновлены; API/architecture/runbook/checklist/backlog/video
согласованы с текущим runtime. Исторические JSON не перезаписаны. Финальный
`reports/verified/stage9-final.json` содержит отдельные hashes и результаты
проверки документации/доставки; это не новый live report. Он фиксирует документацию
на момент поставки этапа 9. После текущих Markdown-правок его documentation hashes
закономерно отличаются; исходный JSON не переписывается. Runtime/source manifest
не изменился, сохранённые v2 тестовые отчёты остаются применимыми.

Root README входят в корпус дня21; новые тексты меняют fingerprint. Индекс не
пересобирался здесь. Перед следующим strict RAG live run из корня:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

README самого дня30 автоматически не входит в frozen corpus1–20; день30 не использует
RAG/knowledge.db. Исторические Day21–29 evidence сохраняют исходный corpus identity.
