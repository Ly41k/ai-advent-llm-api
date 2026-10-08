# Day 29 — V7 independent quality checks

The model selects evidence; the application renders the procedure. Manual semantic review is required.

| Profile | Observations | Blocked | Ready for review |
|---|---:|---:|---:|
| baseline | 15 | 12 | 3 |
| focused-v3-q4 | 15 | 3 | 12 |

- baseline / base-06 / trial 1: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e4-q1", "fragments": ["agent.py", "get_github_repo"]}]

- baseline / base-06 / trial 2: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e4-q1", "fragments": ["agent.py", "get_github_repo"]}]

- baseline / base-06 / trial 3: [{"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e4-q1", "fragments": ["agent.py", "get_github_repo"]}]

- baseline / base-07 / trial 1: [{"kind": "unsupported_technical_fragment", "slot": "c4", "quote_id": "e2-q6", "fragments": ["GITHUB_TOKEN", "api.github.com"]}]

- baseline / base-07 / trial 2: [{"kind": "unsupported_technical_fragment", "slot": "c4", "quote_id": "e2-q6", "fragments": ["GITHUB_TOKEN", "api.github.com"]}]

- baseline / base-07 / trial 3: [{"kind": "unsupported_technical_fragment", "slot": "c4", "quote_id": "e2-q6", "fragments": ["GITHUB_TOKEN", "api.github.com"]}]

- baseline / base-08 / trial 1: [{"kind": "unsupported_technical_fragment", "slot": "c2", "quote_id": "e2-q1", "fragments": ["search_repository(owner, repo)", "summarize_repository(repository)"]}, {"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e2-q2", "fragments": ["save_report(summary)"]}]

- baseline / base-08 / trial 2: [{"kind": "unsupported_technical_fragment", "slot": "c2", "quote_id": "e2-q1", "fragments": ["search_repository(owner, repo)", "summarize_repository(repository)"]}, {"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e2-q2", "fragments": ["save_report(summary)"]}]

- baseline / base-08 / trial 3: [{"kind": "unsupported_technical_fragment", "slot": "c2", "quote_id": "e2-q1", "fragments": ["search_repository(owner, repo)", "summarize_repository(repository)"]}, {"kind": "unsupported_technical_fragment", "slot": "c3", "quote_id": "e2-q2", "fragments": ["save_report(summary)"]}]

- baseline / base-10 / trial 1: [{"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "process_state"]}, {"kind": "missing_actual_verification_actions", "missing": ["inspect_execution_results", "inspect_successive_results_or_timestamps"]}]

- baseline / base-10 / trial 2: [{"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "process_state"]}, {"kind": "missing_actual_verification_actions", "missing": ["inspect_execution_results", "inspect_successive_results_or_timestamps"]}]

- baseline / base-10 / trial 3: [{"kind": "incomplete_periodic_procedure", "missing": ["execution_result", "process_state"]}, {"kind": "missing_actual_verification_actions", "missing": ["inspect_execution_results", "inspect_successive_results_or_timestamps"]}]

- focused-v3-q4 / base-10 / trial 1: [{"kind": "answer_language_mismatch", "slot": "c1"}, {"kind": "answer_language_mismatch", "slot": "c2"}, {"kind": "answer_language_mismatch", "slot": "c3"}, {"kind": "answer_language_mismatch", "slot": "c4"}, {"kind": "missing_actual_verification_actions", "missing": ["inspect_execution_results", "inspect_successive_results_or_timestamps"]}, {"kind": "installation_or_mutation_in_observation_procedure", "commands": ["sudo systemctl daemon-reload", "sudo systemctl enable --now bublik-day18"]}]

- focused-v3-q4 / base-10 / trial 2: [{"kind": "answer_language_mismatch", "slot": "c1"}, {"kind": "answer_language_mismatch", "slot": "c2"}, {"kind": "answer_language_mismatch", "slot": "c3"}, {"kind": "answer_language_mismatch", "slot": "c4"}, {"kind": "missing_actual_verification_actions", "missing": ["inspect_execution_results", "inspect_successive_results_or_timestamps"]}, {"kind": "installation_or_mutation_in_observation_procedure", "commands": ["sudo systemctl daemon-reload", "sudo systemctl enable --now bublik-day18"]}]

- focused-v3-q4 / base-10 / trial 3: [{"kind": "answer_language_mismatch", "slot": "c1"}, {"kind": "answer_language_mismatch", "slot": "c2"}, {"kind": "answer_language_mismatch", "slot": "c3"}, {"kind": "answer_language_mismatch", "slot": "c4"}, {"kind": "missing_actual_verification_actions", "missing": ["inspect_execution_results", "inspect_successive_results_or_timestamps"]}, {"kind": "installation_or_mutation_in_observation_procedure", "commands": ["sudo systemctl daemon-reload", "sudo systemctl enable --now bublik-day18"]}]
