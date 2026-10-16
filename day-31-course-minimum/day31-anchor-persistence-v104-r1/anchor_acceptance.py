"""Persist v103 selected anchors and apply explicitly attributed semantic reviews.

No model calls, replacement evidence, automatic entailment, or text repair.
The v103 helper and installed application remain the source of runtime checks.
"""
from copy import deepcopy
from hashlib import sha256
import json

VERSION = 'source-anchor-persistence-semantic-review-v1'


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def build_record(result, witness, context, result_version):
    """Bind the original chosen quote; do not search for a better supporting one."""
    from bublik_developer.generation import strict_json
    from bublik_developer.contracts import ContextEnvelope
    from source_anchors import catalogs, select
    import forensic_capture

    task_id = witness['task_id']
    tasks = [t for t in result['inference_tasks'] if t['task_id'] == task_id]
    if len(tasks) != 1 or result['request_id'] != witness['request_id']:
        raise ValueError('capture_result_identity_mismatch')
    task = tasks[0]
    if ContextEnvelope.seal(context).digest != witness['context_digest']:
        raise ValueError('capture_context_mismatch')
    for key in ('context_digest', 'message_digest', 'output_schema_digest'):
        if task[key] != witness[key]:
            raise ValueError('capture_task_fingerprint_mismatch')
    replay = forensic_capture.analyze(witness, witness['mode'])
    preview, prepared = forensic_capture.reference(witness['mode'], witness['context_digest'])
    if context != prepared:
        raise ValueError('capture_prepared_context_mismatch')
    # Pure request construction; no client/session is initialized or dispatched.
    from prompt_profile import CoverageBaseline, CoverageQwen
    from bublik_developer.contracts import Role
    from bublik_developer.generation import MODEL, OPTIONS
    single = witness['mode']=='single'
    client = (CoverageBaseline if single else CoverageQwen).__new__(CoverageBaseline if single else CoverageQwen)
    role = Role.MAIN if single else Role.DOCUMENTATION
    body = {'model': MODEL, 'messages': [{'role':'system','content':client.system_prompt(role,context)},
              {'role':'user','content':json.dumps(context,ensure_ascii=False,sort_keys=True)}],
            'stream':False, 'format':client.schema_builder(role,context),
            'options':deepcopy(OPTIONS), 'keep_alive':'0s'}
    if digest(body) != witness['request_body_sha256']:
        raise ValueError('capture_request_body_mismatch')
    runtime_passed = task['output_validation'] == 'passed'
    if runtime_passed != replay['validation_passed']:
        raise ValueError('capture_validation_mismatch')
    if not runtime_passed and task.get('output_validation_reason') != replay['validation_reason']:
        raise ValueError('capture_rejection_reason_mismatch')
    frame = strict_json(witness['response']['message']['content'])
    claims = frame.get('claims')
    if not isinstance(claims, list):
        raise ValueError('capture_claims_missing')
    if runtime_passed:
        normalized = replay['normalized_output']['claims']
        expected = [{'id': f'c{i}', **c} for i, c in enumerate(normalized, 1)]
        # Order may change during Main merge; identity/text/evidence may not.
        if sorted(result['claims'], key=lambda c:c['id']) != sorted(expected, key=lambda c:c['id']):
            raise ValueError('pipeline_claims_differ_from_validated_capture')
    elif result['claims']:
        raise ValueError('rejected_capture_exposed_as_answer_claims')
    origin = {'policy_version': VERSION, 'result_version': deepcopy(result_version),
              'result_sha256': digest(result), 'witness_sha256': digest(witness),
              'context_sha256': digest(context), 'frame_sha256': digest(frame),
              'request_id': result['request_id'], 'task_id': task_id,
              'runtime_passed': runtime_passed, 'claim_count':len(claims)}
    catalog = catalogs(context)
    anchors = []
    for i, claim in enumerate(claims, 1):
        quote = claim.get('source_quote')
        ids = claim.get('evidence_ids')
        chosen = select(catalog, ids, quote)
        # Reuse the v103 source_anchors shape (source, evidence_id, quote,
        # normalized offsets, lines, raw/text digests), including rejected raw.
        item = {'claim_id': f'c{i}', 'text': claim.get('text'),
                'evidence_id': ids[0] if isinstance(ids, list) and len(ids)==1 else None,
                'quote': quote, 'claim_sha256': digest(claim),
                'in_answer': runtime_passed,
                'exact_anchor_check': 'passed' if chosen else 'failed',
                'runtime_validation': {'status': 'passed' if runtime_passed else 'rejected',
                                       'reason': replay['validation_reason']}}
        if chosen:
            item.update(deepcopy(chosen))
        item['binding_sha256'] = digest({'origin': origin, 'selected_anchor': item})
        anchors.append(item)
    return {'version': VERSION, 'origin': origin, 'binding_sha256': digest(origin),
            'runtime_passed': runtime_passed, 'source_anchors': anchors}


def verify_record(record):
    if record['version'] != VERSION or digest(record['origin']) != record['binding_sha256']:
        raise ValueError('grounding_origin_changed')
    if record.get('runtime_passed') != record['origin']['runtime_passed']:
        raise ValueError('grounding_runtime_status_changed')
    ids = []
    for anchor in record['source_anchors']:
        copy = deepcopy(anchor); binding = copy.pop('binding_sha256')
        if digest({'origin':record['origin'], 'selected_anchor':copy}) != binding:
            raise ValueError('grounding_anchor_changed')
        ids.append(anchor['claim_id'])
    if ids != [f'c{i}' for i in range(1, record['origin']['claim_count']+1)]:
        raise ValueError('grounding_claim_set_changed')


