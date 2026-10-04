"""Presentation regression tests with real uploaded source evidence; no Ollama."""

import copy
import io
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import console_demo as demo


class ConsoleDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = demo.read_json(demo.SAVED)
        cls.threshold = demo.read_json(demo.THRESHOLD)

    def result(self):
        return copy.deepcopy(self.report['details'][6]['result'])

    def test_all_uploaded_evidence(self):
        checks = [demo.check_evidence(row['result']) for row in self.report['details']]
        self.assertTrue(all(c['ok'] for c in checks), checks)
        self.assertEqual(sum(c['verified_quotes'] for c in checks), 53)

    def test_changed_quote_is_rejected(self):
        result = self.result()
        result['quotes'][0]['quote'] = 'Invented repository revenue: 100 million dollars.'
        self.assertFalse(demo.check_evidence(result)['ok'])

    def test_claim_bound_to_different_quote_is_rejected(self):
        result = self.result()
        result['claims'][0]['citations'] = result['claims'][1]['citations']
        self.assertFalse(demo.check_evidence(result)['ok'])

    def test_invented_public_answer_is_rejected(self):
        result = self.result()
        result['answer'] += '\nThe agent collects everything itself.'
        self.assertFalse(demo.check_evidence(result)['ok'])

    def test_wrong_source_lines_are_rejected(self):
        result = self.result()
        result['sources'][0]['start_line'] += 2
        self.assertFalse(demo.check_evidence(result)['ok'])

    def test_wrong_quote_lines_are_rejected(self):
        result = self.result()
        result['quotes'][0]['end_line'] += 1
        self.assertFalse(demo.check_evidence(result)['ok'])

    def test_file_outside_repository_is_rejected(self):
        with self.assertRaises(ValueError):
            demo.source_path(demo.ROOT, '../outside.txt')
        with self.assertRaises(ValueError):
            demo.source_path(demo.ROOT, '/etc/passwd')

    def test_missing_quote_is_rejected(self):
        result = self.result()
        result['quotes'].pop()
        self.assertFalse(demo.check_evidence(result)['ok'])

    def test_actual_refusal_and_threshold(self):
        self.assertTrue(demo.check_evidence(self.threshold)['ok'])
        ok, maximum, threshold = demo.check_threshold(self.threshold)
        self.assertTrue(ok)
        self.assertAlmostEqual(maximum, .5939477446770604)
        self.assertEqual(threshold, .99)

    def test_refusal_without_clarification_is_rejected(self):
        result = copy.deepcopy(self.threshold)
        result['clarification'] = ''
        self.assertFalse(demo.check_evidence(result)['ok'])

    def test_threshold_reason_does_not_override_scores(self):
        result = copy.deepcopy(self.threshold)
        result['retrieval']['candidates'][0]['cosine'] = 1.0
        self.assertFalse(demo.check_threshold(result)[0])

    def test_refusal_with_model_call_fails_pre_generation_gate(self):
        result = copy.deepcopy(self.threshold)
        result['validation']['model_calls'] = [{'stage': 'extractive_selector'}]
        self.assertFalse(demo.check_threshold(result)[0])

    def test_recorded_manual_review_kept_separate_from_model(self):
        checks = [demo.check_evidence(r['result']) for r in self.report['details']]
        summary = demo.totals(self.report, checks, True)
        self.assertEqual(summary['model_coverage'], 7)
        self.assertEqual(summary['recorded_manual_complete'], 10)
        self.assertTrue(summary['assignment_review_complete'])
        self.assertFalse(self.report['summary']['assignment_complete'])

    def test_new_unreviewed_run_is_never_completed_automatically(self):
        report = copy.deepcopy(self.report)
        for row in report['details']:
            row['manual_review'] = {}
        checks = [demo.check_evidence(r['result']) for r in report['details']]
        summary = demo.totals(report, checks, True)
        self.assertEqual(summary['source_quote_contract'], 10)
        self.assertEqual(summary['recorded_manual_complete'], 0)
        self.assertFalse(summary['assignment_review_complete'])

    def test_partial_report_is_not_full_assignment(self):
        report = copy.deepcopy(self.report)
        report['details'] = report['details'][6:7]
        checks = [demo.check_evidence(report['details'][0]['result'])]
        self.assertFalse(demo.totals(report, checks, True)['assignment_review_complete'])

    def test_console_shows_evidence_and_negative_verdict(self):
        output = io.StringIO()
        with redirect_stdout(output):
            demo.present(self.report['details'][0], demo.Console(pause=False))
        text = output.getvalue()
        for value in ('chunk_id:', 'section:', 'ЦИТАТА', 'Модельный аудит полноты: НЕТ',
                      'covered=False', 'РУЧНОЙ ПРОВЕРКЕ', 'PASS'):
            self.assertIn(value, text)

    def test_full_console_replay_cli(self):
        output = io.StringIO()
        with patch('sys.argv', ['console_demo.py', '--no-pause']), redirect_stdout(output):
            self.assertEqual(demo.main(), 0)
        text = output.getvalue()
        for value in ('ПРОСМОТР СОХРАНЁННОГО', 'Ответы: 10/10', 'цитат проверено: 53',
                      'аудит полноты: 7/10', 'контрольные отказы с уточнением: 2/2',
                      'Исходный summary.assignment_complete: False', 'max cosine=0.593947'):
            self.assertIn(value, text)

    def test_live_orchestration_saves_new_unreviewed_report(self):
        # Scripted provider for presentation plumbing only; no model-quality claim.
        from pathlib import Path
        class ScriptedAgent:
            def __init__(inner, kb, provider, settings, **options):
                inner.threshold = settings.min_similarity
            def ask(inner, question):
                result = (self.threshold if inner.threshold == .99 else
                          next(r['result'] for r in self.report['details'] if r['question'] == question))
                return SimpleNamespace(to_dict=lambda: copy.deepcopy(result))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'live.json'
            threshold = Path(directory) / 'threshold.json'
            with patch('support24.KnowledgeBase') as kb, patch('grounded_agent.StructuredOllama'), \
                    patch('strict_agent.StrictRAGAgent', ScriptedAgent), redirect_stdout(io.StringIO()):
                args = SimpleNamespace(report=path, threshold_report=threshold, db=Path('unused.db'), url='unused')
                report, experiment, checks, _, _ = demo.live_run(args, demo.Console(pause=False))
            self.assertTrue(path.exists() and path.with_suffix('.md').exists() and threshold.exists())
            self.assertEqual(len(list((path.parent / 'live_answers').glob('*.json'))), 12)
            self.assertTrue(all(c['ok'] for c in checks))
            self.assertFalse(report['summary']['assignment_complete'])
            self.assertTrue(all(r['manual_review']['fully_answers_question'] is None for r in report['details']))
            self.assertFalse(demo.totals(report, checks, True)['assignment_review_complete'])
            kb.return_value.close.assert_called_once()

    def test_live_refuses_to_overwrite_existing_report(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing.json'
            path.write_text('preserve this report')
            args = SimpleNamespace(report=path, threshold_report=Path(directory) / 'threshold.json')
            with self.assertRaises(ValueError):
                demo.live_run(args, demo.Console(pause=False))
            self.assertEqual(path.read_text(), 'preserve this report')


if __name__ == '__main__':
    unittest.main()
