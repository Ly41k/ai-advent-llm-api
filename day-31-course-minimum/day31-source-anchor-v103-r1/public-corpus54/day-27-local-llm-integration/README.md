**English** | [Русский](README.ru.md) | [Project overview](../README.md)

# Day 27. Local LLM Integration — Revik

**Revik** is a Kotlin pre-commit review CLI. It runs real Detekt using the project's configuration, sends the results to a downloaded Qwen model through Ollama, displays explanations and file links, and permits or blocks the Git commit.

This is a standalone application intended for a Kotlin Multiplatform project. It does not use Bublik's RAG index, MCP, or cloud models. Detekt executes static analysis rules; the LLM explains findings and suggests fixes. Free-form model output never overrides findings or the commit decision.

## Assignment outcome

| Requirement | Implementation |
|---|---|
| Integrate a model into an application | Python CLI and Git pre-commit hook |
| Send requests to a local LLM | Ollama `/api/show` and `/api/chat`, downloaded Qwen |
| Receive and display answers | Terminal and JSON/Markdown/HTML reports |
| Work without cloud models | Loopback Ollama only; no API keys or cloud fallback |

The current implementation handles `llm=null` reports, supports Russian/English and three reviewer tones. **28 integration tests pass**. Real Detekt CLI 1.23.8 was also checked with the good/bad examples. Ollama tests use a scripted HTTP server and do not replace live Qwen validation. See [VALIDATION.md](VALIDATION.md).

## Commit flow

```text
Git commit → pre-commit → Git index snapshot → Detekt → local LLM
           → explanation + links + report → exit code → commit or rejection
```

Revik compares the Git index tree with HEAD, selects added/modified `.kt` and `.kts` files, and extracts their staged blobs into a temporary directory. Partially staged files are checked as they will be committed. Deleted Kotlin files are skipped; renamed files are checked under their new names.

The initial commit, or a change to Detekt configuration/configured baseline, triggers analysis of the entire staged Kotlin tree. Before returning, Revik compares the current index tree ID with the original snapshot; an index change blocks the commit. It does not auto-correct working sources, replace the index, or modify the stash.

| Situation | Outcome |
|---|---|
| No `detekt/detekt.yml` in the index | `skipped`, allow commit, no LLM call |
| No selected Kotlin files | `skipped`, allow commit, no LLM call |
| Detekt findings | `blocked`, reject commit |
| Detekt error / missing or invalid fresh XML | `error`, reject commit |
| Clean Detekt and a complete model answer | `allowed`, allow commit |
| Unavailable/incomplete model, `require_llm=true` | `error`, reject commit |
| Same model failure, `require_llm=false` | Keep Detekt's decision and record the LLM error |

Any XML finding blocks the commit, even if Detekt's own issue threshold allowed an exit code of 0. Detekt applies baselines, suppressions and exclusions. CLI exit codes: **0** allow/skip, **1** findings, **2** technical error, **130** interrupted.

## Run in the course repository

Commands in this section run **from the `ai-advent-llm-api` repository root**.

Requirements: macOS/Linux, Git, Python 3.10+ (3.13 is the course target), a compatible JDK, Detekt CLI, running Ollama and a downloaded local model. Revik uses the Python standard library; there are no additional pip dependencies.

```bash
source .venv/bin/activate
python -m unittest discover -s day-27-local-llm-integration/tests -v
```

Download Detekt and the model before the live demonstration. Version 1.23.8 was checked for this lesson's examples; a working project should use a version compatible with its Gradle configuration and rule plugins.

```bash
java -version
mkdir -p day-27-local-llm-integration/.vendor
curl --fail --location \
  https://github.com/detekt/detekt/releases/download/v1.23.8/detekt-cli-1.23.8-all.jar \
  --output day-27-local-llm-integration/.vendor/detekt-cli.jar

# Skip model installation if it is already available.
open -a Ollama
ollama pull qwen2.5:14b

python day-27-local-llm-integration/live_demo.py \
  --detekt-jar day-27-local-llm-integration/.vendor/detekt-cli.jar \
  --model qwen2.5:14b --language en --tone professional \
  --output day-27-local-llm-integration/revik-live.json
```

On Linux, start the local Ollama server instead of `open -a Ollama`. Do not start a second server if the API is already running. To use an installed Detekt CLI, replace `--detekt-jar ...` with `--detekt-bin /absolute/path/to/detekt`.

`live_demo.py` creates a disposable Git repository, copies the configuration from `examples/`, installs a real hook, and tries two commits:

