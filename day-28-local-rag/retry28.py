"""Plan selective retries without inference or editing historical observations."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from rag28 import quality
from verify_report import verify


def retry_plan(path, cases, settings, command, repeats, only_provider=None):
    raw = Path(path).read_bytes()
    baseline = json.loads(raw)
    try:
        checked = verify(baseline, require_success=False)
    except (KeyError, TypeError, IndexError, RuntimeError) as error:
        raise ValueError(f'Cannot inspect baseline report: {error}') from None
    if not checked['passed']:
        raise ValueError('Baseline is internally inconsistent: ' + '; '.join(checked['errors']))
    if (command == 'compare' and only_provider != 'local' and
            settings.get('cloud_provider', 'groq') != baseline['settings'].get('cloud_provider', 'groq')):
        raise ValueError('Retry cloud provider differs from baseline; use a separate new run.')
    for key in ('local_model', 'cloud_model', 'embedding_model', 'strategy', 'candidate_k',
                'final_k', 'min_similarity', 'rewrite', 'max_context_chars', 'num_ctx', 'max_tokens'):
        if settings[key] != baseline['settings'][key]:
            raise ValueError(f'Retry setting {key} differs from baseline; use a separate full run.')
    current = {c['id']: c for c in cases}
    groups = defaultdict(list)
    traces = {(t['case_id'], t['trial']): t for t in baseline['retrievals']}
    for row in baseline['results']:
        groups[(row['case_id'], row['provider'])].append(row)
    old_cases = {c['id']: c for c in baseline['cases']}
    if any(cid not in current or current[cid]['question'] != c['question'] for cid, c in old_cases.items()):
        raise ValueError('Retry questions must retain the baseline IDs and question text.')
    old_plan = baseline.get('planned_observations') or [
        {'case_id': c['id'], 'provider': name, 'trial': trial}
        for c in baseline['cases'] for name in baseline['provider_names']
        for trial in range(1, baseline['planned_trials'] + 1)]
    identities = {(x['case_id'], x['provider']) for x in old_plan}
    pending, assessments = [], []
    for cid, name in sorted(identities):
        if command == 'evaluate' and name != 'local':
            continue
        if only_provider and name != only_provider:
            continue
        rows = groups[(cid, name)]
        reassessed = []
        passed = 0
        for row in rows:
            q = None
            if row['status'] == 'ok':
                q = quality(current[cid], row['response'], traces[(cid, row['trial'])]['excerpts'])
                passed += q['passed'] is True
            if q != row.get('quality'):
                reassessed.append({'trial': row['trial'], 'previous_quality': row.get('quality'), 'current_quality': q})
        expected_trials = {x['trial'] for x in old_plan if (x['case_id'], x['provider']) == (cid, name)}
        complete = {r['trial'] for r in rows} == expected_trials
        retain = complete and passed == len(expected_trials)
        assessment = {'case_id': cid, 'provider': name, 'action': 'retain' if retain else 'rerun',
                      'observations': len(rows), 'current_passes': passed,
                      'rubric_changed': current[cid] != old_cases[cid], 'reassessments': reassessed}
        assessments.append(assessment)
        if not retain:
            pending.extend({'case_id': cid, 'provider': name, 'trial': t} for t in range(1, repeats + 1))
    return {'source_run_id': baseline['run_id'], 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'source_report': str(Path(path).resolve()), 'scope': 'selective_retry',
            'note': 'Historical rows remain unchanged. New metrics describe this subset only. '
                    'An unpaired retry is not a new local/cloud comparison.',
            'assessments': assessments, 'planned_observations': pending,
            'generation_upper_bound': {name: (2 if settings.get('synthesis') else 1) * sum(x['provider'] == name for x in pending)
                                       for name in ('local', 'cloud')}}
