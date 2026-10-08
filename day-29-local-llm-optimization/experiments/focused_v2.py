"""V1 runner with a new, prompt-hashed template and separate profile names.

Only the task template is changed. V1 core files remain byte-for-byte intact so
cached baseline identities stay valid. The existing prompt digest fingerprints
the complete new messages; old compact responses cannot become focused results.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import cli29
import engine29
from focused_prompt_v2 import FOCUSED


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ('doctor', 'plan', 'run'):
        if '--profiles-file' in args or any(a.startswith('--profiles-file=') for a in args):
            raise ValueError('Use the bundled focused-v2 profiles; run main.py for V1 profiles.')
        args[1:1] = ['--profiles-file', str(HERE / 'profiles-focused-v2.json')]
        if '--profiles' not in args and not any(a.startswith('--profiles=') for a in args):
            args[1:1] = ['--profiles', 'baseline', 'focused-q4']
    original = engine29.COMPACT
    engine29.COMPACT = FOCUSED
    try:
        return cli29.main(args)
    finally:
        engine29.COMPACT = original


if __name__ == '__main__':
    raise SystemExit(main())
