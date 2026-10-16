# Проверки foundation и MCP Git

## v0.4.0 — pipeline и Qwen tasks

99/99 checks здесь на Python 3.12.14: Foundation/Project RAG и 24 новых pipeline
checks. Новый tests/test_pipeline.py использует реальные FTS, files, owned
retrieval/verification workers; generation/model identity и его Git replies
явно synthetic. Полный MCP/runtime suite здесь не запускался из-за отсутствия
mcp/jsonschema; full suite содержит 128 tests. Реальный Qwen smoke ещё не запускался.
Report: reports/verified/stage5-v040-offline.json.

Проверены RU/EN routing и changed-files dependency, разграничение contexts,
closed model JSON/IDs, unknown evidence, invented identifiers, main omission,
model profile/cloud rejection, input budget до dispatch, no hidden retries,
uncertain lost response, пустой retrieval, changed sources/Git после Main,
partial deterministic fallback, Git-only без index/model, no-change chain,
exact-relative-path namespace, output trace и запрет повторного запуска request.
Первый test выявил пропуск русского порядка «файлы изменены»; parser исправлен,
последующий suite прошёл. Это не доказательство universal NL routing или
semantic correctness. Сложные несколько Git intentions дают explicit ambiguous.

Этап 4 v0.3.3 принят по новым Mac attachments: 104/104 tests, completed runtime
и 4/4 paraphrases во всех режимах, dense/hybrid MRR=1; 2/2 empty negatives
в каждом варианте. Исходные reports сохранены неизменными. v0.4.0 изменяет
project/docs: old retrieval results не объявляются новым live regression.
[Mac acceptance](PIPELINE_MAC.ru.md).

## v0.3.3 — закреплённые query policies

Присланные Mac reports v0.3.2 проверены: 102/102 tests, completed runtime,
трём ролям success, llm_calls=0; Python source digests совпали с v0.3.2.
Project corpus: 40 docs / 378 chunks. Calibration: FTS 10/10 / MRR .90,
dense vocabulary 10/10 / .95, dense raw 10/10 / .90, hybrid raw 10/10 / .95,
hybrid vocabulary 10/10 / .90. Все negative controls — 2/2 пустых.
session-en имеет dense rank=1 в обоих вариантах; scores .708935/.697645.

Исходный quality_acceptance=failed корректен для прежней гипотезы uniform raw:
dense raw ниже vocabulary по MRR. Файлы Mac не изменяются. v0.3.3 выбирает
vocabulary для dense и raw для hybrid. В новых paired reports uniform-raw
гипотеза записывается как raw_query_acceptance; quality_acceptance проверяет
явно указанную выбранную политику каждого режима. Требования hits, negative
controls и MRR не снижаются: выбранный MRR обязан быть не ниже альтернативного.
Selection только по calibration, не доказательство held-out качества.

Report selection-v033-from-mac-v032.json — ретроспективный расчёт по присланному
report, без новых model calls; не обозначается новым v0.3.3 live experiment.
75 offline checks прошли для v0.3.3; полный 104-test Mac runtime ещё не проверен.
Проектные документы, vectors, corpus и original/paraphrase fixtures не изменились.
Пересборка индекса после v0.3.2 не нужна.
[Проверки](QUERY_POLICY_SELECTION.ru.md).

## v0.3.2 — содержательные границы model-state документации

Mac report v0.3.1 сохранён как retrieval-paired-mac-v031-r2.json.
60 observations / 48 completed embedding calls: dense raw 9/10 / MRR .80,
vocabulary 9/10 / .85; hybrid raw 10/10 / .95, vocabulary 10/10 / .85;
FTS 10/10 / .90. Во всех пяти группах оба negative controls пусты.
Quality acceptance failed: это не объявляется успешно исправленным dense.
tooling.md ранжируется для session-en как 13 / cosine .493027 в vocabulary
и 6 / .528144 в raw. Raw source проходит .5, но не final K=5.

В v0.3.2 изменены docs/tooling.md и docs/architecture.md. Query algorithms,
thresholds/K, evaluation cases и acceptance conditions не менялись.
Новый corpus/index нельзя считать тем же экспериментальным условием, что v0.3.1.
Старые отчёты сохранены, stale old index блокируется до rebuild.
Реальное dense качество v0.3.2 требует нового Mac-отчёта.
[Команды и границы проверки](DENSE_DOCUMENT_FIX.ru.md).

## v0.3.1 — исходный semantic query и paired diagnostics

