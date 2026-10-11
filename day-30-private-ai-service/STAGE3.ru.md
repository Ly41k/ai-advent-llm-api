# Этап 3 — локальный inference, контекст и очередь

Код реализован, offline-проверки выполнены. **Live-приёмка на твоей Qwen ещё
не проведена.** Сетевого API и Web UI пока нет. Терминальный чат нужен для
проверки inference до следующих этапов; это не сценарий видеодемонстрации.

Этапы 1–2 приняты на MacBook: приложенный отчёт Python 3.13.3 / SQLite 3.49.1 /
Darwin arm64 содержит 51 passed, 0 failures/errors/skips. Manifest совпал с
выданными исходниками до изменения этапа 3. Ручные init/reopen/backup и отказ
перезаписи прошли. Копия исходного отчёта хранится в `reports/verified/` без правок.
Его старое поле `not_run: macOS/M1 hardware` — дефект статического списка старого
runner: среда и тесты подтверждают storage-прогон на Mac. Это не Qwen benchmark.

## Что добавлено

- HTTPX AsyncClient: только literal loopback, без env proxies, redirects, retry
  inference или cloud клиента; bounded NDJSON и общий deadline.
- Doctor: OS loopback listener/epoch, Ollama version, local GGUF/Q4_K_M/14B,
  tokenizer, exact template SHA, parameters SHA, model digest и loaded allocation.
- ContextBuilder: system + последний подходящий полный suffix completed пар +
  текущий вопрос. Полная история сохраняется; failed/interrupted/truncated не
  включаются. Oversized текущий вопрос отвергается, не обрезается.
- ChatService: replay до readiness, owned revision, подготовка контекста и
  atomic admission. Owner приходит от будущего HTTP auth, не из browser JSON.
- Один Coordinator/WorkerSession: FIFO, expiration, stream checkpoints, terminal
  commit, graceful shutdown/cancellation и recovery gate.
- `doctor`, `chat`, `recover-inference` CLI; самостоятельный live harness.

Schema остаётся **1**; существующая база не пересоздаётся. Identity хранится в
context snapshot, dispatch epoch/uncertainty — lifecycle metadata в том же JSON.
Prompt/profile не переписываются. Старый stage-2 queued job без identity получает
явный failed без inference; вопрос остаётся, новый retry получает текущий профиль.
Disabled operator marker не является паролем и не должен пройти будущий Argon2 login.

## Установка

Распаковать архив в корень репозитория с обновлением каталога дня 30.
Базы и пользовательские отчёты `reports/check/` в архив не входят.

```bash
source .venv/bin/activate
cd day-30-private-ai-service
python --version
python -m pip install -r requirements.lock
python -m bublik_service init-db
python -W error::ResourceWarning scripts/check_storage.py
```

Последний вызов теперь проверяет storage **и** synthetic inference; пишет новый
отчёт с форматом `bublik-offline-check-v2`. Старые verified JSON не перезаписываются.
Проверять новым verifier новый report; исторический manifest закономерно не
совпадает с изменённым stage-3 checkout.

## Подготовка Ollama на MacBook

Зарезервировать окно без Revik, других уроков и клиентов Ollama. Не запускать
параллельно второй Ollama server. Нужна уже установленная `qwen2.5:14b` Q4_K_M;
сервис не делает автоматический pull, unload, upgrade или restart.

Для Ollama.app рекомендуемые настройки:

```bash
launchctl setenv OLLAMA_HOST "127.0.0.1:11434"
launchctl setenv OLLAMA_NO_CLOUD "1"
launchctl setenv OLLAMA_NUM_PARALLEL "1"
launchctl setenv OLLAMA_MAX_LOADED_MODELS "1"
```

Применяются после **явного штатного Quit Ollama пользователем** и нового запуска:

```bash
open -a Ollama
ollama --version
ollama list
ollama ps
lsof -nP -iTCP:11434 -sTCP:LISTEN
python -m bublik_service doctor
```

Этот restart прерывает работу других локальных клиентов, поэтому выполняется
в зарезервированном окне, не скрытно сервисом. Если используешь `ollama serve`
вместо app, те же переменные задаются окружению этого процесса; второй сервер
поверх работающего app не запускается.

Doctor не генерирует текст и не загружает модель. Ожидаются local identity,
quantization Q4_K_M, known template hash и engine epoch. `loaded_models` может
быть пустым. Default profile: temperature 0, output 1024, context 8192, margin 512.

| Отказ doctor | Что проверить |
|---|---|
| `engine_process_unverified` | Ollama работает под тем же OS user; доступны lsof/ps |
| `ollama_listener_not_isolated` | Только 127.0.0.1/::1, нет wildcard/LAN listener |
| `orphan_or_other_ollama_process` | Остался старый runner или второй Ollama; завершить его штатно и перепроверить |
| `unexpected_loaded_model` | В `ollama ps` загружена другая модель; решить вручную, не выгружается сервисом |
| `loaded_context_mismatch` | Qwen осталась загружена с другим context; завершить её использование и вручную `ollama stop qwen2.5:14b` |
| `unsupported_template` / `unsupported_model_metadata` | Сохранить диагностику модели для ревью; не обходить проверку и не менять hash автоматически |

