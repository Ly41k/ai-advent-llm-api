**English** | [Русский](README.ru.md)

# Day 31 — Bublik Developer Assistant

A developer assistant uses Project RAG for repository documentation, obtains Git facts through a real MCP server, and delegates tasks to Documentation, Git and Verification. Generation runs through local Qwen and Ollama.

**The educational assignment is complete within Course Minimum — Accepted.** Mac evidence covers real tools, delegation, an empty-evidence refusal and one positive RU-1 / Multi answer with exact quotations. The user explicitly approved both claims; Publication Gate returned `answer_accepted=true`. The demonstration video has been recorded.

**Extended Research Stage 7 remains incomplete.** Its limitations and deferred studies are preserved in [BACKLOG_AFTER_COURSE.ru.md](BACKLOG_AFTER_COURSE.ru.md). Course acceptance is not a general model-quality acceptance, acceptance of every question, or proof of a full multi-task Chain.

## Verified configuration

| Component | Verified boundary |
|---|---|
| Base application | App 0.7.29; original `main.py` and 60 Python files retained |
| Model-answer publication | Isolated application copy with Publication Gate v104-r2 and Course Minimum r3 launcher |
| Documentation scenario | Frozen RU-1 / Multi with the existing v103 source-anchor producer and selector |
| Project RAG | Separate FTS54: 54 documents / 510 chunks; production44: 44 documents / 405 chunks retained independently |
| Model | Local Qwen2.5:14b Q4_K_M; temperature 0, seed 31, context 8192, output 1024 |
| Agreed live-run generations | One real Documentation worker call, without retries or cloud fallback |
| Semantic acceptance | Explicit human review bound to immutable claims, selected exact anchors and result version |

RU-1 explains `pending`, `completed`, `failed` and history restoration. The user accepted the omitted broader protective explanation as a non-blocking completeness limitation. Grounding and completeness were assessed separately.

## Architecture

| Role | Responsibility |
|---|---|
| Main | Deterministic routing, shared budget, task dispatch, merge and final checks |
| Documentation | Documentation search in an owned worker; a bounded model task over the selected evidence context |
| Git | Read-only MCP stdio: branch, status, files and diff; no commit/push or arbitrary shell |
| Verification | Provenance, sources, exact quotations and format checks; not a substitute for human semantic review |

`agents demo` runs separate Documentation/Git tasks, then Verification checks their results and Main merges them. These are real processes and MCP/FTS operations with no generation. The accepted RU-1 run performs fresh Documentation/Verification acquisition and passes a shared snapshot to one Documentation Qwen worker. It does not contain a separate Main model call or two independent LLM contexts. See [ARCHITECTURE.ru.md](ARCHITECTURE.ru.md).

## Component locations

- `day-31-developer-assistant/`: base application, tests, evaluation fixtures and documentation. Publication Gate is not installed into its original `main.py`.
- [`day-31-course-minimum/`](../day-31-course-minimum/README.ru.md): three complete verified packages: v103 producer, v104-r1 anchor persistence and r3 launcher, which includes Publication Gate v104-r2. Their original manifests and input evidence are retained.
- Working results, leases and indices remain outside the repository. Historical `/tmp` directories are still required; permanent-state migration and a clean installer are not implemented.

Do not add Python files inside the base application: its retained source binding expects exactly 60 files. JSON files in `evaluation/` are test inputs. Frozen `reports/` inside Course Minimum packages are required by their manifests; do not write new run outputs there.

## Setup and retained-delivery verification

Run commands from the repository root. The target environment is a MacBook Pro M1 / 32 GB, Python 3.13+ and Git. For a new `.venv`:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r day-31-developer-assistant/requirements.lock
```

For an existing environment, activation is sufficient. Delivery verification uses no Ollama, network or indices:

```bash
source .venv/bin/activate
python day-31-course-minimum/verify_delivery.py --root "$PWD"
```

Expected: `status=passed`, `original_packages_verified=3`, `original_app_python_files_verified=60`, `mac_reports_verified=79`, `required_inputs_hidden_by_gitignore=0`, `qwen_calls=0`. This checks integrity and retained human review, **not fresh runtime or semantic acceptance**.

## Real MCP Git without Qwen

```bash
python day-31-developer-assistant/main.py --version
python day-31-developer-assistant/main.py --root "$PWD" git branch
python day-31-developer-assistant/main.py --root "$PWD" git status
python day-31-developer-assistant/main.py --root "$PWD" git diff --scope unstaged
```

These commands call the real MCP Git server without model generation. Diff without explicitly allowed paths does not expose arbitrary file content. An empty diff after a commit is valid.

## Republish the accepted answer without Qwen

The retained external work directory must contain the original audit, raw response, evidence and isolated application copy. Git sources alone do not restore that working state. The command uses the existing explicit user decision and cannot transfer it to a new answer:

```bash
python day-31-course-minimum/day31-course-minimum-r3/entry.py publish \
  --root "$PWD" \
  --v103 "$PWD/day-31-course-minimum/day31-source-anchor-v103-r1" \
  --v104 "$PWD/day-31-course-minimum/day31-anchor-persistence-v104-r1" \
  --work-dir /private/tmp/day31-course-minimum-r3-work \
  --review "$PWD/day-31-course-minimum/evidence/human-review.json" \
  --reviewer-id yuriy
