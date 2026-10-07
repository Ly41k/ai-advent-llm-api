# OpenAI V12 — Small cloud experiment results

Reviewed 2026-10-07. Run ID: 191a3eb0-90f7-4d6f-874e-c5e931e88b6e. gpt-4.1-mini-2025-04-14; three questions × three trials, cloud-only, one call per observation, 1000 output-token limit and no rate retries. Embedding/retrieval remained local; local generation and Groq were not invoked.

Nine HTTP attempts produced nine complete, contract-valid answers with no API errors. Heuristic quality passed 5/9: invariants 0/3, VPS 2/3, conversation isolation 3/3. Strict verifier fails the quality checks; internal consistency passes.

Manual review: invariants answers describe postflight but do not clearly explain preflight as a separate step before generation. Some generic request-checking information exists; the answers are incomplete rather than entirely false. VPS trial 2 cites English README only while its original rubric expects README.ru.md, and incorrectly says GITHUB_TOKEN is needed only for public repositories; the source says it is optional for public repositories. The isolation answers correctly explain SQLite, tables, restoration and conversation_id using exact evidence, with test information explicitly labeled as a test. Original rubrics and raw reports remain unchanged.

Generation wall median: 2.935 s; p95: 3.996 s. Pipeline median: 3.016 s. Exact stability: 0/3 complete groups; wording/citations vary. Invariants trials 2 and 3 match, but the whole group does not. Isolation mechanisms remain consistent by manual review; this is not a new automated semantic-stability score. Temperature zero and a pinned model do not guarantee identical text.

This subset is not a fresh paired local/cloud benchmark. Earlier local V11 timing covers one question and two stages, while this OpenAI measurement covers three questions and one stage. The historical paired V2 evaluation remains separate in FINAL_REPORT.md.

Saved usage totals: 38,769 input and 1,986 output tokens. At gpt-4.1-mini rates of $0.40/$1.60 per million input/output tokens, estimated cost without cache discounts is $0.0186852 (about 1.87 cents). Pricing checked 2026-10-07: https://developers.openai.com/api/docs/models/gpt-4.1-mini . This is a usage-based estimate, not a billing receipt; cached-input details are not retained. Actual billing: https://platform.openai.com/usage .

Local RAG and quality/speed/stability evaluation are demonstrated. Groq limitations and OpenAI quality failures are part of the cloud comparison. No additional paid runs or prompt changes are required for this assignment. The passed isolation case will not be rerun; other defects are documented without retroactively changing scores. A nine-request success does not guarantee general API reliability.

Original report: reports/check/openai-small-v12.json. Independent audit: reports/verified/openai-small-v12-audit.json. This update changes documentation/audit only; V12 code with 63 passing offline tests remains unchanged. No root/other-day/index edits or reindex. All 13 original V2–V12 reports are preserved byte-for-byte. Historical pending notes describe earlier checkpoints; OpenAI live results are now available.
