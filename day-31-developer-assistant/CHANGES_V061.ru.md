# v0.6.1 — корректный unknown и диагностика research

- Pipeline: validated Documentation unknown с найденными, прошедшими final freshness
  sources и без Git-запроса возвращает completed/unknown. Не добавляется
  documentation_not_answered. Stale sources, timeout, lost Git и прочие технические
  ошибки не скрываются abstention и сохраняют исходную классификацию.
- Mixed abstention сохраняет проверенный Git как partial и поясняет отсутствие
  документационного ответа. Chain сообщает отсутствие exact path association
  и проверку только первых четырёх разрешённых изменённых путей. Ambiguous Git
  сообщает о нескольких операциях и предлагает разделить запрос; tools/model не запускаются.
- Research останавливает следующие вопросы при execution_status=failed даже
  без typed ErrorCode. Structural checks отдельно проверяют execution status;
  summary показывает failed_requests. Completed означает завершение наблюдений,
  не доказательство качества ответа.
- inspect-retrieval повторяет production FTS worker с его лимитами 3/4096,
  сохраняет exact source excerpts в новом отчёте, проверяет freeze до/после,
  не вызывает metadata/chat/embedding/Git. Chain не инспектируется без live Git
  dependencies. Labels/rubrics не попадают в worker/model context.
- Восемь новых tests: fresh abstention RU/EN, mixed abstention, Chain limitations,
  incorrect failed status, stop-on-failed, completed unknown continuation,
  exact FTS inspection limits/no model, changed freeze/dependent Chain refusal.
  Existing stale-abstention and deadline tests сохранены.

47 Python files; полный native suite 180 tests. Prompts, retrieval, indexed corpus
и 20 evaluation cases byte-identical с v0.6.0. Corpus 40/380 не пересобирать;
новый freeze обязателен, так как версия/код поменялись.

Исходные v0.6.0 Mac reports сохранены без изменения. Audit не переименовывает
failed в PASS. Первопричина русского /api/ps abstention пока не установлена:
нужен actual FTS inspection, затем решение о следующем исправлении.
Все уже просмотренные cases считаются regression; universal 10/10 не заявляется.
Single/Multi и resource measurements пока не выполнены.

Запуск и новые файлы отчётов: [RESEARCH_MAC.ru.md](RESEARCH_MAC.ru.md).
