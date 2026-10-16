# День 32 — минимальное AI-ревью Pull Request

**Состояние поставки: локальная реализация и offline-проверки. GitHub/bootstrap/live ещё не выполнены.**

Самостоятельное приложение для публичного `Ly41k/ai-advent-llm-api`:

PR metadata/files/patch → проверка границ → FTS5 по base README → один Groq POST → проверка JSON/координат/evidence → Markdown/JSON → необязательный bot-комментарий.

Python 3.12+ с SQLite FTS5. Только стандартная библиотека: устанавливать зависимости, запускать код PR или старые дни не требуется. Проверено в поставляющей среде на Python 3.12; Python 3.13 на Mac ещё не проверен.

## Запуск offline из корня репозитория

```bash
python -m unittest discover -s day-32-pr-review/tests -v
python day-32-pr-review/main.py offline \
  --fixture day-32-pr-review/tests/fixtures/review-case.json \
  --root day-32-pr-review/tests/fixtures/project \
  --output day-32-pr-review/reports/offline-demo
```

Offline-команда не создаёт сетевой transport, не читает ключи и не вызывает провайдера. В тестах реальные HTTP/socket entry points заблокированы. Фикстура полностью искусственная: SHA из повторяющихся цифр, PR #123, учебный дефект и заранее написанный ответ. Синтетические строки, похожие на присваивание пароля, используются только для проверки фильтра; реальных credentials нет.

`review.json`, `review.md`, `run-summary.json` — три результата. `mode=offline_mock`, `generation_calls=0`, `network_calls=0`, `mock_generation_outputs=1`. Настоящие здесь — parsing, FTS5, валидация и rendering. Модель и GitHub подменены. Это не live-приёмка.

Результаты текущей проверки: [OFFLINE_RESULTS.ru.md](OFFLINE_RESULTS.ru.md). Логи и машинный результат находятся в `verification/`; это зафиксированная offline-поставка, не каталог будущих run outputs.

## Границы реализации

| Область | Ограничение |
|---|---|
| Репозиторий/инициатор | Только публичный `Ly41k/ai-advent-llm-api`, автор PR, actor и triggering actor `Ly41k` |
| Ветка PR | Только `day32-demo` → `main`, из того же репозитория |
| Live workflow | Только ручной `workflow_dispatch` с `main`, `run_attempt=1` |
| Код исполнения | Checkout `base_sha` для PR-preflight; checkout workflow `github.sha` для ручного запуска |
| Согласованность | `source_revision == PR base_sha`; head и base сверяются после чтения, перед генерацией, после неё и перед публикацией |
| Файлы | До 20; API-пагинация 10/страница; текстовые patch до 32 KiB суммарно |
| Контекст кода | Только полные hunks API patch; head-файлы не checkout и не исполняются |
| RAG | До 32 разрешённых README / 1 MiB, SQLite FTS5/BM25 в памяти, до 3 hits |
| Документация | Root README RU/EN, README затронутых day-каталогов, ближайший README изменённого файла и Day 32 из base checkout |
| Модель | `openai/gpt-oss-120b`, размещённая у **Groq**; фиксированный endpoint Groq |
| Генерация | Один HTTP POST, до 2000 completion tokens с reasoning, 90-секундный socket timeout |
| Выход | До 5 findings; severity/path/side/range/title/reason/suggestion/evidence IDs |
| Workflow | До 9 минут runner time по timeout трёх jobs; ожидание Environment approval отдельно |
| Artifacts | Компактные отчёты, retention 7 дней |

Упрощение относительно первоначального плана: отдельный токенизатор не скачивается. Применён более строгий byte-BPE upper bound для фиксированного GPT-OSS: число UTF-8-байтов всего JSON request + 1024 служебных токена должно быть ≤4000. Это **верхняя оценка**, не фактический usage. Она учитывает schema и JSON overhead и допускает значительно меньше текста, чем точная токенизация. Уменьшаем контекст целыми hunks; пропуски отражаем в `omissions`. Фактические `prompt_tokens`/`completion_tokens` берём только из ответа. Превышение сервером лимита — ошибка, без повтора. Предположение о служебном резерве и модельный формат требуют проверки первым разрешённым live-run; до этого серверный token accounting не подтверждён.

Missing/binary/truncated/unsupported/слишком большой patch, неполные hunk counts и несовпадение API additions/deletions не объявляются проверенными. LEFT означает строки base; RIGHT — строки head. Для rename LEFT-ссылка ведёт на прежний путь. На одну находку нужен допустимый changed-line anchor и diff evidence в этом диапазоне. Документ сам по себе не доказывает дефект кода.

