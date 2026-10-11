# Этап 8 — реальная приёмка, качество и ресурсы

Этап 8 начат по решению пользователя 2026-10-10, 22:43 Europe/Kiev.
Текущий runtime **0.8.0 / schema 2 / private-chat-v2** после live prompt сравнения.
Установка и новый API baseline: **[PROMPT_V2.ru.md](PROMPT_V2.ru.md)**.
Исторические baseline/recovery ниже выполнены с **0.7.0 / private-chat-v1**.
Qwen2.5:14b Q4_K_M, temperature=0, num_ctx=8192, max_output=1024, margin=512 прежние.
Старые snapshots не изменены.
Нет cloud LLM, model eviction, скрытого replay или изменения предыдущих дней.

Сначала baseline текущей Ollama **0.40.2**. По фактическим ответам решаем, нужно ли
исправление качества. Изменение prompt потребует отдельной версии и сопоставимого
повторного набора; нельзя объявить исправленным старый long_a на основании mock.
Operational backup/restore и перенос старой owner history остаются отложенными.
Историческая инструкция этапа 8: UI-видео позднее записано пользователем.

## 1. Обновление и подготовка

Распакуйте day-30-private-ai-service из нового архива в одноимённый каталог
репозитория. Личная база, token file, launchd и Caddy state находятся отдельно в
HOME и в архив не входят. Новых runtime-зависимостей и миграций здесь нет.
API/Ollama/Tailscale должны работать как после этапа 7; второй serve не запускайте.

```bash
cd /Users/litdi/AI/ai-advent-llm-api/day-30-private-ai-service
source ../.venv/bin/activate

curl --max-time 10 \
  "https://yuriys-macbook-pro.tail893c10.ts.net/api/v1/health/live"
```

Ожидается alive. Mac подключён к питанию и не спит. Завершите текущие ответы;
на время теста не отправляйте вопросы с телефонов и не используйте Ollama в Revik
или других уроках. Откройте только Qwen; другие модели автоматически не выгружаются.
Общая owner HTTP-квота намеренно исчерпывается в конце теста: временный 429 в UI
этого пользователя ожидаем и проходит по Retry-After. Не меняйте лимиты ради PASS.

## 2. Baseline — первый блок, который надо выполнить

Каждый запуск блока создаёт новый private каталог. Не удаляет старые отчёты.
Рабочая база читается/изменяется только через API: создаются **семь контрольных
диалогов, 16 генераций, 32 сообщения**. Содержимое прежних личных чатов не читается
и не включается в JSON. Частично неуспешный запуск может оставить меньше сообщений.

```bash
BUBLIK_STAGE8_DIR="$(mktemp -d "$HOME/bublik-day30-stage8.XXXXXX")"
printf '%s\n' "$BUBLIK_STAGE8_DIR"

python scripts/check_acceptance_live.py \
  --network tailnet \
  --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_STAGE8_DIR/baseline.json"
```

На машине с Qwen это может занять несколько минут и дольше при холодной загрузке
или длинных ответах. Есть progress по terminal cases и явные quota pauses;
пауза 61 s перед конкурентным batch нужна для нового окна квоты. Не прерывайте
рабочий API/Caddy и не перезапускайте модель во время baseline.

Передайте **baseline.json**. Даже status=failed полезен: нужен исходный JSON,
а не только последняя строка. Token file и личную SQLite не передавайте.
Если запущена неизвестная генерация после HTTP-обрыва, дождитесь idle; повтор
всего benchmark создаст другой набор тестовых чатов и не является recovery.
В report.requests остаются case/chat/idempotency key и известный receipt, но
автоматического replay при неоднозначном сетевом результате нет.

### Что проверяется

- Verified TLS/hostname, live, authenticated ready/current runtime, idle/gate.
- Без auth: 401. Context overflow: 422; body overflow: 413; история неизменна.
- Первый успешно принятый send replay: те же три IDs, история без дубля.
- 10 sequential multi-turn: RU/EN, reference/correction/topic change, long_a/b.
  Полная история=20 уникальных messages, omissions видимы, реальные counts <= bound.
