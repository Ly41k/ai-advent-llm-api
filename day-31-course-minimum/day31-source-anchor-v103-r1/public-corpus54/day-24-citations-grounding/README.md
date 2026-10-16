# Day24 — exact evidence with an explicit coverage policy (v14)

Protocol verbatim-extractive-v14. bge-m3/qwen2.5:14b, user's MacM1/32GB/Python3.13.3; stdlib + Days21/23. Corpus/index/models unchanged. The single supplied full live v14 diagnostic run is confirmed against the original assignment:10/10 source-based answers manually supported and complete,53/53 exact quotes,2/2 correct refusals. All46 selected chunks reproduce canonical Day21 fixed metadata/text/IDs/line bounds. Model coverage remains7/10; negative01/03/05 judgments and original results are unchanged. Original assignment_complete=false meant review was pending; reviewed manual_summary.assignment_complete=true records the completed assistant source review. This is not independent human review or strict-model-coverage10/10. See reports/live/REVIEW_evaluate_v14.ru.md and byte-preserved original/reviewed JSON.

Strict remains the CLI/API default and gates publication on model coverage. An explicit --coverage-policy diagnostic mode publishes only app-validated exact selected source passages, preserving negative/failed coverage judgments and flagging manual review. This is a deliberate source-contract mode, not a model quality pass. No negative verdict becomes positive. All10 answers must be manually reviewed for relevance/completeness/source roles before closing the assignment.

Source/section/chunk_id and exact quotes are application-owned. Models select catalog quote IDs and optional coverage proof IDs; they cannot publish free synthesis/translation or invented quote text. Below cosine0.50: unknown+clarification with empty evidence and zero structured calls in heuristic mode. Selector unknown above threshold also refuses. Identity failures still block publication in diagnostic mode; HTTP/embedding failures remain technical errors. Exact source identity does not guarantee relevance, completeness or source truth.

Diagnostic contract_pass covers answer/sources/exact quotes only. coverage_supported stays false when false; manual_review_required is true for a negative/failed audit. Summary includes diagnostic_positive_questions, positive_flagged_for_manual_review, unchanged positive_coverage_pass and assignment_complete=false while manual review is pending. Each row exposes contract_includes_model_coverage. Markdown visibly marks failed coverage. Do not present a10/10 source contract as10/10 answer quality. Historical paraphrase is opt-in and cannot use diagnostic policy.

```bash
python day-24-citations-grounding/test_day24.py -v
python day-24-citations-grounding/main.py --coverage-policy diagnostic evaluate --output day-24-citations-grounding/reports/check/evaluate_v14.json
```

150 local tests:116 Day24+34 Days21–23, Python3.12.14. Includes real SQLite/HTTP/CLI with scripted Ollama stand-ins, not real model quality. Scripted10+2 passes. No local live Ollama run here; the user supplied a full live v14 diagnostic report and all10+2 were reviewed. Program code remains identical to the tested delivered v14. Preserve environment/index/models/reports/check. Read START_HERE.ru.md and FIX_DIAGNOSTIC_POLICY.ru.md. Global options precede subcommands. Exit0 is automatic source-contract pass in diagnostic mode; exit1 saves a failed contract report; exit2 is technical failure.

## Console video demonstration

Run `python day-24-citations-grounding/console_demo.py` to replay the reviewed user reports with Enter pauses. All answers, source/section/chunk_id, full quotes, local file/binding checks, original model coverage7/10 and recorded manual review10/10 are shown. Replay is explicitly labeled; `--live` performs a new run without carrying forward old manual judgments. See CONSOLE_VIDEO.ru.md. All15 original v14 Python files remain unchanged; the presentation module has19 additional tests.
