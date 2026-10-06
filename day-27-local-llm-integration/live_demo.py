#!/usr/bin/env python3
"""Real Detekt + Ollama + actual Git hooks, in a disposable repository."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--detekt-jar', type=Path)
    p.add_argument('--detekt-bin', default='detekt')
    p.add_argument('--model', default='qwen2.5:14b')
    p.add_argument('--language', choices=['ru', 'en'], default='ru')
    p.add_argument('--tone', choices=['professional', 'light_troll', 'hard_troll'], default='professional')
    p.add_argument('--output', type=Path, default=Path('revik-live.json'))
    args = p.parse_args()
    command = ['java', '-jar', str(args.detekt_jar.resolve())] if args.detekt_jar else [args.detekt_bin]
    results = []
    with tempfile.TemporaryDirectory(prefix='revik-live-') as tmp:
        root = Path(tmp)
        def git(*values):
            result = subprocess.run(['git', *values], cwd=root, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr)
        git('init', '-q'); git('config', 'user.email', 'revik-demo@example.invalid'); git('config', 'user.name', 'Revik demo')
        (root / 'detekt').mkdir()
        shutil.copyfile(HERE / 'examples/detekt.yml', root / 'detekt/detekt.yml')
        (root / '.revik.json').write_text(json.dumps({'detekt_command': command, 'model': args.model, 'language': args.language, 'tone': args.tone}), encoding='utf-8')
        git('add', 'detekt/detekt.yml')
        result = subprocess.run([sys.executable, str(HERE / 'revik_cli.py'), 'install'], cwd=root)
        if result.returncode:
            return result.returncode
        for title, file, expected in [('bad', 'Bad.kt', 'blocked'), ('good', 'Good.kt', 'allowed')]:
            shutil.copyfile(HERE / 'examples' / file, root / 'Demo.kt')
            git('add', 'Demo.kt')
            result = subprocess.run(['git', 'commit', '-m', title], cwd=root)
            report = json.loads((root / '.git/revik-reports/latest.json').read_text(encoding='utf-8'))
            ok = report['status'] == expected and bool(report.get('llm', {}).get('local_inference')) and (result.returncode == 0) == (expected == 'allowed')
            results.append({'scenario': title, 'expected': expected, 'git_exit_code': result.returncode, 'passed': ok, 'report': report})
    payload = {'mode': 'live', 'all_passed': all(x['passed'] for x in results), 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Saved:', args.output)
    return 0 if payload['all_passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