- 3 greeting requests в отдельных chats без явного языкового override;
  screen требует кириллицу и отсутствие CJK. Это detector известной регрессии,
  а не полная проверка русского языка или содержательного качества.
- 3 concurrent admissions в разных chats: все ответы сохраняются, isolation
  controls, наблюдаемые queued/running и persisted execution intervals max=1.
  Это concurrency jobs сервиса, не независимое измерение вычислительных потоков GPU.
- Реальный HTTP owner rate limit 120/min: read-only requests до 429/Retry-After,
  восстановление чтения, неизменная history. В отличие от старого generation-quota
  теста результат не зависит от скорости десяти генераций. Отдельный 10/min
  generation limit уже покрыт ASGI/предыдущим Mac HTTP; current timing-independent
  proof этого admission limit здесь **not_run** и не подменён общей HTTP-квотой.
- После нагрузки: та же model identity/profile, ready/idle/no gate;
  direct ports 8000/11434 недоступны с calling Mac через выбранный сетевой host.
  Это Mac probe, не доказательство firewall с чужого физического устройства.

### Как читать результат

`technical_status` — протокол/хранение/лимиты/контекст/очередь/ресурсные observations.
`quality_status` — автоматические literal/language controls (passed/failed/incomplete).
Общий status passed требует оба блока и неизменные sources/закрытые порты.
Неверный ответ сохраняется и не останавливает остальные качественные кейсы.
`semantic_review=pending_human_review` остаётся до отдельного анализа ответов.
Строгий OK не заменяется на «похожий ответ» ради PASS.

## 3. Ресурсы и метрики

Collector требует macOS, тот же OS user, стандартный launchd label и loopback8000.
До/после проверяет isolated Ollama engine epoch; не читает argv или private messages.
Таблица ps ограничена 1 MiB, команды timeout=3 s. HTTP /api/ps только read-only.
Sampling interval=2 s плюс время измерения, max=1800 samples; ошибка наблюдения
явно делает resource/technical result failed, не превращается в оценку памяти.

В samples сохраняются выбранные API/Ollama-family PIDs, RSS в bytes, accumulated
user+system CPU seconds; CPU percent вычисляется по delta/реальному интервалу
для surviving PIDs (100%=один CPU core). Завершившиеся/новые processes могут не
попасть в delta. GPU utilization не измеряется. Другие executable names/argv
и полный ps dump не сохраняются.

Отдельно: vm_stat page size и free/inactive/speculative/wired/compressor/file-backed,
physical hw.memsize, swap used/free/total; Ollama reported size/size_vram/context.
RSS family sum может дважды учитывать shared pages. **Не складываем RSS и
size_vram**, не называем их суммой physical unified-memory peak. Free pages
не равны всей доступной macOS памяти: exact available RAM не заявляется.
Все maxima sampled; короткие spikes между samples могут быть пропущены.
Idle samples перед/после отделены phase; ожидание квоты тоже помечено phase.

Latency: queue wait, TTFT, total/inference/load, decode rate; median и nearest-rank
p95 с n по каждому полю/группе, terminal statuses отдельно. Первый request выделен;
указано, была ли Qwen уже loaded по pre-run metadata. Forced cold eviction не
выполняется, поэтому warm first request не выдаётся за cold measurement.
Измерения включают observer/polling overhead; это не сравнение Python/Rust.

