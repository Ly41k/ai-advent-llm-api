# Day 35 — Local AI Development Journal

Generate a Russian development-journal draft from the real first-parent history of a local private Git checkout. Python standard library, read-only Git, GitHub CLI for GET-only PR metadata, loopback Ollama, Qwen2.5:14b Q4_K_M, Markdown. No cloud LLM, embeddings, or Git writes.

**Final status: Course Minimum PASS.** The accepted Russian journal covers four confirmed merged PRs for 2026-10-14 in `Europe/Kyiv`. The owner supplied local `review` and `summary` output: HTTP 200 from Qwen2.5:14b Q4_K_M, 201.941 seconds of generation, 204.529 seconds for the run, all reference checks passing and an unchanged source checkout. Ly41k recorded semantic acceptance on 2026-10-17. Private output and raw evidence remain on the owner's Mac. See the [final report](FINAL_REPORT.md).

Two real local generation calls were made in total. The first omitted source URLs; the second passed after adding an explicit full-URL format instruction. No links were inserted after generation and the first output was not edited. Runtime code is unchanged after acceptance; final packaging changes documentation and safe status only. Historical v3 request verification remains supported.

See [Russian instructions](README.ru.md) for the complete workflow, acceptance criteria, limitations, privacy rules, and commands. See [video guide](VIDEO.ru.md) and [publication checklist](PUBLICATION.ru.md).

```bash
python3.13 -m unittest discover -s day-35-real-task/tests -v
gh auth status
python3.13 day-35-real-task/main.py check-model
python3.13 day-35-real-task/main.py run \
  --repo /ABSOLUTE/PATH/Imperz --date 2026-10-14 --ref main \
  --expect-pr 111 112 113 114 --run-id day35-imperz-20261014-01
```

Requires a full existing checkout, authenticated `gh` with read access, and a running local Ollama. Standard GitHub two-parent merges and one-parent squash commits with a matching PR suffix are supported. Date selection uses GitHub `merged_at` in `Europe/Kyiv`; `merge_commit_sha` must exist on the local first-parent main chain. The content always comes from local Git, not remote PR descriptions/diffs. The CLI lists closed PR metadata with pagination and explicitly rejects closed-without-merge entries. Control PRs are coverage assertions, not a fixed content selector.

Scope is confirmed merged PR changes only. Other commits whose committer timestamp falls on that day are recorded separately as unattributed candidates; they are not claimed as incorporated on that date or passed to the model as completed work. Unsupported rebase histories stop generation. Network access is needed only for read-only metadata collection; verification and human acceptance work offline. All LLM requests remain local.

Diff excerpts are bounded before the single generation request. Every event is retained; omitted text is recorded. Git content is untrusted data. Generated links, PRs, SHAs and event coverage are checked deterministically; meaning, draft status and numerical claims require human review.

Private output defaults to `~/day35-private/results/<run-id>/`, outside the public course repository. It includes the journal, evidence, acceptance, request, raw response and timing/model metrics. Do not publish these private outputs. The exact model output is retained; human approval is bound to artifact hashes and is invalidated by later edits.

The final package includes updated root READMEs and their two Day 34 delivery-manifest SHA-256 entries. Other Day 34 fingerprints remain unchanged. Stop before any GitHub writes. The video guide is ready; recording by the owner has not yet been confirmed.
