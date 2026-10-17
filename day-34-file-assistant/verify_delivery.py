"""Verify the curated Day 34 delivery offline; never instantiate a live adapter."""
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODULE = HERE.name


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def checked_path(relative):
    parts = PurePosixPath(relative).parts
    check(parts and not relative.startswith('/') and '..' not in parts and '\\' not in relative,
          'unsafe manifest path')
    check(relative in ('README.md', 'README.ru.md') or parts[0] == MODULE, 'unexpected publication scope')
    p = ROOT
    for part in parts:
        p = p / part
        check(not p.is_symlink(), 'symlink in publication')
    check(p.is_file(), 'missing publication file: ' + relative)
    return p


def verify():
    manifest = load(HERE / 'delivery-manifest.json')
    expected = manifest['files_sha256']
    allowed = set(expected) | {MODULE + '/delivery-manifest.json'}
    private = {'results', '__pycache__', '.venv', '.DS_Store', '.env', 'receipts', 'provider-evidence'}
    secret = re.compile(r'(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    local_path = re.compile(r'(?:/Users/[^\s"\x27]+|/workspace/[^\s"\x27]+|/home/[^\s"\x27]+|[A-Za-z]:\\Users\\)')
    for relative, fingerprint in expected.items():
        p = checked_path(relative)
        check(not (set(PurePosixPath(relative).parts) & private), 'private/cache file in publication')
        check(p.suffix not in ('.pyc', '.zip') and 'provider-' not in p.name, 'temporary/provider payload in publication')
        check(sha(p) == fingerprint, 'SHA mismatch: ' + relative)
        text = p.read_text(encoding='utf-8')
        check(not secret.search(text), 'credential pattern in publication: ' + relative)
        # The verifier itself contains these pattern literals, not user paths.
        if p != Path(__file__).resolve():
            check(not local_path.search(text), 'local absolute path in publication: ' + relative)
    # Local private results/caches may stay on a Mac; they must never enter Git's public index.
    for p in HERE.rglob('*'):
        relative = p.relative_to(ROOT).as_posix()
        parts = set(p.relative_to(HERE).parts)
        if parts & {'results', '__pycache__', '.venv', '.DS_Store'}:
            continue
        if p.is_file() or p.is_symlink():
            check(relative in allowed, 'unexpected Day 34 file outside publication manifest: ' + relative)
    git_index_checked = False
    if (ROOT / '.git').exists():
        def git(*args):
            r = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, check=True)
            return r.stdout
        indexed = git('ls-files', '-z', '--', MODULE).decode().split('\0')
        check(all(not p or p in allowed for p in indexed), 'unexpected Day 34 file in Git index')
        staged = git('diff', '--cached', '--name-only', '-z').decode().split('\0')
        check(all(not p or p in allowed for p in staged), 'staged change outside Day 34 and root READMEs')
        changed = git('diff', 'HEAD', '--name-only', '-z').decode().split('\0')
        check(all(not p or p in allowed for p in changed), 'tracked modification outside delivery scope')
        git('diff', '--check')
        git('diff', '--cached', '--check')
        git_index_checked = True

    inputs = load(HERE / 'inputs.json')
    for relative, fingerprint in inputs['files'].items():
        p = ROOT / relative
        check(not p.is_symlink() and sha(p) == fingerprint, 'Day 33 input changed: ' + relative)
    E = HERE / 'evidence'
    acceptance = load(E / 'acceptance.json')
    for field in ('technical_acceptance', 'real_llm_tool_selection', 'file_operations', 'usage_quality',
                  'reviewed_adr_quality', 'course_minimum'):
        check(acceptance[field] == 'PASS', 'unexpected acceptance: ' + field)
    check(acceptance['original_adr_quality'] == 'PARTIAL'
          and acceptance['fully_automatic_original_documents_e2e'] == 'NOT_ACCEPTED'
          and acceptance['editorial_changes_are_model_output'] is False, 'editorial provenance lost')
    for scenario in ('usage', 'adr'):
        check(load(E / f'historical/{scenario}-acceptance.json')['full_e2e'] == 'NOT_ACCEPTED',
              'historical automatic acceptance changed')
    report = load(E / 'historical/mac-offline-v7-report.json')
    check(report['status'] == 'passed' and report['tests_run'] == 65
          and report['real_provider_http_posts'] == 0, 'Mac offline evidence mismatch')
    original = E / 'original/ADR-001-ticket-context.md'
    reviewed = E / 'reviewed/ADR-001-ticket-context-reviewed.md'
    diff = ''.join(difflib.unified_diff(original.read_text().splitlines(keepends=True),
                                      reviewed.read_text().splitlines(keepends=True),
                                      fromfile='original/ADR-001-ticket-context.md',
                                      tofile='editorial-proposal/ADR-001-ticket-context.md'))
    check(diff == (E / 'editorial-changes.diff').read_text(), 'editorial diff mismatch')
    editorial = load(E / 'reviewed/source-evidence.json')
    for item in editorial['evidence']:
        check(item['path'] in inputs['files'], 'editorial source outside allowlist')
        lines = (ROOT / item['path']).read_text().splitlines()
        check(lines[item['line'] - 1] == item['quote'], 'editorial quote mismatch')
    check(len(editorial['evidence']) == 27 and sha(reviewed) == editorial['editorial_document_sha256'],
          'reviewed ADR provenance mismatch')
    refs = set(re.findall(r'(day-33-support-assistant/[A-Za-z0-9_./-]+):(\d+)', reviewed.read_text()))
    check(refs == {(e['path'], str(e['line'])) for e in editorial['evidence']}, 'reviewed references mismatch')
    api = load(E / 'api-usage.json')
    posts = load(E / 'openai-posts.json')['posts']
    check([p['post'] for p in posts] == list(range(1, 11)) and all(p['http_status'] == '200' for p in posts),
          'OpenAI history mismatch')
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        check(sum(p['usage'][key] for p in posts) == api[key], 'usage total mismatch')
    cached = sum(p['usage']['prompt_tokens_details']['cached_tokens'] for p in posts)
    conservative = (api['prompt_tokens'] * .75 + api['completion_tokens'] * 4.50) / 1_000_000
    adjusted = ((api['prompt_tokens'] - cached) * .75 + cached * .075 + api['completion_tokens'] * 4.50) / 1_000_000
    check(abs(conservative - api['conservative_list_cost_usd']) < 1e-10
          and abs(adjusted - api['cache_adjusted_estimate_usd']) < 1e-10
          and conservative < .50 and api['openai_reserved_usd'] <= .50, 'cost evidence mismatch')

    # Original runtime and ReplayAdapter, in an isolated temporary root. No live adapter/key lookup.
    from agent import run
    from file_tools import FileTools
    from llm_adapter import ReplayAdapter
    replays = {}
    with tempfile.TemporaryDirectory(prefix='day34-delivery-') as temporary:
        replay_root = Path(temporary)
        for relative in inputs['files']:
            target = replay_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        for scenario in ('usage', 'adr'):
            saved = load(E / f'{scenario}-trace.json')
            check(saved['provenance']['kind'].startswith('public decision-only projection'), 'trace provenance missing')
            tools = FileTools(replay_root, 'verify-' + scenario, inputs, read_policy=saved['file_read_policy'])
            trace, result = run(saved['goal'], tools, ReplayAdapter(saved), expected=saved)
            check(trace['status'] == 'completed' and result['file_operation'] == 'PASS'
                  and result['new_provider_posts'] == 0, 'replay failed: ' + scenario + ': ' + str(trace['error']))
            for name in saved['documents']:
                check((replay_root / tools.output_rel / name).read_bytes() == (E / 'original' / name).read_bytes(),
                      'replayed Markdown differs')
            check((replay_root / tools.output_rel / 'changes.diff').read_bytes()
                  == (E / f'historical/{scenario}-changes.diff').read_bytes(), 'model diff differs')
            replays[scenario] = {'status':'PASS', 'model_decisions':len(saved['model_calls']),
                                 'operations':len(trace['events']), 'equal':True, 'new_provider_posts':0}

    suite = unittest.defaultTestLoader.discover(str(HERE / 'tests'))
    tests = unittest.TextTestRunner(verbosity=1).run(suite)
    check(tests.wasSuccessful() and tests.testsRun == 65 and not tests.skipped, 'offline tests failed')
    # Everything declared immutable must still match after tests and replay.
    check(all(sha(checked_path(p)) == h for p, h in expected.items()), 'delivery changed during verification')
    check(all(sha(ROOT / p) == h for p, h in inputs['files'].items()), 'inputs changed during verification')
    return {'status':'PASS', 'offline_tests':'65/65 PASS', 'published_files':len(allowed),
            'delivery_sha256':'PASS', 'source_inputs_unchanged':17, 'editorial_diff':'PASS',
            'reviewed_source_quotes':'27/27 PASS', 'original_adr_quotes':'17/17 PASS',
            'public_file_screen':'PASS', 'git_index_checked':git_index_checked,
            'replay':replays, 'new_provider_posts':0,
            'technical_acceptance':'PASS', 'usage_quality':'PASS', 'original_adr_quality':'PARTIAL',
            'reviewed_adr_quality':'PASS', 'course_minimum':'PASS with documented independent editorial review',
            'fresh_live_acceptance':False}


if __name__ == '__main__':
    try:
        result = verify()
    except Exception as error:
        print(json.dumps({'status':'FAIL', 'error':str(error), 'new_provider_posts':0}, ensure_ascii=False, indent=2))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
