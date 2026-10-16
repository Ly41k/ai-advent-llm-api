# Day 31 — Bublik Developer Assistant

**Course Minimum — Accepted.** This developer assistant combines Project RAG, read-only Git through a real MCP server, delegated tasks and local Qwen inference. Acceptance covers the configuration below. Extended Research Stage7 remains **paused/incomplete**; The user has recorded the video. File preparation does not perform commit/push.

## Verified scope

| Component | Actual boundary |
|---|---|
| Base application | App0.7.29; installed main.py retained |
| Model publication | Separate application copy with Publication Gate v104-r2; Course Minimum r3 launcher |
| Retrieval | Existing FTS54: 54 documents/510 chunks; frozen RU1 context and existing v103 selector/producer |
| Production state | Separate production44: 44 documents/405 chunks, not replaced by research54 |
| Model | Local Qwen2.5:14b Q4_K_M through Ollama; temperature0, seed31, context8192, output1024 |
| Accepted case | RU1 / Multi Documentation, exactly one real model call; not two independent LLM contexts |
| Publication | Runtime validation, immutable claim/selected-anchor binding and explicit human review of this result |

RU1 explains pending/completed/failed and history restoration. The user approved both claims and accepted an omitted broader protective explanation as non-blocking for this educational scope. This is not a general model-quality acceptance.

## Architecture

| Role | Responsibility |
|---|---|
| Main | Deterministic routing, budgets, task dispatch, merge/final validation; no separate Main model call in the accepted case |
| Documentation | Real owned-worker FTS retrieval, followed by a separate bounded local model task |
| Git | Real MCP stdio branch/status/files/diff; no commit/push or arbitrary shell |
| Verification | Owned-worker source/provenance/schema verification; not semantic human review |

`agents demo` delegates Documentation and Git, then Verification checks their results and Main merges them. The accepted RU1 live path performs fresh Documentation/Verification acquisition and passes its frozen context snapshot to one Documentation Qwen worker. Snapshot replay is not a full dependent model Chain. See [architecture](ARCHITECTURE.ru.md).

## Setup: preserve the prepared environment

Use Mac/Python3.13+, Git and the existing venv with locked dependencies. All commands start at the repository root. If the venv already works, do not reinstall it. Only when .venv does not exist:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r day-31-developer-assistant/requirements.lock
```

Required retained inputs: unchanged source/Git/corpus pins; `/tmp/day31-stage7-v099-work/native-preflight.json`; `/tmp/day31-independent-v098-r1-work/preparation-bundle.json`; existing production44/research54 states; and the course r3 work containing the live result. This reproduces prepared state, **not a standalone clean installer**. Missing state requires restoring the original backup; no silent rebuild/fallback is provided.

The unchanged runner/producer/adapter sources now live in the sibling `day-31-course-minimum/` directory. Do not put additional Python files inside the base application: its binding requires exactly 60 files. Main, prompts and retrieval remain unchanged. Historical work/state/receipts remain external; do not remove the existing temporary directories before a separate backup.

```bash
source .venv/bin/activate
python --version

export DAY31_COURSE="$PWD/day-31-course-minimum"
day31_entry="$DAY31_COURSE/day31-course-minimum-r3/entry.py"
day31_v103="$DAY31_COURSE/day31-source-anchor-v103-r1"
day31_v104="$DAY31_COURSE/day31-anchor-persistence-v104-r1"
day31_overlay=/private/tmp/day31-course-minimum-r3-work/isolated-app
day31_state54=/private/tmp/day31-independent-v098-r1-work/isolated-fts-state

python "$DAY31_COURSE/verify_delivery.py" --root "$PWD"
```

Source placement does not restore the historical state/receipts. Keep the pinned Git HEAD/branch and documents. Do not rebuild indices for this scenario. Day30 must be off; the dedicated Ollama session must remain confirmed with a matching process epoch. Session status checks OS witnesses and the Day30 loopback8000 TCP handshake; it does not send model HTTP requests.

A new commit changes Git HEAD. The frozen preflight belongs to the old HEAD and may stop afterward; do not rewrite pins to force PASS. Historical acceptance belongs to the saved result. `verify_delivery.py` checks delivery integrity, not fresh E2E acceptance; `publish` verifies the retained bindings without generation.

## Preflight: no Qwen

```bash
python "$day31_entry" preflight --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"
```

Expected: preflight_passed, tests_run32, qwen_calls0 and embedding_calls0. In the accepted existing work, the receipt is verified/reused;32 is not evidence of a newly executed suite. On failure, stop and preserve the bundle. Do not rebuild/restart/delete reservations to obtain PASS.

## Real tools without generation

Serialize the same frozen54 source list into the existing CLI manifest format, outside the repository. No sources, indices or producer policy are changed:

```bash
export DAY31_DEMO_DIR=$(mktemp -d /tmp/day31-demo.XXXXXX)
python - <<'PY'
import json, os
from pathlib import Path
frozen = json.loads((Path(os.environ['DAY31_COURSE']) / 'day31-source-anchor-v103-r1/source-freeze.json').read_text())
rows = frozen['source_manifest']
assert len(rows) == 54
selection = {'schema_version': 1, 'sources': [
    {'path': row['source'], 'kind': row['kind']} for row in rows
]}
path = Path(os.environ['DAY31_DEMO_DIR']) / 'sources54.json'
with path.open('x', encoding='utf-8') as stream:
    json.dump(selection, stream, ensure_ascii=False, indent=2)
