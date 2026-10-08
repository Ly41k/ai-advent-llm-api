"""V7 bounded periodic-procedure selections with preserved factual V3 cache."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'quality_v6'))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))
import cli29
import engine29
import provider29
from store29 import digest, now
from selection7 import FACTUAL, PREFIX, prepare_selection, render, routed_question
from http7 import SelectionHTTP
from guard7 import audit, markdown


@contextmanager
def task_templates():
    original = engine29.COMPACT, cli29.prompt_for, engine29.parse_answer, provider29.StructuredHTTP
    engine29.COMPACT = FACTUAL
    old_prompt, old_parse = original[1:3]
    def routed(prepared, profile):
        value = old_prompt(prepared, profile)
        if profile['prompt'] == 'compact' and routed_question(prepared['question']):
            value = prepare_selection(value)
            value['prompt_sha256'] = digest(value['messages'])
        return value
    def parse(raw, excerpts, catalog=None, contract=None):
        if str(contract or '').startswith(PREFIX):
            value = render(raw, excerpts, catalog, contract)
            # Retain the original exact-substring citation validator as well.
            return old_parse(json.dumps(value, ensure_ascii=False), excerpts)
        return old_parse(raw, excerpts, catalog, contract)
    cli29.prompt_for, engine29.parse_answer = routed, parse
    provider29.StructuredHTTP = SelectionHTTP
    try:
        yield
    finally:
        engine29.COMPACT, cli29.prompt_for, engine29.parse_answer, provider29.StructuredHTTP = original


def write_audit(source, output=None):
    source = Path(source)
    report = cli29.read_report(source)
    output = Path(output) if output else source.with_suffix('.quality.json')
    if output.suffix != '.json' or output.resolve() == source.resolve() or output.with_suffix('.md').resolve() == source.with_suffix('.md').resolve():
        raise ValueError('Audit output must be separate from original JSON/Markdown.')
    value = audit(report, source)
    cli29.atomic_text(output, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    cli29.atomic_text(output.with_suffix('.md'), markdown(value))
    print(json.dumps({'independent_quality_checks': value['summary'], 'source_state': value['state'],
                      'missing_observations': value['missing_observations'], 'additional_model_calls': 0,
                      'human_semantic_review_required': True, 'audit': str(output)}, ensure_ascii=False, indent=2))
    return value


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == 'audit':
        import argparse
        p = argparse.ArgumentParser(description='Offline audit of original V1–V7 reports.')
        p.add_argument('report', type=Path)
        p.add_argument('--output', type=Path)
        a = p.parse_args(args[1:])
        with task_templates():
            value = write_audit(a.report, a.output)
        return int(any(s['blocked'] for s in value['summary'].values()))
    if args and args[0] in ('doctor', 'plan', 'run'):
        if any(a == '--profiles-file' or a.startswith('--profiles-file=') for a in args):
            raise ValueError('Use bundled V3 model settings with V7.')
        args[1:1] = ['--profiles-file', str(HERE.parent / 'focused_v3/profiles.json')]
        if not any(a == '--profiles' or a.startswith('--profiles=') for a in args):
            args[1:1] = ['--profiles', 'baseline', 'focused-v3-q4']
        parsed = cli29.parser().parse_args(args)
        if parsed.repeats > 3:
            raise ValueError('At most three completed answers per unchanged experiment identity.')
        if args[0] == 'run':
            if parsed.output is None:
                parsed.output = HERE.parent.parent / 'reports/check' / ('control-v7-' + now().replace(':', '-').replace('.', '-') + '.json')
                args += ['--output', str(parsed.output)]
            if parsed.max_new_observations is None:
                args += ['--max-new-observations', '3']
    with task_templates():
        status = cli29.main(args)
        if args and args[0] == 'run' and parsed.output.is_file():
            value = write_audit(parsed.output)
            selected = set(parsed.profiles) - {'baseline'}
            if any(s['blocked'] for n, s in value['summary'].items() if n in selected):
                return 1
        return status


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print('ERROR — ' + str(error), file=sys.stderr)
        raise SystemExit(1)