1. `Bad.kt`: local `val factor = 42` → `MagicNumber` finding → LLM explanation → rejected commit.
2. `Good.kt`: `private const val FACTOR = 42` → clean analysis → LLM answer → successful commit.

Both examples are staged as `Demo.kt`. The working KMP project is not changed. On successful completion, JSON records `all_passed=true`, model answers and the expected Git exit codes. This validates application behavior and inference, not the semantic accuracy of recommendations. A technical failure can terminate the demo before its final JSON is saved; inspect console output.

For the recording, show `ollama list`, the demo command, the model answer, a rejected bad commit and a successful corrected commit. Repeat with internet disconnected after downloading dependencies. Do not install a hook in the course repository just to run the demo: the script installs one in its temporary repository.

## Connect to a working KMP project

Copy this lesson into `tools/revik-agent/` **at the target project's root**:

```bash
# From ai-advent-llm-api. Substitute your target project path.
mkdir -p /absolute/path/to/EventConnectMobile/tools/revik-agent
cp -R day-27-local-llm-integration/. /absolute/path/to/EventConnectMobile/tools/revik-agent/
cd /absolute/path/to/EventConnectMobile
```

Target layout:

```text
EventConnectMobile/
  detekt/detekt.yml
  common/
  composeApp/
  tools/revik-agent/
  .revik.json
```

Create a **local** `.revik.json` at the KMP project root. For Detekt on PATH, copy the template:

```bash
cp tools/revik-agent/revik.example.json .revik.json
```

For a standalone JAR, use the following configuration and adjust paths/version to your project:

```json
{
  "language": "en",
  "tone": "professional",
  "detekt_config": "detekt/detekt.yml",
  "detekt_command": ["java", "-jar", "tools/revik-agent/.vendor/detekt-cli.jar"],
  "detekt_plugins": [],
  "baseline": null,
  "build_upon_default_config": false,
  "model": "qwen2.5:14b",
  "ollama_url": "http://127.0.0.1:11434",
  "require_llm": true
}
```

Match `build_upon_default_config` with Gradle's `buildUponDefaultConfig`. Reuse an installed 14B model; change `model` for 7B. If an IDE provides a different PATH, use absolute paths to `java`/`detekt`.

```bash
python3 tools/revik-agent/revik_cli.py doctor
python3 tools/revik-agent/revik_cli.py install

# Stage the configuration and relevant Kotlin changes.
git add detekt/detekt.yml
# Use git add or git add -p for your Kotlin files.
python3 tools/revik-agent/revik_cli.py check
git commit -m "Update transfer state handling"
```

`doctor` displays settings, checks Detekt `--version` and sends a real request to the local model. `check` analyzes the current index. `install` writes a pre-commit hook containing absolute Python/CLI paths; reinstall after moving the project or replacing its venv. `python -m revik check` also works from a directory where the `revik` package is available.

In the working project's root `.gitignore`, add:

```gitignore
/tools/revik-agent/
/.revik.json
/revik-live.json
```

Ignore rules do not untrack existing files. Remove tracking while retaining local files with:

```bash
git rm -r --cached --ignore-unmatch tools/revik-agent
git rm --cached --ignore-unmatch .revik.json revik-live.json
```

In the **course repository**, commit the lesson's sources, documentation, `revik.example.json` and `examples/`. Keep `.vendor/`, local `.revik.json`, venv, Python caches and `revik-live.json` out of commits. The examples are required for the demo, but not for the regular hook.

## Language and reviewer tone

| Setting | Values | Default |
|---|---|---|
| `language` | `ru`, `en` | `ru` |
| `tone` | `professional`, `light_troll`, `hard_troll` | `professional` |

`professional` requests factual explanations and fixes. `light_troll` permits at most one friendly code joke. `hard_troll` permits at most two sharper implementation jokes; fixes remain the main content. “Looks like this bug has joined the team” is a light-tone metaphor, not a stored history of recurring bugs. Roasting targets code, not the developer.

The application translates UI/report headings and instructs the model about answer language/tone. Original Detekt messages and low-level diagnostics remain unchanged. Live model style/language compliance needs manual review and is not established by scripted tests.

```bash
python3 tools/revik-agent/revik_cli.py check --language en --tone professional
python3 tools/revik-agent/revik_cli.py doctor --language ru --tone hard_troll
```

CLI flags override one invocation. For automated commits, edit `.revik.json`; the hook reads it on each run, so reinstallation is unnecessary.

## Reports and settings

