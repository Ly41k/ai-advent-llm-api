"""Experiment identity, context guards, completion validation and honest summaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from time import perf_counter
from bridge29 import ROOT, prepare, parse_answer, quality, percentile, model_matches, ProviderError
from prompts29 import COMPACT
from provider29 import usage
from store29 import digest, now

PROTOCOL = 'day29-v1'


def code_fingerprint():
    files = []
    for directory in ('day-21-document-indexing', 'day-23-reranking-filtering',
                      'day-26-local-llm', 'day-28-local-rag', 'day-29-local-llm-optimization'):
        for path in sorted((ROOT / directory).glob('*.py')):
            if not path.name.startswith('test'):
                files.append([path.relative_to(ROOT).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()])
    return digest(files)


def load_profiles(path):
    result = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(result, dict) or not result:
        raise ValueError('Profiles must be a non-empty object.')
    for name, profile in result.items():
        if not isinstance(name, str) or not name or not isinstance(profile, dict):
            raise ValueError('Invalid profile name/object.')
        if set(profile) != {'model', 'temperature', 'max_tokens', 'num_ctx', 'prompt'}:
            raise ValueError(f'{name}: profile requires model, temperature, max_tokens, num_ctx, prompt.')
        if not isinstance(profile['model'], str) or not profile['model'].strip() or 'cloud' in profile['model'].lower():
            raise ValueError('A downloaded local model is required.')
        temp = profile['temperature']
        if type(temp) not in (int, float) or not 0 <= temp <= 2:
            raise ValueError('Temperature must be finite and in [0, 2].')
        if any(type(profile[k]) is not int or profile[k] <= 0 for k in ('max_tokens', 'num_ctx')):
            raise ValueError('Token settings must be positive integers.')
        if profile['max_tokens'] + 128 >= profile['num_ctx']:
            raise ValueError('Context must leave room for input plus output.')
        if profile['prompt'] not in ('baseline', 'compact'):
            raise ValueError('Prompt must be baseline or compact.')
    return result


def evidence_payload(prepared):
    return {k: prepared[k] for k in ('question', 'excerpts', 'quote_catalog', 'output_contract')}


def prompt_for(prepared, profile):
    result = deepcopy(prepared)
    if profile['prompt'] == 'compact':
        result['messages'][0]['content'] = COMPACT
    result['prompt_sha256'] = digest(result['messages'])
    return result


def identity_for(case, profile_name, profile, prepared, environment, series, seed, interval):
    # Actual prompts, evidence, rubric, model weights, runtime, hardware, context and
    # seed schedule all participate. Timestamps and retrieval timing do not.
    return {'protocol': PROTOCOL, 'origin': 'live', 'profile_name': profile_name,
            'profile': profile, 'case': case, 'evidence_sha256': digest(evidence_payload(prepared)),
            'prompt_sha256': digest(prepared['messages']), 'environment': environment,
            'series': series, 'seed_base': seed, 'sample_interval': interval}


def validate_envelope(envelope):
    identity = envelope['identity']
    if envelope['job_key'] != digest(identity) or identity.get('protocol') != PROTOCOL:
        raise ValueError('Invalid Day 29 identity.')
    if identity.get('origin') != 'live' or type(envelope['trial']) is not int or envelope['trial'] <= 0:
        raise ValueError('Only live positive-trial observations can be reused.')
    prepared, row = envelope['prepared'], envelope['result']
    if digest(evidence_payload(prepared)) != identity['evidence_sha256'] or digest(prepared['messages']) != identity['prompt_sha256']:
        raise ValueError('Prepared evidence/prompt checksum mismatch.')
    if prepared['question'] != identity['case']['question'] or envelope['profile'] != identity['profile']:
        raise ValueError('Case/profile binding mismatch.')
    if row.get('status') != 'ok':
        return False
    called = bool(prepared['excerpts'])
    if row.get('generation_called') is not called:
        raise ValueError('Generation flag mismatch.')
    if called:
        generation = row.get('generation', {})
        if (generation.get('provider') != 'local' or not model_matches(generation.get('model'), identity['profile']['model'])
                or not generation.get('complete') or generation.get('finish_reason') != 'stop'
                or not row.get('local_model_loaded')):
            raise ValueError('No complete verified local generation.')
        if row.get('seed') != identity['seed_base'] + envelope['trial'] - 1:
            raise ValueError('Seed schedule mismatch.')
        matching = [x for x in row.get('running_models_after', [])
                    if model_matches(x.get('name') or x.get('model'), identity['profile']['model'])]
        if not matching or any(x.get('digest') != identity['environment']['model_digest'] for x in matching):
            raise ValueError('Loaded model digest differs from experiment identity.')
        response = parse_answer(generation['answer'], prepared['excerpts'], prepared['quote_catalog'], prepared['output_contract'])
        guard = row.get('context_guard', {})
        if (not guard.get('passed') or guard.get('num_ctx') != identity['profile']['num_ctx']
                or generation.get('input_tokens') != guard.get('input_tokens')
                or guard.get('input_tokens', 0) + identity['profile']['max_tokens'] + 128 > identity['profile']['num_ctx']):
            raise ValueError('Missing or incompatible context guard.')
    else:
        response = {'answer': 'I do not know from these excerpts.', 'abstained': True, 'citations': []}
    if response != row.get('response'):
        raise ValueError('Stored response differs from raw model output.')
    if quality(identity['case'], response, prepared['excerpts']) != row.get('quality'):
        raise ValueError('Stored quality differs from current rubric.')
    return True


def reusable(cache, key, trial):
    for envelope in cache.history(key, trial):
        if validate_envelope(envelope):
            return envelope
    return None


def context_guard(cache, provider, prepared, model_metadata, probe_ctx, maintenance):
    """One cached input-token probe per exact model/prompt, separately accounted.

    A byte-level upper bound protects the high-context probe itself from truncation.
    Qwen2 uses byte-level BPE. No question/source is dropped to fit a smaller profile.
    """
    messages = prepared['messages']
    info = model_metadata.get('model_info', {})
    family = model_metadata.get('details', {}).get('family')
    if family != 'qwen2':
        raise ValueError('V1 context guard supports Qwen2 byte-level BPE models only.')
    supported = next((v for k, v in info.items() if k.endswith('.context_length')), None)
    if type(supported) is not int or probe_ctx > supported:
        raise ValueError('Token-check context exceeds the context reported by /api/show.')
    # Include JSON serialization, schema overhead and a generous special-token reserve.
    upper_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + 1024
    if upper_bound + 128 >= probe_ctx:
        raise ValueError('Prompt exceeds conservative token-probe bound; use a larger supported --token-check-context or smaller explicit retrieval budget in a new experiment.')
    probe_identity = {'model_digest': model_metadata['digest'], 'model_template_sha256': model_metadata['template_sha256'],
                      'server_version': model_metadata['server_version'], 'prompt': messages,
                      'runtime': code_fingerprint(), 'probe_ctx': probe_ctx}
    key = 'token-check:' + digest(probe_identity)
    existing = cache.get(key)
    if existing is None:
        start = perf_counter()
        attempt = {'kind': 'token_check', 'model': provider.model, 'reused': False, 'status': 'started'}
        maintenance.append(attempt)
        try:
            raw = provider.http.request(provider.url + '/api/chat', {
                'model': provider.model, 'messages': messages, 'stream': False, 'keep_alive': 0,
                'options': {'temperature': 0, 'seed': 42, 'num_predict': 1, 'num_ctx': probe_ctx}})
            attempt['status'] = 'returned'
        except (ProviderError, KeyboardInterrupt) as error:
            attempt.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'error', error=str(error))
            raise
        finally:
            attempt['wall_seconds'] = perf_counter() - start
        if not model_matches(raw.get('model'), provider.model):
            raise ProviderError('Input-token probe returned a different model.')
        count = raw.get('prompt_eval_count')
        if type(count) is not int or count <= 0 or count > upper_bound or count + 128 >= probe_ctx:
            raise ProviderError('Cannot verify the full prompt token count.')
        existing = {'kind': 'token_check', 'model': provider.model, 'input_tokens': count,
                    'probe_context': probe_ctx, 'byte_upper_bound': upper_bound,
                    'wall_seconds': perf_counter() - start, 'usage': usage(raw), 'identity': probe_identity}
        cache.put(key, existing)
        attempt.update(existing, status='ok')
    else:
        maintenance.append({**existing, 'reused': True})
    guard = {'input_tokens': existing['input_tokens'], 'output_reserve': provider.max_tokens,
             'margin': 128, 'num_ctx': provider.num_ctx, 'probe_context': probe_ctx,
             'probe_reused': maintenance[-1]['reused']}
    guard['passed'] = guard['input_tokens'] + guard['output_reserve'] + guard['margin'] <= guard['num_ctx']
    return guard


def observe(provider, prepared, case, guard):
    start = perf_counter()
    row = {'created_at': now(), 'generation_called': bool(prepared['excerpts']), 'status': 'error',
           'context_guard': guard, 'seed': provider.seed}
    try:
        if prepared['excerpts']:
            if not guard['passed']:
                row.update(status='context_overflow', error='Full input plus output reserve does not fit this profile. No answer generation was called.', generation_called=False)
                return row
            row['answer_http_attempted'] = True
            generated = provider.generate(prepared['messages'])
            row.update(generation=generated.to_dict(), ollama_usage=usage(provider.last_raw))
            if not generated.complete:
                row.update(status='incomplete', error='Model did not finish normally; raw output retained.')
                return row
            value = parse_answer(generated.answer, prepared['excerpts'], prepared['quote_catalog'], prepared['output_contract'])
            running = provider.running()
            loaded = any(model_matches(x.get('name') or x.get('model'), provider.model)
                         and x.get('digest') == getattr(provider, 'expected_digest', x.get('digest')) for x in running)
            row.update(running_models_after=running, local_model_loaded=loaded)
            if not loaded:
                row.update(status='unverified', error='Generation returned but loaded model could not be verified.')
                return row
            # Count from the actual answer request must also agree with the full-input probe.
            if generated.input_tokens != guard['input_tokens']:
                row.update(status='context_mismatch', error='Answer input count differs from the untruncated probe.')
                return row
        else:
            value = {'answer': 'I do not know from these excerpts.', 'abstained': True, 'citations': []}
        row.update(status='ok', response=value, quality=quality(case, value, prepared['excerpts']))
    except (ProviderError, ValueError) as error:
        row.update(status='invalid' if isinstance(error, ValueError) else 'error', error=str(error))
    except KeyboardInterrupt:
        # Retain the attempted call as a failed slot instead of losing accounting.
        row.update(status='interrupted', error='Interrupted during local generation; slot remains pending.')
    finally:
        row['generation_wall_seconds'] = perf_counter() - start
        row['retrieval_seconds'] = prepared['retrieval_seconds']
        row['pipeline_seconds'] = row['generation_wall_seconds'] + prepared['retrieval_seconds']
        row['pipeline_note'] = 'Reconstructed from one shared retrieval and this generation; not a fresh end-to-end timing.'
        row['resources'] = provider.resources() if row.get('answer_http_attempted') else {'available': False}
    return row


def summarize(report):
    summary = {}
    for name in report['profiles']:
        entries = [e for e in report['observations'] if e['identity']['profile_name'] == name]
        rows = [e['result'] for e in entries]
        ok = [r for r in rows if r['status'] == 'ok']
        generated = [r for r in ok if r['generation_called']]
        timings = [r['generation_wall_seconds'] for r in generated]
        groups = {}
        for entry in entries:
            groups.setdefault(entry['identity']['case']['id'], []).append(entry['result'])
        complete_groups = [rs for rs in groups.values() if len(rs) == report['repeats'] and all(r['status'] == 'ok' for r in rs)]
        memory = [r['resources'].get('ollama_peak_summed_rss_bytes') for r in generated]
        memory = [x for x in memory if x is not None]
        gpu_memory = [x.get('size_vram') for r in generated for x in r.get('running_models_after', [])
                      if model_matches(x.get('name') or x.get('model'), report['profiles'][name]['model']) and x.get('size_vram') is not None]
        speeds = [r['generation'].get('tokens_per_second') for r in generated if r['generation'].get('tokens_per_second') is not None]
        passed = sum(r.get('quality', {}).get('passed') is True for r in ok)
        summary[name] = {'planned_observations': len(report['cases']) * report['repeats'],
                         'observations_present': len(rows), 'valid': len(ok),
                         'quality_passes': passed, 'quality_denominator': len(rows),
                         'errors_or_incomplete': len(rows) - len(ok),
                         'missing_observations': len(report['cases']) * report['repeats'] - len(rows),
                         'reused_observations': sum(e.get('reused', False) for e in entries),
                         'generated_valid': len(generated), 'application_abstentions': len(ok) - len(generated),
                         'generation_median_seconds': percentile(timings, .5),
                         'generation_p95_seconds': percentile(timings, .95),
                         'median_decode_tokens_per_second': percentile(speeds, .5),
                         'max_observed_summed_rss_bytes': max(memory, default=None),
                         'max_reported_size_vram_bytes': max(gpu_memory, default=None),
                         'complete_repeat_groups': len(complete_groups),
                         'exactly_stable_groups': sum(len({digest(r['response']) for r in rs}) == 1 for rs in complete_groups),
                         'human_review_required': True}
    report['summary'] = summary
    report['new_answer_generation_calls'] = sum(bool(e['result'].get('answer_http_attempted'))
                                              for e in report['observations'] if not e.get('reused'))
    report['maintenance_generation_calls'] = sum(not x.get('reused', False) for x in report.get('maintenance', [])
                                                if x['kind'] in ('token_check', 'warmup'))
    report['all_observations_valid'] = bool(summary) and all(s['missing_observations'] == 0 and s['errors_or_incomplete'] == 0 for s in summary.values())
    report['all_heuristic_checks_passed'] = report['all_observations_valid'] and all(s['quality_passes'] == s['quality_denominator'] for s in summary.values())
    report['optimization_verified'] = False
    report['optimization_note'] = 'Candidates are not declared optimized automatically. Compare fresh matched profiles and manually review support/completeness.'
    return report


def markdown(report):
    lines = ['# Day 29 — local LLM optimization / V1', '',
             f"State: {report['state']}; series: {report['series']}; split: {report['split']}", '',
             'Reused rows retain their original timestamps and measurements. Heuristic quality requires manual review.',
             'Warmups and one-token input probes are accounted separately. Application refusals are excluded from generation speed.', '',
             '| Profile | Quality / present | Valid / planned | Reused | Median seconds | Decode tokens/s | Max sampled RSS GiB |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name, s in report['summary'].items():
        fmt = lambda x: '—' if x is None else f'{x:.2f}'
        rss = s['max_observed_summed_rss_bytes']
        lines.append(f"| {name} | {s['quality_passes']}/{s['quality_denominator']} | {s['valid']}/{s['planned_observations']} | {s['reused_observations']} | {fmt(s['generation_median_seconds'])} | {fmt(s['median_decode_tokens_per_second'])} | {fmt(rss / 2**30 if rss is not None else None)} |")
    lines += ['', 'RSS is a sampled sum, not unique physical memory; do not add it to VRAM on Apple Silicon.',
              'Detailed raw outputs, prompts, sources, context checks, process samples and attempt history are in the JSON.', '']
    for e in report['observations']:
        r = e['result']
        lines += [f"## {e['identity']['profile_name']} / {e['identity']['case']['id']} / {e['trial']}", '',
                  f"Status: {r['status']}; reused: {e.get('reused', False)}", '',
                  r.get('response', {}).get('answer', r.get('error', '')), '',
                  'Human review: support □ completeness □ exact names/conditions □ correct refusal □', '']
        for c in r.get('response', {}).get('citations', []):
            source = next(x for x in e['prepared']['excerpts'] if x['excerpt'] == c['excerpt'])
            lines += [f"Source: {source['source']} / {source['section']}", '', c['quote'], '']
    return '\n'.join(lines)
