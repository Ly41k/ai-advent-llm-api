# v0.6.5 — independent case catalog selection for research

--cases controls plan/freeze/run/inspection/review-template. Raw case SHA pinned
in freeze and checked before/after answers; selected questions/labels must equal
the catalog, and a mismatched review rubric is refused. Production Pipeline sees
only questions and existing normal kwargs; no evaluation labels or file path.

Four targeted clarification questions added after known wording issues. They
are explicitly regression follow-ups, not independent held-out or passed labels.
Generation/pipeline/worker/retrieval/prompts/schema/options unchanged. Mac v0.6.4
190/190 and 8 Qwen calls validated; content nuance remains (EN partial and
conditional wording of untracked restriction). Original reports unchanged.

28 harness checks passed locally, including 4 new catalog-integrity tests.
Full 194-test Mac suite/new four native answers pending. Index unchanged, new
freeze with the same --cases required. 4 requests / max 6 Qwen calls, 0 embeddings.

Commands: [RESEARCH_MAC.ru.md](RESEARCH_MAC.ru.md). Stage7/Day31 acceptance,
independent semantic review, Single/Multi and resource measurements remain open.
