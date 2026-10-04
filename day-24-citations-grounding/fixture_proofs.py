"""Legacy authored test verdict adapter. Never imported by production modules."""
from planning import normalize_space


def scripted_proof_response(data, value):
    if not isinstance(value, dict) or set(value) != {'reason', 'answer_excerpt', 'covered'}:
        return value
    excerpt = value['answer_excerpt']
    if type(value['covered']) is not bool or not isinstance(excerpt, str) or len(excerpt) > 800:
        return value
    ids = []
    if value['covered']:
        e = normalize_space(excerpt)
        ids = [p['id'] for p in data['proof_units'] if e and (
            e in normalize_space(p['text']) or normalize_space(p['text']) in e)][:8]
        if not ids:
            ids = ['INVALID_AUTHORED_EXCERPT']
    return {'reason': value['reason'], 'covered': value['covered'], 'proof_ids': ids}
