# v0.7.2 — контекст: исправление учёта, не увеличение окна

## Что остановило v0.7.1

Пакет B stopped на assistant-facts-ru/Multi. Single выполнил 1 real Qwen call,
ответ source-consistent: assistant text фиксирует сказанное, не verified user fact.
Multi получил context_budget_exceeded до /api/chat: llm_calls=0, dispatch_attempts=0,
unknown_inference_attempts=0. Было 2 reserved generation slots, не 2 выполненных
генерации. failed_requests=0 потому что application result partial с excerpts;
technical_failure_requests=1. Остальные вопросы B и пакеты C–E не запускались.
Оба conditions_valid_after=true, embedded freeze равен отдельному. Старый report
сохранён byte-for-byte, без исправления status или measurements.

Старая формула: len(внешнего messages JSON) + 256 + 1024 + 512.
Для этого input 6442+256+1024+512 = 8234, на 42 выше num_ctx=8192.
Но 127 bytes относятся к внешним полям/escaping транспортного JSON. Ollama
разбирает messages и рендерит их Content, а не сетевую JSON-обёртку.
Вложенный JSON в user.content остаётся буквальным текстом и учитывается полностью.

Новая формула: sum(UTF-8 bytes каждого content) + 256 + 1024 + 512.
Этот input: 6315+256+1024+512 = 8107 <= 8192. 256 для chat template и 512 safety
reserve прежние. Это консервативная оценка для поддерживаемого text-only Qwen
profile, не точный tokenizer и не actual token telemetry. Actual prompt_eval_count
и eval_count по-прежнему берутся отдельно из Ollama response.

Проверенные primary sources:
- https://github.com/ollama/ollama/blob/main/server/prompt.go — renderPrompt передаёт
  parsed messages в template/renderer, получает prompt string.
- https://ollama.com/library/qwen2.5:14b-instruct-q4_K_M/blobs/eb4402837c78 — template
  использует .Content и ChatML boundaries.
- https://huggingface.co/docs/transformers/v4.56.0/en/model_doc/qwen2 — byte-level BPE.

## Что меняется

Общий Qwen.generate (Single и Multi) использует один счётчик двух text-only сообщений
system/user. Он не принимает extra messages/media/history. Prompts, payload
messages, context/message/schema digests, модель/options и retrieval не менялись.
Без обрезки evidence, повышения окна/выходного лимита или снижения reserves.

input_bytes остаётся размером внешней JSON serialization для trace digest.
input_content_bytes — отдельная метрика текста. input_token_upper_bound_estimate
теперь content bytes +256. context_budget показывает policy, все reserves,
estimated_total и context_window. Эти значения записываются до admission gate,
поэтому overflow report больше не теряет полезную диагностику. Oversize остаётся
ошибкой до checkpoint/dispatch, без chat retry/restart/cloud fallback.
Новый generation_budget_policy закрепляется в research freeze.

Шесть новых checks: точный публичный input stopped Mac request, Unicode/escaping,
точная граница 8192 и +1, один счётчик Single/Multi, запрет extra shapes, отсутствие
текстов вопроса/источников в budget metadata. Synthetic response в fixture —
unknown, не воспроизведение модели и не semantic PASS.

## Исследование после остановки

v071 серия неполна; её нельзя объявить завершённым сравнением или склеить с v072
в единый experiment identity. Новый catalog research_budget_regression_v072.json
сохраняет все 20 questions/rubrics, но явно маркирует новую фазу known regression:
часть результатов уже просмотрена. Старый prespecified catalog byte-identical
и сохранён отдельно. Ошибки Main RU, untracked RU и Single EN request-state
не исправляются этой технической версией и остаются в исходных отчётах.
После успешного budget smoke соберём новый полный paired repeat в отдельных
bounded batches с новым freeze. Independent human review, новая unseen quality
приёмка, end-to-end, cold/warm и ресурсы Mac остаются открытыми. Stage7 открыт.

## Запуск на Mac

Из корня repo, в существующем Python 3.13 .venv. Сохрани stopped JSON. Старый
run_remaining.sh для v071 больше не запускай. Day30/Revik и другие Ollama clients
остаются выключенными. Модель/корпус/индекс прежние; restart и index rebuild не нужны.

```bash
unzip -o ~/Downloads/day31-stage7-v072.zip -d "$PWD"
python day-31-developer-assistant/main.py --version
python -W error::ResourceWarning day-31-developer-assistant/scripts/check_stage7.py --output /tmp/day31-stage7-preflight-mac-v072.json
```

Ожидается 0.7.2 / 233 tests, FTS/MCP smoke, без --live (0 real Qwen).
Если preflight failed — сначала разбираем его. Если прошёл:

```bash
python day-31-developer-assistant/scripts/compare_single_multi.py freeze --cases day-31-developer-assistant/evaluation/research_budget_regression_v072.json --output /tmp/day31-budget-freeze-mac-v072.json
python day-31-developer-assistant/scripts/compare_single_multi.py run --cases day-31-developer-assistant/evaluation/research_budget_regression_v072.json --freeze /tmp/day31-budget-freeze-mac-v072.json --case-id assistant-facts-ru --case-id assistant-facts-en --max-generation-calls 4 --output /tmp/day31-budget-regression-mac-v072.json
```

Это 2 вопросы / 4 observations / максимум 4 последовательных генерации,
0 embeddings. Нет автоматического повторения v071 запроса — это явно новый
regression run после установки исправления, с новым freeze и output.
Нужны три новых JSON: preflight, budget freeze и regression.
У RU Multi context_budget.estimated_total ожидается 8107 на прежних excerpts.
Любые semantic partial/unknown остаются измерениями, не исправляются до PASS.
Reports новые и вне repo, overwrite запрещён. Human scores pending.

## Локальная проверка

reports/verified/stage7-v072-offline.json: 122/122 checks passed, Python 3.12.14;
source SHA до/после неизменны;
FTS/owned workers настоящие, Qwen/Git responses synthetic. Native 233-test suite,
independent JSON-schema matrices и реальный Qwen regression проверяются на Mac.
