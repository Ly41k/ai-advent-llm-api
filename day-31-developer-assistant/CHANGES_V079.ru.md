# v0.7.9 — закрытые границы строк claim.text

Native v078: 249 tests passed, index verify/admission passed. Один production
Documentation call завершён, frame отклонён с claim_language. Из двух claims
второй (claim_index 1) содержит 35 символов, 29 ASCII Latin, 0 русских букв и
0 других букв, ссылается на EN tooling e2. Ollama server version 0.40.3.
Это доказывает конкретное нарушение script contract; точная формулировка не
retained и не восстанавливается по длине. Claims не опубликованы. Нет retry
или unknown inference; 1083 input / 93 output tokens, budget 6874/8192.
Проверены 58 Python SHA и полные input/context/schema/budget digests.
Все семь raw v078 отчётов сохранены побайтно.

Наш старый RU pattern допускал кавычки/backslash. В Ollama v0.40.3 публичный
source pin LLAMA_CPP_VERSION — b11351. В его converter character class
передаётся в raw string grammar, а результат оборачивается double-quote tokens.
Построен синтетический контрпример: первый русский text lexically поглощает
кавычку, evidence_ids, разделитель объекта и начало второго English text.
JSON parser видит два claims, а raw converted string допускает такое содержимое
в одном text node. Это воспроизведённый дефект нашего pattern; не реконструкция
Mac frame и не доказательство точного installed runner/grammar path.
Source hashes/pins/ссылки — reports/verified/string-boundary-source-audit-v079.json.

v079 исключает из claim.text ASCII double quote, backslash, C0 controls, DEL,
NEL, U+2028 и U+2029. Это одна JSON-safe строка прозы. Schema pattern и validator
приложения одинаково требуют этот новый, более узкий контракт. Нарушение даёт
claim_text_encoding; текст не очищается/переводится и повторная генерация не
выполняется. Переформатирования уже полученного frame нет. Один неправильный
claim по-прежнему блокирует весь model frame.

Ограничение касается только сгенерированных claims. Evidence/цитаты/строки
источников, spans, raw/text digests, question и Git-факты не меняются. Exact
source quotes могут содержать любые прежние поддержанные символы и переносы.
API/code names можно обозначать backticks, если они подтверждены cited quote.
В claims теперь нельзя выдавать multiline code или literal ASCII quote/backslash
snippets. Их точный текст доступен в source excerpts; это явная граница prose
contract, а не гарантированная поддержка произвольного кода в claims.

Русский диапазон/EN exclusion прежние. Это всё ещё character check, не полноценный
language detector и не проверка смысла/entailment/completeness. Статусы/IDs,
unsupported identifier checks, length<=600 и final freshness прежние. Prompt
text не изменён: project-answers-v6. DOC_SCHEMA_VERSION status-claims-script-line-v3,
CLAIM_TEXT_POLICY_VERSION json-safe-line-v1, BASELINE_VERSION snapshot-single-v6.
Паттерн действует и в Single через общий schema builder. Main ID-only прежний.
Нет cloud fallback, hidden retry, restart/update Ollama или увеличения budgets.

Два новых теста: lexical two-claim counterexample old-pass/new-reject и отказ
обоих validators/schema для quotes/escapes/line-controls без repair. Existing
Unicode/schema matrix обновлена под более строгий формат. 139 affected tests
passed на Linux/Python 3.12.14, включая synthetic worker/transport/FTS fixtures.
Native ожидается 251 tests; полный MCP stack локально отсутствует.
40 public inputs в прежнем бюджете без truncation, max 8181/8192.
Backend/Qwen enforcement и semantic результат v079 ещё не измерены.

Helper сохраняет server version, новый production freeze и только один RU
Documentation request, cap 1. Это новый explicit contract experiment, не quiet
retry v078 и не paired Single/Multi benchmark. Corpus/docs/retrieval/model
OPTIONS/lease/order protocol прежние. Индекс 44/405 не пересобирать.
Если на Mac вернулся новый failure/неполный/смешанный ответ, он сохраняется;
никакого автоматического PASS поверх него.

Этап 7 открыт: после targeted fix нужны остальные known cases/оба режима,
независимый held-out/human review, три paired repeats, end-to-end и native
cold/warm/RAM/swap. При завершении 7 сообщить Юрию и согласовать начало 8;
этап 8 автоматически не начинать.

Дополнительно закрыт decoded JSON-schema end-anchor gap: '$' может совпасть
перед последним newline. Schema text добавляет not-forbidden-char predicate;
app line check прежний. Backend enforcement 'not' не предполагается: raw
GBNF использует fenced anchored pattern. Тесты охватывают trailing newline.
Изолированно установлен jsonschema 4.25.1, requirements repo не меняются.
После schema/test-only дополнения 11 affected/independent tests прошли, включая
три ранее не запущенных matrix tests. Текущая подтверждённая локальная coverage
142 tests; исходный PASS 139 и новая verification сохранены отдельно с SHA.
Native full 251 и реальный Mac result pending.
