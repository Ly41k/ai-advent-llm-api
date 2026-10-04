# Полная проверка v13 — 2026-10-04 (Europe/Kiev)

Результат:8/10 positive опубликованы и подтверждены по источникам,2/2 negative правильные. Не завершено: positive01 и03 отказаны. Все original results/summary/decisions сохранены; reviewed добавляет только ручную оценку и provenance. Проверка ассистентом не является независимой человеческой оценкой.

| Вопрос | Содержательный ответ | Источники и цитаты | Разбор |
|---|---|---|---|
| positive-01 | Нет | Пустые при отказе | Отказ. Final selection содержит Startup/select topic/restore messages, SQLite flowchart с load completed messages, UUID и selected conversation_id only для LLM context. Первоначальный selection уже содержитSQLite flowchart и изоляцию. Auditor дважды ошибочно пишет, что операций нет. Actual отказ не засчитывается; нарезанный пример лишний. |
| positive-02 | Да | Да, literal | Полный перечень planning → execution → validation → done, failed validation возвращает execution. Все statements literal. Лишние pause heading и незавершённое When a dialogue is reopened не улучшают ответ. |
| positive-03 | Нет | Пустые при отказе | Отказ. Первый candidate содержит preflight-before-generation и local+semantic postflight-before-persistence, checks every invariant и violated IDs. Auditor признаёт проверки, но требует буквальное versioned invariants. После feedback selector возвращает unknown. Source text отвечает на where, однако actual ответа с quotes нет — не засчитываем. |
| positive-04 | Да | Да, literal | Таблица показывает approved nonempty plan перед execution и PASS перед done; allowed_targets/guards и explicit /task approve подтверждены. RU/EN duplicates лишние. Meaning correct; format citation после table row неудобен, literal source preserved. |
| positive-05 | Да | Да, literal | Опубликован после retry: stdio_client → ClientSession.initialize → list_tools → tool.name/description, definitions ping AND add. Механизм discovery всех server tools объяснён. Первый candidate отклонён моделью; итоговый полный и literal. |
| positive-06 | Да | Да, literal | get_github_repo указан в регистрации и model requests get_github_repo(owner, repo) из Day17. Название первого tool подтверждено. Heading и return fields избыточны. |
| positive-07 | Да | Да, literal | worker.py выполняет periodic polling/GitHub REST/SQLite persistence; agent читает summary через MCP. Роли сохранены. Core answer полный, RU/EN duplicates и cut server.py docstring лишние. |
| positive-08 | Да | Да, literal | search_repository → summarize_repository → save_report названы и описаны в intro и коде. Источники и смысл правильные. Большой полный код excess, основной ответ достаточен. |
| positive-09 | Да | Да, literal | Опубликован полный routing по github/analysis/storage, registry→правильная session, пять calls, comparison report read from disk vs original summary и success only verified=true. Observation теперь выбирает действительный outcome p3_7. Служебные action proofs содержат лишний routing, public answer core correct. Windows/testing/offline sections лишние. |
| positive-10 | Да | Да, literal | Опубликован полный source-based ответ: VPS service/shared DB schedule, systemctl/journalctl, summaries stdout/journal after each run, свежая persisted summary через agent. Observation теперь содержит after each run/summary output, а не только command. Лишние observation proof IDs Run a single worker process и общий intro не являются самостоятельным результатом; прямое after each run содержит нужное доказательство. Reason auditor ошибочно говорит agent collecting, но это служебная оценка, public answer правильно говорит independent worker. Код/цитаты literal. |
| negative-01 | Правильный отказ | Пустые при отказе | Правильный unknown при cosine выше0.50: corpus не содержит revenue, selector отказал, есть уточнение, sources/quotes пусты. |
| negative-02 | Правильный отказ | Пустые при отказе | Правильный below_threshold:0 selected,0 structured calls, русское не знаю и уточнение, источники не выдуманы. |

## Повторная сверка всех нюансов

- Проверены10 положительных вопросов. Sources/section/chunk_id и quotes есть во всех8 опубликованных ответах, но2/10 отказа не засчитываются.
- Все опубликованные цитаты проверены против реальных source files, retrieved chunks и catalog, metadata/lines/source/claim bindings. Ответы воспроизводят source text, основной смысл и полнота8/10 подтверждены.
- Negative01 above threshold, absent facts: правильный insufficient_context. Negative02 below0.50: правильное не знаю, уточнение,0 selected и0 structured model calls.
- Ноль semantic_verifier_pass ожидается: strict extractive использует text identity, не paraphrase semantic verifier.
- Proof IDs устранили копирование/склейку excerpt. 01 ошибочно отвергается как не содержащий operations/rules несмотря на source SQLite flowchart.03 отказывается из-за требования буквального versioned invariants.09 теперь правильно отвечает и показывает verified=true.
- Лишние RU/EN/code/heading и cut source fragments остаются проблемой подачи. Semantic coverage остаётся модельной оценкой, не абсолютным доказательством.
- Результаты v11 и v13 не объединяются в10/10. Новый протокол потребуется проверять отдельным полным прогоном.

## Измерения исходного v13

```json
{
  "questions": 12,
  "positive_questions": 10,
  "automatic_positive_pass": 8,
  "manual_complete_supported_answers": 8,
  "manual_pass_ids": [
    "positive-02",
    "positive-04",
    "positive-05",
    "positive-06",
    "positive-07",
    "positive-08",
    "positive-09",
    "positive-10"
  ],
  "unknown_positive_ids": [
    "positive-01",
    "positive-03"
  ],
  "negative_questions": 2,
  "correct_negative_refusals": 2,
  "published_quotes_verified": 41,
  "candidate_passages_verified": 65,
  "selected_chunks_verified": 46,
  "catalog_fragments_verified": 898,
  "model_calls": 30,
  "prompt_eval_count_range": [
    881,
    7252
  ],
  "done_reasons": [
    "stop"
  ],
  "protocols": [
    "verbatim-extractive-v13"
  ],
  "assignment_complete": false
}
```
