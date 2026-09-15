**English** | [Русский](README.ru.md)

# Day 11 — Explicit Agent Memory Model

On Day 11, Bublik separates memory into three layers with distinct scope, storage, and prompt representation. The destination is selected explicitly instead of being guessed by an automatic classifier.

## Memory layers

| Layer | Data | Scope | Storage | Prompt representation |
|---|---|---|---|---|
| Short-term | Recent messages | Current conversation | `short_term_messages` | Last 6 messages with original roles |
| Working | `TaskContext` and task notes | Current conversation | `working_memory`, `working_notes` | Dedicated current-task system block |
| Long-term | Profile, decisions, knowledge | All conversations | `config/profile.json`, `long_term_memory` | Dedicated system blocks before working memory |

The complete dialogue remains in SQLite, while only the six most recent completed messages are sent to the model. Pending and failed requests are excluded.

Explicit storage APIs and CLI commands make the destination visible:

```text
/remember working "cargo_limit" "100 units"
/remember long decision "engine" "ion engine"
/remember long knowledge "K-41" "water was detected on the planet"
```

Working data is isolated to the selected conversation. Long-term decisions and knowledge are available in newly created conversations.

## Task state machine

Working memory stores the task, state, plan, completed steps, current step, and validation result. `total` is derived from `len(plan)`.

Allowed transitions:

```text
planning -> execution
execution -> validation | planning
validation -> done | execution
done -> no transitions
```

Python code controls transitions. Execution requires an approved non-empty plan, validation requires all steps to be completed, and done requires a successful validation result.

Example:

```text
/task create "Build navigation module"
/task plan "Collect requirements" "Write code" "Run tests"
/task transition execution
/task complete
/task complete
/task complete
/task transition validation
/task check pass "Tests passed and plan matched"
/task transition done
```

## Prompt and invariant validation

Every request is assembled in this order:

```text
profile + invariants
long-term decisions and knowledge
working TaskContext and notes
last 6 short-term messages
current user request
```

`/context` prints the exact prompt without calling Groq. Stack and architecture invariants are injected into the system prompt. Deterministic rules with `forbidden_patterns` validate the model response. A rejected response is marked failed and excluded from completed short-term memory.

Architecture compliance and test results cannot be proven from response text alone, so they are recorded separately with `/task check` during validation.

## Run

```bash
pip install -r requirements.txt
python day-11-memory-layers/main.py
```

Useful commands:

- `/memory short|working|long` — inspect a memory layer;
- `/context` — inspect the assembled prompt;
- `/history` — show the complete conversation log;
- `/remember working KEY VALUE` — save task-local data;
- `/remember long decision|knowledge KEY VALUE` — save durable data;
- `/task ...` — manage task state;
- `/dialogs` — switch conversations;
- `/exit` — quit.

Quote values that contain spaces.

## Verification

Local tests do not call Groq:

```bash
python -m unittest discover -s day-11-memory-layers -p "test_*.py" -v
```

They verify memory isolation and visibility, prompt composition, guarded state transitions, memory influence on the request, and response rejection when an invariant is violated.

To compare two real answers—one without working/long-term memory and one with both layers populated—run:

```bash
python day-11-memory-layers/experiment.py
```

## Result

Bublik now has an explicit memory model. Dialogue history, current task state, and durable knowledge no longer mix; each layer can be inspected, the storage target is explicit, task states cannot be skipped, and responses are checked against formalized invariants.
