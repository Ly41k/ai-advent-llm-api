"""Day 34: offline demo, bounded approved live run, and zero-network replay."""
import argparse
import json
from pathlib import Path
import platform
import sys
import unittest
from agent import GOALS, run
from file_tools import FileTools, MODULE, Rejected, digest, exclusive_write, read_bytes, require, strict_json
from llm_adapter import GroqAdapter, MockAdapter, ReplayAdapter

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent


def load_manifest():
    return strict_json((HERE / 'inputs.json').read_bytes())


def load_trace(root, trace_path):
    # Only read trace artifacts from the fixed Day 34 result tree, no external paths.
    require(trace_path.startswith(MODULE + '/results/') and trace_path.endswith('/trace.json'), 'invalid_trace_path')
    # Traces include all actual requests and may exceed individual source-file cap.
    from file_tools import directory, parts
    import os
    components = parts(trace_path)
    fd = directory(root, components[:-1])
    try:
        handle = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(handle, 'rb') as stream:
            import stat
            require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'invalid_trace_type')
            raw = stream.read(2_000_001)
            require(len(raw) <= 2_000_000, 'trace_too_large')
    finally:
        os.close(fd)
    saved = strict_json(raw)
    return saved, raw


def replay(root, trace_path, run_id):
    saved, _ = load_trace(root, trace_path)
    require(saved['schema'] == 1 and saved['status'] == 'completed', 'incomplete_trace')
    tools = FileTools(root, run_id, load_manifest(), read_policy=saved.get('file_read_policy', 'strict-v1'))
    require(saved['inputs_sha256'] == tools.inputs, 'replay_input_mismatch')
    adapter = ReplayAdapter(saved)
    result, acceptance = run(saved['goal'], tools, adapter, expected=saved)
    return result, acceptance


