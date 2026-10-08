"""V1 measurements and factual V3 cache with language-specific procedures."""
from contextlib import contextmanager
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

import cli29
import engine29
from store29 import digest
from templates5 import FACTUAL, is_verification_question, verification_prompt


@contextmanager
def task_templates():
    old_template, old_prompt_for = engine29.COMPACT, cli29.prompt_for
    engine29.COMPACT = FACTUAL
    def routed(prepared, profile):
        result = old_prompt_for(prepared, profile)
        if profile['prompt'] == 'compact' and is_verification_question(prepared['question']):
            result['messages'][0]['content'] = verification_prompt(prepared['question'])
            result['prompt_sha256'] = digest(result['messages'])
        return result
    cli29.prompt_for = routed
    try:
        yield
    finally:
        cli29.prompt_for = old_prompt_for
        engine29.COMPACT = old_template


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ('doctor', 'plan', 'run'):
        if '--profiles-file' in args or any(a.startswith('--profiles-file=') for a in args):
            raise ValueError('Use bundled V3 profiles with this task-aware launcher.')
        args[1:1] = ['--profiles-file', str(HERE.parent / 'focused_v3' / 'profiles.json')]
        if '--profiles' not in args and not any(a.startswith('--profiles=') for a in args):
            args[1:1] = ['--profiles', 'baseline', 'focused-v3-q4']
    with task_templates():
        return cli29.main(args)


if __name__ == '__main__':
    raise SystemExit(main())
