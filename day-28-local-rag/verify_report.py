"""Recheck a saved live report's pairing, citations, completeness and metrics.

This checks internal consistency, not authenticity or semantic entailment.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

from bridge28 import OllamaProvider, model_matches
from cloud28 import OpenAIProvider
from rag28 import parse_answer, prepare_synthesis, quality, summarize
from quotes28 import catalog_for, model_excerpts
from prompts28 import coverage_prompt, complete_prompt, phase_prompt


def verify(report, require_success=True):
    errors = []
    if report.get('mode') != 'live' or report.get('state') not in (('completed',) if require_success else ('completed', 'interrupted')):
        errors.append('A completed live report is required.')
    if report.get('command') not in ('ask', 'evaluate', 'compare'):
        errors.append('Use an inference/evaluation report, not doctor.')
    settings = report['settings']
    if report.get('schema_version', 0) == 13:
        if settings.get('quality_mode') != 'coverage' or report.get('quality_mode') != 'coverage':
            errors.append('V13 quality mode differs from settings.')
        revision = 'coverage_then_synthesis_v13' if settings.get('synthesis') else 'coverage_v13'
        if report.get('prompt_revision') != revision:
            errors.append('V13 prompt revision differs from settings.')
    elif report.get('schema_version', 0) in (14, 15):
        expected_revision = ('focused_complete_answer_v15' if report['schema_version'] >= 15
                             else 'complete_answer_v14')
        if (settings.get('quality_mode') != 'complete' or report.get('quality_mode') != 'complete'
                or settings.get('synthesis') or report.get('synthesis_mode')
                or report.get('prompt_revision') != expected_revision):
            errors.append('Complete answer mode/revision differs from settings.')
    elif report.get('schema_version', 0) >= 16:
        if (settings.get('quality_mode') != 'phases' or report.get('quality_mode') != 'phases'
                or settings.get('synthesis') or report.get('synthesis_mode')
                or report.get('prompt_revision') != 'before_after_evidence_v16'):
            errors.append('Before/after answer mode/revision differs from settings.')
    if report.get('schema_version', 0) >= 12:
        cloud_api = settings.get('cloud_provider')
        if cloud_api not in ('groq', 'openai') or report.get('cloud_api') != cloud_api:
            errors.append('Cloud API provenance differs from settings.')
        if cloud_api == 'openai' and settings['cloud_model'] not in OpenAIProvider.models:
            errors.append('OpenAI requires an explicit supported model snapshot.')
        if 'cloud' in report['provider_names'] and report.get('providers', {}).get('cloud', {}).get('cloud_api') != cloud_api:
            errors.append('Cloud preflight API differs from settings.')
        preflight = report.get('providers', {}).get('cloud', {})
        if cloud_api == 'openai' and preflight.get('ready') and (
                preflight.get('url') != OpenAIProvider.url or preflight.get('model') != settings['cloud_model']):
            errors.append('OpenAI preflight endpoint/model snapshot differs from settings.')
    # Constructor validates local URL/model without making requests.
    OllamaProvider(settings['local_model'], settings['url'])
    OllamaProvider(settings['embedding_model'], settings['url'])
    if not report.get('index', {}).get('read_only'):
        errors.append('Missing read-only Week 6 index verification.')
    health = report.get('providers', {}).get('local', {})
    if 'local' in report['provider_names'] and (not health.get('ready') or not health.get('installed')):
        errors.append('Missing local provider preflight.')
    if not report.get('embedding_provider', {}).get('installed'):
        errors.append('Missing local embedding preflight.')
    traces = {}
    for trace in report['retrievals']:
        key = (trace['case_id'], trace['trial'])
        if key in traces:
            errors.append(f'Duplicate retrieval trace: {key}.')
        traces[key] = trace
        if 'error' in trace:
            errors.append(f'Retrieval failed: {key}.')
            continue
        messages = trace['messages']
        if report.get('schema_version', 0) == 13 and (
                trace.get('quality_mode') != 'coverage' or messages[0]['content'] != coverage_prompt()):
            errors.append(f'V13 selection prompt differs from quality mode: {key}.')
        elif report.get('schema_version', 0) in (14, 15) and (
                trace.get('quality_mode') != 'complete'
                or messages[0]['content'] != complete_prompt('v15' if report['schema_version'] >= 15 else 'v14')
                or trace.get('output_contract') != 'quote_slots_v4'
                or (report['schema_version'] >= 15 and trace.get('answer_prompt_revision') != 'v15')):
            errors.append(f'Complete final answer prompt differs from quality mode/revision: {key}.')
        elif report.get('schema_version', 0) >= 16 and (
                trace.get('quality_mode') != 'phases' or messages[0]['content'] != phase_prompt()
                or trace.get('output_contract') != 'phase_evidence_v16'):
            errors.append(f'Before/after answer prompt differs from quality mode/revision: {key}.')
        digest = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if digest != trace['prompt_sha256']:
            errors.append(f'Prompt hash mismatch: {key}.')
        user = json.loads(messages[1]['content'])
        expected_context = trace['excerpts']
        if 'quote_catalog' in trace:
            if catalog_for(trace['excerpts'], trace.get('quote_catalog_style', 'lines_v2')) != trace['quote_catalog']:
                errors.append(f'Quotation catalog differs from source text: {key}.')
            expected_context = model_excerpts(trace['excerpts'], trace['quote_catalog'],
                                             trace.get('model_context_style', 'markers_v2'))
        expected_user = {'question': trace['question'], 'excerpts': expected_context}
        if report.get('schema_version', 0) >= 14:
            expected_user['contract'] = ('phase_evidence_v16' if report['schema_version'] >= 16 else 'quote_slots_v4')
        if user != expected_user:
            errors.append(f'Prompt/excerpt mismatch: {key}.')
        selected = {h['chunk_id']: h for h in trace['retrieval']['sources']}
        for excerpt in trace['excerpts']:
            expected = {k: v for k, v in excerpt.items() if k != 'excerpt'}
            if selected.get(excerpt['chunk_id']) != expected:
                errors.append(f'Excerpt differs from selected source: {key}.')
        if not math.isfinite(trace['retrieval_seconds']) or trace['retrieval_seconds'] < 0:
            errors.append(f'Invalid retrieval timing: {key}.')
    cases = {c['id']: c for c in report['cases']}
    observations = set()
    for row in report['results']:
        key = (row['case_id'], row['trial'])
        identity = (*key, row['provider'])
        if identity in observations:
            errors.append(f'Duplicate observation: {identity}.')
        observations.add(identity)
        if report.get('schema_version', 0) >= 12 and row['provider'] == 'cloud' and row.get('cloud_api') != settings['cloud_provider']:
            errors.append(f'Cloud observation API differs from settings: {identity}.')
        trace = traces.get(key)
        if row['status'] != 'ok':
            if require_success:
                errors.append(f'Unsuccessful observation: {identity}.')
            continue
        if trace is None or trace.get('error'):
            errors.append(f'Observation has no valid retrieval: {identity}.')
            continue
        if trace['question'] != cases[row['case_id']]['question']:
            errors.append(f'Retrieval question differs from case: {identity}.')
        if row['prompt_sha256'] != trace['prompt_sha256']:
            errors.append(f'Local/cloud prompt mismatch: {identity}.')
        if row['generation_called'] != bool(trace['excerpts']):
            errors.append(f'Generation/no-context mismatch: {identity}.')
        if row['generation_called']:
            if not row['generation']['complete']:
                errors.append(f'Incomplete generation: {identity}.')
            if settings.get('cloud_provider') == 'openai' and row['provider'] == 'cloud' and (
                    row['generation']['model'] != settings['cloud_model'] or row['generation']['provider'] != 'cloud'):
                errors.append(f'OpenAI generation model/provider differs from settings: {identity}.')
            if 'synthesis' in row:
                selection = row['selection_generation']
                if not report.get('synthesis_mode') or not selection['complete'] or row.get('generation_calls') != 2:
                    errors.append(f'Invalid two-stage generation provenance: {identity}.')
                if row.get('selection_output_contract') != trace['output_contract'] or row.get('output_contract') != 'quote_slots_v4':
                    errors.append(f'Selection/final output contract mismatch: {identity}.')
                if not model_matches(selection['model'], row['model']) or selection['provider'] != row['provider']:
                    errors.append(f'Selection provider/model differs from synthesis: {identity}.')
                if not model_matches(row['generation']['model'], row['model']) or row['generation']['provider'] != row['provider']:
                    errors.append(f'Final synthesis provider/model mismatch: {identity}.')
                selected = parse_answer(selection['answer'], trace['excerpts'], trace['quote_catalog'], trace['output_contract'])
                if selected != row['selection_response']:
                    errors.append(f'Selection raw/parsed mismatch: {identity}.')
                expected_synthesis = prepare_synthesis(trace, selection['answer'])
                if expected_synthesis != row['synthesis']:
                    errors.append(f'Synthesis prompt/evidence differs from selection: {identity}.')
                value = parse_answer(row['generation']['answer'], trace['excerpts'], expected_synthesis['quote_catalog'],
                                     expected_synthesis['output_contract'])
            else:
                value = parse_answer(row['generation']['answer'], trace['excerpts'], trace.get('quote_catalog'),
                                     trace.get('output_contract'))
                if report.get('synthesis_mode') and (row.get('generation_calls') != 1 or not value['abstained']):
                    errors.append(f'Missing synthesis for a factual selected answer: {identity}.')
        else:
            value = {'answer': 'I do not know from these excerpts.', 'abstained': True, 'citations': []}
            if report.get('synthesis_mode') and row.get('generation_calls') != 0:
                errors.append(f'Empty context must make no model calls: {identity}.')
        if value != row['response']:
            errors.append(f'Parsed/raw answer mismatch: {identity}.')
        if quality(cases[row['case_id']], value, trace['excerpts']) != row['quality']:
            errors.append(f'Quality check mismatch: {identity}.')
        sources = [{**next(x for x in trace['excerpts'] if x['excerpt'] == c['excerpt']), 'quote': c['quote']}
                   for c in value['citations']]
        if sources != row['sources']:
            errors.append(f'Published source metadata mismatch: {identity}.')
        requested_model = settings['local_model'] if row['provider'] == 'local' else settings['cloud_model']
        if not model_matches(row['model'], requested_model):
            errors.append(f'Unexpected provider model: {identity}.')
        if row['provider'] == 'local' and row['generation_called']:
            loaded = any(model_matches(x.get('name') or x.get('model'), requested_model)
                         for x in row.get('running_models_after', []))
            if row.get('local_model_loaded') != loaded:
                errors.append(f'Local loaded flag differs from running models: {identity}.')
    recomputed = summarize(deepcopy(report))
    for field in ('summary', 'retrieval_summary', 'local_rag_verified', 'all_checks_passed'):
        if recomputed[field] != report.get(field):
            errors.append(f'Saved {field} differs from recomputed result.')
    if require_success and (('local' in report['provider_names'] and not recomputed['local_rag_verified']) or not recomputed['all_checks_passed']):
        errors.append('Local inference or complete quality/error checks were not verified.')
    expected = {(c['id'], trial, name) for c in report['cases']
                for trial in range(1, report['planned_trials'] + 1) for name in report['provider_names']}
    if 'planned_observations' in report:
        planned = report['planned_observations']
        identities = [(x['case_id'], x['trial'], x['provider']) for x in planned]
        if len(set(identities)) != len(identities) or not set(identities).issubset(expected):
            errors.append('Invalid selective observation plan.')
        expected = set(identities)
        pairs = {(cid, name) for cid, _, name in identities}
        if expected != {(cid, t, name) for cid, name in pairs
                        for t in range(1, report['planned_trials'] + 1)}:
            errors.append('Selective pairs must include every requested trial.')
        if planned != report.get('retry', {}).get('planned_observations'):
            errors.append('Selective plan differs from saved retry provenance.')
        if report.get('scope') != 'selective_retry' or not report.get('retry', {}).get('source_sha256'):
            errors.append('Selective run needs baseline provenance and explicit scope.')
        if {c for c, _, _ in expected} != set(cases) or {p for _, _, p in expected} != set(report['provider_names']):
            errors.append('Selective plan differs from cases/providers.')
    if (observations != expected if report['state'] == 'completed' else not observations.issubset(expected)):
        errors.append('Observation set differs from planned cases/trials/providers.')
    if report['state'] == 'completed' and set(traces) != {(c, t) for c, t, _ in expected}:
        errors.append('Retrieval trace set differs from planned observations.')
    return {'passed': not errors, 'errors': errors,
            'scope': report.get('scope', 'full_run'),
            'note': 'Internal consistency checks only; manually review semantic support and answer quality.'}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(json.loads(args.report.read_text(encoding='utf-8')))
    except (ValueError, KeyError, TypeError, IndexError, OSError, RuntimeError) as error:
        result = {'passed': False, 'errors': [f'Cannot verify report: {error}']}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
