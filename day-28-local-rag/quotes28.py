"""Application-owned exact quotations and a compact model selection contract."""
import re


ANSWER_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'claims': {'type': 'object', 'additionalProperties': False,
                   'properties': {f'c{i}': {
                       'type': ['object', 'null'], 'additionalProperties': False,
                       'properties': {'quote_id': {'type': 'string'},
                                      'statement': {'type': 'string'}},
                       'required': ['quote_id', 'statement']} for i in range(1, 5)},
                   'required': [f'c{i}' for i in range(1, 5)]},
        'abstained': {'type': 'boolean'},
    },
    'required': ['claims', 'abstained'],
}

SYNTHESIS_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'answer': {'type': 'string'}, 'abstained': {'type': 'boolean'},
        'quote_ids': {'type': 'object', 'additionalProperties': False,
                      'properties': {f'q{i}': {'type': ['string', 'null']} for i in range(1, 5)},
                      'required': [f'q{i}' for i in range(1, 5)]}},
    'required': ['answer', 'abstained', 'quote_ids'],
}

PHASE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'phases': {'type': 'object', 'additionalProperties': False,
                   'properties': {name: {
                       'type': ['object', 'null'], 'additionalProperties': False,
                       'description': ('Checks on the input/request before the central operation starts.'
                                       if name == 'before' else
                                       'Checks on the result after the central operation finishes.'),
                       'properties': {'quote_id': {'type': 'string'},
                                      'statement': {'type': 'string'}},
                       'required': ['quote_id', 'statement']} for name in ('before', 'after')},
                   'required': ['before', 'after']},
        'abstained': {'type': 'boolean'}},
    'required': ['phases', 'abstained'],
}


def section_passages(text, soft_limit=2400):
    """Exact contiguous Markdown sections, respecting headings inside code fences."""
    boundaries, offset, fence = [0], 0, None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            char = marker.group(1)[0]
            fence = None if fence == char else char if fence is None else fence
        elif fence is None and re.match(r'^#{1,6}\s', line) and offset:
            boundaries.append(offset)
        offset += len(line)
    boundaries.append(len(text))
    pieces = []
    for start, end in zip(boundaries, boundaries[1:]):
        block = text[start:end].strip('\r\n')
        if not block.strip() or all(re.match(r'^\s*#{1,6}\s', line)
                                    for line in block.splitlines() if line.strip()):
            continue
        # A soft size bound splits large sections at paragraph boundaries while
        # preserving original whitespace. A single long paragraph stays intact.
        cuts = [0, *(m.end() for m in re.finditer(r'\n\s*\n', block)), len(block)]
        group_start = cuts[0]
        group_end = group_start
        for left, right in zip(cuts, cuts[1:]):
            if group_end > group_start and right - group_start > soft_limit:
                pieces.append(block[group_start:group_end].rstrip('\r\n'))
                group_start = left
            group_end = right
        if block[group_start:group_end].strip():
            pieces.append(block[group_start:group_end].rstrip('\r\n'))
    return pieces


def catalog_for(excerpts, style='lines_v2'):
    catalog = []
    for excerpt in excerpts:
        # Every non-empty source line remains available. Long prose lines are
        # split at sentence boundaries; all pieces are exact source substrings.
        if style == 'sections_v8':
            pieces = section_passages(excerpt['text'])
        elif style == 'passages_v4':
            pieces = []
            # Keep contiguous source paragraphs/code blocks. Strip only standalone
            # Markdown headings and fences, preserving all retained text exactly.
            for block in re.split(r'\n\s*\n', excerpt['text']):
                lines = block.splitlines(keepends=True)
                while lines and re.match(r'^\s*(?:#{1,6}\s|```|~~~)', lines[0]):
                    lines.pop(0)
                while lines and re.match(r'^\s*(?:```|~~~)', lines[-1]):
                    lines.pop()
                text = ''.join(lines).rstrip()
                if text.strip():
                    pieces.append(text)
        elif style == 'lines_v2':
            pieces = [piece.rstrip() for line in excerpt['text'].splitlines()
                      for piece in re.split(r'(?<=[.!?])\s+', line.rstrip()) if piece.strip()]
        else:
            raise ValueError('Unknown quotation catalog style.')
        for number, text in enumerate(pieces, 1):
            catalog.append({'quote_id': f"e{excerpt['excerpt']}-q{number}",
                            'excerpt': excerpt['excerpt'], 'quote': text})
    return catalog


