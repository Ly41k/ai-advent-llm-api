**English** | [Русский](README.ru.md)

# Day 10 — Context Management Strategies Without Summary

Day 10 gives Bublik three interchangeable ways to build a prompt from the same persistent SQLite history: Sliding Window, Sticky Facts, and Branching. No cumulative summary is used.

## Strategies

### Sliding Window

Only the latest 6 completed messages are sent to the model. The complete journal remains in SQLite, but older details leave the prompt.

### Sticky Facts / Key-Value Memory

After every user message, a separate GPT-OSS 20B request updates a JSON object containing stable goals, constraints, preferences, decisions, and agreements. The main request receives these facts plus the latest 6 messages. Fact-extraction tokens and cost are persisted separately and included in `/stats`.

### Branching

A checkpoint identifies a point in the active branch. Multiple branches can start from that same point. Each branch inherits history through the checkpoint and cannot see later messages from sibling branches. The model receives the complete inherited history of the active branch.

## Run

```bash
pip install -r requirements.txt
python day-10-context-strategies/main.py
```

Main commands:

- `/strategy sliding|facts|branching` — switch strategy;
- `/history` and `/context` — inspect persisted history and the selected prompt context;
- `/facts` — inspect key-value memory;
- `/checkpoint NAME` — save a branch point;
- `/branch create NAME CHECKPOINT` — create a branch;
- `/branch switch NAME` — switch branches;
- `/branches` — list branches and checkpoints;
- `/stats` — show main-request and fact-update cost;
- `/dialogs` and `/exit` — change conversation or stop.

## Reproducible Scenario

The live experiment collects 11 spacecraft requirements and requests a final specification. Sliding Window and Sticky Facts receive the same messages. Branching shares the first 7 requirements, then creates independent `research` and `economy` branches.

```bash
python day-10-context-strategies/experiment.py
```

The script prints each final answer, total tokens, total cost including fact extraction, and both branch results. Evaluate whether early goals and numeric constraints survive and whether sibling-branch decisions stay isolated.

## Comparison

| Criterion | Sliding Window | Sticky Facts | Branching |
|---|---|---|---|
| Long-dialog quality | Falls when early messages leave the window | Usually preserves extracted requirements | High inside the active branch |
| Important-detail stability | Low for old details | High when extraction is correct | High while the branch fits the model window |
| Prompt tokens | Lowest | Low to medium | Grow with branch length |
| Extra API calls | None | One per user message | None |
| User experience | No memory controls | Automatic structured memory | Explicit checkpoint and branch controls |
| Best fit | Short local conversation | Long sequential requirements | Exploring alternatives in parallel |

## Tests

```bash
python -m unittest discover -s day-10-context-strategies -p "test_*.py" -v
```

The tests use no API and verify window size, facts placement, checkpoint inheritance, and sibling-branch isolation.

## Limitations

- fact extraction depends on model quality and adds an API call;
- facts are conversation-wide, so alternative paths should use Branching;
- switching an existing long conversation to Facts does not backfill old messages;
- Branching does not reduce history and can eventually exceed the context window;
- answer quality is evaluated manually rather than with a separate judge model.

## Outcome

Bublik can switch among three context strategies without deleting its full journal, maintain structured facts, create independent branches from one checkpoint, and expose the real token and cost trade-offs.
