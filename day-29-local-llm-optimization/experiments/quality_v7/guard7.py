"""Separate selector/procedure checks plus stricter reanalysis of legacy drafts."""
import hashlib
import json
from pathlib import Path
import re
import runpy
from selection7 import (HERE, PREFIX, ROLES, command_role, decode, render,
                        is_periodic, is_verification_question)

LEGACY = runpy.run_path(str(HERE.parent / 'quality_v6/guard.py'))


def inspect(envelope):
    p, row = envelope['prepared'], envelope['result']
    if not str(p.get('output_contract', '')).startswith(PREFIX):
        value = LEGACY['inspect'](envelope)
        if row.get('status') == 'ok' and row.get('generation_called') and is_verification_question(p['question']) and is_periodic(p['question']):
            raw = json.loads(row['generation']['answer'])
            statements = [x['statement'] for x in raw.get('claims', {}).values() if x]
            missing = []
            # A copied fact about retrying or persistence is not an instruction
            # to inspect successive results. Do not count code-fence words.
            action = r'провер\w*|наблюда\w*|сравн\w*|сопостав\w*|запрос\w*|check|inspect|observe|compare|query|watch'
            procedural = [re.sub(r'```.*?```', '', text, flags=re.S) for text in statements]
            if not any(re.search(action, t, re.I) and re.search(r'сводк|снимк|результат|summary|snapshot|result|backup', t, re.I) for t in procedural):
                missing.append('inspect_execution_results')
            if not any(re.search(action, t, re.I) and re.search(r'повтор|нов\w*\s+(?:снимк|результат)|врем|timestamp|successive|repeated|new (?:snapshot|result)', t, re.I) for t in procedural):
                missing.append('inspect_successive_results_or_timestamps')
            if missing and not raw.get('abstained'):
                value['issues'].append({'kind': 'missing_actual_verification_actions', 'missing': missing})
            commands = []
            for statement in statements:
                for block in re.findall(r'```(?:bash|sh|shell|console)\s*\n(.*?)```', statement, re.S):
                    commands += [x.strip() for x in block.splitlines() if x.strip()]
            mutations = [c for c in commands if re.search(r'\b(?:daemon-reload|enable|disable|restart|reboot|install|stop|start)\b', c)]
            if mutations:
                value['issues'].append({'kind': 'installation_or_mutation_in_observation_procedure', 'commands': mutations})
            if value['issues']:
                value['decision'] = 'blocked'
        return value
    raw = row.get('generation', {}).get('answer', '')
    value = {'case_id': envelope['identity']['case']['id'], 'profile': envelope['identity']['profile_name'],
             'job_key': envelope['job_key'], 'trial': envelope['trial'],
             'raw_answer_sha256': hashlib.sha256(raw.encode()).hexdigest(),
             'contract': p['output_contract'], 'answer_origin': 'application_source_extractive',
             'model_output_kind': 'four_evidence_selections', 'source_responses_modified': False,
             'rendered_answer_characters': len(row.get('response', {}).get('answer', '')),
             'human_semantic_review_required': True, 'semantically_verified': False,
             'automatic_publication_allowed': False, 'issues': []}
    if row.get('status') != 'ok':
        value.update(decision='blocked', issues=[{'kind': 'incomplete_observation', 'status': row.get('status')}])
        return value
    decoded = decode(raw, p['quote_catalog'], p['excerpts'], p['output_contract'])
    expected = render(raw, p['excerpts'], p['quote_catalog'], p['output_contract'])
    value['selected_evidence'] = {role: {'quote_id': u['quote_id'], 'original_quote_id': u['original_quote_id'],
                                       'excerpt': u['excerpt'], 'source': u['source'], 'quote': u['quote']}
                                  for role, u in decoded['selected'].items()}
    value['selection_errors'] = decoded['errors']
    value['model_abstained'] = decoded['model_abstained']
    value['required_roles_present'] = all(role in decoded['selected'] for role in ROLES)
    value['rendered_response_reproducible'] = expected == row.get('response')
    if decoded['errors']:
        value['issues'].append({'kind': 'insufficient_or_invalid_selection', 'errors': decoded['errors']})
    if not value['rendered_response_reproducible']:
        value['issues'].append({'kind': 'rendered_response_mismatch'})
    value['decision'] = 'blocked' if value['issues'] or decoded['model_abstained'] else 'ready_for_manual_review'
    value['note'] = 'Application rendering is explicit. Complete role coverage is not a universal semantic entailment proof.'
    return value


def audit(report, source):
    rows = [inspect(e) for e in report['observations']]
    code = b''.join((HERE / n).read_bytes() for n in ('guard7.py', 'selection7.py'))
    return {'protocol': 'procedure-selection-quality-v7', 'origin': 'offline_reanalysis_of_sealed_observations',
            'source_report': str(source), 'source_report_sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
            'audit_policy_sha256': hashlib.sha256(code).hexdigest(), 'source_responses_modified': False,
            'additional_model_calls': 0, 'human_semantic_review_required': True, 'semantically_verified': False,
            'state': report['state'], 'automatic_publication_allowed': False,
            'missing_observations': len(report['profiles']) * len(report['cases']) * report['repeats'] - len(rows),
            'limitations': ['The procedural model selects evidence; application-owned rendering is not a free-text LLM answer.',
                            'Source units and role candidates use conservative lexical extraction; relevance and adequacy need manual review.',
                            'Legacy lexical coverage is tightened; previous audits and original responses remain historical evidence.'],
            'summary': {name: {'observations': sum(r['profile'] == name for r in rows),
                              'blocked': sum(r['profile'] == name and r['decision'] == 'blocked' for r in rows),
                              'ready_for_manual_review': sum(r['profile'] == name and r['decision'] == 'ready_for_manual_review' for r in rows)}
                        for name in report['profiles']}, 'observations': rows}


def markdown(value):
    lines = ['# Day 29 — V7 independent quality checks', '',
             'The model selects evidence; the application renders the procedure. Manual semantic review is required.', '',
             '| Profile | Observations | Blocked | Ready for review |', '|---|---:|---:|---:|']
    for name, s in value['summary'].items():
        lines.append(f"| {name} | {s['observations']} | {s['blocked']} | {s['ready_for_manual_review']} |")
    for row in value['observations']:
        if row['issues']:
            lines += ['', f"- {row['profile']} / {row['case_id']} / trial {row['trial']}: " + json.dumps(row['issues'], ensure_ascii=False)]
    return '\n'.join(lines) + '\n'