def decision_status(anchor, decision):
    """Authenticate manual annotation coverage, not the annotator's reasoning."""
    if decision.get('binding_sha256') != anchor['binding_sha256']:
        raise ValueError('review_anchor_binding_changed')
    clauses = decision.get('clauses')
    if not isinstance(clauses, list) or not clauses:
        raise ValueError('review_clause_coverage_missing')
    if ''.join(c.get('text', '') for c in clauses) != anchor['text']:
        raise ValueError('review_clause_text_changed_or_incomplete')
    statuses = []
    for c in clauses:
        status = c.get('status')
        if status not in {'supported', 'unsupported', 'needs_review'}:
            raise ValueError('review_clause_status_invalid')
        if not c['text'].strip() or not isinstance(c.get('reason'), str) or not c['reason'].strip():
            raise ValueError('review_clause_reason_missing')
        support = c.get('support_spans')
        if not isinstance(support, list) or (status=='supported' and not support):
            raise ValueError('review_clause_support_missing')
        if any(not isinstance(s, str) or not s or s not in anchor['quote'] for s in support):
            raise ValueError('review_support_outside_selected_anchor')
        statuses.append(status)
    status = ('unsupported' if 'unsupported' in statuses else
              'needs_review' if 'needs_review' in statuses else 'supported')
    if decision.get('status') != status:
        raise ValueError('review_composite_status_mismatch')
    return status


def semantic_gate(record, review=None, *, authorities=None):
    """Unknown/heuristic/assistant-positive evidence stays needs_review.

    Authorities are supplied by the operator, never taken from the review file.
    This is a local trust configuration, not a signature/identity service.
    Only an explicitly configured human can approve support. A configured
    assistant may record negative findings; it cannot grant positive acceptance.
    """
    verify_record(record)
    authorities = authorities or {}
    decisions = {}; reviewer = None; error = None
    if review is not None:
        try:
            if review.get('policy_version') != VERSION or review.get('result_binding_sha256') != record['binding_sha256']:
                raise ValueError('review_result_version_or_binding_changed')
            reviewer = review['reviewer']
            kind = authorities.get(reviewer['id'])
            if kind not in {'human', 'assistant'} or reviewer.get('kind') != kind:
                raise ValueError('reviewer_not_explicitly_trusted')
            supplied = review['decisions']
            known = {a['claim_id']: a for a in record['source_anchors']}
            if len({d['claim_id'] for d in supplied}) != len(supplied):
                raise ValueError('review_duplicate_claim_ids')
            for d in supplied:
                if d['claim_id'] not in known:
                    raise ValueError('review_unrelated_claim')
                decisions[d['claim_id']] = decision_status(known[d['claim_id']], d)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            decisions = {}; reviewer = None; error = str(exc) or type(exc).__name__
    rows = []
    for anchor in record['source_anchors']:
        finding = decisions.get(anchor['claim_id'])
        status = 'needs_review'; reason = 'explicit_human_review_pending'
        if anchor['exact_anchor_check'] != 'passed':
            reason = 'selected_anchor_not_verified'
        elif finding == 'unsupported':
            status = 'unsupported'; reason = 'explicit_negative_review'
        elif finding == 'supported' and reviewer and reviewer['kind']=='human':
            status = 'supported'; reason = 'explicit_bound_human_review'
        elif finding == 'supported':
            reason = 'assistant_support_finding_is_not_human_acceptance'
        rows.append({'claim_id': anchor['claim_id'], 'binding_sha256': anchor['binding_sha256'],
                     'status': status, 'review_finding': finding, 'reason': reason})
    statuses = [r['status'] for r in rows]
    overall = ('unsupported' if 'unsupported' in statuses else
               'supported' if statuses and all(s=='supported' for s in statuses) else 'needs_review')
    accepted = record['runtime_passed'] and overall=='supported'
    return {'version': VERSION, 'status': overall, 'answer_accepted': accepted,
            'runtime_validation': 'passed' if record['runtime_passed'] else 'rejected',
            'claims': rows, 'reviewer': deepcopy(reviewer), 'review_error': error,
            'review_sha256': digest(review) if review is not None else None,
            'completeness': 'evaluated_separately', 'stage7_acceptance': 'not_evaluated',
            'automatic_semantic_entailment': False}


def attach(result, witness, context, result_version, review=None, *, authorities=None):
    """Add metadata to the final envelope without rewriting any native field."""
    if 'source_anchors' in result or 'semantic_acceptance' in result or 'anchor_binding' in result:
        raise ValueError('grounding_extension_already_present')
    record = build_record(result, witness, context, result_version)
    output = deepcopy(result)
    output['source_anchors'] = deepcopy(record['source_anchors'])
    output['anchor_binding'] = {'version': VERSION, 'origin': record['origin'],
                                'binding_sha256': record['binding_sha256']}
    output['semantic_acceptance'] = semantic_gate(record, review, authorities=authorities)
    return output


def verify_envelope(output, review=None, *, authorities=None):
    """Use before serialization/consumption to detect post-review edits."""
    native = {k:v for k,v in output.items() if k not in {'source_anchors','anchor_binding','semantic_acceptance'}}
    binding = output['anchor_binding']
    if digest(native) != binding['origin']['result_sha256']:
        raise ValueError('post_review_pipeline_result_changed')
    record = {'version':binding['version'], 'origin':binding['origin'],
              'binding_sha256':binding['binding_sha256'],
              'source_anchors':output['source_anchors'],
              'runtime_passed':binding['origin']['runtime_passed']}
    verify_record(record)
    task = next(t for t in native['inference_tasks'] if t['task_id']==binding['origin']['task_id'])
    if (task['output_validation']=='passed') != record['runtime_passed']:
        raise ValueError('gate_runtime_status_changed')
    if semantic_gate(record, review, authorities=authorities) != output['semantic_acceptance']:
        raise ValueError('gate_decision_changed')
    return True
