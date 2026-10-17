"""One separately authorized model repair; strict quotes and failed evidence stay intact."""
from agent import GOALS, run
from file_tools import FileTools, MODULE, digest, read_bytes, require, strict_json
from openai_adapter import OpenAIAdapter, MODEL, MAX_REQUEST_BYTES, FRAME_RESERVE, MAX_OUTPUT, MAX_NANO_USD, dumps
from resume import ContinuationAdapter, PREFLIGHT_STOP, verified_source


def verified_quote_source(root, trace_path, manifest):
    from main import load_trace
    saved, raw = load_trace(root, trace_path)
    require(saved.get('schema') == 1 and saved.get('mode') == 'live_openai'
            and saved.get('status') == 'failed' and saved.get('error') == 'quote_mismatch'
            and saved.get('goal') == GOALS['adr'] and saved.get('file_read_policy') == 'bounded-v3'
            and not saved.get('documents') and not saved.get('historical_rejections')
            and saved.get('inputs_sha256') == manifest['files'], 'unsupported_quote_repair_source')
    calls, events = saved['model_calls'], saved['events']
    require(len(calls) == 4 and saved['generation_calls'] == 2 and events,
            'unsupported_quote_repair_history')
    parent_path = saved['resumed_from']['trace_path']
    parent, parent_raw = verified_source(root, parent_path, manifest)
    require(parent['goal'] == GOALS['adr'] and digest(parent_raw) == saved['resumed_from']['trace_sha256']
            and calls[:2] == parent['model_calls'] and saved['system_prompt'] == parent['system_prompt'],
            'quote_repair_parent_mismatch')
    decisions = [strict_json(c['response_text']) for c in calls]
    actions = [a for d in decisions for a in d['actions']]
    require(not any(d['done'] for d in decisions[:-1]) and decisions[-1]['done']
            and len(decisions[-1]['actions']) == 1 and len(actions) == len(events)
            and all(e['action'] == a for e, a in zip(events, actions))
            and all(e['status'] == 'ok' for e in events[:-1])
            and events[-1]['status'] == 'rejected' and events[-1]['error'] == 'quote_mismatch'
            and events[-1]['turn'] == 4, 'quote_repair_event_mismatch')
    last = actions[-1]
    require(last['tool'] == 'write_file' and last['args']['path'] == 'ADR-001-ticket-context.md',
            'unsupported_quote_repair_submission')
    folder = trace_path.rsplit('/', 1)[0]
    for n, call in enumerate(calls[2:], 1):
        meta = call['meta']
        require(meta.get('mode') == 'live_openai' and meta.get('http_status') == '200'
                and meta.get('curl_exit') == 0 and meta.get('http_post_attempt') == n,
                'quote_repair_provider_not_successful')
        request = read_bytes(root, folder + f'/provider-{n}-request.json')
        response = strict_json(read_bytes(root, folder + f'/provider-{n}-response.json'))
        require(digest(request) == call['wire_request_sha256'] and strict_json(request) == call['wire_request']
                and response['choices'][0]['message'] == call['native_message']
                and response['choices'][0]['finish_reason'] == 'tool_calls'
                and response['usage'] == meta['usage'] and response['model'] == meta['model']
                and (response['model'] == MODEL or response['model'].startswith(MODEL + '-')),
                'quote_repair_raw_evidence_mismatch')
        slot = meta['budget_slot']
        require(slot.startswith(MODULE + '/results/openai-post-budget/post-') and slot.endswith('.json'),
                'quote_repair_budget_path')
        receipt = strict_json(read_bytes(root, slot))
        require(receipt == strict_json(read_bytes(root, folder + f'/provider-{n}-attempt.json'))
                and receipt['request_sha256'] == digest(request) and receipt['run'] == folder,
                'quote_repair_receipt_mismatch')
    return saved, raw, last


class QuoteRepairAdapter(ContinuationAdapter):
    def __init__(self, saved, info, action, live=None):
        super().__init__(saved, info, live)
        self.max_posts = 5  # Four preserved decisions, at most ONE fresh decision.
        self.mode = 'live_openai' if live is not None else 'offline_repair_check'
        self.continuation = 'quote-repair-v7'
        self.historical_rejections = {
            '4':{'error':'quote_mismatch', 'action_sha256':digest(dumps(action).encode())}}


def repair_run(root, trace_path, run_id, manifest, live=False, approved=False):
    require(not live or approved, 'tenth_openai_post_not_approved')
    saved, raw, action = verified_quote_source(root, trace_path, manifest)
    info = {'trace_path':trace_path, 'trace_sha256':digest(raw), 'historical_provider_posts':4,
            'reused_model_decisions':4, 'new_post_cap':1, 'previous_error':'quote_mismatch',
            'tenth_openai_post_explicitly_approved':approved,
            'quote_validation':'EXACT; no normalization or application-written correction',
            'original_attempt_modified':False}
    provider = OpenAIAdapter(approved=True, max_posts=1, read_policy='bounded-v3',
                             continuation='quote-repair-v7', approve_extra_post=True,
                             approve_quote_repair_post=True) if live else None
    tools = FileTools(root, run_id, manifest, read_policy='bounded-v3')
    adapter = QuoteRepairAdapter(saved, info, action, provider)
    trace, acceptance = run(saved['goal'], tools, adapter)
    if live:
        return acceptance, trace['status'] == 'completed' and acceptance['file_operation'] == 'PASS'
    rejected = trace['events'][-1] if trace['events'] else {}
    ready = (trace['error'] == PREFLIGHT_STOP and trace['events'][:-1] == saved['events'][:-1]
             and rejected.get('action') == saved['events'][-1]['action']
             and rejected.get('restored_historical_rejection') is True and trace['inputs_unchanged']
             and not tools.created and adapter.posts == 0)
    receipts = []
    for slot in range(1, 11):
        try:
            receipts.append(strict_json(read_bytes(root, MODULE + f'/results/openai-post-budget/post-{slot:02}.json')))
        except FileNotFoundError:
            pass
    require(all(type(r.get('reserved_nano_usd')) is int and 0 <= r['reserved_nano_usd'] <= MAX_NANO_USD
                for r in receipts), 'openai_invalid_budget_receipt')
    used = sum(r['reserved_nano_usd'] for r in receipts)
    bound = (MAX_REQUEST_BYTES + FRAME_RESERVE) * 750 + MAX_OUTPUT * 4500
    ready = ready and len(receipts) == 9 and used + bound <= MAX_NANO_USD
    report = {'status':'ready_pending_tenth_post_approval' if ready else 'stopped',
              'mode':'offline_quote_repair_preflight', 'provider_posts':0,
              'saved_decisions_verified':len(adapter.records), 'original_write_still_rejected':True,
              'quote_validation':'EXACT', 'mismatches':rejected.get('result',{}).get('quote_mismatches',[]),
              'next_request_utf8_bytes':len(dumps(adapter.preview).encode()) if adapter.preview else None,
              'current_total_post_cap':9, 'proposed_total_post_cap':10, 'new_post_cap':1,
              'existing_openai_post_slots':len(receipts), 'existing_reserved_usd':used/1e9,
              'worst_total_reserved_usd':(used + bound)/1e9, 'new_documents':[],
              'full_e2e':'NOT_ACCEPTED', 'error':None if ready else trace['error'],
              'instruction':'Offline only. A tenth POST requires separate explicit authorization; no quote check is weakened.'}
    tools.save('quote-repair-preflight.json', report)
    return report, ready
