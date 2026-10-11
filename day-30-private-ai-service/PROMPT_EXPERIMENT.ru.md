# Этап 8: сравнение системных инструкций

**Историческая инструкция для runtime0.7.0.** Live сравнение принято:
candidate26/26 против v1 24/26, long_a исправлен в обоих повторениях.
Текущий runtime0.8.0 использует private-chat-v2; установка и следующий контроль
описаны в **[PROMPT_V2.ru.md](PROMPT_V2.ru.md)**. Старую процедуру ниже с новым
runtime не запускайте: original v1 source guard намеренно её остановит.

Recovery принят: prepare21/21, interrupted9/9, restored15/15. Исходная проблема
long_a (`lantern` вместо `OK`) сохранена в v1 отчёте. Реальное frozen сравнение
и следующий dynamic v2 baseline13/13 подтвердили исправление этого кейса;
историческая процедура ниже описывает состояние до внедренияv2.

## Что меняется

Новый `scripts/check_prompt_compare.py` сравнивает исходный private-chat-v1 с
экспериментом candidate-latest-request-v1: новая инструкция явно связывает ответ
с последним запросом и его форматом, история используется как контекст.
Нет специального правила для OK или lantern, temperature/context/output прежние.
Рабочий system prompt, профиль, API/UI, schema2 и личная история **не меняются**.
Кандидат пока не зарегистрирован как серверный профиль и не записывается в DB.

Контексты воспроизводятся из оригинального baseline.json и прежних CASES.
Проверяются runtime hashes, profile, case-script hash и восстановленные bounds/
omissions. У обеих инструкций одна и та же frozen история user/assistant и
текущий вопрос. Новые candidate ответы не добавляются в последующие inputs.
Это точечная проверка инструкций на фиксированной multi-turn истории, не
динамический чат с памятью кандидатной версии и не доказательство её внедрения.

Порядок блоков **A → B → B → A**, по 16 запросов: всего **64 генерации**,
по два повторения каждого кейса для каждой инструкции. 13 quality controls
на повторение (26 на вариант), три initial acknowledgements требуют human review.
Строгие literals не ослабляются, Russian screen не заменяет полноценный review.
Long_a reference bound=6613, candidate=6653 при budget=6656; history одинаковая.
Model digest/template/Ollama version/verified epoch обязаны совпадать с baseline.

Прямой вызов только localhost Ollama, без HTTP API сервиса, paid LLM, tools,
cloud fallback, model eviction или личных DB/token reads. API временно остановлен,
чтобы не пересекаться с benchmark. Оператор также не запускает Revik/другие
Ollama clients. Скрипт проверяет refusal127.0.0.1:8000 перед каждой генерацией,
но это не универсальная блокировка других локальных клиентов или GPU witness.
Он не останавливает/запускает процессы самостоятельно.

Ollama `/api/chat` используется с stream=false: response body <=2MiB,
timeout300s/connect3s, redirects/proxies/retries выключены. Контролируются
terminal/model/role/counters/output/context. Метрики client total, eval/load и
tokens/s не сравниваются напрямую с прежним streaming API first-token timing.
First token, RSS/CPU/GPU/physical-memory здесь not_run; loaded models наблюдаются
doctor отдельно. Forced cold eviction отсутствует. Официальный контракт:
https://docs.ollama.com/api/chat

## Подготовка

Распакуйте day30-stage8-prompt-experiment.zip в корень репозитория с заменой
файлов дня 30. Runtime 0.7.0 и все 27 runtime bytes прежние; API не надо
перезапускать только ради установки scripts. Полный source manifest теперь66,
старые baseline/recovery reports исторические и не перезаписываются.

Используйте исходный baseline.json из первого успешного technical workload.
В той же terminal session переменная BUBLIK_STAGE8_DIR обычно ещё задана.
Если консоль новая, задайте её фактическим каталогом первого baseline, который
вывел mktemp; путь не угадывать. Следующая команда проверяет input **до** API stop:

