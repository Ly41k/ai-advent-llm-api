# Delivery validation

## Automated integration suite

Command:

```bash
python3 -m unittest discover -s tests -v
```

Result: **28 tests passed**.

These tests use real temporary Git repositories and real Git commit/pre-commit execution. Detekt is a scripted subprocess and Ollama is a scripted loopback HTTP server. They cover allow/block, accurate source locations, partial staging in both directions, deleted files, configuration changes/deletion, unstaged configuration, missing baseline, symlink inputs, invalid XML, foreign hooks, invalid Ollama URL, remote models, empty/incomplete/wrong-model answers and concurrent index mutation. They validate software behavior, not live model quality.

## Real Detekt CLI smoke check

Runtime: OpenJDK 17; Detekt CLI **1.23.8**.

The actual production `check` path ran with `java -jar detekt-cli-1.23.8-all.jar`, the bundled demo configuration and a scripted local Ollama HTTP endpoint:

| Input | Detekt result | Revik status | Revik exit |
|---|---|---|---|
| `Bad.kt` copied to staged `Demo.kt` | `detekt.MagicNumber`, line 4, column 18 | blocked | 1 |
| `Good.kt` copied to staged `Demo.kt` | no findings | allowed | 0 |

This checks the real CLI arguments and XML report parsing. It does **not** represent real Qwen inference. Detekt/JDK binaries are not bundled in the archive.

## Remaining live validation on the user's machine

Run `live_demo.py` against installed Detekt and Ollama. A successful live report must show `all_passed=true`, local LLM answers in both scenarios and actual bad/clean commit exit codes. Repeat with internet disabled after downloading dependencies to demonstrate offline operation.

The user's KMP project, Gradle Detekt version, full YAML contents, custom plugins and per-module baselines were not provided. Their exact compatibility must be checked when connecting the agent. Type-resolution rules are outside this version's AST-only scope.

## Fix after first delivery

HTML rendering now handles `llm=null`. Added real pre-commit regression tests for missing configuration, no staged Kotlin changes and optional LLM failure. All three save fresh reports and permit the expected commit.

## Language and tone update

Five additional tests verify invalid values, CLI overrides, English skip/report output, a real English pre-commit hook, and all six language/tone combinations for both allowed and blocked Detekt results. Every combination reaches the scripted local HTTP model prompt with the expected instructions and preserves the deterministic gate. This does not establish the stylistic quality or language compliance of a live Qwen answer.
