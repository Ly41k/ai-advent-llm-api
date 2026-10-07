"""V13 routing and evidence provenance regressions; never paid inference."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_day28 as fixtures
from main import parser, run
from rag28 import prepare, prepare_synthesis, observe, StructuredHTTP, parse_answer
from cloud28 import OpenAIProvider
from providers import Generation
from prompts28 import complete_prompt
from retry28 import retry_plan
from verify_report import verify


class CoverageTests(unittest.TestCase):
    def setUp(self):
        fixtures.Tests.setUp(self)

    def cases_file(self):
        return fixtures.Tests.cases_file(self)

    def test_profile_changes_instructions_without_changing_retrieval_or_injecting_rubric(self):
        enhanced = prepare(self.kb, self.embedding, fixtures.CASE['question'], self.settings,
                           quality_mode='coverage')
        for key in ('question', 'excerpts', 'quote_catalog', 'retrieval'):
            self.assertEqual(enhanced[key], self.prepared[key])
        self.assertEqual(enhanced['messages'][1], self.prepared['messages'][1])
        self.assertNotEqual(enhanced['prompt_sha256'], self.prepared['prompt_sha256'])
        again = prepare(self.kb, self.embedding, fixtures.CASE['question'], self.settings)
        self.assertEqual(again['messages'], self.prepared['messages'])
        model = fixtures.Model()
        case = dict(fixtures.CASE, expected_terms=['unseen-rubric-marker'])
        row = observe(model, enhanced, case)
        self.assertNotIn('unseen-rubric-marker', json.dumps(model.calls))
        self.assertFalse(row['quality']['passed'])
        empty = prepare(self.kb, self.embedding, fixtures.CASE['question'], self.settings,
                        max_context_chars=1, quality_mode='coverage')
        model = fixtures.Model()
        observe(model, empty, dict(fixtures.CASE, answerable=False))
        self.assertEqual(model.calls, [])

    def test_selective_probe_calls_failed_cloud_once_and_freezes_successful_local(self):
        with redirect_stdout(io.StringIO()):
            baseline, _ = fixtures.Tests.make_baseline(self, cloud_bad=True)
        original = baseline.output.read_bytes()
        args = parser().parse_args(['compare', '--only-provider', 'cloud', '--quality-mode', 'coverage',
            '--db', str(self.path), '--questions', str(baseline.questions), '--repeats', '1',
            '--retry-from', str(baseline.output), '--output', str(Path(self.tmp.name) / 'probe.json')])
        plan = retry_plan(baseline.output, [fixtures.CASE], vars(args), 'compare', 1, 'cloud')
        self.assertEqual(plan['generation_upper_bound'], {'local': 0, 'cloud': 1})
        cloud = fixtures.Model(); cloud.name = 'cloud'; cloud.model = 'openai/gpt-oss-20b'
        local = fixtures.Model()
        local.doctor = lambda: (_ for _ in ()).throw(AssertionError('local preflight'))
        local.generate = lambda _: (_ for _ in ()).throw(AssertionError('local generation'))
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), \
                patch('main.LocalEmbeddings', return_value=fixtures.Embed()), \
                patch('main.OllamaProvider', return_value=local), \
                patch('main.GroqProvider', return_value=cloud), \
                patch('main.cloud_key', return_value='offline-placeholder'), redirect_stdout(io.StringIO()):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text())
        self.assertEqual(len(cloud.calls), 1)
        self.assertEqual(len(report['results']), 1)
        self.assertEqual(report['schema_version'], 13)
        self.assertTrue(verify(report)['passed'])
        self.assertEqual(baseline.output.read_bytes(), original)
        self.assertTrue(verify(json.loads(original), require_success=False)['passed'])
        retained = retry_plan(args.output, [fixtures.CASE], vars(args), 'compare', 1, 'cloud')
        self.assertEqual(retained['planned_observations'], [])
        for field in ('quality_mode', 'prompt_revision'):
            corrupt = deepcopy(report); corrupt[field] = 'baseline'
            self.assertFalse(verify(corrupt)['passed'])
        corrupt = deepcopy(report)
        trace = corrupt['retrievals'][0]
        trace['messages'][0]['content'] = 'Changed instructions'
        trace['prompt_sha256'] = hashlib.sha256(json.dumps(trace['messages'], ensure_ascii=False,
                                                        sort_keys=True).encode()).hexdigest()
        corrupt['results'][0]['prompt_sha256'] = trace['prompt_sha256']
        self.assertFalse(verify(corrupt)['passed'])

    def test_new_synthesis_preserves_selected_only_evidence_and_legacy_prompt(self):
        selected = json.loads(fixtures.Model().raw)
        selected['claims']['c1']['statement'] = 'unsupported-first-stage-text'
        old = prepare_synthesis(self.prepared, json.dumps(selected))
        enhanced = deepcopy(self.prepared); enhanced['quality_mode'] = 'coverage'
        enhanced['quote_catalog'].append({'quote_id': 'e1-q2', 'excerpt': 1,
                                          'quote': 'unselected-distractor'})
        new = prepare_synthesis(enhanced, json.dumps(selected))
        self.assertEqual(old['messages'][1], new['messages'][1])
        self.assertEqual(old['quote_catalog'], new['quote_catalog'])
        self.assertNotIn('unsupported-first-stage-text', json.dumps(new['messages']))
        self.assertNotIn('unselected-distractor', json.dumps(new['messages']))
        self.assertNotEqual(old['prompt_sha256'], new['prompt_sha256'])
        self.assertEqual(prepare_synthesis(self.prepared, json.dumps(selected)), old)

    def test_coverage_synthesis_report_reconstructs_both_stages(self):
        args = parser().parse_args(['evaluate', '--quality-mode', 'coverage', '--synthesis',
            '--db', str(self.path), '--questions', str(self.cases_file()), '--repeats', '1',
            '--output', str(Path(self.tmp.name) / 'synthesis.json')])
        model = fixtures.SynthesisModel()
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), \
                patch('main.LocalEmbeddings', return_value=fixtures.Embed()), \
                patch('main.OllamaProvider', return_value=model), \
                patch('main.cloud_key', side_effect=AssertionError('cloud key')), redirect_stdout(io.StringIO()):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text())
        self.assertEqual(len(model.calls), 2)
        self.assertTrue(verify(report)['passed'])
        corrupt = deepcopy(report)
        corrupt['results'][0]['synthesis']['messages'][0]['content'] = 'Changed synthesis'
        self.assertFalse(verify(corrupt)['passed'])

    def test_complete_answer_uses_one_openai_call_and_full_original_catalog(self):
        args = parser().parse_args(['compare', '--only-provider', 'cloud', '--cloud-provider', 'openai',
            '--quality-mode', 'complete', '--db', str(self.path), '--questions', str(self.cases_file()),
            '--repeats', '1', '--output', str(Path(self.tmp.name) / 'complete.json')])
        raw = json.dumps({'answer': 'The worker runs jobs.', 'abstained': False,
                          'quote_ids': {'q1': 'e1-q1', 'q2': None, 'q3': None, 'q4': None}})
        class DirectCloud(OpenAIProvider):
            calls = []
            def doctor(self):
                return {'cloud_api': 'openai', 'url': self.url, 'model': self.model}
            def generate(self, messages):
                self.calls.append(messages)
                return Generation('cloud', self.model, raw, .2, 100, 30, 'stop', True)
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), \
                patch('main.LocalEmbeddings', return_value=fixtures.Embed()), \
                patch('main.OpenAIProvider', DirectCloud), \
                patch('main.cloud_key', return_value='offline-placeholder'), redirect_stdout(io.StringIO()):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text()); trace = report['retrievals'][0]
        self.assertEqual(len(DirectCloud.calls), 1)
        self.assertEqual(trace['quote_catalog'], self.prepared['quote_catalog'])
        self.assertEqual(json.loads(trace['messages'][1]['content'])['excerpts'],
                         json.loads(self.prepared['messages'][1]['content'])['excerpts'])
        self.assertNotIn('synthesis', report['results'][0])
        self.assertTrue(verify(report)['passed'])
        legacy = deepcopy(report)
        legacy.update(schema_version=14, prompt_revision='complete_answer_v14')
        old_trace = legacy['retrievals'][0]
        old_trace.pop('answer_prompt_revision')
        old_trace['messages'][0]['content'] = complete_prompt('v14')
        old_trace['prompt_sha256'] = hashlib.sha256(json.dumps(old_trace['messages'], ensure_ascii=False,
                                                            sort_keys=True).encode()).hexdigest()
        legacy['results'][0]['prompt_sha256'] = old_trace['prompt_sha256']
        self.assertTrue(verify(legacy)['passed'])
        corrupt = deepcopy(report)
        corrupt['retrievals'][0]['answer_prompt_revision'] = 'v14'
        self.assertFalse(verify(corrupt)['passed'])
        with patch('rag28.ReliableHTTP.request', return_value={}) as request:
            StructuredHTTP(rate_retries=0).request(OpenAIProvider.url + '/chat/completions',
                {'model': OpenAIProvider.default_model, 'messages': trace['messages']})
        schema = request.call_args.args[1]['response_format']['json_schema']['schema']
        self.assertIn('answer', schema['properties']); self.assertNotIn('claims', schema['properties'])
        self.assertEqual(schema['properties']['quote_ids']['properties']['q1']['enum'], [None, 'e1-q1'])
        corrupt = deepcopy(report); corrupt['retrievals'][0]['quality_mode'] = 'coverage'
        self.assertFalse(verify(corrupt)['passed'])
        invalid = json.loads(raw); invalid['quote_ids']['q1'] = 'e99-q1'
        with self.assertRaises(ValueError):
            parse_answer(json.dumps(invalid), trace['excerpts'], trace['quote_catalog'], trace['output_contract'])

    def test_complete_mode_rejects_second_stage_before_any_access(self):
        args = parser().parse_args(['evaluate', '--quality-mode', 'complete', '--synthesis'])
        with patch('main.ExistingIndex', side_effect=AssertionError('index access')), \
                patch('main.cloud_key', side_effect=AssertionError('key access')):
            with self.assertRaisesRegex(ValueError, 'without --synthesis'):
                run(args)
        complete = prepare(self.kb, self.embedding, fixtures.CASE['question'], self.settings,
                           quality_mode='complete')
        with self.assertRaisesRegex(ValueError, 'synthesis is unsupported'):
            prepare_synthesis(complete, fixtures.Model().raw)

    def phase_fixture(self):
        text = ('## Before\n\nInputGuard checks requests before the model call.\n\n'
                '## After\n\nOutputGuard checks generated answers before persistence.')
        doc = fixtures.Document('worker.py', 'Checks', text, hashlib.sha256(text.encode()).hexdigest())
        for strategy in ('fixed', 'structural'):
            chunk = fixtures.Chunk(strategy + '-phases', doc.source, doc.title, 'checks', strategy,
                                   text, 1, len(text.splitlines()), 20)
            self.kb.save([doc], strategy, [chunk], [[1., 0.]], 'bge-m3', 500, 75, 'commit@fingerprint')
        case = dict(fixtures.CASE, question='Where are checks performed around the model call?',
                    expected_terms=['InputGuard', 'OutputGuard'])
        raw = {'phases': {'before': {'quote_id': 'e1-q1',
                                     'statement': 'Before: InputGuard checks requests before the model call.'},
                          'after': {'quote_id': 'e1-q2',
                                    'statement': 'After: OutputGuard checks generated answers before persistence.'}},
               'abstained': False}
        prepared = prepare(self.kb, self.embedding, case['question'], self.settings, quality_mode='phases')
        return case, raw, prepared

    def test_phase_contract_requires_both_distinct_evidence_bindings_and_valid_abstention(self):
        _, raw, prepared = self.phase_fixture()
        parse = lambda v: parse_answer(json.dumps(v), prepared['excerpts'], prepared['quote_catalog'],
                                       prepared['output_contract'])
        value = parse(raw)
        self.assertEqual(len(value['citations']), 2)
        self.assertEqual(value['answer'], raw['phases']['before']['statement']+'\n'+raw['phases']['after']['statement'])
        for change in ('missing_before', 'missing_after', 'reuse', 'unknown', 'extra', 'bad_boolean'):
            invalid = deepcopy(raw)
            if change.startswith('missing_'):invalid['phases'][change.removeprefix('missing_')] = None
            elif change == 'reuse':invalid['phases']['after']['quote_id'] = 'e1-q1'
            elif change == 'unknown':invalid['phases']['after']['quote_id'] = 'e99-q1'
            elif change == 'extra':invalid['answer'] = 'unbound text'
            else:invalid['abstained'] = 0
            with self.assertRaises(ValueError):parse(invalid)
        self.assertTrue(parse({'phases': {'before': None, 'after': None}, 'abstained': True})['abstained'])
        with self.assertRaises(ValueError):parse(dict(raw, abstained=True))

    def test_phase_report_one_openai_call_native_schema_and_provenance(self):
        case, raw, prepared = self.phase_fixture()
        questions = Path(self.tmp.name) / 'phase-questions.json'; questions.write_text(json.dumps([case]))
        args = parser().parse_args(['compare', '--only-provider', 'cloud', '--cloud-provider', 'openai',
            '--quality-mode', 'phases', '--db', str(self.path), '--questions', str(questions),
            '--repeats', '1', '--output', str(Path(self.tmp.name) / 'phases.json')])
        class PhaseCloud(OpenAIProvider):
            calls = []
            def doctor(self):return {'cloud_api': 'openai', 'url': self.url, 'model': self.model}
            def generate(self, messages):
                self.calls.append(messages)
                return Generation('cloud', self.model, json.dumps(raw), .2, 100, 30, 'stop', True)
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), \
                patch('main.LocalEmbeddings', return_value=fixtures.Embed()), \
                patch('main.OpenAIProvider', PhaseCloud), patch('main.cloud_key', return_value='offline-placeholder'), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text())
        self.assertEqual(len(PhaseCloud.calls), 1)
        self.assertEqual(report['schema_version'], 16)
        self.assertTrue(verify(report)['passed'])
        with patch('rag28.ReliableHTTP.request', return_value={}) as request:
            StructuredHTTP(rate_retries=0).request(OpenAIProvider.url + '/chat/completions',
                {'model': OpenAIProvider.default_model, 'messages': prepared['messages']})
        schema = request.call_args.args[1]['response_format']['json_schema']['schema']
        self.assertEqual(schema['properties']['phases']['required'], ['before', 'after'])
        for name in ('before', 'after'):
            self.assertEqual(schema['properties']['phases']['properties'][name]['properties']['quote_id']['enum'],
                             ['e1-q1', 'e1-q2'])
        corrupt = deepcopy(report); corrupt['retrievals'][0]['quality_mode'] = 'complete'
        self.assertFalse(verify(corrupt)['passed'])
        with self.assertRaisesRegex(ValueError, 'synthesis is unsupported'):
            prepare_synthesis(prepared, json.dumps(raw))
        args.synthesis = True
        with patch('main.ExistingIndex', side_effect=AssertionError('index access')):
            with self.assertRaisesRegex(ValueError, 'without --synthesis'):
                run(args)


if __name__ == '__main__':
    unittest.main()