Первоисточники:
[Apple ps](https://github.com/apple-oss-distributions/adv_cmds/blob/main/ps/ps.1),
[Apple vm_stat](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/ManagingMemory/Articles/VMPages.html),
[Ollama /api/ps](https://docs.ollama.com/api/ps).

## 4. Прерванный реальный ответ — после разбора baseline

Эти команды **не запускайте одновременно с baseline**. Это операционная проверка
недоступности всего inference сервиса; согласуйте время так, чтобы ни один личный
ответ не вычислялся. API и история остаются доступны. Scripts сами процессы не
останавливают и не выполняют recover-inference. Модель прерывает пользователь явно.

### Prepare и остановка Ollama

После двух коротких отказов Qwen писать 500 предложений checker обновлён:
control `forest-story-v2` просит рассказ из восьми подробных абзацев и сохраняет
actual status/text/metrics до отказа проверки. См. [RECOVERY_CHECKER_FIX.ru.md](RECOVERY_CHECKER_FIX.ru.md).
Default model prompt/profile не менялись. Новый control ещё предстоит проверить
на Qwen; длинный ответ не гарантируется. Старые failed reports сохраняйте.

В одной terminal session:

```bash
BUBLIK_RECOVERY_DIR="$(mktemp -d "$HOME/bublik-day30-recovery.XXXXXX")"
printf '%s\n' "$BUBLIK_RECOVERY_DIR"

python scripts/check_recovery_live.py prepare \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --output "$BUBLIK_RECOVERY_DIR/prepare.json"
```

Prepare создаёт seed turn и длинный запрос только в новом контрольном чате.
После строки `interrupt_Ollama_now` и passed prepare **сразу выйдите из Ollama.app**
обычным Quit. Это ещё running answer, а не законченный тест. Заранее подготовьте
меню Ollama, чтобы успеть до её завершения. API/Caddy/Tailscale оставьте работать.
Если длинный ответ успел закончиться, interruption не доказан; failed prepare
сохраняется. Не прерывайте другую/личную генерацию вместо контрольной.

После выхода Ollama дайте readiness cache обновиться (не менее 5 s). Следующий
script ожидает terminal до 90 s, включая stream timeout, и проверяет unavailable/gate.

```bash
python scripts/check_recovery_live.py interrupted \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --baseline "$BUBLIK_RECOVERY_DIR/prepare.json" \
  --output "$BUBLIK_RECOVERY_DIR/interrupted.json"
```

Ожидается failed/interrupted generation (не completed), исходный prefix partial
сохранён, seed history hash прежний, live200/history200, ready503/model unavailable/
gate=true. Новый send503 без добавленных сообщений. Неизвестное состояние engine
остаётся заблокировано; возвращение Ollama без явного recovery gate не снимает.

### Явный engine restart и recovery

Войдите в Ollama.app заново (именно новый процесс после Quit). Затем остановите
API supervisor, выполните прежний local operator recovery и загрузите API обратно:

```bash
launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"

python -m bublik_service \
  --db "/Users/litdi/bublik-day30-stage4.V1EM3F/chats.sqlite3" recover-inference
```

Только после успешного recover-inference:

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

Дождитесь API/model readiness. При ошибке recovery передайте safe error code.
Не запускайте old runtime к новой
схеме, не удаляйте gate/БД и не делайте автоматический replay interrupted answer.

```bash
python scripts/check_recovery_live.py restored \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --baseline "$BUBLIK_RECOVERY_DIR/interrupted.json" \
  --output "$BUBLIK_RECOVERY_DIR/restored.json"
```

Проверяет verified новый engine epoch, прежние model/profile, idle/gate=false,
полную terminal history и прежний generation ID/status. Создаёт отдельно новый
явный вопрос 2+2 в новом чате; старый ответ не повторяет. Эта последовательность
доказывает interrupted Ollama stream, **не forced API SIGKILL** и не backup.

## 5. История после ещё одного обычного API restart

Baseline допускается с technical_status passed даже при quality_status failed:
сохранность данных проверяется независимо от того, понравился ли ответ модели.
Используйте **тот же baseline.json / исходный каталог** из пункта 2. Sources между
измерениями не меняйте, контрольные чаты не дополняйте. После завершённых jobs:

```bash
launchctl kill SIGTERM "gui/$(id -u)/local.bublik.private-ai.api"
```

Дождитесь автоматического возвращения listener/ready (throttle до 30 s). Запускайте
в той же terminal session с ещё заданным BUBLIK_STAGE8_DIR; после смены terminal
задайте фактический путь из первого printf, а не пример /Users/ВАШ_ПОЛЬЗОВАТЕЛЬ.

```bash
python scripts/check_acceptance_live.py \
  --network tailnet --url "https://yuriys-macbook-pro.tail893c10.ts.net" \
  --token-file "/Users/litdi/bublik-day30-stage4.V1EM3F/check-token.json" \
  --history-from "$BUBLIK_STAGE8_DIR/baseline.json" \
  --output "$BUBLIK_STAGE8_DIR/history-after-restart.json"
```

Это read-only: все 7 полных history hashes/counts, identity/profile/source,
порты; нет новых генераций/resource benchmark. Повторные запуски всегда требуют
NEW output: например history-after-restart-v2.json; originals не перезаписываются.

## 6. Остальная финальная матрица

- LAN/Caddy после reboot всё ещё открыт. Проверьте launchctl Caddy state=running,
  health через прежнюю LAN CA без -k. IP192.168.0.247 должен оставаться текущим:

```bash
launchctl print "gui/$(id -u)/local.bublik.private-ai.caddy"
curl --max-time 10 \
  --cacert "$HOME/bublik-day30-stage6/caddy-data/caddy/pki/authorities/local/root.crt" \
  "https://192.168.0.247:8443/api/v1/health/live"
```

- Прямой HTTP loopback live в proxy mode может вернуть secure_transport_required;
  это не отсутствие сервера. Настоящий TLS endpoint должен отвечать alive.
- Телефон LAN без Tailscale и mobile с Wi-Fi off: реальный новый completed turn,
  один chat ID, синхронизация с Mac; stage6 originals и ручные результаты сохраняются.
- Android/iPhone home-screen запускаются после reboot, история/reopen/background,
  logout/login. Укажите OS/browser versions при возможности. Операции установки
  уже вручную подтверждены; synthetic browser не заменяет hardware acceptance.
- Serve/Funnel status должно оставаться tailnet only, без публичного Funnel.
  Grants policy проверяется в admin editor + policy tests/Save отдельно; ни HTTPS
  response, ни Mac port probe не доказывают фактически сохранённую policy.
- Ollama listener только loopback; phone/other-device port test нужен отдельно
  от Mac собственных address probes. Изоляция engine проверяется OS epoch probe.
- Launchd API stdout/stderr=/dev/null, Caddy access/content logging не включается.
  Содержимое личных чатов/секреты в reports/logs не копируется. Raw ps/status всех
  peer devices и token JSON не публикуйте. Изменение политики diagnostics — backlog.
- CPU/RAM/качество и interrupted-generation report ещё требуют реального Mac run.
  Полная финальная приёмка не достигнута от одного passed offline report.

## 7. Автоматическая проверка реализации harness

```bash
python -W error::ResourceWarning scripts/check_storage.py \
  --output "$BUBLIK_STAGE8_DIR/offline.json"
python scripts/verify_report.py "$BUBLIK_STAGE8_DIR/offline.json"
```

Tests исполняют acceptance workload через SQLite/ASGI и настоящие HTTPS sockets
с проверкой сертификата; inference/OS observer в них synthetic. Проверены quality
failure accounting, resource failure, no ambiguous POST retry, exact 429 replay,
partial/gate/epoch/no old replay, CPU/RSS/page/swap parsers и overlap witness.
Реальную сеть, текущую macOS ps/vm_stat или Qwen это автоматически не доказывает.

## 7. После успешного recovery — quality experiment

Recovery21/21 → 9/9 → 15/15 подтверждён. Новый frozen-context ABBA comparison
описан в [PROMPT_EXPERIMENT.ru.md](PROMPT_EXPERIMENT.ru.md): его запуск сам
не менял рабочий prompt. Live результат принят: candidate26/26, v1 24/26;
long_a исправлен дважды. Текущий runtime0.8.0 внедряет текст как private-chat-v2
с сохранением старых snapshots. Следующий шаг — [Mac upgrade/new API baseline](PROMPT_V2.ru.md).
