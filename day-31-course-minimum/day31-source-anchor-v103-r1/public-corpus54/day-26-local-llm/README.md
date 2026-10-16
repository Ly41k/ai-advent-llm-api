**English** | [Русский](README.ru.md)

# Day 26 — local LLM and comparison with a cloud LLM

Bublik uses two providers through one generation interface:

- **local:** downloaded `qwen2.5:7b` served by Ollama on this computer;
- **cloud:** `openai/gpt-oss-20b` through Groq, as in the early course lessons.

Use `--local-model qwen2.5:14b`, `llama3.2`, or another installed chat model if preferred. This lesson is standalone: it does not require the RAG index, embeddings, MCP, or Day 25 code.

## Experience from earlier lessons

| Lessons | Application here |
|---|---|
| 1–2 | System/user messages, HTTP API, explicit response formats |
| 4–5 and 8 | Common temperature, request latency, actual token usage |
| 21–23 | Local Ollama and explicit context |
| 24 | Application validation of structured results and exact quotations |
| 25 | Separate error/result states and saved JSON for review |

These are reused approaches. The third example receives a bundled README excerpt directly; it does not perform retrieval or run the Day 24 coverage auditor.

## v1.3 profile: model plus calculator

For `calculation`, the application calls `calculate_energy` before generation. Python computes cycle count, total expenditure, and remaining energy using integer arithmetic; the real tool result is passed to the model for JSON formatting. The report records the tool name, inputs, and result in `source`. Both models receive identical context.

This applies a principle from the MCP lessons: a tool performs exact arithmetic. MCP is not connected here; the application selects and calls the tool beforehand, then includes its result in the user message. It is **not a test of unaided model arithmetic**. Generated JSON and values are still validated, and incorrect output remains FAIL. No model-generated Python is executed.

Keep original v1.1/v1.2 reports separately: Qwen made an arithmetic error in those runs. v1.3 is a different assisted profile and does not replace those observations. 38 offline tests passed on Python 3.12; real v1.3 inference on the Mac is also supported by the author-supplied report summarized below.

## Quick start on macOS

Run from the repository root or the extracted delivery directory. Python 3.13 is the project target; this module and its tests have also been checked with Python 3.12.

```bash
source .venv/bin/activate
# If necessary: python3.13 -m venv .venv
# Then: source .venv/bin/activate

# Skip installation if Ollama is already installed.
brew install --cask ollama
open -a Ollama
ollama --version
ollama pull qwen2.5:7b
ollama list

ollama run qwen2.5:7b "What is 2 + 2? Reply with one number."

# Offline tests: no real model or API key required.
python day-26-local-llm/test_day26.py -v

# Verify API/model availability, without generation.
python day-26-local-llm/main.py doctor

# Three real local requests.
python day-26-local-llm/main.py demo --provider local \
  --output day-26-local-llm/reports/check/local.json
```

If the desktop app is not running, use `ollama serve` in another terminal. Do not start a second server if the app already serves port 11434. If the CLI is missing after installation, open a new terminal and check the CLI supplied by the Ollama application.

Reuse an installed model:

```bash
python day-26-local-llm/main.py demo --local-model qwen2.5:14b \
  --output day-26-local-llm/reports/check/local-14b.json
```

## Direct HTTP call

```bash
curl --fail-with-body http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5:7b","messages":[{"role":"user","content":"What is 2 + 2? Reply with one number."}],"stream":false,"options":{"temperature":0,"num_predict":128}}'

curl --fail-with-body http://127.0.0.1:11434/api/ps
ollama ps
```

The Python adapter accepts loopback HTTP URLs only, rejects cloud tags and remote models identified by `/api/show`, and records `/api/ps` after generation. For an additional practical offline demonstration, download the model first, disconnect the internet, and repeat the local demo. Reconnect before running cloud comparison. A loopback address alone cannot rule out a custom proxy; the lesson assumes a normal local Ollama installation.

## Cloud requests and comparison

Reuse `GROQ_API_KEY` from the environment or the existing repository-root `.env`. Only `.env` loading needs `python-dotenv`, already included in the course's root requirements:

```bash
python -m pip install -r day-26-local-llm/requirements.txt
# Reuse root .env if it already contains GROQ_API_KEY.
# Otherwise copy .env.example to .env and fill in the key using an editor.

python day-26-local-llm/main.py doctor --provider cloud
python day-26-local-llm/main.py demo --provider cloud \
  --output day-26-local-llm/reports/check/cloud.json

# Same three prompts in both providers: six generation requests.
python day-26-local-llm/main.py compare \
  --output day-26-local-llm/reports/check/compare.json
```

