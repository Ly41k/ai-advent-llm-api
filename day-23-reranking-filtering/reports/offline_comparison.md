# Day 23 — Mode comparison

Generated answers: False; embedding: offline-lexical-tfidf-hash-1024-v1
Settings: `{"candidate_k": 20, "final_k": 5, "min_similarity": 0.15, "strategy": "structural", "rewrite_method": "heuristic"}`

| Mode | Source hit | Source precision | MRR | Negative abstention | Empty positives | Mean chunks |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.7000 | 0.2000 | 0.4733 | 0.0000 | 0.0000 | 5.0000 |
| filter | 0.5000 | 0.1600 | 0.3533 | 0.0000 | 0.1000 | 3.5000 |
| rewrite | 0.8000 | 0.2200 | 0.6033 | 0.0000 | 0.0000 | 5.0000 |
| rewrite_filter | 0.6000 | 0.1783 | 0.4533 | 0.0000 | 0.1000 | 3.4167 |

- Offline lexical scores and threshold do NOT measure bge-m3/llama3.2 quality.
- Source precision/hit/MRR use labeled source documents, not passage-level semantic judgments.
- Labels may omit other valid sources. Expected-term coverage is not answer correctness.
- A threshold can discard correct evidence; inspect positive_empty_rate and the full context.
- Human review fields are intentionally unfilled. Improvements are not guaranteed.

See the JSON for query rewrites, candidate decisions, contexts, answers and review fields.
