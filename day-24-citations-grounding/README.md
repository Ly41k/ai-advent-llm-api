**English** | [Русский](README.ru.md) | [Project overview](../README.md)

# Day 24 — citations, sources, and grounded answers

Day 24 reuses the Day 21 index and Day 23 retrieval. The current protocol is `verbatim-extractive-v14`: the model selects passages from retrieved chunks; the application builds the answer, sources, and exact quotations. Insufficient context produces “I don't know” and a clarification request.

Answers preserve the original language of their passages and may include code, tables, or diagrams. The default workflow extracts source text; it does not freely explain or translate it.

## Recorded assignment result

The repository includes a complete live diagnostic run on a Mac M1 with 32 GB RAM, Python 3.13.3, `bge-m3`, and `qwen2.5:14b`. The 14B model performed both quote selection and coverage auditing.

| Requirement | Recorded v14 result |
|---|---|
| Evaluate 10 questions | 10 substantive answers |
| Sources: `source` + `section` / `chunk_id` | Present in all 10 answers |
| Quotations from retrieved chunks | Present in every answer; 53/53 quotations are exact |
| Meaning and completeness relative to the question | 10/10 confirmed by subsequent assistant source review |
| Automatic model coverage assessment | 7/10; negative judgments for 01, 03, and 05 remain unchanged |
| Abstention and clarification | 2/2 negative controls; a separate threshold-0.99 refusal demonstration |

Evidence: [question-by-question review, in Russian](reports/live/REVIEW_evaluate_v14.ru.md), [original JSON](reports/live/evaluate_v14_original.json), and [reviewed JSON](reports/live/evaluate_v14_reviewed.json). The review also checked all 46 selected chunks against the canonical Day 21 corpus.

This describes **one run** and assistant review, not independent human review or an automatic 10/10 quality score. The original `summary.assignment_complete=false` records pending review. The reviewed copy adds `manual_summary.assignment_complete=true` while preserving the original judgments and decisions. A repeat console run is available as [original](reports/console/evaluate_again_original.json) and [reviewed](reports/console/evaluate_again_reviewed.json).

## How sources and quotations are enforced

1. `rewrite_filter` retrieval gets candidates from the shared knowledge base. The threshold is **inclusive** and applied before `final-k`.
2. The application builds a passage catalog from retrieved chunks. The model selects known `quote_id` values rather than generating quote text.
3. The application validates IDs, literal text, and retrieved-chunk membership. It takes source paths and sections from index metadata and computes quotation line bounds. Each published claim equals its own quotation. The console demonstration additionally checks quotations against current local files.
4. A model auditor assesses whether the selected passages cover the question using `proof_ids`. Its judgments, including negative results and failures, are retained.
5. The selected coverage policy determines whether the answer can be published or must be replaced with a refusal.

| Result field | Contents |
|---|---|
| `status`, `answer` | Substantive answer or refusal |
| `sources` | `source`, `section`, `chunk_id`, line bounds, cosine, and source ID |
| `quotes` | Exact text, `quote_id`, claim/source binding, and line bounds |
| `claims` | Claims with their quotations |
| `clarification`, `reason` | Clarification request and refusal reason |
| `validation` | Source, quote, and coverage checks; policy; raw model responses |
| `retrieval` | Search parameters, candidates, and selected chunks |

Literal identity establishes text provenance, but does not itself establish relevance, completeness, or source truth. Completing the assignment therefore requires checking the meaning of all 10 answers.

## Two coverage policies

| Policy | Behavior |
|---|---|
| `strict` — default | Publishes only source-validated answers with positive model coverage. After bounded repair attempts, an unconfirmed answer becomes a refusal. |
| `diagnostic` — explicit opt-in | May publish validated exact source passages despite negative or failed coverage auditing. Keeps that result and flags the answer for manual review. |

Both policies block invalid IDs, substituted quotations, and free model prose. In diagnostic mode, `contract_pass` checks the answer/source/exact-quote contract; it **does not mean** the model confirmed completeness. Inspect `coverage_supported`, `manual_review_required`, `contract_includes_model_coverage`, and the report summary to see the distinction.

For a new run, review **all 10 answers**, including those accepted by the model. Until a separate review is recorded, `assignment_complete` remains `false`. Check sources and quotations, retrieved-chunk bindings, answer meaning, completeness, and the roles of the actors described. `expected_terms` and expected-document hits do not substitute for this review.

The historical semantic verifier for paraphrased claims is not used in extractive mode: `semantic_verifier_used=false` and `positive_semantic_verifier_pass=0` are expected. `positive_coverage_pass` records the coverage audit. Historical `--answer-style paraphrase` is opt-in and incompatible with `diagnostic`.

## Local setup

Run all commands **from the repository root**, with `.venv` activated. Day 24 uses Python's standard library and modules from Days 21 and 23; it needs no Groq key.

```bash
source .venv/bin/activate
ollama list
```

If `bge-m3` and `qwen2.5:14b` are already installed, use them. Other installed models need not be removed. Otherwise:

```bash
ollama pull bge-m3
ollama pull qwen2.5:14b
```

Ollama must serve `http://127.0.0.1:11434`. An already-running Ollama desktop app does not require another `ollama serve` process.

