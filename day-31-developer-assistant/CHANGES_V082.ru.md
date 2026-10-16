# v0.7.12 (v082) — длина claim.text ограничена внутри regex

v081 final: 251 tests passed, 59 Python source SHA совпали; индекс/admission
прошли, conditions valid after. Qwen terminal call completed, 1081 input /
1024 output tokens, output_validation_reason output_truncated. Call 112.15 s,
request 113.25 s. Unknown inference/retries/cloud fallbacks 0. Claims пусты;
приложение правильно отклонило незавершённый frame. Exact raw text не retained.
Семь initial файлов, final (1).json и terminal transcript сохранены побайтно
отдельно в reports/verified/mac-v081; interim running не подменён финальным.

Проверена точная reconstruction всех трёх input excerpts, context/messages/schema/
budget digests. В LLAMA_CPP_VERSION b11351 source converter KIND_STRING выбирает
pattern и возвращает до minLength/maxLength branch. Старый unbounded pattern
лексически принимает >600 characters, несмотря на соседний maxLength 600.
Это реальный дефект наших generation constraints. Нельзя установить, какая
часть конкретного v081 raw frame разрасталась: string/claims/whitespace.
Source pin/hash/ограничения — bounded-pattern-source-audit-v082.json.
Точный installed Mac compiled grammar не установлен.

Новый RU pattern: первая русская буква плюс 0–599 safe characters.
EN pattern: 1–600 safe characters с прежним исключением русских букв.
Pattern теперь сам ограничивает размер поля, даже если maxLength не комбинируется
backend с pattern. Максимум 600 characters прежний; первая русская буква —
новое более строгое условие формата. RU текст с ведущими spaces/emoji/API
отклоняется с claim_text_start; приложение не переставляет и не исправляет его.
API можно указать далее, например «Инструмент git_diff ...», при поддержке цитаты.
Exact source quotes/excerpts не ограничены этим prose contract.
Forbidden quote/backslash/control characters прежние. App/schema согласованы.

DOC_SCHEMA_VERSION status-claims-bounded-line-v4,
CLAIM_TEXT_POLICY_VERSION json-safe-bounded-line-v2,
BASELINE_VERSION snapshot-single-v8. Prompt project-answers-v7 прежний побайтно:
общие source/coverage/language/negative/status rules не менялись. Main, pipeline,
retrieval, model/options/lease, paired protocol и known case catalog прежние.
Никакого увеличения num_predict/context_window, truncation repair или retry.
Inputs идентичны v081: context/message digests, budget 6875/8192; output schema
SHA изменился. No real inference на Linux.

Один новый regression test: pattern самостоятельно принимает lengths 1/600 и
отклоняет 0/601/2000, одинаково для Single/Multi и independent JSON-schema/app;
RU start rejected и supported API после Russian prefix admitted. Existing
Unicode/language matrix обновлена под finite length/start contract.
143 affected/runtime/transport/worker/schema tests passed, Python 3.12.14,
isolated jsonschema 4.25.1. Native full 252 и real Qwen result pending.
40 public inputs без truncation укладываются, max 8182/8192. Helper fake-Python
sequencing passed: cap 1 RU Doc, no index build, stop before models при existing
output/failed admission/version. Corpus/docs byte-identical, индекс 44/405 прежний.

Ограничение размера каждого claim не гарантирует, что пять claims и JSON
уложатся в 1024 tokens, и не исключает лишний whitespace в backend grammar.
Script/start constraints не доказывают monolingual prose, entailment/полноту.
Mac experiment cap 1 установит фактический эффект. Failed results сохраняются;
структурный PASS не превращается автоматически в semantic PASS.

Этап 7 открыт: остальные known cases/оба режима, independent held-out/human
review, три paired repeats, end-to-end и native cold/warm/RAM/swap. Когда 7
завершён, сообщить Юрию и согласовать начало 8. Автоматически 8 не начинать.
