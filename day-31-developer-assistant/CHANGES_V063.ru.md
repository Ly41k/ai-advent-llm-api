# v0.6.3 — Documentation instructions

- prompt_version project-answers-v2; RU system instructions локализованы,
  EN semantic guidance эквивалентна. Evidence по-прежнему на любом языке.
- Direct documented negative restrictions/lack of guarantees могут поддерживать
  отрицательный ответ. Сохранять conditions/exclusions, все нужные supported facts;
  не добавлять разрешение к безусловному запрету. Partial/unknown не запрещаются.
- Main instructions и ordering existing IDs, JSON/evidence/language validation,
  pinned Qwen/options, 8 capability calls, deadline, source verification, session
  ownership, no retry/cloud/restart прежние.
- Нет golden labels или /api/ps/untracked special-case в production instructions.
  Corpus/retrieval/evaluation cases неизменны. Mac calibration v0.6.2 сохранена.
- Два новых transport/budget tests; 78 affected local tests passed. Full 187
  native Mac tests и real semantic quality v0.6.3 pending. Synthetic tests не
  проверяют, понимает ли Qwen запрет; это проверяется новым bounded Mac run.
- Mac v0.6.2 retrieval и 185 tests прошли, RU quality case остаётся partial.
  Original five JSON не изменены; input digests доказывают присутствие нужной
  evidence. Exact cause of model abstention is not proven; prompt is a candidate.

Запуск, 6-case / max 8 generations и три отчёта: [RESEARCH_MAC.ru.md](RESEARCH_MAC.ru.md).