| Parameter | Default |
|---|---|
| Knowledge base | `day-21-document-indexing/knowledge.db` |
| Embeddings / quote selection | `bge-m3` / `qwen2.5:14b` |
| Coverage auditor | Same model; override with `--verifier-model` |
| Strategy / rewrite | `fixed` / `heuristic` |
| Candidates / final context | `20` / `5` chunks |
| Raw cosine threshold | `>= 0.50` |
| Style / policy | `extractive` / `strict` |
| Context / generation limit | `16384` / `2500` tokens |
| Temperature / HTTP timeout | `0` / `600` seconds |

A new live run needs an up-to-date index. If it is missing or `verify` reports a stale index:

```bash
python day-21-document-indexing/main.py build
python day-21-document-indexing/main.py verify
```

**Root READMEs are part of the indexed corpus.** After replacing these files and after committing, rebuild the index in the final checkout and run `verify`. New scores and answers may change; saved reports describe the earlier run. Saved console replay needs neither the index nor Ollama.

## One question and the full question set

Global flags go **before** `ask` / `evaluate`. This example explicitly selects the diagnostic policy used in the reviewed run:

```bash
python day-24-citations-grounding/main.py --coverage-policy diagnostic \
  ask "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --output day-24-citations-grounding/reports/check/worker.json

python day-24-citations-grounding/main.py questions

python day-24-citations-grounding/main.py --coverage-policy diagnostic \
  evaluate --output day-24-citations-grounding/reports/check/evaluate.json
```

`questions.json` contains 10 positive questions and 2 negative controls. `ask` prints the complete JSON; `evaluate` saves per-question JSON details and an adjacent Markdown report. Remove `--coverage-policy diagnostic` to use the strict default.

For `evaluate`, exit `0` means the automatic contract passed under the selected policy; diagnostic mode still needs manual review. Exit `1` means failed checks with a saved report; exit `2` means a technical or configuration error. The separate `ask` command does not perform the question-set summary checks.

## Demonstrating abstention

| Recorded scenario | Result |
|---|---|
| `negative-02`: orbital-speed question, max cosine ≈ 0.423 < 0.50 | `below_threshold`, refusal and clarification, 0 selected chunks and 0 structured model calls |
| `negative-01`: revenue question, max cosine ≈ 0.520 >= 0.50 but the fact is absent | `insufficient_context`, refusal and clarification without invented sources |
| Worker question at temporary threshold 0.99, max cosine ≈ 0.594 | `below_threshold`, refusal and clarification, 0 selected chunks and 0 structured model calls |

```bash
python day-24-citations-grounding/main.py --coverage-policy diagnostic \
  --min-similarity 0.99 \
  ask "Which process periodically collects GitHub repository snapshots into SQLite on Day 18?" \
  --output day-24-citations-grounding/reports/check/threshold_check.json
```

Use `0.99` only for a clear experiment with the same question; the working default remains `0.50`. Calibrate the working threshold for your index using Day 23's procedure. Exact scores may differ after rebuilding.

Refusals have empty `sources`, `quotes`, and `claims`: no substantive answer requires no invented evidence. The refusal and clarification follow the question's language. Zero calls at the threshold gate assumes the default `heuristic` rewrite; `llm` rewriting may make a separate call. HTTP and embedding failures remain technical errors rather than being disguised as “I don't know”.

## Record everything in the console

```bash
# Replay the saved real run, pausing on Enter:
python day-24-citations-grounding/console_demo.py

# Perform a new live run with local Ollama:
python day-24-citations-grounding/console_demo.py --live
```

The first mode is explicitly labeled as saved-report replay. It prints every answer, full quotations, `source` / `section` / `chunk_id`, local file-line checks, the original 7/10 model coverage, and recorded 10/10 manual review. `--no-pause` prints everything without stopping.

`--live` gets new answers with the 14B model and diagnostic policy. It saves `reports/check/console_live.json`, Markdown, answer checkpoints in `console_live_answers/`, and `console_live_threshold.json`. Old manual judgments are not carried forward; Enter only advances the screen. Existing outputs are not overwritten: choose new `--report` and `--threshold-report` paths for another run.

For the video, highlight the execution mode, actual source fields, exact quotations, the distinction between the source contract and semantic completeness, negative auditor judgments, and both refusal scenarios. Compare the working threshold 0.50 with the experimental 0.99. See the [Russian recording guide](CONSOLE_VIDEO.ru.md).

## Checks and Git files

```bash
python day-24-citations-grounding/test_day24.py -v
python day-24-citations-grounding/test_console_demo.py -v
```

The current suites contain 116 core tests and 19 console tests: 135 total. They check evidence bindings, policies, refusals, errors, and the CLI/HTTP/SQLite workflow using Ollama stand-ins. Passing these tests is not a new live evaluation of model quality.

`reports/check/`, logs, packaging manifests, and old documentation copies are ignored. The final v14 pair, three console JSON files, and selected historical reports required by regression tests are retained. Do not delete or ignore all of `reports/`: the demonstration and some tests read these files.

Further details, in Russian: [assignment checklist](ASSIGNMENT_CHECKLIST.ru.md), [verification notes](VERIFICATION.ru.md), and [diagnostic-policy rationale](FIX_DIAGNOSTIC_POLICY.ru.md). Presentation limitations include surplus passages, RU/EN duplicates, and truncated chunk boundaries. The reviewed run does not guarantee quality on arbitrary future questions.
