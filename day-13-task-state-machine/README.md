**English** | [Русский](README.ru.md)

# Day 13 — Task State Machine

Day 13 turns Bublik's task context into a finite-state machine. The agent persists the task stage, current step, expected action, and pause flag in SQLite, then restores the same state and injects it into every prompt after restart.

## State model

```text
planning → execution → validation → done
               ↑           |
               └── fail ───┘
```

| Field | Purpose |
|---|---|
| `state` | `planning`, `execution`, `validation`, or `done` |
| `step` / `current` | Current plan position and description |
| `expected_action` | The single action expected next |
| `paused` | An orthogonal pause that preserves stage and progress |

`expected_action` is derived from the complete `TaskContext`, so it cannot drift out of sync with the stage. Its values include `define_plan`, `start_execution`, `complete_current_step`, `start_validation`, `record_validation`, `finish_task`, `return_to_execution`, `resume`, and `none`.

The state machine rejects execution without a plan, validation before all steps are complete, completion without successful validation, and any progress while paused. Failed validation returns the last step to execution for rework.

## Pause and restore

Pause is not a fifth task stage. It preserves the current stage, step, plan, and progress. After `/task resume`, execution continues from the exact stored position.

When a dialogue is reopened, the CLI and model prompt receive:

```text
stage
current step
expected action
paused
```

The user can therefore say only “Continue” instead of repeating the task description and plan.

## Run

```bash
pip install -r requirements.txt
python3 day-13-task-state-machine/main.py
```

Task commands:

| Command | Action |
|---|---|
| `/task create DESCRIPTION` | Create a task in planning |
| `/task plan STEP1 STEP2` | Save the plan |
| `/task transition execution\|validation\|done` | Perform an allowed transition |
| `/task complete` | Complete the current step |
| `/task check pass\|fail RESULT` | Record validation |
| `/task pause` | Pause the task |
| `/task resume` | Resume without resetting context |
| `/task status` | Display formal state |
| `/context` | Inspect the prompt and task state |

Quote values that contain spaces.

## Verification

Run all local tests without an API call:

```bash
python3 -m unittest discover -s day-13-task-state-machine -p "test_*.py" -v
```

They cover expected actions, transition guards, pause/resume in every non-terminal stage, persistence across new repository and agent instances, prompt restoration, failed-validation rework, and all retained Day 11–12 memory and personalization behavior.

Manual restart scenario:

```text
/task create "Prepare navigation module"
/task plan "Define API" "Add tests"
/task transition execution
/task complete
/task pause
/exit
```

Restart, reopen the same dialogue, then run:

```text
/task status
/context
/task resume
Continue.
```

The restored state must point to the second step without asking for the task description again.

The Groq-backed experiment automates the same scenario:

```bash
python3 day-13-task-state-machine/experiment.py
```

## Result

Bublik now has a formal, persistent task state. Code controls its stage, current step, and expected action; any unfinished stage can be paused and resumed after restart without repeated explanations.