Reports are stored under `git rev-parse --git-path revik-reports`: `latest.json`, `latest.md`, `latest.html`. In a regular repository this is `.git/revik-reports/`. Each run replaces the previous report, including skip/error. JSON and Markdown use temporary-file replacement; HTML uses a regular write. Reports are not part of the commit.

Console findings use `/absolute/path/File.kt:line:column`. Markdown/JSON include `file://` and `vscode://` links; HTML includes VS Code links. Click support depends on the terminal/IDE and installed protocol handler.

**Locations refer to staged versions; links open working files.** Unstaged changes may shift line numbers. JSON records the tree ID, language/tone and, on LLM success, the model, answer, messages SHA-256, HTTP chat latency and token counts.

| Additional setting | Default |
|---|---|
| `detekt_timeout`, `llm_timeout` | 180 seconds each |
| `num_ctx` | 8192 |
| `num_predict` | 1500 |
| `max_findings_for_llm` | 12 |
| `snippet_lines` | 3 on either side, up to 300 characters per line |

All findings are retained; a bounded subset with short staged snippets goes to the LLM. A clean run sends only a summary. `.revik.json` comes from the repository working directory; Detekt YAML and baseline come from the index. Unknown setting keys are rejected.

`baseline` names one explicit repository-relative staged XML file. Revik does not automatically discover `detekt/baselines/`. `detekt_plugins` lists installed compatible local rule JARs. With `baseline=null`, existing issues in a changed file can also block the commit.

## Exceptions and analysis scope

For an MVI reducer, suppress only the length/complexity checks on the specific function:

```kotlin
@Suppress("LongMethod", "CyclomaticComplexMethod")
override fun reduce(/* existing parameters */): State {
    // existing state handling
}
```

This is a template: retain your actual parameters/state type. Other rules and methods remain checked. YAML `excludes` for every `*ViewModel.kt` has a wider effect. Stage the updated file after editing.

Revik runs Detekt CLI **without type resolution**: AST analysis does not replace KMP compilation, Android Lint or platform-specific Gradle tasks. Rules requiring resolved types may not execute. Match CLI/config/plugin versions; 1.23.8 was checked, and 2.x compatibility is not claimed.

The entire changed file is analyzed, not only changed lines. Per-module/per-variant multiple baselines are unsupported. External YAML resources such as license templates are not automatically copied. Symlink sources/configuration are rejected; Git submodule contents are not traversed.

The URL is restricted to loopback HTTP; proxies and redirects are disabled. Cloud tags and `remote_host`/`remote_model` are rejected. This assumes a normal local Ollama installation rather than attesting any server listening on loopback.

## Combine or disable hooks

The installer honors `core.hooksPath` and worktrees through `git rev-parse --git-path hooks/pre-commit`. It preserves foreign hooks. Add one invocation to an existing shared hook before it returns success:

```sh
python3 tools/revik-agent/revik_cli.py check || exit $?
```

Bypass pre-commit and commit-msg for one commit:

```bash
git commit --no-verify -m "Commit without pre-commit checks"
```

Temporarily disable a **standalone hook installed by Revik**:

```bash
revik_hook_path="$(git rev-parse --git-path hooks/pre-commit)"
mv "$revik_hook_path" "$revik_hook_path.disabled"
```

Enable it again:

```bash
revik_hook_path="$(git rev-parse --git-path hooks/pre-commit)"
mv "$revik_hook_path.disabled" "$revik_hook_path"
```

For a shared hook, comment out only Revik's command. Git hooks are local, installed per developer and bypassable; retain mandatory project checks in CI.

## Files

| File | Purpose |
|---|---|
| `revik_cli.py`, `revik/__main__.py` | Entry points |
| `revik/app.py` | Git snapshot, Detekt, Ollama, reports and hook installation |
| `revik/i18n.py` | UI translations and reviewer tone instructions |
| `revik.example.json` | Public local-settings template |
| `live_demo.py`, `examples/` | Live demonstration of two Git commits |
| `tests/test_revik.py` | 28 offline integration tests |
| `VALIDATION.md` | Recorded implementation checks |

API references: [Detekt CLI](https://detekt.dev/docs/1.23.8/gettingstarted/cli/), [type resolution](https://detekt.dev/docs/1.23.8/gettingstarted/type-resolution/), [suppressions](https://detekt.dev/docs/1.23.8/introduction/suppressing-rules/), [Git hooks](https://git-scm.com/docs/githooks), [Ollama chat](https://docs.ollama.com/api/chat).
