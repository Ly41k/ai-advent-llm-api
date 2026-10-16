# Day 32 — final acceptance

Date: 2026-10-16. **The owner accepted Day 32 as PARTIAL.**

| Area | Result |
|---|---|
| Day 32 Course Minimum | PARTIAL — accepted with retained limitations |
| Local technical integration | PASS |
| Local AI review quality | PARTIAL |
| GitHub Actions preflight | PASS |
| GitHub Actions live E2E | FAIL — two HTTP 403 failures |

The local result has `execution_environment=local_mac`. It is not a successful GitHub Actions live E2E. A technical `completed` status does not replace human quality assessment.

## Immutable bindings and history

- Repository: [Ly41k/ai-advent-llm-api](https://github.com/Ly41k/ai-advent-llm-api).
- Bootstrap [PR #1](https://github.com/Ly41k/ai-advent-llm-api/pull/1) was merged. Trusted base/main/source: `c450c3fc4f643531889162c4acbb068abb9bf1c6`.
- Demo [PR #2](https://github.com/Ly41k/ai-advent-llm-api/pull/2) remains open and Draft. Head: `ae74ec45c288e7f0547f7fdf380a24edf9a848e8`.
- Its only change is `day-32-pr-review/demo/percentage.py`, intentionally containing `return value / 0`. It was not executed; the PR was neither merged nor closed.
- The initial bootstrap workflow validation defect was fixed before merge. Subsequent failed attempts remain recorded below.

| Real GitHub run | preflight | review | publish | Groq POST attempts |
|---|---|---|---|---:|
| [38940777931](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38940777931) | success | skipped | skipped | 0 |
| [38945811433](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38945811433) | success | failure: http_403 | skipped | 1 |
| [38952494436](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38952494436) | success | failure: http_403 | skipped | 1 |

The live runs were separate dispatches, both attempt=1, not Re-run jobs. Both failure artifacts have unknown usage/request ID, github_calls=4 and retrieval_selected_chunks=3. `generation_calls=1` means one attempted POST, not a successful generation. No retry or OpenAI fallback occurred.

Original artifacts copied into the separate non-public evidence package:

| Artifact | ID / link | Original ZIP SHA256 |
|---|---|---|
| day32-preflight-38940777931-1 | [12063625798](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38940777931/artifacts/12063625798) | `27eb2618169cba86a43c4eb60250a7b85793d65990355d972a6a3e37cde435a3` |
| day32-review-38945811433-1 | [12067388422](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38945811433/artifacts/12067388422) | `d0fffac59223fac687c0e41fe07aed7e632d535bf274ce089fe9f08f764d9be2` |
| day32-review-38952494436-1 | [12068454878](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38952494436/artifacts/12068454878) | `93fd07d386e04bec90d5e9de03da6e9c33e3a70c12b41e002bdaa8a2c0bd26ec` |

GitHub retention is finite; local ZIP copies preserve evidence after expiry. Additional preflight artifacts from the live runs: [12066290998](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38945811433/artifacts/12066290998) and [12067859561](https://github.com/Ly41k/ai-advent-llm-api/actions/runs/38952494436/artifacts/12067859561). Their metadata/links are retained; those two additional preflight ZIPs are not included.

## Real local full review

Groq `openai/gpt-oss-120b`, Mac Python 3.13.3, curl 8.7.1. One authorized POST, HTTP **200**, curl exit 0; no retry, redirects or fallback. The local helper remains external; application code and workflow were unchanged.

- Actual usage: **649 input / 284 completion tokens**.
- HTTP request ID: `req_01m533sf0sev1r2mnq27rfh7t6`.
- Completion ID (`response.id`, stored as request_id by the original adapter): `chatcmpl-9bfc9e5b-ff81-43b1-b816-8c619cda2e3c`.
- Request body SHA256: `1e649afdab2d725d4597a615bfb47ec37ef03ad783322a3ce8b065e690a0cdc5`.
- Context digest: `23012115b65569b33653636cf7dae77e125cfadf964d838f8f7c6136f45b8944`.
- Input bound 3757 <=4000; maximum completion 2000, reasoning low, timeout 90 s.
- FTS5/BM25: 247 indexed chunks, 20 oversized chunks omitted, 3 selected documents, 2 changed lines. This is bounded retrieval, not whole-repository analysis.
- System prompt, diff, documents and strict JSON Schema came from unchanged `groq_adapter.request_body()`; serialized bytes matched the prepared body. `mock_generation_outputs=0`.

The existing validator accepted one finding, with rejected_findings=[] and omissions=[]. Report integrity, Markdown and retained findings were rechecked offline. The original response passed schema/validation in the local pipeline; initial final inspection had the three reports. The owner subsequently added the raw envelope and other originals to the private package on Mac; that final package was not re-read in this environment.

## Human quality assessment

**The main defect was correctly detected:** [percentage.py:2](https://github.com/Ly41k/ai-advent-llm-api/blob/ae74ec45c288e7f0547f7fdf380a24edf9a848e8/day-32-pr-review/demo/percentage.py#L2) contains `return value / 0`, raising ZeroDivisionError for numeric input. The suggested `/ 100` matches the [trusted contract](https://github.com/Ly41k/ai-advent-llm-api/blob/c450c3fc4f643531889162c4acbb068abb9bf1c6/day-32-pr-review/demo/README.md#L3-L4).

Retained limitations:

1. The finding spans lines 1–2, including defective line 2. This passes the validator but is less precise.
2. Evidence contains only `F1H1R2`. D1–D3 were supplied in the prompt, but no document evidence ID appears in the finding; strict document grounding was not demonstrated.
3. The extra suggestion to guard zero input is unsupported: zero input is valid and `0 / 100 = 0`. The main fix is correct; the extra recommendation is not accepted.
4. Original `semantic_support_verified=false` remains unchanged. This separate report records the human assessment; the original output was not edited to obtain PASS.

## Tests and cost accounting

- Original offline suite: Mac Python 3.13.3, **53/53 PASS**, no model; original log/summary retained. Those available files cover the initial Mac check before bootstrap; the owner separately confirmed another 53/53 after the workflow fix.
- External local acceptance helper: **9/9 PASS on Mac**, evidenced by the supplied terminal transcript. HTTP/GitHub responses in those tests are mocked; real FTS5, packing and validation run. These are not nine generations.
- Actionlint 1.7.12: PASS after bootstrap fix; prior evidence retained. No new lint/Actions execution during finalization.
- SQLite `ResourceWarning: unclosed database` remains a separate issue; the tests passed. No connection-lifecycle fix was implemented now.

| Observation | Input / completion | Estimated list-price cost | Actual charge |
|---|---:|---:|---|
| Mac full review | 649 / 284 | $0.00026775 | Unverified, actual_billed_usd=null |
| Separate Mac smoke-test, owner-reported | 74 / 19 | $0.00002250 | Unverified; original API response not supplied |
| Two Actions HTTP 403 attempts | null / null | Unknown | Unknown |

Estimates use the retained 2026-10-16 pricing snapshot: $0.15 input / $0.60 completion per 1M tokens. They are usage arithmetic, not an invoice. Four Day 32 POST attempts are known: two Actions failures, one Mac smoke-test and one Mac full review. The full review is not presented as the only call in the day's history. The owner confirmed Free Plan, but an actual $0 charge is not asserted. OpenAI API was not used for Day 32; the approximately $5 manual reserve for Days 32–35 does not imply automatic fallback.

## HTTP 403 cause and backlog

The exact cause is **unknown**. The original urllib HTTPError handler discarded provider body/headers. The same full payload succeeding on Mac disproves a blanket claim that this body cannot work, but does not isolate the runner failure. Network route/IP, HTTP/TLS/User-Agent and key/project permissions remain hypotheses; WAF, a wrong key or a paid-plan requirement are unproven.

[Post-course backlog](BACKLOG_AFTER_COURSE.ru.md) retains safe 403 diagnostics, full-payload verification inside Actions, document evidence, unsupported suggestions and SQLite connection closure. No implementation changed now. Any new real request needs separate authorization.

## Evidence and stop boundary

The separate private package retains original GitHub ZIPs/reports, local reports and original Mac request.json/raw-response.json/POST_ATTEMPTED.json, original Mac 53-test log/summary, the 9-test transcript, links and a SHA256 manifest. The first assembly lacked three Mac originals and explicitly labelled the identical reconstructed body. The owner subsequently ran complete_on_mac.py with zero network/generation calls and reported integrity PASS, secret_scan PASS_heuristic_no_matches and files_verified=49. Final private archive: day32-finalization-with-mac-originals.zip; SHA256 `1e354d1522353de3fc6a57169115805602469ba755d7e8157873d821cf8602b8`. That final hash and completed transfer are owner-reported: the completed ZIP was not supplied here for independent verification. Original model outputs were not edited.

Only README, final reports, backlog and checksum metadata are proposed for public delivery. Raw payload/response, model JSON/Markdown artifacts and the private evidence package are excluded from GitHub without separate authorization.

`DAY32_LIVE_ENABLED=false` remains in place; its last confirmation came from the successful local helper's repeated checks and the owner. Stage 5 did not enable it. PR #2 remains open Draft, neither merged nor closed. Stage 5 preparation performed zero new Groq/OpenAI calls, dispatches, approvals or GitHub writes. Days 1–31 and workflow are unchanged. **STOP.**
