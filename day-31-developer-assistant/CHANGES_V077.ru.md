# v0.7.7 — существующий script check в схеме генерации

Native v076: 242 tests, index verify и zero-model admission прошли.
Untracked RU Single дал корректный answered: нельзя читать содержимое untracked
даже с явно разрешённым путём. Затем RU Multi stopped: terminal model frame
отклонён с claim_language. 2/12 observations, 2 Qwen calls, 2200 input /
172 output tokens. Другие targeted modes не запускались. Проверены 56 Python
SHA и обе пары context/message/schema/budget digests. Нет replay или unknown
inference attempt; rejected Multi input budget 6874/8192, не overflow.
Отклонённый текст не retained: точная формулировка/язык неизвестны. Claims не
опубликованы. Все шесть исходных v076 reports сохранены побайтно.

Предыдущие уточнения prompt не устранили отказ по языку в обеих ролях.
v077 сохраняет system/user text v076 и добавляет pattern в claim.text schema,
которую уже отправляет в Ollama через format. Pattern выражает прежний check:
RU text содержит хотя бы одну букву диапазонов А–Я/а–я или Ё/ё; EN text их
не содержит. Простые anchored classes/groups, без lookaround/regex shorthands,
без зависимости от dot/newlines. То же ограничение входит в Single schema
через общий documentation schema builder. Base schema не мутирует между языками.

Это лишь символьный критерий, а не полноценное определение RU/EN языка:
например, наличие одной русской буквы не доказывает русский текст, а отсутствие
кириллицы не доказывает английский. Он не оценивает смысл, completeness,
истинность, поддержку источником или отсутствие выдуманных параметров.
Language/identifier/status/length/ID validators приложения побайтно сохранены.
Нет автоматического перевода, frame repair, partial upgrade, extra generation
или retry. minLength/maxLength остаются в schema и validator приложения.
Нельзя считать наличие pattern в запросе доказательством его исполнения backend.

DOC_SCHEMA_VERSION status-claims-language-v2; BASELINE_VERSION snapshot-single-v5
(новая schema contract revision; текст baseline prompt не изменён).
PROMPT_VERSION по-прежнему project-answers-v6. Main ID-only schema, source rules,
corpus/docs/retrieval, model OPTIONS, 8192 budget/reserves, paired-snapshot-v2,
lease/session и task limits прежние. Новый freeze обязателен; rebuild не нужен.

Добавлены четыре проверки: Unicode/newline parity pattern с прежним check;
независимый Draft202012 schema/application matrix для обоих режимов, длин,
status и script; фактическая отправка schema обоими clients без мутации base;
строгий отказ/no text leak/no replay, если backend проигнорировал constraint.
Fixtures синтетические. Локально полный MCP/jsonschema stack отсутствует;
independent schema matrix выполняется в native preflight. Ожидается 246 tests.
134 локальные проверки подтверждены: 133 прошли в исходном suite, один
тест имел устаревшее expected version v4 вместо v5. Исправлен только label
в тесте; targeted rerun прошёл. Исходный failed report сохранён без изменений,
новая aggregate verification содержит его SHA и единственный test-only diff.
Независимый jsonschema matrix остаётся native pending. Helper/budget checks passed;
40 public inputs помещаются без обрезки, максимум 8181/8192. Обе точные v076
messages/context/budget сохранены, только schema digests изменились.
Все отчёты — reports/verified.

Ollama принимает JSON Schema в format:
[официальная документация](https://docs.ollama.com/capabilities/structured-outputs).
Upstream converter обрабатывает anchored patterns, но поддерживает подмножество
regex/schema и может предупреждать о неподдержанной части:
[исходник llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/common/json-schema-to-grammar.cpp).
Это подтверждает выбранный механизм, но не заменяет измерение на установленной
Mac Ollama. При отклонённом/ошибочном ответе приложение не ослабляет проверки.

Поэтому первый native experiment ограничен одним known RU вопросом про untracked:
Single + Multi, до двух Qwen calls. Preflight/index verify/admission/plan/freeze
предшествуют генерации. EN untracked, unknown, serialized и остальные known cases
ещё pending под новой schema. Нельзя автоматически закрыть качество по одной паре.

Этап 7 открыт: затем полная revised-contract regression, независимый held-out/human,
три paired repeats, end-to-end и native cold/warm/RAM/swap. При завершении этапа 7
явно сообщить Юрию и согласовать время начала этапа 8. Не начинать 8 автоматически.
