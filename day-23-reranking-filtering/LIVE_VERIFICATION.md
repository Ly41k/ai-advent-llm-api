# Day 23 — live verification

The user ran local Ollama evaluations on a Mac on September 30–October 1, 2026. Original uploaded JSON reports are preserved in `reports/live/`; model runs were not reproduced in the archive preparation environment. See `LIVE_VERIFICATION.ru.md` for the detailed requirement checklist and answer review.

The inspected profile uses bge-m3 embeddings, qwen2.5:7b generation, fixed chunks (500 indexer units, 75 overlap), candidate-K=20, final-K=5, heuristic rewriting, and inclusive raw cosine >=0.50. Supply these CLI flags explicitly; code defaults remain unchanged.

| Metric | baseline | filter | rewrite | rewrite_filter |
|---|---:|---:|---:|---:|
| Labeled document hits, 10 positive questions | 10/10 | 10/10 | 10/10 | 10/10 |
| Mean positive source precision | 28.0% | 30.3% | 30.0% | 37.3% |
| Positive empty contexts | 0/10 | 0/10 | 0/10 | 0/10 |
| Negative empty contexts | 0/2 | 1/2 | 0/2 | 1/2 |
| Mean context words, all 12 questions | 2007.8 | 1592.8 | 1851.8 | 1393.3 |

Compared with rewrite alone, rewrite_filter improves labeled source precision by 7.3 percentage points and reduces context by 24.8%, preserving document hits on these questions. Filter also restores preflight in the invariant answer, where baseline mentions only postflight. This supports an improvement in context selection; it does not establish universal improvement in answer correctness. Rewriting alone lowers MRR and expected-term coverage compared with baseline.

Remaining answer problems include fabricated VPS commands, failure to explain Day 20's read_report → verify_report workflow, and treating the example 60-minute job interval as universal. Correct document retrieval and expected-term coverage are not answer accuracy. The attached `assistant_review_050.json` records an assistant review of all 48 answers; it is not independent human labeling, and original human_review fields are untouched.

The original eight-question calibration selected 0.55. On fixed evaluation, that threshold produces one positive empty context in filter and two in rewrite_filter. The later 0.50 setting was selected after inspecting evaluation results, so the final run is exploratory, not fresh holdout evidence. Validate a frozen profile on new questions before claiming generalization. No full calibration sweep was uploaded; its console summary is described honestly in the Russian report.

Both out-of-corpus questions receive semantic refusals in every mode. Negative abstention rate measures empty retrieval context, not whether the LLM refuses. Filtering skips generation for the empty case; it retains one irrelevant chunk for the revenue question at 0.50, where Qwen still refuses correctly.

All 48 latest result traces were checked for candidate-K, final-K, inclusive threshold, decisions, exact assembled context, corpus boundary and paired pools. The unchanged implementation has 34 passing Day 21–23 tests, including SQLite, HTTP mock and CLI integration. Live model performance comes from the user's reports, not the mock tests or lexical offline demo.
