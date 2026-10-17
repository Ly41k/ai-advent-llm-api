"""One goal -> bounded model decisions -> validated filesystem operations."""
import difflib
import json
from file_tools import CORE, MAX_OPERATIONS, Rejected, digest, exclusive_write, read_bytes, require
from llm_adapter import MAX_ROUNDS, SYSTEM

GOALS = {
    'usage': 'Найди все места использования fetch_context в модуле Day 33 и подготовь отчёт.',
    'adr': 'Изучи, как Day 33 получает контекст тикета через MCP, и создай краткий ADR с описанием архитектуры.'
}


def run(goal, tools, adapter, expected=None):
    require(isinstance(goal, str) and 0 < len(goal.encode()) <= 2000, 'invalid_goal')
    system_prompt = getattr(adapter, 'system_prompt', SYSTEM)
    max_rounds = min(MAX_ROUNDS, getattr(adapter, 'max_posts', MAX_ROUNDS))
    messages = [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': goal}]
    trace = {'schema': 1, 'mode': adapter.mode, 'goal': goal, 'inputs_sha256': tools.inputs,
             'model_calls': adapter.records, 'events': [], 'status': 'running', 'system_prompt': system_prompt,
             'limits': {'model_rounds': max_rounds, 'operations': MAX_OPERATIONS},
             'automatic_retries': 0, 'fallback_calls': 0}
    trace['file_read_policy'] = tools.read_policy
    if hasattr(adapter, 'resume_info'):
        trace['resumed_from'] = adapter.resume_info
    historical_rejections = getattr(adapter, 'historical_rejections', {})
    if historical_rejections:
        trace['historical_rejections'] = historical_rejections
    error = None
    done = False
    try:
        for turn in range(max_rounds):
            decision = adapter.choose(messages.copy(), tools)
            require(isinstance(decision, dict) and set(decision) == {'actions', 'done'}, 'invalid_decision')
            actions = decision['actions']
            require(type(decision['done']) is bool and isinstance(actions, list) and len(actions) <= 8
                    and (actions or decision['done']), 'invalid_decision')
            messages.append({'role': 'assistant', 'content': json.dumps(decision, ensure_ascii=False)})
            results = []
            restored_rejection = False
            for action in actions:
                event = {'turn': turn + 1, 'action': action}
                trace['events'].append(event)
                try:
                    result = tools.execute(action)
                    event.update(status='ok', result=result)
                    results.append(result)
                except Exception as exc:
                    event.update(status='rejected', error=str(exc) if isinstance(exc, Rejected) else 'filesystem_or_argument_error')
                    rule = historical_rejections.get(str(turn + 1))
                    fingerprint = digest(json.dumps(action, ensure_ascii=False).encode())
                    if (isinstance(exc, Rejected) and str(exc) == 'quote_mismatch'
                            and rule == {'error':'quote_mismatch', 'action_sha256':fingerprint}
                            and action['tool'] == 'write_file' and len(actions) == 1):
                        # Explicitly restore ONE verified historical rejection as tool feedback.
                        # Fresh tool/HTTP errors still stop; no arguments or quotes are repaired here.
                        mismatch = tools.quote_mismatches(action['args']['evidence'])
                        require(bool(mismatch), 'missing_historical_quote_diagnostic')
                        result = {'error':'quote_mismatch', 'file_written':False,
                                  'quote_mismatches':mismatch}
                        event.update(result=result, restored_historical_rejection=True)
                        results.append(result)
                        restored_rejection = True
                    else:
                        raise
            messages.append({'role': 'user', 'content': json.dumps({'untrusted_tool_results': results}, ensure_ascii=False)})
            if decision['done'] and not restored_rejection:
                require(bool(tools.created), 'done_without_document')
                done = True
                break
        require(done, 'model_round_limit')
        if hasattr(adapter, 'exhausted'):
            adapter.exhausted()
        tools.snapshot()
        trace['status'] = 'completed'
        if expected:
            require(trace['events'] == expected['events'], 'replay_tool_result_mismatch')
            require(tools.created.keys() == expected['documents'].keys(), 'replay_document_set_mismatch')
            require(all(tools.created[p]['sha256'] == expected['documents'][p]['sha256'] for p in tools.created), 'replay_document_mismatch')
    except BaseException as exc:
        error = str(exc) if isinstance(exc, Rejected) else 'interrupted_or_local_error'
        trace['status'] = 'failed'
    finally:
        try:
            unchanged = tools.snapshot() == tools.inputs
        except Exception:
            unchanged = False
            error = error or 'inputs_changed'
            trace['status'] = 'failed'
        trace.update(error=error, generation_calls=adapter.posts, documents=tools.created,
                     evidence=tools.evidence, inputs_unchanged=unchanged)
        if expected:
            trace['replay_of'] = {'mode': expected['mode'], 'fresh_live_acceptance': False}
        # Events do not include run-specific output paths; replays can compare exactly.
        changes = []
        diff = []
        for name, item in tools.created.items():
            raw = read_bytes(tools.root, item['path'])
            changes.append({'operation': 'create', 'name': name, 'sha256': digest(raw), 'bytes': len(raw)})
            diff.extend(difflib.unified_diff([], raw.decode().splitlines(keepends=True),
                                           fromfile='/dev/null', tofile='b/' + name))
        tools.save('changes.json', changes)
        exclusive_write(tools.root, tools.output_rel + '/changes.diff', ''.join(diff).encode())
        tools.save('trace.json', trace)
        searches = [e['result'] for e in trace['events'] if e.get('status') == 'ok' and e['action']['tool'] == 'search_files']
        reads = {e['action']['args']['path'] for e in trace['events'] if e.get('status') == 'ok' and e['action']['tool'] == 'read_file'}
        covered = {e['action']['tool'] for e in trace['events'] if e.get('status') == 'ok'}
        checks = {'completed': done and error is None, 'inputs_unchanged': unchanged,
                  'searched_at_least_three_files': any(len(s['searched_files']) >= 3 for s in searches),
                  'all_four_tools_observed': covered == {'list_files', 'search_files', 'read_file', 'write_file'},
                  'read_core_three': set(CORE) <= reads, 'documents_created': bool(tools.created),
                  'references_and_quotes_validated': bool(tools.evidence)}
        accepted = {'mode': adapter.mode, 'technical_checks': checks,
                    'file_operation': 'PASS' if all(checks.values()) else 'FAIL',
                    'real_llm_tool_selection': 'PENDING_REVIEW' if adapter.mode in ('live_groq','live_openai') and error is None else 'NOT_EVALUATED',
                    'result_quality': 'PENDING_REVIEW', 'full_e2e': 'NOT_ACCEPTED',
                    'new_groq_posts': adapter.posts if adapter.mode == 'live_groq' else 0,
                    'new_openai_posts': adapter.posts if adapter.mode == 'live_openai' else 0,
                    'new_provider_posts': adapter.posts, 'error': error,
                    'note': 'Offline/mock and replay cannot establish fresh real LLM selection or semantic quality.'}
        if hasattr(adapter, 'resume_info'):
            accepted.update(reused_model_decisions=adapter.resume_info['reused_model_decisions'],
                            historical_openai_posts=adapter.resume_info['historical_provider_posts'],
                            continuation_trace=tools.output_rel + '/trace.json')
        tools.save('acceptance.json', accepted)
    return trace, accepted
