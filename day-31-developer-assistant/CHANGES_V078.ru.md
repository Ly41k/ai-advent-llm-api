# v0.7.8 — диагностика повторяемого claim_language, один Documentation вызов

Native v077: 246 tests, index verify и zero-model admission passed.
RU Single untracked дал корректный answered. RU Multi снова получил terminal
ответ, отклонённый с claim_language. 2 Qwen calls, 2200 input / 172 output tokens,
0 replay/unknown inference attempts. Input Multi 6874/8192, не overflow.
Проверены 57 Python SHA и обе context/message/schema/budget записи. Runtime
requested schema изменилась в v077, но требуемого результата не получила.
Совпадение token counts/message digests с v076 не доказывает тождество rejected
frame или конкретную backend причину. Rejected text не retained; claims не
публиковались. Все шесть raw native v077 reports сохранены побайтно.

v078 — диагностическая версия. System/user messages, schema patterns/version,
model/OPTIONS, corpus/docs/FTS/vector index и source selection прежние.
PROMPT_VERSION project-answers-v6, DOC_SCHEMA_VERSION status-claims-language-v2,
BASELINE_VERSION snapshot-single-v5 сохранены. При claim_language сохраняется
closed output_validation_details формата claim-script-counts-v1:

- expected_language, номер первого проблемного claim (0-based), число claims;
- число символов, русских букв из прежнего диапазона, ASCII Latin и других букв;
- только проверенные evidence IDs e1–e3.

Ни claim text, ни имена/параметры из него, ни question/quote/history не входят
в эту диагностику. Контроль script, schema/status/IDs/length и unsupported
identifier остаётся тем же; только к ошибке добавляются безопасные счётчики.
Parent проверяет closed diagnostic keys, типы, пределы, соответствие language
failure и ограниченные evidence IDs. Нельзя подмешать свободный текст или
некорректные числовые поля через owned worker metrics.
Нет перевода/repair/частичного исправления, auto retry, extra LLM call,
cloud fallback, обновления/restart Ollama или ослабления проверки публикации.

Три unit tests проверяют оба clients и оба языка: first offending claim counts,
no text leakage/replay, отказ от forged/unbounded diagnostic objects и
передачу counts-only error через настоящий execute handler с синтетическим
transport/workspace/session. 137 affected tests passed на Python 3.12.14;
native полный MCP/jsonschema stack здесь отсутствует. Native ожидается 249 tests.
40 сохранённых public input budgets проходят без обрезки, max 8181/8192.
Unit tests не измеряют текущую Mac Ollama или semantic качество.

Helper также сохраняет версию действующего Ollama server через GET /api/version:
[официальный API](https://github.com/ollama/ollama/blob/main/docs/api.md).
Это read-only metadata, без generation/embedding. Ответ ограничен version string;
ошибка/невалидный ответ останавливает helper до freeze/generation.
Версия сервера сама по себе не доказывает enforcement pattern.

Рабочие гипотезы пока не установлены: неподдержанный pattern/backend conversion
либо особенности обработки нескольких claim строк. Upstream converter применяет
pattern в string grammar, с ограниченным regex subset; наш отрицательный class
допускает кавычки/escape characters. Возможное пересечение JSON string boundaries
следует проверить по offending claim index/count и конкретной server version,
а не объявлять подтверждённой причиной без этих данных.
[Исходник converter](https://github.com/ggml-org/llama.cpp/blob/master/common/json-schema-to-grammar.cpp).
До получения диагностического отчёта prompt/schema не переписываются вновь.

Новый experiment использует существующий production multi-context research
runner и тот же known case/catalog v077. Новый production freeze, один RU запрос
про untracked, cap 1. Это не paired Single/Multi comparison и не retry старого
report. Single, уже давший правильный ответ, здесь не генерируется. Только
Documentation; при отказе Main не получает непроверенных claims. Новый report
может снова остановиться, но сохранит необходимые non-text details.
Строгий known/unknown call accounting и uncertain recovery прежние.

Индекс 44/405 не пересобирать. Этап 7 открыт: полная revised-contract regression,
held-out/human, три paired repeats, end-to-end и native cold/warm/RAM/swap pending.
Когда этап 7 завершён, явно сообщить Юрию и согласовать время начала этапа 8.
Не начинать 8 автоматически.