Cloud commands send prompts to Groq and consume API quota. Local mode does not require a key and never falls back to cloud. Comparison runs providers sequentially and preserves failures alongside successful results. There are no automatic API retries.

## Three difficulty levels

The built-in prompts are in Russian, consistent with Bublik's earlier lessons.

| ID | Difficulty | Task | Application check |
|---|---|---|---|
| `simple` | Simple | 2 + 2, reply with one number | Exactly `4` |
| `calculation` | Medium | Python calculator: 3600 energy, 1200 activation, 400 per cycle | Integer JSON fields: `cycles=6`, `total_cost=3600`, `remaining=0` |
| `grounded_json` | Complex | Extract Day 18 worker facts and a verbatim quotation | Five correct fields, exact metrics/channels and quotation |

```bash
python day-26-local-llm/main.py examples
```

`fixtures/day18-context.json` contains lines 5–17 of `day-18-scheduled-mcp/README.md` at commit `3db748323dadf8e863d0106ddec5b804ce66c953`. This is a versioned source excerpt, not fresh retrieval. A test checks it against the sibling Day 18 file when available. Updating the current README does not automatically update the fixture.

Each request uses only the common system message and one user message. Earlier answers never enter later examples. Comparison reports preserve input SHA-256 hashes so equal prompts can be checked.

## CLI and settings

Place options **after the subcommand**:

```bash
python day-26-local-llm/main.py ask "Explain local versus cloud LLMs in three sentences." --provider local
python day-26-local-llm/main.py ask "Explain local versus cloud LLMs in three sentences." --provider cloud
python day-26-local-llm/main.py ask "What is 12 × 13?" --provider both --output day-26-local-llm/reports/check/custom.json

python day-26-local-llm/main.py compare --local-model qwen2.5:14b \
  --cloud-model openai/gpt-oss-20b --timeout 300 --max-tokens 4096
```

| Option | Default | Purpose |
|---|---|---|
| `--provider` | `local` | local/cloud/both; compare always uses both |
| `--local-model` | `qwen2.5:7b` | Downloaded Ollama model |
| `--cloud-model` | `openai/gpt-oss-20b` | Available Groq chat model |
| `--url` | `http://127.0.0.1:11434` | Loopback Ollama API |
| `--temperature` | `0` | Sent to both providers |
| `--max-tokens` | `2048` | Ollama num_predict; Groq max_completion_tokens |
| `--num-ctx` | `8192` | Local context window |
| `--timeout` | `180` | Seconds per HTTP request |
| `--output` | Unset | JSON + Markdown for demo/compare/ask; JSON only for doctor |

`OLLAMA_MODEL` and `GROQ_MODEL` may be set in the process environment; CLI options take priority. `.env` is loaded only to obtain the cloud key. GPT-OSS on Groq uses `reasoning_effort=low`, which is not an identical reasoning mode to Qwen. Equal numerical token limits do not imply equal visible output lengths.

## Results and interpretation

Reports preserve answers, HTTP latency, provider token usage, finish reason, validation, and source metadata. Local results additionally contain load time, generation time, decode tokens/s, and running-model evidence. API keys and Authorization headers are not written to reports.

- `status=ok`: nonempty text and a normal `stop` completion;
- `status=incomplete`: a response that did not finish normally, such as a token-limit `length` stop;
- `status=error`: configuration, HTTP, or malformed-response error;
- `check.passed`: correctness for the selected example;
- `local_launch_verified`: at least one complete local answer and the model visible in `/api/ps`;
- `day26_local_three_requests_verified`: all three distinct built-in local requests completed and the model is loaded;
- `all_checks_passed`: every answer check passed.

A working model may produce incorrect JSON: inference verification and answer quality are deliberately separate. Custom `ask` checks completion only and requires manual content review. Exit 0 means checks succeeded; 1 means a failed check, provider error, incomplete generation, or unverified local loading; 2 means invalid CLI arguments.

This compares **models and their environments**. HTTP latency includes local loading and cloud network/processing overhead. Tokenizers differ; local tokens/s uses `eval_duration`, not total HTTP latency. Missing metrics are `null`. Local compute cost is not assumed to be zero or estimated automatically. Run again separately to observe an already loaded model. Three prompts do not establish a general model ranking or arbitrary-answer reliability.

