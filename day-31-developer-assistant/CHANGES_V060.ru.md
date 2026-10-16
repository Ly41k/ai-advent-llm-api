# v0.6.0 — Research 7A candidate

Accepted native v0.5.0: 154/154 tests, 43 Python hashes match, RU doc 22.11 s,
EN mixed 24.38 s, 3 real Qwen calls, no retries/fallback/unknown attempts.
Fresh retrieval v0.5.0: 60 observations, 48 embeddings, 0 answer calls, 10/10
in all five variants, 2/2 empty negatives; selected quality passed. Uniform raw
MRR acceptance remains failed and unchanged in the saved original report.

Added bublik_developer/research.py, scripts/research_project.py,
scripts/check_stage7.py, tests/test_research.py (18 methods),
evaluation/research_cases.json (20 new questions / 10 RU/EN pairs), instructions
and version 0.6.0. Production pipeline/generation/retrieval files are unchanged;
corpus docs are byte-identical to v0.5.0. The verified index remains current.

Frozen conditions include model/profile/prompt, code/cases digests, exact index
and Git HEAD/branch. Per-task generation slots persist before dispatch. Each row
retains actual result/trace; technical failure or drift stops the batch. Labels
and manual rubric remain outside production context and index. No automatic repair.

New 18 tests passed locally, with explicit synthetic pipeline/model fixtures.
Full Mac suite: 172. New Qwen core evaluation (max6calls), remaining questions,
human semantics, Single/Multi and resources are pending. Do not claim complete
Stage7 acceptance from retrieval hit@5 or from the original two smoke questions.
