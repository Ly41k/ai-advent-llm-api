"""Offline transport tests; no actual LLM generations or semantic scoring."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import cli29
import engine29
from focused_v2 import main
from focused_prompt_v2 import FOCUSED
from provider29 import MeasuredOllama
from test_day29 import Tests as V1Fixture, FakeIndex, FakeEmbedding


class FocusedTests(unittest.TestCase):
    def setUp(self):
        self.fixture = V1Fixture('test_three_answers_are_reused_without_probe_or_warmup')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.profiles = engine29.load_profiles(HERE / 'profiles-focused-v2.json')
        old = {'baseline': self.profiles['baseline'],
               'candidate-q4': self.profiles['focused-q4']}
        self.fixture.profiles.write_text(json.dumps(old))

    def focused_args(self, command='run', *extra):
        args = self.fixture.args(command, '--profiles', 'baseline', 'focused-q4', *extra)
        del args[1:3]  # The launcher supplies its bundled profiles file.
        return args

    def execute_focused(self, args):
        fake = self.fixture.http
        def provider(profile, url, timeout, seed=42, sample_interval=.5):
            return MeasuredOllama(profile, url, timeout, seed, http=fake, sample_interval=sample_interval)
        with ExitStack() as stack:
            stack.enter_context(patch.object(cli29, 'ExistingIndex', FakeIndex))
            stack.enter_context(patch.object(cli29, 'LocalEmbeddings', FakeEmbedding))
            stack.enter_context(patch.object(cli29, 'MeasuredOllama', side_effect=provider))
            stack.enter_context(patch.object(cli29, 'psutil', SimpleNamespace(__version__='offline-test')))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(redirect_stderr(io.StringIO()))
            return main(args)

    def test_baseline_is_preserved_and_only_focused_trials_are_generated(self):
        f = self.fixture
        core_before = engine29.code_fingerprint()
        old_template = engine29.COMPACT
        self.assertEqual(f.execute(f.args('run', '--profiles', 'baseline', 'candidate-q4')), 0)
        old = cli29.read_report(f.output)
        old_path = f.output
        baseline = [x for x in old['observations'] if x['identity']['profile_name'] == 'baseline']
        candidate = [x for x in old['observations'] if x['identity']['profile_name'] == 'candidate-q4']
        self.assertEqual(f.http.answer_calls, 6)
        f.output = f.root / 'focused.json'
        self.assertEqual(self.execute_focused(self.focused_args('run', '--retry-from', str(old_path))), 0)
        result = cli29.read_report(f.output)
        self.assertEqual(f.http.answer_calls, 9)
        self.assertEqual(result['new_answer_generation_calls'], 3)
        self.assertEqual(result['summary']['baseline']['reused_observations'], 3)
        self.assertEqual(result['summary']['focused-q4']['reused_observations'], 0)
        preserved = [x for x in result['observations'] if x['identity']['profile_name'] == 'baseline']
        self.assertEqual([x['job_key'] for x in baseline], [x['job_key'] for x in preserved])
        self.assertEqual([x['result'] for x in baseline], [x['result'] for x in preserved])
        focused = [x for x in result['observations'] if x['identity']['profile_name'] == 'focused-q4']
        self.assertEqual(candidate[0]['profile'], focused[0]['profile'])
        self.assertEqual(candidate[0]['identity']['evidence_sha256'], focused[0]['identity']['evidence_sha256'])
        self.assertNotEqual(candidate[0]['identity']['prompt_sha256'], focused[0]['identity']['prompt_sha256'])
        self.assertEqual(focused[0]['prepared']['messages'][0]['content'], FOCUSED)
        self.assertEqual(engine29.code_fingerprint(), core_before)
        self.assertEqual(engine29.COMPACT, old_template)
        counts = (f.http.answer_calls, f.http.probe_calls, f.http.warmups)
        self.assertEqual(self.execute_focused(self.focused_args()), 0)
        again = cli29.read_report(f.output)
        self.assertEqual((f.http.answer_calls, f.http.probe_calls, f.http.warmups), counts)
        self.assertEqual(again['new_answer_generation_calls'], 0)
        self.assertEqual(again['maintenance_generation_calls'], 0)
        self.assertEqual(again['summary']['focused-q4']['reused_observations'], 3)
        self.assertEqual(cli29.read_report(old_path), old)

    def test_partial_focused_run_only_completes_missing_trials(self):
        f = self.fixture
        self.assertEqual(f.execute(f.args()), 0)
        self.assertEqual(self.execute_focused(self.focused_args('run', '--max-new-observations', '2')), 0)
        self.assertEqual(f.http.answer_calls, 5)
        self.assertEqual(cli29.read_report(f.output)['state'], 'paused')
        self.assertEqual(self.execute_focused(self.focused_args()), 0)
        self.assertEqual(f.http.answer_calls, 6)
        report = cli29.read_report(f.output)
        self.assertEqual(report['summary']['baseline']['reused_observations'], 3)
        self.assertEqual(report['summary']['focused-q4']['reused_observations'], 2)
        self.assertEqual(report['new_answer_generation_calls'], 1)

    def test_portable_baseline_import_works_with_an_empty_cache(self):
        f = self.fixture
        self.assertEqual(f.execute(f.args()), 0)
        old_path = f.output
        f.cache_path = f.root / 'fresh.sqlite3'
        f.output = f.root / 'focused.json'
        self.assertEqual(self.execute_focused(self.focused_args('run', '--retry-from', str(old_path))), 0)
        self.assertEqual(f.http.answer_calls, 6)
        report = cli29.read_report(f.output)
        self.assertEqual(report['summary']['baseline']['reused_observations'], 3)
        self.assertEqual(report['new_answer_generation_calls'], 3)

    def test_failure_restores_original_template(self):
        original = engine29.COMPACT
        with patch.object(cli29, 'main', side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError):
                main(['verify', 'unused.json'])
        self.assertEqual(engine29.COMPACT, original)

    def test_v1_profile_file_cannot_be_silently_used_with_new_template(self):
        with self.assertRaises(ValueError):
            main(['run', '--profiles-file', str(self.fixture.profiles)])


if __name__ == '__main__':
    unittest.main()