## Assignment demonstration

For an installed `qwen2.5:14b`:

```bash
ollama --version
ollama list
python day-26-local-llm/main.py compare --local-model qwen2.5:14b \
  --output day-26-local-llm/reports/video/compare-video.json
ollama ps
```

`compare` sends three local and three cloud prompts. The console prints answers, PASS/FAIL, and the summary; JSON preserves full prompts, sources, and metrics. Explain that the middle example uses a Python calculation. To record only the required local part, replace `compare` with `demo --provider local`, retaining the other options; no cloud key is needed.

Show `local_launch_verified=true` and `day26_local_three_requests_verified=true`. `all_checks_passed=true` means all answer checks passed; inference and answer correctness are separate checks. A generation-free `doctor` run alone is insufficient.

`reports/check/` and `reports/video/` are ignored by Git. After manual review, keep selected evidence for a commit:

```bash
mkdir -p day-26-local-llm/reports/live
cp day-26-local-llm/reports/check/compare-v1.3.json day-26-local-llm/reports/live/
cp day-26-local-llm/reports/check/compare-v1.3.md day-26-local-llm/reports/live/
```

Adjust the source path to your actual report. Commit `.env.example`, code, tests, the fixture, READMEs, and selected reports. Keep the real `.env`, `.venv`, and `__pycache__` local, and do not expose credentials in recordings.

## Offline verification

38 offline tests on Python 3.12 exercise actual HTTP calls to a fixture server, both payloads, identical prompts, reports, strict JSON/exact quotes, errors, redirects, timeouts, empty/truncated answers, and absence of hidden cloud fallback.

Offline tests exercise the implementation and do not replace live inference. The author ran the models on the Mac; the following results were checked against the supplied `compare-v1.3.json`, separately from the tests.

## Verified live run — 2026-10-06

The live report records Python **3.13.3**, Ollama **0.34.4**, local **qwen2.5:14b** (14.8B, Q4_K_M), and cloud **openai/gpt-oss-20b** through Groq. Ollama serves `http://127.0.0.1:11434`; Qwen is installed and visible in `/api/ps` after the three generations. The installed and loaded model digests match.

| Example | Local Qwen | Groq | Local / cloud HTTP seconds |
|---|---|---|---|
| Simple answer | PASS: `4` | PASS: `4` | 0.603 / 0.198 |
| Calculator-result JSON | PASS: 6 cycles, 3600 total, 0 remaining | PASS: identical values | 4.077 / 0.486 |
| Context facts and exact quotation | PASS: all five fields | PASS: all five fields | 5.804 / 0.542 |

All six answers finished normally with `stop`. Each local/cloud pair used identical messages and matching input SHA-256 hashes. Summary: `complete_answers=6`, `checks_passed=6`, `all_checks_passed=true`, `local_launch_verified=true`, and `day26_local_three_requests_verified=true`.

| Day 26 requirement | Evidence |
|---|---|
| Install and launch a local model | Downloaded Qwen in Ollama, installed=true, loaded after generation |
| CLI or HTTP access | Three actual `/api/chat` requests; HTTP satisfies the requirement |
| Answer a simple prompt | `2 + 2 → 4` |
| At least three prompts of different difficulty | Short answer, tool-result JSON, context extraction with an exact quote |
| Local LLM responds | Three complete local answers; 3/3 checks passed |

The source is the author-supplied report with run_id `9004bb0a-1f3e-48c1-b87d-81d7eaa8f32e`, created at `2026-10-06T19:26:18.662483+00:00`. Updating this README does not add that JSON to the repository: save the report and sibling Markdown under `reports/live/`.

In v1.1/v1.2, Qwen answered every prompt but made an unaided arithmetic error: 2/3 local checks versus 3/3 cloud checks. v1.3 supplies the actual calculator result, and both models passed 3/3. This changes the workflow; it does not establish that Qwen's unaided arithmetic was fixed. Future runs can produce different answers or provider errors.

Files: `main.py` (CLI), `providers.py` (HTTP adapters), `examples.py` (prompts/checks), `runner.py` (execution/reports), `fixtures/day18-context.json` (source excerpt), and `test_day26.py` (offline tests).

Official references: [Ollama chat](https://docs.ollama.com/api/chat), [running models](https://docs.ollama.com/api/ps), [Groq API](https://console.groq.com/docs/api-reference), [Groq models](https://console.groq.com/docs/models). Parameters checked on 2026-10-06; doctor checks selected-model availability at runtime.
