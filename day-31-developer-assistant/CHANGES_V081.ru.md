# v0.7.11 (v081) — синхронизация ожидаемой prompt version в тесте

Native v080: 251 tests run, 250 passed / 1 failed. Все 59 Python digests совпали
с архивом. Actual-project FTS/Git/owned-worker smoke прошёл без model calls.
Реальный результат Qwen v7 не получен: helper set -e остановился на preflight.
В чат передан один preflight report; прочих v080 отчётов нет.

Локально воспроизведён fail test_pipeline.GenerationTests.
test_documentation_prompt_localizes_without_rewriting_context_or_extra_dispatch:
строка 137 сравнивает metrics.prompt_version с project-answers-v6, а v080
production client возвращает project-answers-v7. Это мой пропуск обновления
конкретного теста при изменении общего language prompt в v080.
Native traceback не вложен; точный AssertionError установлен локальным запуском
тех же исходников. Raw Mac failure не исправлялся в PASS и сохранён побайтно
в reports/verified/mac-v080. Результат разбора — codex-preflight-review-v080.json.

Исправлен один literal expected version v6 → v7 в существующем тесте.
Остальные проверки этого теста прежние: RU/EN system script, source context,
schema language enum, one dispatch, exact message/context digests и call count.
Тест не отключён; validator не ослаблен. Package version 0.7.10 → 0.7.11.
Production generation.py и Baseline byte-identical v080; prompt project-answers-v7,
Baseline snapshot-single-v7, DOC schema status-claims-script-line-v3 прежние.
Model/options/lease/retrieval/corpus/paired protocol/application validators прежние.

Весь GenerationTests блок — 16 tests — passed на Linux/Python 3.12.14,
с isolated jsonschema 4.25.1, включая independent schema matrix. Model transport
синтетический; реальных Qwen calls здесь 0. Helper/CLI package checks прошли,
40 exact public inputs в бюджете без truncation, max 8182/8192. Native full 251
и real Mac v7 quality pending. Новых тестов не добавлено.

Новый helper run_v081_mac.sh использует уникальные v081 outputs и package check
0.7.11; cap 1, один RU production Documentation request, no index build/embeddings.
Это продолжение ещё не выполненного prompt experiment v080, не повтор inference.
Новый freeze обязателен из-за package/source digests; старые outputs не overwrite.
Ожидаем увидеть supported prohibition даже при allowed path, полностью русский
prose answer без исходного EN дубля. Schema/script PASS сам по себе недостаточен.

Этап 7 открыт. После clean target идут остальные known cases/оба режима,
independent held-out/human review, три paired repeats, end-to-end и native
cold/warm/RAM/swap. Когда 7 завершён, сообщить Юрию и согласовать начало 8.
Автоматически этап 8 не начинать. Архив v081 — версия этапа 7, app 0.7.11.