```bash
python - "$BUBLIK_STAGE8_DIR/baseline.json" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from check_prompt_compare import load_baseline, frozen_cases
baseline, digest = load_baseline(Path(sys.argv[1]))
print({"frozen_cases": len(frozen_cases(baseline)), "baseline_sha256": digest})
PY
```

Ожидается frozen_cases16. При ошибке input API пока не останавливайте; передайте
вывод. Original baseline accepted даже с quality_statusfailed; полный старый source
не обязан совпадать с новыми scripts, но runtime/profile/CASES обязаны совпасть.
Новые live quality reports не притворяются старым 64-file source запуском.

## Запуск

Завершите личные генерации, не отправляйте сообщения с устройств во время теста.
Mac подключён к питанию и не спит. Ollama/Tailscale/Caddy оставьте работать.
После bootout приватный чат временно недоступен через reverse proxy — это
ожидаемое следствие остановки API, не сбой сертификатов.

```bash
BUBLIK_PROMPT_DIR="$(mktemp -d "$HOME/bublik-day30-prompt.XXXXXX")"
printf '%s\n' "$BUBLIK_PROMPT_DIR"

launchctl bootout "gui/$(id -u)/local.bublik.private-ai.api"
```

Только после успешного bootout, в той же консоли:

```bash
python scripts/check_prompt_compare.py \
  --baseline "$BUBLIK_STAGE8_DIR/baseline.json" \
  --confirm-exclusive-engine-use \
  --output "$BUBLIK_PROMPT_DIR/compare.json"
```

64 progress records, обычно несколько минут; реальная длительность не гарантируется.
Все вызовы последовательные — это не новый concurrency benchmark. Не прерывайте
инференс и не стартуйте API/Ollama clients в середине. Выходной файл новый0600,
старые reports не перезаписываются. Ответы только synthetic контрольных inputs.
Неоднозначный POST не повторяется автоматически.

## Завершение и интерпретация

Итоговая строка содержит inference_outcome_unknown. При **false** запросы имеют
известное terminal состояние (или dispatch не было); можно вернуть API:

```bash
launchctl bootstrap "gui/$(id -u)" \
  "$HOME/Library/LaunchAgents/local.bublik.private-ai.api.plist"
```

При **true** не запускать API до явного Quit/restart Ollama: timeout/transport
ошибка не доказывает завершение GPU work. После нового процесса API doctor
проверит epoch/isolation/orphan runners. Передайте compare.json для анализа;
не удалять DB/gate и не replay неизвестный experimental запрос. Benchmark не
создаёт durable jobs в рабочей DB, поэтому её recovery gate не изменяется.

Общий passed означает technical passed и **26/26 candidate controls**, sources
unchanged. Исходный вариант может failed — это допустимый baseline сравнения.
`improvement_observed_cases` отдельно показывает, где кандидат прошёл оба повтора,
а исходный вариант ошибся хотя бы раз. Если оба варианта проходят, нельзя заявлять,
что конкретный old long_a воспроизведён и исправлен. Полный human review остаётся.

На момент подготовки эксперимента сервис использовал private-chat-v1. После анализа live JSON
выбираем: принять candidate как НОВУЮ server prompt version с registry/budget/
snapshot tests и повторным API baseline/history, или продолжить эксперимент.
Нельзя заменить текст под старым private-chat-v1 и переписать прошлые snapshots.
Старые chats, message/generation IDs, model/profile/context snapshots сохраняются.
Rust, RAG и backup/owner transfer этим экспериментом не внедряются.

Проверка реализации: targeted4/4, полный suite **140/140** (45.364s),
ResourceWarning как ошибка; source66 и runtime27 проверены. Исходные Mac
baseline/recovery сохранены побайтно. На момент подготовки real candidate результат ожидался; принят позже, см. PROMPT_V2.ru.md.
