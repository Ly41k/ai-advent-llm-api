# Day 35 — Local AI Development Journal

Generate a Russian development-journal draft from the real first-parent history of a local private Git checkout. Python standard library, read-only Git, GitHub CLI for GET-only PR metadata, loopback Ollama, Qwen2.5:14b Q4_K_M, Markdown. No cloud LLM, embeddings, or Git writes.

**Final status: Course Minimum PASS.** The accepted Russian journal covers four confirmed merged PRs for 2026-10-14 in `Europe/Kyiv`. The owner supplied local `review` and `summary` output: HTTP 200 from Qwen2.5:14b Q4_K_M, 201.941 seconds of generation, 204.529 seconds for the run, all reference checks passing and an unchanged source checkout. Ly41k recorded semantic acceptance on 2026-10-17. Private output and raw evidence remain on the owner's Mac. See the [final report](FINAL_REPORT.md).

Two real local generation calls were made in total. The first omitted source URLs; the second passed after adding an explicit full-URL format instruction. No links were inserted after generation and the first output was not edited. Runtime code is unchanged after acceptance; final packaging changes documentation and safe status only. Historical v3 request verification remains supported.

See [Russian instructions](README.ru.md) for the complete workflow, acceptance criteria, limitations, privacy rules, and commands. See [video guide](VIDEO.ru.md) and [publication checklist](PUBLICATION.ru.md).

## Inspect the accepted result without generation

Run from the course repository root on the owner's Mac. The accepted result is `day35-imperz-20261014-07`; its private files are not included in this repository.

```bash
python3.13 day-35-real-task/main.py summary \
  "$HOME/day35-private/results/day35-imperz-20261014-07"
```

Expected: `technical`, `ai_generation_evidence`, `ai`, `course_minimum` and `human_review` are `PASS`; `http_status=200`, `model=qwen2.5:14b`, `events_count=4`, `imperz_unchanged_during_run=true`. Generation took 201.941 seconds; the full run took 204.529 seconds, with 11,357 prompt / 698 output tokens. `generation_calls=1` applies to this accepted run; there were two real generation calls overall.

`summary` verifies saved artifacts offline and updates local `acceptance.json`; it does not contact GitHub or Ollama and does not print the private journal, evidence, source SHA or source paths. Do not open raw private files while recording. The accepted generation and semantic review do not need to be repeated for the video.

Independent checks:

```bash
python3.13 -m unittest discover -s day-35-real-task/tests -v
python3.13 day-35-real-task/main.py check-model
```

The 30 synthetic tests use disposable Git fixtures and mocked metadata/HTTP, without real model requests. They passed in the preparation environment (Linux, Python 3.12.14); a complete Mac suite result has not been separately supplied. The accepted live scenario and human review ran on the Mac with Python 3.13. `check-model` only reads local Ollama `GET /api/tags` and checks the installed Q4_K_M model; it does not generate text.

## Fresh-run reference

The following is a reference for a separately authorized new run, not a step of the accepted-result video. Do not run it to reconfirm the existing PASS. `--repo` must be an existing checkout root, not a GitHub URL or an exported folder without `.git`. The timestamped run ID avoids reusing an existing result directory.

```bash
DAY35_RUN_ID="day35-imperz-20261014-$(date -u +%Y%m%dT%H%M%SZ)"
python3.13 day-35-real-task/main.py run \
  --repo /ABSOLUTE/PATH/Imperz --date 2026-10-14 --ref main \
  --expect-pr 111 112 113 114 --run-id "$DAY35_RUN_ID"
```

Requires a full existing checkout, authenticated `gh` with read access, and a running local Ollama. Standard GitHub two-parent merges and one-parent squash commits with a matching PR suffix are supported. Date selection uses GitHub `merged_at` in `Europe/Kyiv`; `merge_commit_sha` must exist on the local first-parent main chain. The content always comes from local Git, not remote PR descriptions/diffs. The CLI lists closed PR metadata with pagination and explicitly rejects closed-without-merge entries. Control PRs are coverage assertions, not a fixed content selector.

Scope is confirmed merged PR changes only. Other commits whose committer timestamp falls on that day are recorded separately as unattributed candidates; they are not claimed as incorporated on that date or passed to the model as completed work. Unsupported rebase histories stop generation. Network access is needed only for read-only metadata collection; verification and human acceptance work offline. All LLM requests remain local.

Diff excerpts are bounded before the single generation request. Every event is retained; omitted text is recorded. Git content is untrusted data. Generated links, PRs, SHAs and event coverage are checked deterministically; meaning, draft status and numerical claims require human review.

Private output defaults to `~/day35-private/results/<run-id>/`, outside the public course repository. It includes the journal, evidence, acceptance, request, raw response and timing/model metrics. Do not publish these private outputs. The exact model output is retained; human approval is bound to artifact hashes and is invalidated by later edits.

The implementation and safe documentation are published in open [PR #9](https://github.com/Ly41k/ai-advent-llm-api/pull/9); it has not been merged. The final package includes updated root READMEs and their two Day 34 delivery-manifest SHA-256 entries. Other Day 34 fingerprints remain unchanged. `STATUS.json`, the final reports and publication checklist retain the final-v5 preparation snapshot from before the PR was published; their zero-write/not-published fields describe that snapshot. The CLI itself performs no GitHub writes. The video guide is ready; recording by the owner has not yet been confirmed.
