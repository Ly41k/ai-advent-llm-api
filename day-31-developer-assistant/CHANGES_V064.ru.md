# v0.6.4 — согласованная Documentation schema

Root oneOf с отдельными complete object variants: unknown/empty claims;
answered-or-partial/1–5 claims. Same pinned language/IDs, bounds and closed fields.
App validator не ослаблен: contradictory frames остаются rejected; нет retry
или автоматического исправления status. Точные fixed validation reason codes,
schema version/digest in metrics; prompt project-answers-v3 уточняет scoped status.
Research freeze фиксирует schema version, summary technical_failure_requests
показывает typed partial failures отдельно от execution_status=failed.

80 affected local tests passed; independent jsonschema status matrix не запускался
локально (dependency отсутствует), включён в 190-test Mac suite. Native Ollama
union enforcement и new real answers pending. Corpus/retrieval/options/fixtures
не менялись, index не пересобирать. Предыдущие Mac 187 tests passed, но quality
batch остановился на diff-policy-ru: broad schema/status validation rejection;
точный original field неизвестен, rejected raw frame не retained. Не заявляется,
что новая schema доказывает причину того кадра или исправляет semantic quality.

Original two uploaded v0.6.3 reports byte-preserved; standalone freeze недоставлен,
embedded frozen_conditions с совпавшим canonical digest проверены отдельно.
Запуск: [RESEARCH_MAC.ru.md](RESEARCH_MAC.ru.md); 6 cases / max 8 Qwen calls,
сначала оба diff-policy, 0 embeddings, без повторной calibration.