Новый offline report: reports/verified/query-policy-v031-offline.json.
73/73 Foundation/Project RAG tests прошли здесь на Python 3.12.14, включая
8 новых regression checks. MCP/jsonschema и Python 3.13 в текущем окружении
недоступны, поэтому новый полный MCP/runtime suite здесь не запускался.
Полный suite содержит 102 tests; прежний Mac report 94/94 относится к v0.3.0.
Real bge-m3 10/10, новый Mac/runtime и paraphrase quality пока не подтверждены.
Проектные документы и прежние evaluation cases сохранены байт-в-байт.
[Описание изменения и Mac-проверка](DENSE_QUERY_FIX.ru.md).

## Этап 4 / 0.3.0 — dispatcher и роли

94 tests на Linux/Python 3.13.16 и actual-project runtime smoke прошли.
Report: reports/verified/stage4-linux.json. Documentation/Verification используют
owned workers, Git — реальный MCP. Контексты sealed, роли и входы закрыты,
dependencies проверяются до выполнения. Успешная Verification предшествует
MERGE. Смоки и тесты этого этапа выполняют 0 model calls.

Проверены canary isolation, caller mutation, wrong-role/write/extra-history,
project/request/dependency ошибки, budget exhaustion, отказ на подменённую
цитату/изменённый source, successful insufficient_evidence, task timeout,
request deadline/cancel, output limit и cleanup process group/pipes.
В промежуточном worker overflow test обнаружен unclosed stdout transport;
cleanup исправлен дренированием pipes после завершения owned group.
Финальный полный прогон с ResourceWarning-as-error не содержит таких warnings.

Mac v0.2.3 accepted: 78 tests/FTS smoke, source digests совпали с выданной версией.
Новое comparison на прежнем index/cases: FTS 10/10 hit@5 / MRR .90,
dense 9/10 / .85, hybrid 10/10 / .85; по 2/2 пустых negative queries.
Reports: stage3-mac-v023.json и retrieval-mac-v023.json в reports/verified.
Исходный FTS выбран по этой ограниченной calibration, не как универсальный
лучший retrieval. Новый runtime на Mac ещё требует отдельной приёмки.
[Команды и ограничения](AGENTS_MAC.ru.md).

## Этап 3 / 0.2.3 — отбор содержательного контекста

На Linux/Python 3.13.16 прошли 78 tests и actual-project FTS smoke.
Новые regression tests проверяют heading-only exclusion перед top-k=1 во всех
трёх режимах, точные spans и отсутствие изменений CURRENT/index, no_evidence
для корпуса только из заголовков и сохранение code/schema candidates.
Reports: stage3-heading-filter-linux.json и fts-heading-filter-linux.json
в reports/verified. Новый фильтр использует прежний FTS-индекс без rebuild:
10/10 hit@5, MRR=0.90, 2/2 пустых отрицательных queries.

Из присланных пользователем Mac результатов подтверждены 73 tests v0.2.1,
doctor v0.2.2 (day30_off, disabled/unloaded, 0 процессов, порт 8000 свободен),
fresh Ollama epoch и bge-m3 build/verify: 40 docs / 376 chunks / dimension 1024,
47 embedding calls, 55.09 s build. Hybrid query: 1.89 s; два первых результата
были только заголовками, что стало причиной исправления retrieval policy.

Неизменённый Mac baseline reports/verified/retrieval-mac-v022-baseline.json
подтверждает FTS 10/10 hit@5 / MRR .90, dense 9/10 / .80, hybrid 10/10 / .85;
по 2/2 пустых отрицательных query в каждом режиме. Это 12-case calibration,
не Qwen answer evaluation. Политика v0.2.3 и её real dense/hybrid quality на
Mac проверяются отдельно. [Описание и команды](RETRIEVAL_FILTER.ru.md).

## Этап 3 / 0.2.0

72 tests на Linux/Python 3.13.16, actual-project FTS smoke: 40 docs/376 chunks,
точные spans/digests и три RU/EN query. Report: reports/verified/stage3-linux.json.
Dense vectors, embedding HTTP payloads и OS epoch witnesses явно синтетические;
это не реальные bge-m3/Qwen measurements или проверка fresh session на Mac.

Новые tests проверяют LF/CRLF/CR, initial blank lines, code fences, repeated spans,
явный JSON/YAML corpus, private sources/symlinks, additions/deletions, code-only
changes, state permissions, tampering, locks, old versions after failure,
project isolation, namespace-before-K, RRF, query injection и budgets.
Model session tests покрывают changed epoch, escaped/overlapping lease и
persisted uncertain checkpoint до dispatch. Silent replay запрещён.

12-case FTS calibration: 10/10 positive source hits@5, source MRR=0.90,
2/2 negative queries без candidates. Report: reports/verified/fts-calibration-linux.json.
Это retrieval source/keyword checks, не semantic answer evaluation и не final
held-out set. Evaluation cases не входят в corpus или embedding questions.
Source excerpts отмечены semantic_support_verified=false; score не подменяет
проверку смысла. Phase 4 добавит actual agent lifecycle и Qwen pipeline.

