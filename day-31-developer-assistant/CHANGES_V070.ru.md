# v0.7.0 — одинаковый снимок для Single/Multi

Добавлены paired_research.py, baseline.py, baseline_worker.py и
scripts/compare_single_multi.py; 27 контрактных/failure/fairness checks.
Multi использует production pipeline без правок. Single за одну модельную задачу
видит тот же полный evidence/Git набор, общий вопрос и закрытый Git catalog.
Generation/InferenceTasks/model_worker получили расширяемые hooks с прежними
production defaults; production prompts/schema/options остаются точными.

Одна общая FTS/MCP acquisition на пару, одинаковый snapshot digest, отдельные
freshness/Git проверки после каждого режима; одинаковые лимиты 8/300 s. Общая
подготовка явно отделена от физических повторных операций. Порядок чередуется,
все реальные generation slots резервируются до запуска и не возвращаются.
Technical failure/unknown останавливают очередь, без replay/restart/cloud.

v0.6.5 Mac: 194 tests, 4 requests / 6 real calls, technical completion.
RU untracked дал ошибочную условную трактовку allowed paths; retained semantic
failure, не «10/10». EN untracked supported rule, self-reported partial; RU/EN
явные /api/ps ответы поддержаны. Три исходных Mac отчёта сохранены byte-for-byte.

Первый run: два известных regression вопроса, максимум 6 последовательных calls.
Ни independent held-out, ни end-to-end, ни cold/warm/RAM acceptance пока не закрыты.
Подробности и команды: RESEARCH_MAC.ru.md.

Итоговая локальная регрессия: 110/110, Python 3.12.14; source SHA до/после совпали.
Полный Mac preflight ожидает 221 tests; native Qwen smoke ещё не запускался.
Первый failed локальный report сохранён отдельно, не переписан в PASS.
