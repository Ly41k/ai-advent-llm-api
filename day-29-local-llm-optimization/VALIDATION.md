# V7 implementation verification

- 14 V7 tests passed, using unrelated synthetic archive sources: exact units,
  exclusion of mutation commands/unrelated agent details, language chosen per
  role before the model payload, deterministic citations, no filling missing
  roles, unknown/wrong-role IDs, damaged source and substituted metadata,
  explicit abstention/malformed complete output, the actual selector HTTP
  schema, scoped routing, portable replay of three quality failures with no
  further answers/probes/warmups, tamper detection and runtime restoration.
- The 28 original V1 and 17 V6 tests previously passed; their code is unchanged.
- Offline identity reconstruction from actual control-v6.json: 27 job keys
  unchanged and three candidate base-10 keys changed for V7.
- The original V6 live report's integrity and all 27 reused original result
  objects are verified; the original uploaded V6 quality file is preserved.
- All V1–V6 Python bytes and original live reports are byte-identical.
- The independent stricter V7 reanalysis flags V6 language, missing actual
  verification actions and installation/mutation commands in all three drafts.
- Live V7 calibration and transfer reports from the user's Mac are completed.
  Their seals and independently recomputed audit fields match the originals.
  All selected quote units are exact substrings of the repository sources.
  Calibration passes 3/3; frozen RU/EN transfer cases pass 6/6 semantic reviews.
  Each new case has identical rendered responses across all three trials.
  Frozen runtime and questions match the pre-transfer hashes.
  No runtime changes or extra model calls were made for this final packaging.

```bash
python -m unittest discover -s day-29-local-llm-optimization/experiments/quality_v7 -p test_quality_v7.py -v
```

Historical implementation checks: docs/V6-VALIDATION.md.
