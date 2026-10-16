# v0.7.4 — явная полнота и корректный counterbalance

v073 завершил полную 20-question серию. Source/model/JSON checks прошли;
новые вопросы не дают самостоятельной semantic acceptance. В двух Multi ответах
есть поддержанный полный текст с `partial`, а четыре ответа про Qwen не называют
явно отсутствие копии на каждого агента, хотя эта выдержка была в контексте.
Ранее наблюдавшийся untracked conditional-permission defect ещё не был проверен
на новом двуязычном corpus.

Добавлены общие SOURCE_RULES для Documentation и Single. Правила требуют явно
ответить на каждую запрошенную часть; в сравнении вариантов назвать подтверждённый
и отвергнуть другой, когда это поддержано цитатой. Status оценивает только scoped
documentation question после составления claims. Отрицательный ответ, язык цитат,
Git и незапрошенные детали не служат причиной partial. Unsupported part сохраняет
право на partial; отсутствие поддержки — unknown. Условия/запреты и запрет выдумок
остаются. В prompts нет case IDs, rubric paths/answers или списка целевых тем.

PROMPT_VERSION project-answers-v4, BASELINE_VERSION snapshot-single-v2.
Schema/validators/output fields прежние. Нет автоматического перевода partial
в answered, frame repair, extra generation call или retry. Main assembly prompt
и ID-only contract прежние. Модель, OPTIONS, corpus, vectors, retrieval и admission
algorithm прежние. Из-за нового prompt требуется полный последующий regression;
в этом запуске сначала 12 targeted/control questions.

Новый paired-snapshot-v2 protocol задаёт порядок по frozen catalog position,
Gray parity (S/M/M/S) и repeat inversion. Разбиение на batches не сбрасывает его.
Повторные even-sized datasets больше не сохраняют один порядок для каждого case.
Каждый report записывает catalog_position и order; CLI plan показывает весь schedule.
Это детерминированный баланс, не рандомизация. Для произвольного языка/каталога
распределение надо проверить отдельно; три repeats дают 2:1 на один case.

Новый known catalog содержит прежние 20 вопросов и два untracked controls из
исторического clarification catalog. Labels остаются вне inference/index.
Старые catalogs/reports, raw-query acceptance failure и partial labels сохранены.
Изменение prompt/order нельзя считать независимым held-out экспериментом.

130 affected tests прошли на Linux/Python 3.12.14, включая shared-rule parity,
40 точных public Doc/Single inputs v073 в бюджете без обрезки (max 8147/8192),
сохранение валидного partial без repair/retry, language-group order balance и
реальный runner с одним selected case на catalog position 2 в трёх repeats.
Model/Git replies в этих runner tests синтетические; FTS/owned processes реальные.
Native complete 241 tests и Qwen semantic results pending; локально MCP/jsonschema
dependencies отсутствуют.

Исторический тест budget 8234→8107 сохранён с отдельным immutable historical
system text, поскольку текущий prompt изменён. Он проверяет прежний transport
accounting defect и не выдаёт v3 prompt за текущую реальную генерацию.

Индекс 44/405 остаётся тем же: восемь project/docs побайтно неизменны.
Rebuild/embedding calibration повторять не надо. Новый freeze обязателен.
Этап 7 и независимые semantic/resource/end-to-end acceptance остаются открытыми.
