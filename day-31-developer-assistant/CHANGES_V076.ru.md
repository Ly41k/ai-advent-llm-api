# v0.7.6 — явный язык каждого утверждения и обе альтернативы

v075 не прошла targeted quality. Native 242 tests passed, индекс 44/405 verified,
FTS/admission passed. Проверены 56 Python SHA и все семь inference
context/message/schema/budget digests. Serialized пакет завершён, untracked
остановился после первого RU Single ответа. Всего 5/12 observations,
7 Qwen calls, 6177 input / 487 output tokens. Следующие untracked modes и
весь unknown пакет не запускались. Это не полный Single/Multi comparison.

Причина отказа RU Single — claim_language: хотя бы один claim не прошёл
проверку русского текста. HTTP вернул terminal reply, lease завершена;
нет generation retry/unknown inference attempt. Input budget 7044/8192,
поэтому это не overflow. Отклонённый текст не retained; его точный язык,
содержание и формулировку восстановить нельзя. Claims не опубликованы.
Нельзя переносить корректные untracked ответы v074 на acceptance v075.

RU Single serialized теперь явно отвергает отдельные копии Qwen. Остальные
три ответа всё ещё пропускают эту часть; у EN Single исчезло явное сравнение,
которое было в v074. Codex review не нашёл неподтверждённых опубликованных
фактов, но полнота нестабильна. Independent human review pending.

SOURCE_RULES теперь задают язык каждого claim.text прямо: русский в RU prompt,
английский в EN prompt, даже если цитата на другом языке. Подтверждённые API
names сохраняются. При сравнении нужно назвать ОБА варианта: поддержанный
и отвергнутый по цитате; общий тезис не заменяет этот ответ. Правила разбиты
строками, одинаковы для Single и Documentation. Они не содержат тем, названий
контрольных случаев, эталонных ответов, rubric paths или eval labels.
RU Baseline prefix сокращён с сохранением scoped doc question, данных вместо
инструкций, запрета tools/history и обязательного Git ID selection. Это
позволяет оставить прежний 8192 budget/reserves без truncation evidence.

PROMPT_VERSION project-answers-v6; BASELINE_VERSION snapshot-single-v4.
Language/identifier/status/schema validators прежние и строгие. Нет output
translation, frame repair, partial upgrade, extra generation или auto retry.
Corpus/docs/retrieval, Main assembly, paired-snapshot-v2 order, session/lease,
model profile/OPTIONS и budgets прежние. Нужен новый freeze, rebuild не нужен.
Все семь raw native v075 reports сохранены побайтно в reports/verified/mac-v075;
review overall_quality_status not_accepted. Новый prompt — отдельный явный опыт,
не молчаливое исправление старого отчёта. Real v076 quality ещё pending.

Mac helper: preflight (ожидается 242 tests), index verify, zero-model admission,
plan/freeze, затем untracked RU/EN (cap 4), unknown RU/EN (cap 4), serialized
RU/EN (cap 6). Порядок между пакетами меняется; внутри пары задаётся прежней
frozen catalog position. 6 вопросов / 12 observations, до 14 последовательных
Qwen calls, 0 embeddings. При technical failure следующий пакет не стартует.
131 локальная affected проверка прошла. 40 public v073 inputs и все 7 v075
inputs с новыми prompts помещаются без truncation: максимум 8181/8192.
Helper/CLI plan checks passed; отчёты в reports/verified.
Синтетические ответы не доказывают улучшение реального Qwen.

Этап 7 открыт. После targeted нужны остальные известные вопросы под v6,
независимые held-out/human checks, три paired repeats, end-to-end и native
cold/warm/RAM/swap. Когда все критерии этапа 7 выполнены, явно сообщить Юрию
о завершении и согласовать время начала этапа 8. Не начинать этап 8 автоматически.
