# v0.7.5 — отказ без неподтверждённых имён и явное сравнение вариантов

Mac v074: 241 tests прошли. Индекс прежний — 44 документа / 405 чанков.
Пять пакетов завершены; последний stopped после отклонённого EN Single ответа:
`unsupported_identifier`. Всего 23 observations из 24, 29 Qwen calls,
26 195 input / 2 062 output tokens. EN Multi unknown не запускался.
56 Python digests и все 29 context/message/schema/budget digests проверены.
Вход отклонённого ответа был 5523/8192, не overflow. HTTP вернул terminal reply;
lease завершена, unknown inference attempts и generation replay — 0.
Отклонённый текст не retained: конкретный идентификатор/формулировка неизвестны.
Валидатор заблокировал публикацию; это не успешный unknown ответ.

Dense RU Multi и paraphrase EN Multi теперь answered с поддержанным текстом.
Все четыре untracked ответа запрещают чтение даже при explicitly allowed paths:
прежняя RU conditional permission отсутствует. Однако EN Multi всё ещё partial.
Explicit «одна Qwen, не копия на агента» есть у Single EN; остальные три ответа
про сериализацию пропускают эту часть. RU Single также повторяет общий тезис.
Это разбор Codex, не независимый human verdict. Этап 7 остаётся открыт.

Общие SOURCE_RULES для Single и Documentation уточнены: вопрос не evidence;
не повторять неподтверждённые имена/параметры даже в отказе. Общие сведения
не подтверждают конкретную сущность/значение. Если нужной поддержки нет,
вернуть unknown с пустыми claims. Для выбора вариантов отдельный claim должен
явно сравнить подтверждённый и отвергнутый варианты по источнику. Статус после
claims оценивает только scoped documentation question; supported negative
answer не требует partial. Правила общие, без case names/answers/rubric paths.

PROMPT_VERSION `project-answers-v5`, BASELINE_VERSION `snapshot-single-v3`.
Schema/validators не ослаблены; нет автоматической правки ответов/статуса,
дополнительной генерации или скрытого retry. Main assembly, retrieval, model
OPTIONS, budgets, source allowlist и corpus прежние. Новый freeze обязателен.
Новая версия — явный эксперимент с изменённым prompt; raw v074 failure сохранён.

Дополнительный unit test проверяет строгую границу: имя только из вопроса
нельзя включать даже в refusal claim в обоих режимах; unknown/empty допустим.
Это синтетическая проверка валидатора, не доказательство поведения Qwen.
Полные 40 public Doc/Single inputs v073 проверяются без обрезки evidence,
с прежним окном 8192 и резервами. 131 локальная affected проверка прошла; максимум 8176/8192.
Shell helper/CLI plan также проверены без model calls. Native ожидается 242 tests;
реальная semantic проверка v075 ещё не выполнена.

Mac helper сначала делает preflight/index verify/admission/plan/freeze, затем
только сериализацию, untracked и unknown RU/EN: 6 вопросов, 12 observations,
до 14 последовательных Qwen calls, 0 embeddings. Индекс не пересобирать.
Все 11 native отчётов v074 сохранены побайтно в reports/verified/mac-v074;
разбор — codex-complete-review-v074.json, overall_quality_status not_accepted.

После targeted проверки нужны остальные 16 известных вопросов под новым prompt,
независимый held-out/human review, три paired repeats, end-to-end и native
cold/warm/RAM/swap. Known regression не заменяет эти acceptance checks.
