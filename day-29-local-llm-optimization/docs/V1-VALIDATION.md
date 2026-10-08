# V1 validation

Source repository: `Ly41k/ai-advent-llm-api`, commit `3d2e9616dc2fd857a918606f1cb371045ef48cd4`.

Checks performed in the delivery environment on Python 3.12:

- 28 offline Day 29 tests: PASS.
- 71 offline Day 28 regression tests: PASS (unchanged source and repository fixtures/corpus).
- Python compilation: PASS.
- Real CLI `plan`: PASS, zero provider calls; no live model/cache results bundled.

The Day 29 integration tests script local transport/model metadata and retrieval. They verify three-answer reuse with zero new answer/probe/warmup calls, partial resume, interruption/error history, portable import, identity invalidation, context guards, seed/profile ordering, source sharing, raw-output checksums and process metric accounting. Their answers and performance metadata are fixtures, not measured Qwen results.

The psutil sampler can run in this environment, but Ollama/Qwen and the author's Mac are not available here. Live local inference, macOS process visibility, quality, speed, memory pressure and actual Q4/Q5 differences remain to be measured using the supplied commands. No optimization improvement is claimed by this release.

The default context-count probe temporarily uses 32768 context and one output token per unique model/prompt; warmups precede measured blocks. These calls are explicitly reported and excluded from quality and answer-speed statistics. Cached measurements retain their original timestamps.

Accepted reports should undergo manual semantic review in addition to structural verification. SHA-256 checks establish internal consistency, not authenticity. A malformed/poor candidate is an experiment outcome, not something to hide or repeatedly regenerate until a pass.
