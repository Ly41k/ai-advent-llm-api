# День24 — итоговая проверка actual v14 (2026-10-04, Europe/Kiev)

**По исходным требованиям задания этот единый полный diagnostic прогон подтверждён:10/10 содержательных source-based ответов и2/2 правильных отказа.** Все источники и цитаты проверены против retrieved chunks/catalog и source files. Проверка выполнена ассистентом, не независимым человеком.

Model coverage остаётся7/10; отрицательные01/03/05 не исправлялись. После ручной source review эти ответы приняты по смыслу и полноте. Original summary.assignment_complete=false означает, что во время evaluate manual review ещё не было. В reviewed добавлена manual_summary.assignment_complete=true; original summary/results/checks/decisions сохранены неизменными.

Это подтверждение конкретного полного v14 diagnostic отчёта. Strict model coverage не получил10/10. Diagnostic не гарантирует полноту на произвольных будущих вопросах; новые runs требуют review. Ответы содержат избыточные/обрезанные source passages, но необходимые прямые фрагменты покрывают каждый заданный вопрос. Улучшение подачи остаётся отдельной работой.

| Вопрос | Sources/quotes | Смысл и полнота | Основание |
|---|---|---|---|
| positive-01 | Есть, точные | Подтверждено | Основной ответ полный: SQLite flowchart Start→open database→select/create topic→load completed messages→isolated LLM context→save exchange; UUID и only selected conversation_id объясняют изоляцию. Это конкретные операции и правила; model false coverage — ошибочное отклонение. Обрывок cooling module, тестовый диалог и status list лишние; подача требует чистки, но основной механизм не отсутствует. |
| positive-02 | Есть, точные | Подтверждено | planning → execution → validation → done; failed validation возвращает execution; pause не отдельная стадия. Смысл подтверждён диаграммой и prose. Лишний незавершённый When a dialogue is reopened... и заголовок ухудшают подачу. |
| positive-03 | Есть, точные | Подтверждено | Diagram preflight перед generation, semantic/local request guards; postflight проверяет generated response до persistence; every invariant/IDs указаны. Это отвечает на where around response. Слово versioned не нужно повторять для объяснения расположения проверок source invariants из Day14; номер версии/формат version вопрос не просит. Model negative сохранён, manually accepted. |
| positive-04 | Есть, точные | Подтверждено | Approved nonempty plan guard перед execution, PASS guard перед done, failed validation возвращает execution; allowed_targets/approval/semantic postflight объясняют запрет обхода. RU/EN duplicates избыточны, но основной смысл полный. |
| positive-05 | Есть, точные | Подтверждено | stdio_client→ClientSession→initialize→list_tools→вывод всех tool.name/description. Общая discovery операция применяется к зарегистрированным ping/add, отдельные invoke/definition каждого не нужны для вопроса о механизме discovery. В публичном ответе явно только definition ping, но нет ложного утверждения о signature add. Model audit дополнительно требует use/invoke — это не задано вопросом. Основной механизм полный; imports/ping example лишние. |
| positive-06 | Есть, точные | Подтверждено | get_github_repo назван в регистрации и model request из Day17; связь с MCP execution показана. Heading и перечень return fields лишние; основное название подтверждено. |
| positive-07 | Есть, точные | Подтверждено | Independent worker/worker.py выполняет periodic due jobs/GitHub REST/SQLite snapshots; agent читает persisted summaries. Роли сохранены. RU/EN duplicates и обрезанная docstring лишние. Основной process answer полный. |
| positive-08 | Есть, точные | Подтверждено | search_repository → summarize_repository → save_report и их обязанности прямо названы в intro и коде. Full code избыточен, но все три инструмента и порядок подтверждены. |
| positive-09 | Есть, точные | Подтверждено | github/analysis/storage registry routes to correct session, five calls, compare disk-read report with original summary, success only verified=true. JSONSchema относится к pending selection, не выдуманной гарантии сравнения. Fallback/correction не считаются model selected, ошибок роли/causal fusion нет. Windows/offline/test sections лишние. Все запрошенные части покрыты. |
| positive-10 | Есть, точные | Подтверждено | Service на VPS, shared DB/schedule, systemctl/journalctl checks, summaries stdout/journal after each run и persisted fresh summary через agent. Есть действия и наблюдаемое повторное output; это инструкция проверки, не заявление о проведённом нами VPS deployment. Не выводим periodicity из одной service liveness. Основной ответ полный, исходные passages partly English и verbose. |
| negative-01 | Пустые при отказе | Правильный отказ | Cosine выше0.50, но revenue в источниках отсутствует; selector unknown, insufficient_context, уточнение, empty evidence. Правильный отказ без фиктивных источников. |
| negative-02 | Пустые при отказе | Правильный отказ | Ниже0.50: no selected sources,0 structured calls,0 attempts, русское не знаю и уточнение. Правильный пороговый отказ. |