def model_excerpts(excerpts, catalog, style='markers_v2'):
    if style not in ('markers_v2', 'objects_v8'):
        raise ValueError('Unknown model context style.')
    return [{'excerpt': x['excerpt'], 'source': x['source'], 'section': x['section'],
             'quotations': ([{'quote_id': q['quote_id'], 'quote': q['quote']} for q in catalog
                             if q['excerpt'] == x['excerpt']] if style == 'objects_v8' else
                            '\n'.join(f"[{q['quote_id']}] {q['quote']}" for q in catalog
                                      if q['excerpt'] == x['excerpt']))}
            for x in excerpts]


def resolve_selection(value, catalog, contract=None):
    if contract == 'phase_evidence_v16':
        if not isinstance(value, dict) or set(value) != {'phases', 'abstained'}:
            raise ValueError('Phase answer requires exactly phases and abstained.')
        phases = value['phases']
        if not isinstance(phases, dict) or set(phases) != {'before', 'after'}:
            raise ValueError('Phase answer requires exactly before and after.')
        if value['abstained'] is False and any(phases[name] is None for name in ('before', 'after')):
            raise ValueError('A factual phase answer requires both before and after evidence.')
        # Reuse exact evidence binding, boolean validation, abstention handling,
        # and distinct-ID validation without inventing or rewriting statements.
        return resolve_claims({'claims': {'c1': phases['before'], 'c2': phases['after'],
                                          'c3': None, 'c4': None},
                               'abstained': value['abstained']}, catalog)
    if contract in ('evidence_claims_v7', 'evidence_claims_v8'):
        return resolve_claims(value, catalog, allow_reuse=contract == 'evidence_claims_v8')
    if not isinstance(value, dict) or set(value) != {'answer', 'abstained', 'quote_ids'}:
        raise ValueError('Answer requires exactly answer, abstained, quote_ids.')
    ids = value['quote_ids']
    if isinstance(ids, dict):
        if contract == 'quote_ids_v2':
            raise ValueError('V2 requires a quotation IDs array.')
        if set(ids) != {'q1', 'q2', 'q3', 'q4'} or any(
                x is not None and not isinstance(x, str) for x in ids.values()):
            raise ValueError('quote_ids needs exactly q1, q2, q3, q4, each a string ID or null.')
        ids = [ids[f'q{i}'] for i in range(1, 5) if ids[f'q{i}'] is not None]
    elif contract == 'quote_slots_v4':
        raise ValueError('V4 requires the fixed quotation slots object.')
    if not isinstance(ids, list) or len(ids) > 12 or any(not isinstance(x, str) for x in ids):
        raise ValueError('quote_ids must be an array of at most 12 string IDs.')
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate quotation IDs are invalid.')
    by_id = {q['quote_id']: q for q in catalog}
    if any(x not in by_id for x in ids):
        raise ValueError('Unknown quotation ID.')
    return {'answer': value['answer'], 'abstained': value['abstained'],
            'citations': [{'excerpt': by_id[x]['excerpt'], 'quote': by_id[x]['quote']} for x in ids]}


def resolve_claims(value, catalog, allow_reuse=False):
    """Assemble model-written claims and their exact evidence; never invent claims."""
    if not isinstance(value, dict) or set(value) != {'claims', 'abstained'}:
        raise ValueError('Claim format requires exactly claims and abstained, without a detached answer.')
    slots = value['claims']
    if type(value['abstained']) is not bool or not isinstance(slots, dict) or set(slots) != {
            f'c{i}' for i in range(1, 5)}:
        raise ValueError('Claim format requires a boolean abstained and exactly c1, c2, c3, c4.')
    claims = [slots[f'c{i}'] for i in range(1, 5) if slots[f'c{i}'] is not None]
    if value['abstained']:
        if claims:
            raise ValueError('An abstention cannot contain claims or evidence.')
        return {'answer': 'I do not know from these excerpts.', 'abstained': True, 'citations': []}
    if not claims:
        raise ValueError('A factual answer requires at least one evidence-bound claim.')
    by_id = {q['quote_id']: q for q in catalog}
    seen, statements, citations = set(), [], []
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {'quote_id', 'statement'}:
            raise ValueError('Each claim requires exactly quote_id and statement.')
        qid, statement = claim['quote_id'], claim['statement']
        if not isinstance(qid, str) or qid not in by_id:
            raise ValueError('Unknown claim quotation ID.')
        if qid in seen and not allow_reuse:
            raise ValueError('Duplicate claim quotation IDs are invalid.')
        if not isinstance(statement, str) or not statement.strip():
            raise ValueError('A claim statement must be nonempty text.')
        seen.add(qid)
        statements.append(statement.strip())
        quote = by_id[qid]
        citations.append({'excerpt': quote['excerpt'], 'quote': quote['quote']})
    return {'answer': '\n'.join(statements), 'abstained': False, 'citations': citations}
