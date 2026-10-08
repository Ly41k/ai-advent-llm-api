"""Conservative offline checks; passing is NOT semantic entailment or approval."""
import hashlib
import json
from pathlib import Path
import re

from policy import is_periodic, is_verification_question, russian

REVISION = 'procedure-evidence-guard-v6'


def normalized(text):
    return ' '.join(text.split())


def supported_literal(literal, quote):
    """Ignore whitespace, preserve names/case, require token boundaries."""
    literal, quote = normalized(literal.strip('`')), normalized(quote)
    if not literal:
        return True
    left = r'(?<![\w.-])' if '/' not in literal else r'(?<![\w./-])'
    return bool(re.search(left + re.escape(literal) + r'(?![\w./-])', quote))


def technical_fragments(statement, catalog):
    items = set(re.findall(r'`([^`\n]+)`', statement))
    items.update(re.findall(r'(?<![\w./-])[\w./-]+\.(?:py|db|sqlite3?|service|json|ya?ml|sh)\b', statement))
    items.update(re.findall(r'\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b', statement))
    # Recognize tool names from the actual catalog, even if the model omits ticks.
    identifiers = set(re.findall(r'\b[a-z][a-z0-9]+_[a-z0-9_]+\b', '\n'.join(q['quote'] for q in catalog)))
    items.update(x for x in identifiers if re.search(r'(?<!\w)' + re.escape(x) + r'(?!\w)', statement))
    # Shell executable names come from source fences, not a task-specific list.
    executables = set()
    for q in catalog:
        for block in re.findall(r'```(?:bash|sh|shell|console)\s*\n(.*?)```', q['quote'], re.S):
            for line in block.splitlines():
                tokens = line.strip().split()
                if tokens and not tokens[0].startswith('#'):
                    executables.add(tokens[1] if tokens[0] == 'sudo' and len(tokens) > 1 else tokens[0])
    for executable in executables:
        pattern = r'(?<![\w./-])' + re.escape(executable) + r'\s+(?:[-\w./=]+\s*)+'
        for m in re.finditer(pattern, statement):
            fragment = m[0].strip().rstrip('.')
            # Stop on prose words (Cyrillic) and sentence delimiters. Unquoted
            # English commands are checked conservatively up to known flags.
            fragment = re.split(r'\s+(?=[А-Яа-яЁё])|\s+(?=(?:and|or|to|for|with|then|using|from|the|in|on|as|is|are|can|shows|lets|which|that|after|before)\b)', fragment, maxsplit=1)[0]
            items.add(fragment)
    return sorted(items)


def features(text):
    t = text.casefold()
    return {
        'process_state': bool(re.search(r'\bstatus\b|is-active|состояни\w*|статус\w*|process (?:state|running)', t)),
        'logs': bool(re.search(r'journal|\blogs?\b|журнал\w*', t)),
        'execution_result': bool(re.search(r'сводк\w*|снимк\w*|snapshot\w*|summar\w*|результат\w*|result\w*|архив\w*|backup\w*', t)),
        'recurrence': bool(re.search(r'повтор\w*|нов\w*\s+(?:снимк|сводк|запис)|кажд\w*\s+(?:запуск|выполн)|после каждого|интервал\w*|расписан\w*|период\w*|recurr\w*|repeated|successive|each run|new (?:snapshot|record)|interval|schedule', t)),
    }


