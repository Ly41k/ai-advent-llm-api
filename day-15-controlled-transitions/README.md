# Day 15 — Controlled Task-State Transitions

This standalone lesson extends Day 13's task state machine and Day 14's invariant policy. The lifecycle graph is now an explicit contract visible to the agent, prompt, CLI, and tests.

## Lifecycle contract

States: `planning`, `execution`, `validation`, `done`.

| Current | Allowed transitions | Guard |
|---|---|---|
| planning | execution | A non-empty, explicitly approved plan is required |
| execution | validation, planning | Validation requires every step; planning is controlled re-planning |
| validation | done, execution | `done` requires PASS; failed validation returns to execution |
| done | none | Terminal state |

Pause is orthogonal to the stage. While paused, no transition or progress mutation is accepted; only explicit resume is allowed. State is persisted in SQLite.

## Day 15 additions

- `TaskState` is the finite set of valid states.
- `ALLOWED_TRANSITIONS` is the single transition graph.
- `allowed_targets()` applies guards and exposes only transitions available right now.
- Guards reject skipped stages and explain the refusal with current state, allowed transitions, and expected action.
- `/task approve` explicitly approves a plan; editing the plan revokes approval.
- The model prompt receives the same policy and is told never to skip stages.
- Semantic postflight validates the generated answer against the current stage and `expected_action`.
- Implementation generated during `planning` is discarded and replaced with a deterministic refusal.
- `/task status` displays allowed transitions.
- Day 14 invariant checks remain active.

## Run and test

```bash
cd day-15-controlled-transitions
cp .env.example .env
python3 -m pip install -r requirements.txt
python3 main.py
python3 -m unittest discover -s . -p 'test_*.py' -q
```

Main flow: `/task create`, `/task plan`, `/task approve`, `/task transition execution`, `/task complete`, `/task transition validation`, `/task check pass`, `/task transition done`.

35 tests cover invalid jumps, guard-aware status output, explicit plan approval, premature implementation blocking, pause/resume continuation, restart persistence, prompt policy injection, and Day 14 compatibility. The implementation uses Python 3.13, SQLite, and Groq; Node.js and PostgreSQL are not required.
