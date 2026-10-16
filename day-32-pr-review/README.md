# Day 32 — Minimal AI Pull Request Review

**Final status, 2026-10-16: Day 32 accepted as PARTIAL. Local technical integration PASS; local AI review quality PARTIAL; GitHub Actions preflight PASS; GitHub Actions live E2E FAIL (two HTTP 403 failures).**

The separately authorized Mac full review used Groq `openai/gpt-oss-120b`, one POST, HTTP 200, 649 input / 284 completion tokens. It correctly found `percentage.py:2` and suggested `/ 100`; document evidence ID was absent and the extra zero-input guard suggestion was unsupported. Three base-revision FTS5 documents were selected. SQLite ResourceWarning remains recorded.

See [FINAL_REPORT.md](FINAL_REPORT.md) ([RU](FINAL_REPORT.ru.md)) for immutable SHAs, request IDs, all failed-run and artifact links, the separate 74/19-token smoke-test, evidence provenance and unverified actual billing. Raw request/response and model artifacts remain outside the public repository. `DAY32_LIVE_ENABLED=false`; demo [PR #2](https://github.com/Ly41k/ai-advent-llm-api/pull/2) was closed without merge, and documentation [PR #3](https://github.com/Ly41k/ai-advent-llm-api/pull/3) was merged. No new generation is authorized.

The setup/bootstrap/live procedures below are retained for historical context and separately authorized reproduction; they are not pending actions or permission to run again. The original Actions-only CLI is unchanged; local acceptance used an external curl helper without pretending to be GitHub Actions.

Public course repository only: `Ly41k/ai-advent-llm-api`.

PR metadata/files/patch → bounded context → base-revision README FTS5 → one Groq POST → deterministic JSON/evidence/line validation → JSON/Markdown artifacts → optional ordinary bot comment.

Python 3.12+ with SQLite FTS5; standard library only. No package installation, PR code execution, or dependencies on Days 1–31. Original offline delivery passed 53/53 tests on Mac Python 3.13.3; the external local acceptance helper passed 9/9 there. Historical offline evidence is retained.

## Offline reproduction

From the repository root:

```bash
python -m unittest discover -s day-32-pr-review/tests -v
python day-32-pr-review/main.py offline \
  --fixture day-32-pr-review/tests/fixtures/review-case.json \
  --root day-32-pr-review/tests/fixtures/project \
  --output day-32-pr-review/reports/offline-demo
```

Offline mode creates no network transport, reads no credentials, and makes no provider calls. Tests block real HTTP/socket entry points. Fixture PR #123, SHAs, source patch and review are synthetic. Secret-filter tests contain deliberately fake placeholder assignments, never real credentials.

Outputs: `review.json`, `review.md`, `run-summary.json`. Offline reports explicitly record `mode=offline_mock`, `generation_calls=0`, `network_calls=0`, `mock_generation_outputs=1`. Parsing, retrieval, validation and rendering really execute; GitHub and generation are mocked. This is not live acceptance. Current evidence: [OFFLINE_RESULTS.ru.md](OFFLINE_RESULTS.ru.md) and `verification/`.

## Scope and trust boundary

Only owner-authored PRs from owner-controlled `day32-demo` to `main`, initiated by `Ly41k`, are admitted. Same-repository membership, branch name and author checks do **not** establish push permissions. `main` and the demo branch must be owner-controlled/protected; review the exact head before approval if collaborators exist.

Automatic `pull_request` events perform preflight without any provider secret. Real generation uses **manual `workflow_dispatch` from main**, followed by GitHub Environment approval. This avoids a custom approval ledger and ensures the executable workflow comes from main. The application is checked out at the fixed trusted revision; for live this must equal the current PR base SHA. PR title/body are never included in the prompt. PR patches are data, never commands.

No checkout/build/test/install/eval/subprocess of PR content. No tools, remote browsing, inline review, auto-fix, approve, merge, push, Qwen, multi-agent analysis or OpenAI fallback.

| Limit | Value |
|---|---|
| Files | 20; bounded API pagination, 10/page |
| Patch | 32 KiB total; whole hunks only |
| Code context | API patch only; no full head-file reads |
| Documentation | Root/touched-day/Day 32 README RU/EN and changed file's nearest README from trusted base; ≤32 files / 1 MiB |
| Retrieval | In-memory SQLite FTS5/BM25; ≤3 selected hits |
| Provider/model | Groq / `openai/gpt-oss-120b` |
| Input | Conservative upper bound ≤4000 tokens |
| Completion | 2000 tokens including reasoning; one POST |
| HTTP timeout | 90-second socket timeout; workflow timeout additionally bounds execution |
| Findings | 5; changed-line coordinates plus supplied evidence IDs |
| Active runner timeouts | 3 + 4 + 2 minutes; approval waiting separate |
| Artifact retention | 7 days |

To keep dependencies minimal, no tokenizer is downloaded. The fixed GPT-OSS byte-BPE input bound uses the entire serialized request's UTF-8 byte count plus 1024 reserved template/service tokens. This is a conservative **upper estimate**, not measured server usage; it includes schema/JSON overhead and admits less text than exact tokenization. The authorized local sample measured 649 input tokens against bound 3757; this single sample does not prove all future service-overhead assumptions. Actual usage is read from the response and excess usage invalidates the run without retry.

Unavailable/binary/unsupported/oversized/truncated patches, mismatched hunk/stat counts and context-budget omissions are explicit unreviewed regions. LEFT anchors refer to base lines; RIGHT anchors to head. Rename LEFT links use the original path. Document citations alone cannot anchor code findings. `findings=[]` is valid after analysis; all rejected findings yield `invalid_findings`, not a clean review. Invalid JSON, wrong model, refusal/tool calls, missing usage or incomplete generation stop the run without repair calls.

Secret-like content is withheld before generation; decoded JSON strings and final reports are checked too. This remains heuristic. Offline prompt-injection tests prove separation of data and execution, not the real model's semantic resistance. Source existence/line validation does not prove that an engineering finding is correct.

## Bootstrap, after separate authorization

1. Extract the archive **at the existing repository root**, preserving the hidden `.github/` directory. It adds only Day 32 and its workflow; do not extract into Day 31.
2. Use branch **`day32-bootstrap`**, run the offline commands and inspect `git diff --cached --check`. Do not create a provider secret or enable any `DAY32_*` variable yet.
3. Revalidate pinned checkout/upload/download Action commit SHAs against their official upstream repositories before live. Their current remote availability was not checked during this offline implementation.
4. Separately authorize a bootstrap PR. Its jobs intentionally skip because its branch is not `day32-demo`; the application does not yet exist in its base. This is not AI acceptance.
5. Review the Python and YAML; separately authorize merge. The next demo PR can then run the trusted application from main.

No commit/push/PR/merge is performed by this package. Detailed Russian instructions: [README.ru.md](README.ru.md).

## Environment secret and approval setup

In repository Settings → Environments create **`day32-live`** before enabling live:

1. Configure **Required reviewers**. A sole maintainer must explicitly allow self-review; otherwise the initiator cannot approve their own job.
2. Restrict **deployment branches/tags to main only**. Do not allow all branches, the demo branch or PR merge refs.
3. Add **Environment secret `GROQ_API_KEY`** only after protection exists. Paste directly into GitHub's secret field; never put the value in chat, files, PRs, screenshots or CLI arguments. Do not create a repository-level copy of this secret.
4. Verify branch push permissions for main/demo, current Groq Free Plan, fixed model access, rate limits and pricing. None of these account settings was verified offline.
5. Set repository Actions **variables** to `true` only when verified: `DAY32_ENVIRONMENT_CONFIRMED`, `DAY32_BRANCH_TRUST_CONFIRMED`, `DAY32_FREE_PLAN_CONFIRMED`, `DAY32_LIVE_ENABLED`.

GitHub can auto-create an unprotected Environment; its name alone is insufficient. Confirmation variables prevent accidental launches, not malicious configuration changes. If reviewers or main-only deployment restrictions are unavailable, leave live disabled and do not add the key. Agree on a simpler safe alternative separately.

## Exactly one live test, after separate authorization

1. Create owner-controlled `day32-demo` from the updated main. Add only `day-32-pr-review/demo/percentage.py` containing `def percentage(value):` and an indented `return value / 0`. This intentionally defective example is never executed and need not be merged. Do not change workflow/application/dependencies.
2. Open the separately authorized demo PR. Automatic preflight should retrieve real PR files/patch and documentation, create artifacts, and record **zero generation calls**. Confirm admitted changes and at least one selected document.
3. Record the PR number, exact 40-character head SHA and base/application SHA. Keep the PR unchanged; if base no longer matches the application revision, refresh and repeat only no-generation preflight.
4. After approval to spend one call, run Day 32 PR Review manually on **main**, with exact PR/head and `confirm_one_call=true`. `publish_comment=false` by default; enable only if comment publication was separately authorized.
5. The review job must wait for `day32-live` approval. Inspect main workflow revision, PR/head, branch permissions and context limits before approving. The application re-fetches PR metadata/files after approval.
6. Verify one Groq POST, actual usage/request ID, real FTS5 sources, validated findings and three artifacts. Manually check the result, preferably the division-by-zero finding. Save the run URL, artifact URL and human verdict. Verify the comment if authorized.
7. Disable `DAY32_LIVE_ENABLED` after the attempt. Never automatically rerun a request: `run_attempt>1` is blocked. A new dispatch is a new separately authorized attempt with a new Environment approval.

After timeout/cancellation, a sent request can still run. One generation call means one attempted send; unknown usage/cost remain null, not zero. No retry/fallback or second model. A changed PR SHA after generation invalidates publication without a new generation call.

### Demonstration percentage helper contract

The percentage helper accepts a number and returns that number divided by 100. The percentage helper must never divide by zero. This contract exists solely for the small Day 32 demonstration PR; it is not a global project coding rule.

## Cost, evidence and limitations

Groq is primary. The Groq-hosted model name does not spend OpenAI API credit. OpenAI API remains an unused manual reserve of approximately $5 **across Days 32–35**; no OpenAI adapter/key/call is included. Every paid call requires separate agreement. Current code contains only a list-price planning snapshot (2026-10-16: $0.15 input / $0.60 output per million tokens); recheck before live. `estimated_list_cost_usd` is not an invoice. `actual_billed_usd` stays null pending billing reconciliation, even when Free Plan is expected.

Publication is a separate write-permission job; generation has read-only GitHub permissions. Only the bot's own marker comment can be updated. More than 300 comments or duplicate bot markers stop publication without another generation. Report SHA256 detects corruption, not authenticity. There is no atomic transaction between the final SHA read and the comment POST; all links and the displayed review head remain revision-bound.

Other limits: small byte budget, patch-only context, lexical README RAG and heuristic secrets filtering. Mac compatibility, Action pins and real preflight were checked; Actions live failed twice with 403. Local generation success does not establish Actions E2E or complete semantic grounding. No further live work is required for the owner's accepted PARTIAL verdict.

Adapted narrowly from Days 17 (HTTP), 24 (strict JSON/evidence), 27 (advisory reports/usage) and 31 (paths/secrets/source spans/FTS literals); no old-day runtime imports or source edits. Course Minimum is **accepted as PARTIAL**, with the separate outcomes in the final report. Improvements: [BACKLOG_AFTER_COURSE.ru.md](BACKLOG_AFTER_COURSE.ru.md).
