# День24 — точные источники и цитаты, пороговый отказ (v14)

Протокол: verbatim-extractive-v14. Целевое окружение прежнее: MacM1/32GB/Python3.13.3, Ollama bge-m3 и qwen2.5:14b. Corpus/index/модели неизменны; stdlib и модули Дней21/23. Default settings: fixed, candidate20/final5/cosine0.50 inclusive, heuristic rewrite, ctx16384/output2500/temp0/timeout600s.

**День24 подтверждён по исходным требованиям на одном полном actual v14 diagnostic прогоне:**10/10 source-based ответов после ручной source review,53/53 exact quotes,2/2 правильных отказа. Все46 selected chunks воспроизводятся corpus Day21 fixed с теми же metadata/text/ID/lines. Модельный coverage остался7/10; false01/03/05 сохранены. Original summary.assignment_complete=false не менялся: ручная проверка ещё не была проведена во время evaluate. В reviewed manual_summary.assignment_complete=true после проверки.

Отчёт: reports/live/REVIEW_evaluate_v14.ru.md; original и reviewed JSON рядом. Это ручная оценка ассистента, не независимого человека. Строгий model-coverage режим не получил10/10. Подтверждение относится к указанному diagnostic отчёту; новая оценка произвольных вопросов требует нового review.

## Два режима проверки полноты

| coverage-policy | Публикация | Что означает automatic contract pass |
|---|---|---|
| strict (default, прежнее поведение) | Только после положительного model coverage | Answer+valid sources+exact quotes+positive model coverage; ручная проверка всё равно нужна |
| diagnostic (отдельный режим для задания) | Exact selected source passages после app identity/provenance validation; negative/failed coverage остаётся в trace | Только корректный контракт answer/sources/quotes. Качество/полнота ещё не зачтены |

Выбор режима явный: --coverage-policy diagnostic перед ask/evaluate. Никакие отрицательные judgments не меняются на positive. В diagnostic при false/invalid audit: coverage_supported=false, manual_review_required=true, reason=coverage_requires_review либо coverage_check_failed_review_required. Ответ и quotes состоят из того же исходного текста, проверенного приложением. Markdown report явно помечает такую оценку. All10 answers требуют manual review по заданию, даже если model verdict true.

Модель выбирает1–6 quote IDs из retrieved chunks; source/section/chunk_id/строки и exact quote разрешает приложение. Free synthesis/translation отсутствуют. Затем coverage выбирает bounded proof IDs из exact sentence/line units только выбранного ответа. В diagnostic false coverage не запускает повторную selection: этот кандидат предъявляется для ручной оценки; strict продолжает прежний bounded retry/refusal. Malformed coverage получает одну format retry, raw errors сохраняются. Неизвестные/free-form quote IDs и лишние генерируемые answer claims не допускаются в обоих режимах.

Below cosine0.50: deterministic не знаю + уточнение, пустые sources/quotes,0 structured calls в heuristic. Selector unknown при достаточном score также отказывает. HTTP/embedding faults остаются errors и не маскируются manual-review answer. Exact text identity не доказывает source truth, relevance или полноту; при high similarity может быть неполный/лишний source passage. Его нужно отклонить при manual review. Diagnostic сознательно не даёт такой гарантии автоматом.

## Отчёт и завершение

```bash
python day-24-citations-grounding/test_day24.py -v
python day-24-citations-grounding/main.py --coverage-policy diagnostic evaluate --output day-24-citations-grounding/reports/check/evaluate_v14.json
```

Fields: answer, sources(source+section+chunk_id/lines/cosine), quotes(exact text+quote_id+claim_id+source_id), claims, reason, clarification, validation и retrieval. Diagnostic evaluation показывает contract_includes_model_coverage=false, diagnostic_positive_questions, positive_flagged_for_manual_review, positive_coverage_pass (не исправляется) и assignment_complete=false. Этот false означает, что ручная оценка пока не заполнена. Source contract10/10 не равен quality10/10. Manual review выполняется по каждому actual answer/quote/source, reviewed копия сохраняет original results и добавляет итог.

positive_semantic_verifier_pass=0 ожидается: extractive identity проверяется кодом, paraphrase entailment verifier не используется. Исторический paraphrase доступен отдельно; diagnostic policy с ним не поддерживается. Model coverage может ошибаться в обоих режимах. Лишние RU/EN дубли, headings, длинный code и cut source fragments остаются возможными.

Подготовка:150 tests (116 Дня24+34 прошлых дней), Python3.12.14. Scripted10+2 и saved-context contract replay проходят с авторскими/сохранёнными judgments, это не live v14 quality. Ollama/Qwen на Mac здесь недоступны. Пользовательский actual v14.json получен, все10+2 проверены; итог подтверждён в reports/live/evaluate_v14_reviewed.json. Программный код не изменён после этого прогона. Применение: START_HERE.ru.md; объяснение policy: FIX_DIAGNOSTIC_POLICY.ru.md.

## Демонстрация в консоли

Для видео: `python day-24-citations-grounding/console_demo.py` — полный просмотр ваших проверенных evaluate_again/threshold_check с паузами Enter. Показывает ответы, source/section/chunk_id, все цитаты, повторные проверки файлов и связей, исходный модельный coverage7/10 и записанную ручную проверку10/10. Это просмотр сохранённого реального прогона, а не новая генерация. `--live` выполняет новый прогон с немедленным показом ответов; новые manual reviews не заполняются автоматически. Подробности и акценты для видео: CONSOLE_VIDEO.ru.md. Основные15 Python-файлов v14 неизменны; добавлены presentation module и19 tests.