print(path)
PY
day31_manifest="$DAY31_DEMO_DIR/sources54.json"
```

```bash
python "$day31_overlay/main.py" --version
python "$day31_overlay/main.py" --root "$PWD" git branch | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" git status | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" git diff --scope unstaged | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" index verify | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" search 'pending completed failed' --mode fts --final-k 3 --source day-07-context-persistence/README.ru.md | python -m json.tool --no-ensure-ascii
python "$day31_overlay/main.py" --root "$PWD" --state-dir "$day31_state54" --manifest "$day31_manifest" agents demo --question 'Чем отличаются pending, completed и failed?' | python -m json.tool --no-ensure-ascii
```

`agents demo` uses real FTS/MCP/workers and **zero LLM calls**. Its generic retrieval output is not presented as the identical frozen v103 selection used by Qwen. An empty diff is valid; no repository edits are needed for recording. JSON tool displays readable Unicode while preserving JSON control-character escaping.

## The model run and publication

Executed order: preflight → live → offline audit → explicit human review → publish. The historical live command was:

```bash
python "$day31_entry" live --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"
```

**Do not run it for Stage8.** It was already executed once; the reservation in the current work prevents replay. The launcher accepts only frozen RU1/Multi with cap1, fixed context/schema/options and no model retry/cloud fallback. Installed main.py ask is not a substitute for this verified publication route.

The actual human review has now been saved and verified on Mac: both claims supported, answer_accepted=true; review SHA `7ed6948e516e35d077888b5e8ee34b4c3e24590a6d1011ffc4cf41ecb6674174`. To demonstrate publication again without generation:

```bash
python "$day31_entry" publish --root "$PWD" --v103 "$day31_v103" --v104 "$day31_v104"   --review "$DAY31_COURSE/evidence/human-review.json" --reviewer-id yuriy   | python -m json.tool --no-ensure-ascii
```

Publish reads the unchanged audit and the same explicitly approved decision. Claims, anchors and result bindings must match. Original withheld/raw records remain intact; derived reviewed/public records are separate. Repeating publish is idempotent for the review and creates a new numbered export, not another model call.

Without explicit human approval: needs_review and answer_accepted=false. Unsupported claims/runtime refusals cannot be published. Identifier checks and exact quote matching alone do not establish semantic support.

## Evidence

- Mac r3 preflight:32/32 tests on Python3.13.3; real MCP/delegation and an empty-evidence unknown response with zero model attempts.
- One real RU1 Ollama call:1109 input/396 output tokens,47.67s chat; no retries or uncertain attempts. One observation, not a benchmark.
- Two claims/seven semantic parts audited; current immutable bindings and the broader completeness limitation explicitly approved by the user.
- Mac publish bundle:79 report digests verified; all76 previous live reports unchanged; current human review and positive publication match.
- Six metadata HTTP events around the single chat are not six additional generations. Review/publication/Stage8 added zero Qwen calls.

Unit-test transport and human approvals were synthetic fixtures. This accepted model response and the final user's approval are real. Full Chain, arbitrary contexts, multiple independent LLM contexts and final held-out quality remain unproven.

## Limits and submission

This is application capability isolation with trusted code, not an OS sandbox. Workspace/role/schema/budget/path guards remain; secret/private database/symlink/untracked content is excluded and diff content needs explicit paths. Native diagnostic audits are not public answers.

Research Stage7 stays **incomplete**. EN3 anchors/claim decomposition, broad Single/Multi comparison, full Chain/human workflow, held-out, stability/resource studies and corpus44/54 calibration are retained in [BACKLOG_AFTER_COURSE.ru.md](BACKLOG_AFTER_COURSE.ru.md). Historical known22 quality is not attributed to the current producer.

The [terminal video scenario](CONSOLE_VIDEO.ru.md) combines fresh real tools, publication of the saved actual answer and explicitly labelled historical model evidence, without another generation. Review the staged diff and file inventory before commit/push. The video file/link is not included in this package.
