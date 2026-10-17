"""Explicit, request-bound continuations of verified local range failures.

Reuses saved MODEL choices, never supplies a scripted replacement plan. The source
attempt and budget receipts remain immutable. No network code runs during check.
"""
from agent import GOALS, run
from file_tools import FileTools, MODULE, digest, read_bytes, require, strict_json
from llm_adapter import ReplayAdapter
from openai_adapter import (OpenAIAdapter, MODEL, MAX_REQUEST_BYTES, FRAME_RESERVE,
                            MAX_OUTPUT, MAX_NANO_USD, TOTAL_POSTS, dumps)

PREFLIGHT_STOP = 'resume_preflight_complete_no_posts'


def verified_source(root, trace_path, manifest):
    from main import load_trace
    saved, raw = load_trace(root, trace_path)
    require(saved.get('schema') == 1 and saved.get('mode') == 'live_openai'
            and saved.get('status') == 'failed' and saved.get('error') == 'invalid_line_range'
            and saved.get('goal') in GOALS.values() and not saved.get('documents')
            and saved.get('inputs_sha256') == manifest['files'], 'unsupported_resume_source')
    calls, events = saved['model_calls'], saved['events']
    is_adr = saved['goal'] == GOALS['adr']
    expected_calls = 2 if is_adr else 3
    expected_policy = 'bounded-v2' if is_adr else 'strict-v1'
    require(saved.get('file_read_policy', 'strict-v1') == expected_policy
            and len(calls) == expected_calls and calls[-1]['response_text'] and events
            and saved['generation_calls'] == expected_calls, 'unsupported_resume_prefix')
    decisions = [strict_json(c['response_text']) for c in calls]
    actions = [a for d in decisions for a in d['actions']]
    require(not any(d['done'] for d in decisions) and len(events) <= len(actions)
            and all(e['action'] == a for e, a in zip(events, actions))
            and all(e['status'] == 'ok' for e in events[:-1])
            and events[-1]['status'] == 'rejected' and events[-1]['error'] == 'invalid_line_range',
            'unsupported_resume_events')
    # The application may have stopped in the middle of a saved model-selected batch.
    require(events[-1]['turn'] == len(calls), 'unsupported_resume_events')
    action = actions[len(events) - 1]
    require(action['tool'] == 'read_file', 'unsupported_resume_action')
    args = action['args']
    require(args.get('path') in manifest['files'] and type(args.get('start')) is int
            and type(args.get('end')) is int, 'unsupported_resume_range')
    lines = read_bytes(root, args['path']).decode().splitlines()
    require(1 <= args['start'] <= len(lines) and args['start'] <= args['end']
            and (args['end'] > len(lines) if is_adr else
                 args['end'] <= len(lines) and args['end'] - args['start'] >= 200),
            'unsupported_resume_range')
    folder = trace_path.rsplit('/', 1)[0]
    for n, call in enumerate(calls, 1):
        meta = call['meta']
        require(meta.get('mode') == 'live_openai' and meta.get('http_status') == '200'
                and meta.get('curl_exit') == 0 and meta.get('http_post_attempt') == n,
                'resume_provider_call_not_successful')
        request = read_bytes(root, folder + f'/provider-{n}-request.json')
        response = strict_json(read_bytes(root, folder + f'/provider-{n}-response.json'))
        require(digest(request) == call['wire_request_sha256']
                and strict_json(request) == call['wire_request']
                and response['choices'][0]['finish_reason'] == 'tool_calls'
                and response['choices'][0]['message'] == call['native_message']
                and response['usage'] == meta['usage'] and response['model'] == meta['model']
                and (response['model'] == MODEL or response['model'].startswith(MODEL + '-')),
                'resume_raw_evidence_mismatch')
        slot = meta['budget_slot']
        require(slot.startswith(MODULE + '/results/openai-post-budget/post-')
                and slot.endswith('.json'), 'resume_invalid_budget_slot')
        receipt = strict_json(read_bytes(root, slot))
        attempt = strict_json(read_bytes(root, folder + f'/provider-{n}-attempt.json'))
        require(receipt == attempt and receipt['request_sha256'] == digest(request)
                and receipt['run'] == folder, 'resume_budget_receipt_mismatch')
    return saved, raw


class ContinuationAdapter:
    def __init__(self, saved, info, live=None):
        self.mode = 'live_openai' if live is not None else 'offline_resume_check'
        self.prefix = ReplayAdapter(saved)
        self.system_prompt = self.prefix.system_prompt
        self.saved = saved
        self.resume_info = info
        self.live = live
        self.records = []
        self.preview = None
        self.max_posts = len(saved['model_calls']) + 2
        self.read_policy = 'bounded-v3' if saved['goal'] == GOALS['adr'] else 'bounded-v2'
        self.continuation = 'adr-v3' if saved['goal'] == GOALS['adr'] else True

    @property
    def posts(self):
        return self.live.posts if self.live is not None else 0

    def choose(self, messages, tools):
        if len(self.records) < len(self.saved['model_calls']):
            decision = self.prefix.choose(messages, tools)
            self.records.append(self.prefix.records[-1])
            return decision
        self.prefix.exhausted()
        native = [c['native_message'] for c in self.records]
        self.preview = OpenAIAdapter.build_request(messages, native, self.read_policy, self.continuation)
        require(len(dumps(self.preview).encode()) <= MAX_REQUEST_BYTES,
                'openai_request_budget_exceeded_before_post')
        if self.live is None:
            tools.save('continuation-request-preview.json', self.preview)
            require(False, PREFLIGHT_STOP)
        self.live.native_messages = native
        try:
            return self.live.choose(messages, tools)
        finally:
            # Include errors and usage in the combined trace, without changing old records.
            self.records[:] = self.saved['model_calls'] + self.live.records


