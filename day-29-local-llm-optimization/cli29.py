"""Local-only CLI. Resume is automatic; plan/verify never contact Ollama."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import uuid

from bridge29 import (ROOT, ExistingIndex, LocalEmbeddings, StructuredHTTP, Settings,
                      prepare, ProviderError)
from engine29 import (PROTOCOL, code_fingerprint, load_profiles, prompt_for, identity_for,
                      reusable, context_guard, observe, validate_envelope, summarize, markdown)
from provider29 import MeasuredOllama
from resources29 import machine_identity, psutil
from store29 import Cache, owned_cache, digest, now

HERE = Path(__file__).resolve().parent
DEFAULT_CACHE = HERE / 'cache/experiments.sqlite3'


def positive_int(value):
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError('Must be greater than zero.')
    return n


def positive_float(value):
    n = float(value)
    if not math.isfinite(n) or n <= 0:
        raise argparse.ArgumentTypeError('Must be finite and greater than zero.')
    return n


def atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def seal(report):
    result = deepcopy(report)
    result.pop('integrity_sha256', None)
    result['integrity_sha256'] = digest(result)
    return result


def save(report, output):
    summarize(report)
    atomic_text(output, json.dumps(seal(report), indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    atomic_text(Path(output).with_suffix('.md'), markdown(report))


def read_report(path):
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(report, dict) or report.get('protocol') != PROTOCOL or report.get('mode') != 'live':
        raise ValueError('Only a live Day 29 V1 report can be imported. Day 28 reports use a different identity and are historical evidence only.')
    checksum = report.pop('integrity_sha256', None)
    if checksum != digest(report):
        raise ValueError('Report checksum mismatch; use the original unedited JSON.')
    seen = set()
    for envelope in report.get('observations', []):
        key = (envelope['job_key'], envelope['trial'])
        if key in seen:
            raise ValueError('Duplicate job/trial in report.')
        seen.add(key)
        validate_envelope(envelope)
        name = envelope['identity']['profile_name']
        if (name not in report['profiles'] or envelope['profile'] != report['profiles'][name]
                or envelope['trial'] > report['repeats'] or envelope['identity']['case'] not in report['cases']
                or envelope['identity']['series'] != report['series']):
            raise ValueError('Observation is outside the report scope.')
    expected = deepcopy(report)
    summarize(expected)
    if report.get('summary') != expected['summary']:
        raise ValueError('Report summary is inconsistent with observations.')
    return report


def load_cases(args):
    # Reuse Day 28 validation without importing its generic main module.
    cases = json.loads(args.questions.read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('Questions must be a non-empty array.')
    seen = set()
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id'].strip()
                or case['id'] in seen or not isinstance(case.get('question'), str) or not case['question'].strip()
                or type(case.get('answerable')) is not bool):
            raise ValueError('Invalid/duplicate question id, text or answerable flag.')
        seen.add(case['id'])
        for field in ('expected_terms', 'expected_sources'):
            if not isinstance(case.get(field), list) or any(not isinstance(t, str) or not t.strip() for t in case[field]):
                raise ValueError('Questions require arrays of expected terms and sources.')
        if case['answerable'] and (not case['expected_terms'] or not case['expected_sources']):
            raise ValueError('Answerable questions need a rubric.')
        for field in ('expected_term_groups', 'expected_evidence_groups'):
            groups = case.get(field, [])
            if not isinstance(groups, list) or any(not isinstance(g, list) or not g or
                    any(not isinstance(t, str) or not t.strip() for t in g) for g in groups):
                raise ValueError('Invalid rubric groups.')
    if args.case:
        unknown = set(args.case) - seen
        if unknown:
            raise ValueError('Unknown case IDs: ' + ', '.join(sorted(unknown)))
        cases = [c for c in cases if c['id'] in args.case]
    if args.split != 'all':
        cases = [c for c in cases if c.get('split') == args.split]
    if not cases:
        raise ValueError('No questions match this split/case selection; try --split all.')
    return cases


def parser():
    p = argparse.ArgumentParser(description='Day 29 V1 — local Qwen RAG optimization with resumable three-trial cache')
    commands = p.add_subparsers(dest='command', required=True)
    for name in ('doctor', 'plan', 'run'):
        c = commands.add_parser(name)
        c.add_argument('--profiles-file', type=Path, default=HERE / 'profiles.json')
        c.add_argument('--profiles', nargs='+', default=['baseline', 'candidate-q4'])
        c.add_argument('--questions', type=Path, default=HERE / 'questions.json')
        c.add_argument('--split', choices=('calibration', 'evaluation', 'all'), default='calibration')
        c.add_argument('--case', nargs='+')
        c.add_argument('--repeats', type=positive_int, default=3)
        c.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
        c.add_argument('--db', type=Path, default=ROOT / 'day-21-document-indexing/knowledge.db')
        c.add_argument('--url', default='http://127.0.0.1:11434')
        c.add_argument('--embedding-model', default='bge-m3')
        c.add_argument('--timeout', type=positive_float, default=300)
        c.add_argument('--sample-interval', type=positive_float, default=.5)
        c.add_argument('--seed', type=int, default=42)
        c.add_argument('--series', default='v1')
        c.add_argument('--token-check-context', type=positive_int, default=32768)
        c.add_argument('--max-new-observations', type=positive_int)
        c.add_argument('--retry-from', type=Path, nargs='*', default=[])
        c.add_argument('--output', type=Path)
    for name in ('verify', 'summary'):
        c = commands.add_parser(name)
        c.add_argument('report', type=Path)
    return p


def selection(args):
    all_profiles = load_profiles(args.profiles_file)
    if len(set(args.profiles)) != len(args.profiles):
        raise ValueError('Profile selection contains duplicates.')
    unknown = set(args.profiles) - set(all_profiles)
    if unknown:
        raise ValueError('Unknown profiles: ' + ', '.join(sorted(unknown)))
    return {name: all_profiles[name] for name in args.profiles}, load_cases(args)


def model_metadata(provider):
    info = provider.doctor()
    raw = provider.http.request(provider.url + '/api/show', {'model': provider.model})
    if raw.get('remote_host') or raw.get('remote_model'):
        raise ProviderError('Remote Ollama models are not allowed.')
    if not isinstance(info.get('digest'), str) or not info['digest']:
        raise ProviderError('A model digest is required for reproducible reuse.')
    info['model_info'] = raw.get('model_info', {})
    info['template_sha256'] = digest({'template': raw.get('template'), 'parameters': raw.get('parameters'),
                                    'system': raw.get('system')})
    return info


def retrieval_key(environment, case):
    return 'retrieval:' + digest({'index': environment['index_sha256'],
                                'embedding': environment['embedding_digest'],
                                'runtime': environment['runtime_sha256'], 'question': case['question'],
                                'retrieval': environment['retrieval']})


def job_environment(common, meta):
    return {**common, 'model_digest': meta['digest'], 'model_details': meta['details'],
            'model_template_sha256': meta['template_sha256'], 'ollama_version': meta['server_version']}


def make_jobs(args, profiles, cases, common, metadata, prepared_by_case):
    jobs = {}
    for name, profile in profiles.items():
        for case in cases:
            prepared = prompt_for(prepared_by_case[case['id']], profile)
            identity = identity_for(case, name, profile, prepared, job_environment(common, metadata[profile['model']]),
                                    args.series, args.seed, args.sample_interval)
            jobs[(name, case['id'])] = {'job_key': digest(identity), 'identity': identity,
                                      'profile': profile, 'prepared': prepared}
    return jobs


def import_reports(cache, paths):
    for path in paths:
        report = read_report(path)
        for envelope in report['observations']:
            if validate_envelope(envelope) and reusable(cache, envelope['job_key'], envelope['trial']) is None:
                copy = deepcopy(envelope)
                copy.pop('reused', None)
                copy['imported_from_run_id'] = report['run_id']
                cache.record(copy)


def preview(args, cache, profiles, cases):
    previous = cache.get('environment:last')
    result = {'mode': 'plan', 'http_calls': 0, 'profiles': profiles, 'cases': [c['id'] for c in cases],
              'repeats': args.repeats, 'series': args.series, 'live_verification_pending': True,
              'planned_observations': len(profiles) * len(cases) * args.repeats,
              'note': 'Cached estimates use the last live environment. Run rechecks model/index/runtime before reuse. Warmups and input-token probes are additional, separately reported calls.'}
    counts = {'reuse_estimate': 0, 'new_observations_estimate': 0}
    if previous and previous['common']['runtime_sha256'] == code_fingerprint() and previous['common']['hardware'] == machine_identity():
        preparations = {c['id']: cache.get(retrieval_key(previous['common'], c)) for c in cases}
        if all(preparations.values()) and all(p['model'] in previous['metadata'] for p in profiles.values()):
            jobs = make_jobs(args, profiles, cases, previous['common'], previous['metadata'], preparations)
            for job in jobs.values():
                for trial in range(1, args.repeats + 1):
                    counts['reuse_estimate' if reusable(cache, job['job_key'], trial) else 'new_observations_estimate'] += 1
            result.update(counts)
    if 'reuse_estimate' not in result:
        result.update(reuse_estimate=None, new_observations_upper_bound=result['planned_observations'])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.output:
        atomic_text(args.output, json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    return 0


def live(args, cache, profiles, cases):
    if psutil is None:
        raise ValueError('Install requirements first: psutil is needed to measure resources.')
    providers = {name: MeasuredOllama(profile, args.url, args.timeout, seed=args.seed,
                                    sample_interval=args.sample_interval) for name, profile in profiles.items()}
    kb = ExistingIndex(args.db)
    try:
        verified = kb.verify()
        embedding = LocalEmbeddings(args.embedding_model, args.url, args.timeout,
                                    http=StructuredHTTP(args.timeout, local=True))
        embedding_meta = embedding.doctor()
        if kb.info('fixed')['model'] != args.embedding_model:
            raise ValueError('Embedding model differs from the Day 21 index.')
        metadata = {}
        for provider in providers.values():
            if provider.model not in metadata:
                metadata[provider.model] = model_metadata(provider)
            provider.expected_digest = metadata[provider.model]['digest']
        common = {'index_sha256': hashlib.sha256(args.db.read_bytes()).hexdigest(),
                  'embedding_digest': embedding_meta['digest'], 'embedding_model': args.embedding_model,
                  'embedding_ollama_version': embedding_meta['server_version'],
                  'runtime_sha256': code_fingerprint(), 'hardware': machine_identity(),
                  'python': platform.python_version(), 'psutil': psutil.__version__,
                  'url': args.url, 'timeout': args.timeout,
                  'retrieval': {'strategy': 'fixed', 'candidate_k': 20, 'final_k': 5,
                                'min_similarity': .5, 'rewrite': 'heuristic', 'max_context_chars': 16000}}
        cache.put('environment:last', {'common': common, 'metadata': metadata})
        if args.command == 'doctor':
            print(json.dumps({'ready': True, 'index': verified, 'embedding': embedding_meta,
                              'models': metadata, 'hardware': common['hardware'], 'answer_generation_calls': 0,
                              'resource_sampler': True}, indent=2, ensure_ascii=False))
            if args.output:
                atomic_text(args.output, json.dumps({'ready': True, 'models': metadata, 'index': verified,
                                                    'hardware': common['hardware']}, indent=2, ensure_ascii=False) + '\n')
            return 0
        if args.output is None:
            args.output = HERE / 'reports/check' / (now().replace(':', '-').replace('.', '-') + '.json')
        if args.output.suffix != '.json' or any(args.output.resolve() == p.resolve() for p in args.retry_from):
            raise ValueError('Output must be a new .json, different from every --retry-from input.')
        report = {'protocol': PROTOCOL, 'mode': 'live', 'run_id': str(uuid.uuid4()), 'created_at': now(),
                  'state': 'preparing', 'series': args.series, 'split': args.split, 'repeats': args.repeats,
                  'profiles': profiles, 'cases': cases, 'environment': common, 'model_metadata': metadata,
                  'index_verification': verified, 'observations': [], 'attempt_history': [], 'maintenance': [],
                  'limitations': ['Heuristics and exact quotes require human semantic review.',
                                  'Cached timings retain their original environment/time; this is not a new benchmark.',
                                  'One-token context probes and warmups are additional local generations, never scored answers.',
                                  'Sampled process RSS is not unique physical memory; GPU utilization is unavailable.',
                                  'Three repeats and interpolated p95 describe this small sample only.']}
        save(report, args.output)
        try:
            prepared_by_case = {}
            for case in cases:
                key = retrieval_key(common, case)
                prepared = cache.get(key)
                if prepared is None:
                    prepared = prepare(kb, embedding, case['question'], Settings(20, 5, .5, 'fixed', 'heuristic'))
                    prepared['retrieval_created_at'] = now()
                    cache.put(key, prepared)
                prepared_by_case[case['id']] = prepared
            # Keep embedding residency identical for every answer profile.
            embedding.http.request(embedding.url + '/api/generate', {'model': embedding.model, 'keep_alive': 0})
            jobs = make_jobs(args, profiles, cases, common, metadata, prepared_by_case)
            slot_entries = {}
            for (name, case_id), job in jobs.items():
                for trial in range(1, args.repeats + 1):
                    existing = reusable(cache, job['job_key'], trial)
                    if existing:
                        slot_entries[(name, case_id, trial)] = {**existing, 'reused': True}
            report['observations'] = list(slot_entries.values())
            report['state'] = 'running'
            save(report, args.output)
            total = len(jobs) * args.repeats
            print(f"Plan: {total} observations; reuse {len(slot_entries)}; pending {total - len(slot_entries)}.", flush=True)
            fresh = 0
            guards = {}
            for trial in range(1, args.repeats + 1):
                order = list(profiles) if trial % 2 else list(reversed(profiles))
                for name in order:
                    pending = [c for c in cases if (name, c['id'], trial) not in slot_entries]
                    if not pending:
                        continue  # Critically: no probe or warmup for fully cached profiles.
                    if args.max_new_observations and fresh >= args.max_new_observations:
                        report['state'] = 'paused'
                        save(report, args.output)
                        print(f'Batch limit reached. Resume with the same command. Report: {args.output}')
                        return 0
                    if args.max_new_observations:
                        pending = pending[:args.max_new_observations - fresh]
                    provider = providers[name]
                    # Never keep both selected quantizations loaded at once.
                    for model, meta in metadata.items():
                        if model != provider.model:
                            other = next(p for p in providers.values() if p.model == model)
                            other.unload()
                    # All probes precede this block's warmup, avoiding reloads inside timed answers.
                    probe_failed = {}
                    for case in pending:
                        guard_key = (name, case['id'])
                        if guard_key not in guards and jobs[guard_key]['prepared']['excerpts']:
                            try:
                                guards[guard_key] = context_guard(cache, provider, jobs[guard_key]['prepared'],
                                                                 metadata[provider.model], args.token_check_context,
                                                                 report['maintenance'])
                            except (ProviderError, ValueError) as error:
                                probe_failed[case['id']] = str(error)
                        save(report, args.output)
                    needs_generation = [c for c in pending if c['id'] not in probe_failed and
                                        jobs[(name, c['id'])]['prepared']['excerpts'] and
                                        guards.get((name, c['id']), {}).get('passed')]
                    if needs_generation:
                        warm = {'kind': 'warmup', 'profile': name, 'trial_block': trial, 'reused': False, 'status': 'started'}
                        report['maintenance'].append(warm)
                        try:
                            warm.update(provider.warmup(), status='ok')
                        except (ProviderError, KeyboardInterrupt) as error:
                            warm.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'error', error=str(error))
                            raise
                        save(report, args.output)
                    for case in pending:
                        if args.max_new_observations and fresh >= args.max_new_observations:
                            report['state'] = 'paused'
                            save(report, args.output)
                            print(f'Batch limit reached. Report: {args.output}')
                            return 0
                        job = jobs[(name, case['id'])]
                        provider.seed = args.seed + trial - 1
                        print(f"{name} / {case['id']} / trial {trial}: ", end='', flush=True)
                        if case['id'] in probe_failed:
                            row = {'created_at': now(), 'status': 'preflight_error', 'generation_called': False,
                                   'error': probe_failed[case['id']], 'generation_wall_seconds': 0, 'resources': {'available': False}}
                        else:
                            row = observe(provider, job['prepared'], case, guards.get((name, case['id']), {'passed': True}))
                        envelope = {**deepcopy(job), 'trial': trial, 'result': row, 'reused': False}
                        cache.record(envelope)
                        slot_entries[(name, case['id'], trial)] = envelope
                        report['observations'] = list(slot_entries.values())
                        report['attempt_history'].append({'job_key': job['job_key'], 'trial': trial,
                                                         'prior_attempts': cache.history(job['job_key'], trial)[1:],
                                                         'current_status': row['status']})
                        fresh += 1
                        save(report, args.output)
                        print(f"{row['status']} / quality={row.get('quality', {}).get('passed')}", flush=True)
                        if row['status'] == 'interrupted':
                            report['state'] = 'interrupted'
                            save(report, args.output)
                            print('Interrupted. Completed answers remain cached; interrupted attempt is recorded.', flush=True)
                            return 130
                        if row['status'] in ('error', 'unverified', 'preflight_error'):
                            report['state'] = 'blocked'
                            save(report, args.output)
                            print('Stopped after a technical error; completed observations remain cached.', flush=True)
                            return 1
            report['state'] = 'completed'
            save(report, args.output)
            print(json.dumps(report['summary'], indent=2, ensure_ascii=False))
            print(f"JSON: {args.output}\nMarkdown: {args.output.with_suffix('.md')}")
            return 0 if report['all_heuristic_checks_passed'] else 1
        except KeyboardInterrupt:
            report['state'] = 'interrupted'
            save(report, args.output)
            print(f'Interrupted. Completed observations are cached. Report: {args.output}', flush=True)
            return 130
        except (ProviderError, ValueError, OSError) as error:
            report.update(state='blocked', error=str(error))
            save(report, args.output)
            raise
    finally:
        kb.close()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command in ('verify', 'summary'):
            report = read_report(args.report)
            print(json.dumps({'consistent': True, 'state': report['state'], 'summary': report['summary'],
                              'all_heuristic_checks_passed': report['all_heuristic_checks_passed'],
                              'optimization_verified': False, 'human_review_required': True}, indent=2, ensure_ascii=False))
            return 0  # Structural verifier is deliberately not a semantic quality verdict.
        if not args.series.strip():
            raise ValueError('Series must be non-empty.')
        profiles, cases = selection(args)
        with owned_cache(args.cache):
            cache = Cache(args.cache)
            try:
                import_reports(cache, args.retry_from)
                if args.command == 'plan':
                    return preview(args, cache, profiles, cases)
                return live(args, cache, profiles, cases)
            finally:
                cache.close()
    except (ProviderError, ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f'ERROR — {error}', file=sys.stderr)
        return 1
