"""Closed public projection. Native traces are diagnostic, never public answers.

No model, semantic heuristic or evidence reselection. Human authorities are
operator configuration, not identities trusted from a result/review payload.
"""
from copy import deepcopy
import json

POLICY = 'claim-anchor-publication-v1'


def _public(native, gate, *, accepted=False, anchors=(), binding=None):
    # Construct from an allowlist. Do not pass through arbitrary answer formats,
    # excerpts, worker data, raw replies, recovery text, paths or extra fields.
    claims = deepcopy(native['claims']) if accepted else []
    selected = deepcopy(list(anchors)) if accepted else []
    text = '\n\n'.join(c['text'] for c in claims) if accepted else (
        'Ответ не опубликован: требуется подтверждение.' if native.get('language')=='ru'
        else 'Answer withheld: confirmation required.')
    return {'schema_version': 1, 'result_format': 'publication-gated-answer-v1',
            'request_id': native['request_id'], 'project_id': native['project_id'],
            'language': native.get('language'), 'execution_status': native['execution_status'],
            'answer_status': 'supported' if accepted else 'withheld',
            'answer_accepted': bool(accepted), 'answer': text, 'claims': claims,
            'citations': [{'claim_id':a['claim_id'], 'source':a['source'],
                           'start_line':a['start_line'], 'end_line':a['end_line'],
                           'quote':a['quote'], 'binding_sha256':a['binding_sha256']}
                          for a in selected],
            'source_anchors': selected, 'semantic_acceptance': deepcopy(gate),
            'publication': {'policy':POLICY, 'result_binding_sha256':binding,
                            'partial_answer_published':False,
                            'runtime_refusal_preserved':gate['runtime_validation']=='rejected'},
            # SnapshotPipeline adds accounting here after the common boundary.
            'metrics': {k:deepcopy(v) for k,v in native.get('metrics',{}).items()
                        if isinstance(v,(int,float,bool)) or v is None}}


def deny_unreviewed(native):
    """Default for legacy model routes without a captured binding/review.

Zero-model deterministic Git operations retain their existing contract.
Model observations OR nonempty model claims always enter the closed boundary.
"""
    m=native.get('metrics',{})
    if (not native.get('inference_tasks') and not native.get('claims')
            and m.get('llm_calls',0)==0 and not m.get('known_llm_calls',0)
            and not m.get('unknown_inference_attempts',0)):
        return deepcopy(native)
    tasks = native.get('inference_tasks',[])
    runtime = 'passed' if tasks and all(t.get('output_validation')=='passed' for t in tasks) else 'rejected'
    gate = {'status':'needs_review', 'answer_accepted':False,
            'runtime_validation':runtime, 'claims':[], 'reviewer':None,
            'review_error':'captured_anchor_binding_and_explicit_human_review_required',
            'automatic_semantic_entailment':False, 'completeness':'evaluated_separately'}
    return _public(native,gate)


def publish_verified(output, review=None, *, authorities=None):
    """Verify immutable native envelope and review BEFORE releasing any text."""
    from anchor_acceptance import verify_envelope
    verify_envelope(output,review,authorities=authorities)
    gate=output['semantic_acceptance']
    accepted = gate['answer_accepted'] and gate['runtime_validation']=='passed'
    anchors=output['source_anchors']; claims=output['claims']
    if accepted:
        expected={a['claim_id']:a for a in anchors}
        states={c['claim_id']:c for c in gate['claims']}
        if (not claims or len(claims)!=len(expected) or len({c['id'] for c in claims})!=len(claims)
                or {c['id'] for c in claims}!=set(expected)):
            raise ValueError('publication_claim_set_mismatch')
        for c in claims:
            a=expected[c['id']]
            if (a['exact_anchor_check']!='passed' or not a['in_answer']
                    or c['text']!=a['text'] or c['evidence_ids']!=[a['evidence_id']]
                    or states[c['id']]['status']!='supported'
                    or states[c['id']]['binding_sha256']!=a['binding_sha256']):
                raise ValueError('publication_claim_anchor_mismatch')
        if not gate['reviewer'] or gate['reviewer']['kind']!='human':
            raise ValueError('publication_requires_explicit_human_review')
    return _public(output,gate,accepted=accepted,anchors=anchors,
                   binding=output['anchor_binding']['binding_sha256'])


def render_verified(output,review=None,*,authorities=None,format='json'):
    """Both supported renderers recompute the same gate; no native-answer path."""
    public=publish_verified(output,review,authorities=authorities)
    if format=='json':return json.dumps(public,ensure_ascii=True,sort_keys=True)
    if format=='text':return public['answer']
    raise ValueError('unsupported_publication_format')
