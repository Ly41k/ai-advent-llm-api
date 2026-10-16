# v0.7.3 — русские документы Project RAG

Mac диагностика v072 воспроизвела все 20 исходных выборок без моделей.
Архитектурные чанки Main были на 48-м и 136-м местах русского запроса,
вне candidate_k=20. Контракт checked claims находился в чанке на 136-м месте;
раздел о лимите путей не входил в MATCH. Русский вопрос не имел нужных лексических
совпадений с английским описанием.

Добавлены architecture.ru.md, tooling.ru.md, memory.ru.md и api.ru.md в project/docs.
Переведены все темы четырёх документов: runtime/contexts, MCP, history/owner
isolation, API, language, epochs, lease, pipeline и ограничения. Описания разделены
по самостоятельным темам. Разделы явно указывают день/подсистему; поведение прежнее.

В default_sources разрешены ровно четыре новых именных документа, а не любые
*.ru.md. Root README и дни 1–30 не менялись. Английские project/docs побайтно
сохранены. Алгоритмы query expansion/BM25, endpoint priority, dense cosine и
hybrid RRF прежние. Golden paths не участвуют в production query/ranking.

Нужен новый hybrid index: на прежнем Mac repository ожидается 44 документа.
Меняются corpus fingerprint, selection digest, chunks и vectors. Старый index
должен дать INDEX_STALE; rebuild атомарно публикует новую версию, старую сохраняет.
Новый research freeze обязателен.

Model/options/prompts/schemas/context admission и Single/Multi implementations
побайтно прежние: 8192 window, output 1024, safety 512, temp 0, seed 31.
Нет автоматического исправления unknown/partial или нового inference retry.

Новые evaluation catalogs — known_regression. Вопросы и required_points сохранены;
к допустимым source paths добавлены RU counterparts. Старые catalogs/reports,
включая ошибки, сохранены. FTS calibration сохраняет 12 questions/keywords;
переводы допустимы как sources. Helper отдельно показывает source hit по старому
fixture. Эти source/keyword labels не передаются модели.

125 affected regression checks прошли на Linux/Python 3.12.14. Три новые checks
проверяют именной allowlist, symlink rejection, точные UTF-8 spans и stale detection.
Native complete 236 tests pending: MCP/jsonschema отсутствуют в локальном runtime.
Synthetic model/Git fixtures не являются реальными ответами Qwen.

На fixture из восьми настоящих project docs и тестового README проходят шесть
target RU/EN source/keyword hits, все 40 возможных Single/Doc inputs и 12 FTS
calibration checks. Transport/lease при проверке helper запрещены mock exceptions.
Это не полный Mac corpus; все checks повторяются нативно до Qwen.

Native/semantic v073 ещё не измерены. В v072 сохранены два неверных Main RU,
три пропущенных documentation answers, три поддержанных текста с partial и четыре
замечания к полноте. RU docs улучшают вход поиска; правильность формулировок
проверяет новый bounded regression, а не сам факт перевода.
Этап 7 открыт; 10/10, held-out, end-to-end и преимущество Multi не заявляются.

Runner по-прежнему чередует порядок по pair index. В этих двухвопросных пакетах
RU Single-first / EN Multi-first: это ограничение. Перед окончательными тремя
repeats нужны правильный counterbalance и новый freeze. Cold/warm и RAM/swap
этот helper не измеряет.
