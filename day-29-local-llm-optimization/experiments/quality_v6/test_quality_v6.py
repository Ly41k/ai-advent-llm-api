"""Meaningful offline regressions. Scripted transport is not Qwen quality."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))
import cli29
import engine29
import test_focused_v2 as transport_fixture
from guard import inspect, supported_literal
from policy import FACTUAL, focus, is_verification_question, template
spec = importlib.util.spec_from_file_location('quality_v6_launcher', HERE / 'main.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def sample():
    catalog = [
        {'quote_id': 'e1-q1', 'excerpt': 1, 'quote': '## Commands\n```bash\narchivectl status vault42\narchivectl logs vault42\n```\nInspect process state and logs.'},
        {'quote_id': 'e1-q2', 'excerpt': 1, 'quote': 'After each run, the worker prints a backup result to the logs. Saved archives have timestamps and a configured recurring interval.'},
        {'quote_id': 'e1-q3', 'excerpt': 1, 'quote': '## Checklist\n| Requirement | Check |\n| Recurring backups | Check process and logs |'},
    ]
    question = 'How can I verify periodic backups?'
    return {'question': question, 'quote_catalog': catalog,
            'excerpts': [{'excerpt': 1, 'source': 'backups/README.md', 'section': 'README.md', 'text': '\n\n'.join(q['quote'] for q in catalog)}],
            'messages': [{'role': 'system', 'content': 'old'}, {'role': 'user', 'content': '{}'}]}


def observation(prepared, claims):
    return {'job_key': 'scripted-not-live', 'trial': 1,
            'identity': {'case': {'id': 'toy-unseen-in-prompt'}, 'profile_name': 'toy'},
            'prepared': prepared, 'result': {'status': 'ok', 'generation_called': True,
                'generation': {'answer': json.dumps({'claims': dict(zip(('c1', 'c2', 'c3', 'c4'), [*claims, *([None] * (4 - len(claims)))])), 'abstained': False})}}}


class GuardTests(unittest.TestCase):
    def test_command_cannot_borrow_support_from_neighboring_quote(self):
        p = sample()
        row = observation(p, [{'quote_id': 'e1-q3', 'statement': 'Use `archivectl status vault42` to inspect process state.'}])
        value = inspect(row)
        self.assertEqual(value['decision'], 'blocked')
        issue = next(i for i in value['issues'] if i['kind'] == 'unsupported_technical_fragment')
        self.assertIn('archivectl status vault42', issue['fragments'])

    def test_unquoted_command_is_checked_and_changed_arguments_blocked(self):
        p = sample()
        row = observation(p, [{'quote_id': 'e1-q1', 'statement': 'Use archivectl status another_vault to inspect process state.'}])
        self.assertTrue(any(i['kind'] == 'unsupported_technical_fragment' for i in inspect(row)['issues']))

    def test_status_is_not_execution_proof_even_with_correct_quote(self):
        p = sample()
        row = observation(p, [{'quote_id': 'e1-q1', 'statement': 'Confirm execution of backups using `archivectl status vault42`.'}])
        self.assertTrue(any(i['kind'] == 'process_status_is_not_execution_proof' for i in inspect(row)['issues']))

    def test_complete_documented_procedure_still_requires_semantic_review(self):
        p = sample()
        row = observation(p, [
            {'quote_id': 'e1-q1', 'statement': 'Use `archivectl status vault42` and `archivectl logs vault42` to inspect process state and logs.'},
            {'quote_id': 'e1-q2', 'statement': 'Check the backup result after each run in logs and compare saved archives with timestamps against the recurring interval.'},
        ])
        value = inspect(row)
        self.assertEqual(value['issues'], [])
        self.assertEqual(value['decision'], 'ready_for_manual_review')
        self.assertTrue(value['human_semantic_review_required'])
        self.assertFalse(value['semantically_verified'])
        self.assertFalse(value['automatic_publication_allowed'])

    def test_process_and_logs_without_recurring_results_are_incomplete(self):
        p = sample()
        row = observation(p, [{'quote_id': 'e1-q1', 'statement': 'Use `archivectl status vault42` and `archivectl logs vault42` to check process state and logs.'}])
        self.assertIn('incomplete_periodic_procedure', [i['kind'] for i in inspect(row)['issues']])

    def test_literal_boundaries_preserve_names_but_accept_path_basename(self):
        self.assertFalse(supported_literal('worker.py', 'other_worker.py'))
        self.assertTrue(supported_literal('worker.py', '/opt/app/worker.py'))
        self.assertFalse(supported_literal('TOKEN', 'OTHER_TOKEN'))
        self.assertTrue(supported_literal('archivectl status vault42', 'archivectl   status\n vault42'))

    def test_audit_does_not_edit_raw_answer_or_evidence(self):
        row = observation(sample(), [{'quote_id': 'e1-q3', 'statement': 'Use `archivectl status vault42`.'}])
        original = deepcopy(row)
        inspect(row)
        self.assertEqual(row, original)

    def test_focus_is_exact_and_removes_detailed_command_distractor(self):
        original = sample()
        p = focus(original)
        self.assertEqual([q['quote_id'] for q in p['quote_catalog']], ['e1-q1', 'e1-q2'])
        self.assertEqual(p['quote_catalog'], original['quote_catalog'][:2])
        self.assertEqual(len(original['quote_catalog']), 3)
        self.assertNotIn('expected_terms', p['messages'][1]['content'])

    def test_focus_falls_back_rather_than_discarding_all_evidence(self):
        p = sample()
        p['quote_catalog'] = p['quote_catalog'][-1:]
        self.assertEqual(focus(p)['quote_catalog'], p['quote_catalog'])

    def test_language_preference_preserves_unique_foreign_language_evidence(self):
        p = sample()
        p['question'] = 'Как проверить периодическое архивирование?'
        p['excerpts'].append({'excerpt': 2, 'source': 'backups/README.ru.md', 'section': 'README.ru.md', 'text': 'Снимки сохраняются.'})
        p['quote_catalog'].append({'quote_id': 'e2-q1', 'excerpt': 2, 'quote': 'Снимки сохраняются.'})
        q = focus(p)['quote_catalog']
        self.assertEqual(q[0]['quote_id'], 'e2-q1')
        self.assertIn('e1-q1', [item['quote_id'] for item in q])

    def test_all_explicit_projects_are_kept_and_unrelated_project_excluded(self):
        p = sample()
        p['question'] = 'How can I verify the services on Day 18 and Day 20?'
        p['excerpts'][0]['source'] = 'day-18-backups/README.md'
        for n, day in ((2, 20), (3, 22)):
            p['excerpts'].append({'excerpt': n, 'source': f'day-{day}-services/README.md', 'section': 'Services', 'text': 'Inspect the process.'})
            p['quote_catalog'].append({'excerpt': n, 'quote_id': f'e{n}-q1', 'quote': 'Inspect the process.'})
        ids = [item['quote_id'] for item in focus(p)['quote_catalog']]
        self.assertIn('e1-q1', ids)
        self.assertIn('e2-q1', ids)
        self.assertNotIn('e3-q1', ids)

    def test_detailed_procedure_table_is_not_mistaken_for_assignment_overview(self):
        p = sample()
        p['quote_catalog'].append({'excerpt': 1, 'quote_id': 'e1-q4', 'quote': '| Step | Command |\n|---|---|\n| Inspect state | archivectl status vault42 |'})
        self.assertIn('e1-q4', [q['quote_id'] for q in focus(p)['quote_catalog']])

    def test_templates_do_not_contain_expected_domain_answers(self):
        for q in ('Как проверить периодическое архивирование?', 'How do I verify recurring backups?'):
            text = template(q)
            self.assertNotIn('base-10', text)
            self.assertNotIn('bublik-day18', text)
            self.assertNotIn('get_github_summary', text)
            self.assertNotIn('journalctl', text)


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.transport = transport_fixture.FocusedTests('test_portable_baseline_import_works_with_an_empty_cache')
        self.transport.setUp()
        self.addCleanup(self.transport.doCleanups)
        self.f = self.transport.fixture
        profiles = engine29.load_profiles(HERE.parent / 'focused_v3' / 'profiles.json')
        self.f.profiles.write_text(json.dumps({k: profiles[k] for k in ('baseline', 'focused-v3-q4')}))
        case = json.loads(self.f.questions.read_text())[0]
        # This lacks procedure evidence on purpose. Its three quality failures
        # must be retained and never retried to achieve a passing result.
        self.f.questions.write_text(json.dumps([case, {**case, 'id': 'procedure', 'question': 'How can I verify periodic jobs?'}]))

    def test_changed_procedure_only_three_calls_then_zero_even_if_quality_blocked(self):
        f = self.f
        with patch.object(engine29, 'COMPACT', FACTUAL):
            self.assertEqual(f.execute(f.args('run', '--profiles', 'baseline', 'focused-v3-q4')), 0)
        old_path = f.output
        original = old_path.read_bytes()
        f.output, f.cache_path = f.root / 'v6.json', f.root / 'new.sqlite3'
        args = f.args('run', '--profiles', 'baseline', 'focused-v3-q4', '--retry-from', str(old_path))
        del args[1:3]
        with patch.object(transport_fixture, 'main', launcher.main):
            self.assertEqual(self.transport.execute_focused(args), 1)
            report = cli29.read_report(f.output)
            self.assertEqual(report['new_answer_generation_calls'], 3)
            self.assertEqual(sum(e['reused'] for e in report['observations']), 9)
            value = json.loads(f.output.with_suffix('.quality.json').read_text())
            self.assertEqual(value['summary']['focused-v3-q4']['blocked'], 3)
            counts = f.http.answer_calls, f.http.probe_calls, f.http.warmups
            self.assertEqual(self.transport.execute_focused(args), 1)
            self.assertEqual((f.http.answer_calls, f.http.probe_calls, f.http.warmups), counts)
            report = cli29.read_report(f.output)
            self.assertEqual(report['new_answer_generation_calls'], 0)
            self.assertEqual(report['maintenance_generation_calls'], 0)
        self.assertEqual(old_path.read_bytes(), original)

    def test_restores_router_after_error_and_preserves_factual_identity(self):
        profile = engine29.load_profiles(self.f.profiles)['focused-v3-q4']
        with patch.object(engine29, 'COMPACT', FACTUAL):
            factual = engine29.prompt_for(self.f.prepared, profile)
        before = cli29.prompt_for, engine29.COMPACT, engine29.code_fingerprint()
        with self.assertRaises(RuntimeError):
            with launcher.task_templates():
                self.assertEqual(cli29.prompt_for(self.f.prepared, profile), factual)
                raise RuntimeError('scripted')
        self.assertEqual((cli29.prompt_for, engine29.COMPACT, engine29.code_fingerprint()), before)

    def test_maximum_three_repeats_is_enforced(self):
        with self.assertRaisesRegex(ValueError, 'at most three'):
            launcher.main(['plan', '--repeats', '4'])

    def test_audit_cannot_overwrite_original_json_or_markdown(self):
        self.f.execute(self.f.args())
        original = self.f.output.read_bytes()
        with self.assertRaises(ValueError):
            launcher.write_audit(self.f.output, self.f.output)
        self.assertEqual(self.f.output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