`findings=[]` допустим только после выполненного анализа. Все findings отклонены → `invalid_findings`, exit 2, без комментария. Часть отклонена/контекст урезан → `partial`. Неправильный JSON, wrong model, refusal, tool calls, missing usage и обрезанная генерация → error. Никакого repair call.

Фильтр секретов проверяет plain и декодированные JSON-строки. Это эвристика, а не гарантия отсутствия всех секретов. Diff/title/body недоверенные; title/body вообще не включаются в prompt. Источники из base доверены как документация, но не как инструкции модели. Нет `eval`, subprocess, install scripts, shell из PR или model tool execution. Проверка prompt injection offline доказывает границу данных/исполнения; устойчивость настоящей модели ещё не проверялась.

## Bootstrap — только после отдельного разрешения

1. Распаковать архив **в корень существующего репозитория**. Он содержит `day-32-pr-review/` и скрытый `.github/workflows/day32-pr-review.yml`. Прочие дни и корневые README не перезаписываются. Не распаковывать внутрь Day 31.
2. Проверить `git status --short --untracked-files=all`, выполнить offline-команды выше и изучить изменения. Использовать ветку **`day32-bootstrap`**, не `day32-demo`.
3. Проверить SHA закреплённых `actions/checkout`, `upload-artifact`, `download-artifact` по соответствующим upstream Actions. Здесь SHA фиксированы, но их актуальная доступность удалённо в рамках реализации не проверялась.
4. Отдельно согласовать создание bootstrap PR. Ключей и включённых `DAY32_*` variables на этом этапе нет. В bootstrap PR jobs намеренно skipped по имени ветки: приложения ещё нет в base. Это не успешный AI-run.
5. Просмотреть код и YAML, отдельно согласовать merge. Исполняемое приложение после этого появится в доверенном `main`.
6. Настроить Environment и доверенную demo-ветку, затем отдельно согласовать один live-тест ниже.

Планируемые команды после согласования (сейчас они не выполнялись):

```bash
git switch -c day32-bootstrap
git add day-32-pr-review .github/workflows/day32-pr-review.yml
git diff --cached --stat
git diff --cached --check
```

Commit/push/PR/merge здесь намеренно не автоматизированы.

## Настройка Secret и approval — без раскрытия ключа

В интерфейсе репозитория `Settings → Environments` создать **`day32-live`**.

1. Установить **Required reviewers**: конкретный доверенный reviewer. При единственном владельце требуется разрешённое self-review; иначе сам инициатор не сможет подтвердить job. Выбор фиксируется явно.
2. В **Deployment branches and tags** выбрать только ветку **`main`**. Не разрешать все ветки, `day32-demo` или pull-request merge refs.
3. Только после настройки защиты добавить Environment secret **`GROQ_API_KEY`**. Значение вставлять непосредственно в поле GitHub. Не отправлять его в чат, CLI arguments, файл, PR или screenshot.
4. **Не создавать repository-level secret с этим именем.** Environment restriction — часть границы доверия. GitHub может автоматически создать пустой Environment без reviewer protection; такое состояние не разрешает live.
5. Защитить `main` и `day32-demo` от push недоверенных участников либо подтвердить, что писать туда может только владелец. Совпадение `head.repo.full_name`, author/actor и имя ветки сами по себе этого не доказывают. При наличии других writers не ставить confirmation, пока доступ к ветке не ограничен и точный head не просмотрен.
6. Проверить текущие Groq Free Plan, доступность фиксированной модели, quota и стоимость. Эти сведения аккаунта в offline-поставке не проверены. Платный Groq-run здесь не разрешён.
7. В `Settings → Secrets and variables → Actions → Variables` установить четыре несекретные переменные со значением `true` **только после соответствующей проверки**: `DAY32_ENVIRONMENT_CONFIRMED`, `DAY32_BRANCH_TRUST_CONFIRMED`, `DAY32_FREE_PLAN_CONFIRMED`, `DAY32_LIVE_ENABLED`.

Если Required reviewers или restriction на main недоступны, ключ не добавлять и live не включать. Остановиться и согласовать более простой безопасный сценарий отдельно. Переменные — проверка настроек от случайного запуска; они не заменяют реальную защиту Environment.

## Один настоящий live-тест — после отдельного разрешения

