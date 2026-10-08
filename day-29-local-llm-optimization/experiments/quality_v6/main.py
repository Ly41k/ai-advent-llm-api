"""V6 procedure evidence focus plus a zero-generation independent audit."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))
import cli29
import engine29
from store29 import digest, now
from policy import FACTUAL, focus, is_verification_question, template
from guard import audit, markdown


@contextmanager
def task_templates():
    old_template, old_prompt_for = engine29.COMPACT, cli29.prompt_for
    engine29.COMPACT = FACTUAL
    def routed(prepared, profile):
        result = old_prompt_for(prepared, profile)
        if profile['prompt'] == 'compact' and is_verification_question(prepared['question']):
            result = focus(result)
            revision = hashlib.sha256((HERE / 'policy.py').read_bytes()).hexdigest()
            result['messages'][0]['content'] = template(prepared['question']) + '\nEvidence preparation policy SHA256: ' + revision
            result['prompt_sha256'] = digest(result['messages'])
        return result
    cli29.prompt_for = routed
    try:
        yield
    finally:
        cli29.prompt_for, engine29.COMPACT = old_prompt_for, old_template


def write_audit(source, output=None):
    source = Path(source)
    report = cli29.read_report(source)  # Full original envelope/integrity checks.
    output = Path(output) if output else source.with_suffix('.quality.json')
    if output.suffix != '.json' or output.resolve() == source.resolve() or output.with_suffix('.md').resolve() == source.with_suffix('.md').resolve():
        raise ValueError('Audit output must be a separate .json, preserving original JSON and Markdown.')
    value = audit(report, source)
    cli29.atomic_text(output, json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    cli29.atomic_text(output.with_suffix('.md'), markdown(value))
    print(json.dumps({'independent_quality_checks': value['summary'], 'source_state': value['state'],
                      'missing_observations': value['missing_observations'], 'human_semantic_review_required': True,
                      'additional_model_calls': 0, 'audit': str(output)}, ensure_ascii=False, indent=2))
    return value


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == 'audit':
        import argparse
        p = argparse.ArgumentParser(description='Audit saved Day 29 claims with no HTTP/model calls.')
        p.add_argument('report', type=Path)
        p.add_argument('--output', type=Path)
        a = p.parse_args(args[1:])
        value = write_audit(a.report, a.output)
        return int(any(s['blocked'] for s in value['summary'].values()))
    if args and args[0] in ('doctor', 'plan', 'run'):
        if any(a == '--profiles-file' or a.startswith('--profiles-file=') for a in args):
            raise ValueError('Use bundled V3 model settings with this launcher.')
        args[1:1] = ['--profiles-file', str(HERE.parent / 'focused_v3' / 'profiles.json')]
        if not any(a == '--profiles' or a.startswith('--profiles=') for a in args):
            args[1:1] = ['--profiles', 'baseline', 'focused-v3-q4']
        parsed = cli29.parser().parse_args(args)
        if parsed.repeats > 3:
            raise ValueError('V6 allows at most three answers per unchanged experiment identity.')
        if args[0] == 'run':
            if parsed.output is None:
                parsed.output = HERE.parent.parent / 'reports/check' / ('control-v6-' + now().replace(':', '-').replace('.', '-') + '.json')
                args += ['--output', str(parsed.output)]
            if parsed.max_new_observations is None:
                args += ['--max-new-observations', '3']
    with task_templates():
        status = cli29.main(args)
    if args and args[0] == 'run' and parsed.output.is_file():
        value = write_audit(parsed.output)
        selected = set(parsed.profiles) - {'baseline'}
        # A baseline failure is comparison evidence, not a reason to discard
        # or regenerate the optimized answers. Candidate failures remain cached.
        if any(s['blocked'] for name, s in value['summary'].items() if name in selected):
            return 1
    return status


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print('ERROR — ' + str(error), file=sys.stderr)
        raise SystemExit(1)
