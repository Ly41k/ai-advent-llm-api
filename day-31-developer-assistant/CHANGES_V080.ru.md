# v0.7.10 (v080) — проза на языке ответа без исходного дубля

Native v079: 251 tests passed, 59 Python digests совпали с архивом/freeze.
Index/admission прошли, индекс прежний 44/405. Production request completed,
1 real Qwen call, 1083 input / 163 output tokens, request 34.70 s; no retry,
unknown inference или cloud fallback. Server Ollama 0.40.3.

Первый claim: «Содержимое untracked файлов не читается, даже если путь явно
разрешён.» Он сохраняет точный запрет и условие allowed path. Второй claim
выдаёт EN оригинал и RU перевод, дублирует policy и добавляет незапрошенные
правила secrets/private DB. Его сведения поддержаны e2, но смешанная проза
не выполняет требование русского ответа. Итоговый automated validator PASS
не повышен до semantic PASS. Независимый human review ещё pending.
Две опубликованные цитаты проверены по exact spans, line ranges и SHA.
Три входные выдержки восстановлены из v078; context digest точно совпал с
v079. Messages/schema/budget воспроизведены; Mac files повторно не читались.
Семь raw отчётов byte-preserved в reports/verified/mac-v079.

Наблюдение показывает исчезновение claim_language под новой schema при том
же контексте и message input. Оно не доказывает точную причину предыдущего
Mac rejection или стабильное enforcement всех backend/schema constraints.
Существующий RU check требует наличие русских букв, а не отсутствие английской
прозы. Поэтому смешанный claim проходит. Новый script/ratio запрет не добавлен:
подтверждённые API/code names могут быть латинскими; language quality оценивается
отдельно. Ни готовый текст, ни citations/claims не фильтруются и не переводятся
приложением; никаких repair/retry.

Изменена первая строка общих SOURCE_RULES_RU/EN: английскую/русскую прозу
источника перевести на язык ответа без оригинала/дубля, API имена сохранить.
Правила одинаковые для Single и Multi. RU строка выросла всего на 1 UTF-8 byte,
EN на 14 bytes. Остальные source/coverage/negative/status правила прежние.
PROMPT_VERSION project-answers-v7; BASELINE_VERSION snapshot-single-v7.
DOC_SCHEMA_VERSION status-claims-script-line-v3 и JSON-safe prose contract
прежние; application validators, Main, pipeline, retrieval, model/session,
OPTIONS, paired order protocol и case catalog не изменены.

21 affected prompt/budget/Baseline tests passed на Linux/Python 3.12.14,
включая independent JSON-schema matrix с isolated jsonschema 4.25.1.
40 точных прежних public inputs укладываются без truncation, max 8182/8192;
проблемный Documentation input теперь 6875/8192, evidence/context/schema прежние.
Helper проверен с fake Python: cap 1, one RU Doc, no index build; существующий
output/failed admission/failed server version останавливают до dispatch.
Native suite 251 tests и real Qwen quality v080 pending. Новых тестов не добавлено.

Версия приложения 0.7.10: v080 — номер архива, не начало этапа 8.
Helper сохраняет GET /api/version, новый production freeze и один RU call.
Это явный новый prompt experiment; не тихий повтор v079 и не paired benchmark.
Индекс не пересобирать; embeddings 0; Single не генерируется.
Если ответ останется смешанным/неполным/ошибочным, сохранить факт без PASS repair.
После successful clean claim продолжить known regressions/оба режима.

Этап 7 открыт: full known regression, independent held-out/human review, три
paired repeats, end-to-end и native cold/warm/RAM/swap. Когда 7 завершён,
сообщить Юрию и согласовать время начала 8; автоматически 8 не начинать.