def offline_check(root, run_id):
    report_tools = FileTools(root, run_id, load_manifest())
    suite = unittest.defaultTestLoader.discover(str(HERE / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    fixtures = strict_json((HERE / 'offline_fixtures.json').read_bytes())
    cases = {}
    for scenario in GOALS:
        tools = FileTools(root, run_id + '-' + scenario, load_manifest())
        trace, acceptance = run(GOALS[scenario], tools, MockAdapter(fixtures[scenario]))
        repeated, replay_acceptance = replay(root, tools.output_rel + '/trace.json', run_id + '-' + scenario + '-replay')
        cases[scenario] = {'run': tools.output_rel, 'file_operation': acceptance['file_operation'],
                           'replay_equal': trace['events'] == repeated['events'] and trace['evidence'] == repeated['evidence'],
                           'replay_completed': repeated['status'] == 'completed',
                           'replay_new_posts': replay_acceptance['new_groq_posts']}
    # Snapshot every repository file outside Day 34 in test_offline_both_and_replay.
    passed = (result.wasSuccessful() and result.testsRun > 0 and not result.skipped
              and all(c['file_operation'] == 'PASS' and c['replay_equal'] and c['replay_completed']
                      and c['replay_new_posts'] == 0 for c in cases.values()))
    report = {'status': 'passed' if passed else 'failed', 'offline_technical': 'PASS' if passed else 'FAIL',
              'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'skipped': len(result.skipped), 'environment': {'platform': platform.platform(), 'python': platform.python_version()},
              'scenarios': cases, 'real_generation_calls': 0, 'real_provider_http_posts': 0,
              'real_llm_tool_selection': 'NOT_EVALUATED', 'result_quality': 'PENDING_LIVE_REVIEW',
              'full_e2e': 'NOT_ACCEPTED', 'inputs_sha256': report_tools.inputs,
              'source_sha256': {str(p.relative_to(HERE)): digest(p.read_bytes()) for p in sorted(HERE.rglob('*'))
                                if p.is_file() and p.name != 'offline-linux.json' and 'results' not in p.relative_to(HERE).parts
                                and '__pycache__' not in p.parts}}
    report_tools.save('offline-report.json', report)
    return report, passed


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('offline', 'live', 'openai-live'):
        p = sub.add_parser(name)
        group = p.add_mutually_exclusive_group(required=True)
        group.add_argument('--scenario', choices=GOALS)
        group.add_argument('--goal')
        p.add_argument('--run-id', required=True)
        if name == 'live':
            p.add_argument('--approve-up-to-5-groq-posts', action='store_true')
            p.add_argument('--max-posts', type=int, choices=range(1, 6), default=5)
        if name == 'openai-live':
            p.add_argument('--approve-up-to-4-openai-posts', action='store_true')
            p.add_argument('--max-posts', type=int, choices=range(1, 5), default=4)
    p = sub.add_parser('replay')
    p.add_argument('--trace', required=True)
    p.add_argument('--run-id', required=True)
    p = sub.add_parser('offline-check')
    p.add_argument('--run-id', required=True)
    for name in ('openai-resume-check', 'openai-resume'):
        p = sub.add_parser(name)
        p.add_argument('--trace', required=True)
        p.add_argument('--run-id', required=True)
        if name == 'openai-resume':
            p.add_argument('--approve-up-to-2-openai-posts', action='store_true')
            p.add_argument('--approve-one-extra-openai-post', action='store_true')
    for name in ('openai-repair-check', 'openai-repair'):
        p = sub.add_parser(name)
        p.add_argument('--trace', required=True)
        p.add_argument('--run-id', required=True)
        if name == 'openai-repair':
            p.add_argument('--approve-tenth-openai-post', action='store_true')
    sub.add_parser('plan-live')
    sub.add_parser('plan-openai')
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == 'plan-openai':
            from openai_adapter import (MODEL, MAX_POSTS, TOTAL_POSTS, MAX_REQUEST_BYTES,
                                        MAX_OUTPUT, FRAME_RESERVE, MAX_RESERVED_USD)
            manifest = load_manifest()
            require(all(digest(read_bytes(root, p)) == sha for p, sha in manifest['files'].items()), 'input_hash_mismatch')
            output = {'mode':'preflight_only', 'provider':'openai', 'model':MODEL,
                      'native_function_calling':True, 'strict_tools':True,
                      'max_posts_per_scenario':MAX_POSTS, 'max_posts_total':TOTAL_POSTS,
                      'max_request_utf8_bytes':MAX_REQUEST_BYTES, 'prompt_frame_token_reserve':FRAME_RESERVE,
                      'max_output_tokens_per_post':MAX_OUTPUT, 'max_reserved_list_cost_usd':MAX_RESERVED_USD,
                      'automatic_retries':0, 'fallback_calls':0, 'provider_posts':0,
                      'key_required_for_live_only':'OPENAI_API_KEY', 'account_model_access':'NOT_CHECKED'}
            ok = True
        elif args.command in ('openai-repair-check', 'openai-repair'):
            from quote_repair import repair_run
            live = args.command == 'openai-repair'
            approved = live and args.approve_tenth_openai_post
            require(not live or approved, 'tenth_openai_post_not_approved')
            output, ok = repair_run(root, args.trace, args.run_id, load_manifest(), live=live, approved=approved)
        elif args.command in ('openai-resume-check', 'openai-resume'):
            from resume import resume_run
            live = args.command == 'openai-resume'
            require(not live or args.approve_up_to_2_openai_posts, 'openai_resume_not_approved')
            output, ok = resume_run(root, args.trace, args.run_id, load_manifest(), live=live,
                                    approve_extra_post=live and args.approve_one_extra_openai_post)
        elif args.command == 'plan-live':
            from llm_adapter import MAX_ROUNDS, MAX_COMPLETION, TOTAL_COMPLETION, TOTAL_PROMPT_BYTES
            manifest = load_manifest()
            # Pure local source verification; no key lookup and no provider request.
            require(all(digest(read_bytes(root, p)) == sha for p, sha in manifest['files'].items()), 'input_hash_mismatch')
            output = {'mode': 'preflight_only', 'base_sha': manifest['base_sha'], 'model': 'openai/gpt-oss-120b',
                      'scenarios': GOALS, 'expected_calls_per_scenario': '3–4', 'hard_max_posts_per_scenario': MAX_ROUNDS,
                      'max_completion_per_post': MAX_COMPLETION, 'max_completion_total_per_scenario': TOTAL_COMPLETION,
                      'max_cumulative_prompt_utf8_bytes_per_scenario': TOTAL_PROMPT_BYTES,
                      'transport': 'fixed curl POST', 'retry': False, 'fallback': False,
                      'response_format': 'json_schema strict=true', 'native_tool_choice': 'none',
                      'provider_posts': 0, 'approval_required': True}
            ok = True
        elif args.command == 'offline-check':
            output, ok = offline_check(root, args.run_id)
        elif args.command == 'replay':
            trace, output = replay(root, args.trace, args.run_id)
            ok = trace['status'] == 'completed'
        else:
            goal = args.goal or GOALS[args.scenario]
            if args.command == 'openai-live':
                from openai_adapter import OpenAIAdapter
                require(args.approve_up_to_4_openai_posts, 'openai_not_approved')
                adapter = OpenAIAdapter(approved=True, max_posts=args.max_posts, read_policy='bounded-v3')
            elif args.command == 'live':
                require(args.approve_up_to_5_groq_posts, 'live_not_approved')
                adapter = GroqAdapter(approved=True, max_posts=args.max_posts)
            else:
                require(args.scenario is not None, 'mock_requires_named_scenario')
                adapter = MockAdapter(strict_json((HERE / 'offline_fixtures.json').read_bytes())[args.scenario])
            tools = FileTools(root, args.run_id, load_manifest(),
                              read_policy='bounded-v3' if args.command == 'openai-live' else 'strict-v1')
            trace, output = run(goal, tools, adapter)
            ok = trace['status'] == 'completed' and output['file_operation'] == 'PASS'
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    except Exception as exc:
        print(json.dumps({'status': 'stopped', 'error': str(exc) if isinstance(exc, Rejected) else 'local_configuration_or_io_error',
                          'instruction': 'Inspect existing evidence. Do not automatically repeat a live attempt.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(cli())