def resume_run(root, trace_path, run_id, manifest, live=False, approve_extra_post=False):
    saved, raw = verified_source(root, trace_path, manifest)
    is_adr = saved['goal'] == GOALS['adr']
    require(not approve_extra_post or is_adr, 'extra_post_approval_only_for_adr_continuation')
    require(not (live and is_adr) or approve_extra_post, 'extra_openai_post_not_approved')
    policy = 'bounded-v3' if is_adr else 'bounded-v2'
    continuation = 'adr-v3' if is_adr else True
    count = len(saved['model_calls'])
    info = {'trace_path':trace_path, 'trace_sha256':digest(raw), 'historical_provider_posts':count,
            'reused_model_decisions':count, 'new_post_cap':2, 'previous_error':saved['error'],
            'policy_change':saved.get('file_read_policy', 'strict-v1') + ' -> ' + policy,
            'one_extra_post_explicitly_approved':approve_extra_post,
            'original_attempt_modified':False}
    provider = OpenAIAdapter(approved=True, max_posts=2, read_policy=policy, continuation=continuation,
                             approve_extra_post=approve_extra_post) if live else None
    tools = FileTools(root, run_id, manifest, read_policy=policy)
    adapter = ContinuationAdapter(saved, info, provider)
    trace, acceptance = run(saved['goal'], tools, adapter)
    if live:
        return acceptance, trace['status'] == 'completed' and acceptance['file_operation'] == 'PASS'
    expected = saved['events'][:-1]
    ready = (trace['error'] == PREFLIGHT_STOP and trace['events'][:len(expected)] == expected
             and all(e['status'] == 'ok' for e in trace['events']) and trace['inputs_unchanged']
             and adapter.posts == 0)
    receipts = []
    for slot in range(1, TOTAL_POSTS + 2):
        try:
            receipts.append(strict_json(read_bytes(root, MODULE + f'/results/openai-post-budget/post-{slot:02}.json')))
        except FileNotFoundError:
            pass
    require(all(type(r.get('reserved_nano_usd')) is int and 0 <= r['reserved_nano_usd'] <= MAX_NANO_USD
                for r in receipts), 'openai_invalid_budget_receipt')
    used = sum(r['reserved_nano_usd'] for r in receipts)
    bound_per_post = (MAX_REQUEST_BYTES + FRAME_RESERVE) * 750 + MAX_OUTPUT * 4500
    preview_bytes = len(dumps(adapter.preview).encode()) if adapter.preview else None
    proposed_cap = TOTAL_POSTS + int(is_adr)
    budget_extension_needed = is_adr and len(receipts) + 2 > TOTAL_POSTS
    ready = ready and len(receipts) + 2 <= proposed_cap and used + 2 * bound_per_post <= MAX_NANO_USD
    recovered = trace['events'][len(expected)].get('result', {})
    report = {'status':('ready_pending_budget_approval' if budget_extension_needed else 'ready') if ready else 'stopped',
              'mode':'offline_resume_preflight',
              'source':info, 'saved_decisions_verified':len(adapter.records), 'provider_posts':0,
              'successful_local_operations':sum(e['status'] == 'ok' for e in trace['events']),
              'bounded_read_result':{k:v for k,v in recovered.items() if k != 'lines'},
              'next_request_utf8_bytes':preview_bytes, 'max_request_utf8_bytes':MAX_REQUEST_BYTES,
              'existing_openai_post_slots':len(receipts), 'remaining_openai_post_slots':TOTAL_POSTS-len(receipts),
              'proposed_total_post_cap':proposed_cap, 'budget_extension_approval_required':budget_extension_needed,
              'existing_reserved_usd':used/1e9,
              'worst_reserved_usd_using_all_remaining_slots':(used+(proposed_cap-len(receipts))*bound_per_post)/1e9,
              'new_documents':list(trace['documents']), 'full_e2e':'NOT_ACCEPTED',
              'instruction':('Offline only. ADR continuation requires explicit approval of one extra OpenAI POST (total 9), while retaining the $0.50 cost cap.'
                             if is_adr else 'Offline only. Live continuation is a separate explicit command within the existing OpenAI POST/cost limits.'),
              'error':None if ready else trace['error']}
    tools.save('resume-preflight.json', report)
    return report, ready
