# Полная проверка v11 — 2026-10-03

Результат:3/10 положительных опубликованы и подтверждены вручную (02/07/08),2/2 отрицательных отказа правильные. Задание НЕ закрыто. Это настоящий пользовательский Ollama-прогон на MacM1/32GB; ручная проверка ассистентом не является независимой человеческой оценкой.

Оригинал сохранён побайтно. В reviewed добавлены только manual_review, manual_summary и provenance: результаты модели, summary и automatic decisions не исправлялись.

| Вопрос | Опубликован полный ответ | Источники и цитаты | Диагноз |
|---|---|---|---|
| positive-01 | Нет | Пустые при отказе | Отказ. В обоих selections есть восстановление выбранной темы при старте и UUID/selected conversation_id для каждого LLM request. Auditor ошибочно утверждает, что механизм отсутствует. База SQLite не выбрана явно; пример диалога и неполный фрагмент лишние. |
| positive-02 | Да | Да, точные | Опубликован полный перечень planning → execution → validation → done и возврат на execution при failed validation. Все statements дословны. Заголовок и незавершённое When a dialogue is reopened... лишние, но основной ответ полный. |
| positive-03 | Нет | Пустые при отказе | Отказ при наличии diagram с preflight до generation и postflight после, explicit local/semantic проверки перед persistence. Auditor ошибочно требует отсутствующее объяснение места; нужная последовательность уже показана. |
| positive-04 | Нет | Пустые при отказе | Отказ. Таблица содержит approved nonempty plan перед execution и PASS перед done; список также содержит allowed_targets/guards. Первый auditor склеивает EN и RU куски через | в строку, которой в answer нет. Повторный auditor ошибочно считает таблицу недостаточным объяснением. |
| positive-05 | Нет | Пустые при отказе | Отказ. stdio_client → ClientSession.initialize → list_tools → вывод metadata объясняет discovery всего server tool set. Auditor требует отдельную discovery процедуру для ping/add, хотя механизм общий; add name не выбран явно. Первый mechanism excerpt дополнительно теряет backtick и склеивает строки. RU/EN дубли и ping example лишние. |
| positive-06 | Нет | Пустые при отказе | Отказ несмотря на явное get_github_repo в регистрации и шаге model requests get_github_repo(owner, repo) из Day17. Auditor ошибочно пишет, что название не указано. |
| positive-07 | Да | Да, точные | Опубликованный ответ правильно относит periodic polling/GitHub REST/SQLite snapshots к worker.py, чтение summaries — к agent. Основной ответ полный. RU/EN duplicate и незакрытая server.py docstring лишние и ухудшают подачу. |
| positive-08 | Да | Да, точные | Опубликованы search_repository → summarize_repository → save_report с правильными функциями. Есть direct intro и точный код. Ответ полный, но гораздо длиннее необходимого. |
| positive-09 | Нет | Пустые при отказе | Отказ. Три servers/registry routing, пятишаговый flow, сравнение disk report с original summary и success only verified=true присутствуют. Auditor склеивает раздельные фрагменты диаграммы и prose в excerpt, которого в ответе нет; validator правильно отвергает. До action/observation calls выполнение не доходит. |
| positive-10 | Нет | Пустые при отказе | Отказ. Selection содержит systemctl/journalctl, summary stdout after each run и свежую summary через agent/shared DB. В совокупности кандидат содержит действия и наблюдаемую повторную сводку. Auditor оба раза выбирает journalctl как observation. Local disjoint guard правильно блокирует эту ошибочную доказательную строку. |
| negative-01 | Правильный отказ | Пустые при отказе | Правильный отказ: finance revenue отсутствует. Релевантные по словам README chunks найдены (max cosine выше0.50), selector возвращает unknown, sources/quotes пусты; есть уточнение. |
| negative-02 | Правильный отказ | Пустые при отказе | Правильный отказ ниже0.50: нет выбранных sources, structured model_calls=[], attempts=0; русское не знаю и просьба уточнить. |

## Повторная сверка нюансов

- Проверено10 положительных вопросов; ответы получены только на3. Поэтому обязательные sources/quotes пока есть лишь в3/10 положительных ответов.
- Во всех3 опубликованных ответах source+section+chunk_id действительны, цитаты совпадают с source files, chunks/catalog и claim text. Основной смысл корректен.
- Положительные отказы не засчитаны как успешные ответы.
- Финансовый вопрос: выше порога, но факты отсутствуют; правильный insufficient_context. Орбита: below_threshold, ни одного structured вызова, правильное не знаю и уточнение.
- Ноль positive_semantic_verifier_pass ожидается при строгом extractive: здесь source identity, а не отдельный paraphrase entailment verifier. Это не причина7 отказов.
- Во всех model calls stop, нет признака truncation по done_reason; нельзя объяснять сбой нехваткой token budget.
- Подтверждены ложные coverage refusals, literal excerpt formatting failures и ошибочная команда как observable result.
- Качество подачи: лишние RU/EN copies, setup/heading и оборванные source fragments. Их точность не означает хорошую полноту/лаконичность.

## Исправление v12 и пределы проверки

Coverage model выбирает ID точных sentence/line units опубликованного кандидата; программа разрешает ID в буквальный текст. Нет свободного excerpt, который модель должна скопировать или склеить. По одному criterion на вызов; action units и shell commands исключаются из выбора observation. Отрицательное semantic решение не превращается в одобрение. Malformed proof decision получает одну bounded format retry на том же answer; затем обычный safe refusal. Prompt позволяет читать code/diagrams/tables и provenance, без expected answers/reference case facts.

Это устраняет конкретные контрактные причины, но улучшение качества Qwen нельзя утверждать по scripted tests. Нужен новый полный evaluate_v12.json и проверка10+2. Индекс/корпус/модели прежние.

## Измерения исходного v11

```json
{
  "questions": 12,
  "positive_questions": 10,
  "automatic_positive_pass": 3,
  "manual_complete_supported_answers": 3,
  "manual_pass_ids": [
    "positive-02",
    "positive-07",
    "positive-08"
  ],
  "unknown_positive_ids": [
    "positive-01",
    "positive-03",
    "positive-04",
    "positive-05",
    "positive-06",
    "positive-09",
    "positive-10"
  ],
  "negative_questions": 2,
  "correct_negative_refusals": 2,
  "published_quotes_verified": 16,
  "candidate_passages_verified": 87,
  "selected_chunks_verified": 46,
  "catalog_fragments_verified": 898,
  "model_calls": 43,
  "prompt_eval_count_range": [
    680,
    7252
  ],
  "done_reasons": [
    "stop"
  ],
  "protocols": [
    "verbatim-extractive-v11"
  ],
  "assignment_complete": false
}
```
