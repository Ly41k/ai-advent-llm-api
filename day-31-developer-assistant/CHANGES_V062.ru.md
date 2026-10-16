# v0.6.2 — endpoint headings до FTS candidate LIMIT

Изменения: rag/retrieval.py добавляет literal standalone endpoint extraction,
case-sensitive exact heading matches и ordering (match count DESC, BM25, chunk ID)
для FTS. Source allowlist/body filter выполняются до candidate limit; нет
расширения model context, cloud calls или file reads по endpoint. Ordinary BM25
и dense ranking прежние; Hybrid RRF получает изменённые FTS ranks.
Research conditions фиксируют fts_endpoint_policy. Source docs/index не меняются.

Пять новых tests + 104 affected local tests прошли. Полный Mac suite 185 tests
и новые реальные /api/ps ответы ещё pending. Mac v0.6.1 180/180 и unknown fix
приняты отдельно. Исходные отчёты не подменяются; новая версия = новый freeze.

Изменение не гарантирует semantic relevance: section title — lexical hint.
При нескольких подходящих sections BM25 и stable chunk IDs разрешают равенство;
при отсутствии exact heading ordering остаётся прежним. Cases не используются
для выбора source/score, ретривер не содержит special-case /api/ps/tooling.md.
Query/candidate/context limits и negative/no-evidence semantics сохранены.

Команды, budget и пять отчётов: [RESEARCH_MAC.ru.md](RESEARCH_MAC.ru.md).
