# Revik — local Kotlin pre-commit review agent

Revik is a Python CLI application for AI Advent Day 27. It runs Detekt on staged Kotlin files using `detekt/detekt.yml`, asks a downloaded Ollama model to explain the results, prints file locations, writes linked reports, and blocks or permits a Git commit.

Read [the complete Russian setup guide](README.ru.md) for the KMP integration steps, settings, baseline/plugin support and limitations.

No Detekt configuration in the Git index → skip, allow commit. No changed Kotlin files → skip. Detekt findings or execution errors → block. Local LLM is required by default; its explanations never override Detekt's findings. There is no cloud provider or cloud fallback.

The archive contains source code and tests. Install Python 3.10+, Git, a compatible JDK, Detekt CLI matching your project's version, and Ollama with a downloaded Qwen model separately.

From the target project root, after copying this package into `tools/revik-agent` and creating `.revik.json` from the example:

```bash
python3 tools/revik-agent/revik_cli.py doctor
python3 tools/revik-agent/revik_cli.py install
python3 tools/revik-agent/revik_cli.py check
git commit -m "Your message"
```

Offline integration checks:

```bash
python3 -m unittest discover -s tools/revik-agent/tests -v
```

Real Detekt and real local LLM demonstration, from this package directory:

```bash
python3 live_demo.py --detekt-jar /absolute/path/to/detekt-cli.jar \
  --model qwen2.5:14b --output revik-live.json
```

The demo creates a disposable Git repository, blocks a bad commit and permits a corrected commit. It does not edit your working project.

Revik analyzes staged content rather than unstaged working files, including partially staged files. It uses AST-only Detekt analysis without type resolution; keep Gradle/CI for platform-specific rules, resolved-type analysis and compilation. It supports one explicitly configured baseline and local rule plugin jars. It does not infer per-module baselines.

Reports are under `git rev-parse --git-path revik-reports`: `latest.json`, `latest.md`, `latest.html`. Links open working files; line positions may differ from staged versions if unstaged edits are present.

Git hooks are local and can be bypassed with `--no-verify`. Existing hooks are preserved; see the Russian guide for manual chaining. Installation stores an absolute Python interpreter and CLI path, so rerun installation after moving the project or replacing its venv.

See [VALIDATION.md](VALIDATION.md) for the checks actually performed. Real Qwen inference on the user's Mac has not been executed in the delivery environment.

MIT licensed.

## Language and reviewer tone

Add `"language": "en"` (or `"ru"`) and `"tone": "professional"`, `"light_troll"` or `"hard_troll"` to your existing `.revik.json`. Defaults are Russian and professional. Preserve your Detekt command and other settings.

The language switches application messages/report headings and instructs the local model. Original Detekt messages and low-level technical diagnostics remain unchanged. Tone affects model explanations only: light roasting adds at most one joke, hard roasting at most two. Roasting targets code and bugs, never the developer. Model style/language compliance requires live review.

One-off overrides: `python3 revik_cli.py check --language en --tone hard_troll`. Hooks read the persistent JSON settings on every commit. No hook reinstallation is needed. When updating, copy the complete `revik/` directory, including the new `i18n.py`; keep your existing local settings.
