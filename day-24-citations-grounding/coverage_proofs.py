"""Application-owned proof units for extractive answer coverage, not truth labels."""
import json
import re

from evidence import EvidenceError, keys, parse_json, text
from planning import normalize_space

PROOF_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['reason', 'proof_ids', 'covered'], 'properties': {
        'reason': {'type': 'string', 'minLength': 1, 'maxLength': 500},
        'proof_ids': {'type': 'array', 'maxItems': 8, 'items': {'type': 'string'}},
        'covered': {'type': 'boolean'}}}


def build_proofs(claims):
    """Split only exact answer substrings; retain their parent claim and source.

    Sentence/line boundaries make it possible to point at an observed outcome
    separately from a nearby command. Shell-only units are identified locally;
    this narrow filter does not certify that other prose proves an observation.
    """
    rows = {}
    for index, claim in enumerate(claims, 1):
        citation = claim['citations'][0]
        shell = False
        counter = 0
        for line in claim['text'].splitlines():
            stripped = line.strip()
            if stripped.startswith(('```', '~~~')):
                shell = not shell if re.match(r'^(?:```|~~~)(?:bash|sh|shell|console)\b', stripped) or shell else False
                continue
            if not stripped:
                continue
            for sentence in re.split(r'(?<=[.!?])\s+(?=[A-ZА-ЯЁ])', line):
                remaining = sentence.strip()
                while remaining:
                    end = len(remaining) if len(remaining) <= 800 else remaining.rfind(' ', 0, 800)
                    if end <= 0:
                        end = min(800, len(remaining))
                    unit = remaining[:end].strip()
                    remaining = remaining[end:].strip()
                    counter += 1
                    ident = f'p{index}_{counter}'
                    command = shell or bool(re.match(
                        r'^(?:\$\s*)?(?:sudo\s+)?(?:journalctl|systemctl|curl|wget|python\d*|ollama|tail|cat|ls|echo|cd|pip\d*|source|chmod|cp|mkdir)\b', unit))
                    assert unit in claim['text']
                    rows[ident] = {'id': ident, 'text': unit, 'claim_id': index,
                        'quote_id': citation['quote_id'], 'chunk_id': citation['chunk_id'],
                        'command_only': command}
    return rows


def proof_choices(proofs, requirement, previous_rows):
    allowed = dict(proofs)
    if requirement['id'] == 'verification-observation':
        action = next((r for r in previous_rows if r['id'] == 'verification-action'), None)
        action_texts = [p['text'] for p in (action or {}).get('proofs', [])]
        allowed = {i: p for i, p in proofs.items() if not p['command_only'] and not any(
            normalize_space(p['text']) in normalize_space(a) or normalize_space(a) in normalize_space(p['text'])
            for a in action_texts)}
    return allowed


def validate_proof_verdict(raw, requirement, allowed):
    value = parse_json(raw)
    keys(value, ('reason', 'proof_ids', 'covered'))
    text(value['reason'], 500)
    if type(value['covered']) is not bool:
        raise EvidenceError('Coverage covered must be boolean')
    ids = value['proof_ids']
    if not isinstance(ids, list) or len(ids) > 8 or any(not isinstance(i, str) for i in ids):
        raise EvidenceError('Coverage proof_ids must be a bounded list of strings')
    if len(set(ids)) != len(ids) or any(i not in allowed for i in ids):
        raise EvidenceError('Unknown, duplicate or ineligible coverage proof ID')
    if value['covered'] and not ids:
        raise EvidenceError('A covered requirement needs exact answer proof IDs')
    # False stays false. No selected proof is published for a negative judgment.
    selected = [allowed[i] for i in ids] if value['covered'] else []
    return {'id': requirement['id'], 'reason': value['reason'], 'covered': value['covered'],
            'proof_ids': ids if value['covered'] else [], 'proofs': selected,
            'answer_excerpt': selected[0]['text'] if selected else ''}


def proof_schema(allowed):
    schema = json.loads(json.dumps(PROOF_SCHEMA))
    if allowed:
        schema['properties']['proof_ids']['items']['enum'] = list(allowed)
    else:
        schema['properties']['proof_ids']['maxItems'] = 0
    return schema


def strict_requirements(question):
    """A how question has one full mechanism gate, not two competing ones.

    The all-parts obligation remains inside that gate. Verification questions
    retain overall coverage plus independent action and observed-result checks.
    Historical paraphrase requirements are unchanged.
    """
    from planning import coverage_requirements
    rows = coverage_requirements(question, {'parts': []})
    if any(r['id'] == 'mechanism' for r in rows):
        return [{'id': 'mechanism', 'need':
            'Explain the mechanism or sequence for ALL parts explicitly asked in the original question. '
            'Require concrete operations or rules; only naming a feature, database or identifier is insufficient. '
            'Do not demand details the question did not ask for.'}]
    return rows


def coverage_task(requirement):
    """Task wording isolates each gate; no lesson facts or expected answers."""
    ident = requirement['id']
    if ident == 'verification-observation':
        return (
            'TASK: Identify ONLY the observable outcome that confirms the requested verification succeeded '
            'or failed. Select direct proof units stating an expected output, returned success/failure '
            'flag, saved result or changed state. The question gives topic context only. '
            'Do NOT require the routing, implementation steps, checks or the whole answer in this call: '
            'those are judged by other criteria. A command, comparison action or process liveness is '
            'not an observable result. If recurring behavior is requested, require repeated output/samples.')
    if ident == 'verification-action':
        return (
            'TASK: Identify ONLY the concrete verification checks/actions requested. '
            'Select units that describe what is checked, compared, read, queried or observed. '
            'Do NOT select background routing, server introductions or expected results as actions. '
            'Do NOT require the whole answer or the observable outcome here: other criteria judge them. '
            'The original question gives topic context only.')
    return (
        'TASK: Determine whether the answer supplies ALL information explicitly requested in the '
        'original question. For a mechanism, require the actual operations or rules for every asked '
        'part, not only feature names. Do not invent additional requirements. '
        'If information is missing, name the specific asked part that has no evidence; '
        'a generic statement that the answer is incomplete is not an explanation.')
