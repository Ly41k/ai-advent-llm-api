# v0.7.13 (v083) — общие правила полноты, цитат и отрицательных ответов

v082 завершила три known paired regression packets: 6 pairs / 12 observations /
14 Qwen calls, 12944 input / 734 output tokens, technical failures/unknown
inference/retries/cloud fallback 0. Все 59 Python SHA каждой freeze совпали,
14 контекстов/messages/schema/budget digest восстановлены. Native suite 252 passed.
Порядок по frozen catalog Gray parity/repeat preserved; same snapshot each pair.
19 raw v082 JSON (7 diagnostic/preflight + 12 paired packet files) byte-preserved.
Оригинальные failed/partial предыдущих версий тоже сохранены без PASS repair.

Unknown: 4/4 correct unknown, без выдуманных механизмов/значений/claims.
Serialized: все четыре ответа верно называют serial/shared lease и actual main,
но пропускают required explicit one-Qwen/no-copy-per-agent alternative. При этом
нужный тезис присутствует в e2. EN Multi добавляет concurrent Doc/Git clause,
ссылаясь только на e3: этот excerpt поддерживает serialization, но не concurrent
tasks. Сам тезис есть в других предоставленных quotes, неправильно выбран subset
citations. Main сохранил все предоставленные IDs, separate Doc/Main contexts
подтверждены; пропуск на этапе Doc/Baseline wording, не потеря при Main merge.

Untracked: RU Single, RU Multi и EN Single правильно запрещают чтение даже при
allowed paths. EN Multi выдаёт unknown несмотря на прямой запрет e1/e2.
RU Multi повторяет факт из EN/RU как два claims, второй awkward transliteration.
Технически все completed; semantic acceptance не повышена до PASS. Independent
human review pending. Источники Day31 проверены по local exact spans/lines/SHA;
legacy day18/day25 snapshot quotes доступны, current source bytes здесь отсутствуют.

Переписаны общие SOURCE_RULES_RU/EN в production Documentation и benchmark Single:
- один claim на нужный факт, не на источник; RU/EN дубли объединить;
- каждый тезис внутри claim подтверждается его evidence_ids (EN: include all needed quotes);
- явно отвергнуть неверный и подтвердить верный вариант сравнения, назвать оба;
- безусловный запрет даёт supported negative даже при условии из вопроса;
- сохранить ограничения, coverage всех supported doc-parts и исключить unrequested/invention;
- question не источник, generic facts не доказывают entity/value, unsupported names/parameters
  не повторяются даже в refusals; unknown/empty и supported/nonempty/status rules прежние.

Это generic instructions, без новых hardcoded facts, fixture IDs/paths или
expected answers. Нет post-generation добавления missing point, перевода,
semantic auto-upgrade, скрытого retry или исправления raw output.
PROMPT_VERSION project-answers-v8; BASELINE_VERSION snapshot-single-v9.
DOC schema status-claims-bounded-line-v4 и json-safe-bounded-line-v2 прежние;
1–600 chars, RU first letter, encoding/ID/script validators unchanged.
Production Main system prompt/ID-only context unchanged. Model/OPTIONS/lease,
pipeline/paired protocol/retrieval/corpus unchanged. Индекс 44/405 не rebuild.

Budget уменьшился: RU shared rules: 1194 bytes вместо 1200; EN: 908 вместо 933.
40 exact public evidence contexts without truncation max 8176/8192. Native
complete suite 252 и actual v083 semantics pending. Локально 37 affected prompt,
context budget, Baseline и весь GenerationTests прошли Python 3.12.14, isolated
jsonschema 4.25.1. Перед косметическим форматированием literals также37 passed;
первый report сохранён отдельно, current source SHA в финальном local report.
Synthetic transport/JSON-schema tests не доказывают Qwen answer quality.

run_v083_mac.sh делает preflight/admission/version и первый paired serialized
RU/EN packet, cap 6. continue_v083_mac.sh сверяет current source с успешным
native /tmp preflight перед dispatch; позволяет следующие selected packets,
не выполняет их автоматически и не повторяет full suite без изменения кода.
Shell syntax/real CLI plans/40 budget inputs/source guard tampering/fake-Python
failure sequencing проверены. Initial script stops до models при existing
output, failed preflight/admission/version/source/freeze; failed run no replay.
Embedding calls 0, model context/output limits прежние. Все model calls serial.

Новая версия — эксперимент generic source/coverage prompt, не гарантия исправления.
Сначала оцениваем полный serialized ответ и cited support, потом остальные known
cases/отказы/wording и held-out. Ошибки нового запуска сохранять отдельно.
Этап 7 открыт: full known catalog under final contract, independent held-out/human,
three paired repeats, end-to-end, controlled native cold/warm/RAM/swap. После
завершения 7 сообщить Юрию и согласовать время начала 8. Автоматически 8 не начинать.
