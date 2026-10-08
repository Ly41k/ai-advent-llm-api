# Day 29 — independent quality checks V6

These are conservative offline checks, not a semantic approval. Original responses are unchanged.

| Profile | Observations | Blocked | Ready for manual review |
|---|---:|---:|---:|
| baseline | 15 | 12 | 3 |
| focused-v3-q4 | 15 | 3 | 12 |

## Detected issues

- baseline / base-06 / trial 1: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e4-q1", "fragments": ["agent.py", "get_github_repo"]}]
- baseline / base-06 / trial 2: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e4-q1", "fragments": ["agent.py", "get_github_repo"]}]
- baseline / base-06 / trial 3: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e4-q1", "fragments": ["agent.py", "get_github_repo"]}]
- baseline / base-07 / trial 1: [{"kind": "unsupported_technical_fragment", "slot": "c4", "quote_id": "e2-q6", "fragments": ["GITHUB_TOKEN", "api.github.com"]}]
- baseline / base-07 / trial 2: [{"kind": "unsupported_technical_fragment", "slot": "c4", "quote_id": "e2-q6", "fragments": ["GITHUB_TOKEN", "api.github.com"]}]
- baseline / base-07 / trial 3: [{"kind": "unsupported_technical_fragment", "slot": "c4", "quote_id": "e2-q6", "fragments": ["GITHUB_TOKEN", "api.github.com"]}]
- baseline / base-08 / trial 1: [{"kind": "unsupported_technical_fragment", "slot": "c2", "quote_id": "e2-q1", "fragments": ["search_repository(owner, repo)", "summarize_repository(repository)"]}, {"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e2-q2", "fragments": ["save_report(summary)"]}]
- baseline / base-08 / trial 2: [{"kind": "unsupported_technical_fragment", "slot": "c2", "quote_id": "e2-q1", "fragments": ["search_repository(owner, repo)", "summarize_repository(repository)"]}, {"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e2-q2", "fragments": ["save_report(summary)"]}]
- baseline / base-08 / trial 3: [{"kind": "unsupported_technical_fragment", "slot": "c2", "quote_id": "e2-q1", "fragments": ["search_repository(owner, repo)", "summarize_repository(repository)"]}, {"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e2-q2", "fragments": ["save_report(summary)"]}]
- baseline / base-10 / trial 1: [{"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "process_state"]}]
- baseline / base-10 / trial 2: [{"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "process_state"]}]
- baseline / base-10 / trial 3: [{"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "process_state"]}]
- focused-v3-q4 / base-10 / trial 1: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e1-q6", "fragments": ["systemctl status bublik-day18"]}, {"kind": "process_status_is_not_execution_proof", "slot": "c3", "quote_id": "e1-q6"}, {"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "recurrence", "process_state"]}]
- focused-v3-q4 / base-10 / trial 2: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e1-q6", "fragments": ["systemctl status bublik-day18"]}, {"kind": "process_status_is_not_execution_proof", "slot": "c3", "quote_id": "e1-q6"}, {"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "recurrence", "process_state"]}]
- focused-v3-q4 / base-10 / trial 3: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e1-q6", "fragments": ["systemctl status bublik-day18"]}, {"kind": "process_status_is_not_execution_proof", "slot": "c3", "quote_id": "e1-q6"}, {"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "recurrence", "process_state"]}]
