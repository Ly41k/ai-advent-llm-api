# v0.7.1 — новые RU/EN вопросы после парного smoke

Mac v070: 221 tests, all 52 Python digests and 6 reconstructed actual context/
message/schema digests matched; 2 pairs / 4 observations / 6 real Qwen calls,
без technical failures/retries. Single EN расширил residency до request state;
эта неточность сохранена отдельно от schema/citation validity. Human review pending.

Новый prespecified catalog: 20 questions, 10 topics, 5 bounded batches, first
batch 4 questions / 8 observations / max 10 serialized calls. New root metadata
не передаётся модели. Catalog kind/scope, full byte digest и case_count закреплены
в freeze; report различает regression smoke и новые вопросы. Custom --cases
по умолчанию выбирает его batch_core, старый default smoke сохраняется.

Production generation/baseline/pipeline/schema/retrieval/corpus/options прежние.
End-to-end, 3 paired repeats, независимый human review и Mac RAM/swap ещё впереди.
Команды первого пакета и ограничения: RESEARCH_MAC.ru.md.

Локальная affected regression: 116/116, Python 3.12.14, source SHA неизменны.
Native Mac v071 preflight ожидает 227 tests; новые Qwen ответы пока не получены.
