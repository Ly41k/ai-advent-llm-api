"""Day 28: local-only default, optional paired Groq comparison."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import uuid

from bridge28 import ROOT, Settings, OllamaProvider, GroqProvider, ProviderError
from cloud28 import OpenAIProvider
from rag28 import ExistingIndex, LocalEmbeddings, StructuredHTTP, prepare, observe, summarize
from retry28 import retry_plan

HERE = Path(__file__).resolve().parent


def positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError('Must be greater than zero.')
    return result


def nonnegative_int(value):
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError('Must be zero or greater.')
    return result


def positive_float(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError('Must be finite and greater than zero.')
    return result


def cosine(value):
    result = float(value)
    if not math.isfinite(result) or not -1 <= result <= 1:
        raise argparse.ArgumentTypeError('Must be finite raw cosine in [-1, 1].')
    return result


def load_cases(path):
    cases = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not cases:
        raise ValueError('Questions must be a non-empty array.')
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id'].strip():
            raise ValueError('Each question needs a non-empty string id.')
        if case['id'] in seen:
            raise ValueError('Question IDs must be unique.')
        seen.add(case['id'])
        if not isinstance(case.get('question'), str) or not case['question'].strip():
            raise ValueError('Each question needs non-empty text.')
        if type(case.get('answerable')) is not bool:
            raise ValueError('Each question needs boolean answerable.')
        for field in ('expected_terms', 'expected_sources'):
            if not isinstance(case.get(field), list) or any(not isinstance(x, str) or not x.strip() for x in case[field]):
                raise ValueError(f'{field} must be an array of non-empty strings.')
        if case['answerable'] and (not case['expected_terms'] or not case['expected_sources']):
            raise ValueError('Answerable cases need expected terms and sources.')
        for field in ('expected_term_groups', 'expected_evidence_groups'):
            groups = case.get(field, [])
            if not isinstance(groups, list) or any(not isinstance(g, list) or not g or
                    any(not isinstance(t, str) or not t.strip() for t in g) for g in groups):
                raise ValueError(f'{field} must contain non-empty arrays of non-empty strings.')
    return cases


def cloud_key(provider='groq'):
    variable = 'OPENAI_API_KEY' if provider == 'openai' else 'GROQ_API_KEY'
    key = os.getenv(variable)
    if key and key.strip():
        return key
    path = ROOT / '.env'
    if path.is_file():
        try:
            from dotenv import load_dotenv
        except ImportError:
            raise ProviderError(f'Install Day 28 requirements or export {variable}.') from None
        load_dotenv(path, override=False)
    return os.getenv(variable)


def atomic_text(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            output.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def markdown(report):
    lines = ['# Day 28 — Local RAG comparison', '', f"Run: {report['run_id']}",
             f"State: {report['state']}; mode: {report['mode']}", '',
             'Heuristic term/source checks and exact quote checks require human semantic review.',
             'Generation timings exclude application abstentions. First trials may include model loading.',
             ('Paired providers share the selection prompt; synthesis evidence and prompts may differ. Pair order alternates. Tokenizers differ.'
              if report.get('synthesis_mode') else
              'Where both providers are scheduled, they share the exact prompt; pair order alternates. Tokenizers differ.'), '',
             '## Summary', '', '```json', json.dumps(report.get('summary', {}), ensure_ascii=False, indent=2), '```', '']
    if report.get('cloud_comparison'):
        lines += [f"Cloud comparison: {report['cloud_comparison']}", '']
    if report.get('scope') == 'selective_retry':
        lines += ['Selective retry: metrics cover only newly requested observations.',
                  'Historical successes remain in the baseline; unpaired results are not a fresh comparison.', '',
                  '```json', json.dumps(report['retry'], ensure_ascii=False, indent=2), '```', '']
    for row in report['results']:
        lines += [f"## {row['provider']} / {row['case_id']} / trial {row['trial']}", '',
                  f"Status: {row['status']}", '',
                  row.get('response', {}).get('answer', row.get('error', '')), '',
                  '```json', json.dumps(row, ensure_ascii=False, indent=2), '```', '']
    lines += ['## Retrieval traces and source excerpts', '',
              'See the sibling JSON report: it contains prompts, excerpts, candidates, thresholds, index and model provenance.', '']
    return '\n'.join(lines)


def save(report, output):
    summarize(report)
    atomic_text(output, json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    atomic_text(Path(output).with_suffix('.md'), markdown(report))


def parser():
    root = argparse.ArgumentParser(description='Day 28 — Week 6 index + local LLM + RAG')
    subs = root.add_subparsers(dest='command', required=True)
    subs.add_parser('questions')
    for name in ('doctor', 'ask', 'evaluate', 'compare'):
        cmd = subs.add_parser(name)
        if name == 'ask':
            cmd.add_argument('question')
        cmd.add_argument('--db', type=Path, default=ROOT / 'day-21-document-indexing/knowledge.db')
        cmd.add_argument('--url', default='http://127.0.0.1:11434')
        cmd.add_argument('--embedding-model', default='bge-m3')
        cmd.add_argument('--local-model', default='qwen2.5:14b')
        cmd.add_argument('--cloud-model', default='openai/gpt-oss-20b')
        cmd.add_argument('--cloud-provider', choices=('groq', 'openai'), default='groq')
        cmd.add_argument('--timeout', type=positive_float, default=180)
        cmd.add_argument('--strategy', choices=('fixed', 'structural'), default='fixed')
        cmd.add_argument('--candidate-k', type=positive_int, default=20)
        cmd.add_argument('--final-k', type=positive_int, default=5)
        cmd.add_argument('--min-similarity', type=cosine, default=.50)
        cmd.add_argument('--rewrite', choices=('none', 'heuristic'), default='heuristic')
        cmd.add_argument('--max-context-chars', type=positive_int, default=16000)
        cmd.add_argument('--max-tokens', type=positive_int, default=2048)
        cmd.add_argument('--num-ctx', type=positive_int, default=16384)
        cmd.add_argument('--repeats', type=positive_int, default=3 if name in ('evaluate', 'compare') else 1)
        cmd.add_argument('--questions', type=Path, default=HERE / 'questions.json')
        cmd.add_argument('--output', type=Path, default=HERE / 'reports/check' / f'{name}.json')
        cmd.add_argument('--cloud-rate-retries', type=nonnegative_int, default=2)
        cmd.add_argument('--cloud-retry-delay', type=positive_float, default=30)
        cmd.add_argument('--synthesis', action='store_true',
                         help='Select evidence, then synthesize from selected passages in a second model call.')
        cmd.add_argument('--quality-mode', choices=('baseline', 'coverage', 'complete', 'phases'), default='baseline',
                         help='Baseline, coverage claims, complete answer, or evidence for before/after checks (V16).')
        if name in ('evaluate', 'compare'):
            cmd.add_argument('--retry-from', type=Path)
            cmd.add_argument('--plan-only', action='store_true')
        if name == 'compare':
            cmd.add_argument('--only-provider', choices=('local', 'cloud'))
    return root


def run(args):
    if args.quality_mode == 'complete' and args.synthesis:
        raise ValueError('Use complete quality mode without --synthesis: it uses one final-answer call.')
    if args.quality_mode == 'phases' and args.synthesis:
        raise ValueError('Use phases quality mode without --synthesis: it uses one final-answer call.')
    if args.cloud_provider == 'openai':
        args.cloud_model = OpenAIProvider.normalize_model(
            OpenAIProvider.default_model if args.cloud_model == 'openai/gpt-oss-20b' else args.cloud_model)
    settings = Settings(args.candidate_k, args.final_k, args.min_similarity, args.strategy,
                        'heuristic')
    if args.output.suffix.lower() != '.json':
        raise ValueError('--output must end in .json.')
    if args.command == 'ask' and not args.question.strip():
        raise ValueError('Question must not be empty.')
    cases = ([{'id': 'custom', 'question': args.question}] if args.command == 'ask'
             else [] if args.command == 'doctor' else load_cases(args.questions))
    retry = None
    if getattr(args, 'plan_only', False) and not getattr(args, 'retry_from', None):
        raise ValueError('--plan-only requires --retry-from.')
    if getattr(args, 'retry_from', None):
        if args.output.resolve() == args.retry_from.resolve():
            raise ValueError('Retry output must differ from the baseline report.')
        retry = retry_plan(args.retry_from, cases, vars(args), args.command, args.repeats,
                           only_provider=getattr(args, 'only_provider', None))
        print(json.dumps({'scope': retry['scope'], 'source_run_id': retry['source_run_id'],
                          'generation_upper_bound': retry['generation_upper_bound'],
                          'rerun': [{k: a[k] for k in ('case_id', 'provider')} for a in retry['assessments']
                                    if a['action'] == 'rerun'],
                          'retained_case_provider_pairs': sum(a['action'] == 'retain' for a in retry['assessments']),
                          'reassessed_case_provider_pairs': sum(bool(a['reassessments']) for a in retry['assessments'])},
                         ensure_ascii=False, indent=2), flush=True)
        if args.plan_only or not retry['planned_observations']:
            return 0
        selected = {x['case_id'] for x in retry['planned_observations']}
        cases = [c for c in cases if c['id'] in selected]
    planned_names = ({x['provider'] for x in retry['planned_observations']} if retry else
                     {args.only_provider} if getattr(args, 'only_provider', None) else {'local', 'cloud'})
    report = {'schema_version': 12, 'cloud_api': args.cloud_provider,
              'prompt_revision': 'context_then_question_v10',
              'run_id': str(uuid.uuid4()), 'mode': 'live', 'state': 'running',
              'created_at': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'command': args.command, 'output_controls': {
                  'local': 'Ollama JSON schema with four nullable evidence-bound claims and catalog ID enum',
                  'cloud': 'Groq strict evidence-claim schema for GPT-OSS; JSON object for other models; application validation'},
              'settings': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              'providers': {}, 'provider_names': ['local'], 'cases': cases,
              'planned_trials': args.repeats, 'retrievals': [], 'results': [],
              'limitations': ['Heuristic checks do not prove semantic grounding.',
                              'Exact stability is response identity, not semantic equivalence.',
                              'Small sample; timings include loading and network for cloud.']}
    if args.cloud_provider == 'openai':
        report['output_controls']['cloud'] = 'OpenAI pinned snapshot with strict evidence-claim JSON schema'
    if args.synthesis:
        report['synthesis_mode'] = True
        report['prompt_revision'] = 'selection_then_synthesis_v11'
        report['output_controls'] = {
            'local': 'Ollama schemas: evidence-bound selection claims, then answer with selected quote IDs',
            'cloud': 'Groq GPT-OSS strict schemas for both stages; other models JSON object mode'}
        report['limitations'].append('Two stages: provider-specific evidence choices lead to different synthesis prompts.')
        if args.cloud_provider == 'openai':
            report['output_controls']['cloud'] = 'OpenAI pinned snapshot with strict JSON schemas for both stages'
    if getattr(args, 'only_provider', None):
        report['provider_names'] = [args.only_provider]
    if args.quality_mode == 'coverage':
        report.update(schema_version=13, quality_mode='coverage',
                      prompt_revision='coverage_then_synthesis_v13' if args.synthesis else 'coverage_v13')
    elif args.quality_mode == 'complete':
        report.update(schema_version=15, quality_mode='complete', prompt_revision='focused_complete_answer_v15')
        report['output_controls'] = {
            'local': 'Ollama final answer schema with four distinct nullable quote IDs in one call',
            'cloud': 'Final answer schema with four distinct nullable quote IDs in one call; OpenAI/Groq GPT-OSS strict schemas'}
    elif args.quality_mode == 'phases':
        report.update(schema_version=16, quality_mode='phases', prompt_revision='before_after_evidence_v16')
        report['output_controls'] = {
            'local': 'Ollama schema with before/after statements and distinct evidence IDs in one call',
            'cloud': 'Before/after evidence schema in one call; OpenAI/Groq GPT-OSS strict schemas'}
    if retry:
        report.update(scope='selective_retry', retry=retry,
                      planned_observations=retry['planned_observations'],
                      provider_names=[n for n in ('local', 'cloud') if n in planned_names])
    kb = None
    try:
        kb = ExistingIndex(args.db)
        report['index'] = kb.verify()
        embedding = LocalEmbeddings(args.embedding_model, args.url, args.timeout,
                                    http=StructuredHTTP(args.timeout, local=True))
        report['embedding_provider'] = embedding.doctor()
        if kb.info(args.strategy)['model'] != embedding.model:
            raise ValueError('Embedding model differs from the Week 6 index.')
        local = OllamaProvider(args.local_model, args.url, args.timeout,
                               max_tokens=args.max_tokens, num_ctx=args.num_ctx,
                               http=StructuredHTTP(args.timeout, local=True))
        providers = []
        if 'local' in planned_names:
            report['providers']['local'] = {**local.doctor(), 'ready': True}
            providers.append(local)
        if args.command == 'compare' and 'cloud' in planned_names:
            try:
                key = cloud_key(args.cloud_provider)
            except ProviderError as error:
                key = None
                report['cloud_setup_error'] = str(error)
            if not key or not key.strip():
                variable = 'OPENAI_API_KEY' if args.cloud_provider == 'openai' else 'GROQ_API_KEY'
                report['cloud_comparison'] = f'skipped: {variable} unavailable; local evaluation still runs'
                if report.get('cloud_setup_error') or retry or getattr(args, 'only_provider', None) == 'cloud':
                    if 'cloud' not in report['provider_names']:
                        report['provider_names'].append('cloud')
                    report['providers']['cloud'] = {'ready': False, 'cloud_api': args.cloud_provider,
                                                   'error': report.get('cloud_setup_error', f'{variable} missing for requested cloud run.')}
                    report['cloud_comparison'] = 'cloud setup failed; local evaluation still runs'
            else:
                if 'cloud' not in report['provider_names']:
                    report['provider_names'].append('cloud')
                try:
                    provider_class = OpenAIProvider if args.cloud_provider == 'openai' else GroqProvider
                    cloud = provider_class(key, args.cloud_model, args.timeout, max_tokens=args.max_tokens,
                                         http=StructuredHTTP(args.timeout, rate_retries=args.cloud_rate_retries,
                                                             retry_delay=args.cloud_retry_delay))
                    report['providers']['cloud'] = {**cloud.doctor(), 'ready': True, 'cloud_api': args.cloud_provider}
                    providers.append(cloud)
                    report['cloud_comparison'] = ('selective: pairs share prompts where both providers are scheduled; '
                                                   'unpaired retries are separate measurements' if retry else
                                                   'enabled: identical excerpts and prompts')
                    if set(report['provider_names']) == {'cloud'}:
                        report['cloud_comparison'] = 'cloud-only: separate measurements; no fresh local/cloud pairing'
                    if args.synthesis:
                        report['cloud_comparison'] = ('two-stage: selection prompts share retrieval where paired; '
                                                       'provider-specific evidence can change synthesis prompts; '
                                                       'unpaired retries are separate measurements')
                except ProviderError as error:
                    report['providers']['cloud'] = {'ready': False, 'cloud_api': args.cloud_provider, 'error': str(error)}
                    report['cloud_comparison'] = 'failed preflight; local evaluation still runs'
        for trial in range(1, args.repeats + 1):
            for case in cases:
                requested = ({x['provider'] for x in retry['planned_observations']
                              if x['case_id'] == case['id'] and x['trial'] == trial}
                             if retry else set(report['provider_names']))
                if not requested:
                    continue
                print(f"Trial {trial}/{args.repeats}: {case['id']}", flush=True)
                # 'none' uses the existing Day23 filter mode without rewriting.
                try:
                    mode = 'filter' if args.rewrite == 'none' else 'rewrite_filter'
                    prepared = prepare(kb, embedding, case['question'], settings,
                                       args.max_context_chars, mode=mode, quality_mode=args.quality_mode)
                    prepared.update(case_id=case['id'], trial=trial)
                    report['retrievals'].append(prepared)
                    available = [p for p in providers if p.name in requested]
                    order = available if trial % 2 else list(reversed(available))
                    for provider in order:
                        if provider.name == 'cloud' and report.get('cloud_paused_after'):
                            row = {'provider': 'cloud', 'model': provider.model, 'case_id': case['id'],
                                   'status': 'error', 'generation_called': False,
                                   'error': 'Cloud HTTP 429 persisted; remaining cloud calls skipped this run.'}
                        else:
                            row = observe(provider, prepared, case, synthesize=args.synthesis)
                            if provider.name == 'cloud' and row.get('error', '').startswith('HTTP 429 '):
                                report['cloud_paused_after'] = {'case_id': case['id'], 'trial': trial,
                                                              'reason': 'HTTP 429 persisted after configured retries.'}
                                print('  cloud: rate limit persists; remaining cloud calls paused for this run', flush=True)
                        row['trial'] = trial
                        if provider.name == 'cloud':
                            row['cloud_api'] = args.cloud_provider
                        report['results'].append(row)
                        print(f"  {provider.name}: {row['status']}", flush=True)
                    for name in requested:
                        if name not in [p.name for p in providers]:
                            report['results'].append({'provider': name, 'case_id': case['id'], 'trial': trial,
                                                      'status': 'error', 'generation_called': False,
                                                      'error': 'Provider preflight failed.'})
                except (ProviderError, ValueError, sqlite3.Error) as error:
                    report['retrievals'].append({'case_id': case['id'], 'trial': trial, 'error': str(error)})
                    for name in requested:
                        report['results'].append({'provider': name, 'case_id': case['id'], 'trial': trial,
                                                  'status': 'error', 'generation_called': False,
                                                  'error': 'Local retrieval failed: ' + str(error)})
                save(report, args.output)
        report['state'] = 'completed'
        if args.command == 'doctor':
            report['doctor_ready'] = True
    except (ProviderError, ValueError, sqlite3.Error) as error:
        report.update(state='failed', error=str(error))
    except KeyboardInterrupt:
        report['state'] = 'interrupted'
    finally:
        if kb:
            kb.close()
        for row in report['results']:
            if row['provider'] == 'cloud':
                row['cloud_api'] = args.cloud_provider
        save(report, args.output)
    print(json.dumps({k: report.get(k) for k in ('scope', 'state', 'error', 'summary', 'local_rag_verified', 'cloud_comparison')}, ensure_ascii=False, indent=2))
    for row in report['results']:
        if args.command == 'ask':
            print(json.dumps(row, ensure_ascii=False, indent=2))
    print(f'Saved: {args.output} and {args.output.with_suffix(".md")}')
    if report['state'] == 'interrupted':
        return 130
    if args.command == 'doctor':
        return 0 if report.get('doctor_ready') else 1
    return 0 if report['state'] == 'completed' and report['all_checks_passed'] and (
        'local' not in report['provider_names'] or report['local_rag_verified']) else 1


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == 'questions':
        print(json.dumps(load_cases(HERE / 'questions.json'), ensure_ascii=False, indent=2))
        return 0
    return run(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, ProviderError) as error:
        print(f'Cannot complete Day 28: {error}', file=sys.stderr)
        raise SystemExit(1)
