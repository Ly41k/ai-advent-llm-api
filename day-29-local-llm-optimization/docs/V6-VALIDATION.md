# V6 implementation validation

- 28 original V1 measurement/cache/resource tests passed.
- 17 new V6 tests passed: incorrect evidence binding, unquoted commands with
  changed arguments, status versus execution, recurrence completeness, literal
  boundaries, no raw-response edits, exact evidence focus/fallback, preservation
  of foreign-language facts and all explicit projects, detailed procedure tables,
  generic templates without expected domain answers, candidate-only cache
  invalidation, three cached quality failures with zero repeat calls, restoration
  after failure, a three-repeat cap and protection of original output files.
- Scripted integration: 9 cached observations plus 3 new changed procedure
  answers; a repeated quality-blocked run makes zero answers/probes/warmups.
- Offline identity reconstruction from the real control-v5.json: 27 observations
  retain job keys; only three optimized base-10 keys change with V6 messages.
- All original V1–V5 Python bytes and eight uploaded JSON reports are preserved.
- V5 offline audit detects all three known optimized procedure defects; the
  other twelve optimized observations are ready for human review, not
  automatically semantically approved.
- Original envelopes, response hashes and source passages remain unchanged.
- No live Ollama is available in this preparation environment. No V6 model
  quality, latency or memory results are fabricated. Those require the Mac run.

Reproduce implementation tests from repository root:

```bash
python -m unittest discover -s day-29-local-llm-optimization -p test_day29.py -v
python -m unittest discover -s day-29-local-llm-optimization/experiments/quality_v6 -p test_quality_v6.py -v
```

Historical measurement validation: docs/V5-VALIDATION.md.