```

For the retained bindings, expect `answer_accepted=true`. The original withheld result, raw response and evidence remain unchanged; derived reviewed/public records are separate. Repeated `publish` calls do not invoke Qwen and create the next numbered export. Binding mismatch causes STOP; do not edit evidence or review to force PASS.

Without explicit human approval, new bindings remain `needs_review` with `answer_accepted=false`. Unsupported claims and runtime refusals cannot become successful publications. Exact quotation and identifier checks alone do not establish semantic support. Ordinary `main.py ask` is not a substitute for the accepted Publication Gate route.

## Preflight and corpus changes

Historical r3 preflight passed on Python 3.13.3: 32/32 checks, real MCP/delegation and an empty-evidence `unknown`, with zero Qwen calls. It used retained native276 evidence, a preparation bundle, production44/FTS54 and a pinned Git HEAD. Day30 was off; the Ollama session had a confirmed process epoch.

For **that same prepared state**, the command is:

```bash
python day-31-course-minimum/day31-course-minimum-r3/entry.py preflight \
  --root "$PWD" \
  --v103 "$PWD/day-31-course-minimum/day31-source-anchor-v103-r1" \
  --v104 "$PWD/day-31-course-minimum/day31-anchor-persistence-v104-r1" \
  --work-dir /private/tmp/day31-course-minimum-r3-work
```

A new commit changes Git HEAD. **Updating root READMEs also changes corpus fingerprints**, so previous indices return stale/STOP when checked against the current corpus. The old receipt does not validate a new revision. Do not rewrite pins, remove reservations or rebuild the old frozen index to force PASS.

This documentation revision rebuilds no indices. Future live retrieval over the changed corpus needs a separately prepared current index and condition checks. Delivery verification, MCP Git and publication of the saved accepted answer need no new Qwen call. The [terminal video scenario](CONSOLE_VIDEO.ru.md) describes the historical prepared environment; the video is already recorded and no new generation is required.

## Retained evidence

- [Final Mac bundle](../day-31-course-minimum/evidence/mac-course-minimum-bundle.json): 79 reports with SHA digests; all 76 prior live reports retained.
- [Human review](../day-31-course-minimum/evidence/human-review.json): c1/c2 `supported`, two claims and seven semantic parts; the user's decision is bound to the current immutable bindings.
- [Accepted public answer](../day-31-course-minimum/evidence/accepted-public-result.json): `answer_accepted=true`, exact source anchors and fingerprints.
- [Mac verification summary](../day-31-course-minimum/evidence/mac-publication-check.json): the actual acceptance scope.
- One real Ollama chat: 1109 input / 396 output tokens, 47.67 s; no retries or unknown inference attempts. One observation, not a benchmark. Six metadata HTTP events are not additional generations.
- Local placement checks: 17/17 PASS, including actual offline `entry.py publish` over a separate copy of retained Mac data. Subsequent Mac delivery verification also passed. These checks are not a fresh full runtime regression.

## Limitations

Isolation uses application capabilities in trusted code, **not an OS sandbox**. Workspace, role, schema, deadline, call-budget, path and content guards remain. Synthetic model transport is labelled as a fixture; fixture human approvals do not replace the actual user's decision.

Full multi-task Chain, arbitrary new contexts, a general human-review workflow, EN-3 claim decomposition, final held-out evaluation, repeatability/resource studies and expanded corpus44/54 calibration remain in the [backlog](BACKLOG_AFTER_COURSE.ru.md). Historical known22 results are not attributed to the current producer. Old `CHANGES_V*`, `RESEARCH_MAC_V*` and versioned shell runners are development history, not the current run instructions.