1. От обновлённого `main` создать owner-controlled **`day32-demo`**. Добавить только `day-32-pr-review/demo/percentage.py` с двумя строками: `def percentage(value):` и `    return value / 0`. Не менять workflow/приложение/зависимости. Это намеренно дефектная **неисполняемая** демонстрация; demo PR затем можно закрыть без merge.
2. README base уже содержит контракт ниже. Создать учебный PR после разрешения. Автоматический PR-run должен выполнить preflight, FTS5 и artifacts с `generation_calls=0`. Проверить, что есть admitted changed lines и хотя бы один selected document. Не считать этот run AI-приёмкой.
3. Зафиксировать PR number, точный 40-символьный head SHA и source/base SHA. Не менять PR в ходе проверки. Если base != текущей ревизии приложения, обновить demo-ветку и заново выполнить preflight без генерации.
4. После согласования выбрать Actions → Day 32 PR Review → Run workflow → **main**. Указать PR number и head SHA, включить `confirm_one_call`. `publish_comment=false` по умолчанию; включать только при отдельно согласованном комментарии.
5. Review job должен ждать `day32-live` approval. Перед approval проверить ссылку на workflow из main, source SHA, diff, branch permissions, PR/head и предельный объём. Не подтверждать устаревший run. Если ожидания approval нет, отменить до выдачи ключа и разобраться с настройками.
6. После approval приложение заново получает PR/files и проверяет SHA. Ожидается ровно один Groq POST, настоящий retrieval, проверенные findings (желательно division-by-zero) либо результат для ручного анализа, три artifacts. Найденный дефект вручную сверить с кодом.
7. Проверить `run-summary.json`: `mode=live_groq`, `provider=groq`, `generation_calls=1`, настоящий request ID и usage. Billing status остаётся непроверенным до сверки с консолью. Сохранить run/artifact URL и краткий human verdict отдельно. Если комментарий разрешён — проверить его SHA и источник.
8. Выключить `DAY32_LIVE_ENABLED` после попытки. Не нажимать Re-run: attempts >1 заблокированы. Новый dispatch означает новое отдельное разрешение/approval, даже для того же head.

После timeout/cancel отправленный запрос может продолжать обрабатываться. `generation_calls=1` означает попытку отправки; неизвестные usage/cost остаются `null`, не нулём. Автоматических retries, fallback, параллельной второй модели нет. Если после ответа SHA изменился, отчёт ошибочный и не публикуется; повторной генерации нет.

### Контракт демонстрационного percentage helper

The percentage helper accepts a number and returns that number divided by 100. The percentage helper must never divide by zero. This contract exists solely for the small Day 32 demonstration PR; it is not a global project coding rule.

## Деньги, ограничения и дальнейшая работа

Groq — основной провайдер. `openai/gpt-oss-120b` здесь не расходует OpenAI API balance. OpenAI API остаётся ручным резервом около $5 **на дни 32–35 вместе**: адаптера, ключа и разрешённых OpenAI calls в этой поставке нет. Любой платный вызов отдельно согласуется. List-price snapshot в коде (2026-10-16: $0.15 input / $0.60 output за 1M tokens) используется только для расчётной стоимости, не подтверждает тариф аккаунта. До live тариф перепроверяется. `actual_billed_usd=null` до сверки биллинга; из предположения о Free Plan фактический ноль не выводится.

Текущие ограничения: небольшой byte-budget; только patch-контекст; README-only lexical RAG; secret detector эвристический; нет доказательства семантической корректности; GitHub Environment и action SHAs не проверены на реальном run; между финальной проверкой SHA и API комментария нет атомарной транзакции. Ссылки всегда закреплены на проанализированном SHA. SHA256 отчёта обнаруживает случайную порчу, но не является подписью/аутентификацией.

Публикация имеет отдельный job с `pull-requests: write`; модельный job имеет только read. Комментарий обновляется по маркеру только у `github-actions[bot]`; чужой комментарий с таким маркером не меняется. Более 300 комментариев или несколько совпадающих bot-комментариев — остановка публикации без нового вызова модели.

Основа переиспользования: Day 17 — HTTP-паттерны; Day 24 — strict JSON и evidence IDs; Day 27 — advisory report/usage; Day 31 — safe paths, secret patterns, immutable source spans, FTS literal queries. Полные runtime и imports старых дней не перенесены.

После bootstrap и настройки остаётся ориентировочно **45–90 минут активной работы** на один live-тест, ручную проверку, фиксацию evidence и демонстрацию. Ожидание merge/approval отдельно. Course Minimum ещё **не принят**: нужен реальный Actions + Groq run. Дальнейшие улучшения — [BACKLOG_AFTER_COURSE.ru.md](BACKLOG_AFTER_COURSE.ru.md).
