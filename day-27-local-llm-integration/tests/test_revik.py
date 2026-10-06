import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revik.app import DEFAULT, RevikError, check, git, install, parse_xml, settings

FAKE = '''import sys
from pathlib import Path
import xml.etree.ElementTree as E
args=sys.argv[1:]
if '--version' in args:
    print('fake-detekt'); raise SystemExit(0)
root=Path(args[args.index('--input')+1])
report=Path(args[args.index('--report')+1].split(':',1)[1])
r=E.Element('checkstyle')
bad=False
for f in root.rglob('*.kt'):
    if 'BAD' in f.read_text():
        n=E.SubElement(r,'file',name=str(f))
        E.SubElement(n,'error',line='1',column='1',source='detekt.TestRule',message='Remove BAD',severity='warning')
        bad=True
E.ElementTree(r).write(report)
raise SystemExit(2 if bad else 0)
'''

class Handler(BaseHTTPRequestHandler):
    calls = []
    mode = 'ok'
    def log_message(self, *args): pass
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.calls.append((self.path, data))
        if self.path == '/api/show':
            result = {'remote_host': 'example.com'} if self.mode == 'remote' else {'details': {'family': 'qwen2'}}
        else:
            result = {'model': data['model'], 'done': True, 'done_reason': 'stop', 'message': {'content': 'Локальное объяснение.'}}
            if self.mode == 'length': result['done_reason'] = 'length'
            if self.mode == 'empty': result['message']['content'] = ''
            if self.mode == 'wrong': result['model'] = 'wrong-model'
        payload = json.dumps(result).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(payload)

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='revik tests ')
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q'); git(self.root, 'config', 'user.email', 'test@example.invalid'); git(self.root, 'config', 'user.name', 'Test')
        self.tool = self.root / 'fake.py'; self.tool.write_text(FAKE)
        self.cfg = dict(DEFAULT, detekt_command=[sys.executable, str(self.tool)], ollama_url=f'http://127.0.0.1:{self.server.server_port}')
        (self.root / '.revik.json').write_text(json.dumps(self.cfg))
        Handler.mode = 'ok'; Handler.calls.clear()
    def tearDown(self): self.tmp.cleanup()
    def add(self, name, content):
        p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content); git(self.root, 'add', '--', name)
    def config(self): self.add('detekt/detekt.yml', 'config:\n  validation: false\n')
    def test_language_and_tone_reach_local_model_without_changing_gate(self):
        self.config()
        for language in ('ru', 'en'):
            for tone in ('professional', 'light_troll', 'hard_troll'):
                for source, expected in [('BAD', 1), ('clean', 0)]:
                    with self.subTest(language=language, tone=tone, source=source):
                        self.add('A.kt', source)
                        cfg = dict(self.cfg, language=language, tone=tone)
                        report, code = check(self.root, cfg)
                        self.assertEqual(code, expected)
                        self.assertEqual(report['language'], language)
                        self.assertEqual(report['tone'], tone)
                        self.assertEqual(report['llm']['tone'], tone)
                        prompt = Handler.calls[-1][1]['messages'][0]['content']
                        self.assertIn('Russian' if language == 'ru' else 'English', prompt)
                        expected_style = {'professional': 'Tone: professional', 'light_troll': 'Tone: light playful roasting', 'hard_troll': 'Tone: hard code roasting'}[tone]
                        self.assertIn(expected_style, prompt)
                        self.assertIn('Do not change the gate decision', prompt)
    def test_invalid_language_and_tone_rejected(self):
        for key, value in [('language', 'de'), ('tone', 'random')]:
            with self.subTest(key=key):
                (self.root / '.revik.json').write_text(json.dumps(dict(self.cfg, **{key: value})))
                with self.assertRaises(RevikError): settings(self.root)
    def test_cli_overrides_config_language_and_tone(self):
        cfg = settings(self.root, {'language': 'en', 'tone': 'hard_troll'})
        self.assertEqual(cfg['language'], 'en')
        self.assertEqual(cfg['tone'], 'hard_troll')
        self.assertEqual(settings(self.root)['language'], 'ru')
    def test_english_cli_skip_and_report(self):
        self.add('README.md', 'text')
        p = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'revik_cli.py'), 'check', '--language', 'en', '--tone', 'light_troll'], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('check skipped', p.stdout)
        self.assertNotIn('Ревик', p.stdout)
        report = json.loads((self.root / '.git/revik-reports/latest.json').read_text())
        self.assertEqual(report['language'], 'en')
        self.assertEqual(report['tone'], 'light_troll')
        self.assertIn('Staged versions are checked', (self.root / '.git/revik-reports/latest.html').read_text())
    def test_english_real_hook_with_config(self):
        self.config(); self.add('A.kt', 'BAD')
        (self.root / '.revik.json').write_text(json.dumps(dict(self.cfg, language='en', tone='hard_troll')))
        install(self.root, Path(__file__).resolve().parents[1], 'en')
        p = subprocess.run(['git', 'commit', '-m', 'bad english'], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Commit blocked', p.stdout + p.stderr)
        report = json.loads((self.root / '.git/revik-reports/latest.json').read_text())
        self.assertEqual(report['tone'], 'hard_troll')
    def test_no_config_skips_without_tools(self):
        self.add('common/A.kt', 'BAD')
        self.cfg['detekt_command'] = ['nonexistent']
        report, code = check(self.root, self.cfg)
        self.assertEqual((report['status'], code), ('skipped', 0)); self.assertFalse(Handler.calls)
    def test_no_kotlin_skips(self):
        self.config(); git(self.root, 'commit', '-qm', 'config')
        self.add('README.md', 'text'); self.assertEqual(check(self.root, self.cfg)[0]['status'], 'skipped')
    def test_actual_commit_without_config_saves_skip_report(self):
        self.add('A.kt', 'BAD')
        install(self.root, Path(__file__).resolve().parents[1])
        p = subprocess.run(['git', 'commit', '-m', 'skip without config'], cwd=self.root, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads((self.root / '.git/revik-reports/latest.json').read_text())
        self.assertEqual(report['status'], 'skipped')
        self.assertTrue((self.root / '.git/revik-reports/latest.html').is_file())
        self.assertFalse(Handler.calls)
    def test_actual_commit_without_kotlin_saves_skip_report(self):
        self.config(); git(self.root, 'commit', '-qm', 'config')
        self.add('README.md', 'text')
        install(self.root, Path(__file__).resolve().parents[1])
        p = subprocess.run(['git', 'commit', '-m', 'documentation'], cwd=self.root, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads((self.root / '.git/revik-reports/latest.json').read_text())
        self.assertEqual(report['status'], 'skipped')
        self.assertTrue((self.root / '.git/revik-reports/latest.html').is_file())
        self.assertFalse(Handler.calls)
    def test_optional_llm_failure_report_does_not_block_clean_commit(self):
        self.config(); self.add('A.kt', 'clean'); Handler.mode = 'remote'
        self.cfg['require_llm'] = False
        (self.root / '.revik.json').write_text(json.dumps(self.cfg))
        install(self.root, Path(__file__).resolve().parents[1])
        p = subprocess.run(['git', 'commit', '-m', 'optional model'], cwd=self.root, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads((self.root / '.git/revik-reports/latest.json').read_text())
        self.assertEqual(report['status'], 'allowed')
        self.assertIsNone(report['llm'])
        self.assertTrue(report['llm_error'])
    def test_clean_local_llm(self):
        self.config(); self.add('common/Hello.kt', 'fun hello() = 1')
        report, code = check(self.root, self.cfg)
        self.assertEqual(code, 0); self.assertEqual(report['status'], 'allowed'); self.assertTrue(report['llm']['local_inference'])
        self.assertEqual([x[0] for x in Handler.calls], ['/api/show', '/api/chat'])
    def test_violation_blocks_and_exact_location(self):
        self.config(); self.add('common/a space.kt', 'BAD')
        report, code = check(self.root, self.cfg)
        self.assertEqual(code, 1); self.assertEqual(report['findings'][0]['path'], 'common/a space.kt')
    def test_partial_staging_clean_index_dirty_worktree(self):
        self.config(); self.add('A.kt', 'clean')
        (self.root / 'A.kt').write_text('BAD')
        self.assertEqual(check(self.root, self.cfg)[1], 0)
        self.assertEqual((self.root / 'A.kt').read_text(), 'BAD')
    def test_partial_staging_bad_index_clean_worktree(self):
        self.config(); self.add('A.kt', 'BAD'); (self.root / 'A.kt').write_text('clean')
        self.assertEqual(check(self.root, self.cfg)[1], 1)
    def test_deleted_file_not_analyzed(self):
        self.config(); self.add('A.kt', 'clean'); git(self.root, 'commit', '-qm', 'base'); git(self.root, 'rm', 'A.kt')
        self.assertEqual(check(self.root, self.cfg)[0]['status'], 'skipped')
    def test_config_change_checks_all_sources(self):
        self.config(); self.add('A.kt', 'BAD'); git(self.root, 'commit', '-qm', 'base')
        self.add('detekt/detekt.yml', '# modified\n')
        report, code = check(self.root, self.cfg); self.assertEqual(code, 1); self.assertEqual(report['scope'], 'all_staged_kotlin')
    def test_config_deleted_skips(self):
        self.config(); git(self.root, 'commit', '-qm', 'base'); git(self.root, 'rm', 'detekt/detekt.yml'); self.add('A.kt', 'BAD')
        self.assertEqual(check(self.root, self.cfg)[1], 0)
    def test_unstaged_config_not_used(self):
        self.add('A.kt', 'BAD'); (self.root / 'detekt').mkdir(); (self.root / 'detekt/detekt.yml').write_text('x')
        self.assertEqual(check(self.root, self.cfg)[0]['status'], 'skipped')
    def test_llm_incomplete_empty_wrong_and_remote(self):
        self.config(); self.add('A.kt', 'clean')
        for mode in ['length', 'empty', 'wrong', 'remote']:
            with self.subTest(mode=mode):
                Handler.mode = mode; report, code = check(self.root, self.cfg); self.assertEqual(code, 2); self.assertEqual(report['status'], 'error')
    def test_optional_llm_never_overrides_detekt(self):
        self.config(); self.add('A.kt', 'BAD'); Handler.mode = 'remote'; self.cfg['require_llm'] = False
        self.assertEqual(check(self.root, self.cfg)[1], 1)
        self.add('A.kt', 'clean'); self.assertEqual(check(self.root, self.cfg)[1], 0)
    def test_index_mutation_blocks(self):
        self.config(); self.add('A.kt', 'clean')
        def mutation(*args):
            self.add('B.kt', 'clean'); return {'answer': 'ok'}
        with patch('revik.app.explain', side_effect=mutation): self.assertEqual(check(self.root, self.cfg)[1], 2)
    def test_detekt_technical_error(self):
        self.config(); self.add('A.kt', 'clean'); self.cfg['detekt_command'] = [sys.executable, '-c', 'raise SystemExit(3)']
        with self.assertRaises(RevikError): check(self.root, self.cfg)
    def test_existing_hook_preserved(self):
        hook = self.root / '.git/hooks/pre-commit'; hook.write_text('#!/bin/sh\nexit 7\n')
        with self.assertRaises(RevikError): install(self.root, Path(__file__).resolve().parents[1])
        self.assertIn('exit 7', hook.read_text())
    def test_actual_git_commit_hook_blocks_and_allows(self):
        self.config(); self.add('A.kt', 'BAD'); install(self.root, Path(__file__).resolve().parents[1])
        p = subprocess.run(['git', 'commit', '-m', 'bad'], cwd=self.root, capture_output=True)
        self.assertNotEqual(p.returncode, 0); self.assertFalse(run_head(self.root))
        report = json.loads((self.root / '.git/revik-reports/latest.json').read_text())
        self.assertEqual(report['status'], 'blocked'); self.assertIn('vscode://', report['findings'][0]['links']['vscode'])
        self.add('A.kt', 'clean'); p = subprocess.run(['git', 'commit', '-m', 'good'], cwd=self.root, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr); self.assertTrue(run_head(self.root))
    def test_settings_reject_external_url(self):
        self.cfg['ollama_url'] = 'https://example.com'; (self.root / '.revik.json').write_text(json.dumps(self.cfg))
        with self.assertRaises(RevikError): settings(self.root)
    def test_symlink_rejected(self):
        self.config(); os.symlink('/etc/passwd', self.root / 'A.kt'); git(self.root, 'add', 'A.kt')
        with self.assertRaises(RevikError): check(self.root, self.cfg)
    def test_missing_baseline_rejected(self):
        self.config(); self.add('A.kt', 'clean'); self.cfg['baseline'] = 'detekt/baselines/missing.xml'
        with self.assertRaises(RevikError): check(self.root, self.cfg)
    def test_invalid_xml_rejected(self):
        path = self.root / 'report.xml'; path.write_text('<wrong/>')
        with self.assertRaises(RevikError): parse_xml(path, self.root, [])

def run_head(root):
    return subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=root, capture_output=True).returncode == 0

if __name__ == '__main__': unittest.main()
