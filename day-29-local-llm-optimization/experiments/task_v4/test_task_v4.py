"""Offline identity and resume tests; scripted answers do not assess semantics."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

import cli29
import engine29
import test_focused_v2 as transport_fixture
spec = importlib.util.spec_from_file_location('task_v4_launcher', HERE / 'main.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
task_templates, main = launcher.task_templates, launcher.main
from templates4 import FACTUAL, VERIFICATION, is_verification_question


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.transport = transport_fixture.FocusedTests('test_portable_baseline_import_works_with_an_empty_cache')
        self.transport.setUp()
        self.addCleanup(self.transport.doCleanups)
        self.f = self.transport.fixture
        profiles = engine29.load_profiles(HERE.parent / 'focused_v3' / 'profiles.json')
        self.f.profiles.write_text(json.dumps({k: profiles[k] for k in ('baseline', 'focused-v3-q4')}))
        case = json.loads(self.f.questions.read_text())[0]
        procedure = {**case, 'id': 'procedure', 'question': 'How can I verify the scheduled worker runs?'}
        self.f.questions.write_text(json.dumps([case, procedure]))

    def test_router_changes_only_verification_questions_in_optimized_profile(self):
        prepared = self.f.prepared
        profile = engine29.load_profiles(self.f.profiles)['focused-v3-q4']
        with patch.object(engine29, 'COMPACT', FACTUAL):
            factual = engine29.prompt_for(prepared, profile)
        procedural_input = deepcopy(prepared)
        procedural_input['question'] = 'Как проверить работу фонового процесса?'
        procedural_input['messages'][1]['content'] = json.dumps({'question': procedural_input['question'], 'excerpts': procedural_input['excerpts']})
        baseline = engine29.load_profiles(self.f.profiles)['baseline']
        before = engine29.prompt_for(procedural_input, baseline)
        core = engine29.code_fingerprint()
        with task_templates():
            self.assertEqual(cli29.prompt_for(prepared, profile), factual)
            changed = cli29.prompt_for(procedural_input, profile)
            self.assertEqual(changed['messages'][0]['content'], VERIFICATION)
            self.assertNotEqual(changed['prompt_sha256'], factual['prompt_sha256'])
            self.assertEqual(cli29.prompt_for(procedural_input, baseline), before)
            self.assertEqual(engine29.evidence_payload(changed), engine29.evidence_payload(procedural_input))
        self.assertEqual(engine29.code_fingerprint(), core)

    def test_old_report_import_only_generates_three_changed_procedural_answers(self):
        f = self.f
        with patch.object(engine29, 'COMPACT', FACTUAL):
            self.assertEqual(f.execute(f.args('run', '--profiles', 'baseline', 'focused-v3-q4')), 0)
        original = cli29.read_report(f.output)
        self.assertEqual(f.http.answer_calls, 12)
        old_path = f.output
        f.cache_path = f.root / 'new-cache.sqlite3'
        f.output = f.root / 'v4.json'
        args = f.args('run', '--profiles', 'baseline', 'focused-v3-q4', '--retry-from', str(old_path))
        del args[1:3]
        with patch.object(transport_fixture, 'main', main):
            self.assertEqual(self.transport.execute_focused(args), 0)
            result = cli29.read_report(f.output)
            self.assertEqual(f.http.answer_calls, 15)
            self.assertEqual(result['new_answer_generation_calls'], 3)
            self.assertEqual(sum(x['reused'] for x in result['observations']), 9)
            old_keys={x['job_key'] for x in original['observations']}
            fresh = [x for x in result['observations'] if not x['reused']]
            self.assertEqual(len(fresh), 3)
            self.assertTrue(all(x['identity']['profile_name']=='focused-v3-q4' and x['identity']['case']['id']=='procedure' for x in fresh))
            self.assertTrue(all(x['job_key'] not in old_keys for x in fresh))
            old_rows={(x['job_key'], x['trial']): x['result'] for x in original['observations']}
            for row in result['observations']:
                if row['reused']:
                    self.assertEqual(row['result'], old_rows[(row['job_key'], row['trial'])])
            counts = f.http.answer_calls, f.http.probe_calls, f.http.warmups
            self.assertEqual(self.transport.execute_focused(args), 0)
            self.assertEqual((f.http.answer_calls, f.http.probe_calls, f.http.warmups), counts)
            again = cli29.read_report(f.output)
            self.assertEqual(again['new_answer_generation_calls'], 0)
            self.assertEqual(again['maintenance_generation_calls'], 0)
        self.assertEqual(cli29.read_report(old_path), original)

    def test_router_uses_question_forms_instead_of_benchmark_answers(self):
        self.assertTrue(is_verification_question('Как на любом сервере проверить периодическую выгрузку?'))
        self.assertTrue(is_verification_question('How do I verify scheduled backups?'))
        self.assertFalse(is_verification_question('Which process collects snapshots?'))
        self.assertFalse(is_verification_question('What is the name of verify_report?'))
        self.assertFalse(is_verification_question('How does the client discover tools?'))
        self.assertNotIn('systemctl', VERIFICATION)
        self.assertNotIn('journalctl', VERIFICATION)
        self.assertNotIn('base-10', VERIFICATION)

    def test_template_and_router_are_restored_after_failure(self):
        before = engine29.COMPACT, cli29.prompt_for
        with self.assertRaises(RuntimeError):
            with task_templates():
                raise RuntimeError('scripted')
        self.assertEqual((engine29.COMPACT, cli29.prompt_for), before)


if __name__ == '__main__':
    unittest.main()
