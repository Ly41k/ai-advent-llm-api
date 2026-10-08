# Final package validation

- 28 original Day 29 offline tests passed from the packaged directory on Python 3.12.
- All eight supplied report checksums, envelopes and summary bindings passed the structural verifier.
- All original V1 Python files and every delivered V2–V5 experiment file are byte-for-byte unchanged.
- All eight packaged JSON reports are byte-for-byte identical to the uploaded originals.
- All 24 factual-subset observation identities match the preserved baseline/V3 messages and profile settings.
- V4 routing tests passed earlier (four tests); V5 scripted import/replay generated only three changed-question responses and no calls on a complete repeat.
- The current environment did not run Qwen. Live timings and resources come from the user's Mac reports.
- Manual review approves the selected profile's four factual/abstention cases (12 responses), not the full five-case control set.
- V5's procedural c3 remains a semantic/evidence issue despite an automatic PASS. No source report was edited to hide it.

Runtime reuse still requires the user's original models, index, hardware and settings. Structural report verification works offline.