## Повтор каждого нюанса задания

| Требование | Результат этого отчёта |
|---|---|
| Ответ |10/10 published answers, механизм/операции подтверждены source text |
| Sources:source+section/chunk_id |10/10 positive answers; trusted metadata и bindings сверены |
| Цитаты из найденных chunks |10/10 positive answers; все опубликованные цитаты exact |
| Смысл ответа совпадает с цитатами |10/10 manually confirmed; каждый claim — тот же literal passage |
| Полнота ответа на исходный вопрос |10/10 main answers cover all explicitly asked parts; не требуются unasked tool invocations или literal adjective repetition |
| Weak relevance:не знаю+уточнение | negative02 below_threshold0.50,0 selected,0 structured calls |
| Нет нужных фактов при достаточном score | negative01 insufficient_context, уточнение, empty evidence |
| Повторная сверка всех требований | Пройден этот полный10+2 отчёт; результаты других версий не добавлялись |

## Что остаётся ограничением

Extractive answer на исходном языке, возможен code/table/diagram вместо свободного объяснения. Есть RU/EN duplicates, лишние tests/setup passages и cut source boundaries. Text identity не доказывает source truth или future relevance/completeness; model coverage ошибается. Требования этого задания подтверждены указанной manual review конкретного прогона, а не общей гарантией anti-hallucination.

## Измерения

```json
{
  "questions": 12,
  "positive_questions": 10,
  "automatic_source_contract_pass": 10,
  "model_coverage_positive_pass": 7,
  "model_flagged_for_manual_review": 3,
  "manual_complete_supported_answers": 10,
  "manual_pass_ids": [
    "positive-01",
    "positive-02",
    "positive-03",
    "positive-04",
    "positive-05",
    "positive-06",
    "positive-07",
    "positive-08",
    "positive-09",
    "positive-10"
  ],
  "negative_questions": 2,
  "correct_negative_refusals": 2,
  "published_quotes_verified": 53,
  "selected_passages_verified": 53,
  "selected_chunks_verified": 46,
  "catalog_fragments_verified": 898,
  "final_proof_units_verified": 260,
  "raw_proof_id_references_verified": 57,
  "model_calls": 25,
  "prompt_eval_count_range": [
    881,
    7252
  ],
  "done_reasons": [
    "stop"
  ],
  "protocols": [
    "verbatim-extractive-v14"
  ],
  "coverage_policies": [
    "diagnostic"
  ],
  "assignment_complete": true,
  "completion_scope": "This single supplied live v14 diagnostic run plus assistant manual source review; not a universal quality guarantee and not strict-model-coverage10/10."
}
```

Дополнительная canonical проверка: все 46 selected chunks воспроизводятся по Day21 fixed corpus с теми же chunk_id/source/section/text/line bounds. Max cosine отрицательного орбитального вопроса: 0.423014, ниже0.50.