## Дополнение 0.1.2

Причина Mac doctor failure подтверждена выводом пользователя: print-disabled
выдаёт `disabled/enabled`, а предыдущий parser принимал только `true/false`.
Оба формата поддержаны с точным именем сервиса и полным значением. Неизвестный
формат, чужой label и неоднозначный duplicate остаются блокирующими.
40/40 tests на Linux/Python 3.13.16, включая 2 новых regression tests;
отчёт `reports/verified/stage12-launchctl-format-linux.json`.
Mac doctor 0.1.2 и 40-test suite на Mac пока не запускались.

## Дополнение 0.1.1

38/38 tests на Linux/Python 3.13.16; новый отчёт
`reports/verified/stage12-preflight-fix-linux.json` отдельно от предыдущего.
4 новых tests покрывают ps display с апострофами, отдельный executable/comm,
per-probe diagnostics и обязательную блокировку отсутствующего disabled override.
Из вывода пользователя подтверждены 34/34 tests и настоящий MCP branch для
0.1.0 на Mac. Причина неуспеха старого doctor ещё не подтверждена; 0.1.1
исправляет ошибочный shell parsing и добавляет проверяемую диагностику.
Описание: [PREFLIGHT_FIX.ru.md](PREFLIGHT_FIX.ru.md).

## Исторический baseline 0.1.0

Область: версия 0.1.0, этапы 1–2. Полное задание day31 не объявляется выполненным.

В Linux/Python 3.13.16 прошли **34/34** tests. MCP 1.30.0, jsonschema 4.26.0,
Pydantic 2.14.1. Отдельный venv и `ResourceWarning` как ошибка. Отчёт фиксирует
source digests и границы проверки; актуальный результат лежит в
`reports/verified/stage12-linux.json`.

| Проверка | Что фактически выполняется |
|---|---|
| Foundation | Immutable JSON snapshots, task/result validation, call/context budgets, role restrictions |
| Workspace | Real directories/repos, traversal, symlinks, root replacement и content allowlist |
| Subprocess | Real timeout и limit на читаемые stdout/stderr; own process cleanup |
| Day30 checks | Real occupied socket; simulated process/launchctl branches; не реальная остановка Mac |
| MCP | Реальный stdio subprocess, initialize, list_tools, call_tool и closed output validation |
| Git | Real temporary repos: branch switch/detached/unborn, staged/unstaged, rename/Unicode/newline, delete/untracked |
| Content security | Tracked `.env`, symlink mode, secret-like source patch и запрет path escape |
| External code | Helper fixture остаётся неисполненным при external diff, textconv, fsmonitor, clean/process filter configuration |
| MCP cleanup | Instrumentation real SDK process factory; проверяется returncode после context exit, transport не подменяется |
| CLI | `/help` с Python `-S` вне Git и explicit unavailable для documentation question |

Один промежуточный дополнительный test process cleanup зависел от `ps` и упал
из-за Linux process-table `lookup self` error. Он заменён наблюдением реального
process object SDK; final suite проходит. Production preflight при невозможности
прочитать process table fail closed, а не заявляет, что сервис выключен.

## Что ещё не проверено для текущего этапа

- Реальные Qwen ответы, поведение при потерянном inference ответе и память M1.
- Новый agent runtime v0.3.0 на Mac.
- Широкое качество RU/EN ответов вне retrieval calibration.
- Независимые LLM contexts и полный lifecycle модельных задач.
- Router/Chain/Fan-Out, single/multi comparison и golden quality set.

## Практические ограничения

Git observations не являются атомарным OS snapshot: проверяются HEAD, index,
status и numstat; при content — также digests выбранных worktree files. Изменение
наблюдаемых witnesses блокирует результат. Это не защита от всякой ABA race или
конкурентной подмены config/files тем же OS user.

Read-only ограничивает действия приложения в проекте. Test harness вправе
создавать fixture commits только в temporary repos. Схема output проверяет
формат и идентичность источника, а не семантику будущего LLM explanation.

Default metadata может содержать имена обычных исходников; sensitive names
withheld. Pattern checks дополнительно блокируют известные секреты в diff,
но полного secret scanner нет. Terminal JSON печатается с ASCII escaping,
чтобы filename/patch не смог выполнить управляющую terminal escape sequence.

Requirements lock сформирован и установлен на Linux/Python 3.13. Совместимость
этого набора с Mac подтверждается отдельной установкой и тестами, не текущим отчётом.