OS witness проверяет names/parents процессов без чтения argv с личными prompts.
Новый server epoch принимается только при отсутствии известных orphan runners.
Один лишь `/api/ps` не доказывает отсутствие активного вычисления.
Это также не заменяет remote-тест недоступности порта 11434 на этапе 6.

## Терминальный multi-turn чат

```bash
python -m bublik_service chat
```

Сохрани напечатанный `chat_id`. Например, отправь:

1. `Запомни: контрольное слово — мандарин.`
2. `Какое контрольное слово я назвал?`
3. `/history`
4. `/quit`

Повторное открытие той же истории:

```bash
python -m bublik_service chat --chat-id CHAT_ID_ИЗ_ПРЕДЫДУЩЕГО_ЗАПУСКА
```

Команды `/new`, `/history`, `/retry`, `/recover`, `/quit` относятся только к
локальной консоли. `/retry` повторяет последний retryable вопрос без нового user
message. Открывать chat должен тот же `--username` (default local-stage3-operator).
CLI читает запись через локальные права OS; browser login появится на этапе 4.
Текст показывается в явном интерфейсе чата, не в служебных логах.

## Реальная приёмка Qwen

```bash
BUBLIK_STAGE3_REPORT="reports/check/mac-stage3-live-$(date +%Y%m%d-%H%M%S).json"
python scripts/check_inference_live.py --output "$BUBLIK_STAGE3_REPORT"
```

Испытание создаёт **новую отдельную базу** рядом с отчётом. Содержит только
фиксированные синтетические вопросы/ответы; не читает личные чаты из default DB.
13 inference: 10 последовательных, затем 3 конкурентных admission в разных
чатах. Плюс replay, long-history omission, oversized question rejection,
actual prompt count <= supplied upper bound, полный history reopen.

Ожидается `status: passed`, 13 completed, все checks passed, max active = 1.
Проверить глазами RU/EN ответы и corrections: substring controls не заменяют
общую оценку качества. Ошибка/обрыв не перезапускает сценарий скрытно. Даже при
ошибке сохраняются накопленные observations и база; для повторения нужны новые пути.

Записаны queue wait до claim, время POST/stream с checkpoint I/O, TTFT до первого
текстового fragment, Ollama eval/load duration, tokens и decode rate.
Loaded size/size_vram — отдельные наблюдения, не physical RAM peak. CPU/RSS/swap,
длительный stability benchmark и HTTP network acceptance остаются этапу 8.

## Обрыв и восстановление

При неоднозначном timeout/EOF/cancellation частичный сохранённый текст остаётся,
attempt получает failed/interrupted, persistent gate блокирует новые admission
и следующие claim. Idempotent replay сохранённого запроса остаётся доступен.

Для проверки после успешного live run: начать запрос в консоли, остановить
Ollama в другом терминале/через Quit, дождаться явного failed/interrupted,
проверить `/history`. Полностью перезапустить Ollama штатно, затем `/recover`.
Recovery требует смены OS listener epoch и отсутствия orphan Ollama runners;
без фактического restart прежнего server gate не снимается. Затем `/retry`.
Старая попытка сохраняется, вопрос не дублируется. Сервис сам Ollama не убивает.

Если консоль уже завершена:

```bash
python -m bublik_service recover-inference
python -m bublik_service chat --chat-id CHAT_ID
```

Crash до commit dispatch epoch в stage-3 job допускает `verified_no_dispatch`:
это доказательство, что POST этим сервисом не отправлялся. Legacy interrupted
job без stage-3 identity не имеет проверяемого restart witness и gate автоматически
не обходится. Не удалять базу и не менять service_state вручную для обхода.

## Область доказательств

Offline tests используют real SQLite/processes и synthetic loopback HTTP fixture;
engine witness имеет unit fixtures. Они не доказывают Qwen, качество или сеть.
Наш сохранённый Linux offline отчёт: `reports/verified/stage3-offline.json`.
Твой live JSON и manual observations нужны для завершения приёмки этапа 3.
LAN, мобильный интернет, HTTP auth/rate limit и PWA не реализованы здесь.

## Источники контракта

- https://docs.ollama.com/api/chat
- https://docs.ollama.com/api-reference/show-model-details
- https://docs.ollama.com/faq
- https://ollama.com/library/qwen2.5:14b/blobs/eb4402837c78
- https://www.python-httpx.org/async/

Для reviewed no-tools ChatML overhead ограничен 128 bytes/message + 128 prefix/BOS;
контент считается UTF-8 bytes, не эвристикой bytes/4. Для byte BPE это conservative
upper bound. Known template/tokenizer проверяются before admission/dispatch,
а live count проверяется после inference. Это не exact tokenizer: usable history
может быть существенно короче actual token window. Улучшение счётчика требует
отдельной проверки совместимости, а не изменения old snapshots.