def inspect(envelope):
    prepared, row = envelope['prepared'], envelope['result']
    question = prepared['question']
    result = {'case_id': envelope['identity']['case']['id'], 'profile': envelope['identity']['profile_name'],
              'job_key': envelope['job_key'], 'trial': envelope['trial'],
              'raw_answer_sha256': hashlib.sha256(row.get('generation', {}).get('answer', '').encode()).hexdigest(),
              'checks': [], 'issues': [], 'human_semantic_review_required': True,
              'semantically_verified': False, 'automatic_publication_allowed': False}
    if row.get('status') != 'ok':
        result.update(decision='blocked', issues=[{'kind': 'incomplete_observation', 'status': row.get('status')}])
        return result
    if not row.get('generation_called'):
        result.update(decision='ready_for_manual_review', coverage=None, note='No-generation refusal; answerability is not inferred from the rubric.')
        return result
    raw = json.loads(row['generation']['answer'])
    if raw.get('abstained'):
        result.update(decision='ready_for_manual_review', coverage=None, note='Refusal remains unchanged; a human must assess whether evidence was sufficient.')
        return result
    catalog = prepared['quote_catalog']
    by_id = {q['quote_id']: q for q in catalog}
    claims = raw.get('claims')
    if not isinstance(claims, dict):
        result.update(decision='blocked', issues=[{'kind': 'unsupported_contract_for_claim_audit'}])
        return result
    combined = {key: False for key in features('')}
    for slot, claim in claims.items():
        if claim is None:
            continue
        statement, qid = claim['statement'], claim['quote_id']
        q = by_id.get(qid)
        if q is None:
            result['issues'].append({'kind': 'unknown_quote', 'slot': slot, 'quote_id': qid})
            continue
        literals = technical_fragments(statement, catalog)
        absent = [x for x in literals if not supported_literal(x, q['quote'])]
        check = {'slot': slot, 'quote_id': qid, 'technical_fragments': literals, 'unsupported': absent}
        result['checks'].append(check)
        if absent:
            result['issues'].append({'kind': 'unsupported_technical_fragment', 'slot': slot, 'quote_id': qid, 'fragments': absent})
        if is_verification_question(question):
            sf, qf = features(statement), features(q['quote'])
            for key in combined:
                combined[key] |= sf[key] and qf[key]
            # An imperative connecting a status operation to execution is an
            # identifiable bad inference. Mentioning its LIMIT does not trigger.
            if re.search(r'\bstatus\b|is-active', statement, re.I) and re.search(
                    r'(?:провер\w*|подтверд\w*)\s+(?:\w+\s+){0,2}(?:выполнени\w*|запуск\w*)\s+.*?(?:через|помощью)|'
                    r'(?:verify|confirm|prove)\s+(?:\w+\s+){0,3}(?:execution|runs?)\s+.*?(?:using|with|via)', statement, re.I):
                result['issues'].append({'kind': 'process_status_is_not_execution_proof', 'slot': slot, 'quote_id': qid})
            if russian(question) and not russian(statement):
                result['issues'].append({'kind': 'answer_language_mismatch', 'slot': slot})
    if is_verification_question(question):
        result['coverage'] = {'kind': 'conservative_lexical_procedure_check', **combined, 'periodic_requested': is_periodic(question)}
        if is_periodic(question):
            required = ['execution_result', 'recurrence']
            available = features('\n'.join(q['quote'] for q in catalog))
            required += [k for k in ('process_state', 'logs') if available[k]]
            missing = [k for k in required if not combined[k]]
            if missing:
                result['issues'].append({'kind': 'incomplete_periodic_procedure', 'missing': missing})
    else:
        result['coverage'] = None
    result['decision'] = 'blocked' if result['issues'] else 'ready_for_manual_review'
    return result


def audit(report, report_path):
    policy_files = [Path(__file__), Path(__file__).with_name('policy.py')]
    policy_hash = hashlib.sha256(b''.join(p.read_bytes() for p in policy_files)).hexdigest()
    rows = [inspect(e) for e in report['observations']]
    return {'protocol': REVISION, 'origin': 'offline_reanalysis_of_original_live_observations',
            'source_report': str(report_path), 'source_report_sha256': hashlib.sha256(Path(report_path).read_bytes()).hexdigest(),
            'audit_policy_sha256': policy_hash, 'source_responses_modified': False,
            'additional_model_calls': 0, 'human_semantic_review_required': True,
            'semantically_verified': False, 'automatic_publication_allowed': False,
            'limitations': ['Checks detect concrete technical-binding defects and selected coverage gaps.',
                            'Lexical coverage and supported technical literals do not prove all natural-language entailment.',
                            'No repairs, substituted citations, invented claims or hidden regeneration.'],
            'state': report['state'], 'missing_observations': len(report['profiles']) * len(report['cases']) * report['repeats'] - len(rows),
            'summary': {name: {'observations': sum(r['profile'] == name for r in rows),
                              'blocked': sum(r['profile'] == name and r['decision'] == 'blocked' for r in rows),
                              'ready_for_manual_review': sum(r['profile'] == name and r['decision'] == 'ready_for_manual_review' for r in rows)}
                        for name in report['profiles']}, 'observations': rows}


def markdown(value):
    lines = ['# Day 29 — independent quality checks V6', '',
             'These are conservative offline checks, not a semantic approval. Original responses are unchanged.', '',
             '| Profile | Observations | Blocked | Ready for manual review |', '|---|---:|---:|---:|']
    for name, s in value['summary'].items():
        lines.append(f"| {name} | {s['observations']} | {s['blocked']} | {s['ready_for_manual_review']} |")
    lines += ['', '## Detected issues', '']
    for row in value['observations']:
        if row['issues']:
            lines.append(f"- {row['profile']} / {row['case_id']} / trial {row['trial']}: " + json.dumps(row['issues'], ensure_ascii=False))
    return '\n'.join(lines) + '\n'
