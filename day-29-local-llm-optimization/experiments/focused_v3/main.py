"""V1 measurements and cache with an independently prompt-hashed template."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

import cli29
import engine29
from template import FOCUSED


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ('doctor', 'plan', 'run'):
        if '--profiles-file' in args or any(a.startswith('--profiles-file=') for a in args):
            raise ValueError('Use the bundled focused-v3 profiles; run the original main.py for V1 profiles.')
        args[1:1] = ['--profiles-file', str(HERE / 'profiles.json')]
        if '--profiles' not in args and not any(a.startswith('--profiles=') for a in args):
            args[1:1] = ['--profiles', 'baseline', 'focused-v3-q4']
    original = engine29.COMPACT
    engine29.COMPACT = FOCUSED
    try:
        return cli29.main(args)
    finally:
        engine29.COMPACT = original


if __name__ == '__main__':
    raise SystemExit(main())
