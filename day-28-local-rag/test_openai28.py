"""OpenAI routing/provenance/contract regressions; no paid requests."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_day28 as fixtures
from cloud28 import OpenAIProvider
from bridge28 import ProviderError
from providers import Generation
from main import parser, run, cloud_key
from rag28 import StructuredHTTP, prepare_synthesis
from retry28 import retry_plan
from verify_report import verify


class FakeOpenAI(OpenAIProvider):
    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []
        self.instances.append(self)

    def doctor(self):
        return {'available': True, 'cloud_api': 'openai', 'url': self.url, 'model': self.model}

    def generate(self, messages):
        self.calls.append(messages)
        return Generation('cloud', self.model, fixtures.Model().raw, .2, 100, 30, 'stop', True)


class OpenAITests(unittest.TestCase):
    def setUp(self):
        fixtures.Tests.setUp(self)

    def args(self, *extra):
        questions = Path(self.tmp.name) / 'questions.json'
        questions.write_text(json.dumps([fixtures.CASE]))
        return parser().parse_args(['compare', '--only-provider', 'cloud', '--cloud-provider', 'openai',
            '--db', str(self.path), '--questions', str(questions), '--repeats', '3',
            '--output', str(Path(self.tmp.name) / 'openai.json'), *extra])

    def test_openai_cloud_only_report_keeps_local_uninvoked_and_checks_provenance(self):
        args = self.args()
        local, embedding = fixtures.Model(), fixtures.Embed()
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), \
                patch('main.LocalEmbeddings', return_value=embedding), \
                patch('main.OllamaProvider', return_value=local), \
                patch('main.GroqProvider', side_effect=AssertionError('Groq called')), \
                patch('main.OpenAIProvider', FakeOpenAI), \
                patch('main.cloud_key', return_value='offline-placeholder') as key:
            self.assertEqual(run(args), 0)
        key.assert_called_once_with('openai')
        report = json.loads(args.output.read_text())
        self.assertEqual(local.calls, [])
        self.assertEqual(embedding.calls, 3)
        self.assertEqual(len(FakeOpenAI.instances[-1].calls), 3)
        self.assertEqual(report['settings']['cloud_model'], OpenAIProvider.default_model)
        self.assertEqual(report['provider_names'], ['cloud'])
        self.assertIn('no fresh local/cloud pairing', report['cloud_comparison'])
        self.assertEqual(report['summary']['cloud']['heuristic_passes'], 3)
        self.assertTrue(verify(report)['passed'])
        self.assertNotIn('offline-placeholder', args.output.read_text())
        for location in ('root', 'row', 'preflight'):
            corrupt = deepcopy(report)
            target = (corrupt if location == 'root' else corrupt['results'][0] if location == 'row'
                      else corrupt['providers']['cloud'])
            target['cloud_api'] = 'groq'
            self.assertFalse(verify(corrupt)['passed'])
        for location in ('url', 'model', 'generation'):
            corrupt = deepcopy(report)
            if location == 'generation':
                corrupt['results'][0]['generation']['model'] = 'other-model'
            else:
                corrupt['providers']['cloud'][location] = 'other'
            self.assertFalse(verify(corrupt)['passed'])
        changed = dict(vars(args), cloud_provider='groq')
        with self.assertRaisesRegex(ValueError, 'provider differs'):
            retry_plan(args.output, [fixtures.CASE], changed, 'compare', 3, 'cloud')

    def test_keys_are_selected_by_provider_without_fallback(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'openai-placeholder',
                                      'GROQ_API_KEY': 'groq-placeholder'}, clear=True):
            self.assertEqual(cloud_key('openai'), 'openai-placeholder')
            self.assertEqual(cloud_key(), 'groq-placeholder')
        args = self.args()
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), \
                patch('main.LocalEmbeddings', return_value=fixtures.Embed()), \
                patch('main.cloud_key', return_value=None), \
                patch('main.OpenAIProvider') as provider:
            provider.normalize_model.side_effect = OpenAIProvider.normalize_model
            provider.default_model = OpenAIProvider.default_model
            self.assertEqual(run(args), 1)
            provider.assert_not_called()
        r = json.loads(args.output.read_text())
        self.assertEqual(r['results'][0]['status'], 'error')
        self.assertIn('OPENAI_API_KEY', r['providers']['cloud']['error'])

    def test_openai_uses_strict_schemas_and_selected_ids_in_both_stages(self):
        synthesis = prepare_synthesis(self.prepared, fixtures.Model().raw)
        for messages, key in ((self.prepared['messages'], 'claims'), (synthesis['messages'], 'quote_ids')):
            with patch('rag28.ReliableHTTP.request', return_value={}) as request:
                StructuredHTTP(rate_retries=0).request('https://api.openai.com/v1/chat/completions',
                    {'model': OpenAIProvider.default_model, 'messages': messages})
            body = request.call_args.args[1]
            self.assertEqual(body['messages'], messages)
            self.assertEqual(body['response_format']['type'], 'json_schema')
            self.assertTrue(body['response_format']['json_schema']['strict'])
            schema = body['response_format']['json_schema']['schema']
            self.assertIn(key, schema['properties'])
            slot = schema['properties'][key]['properties']['c1' if key == 'claims' else 'q1']
            enum = slot['properties']['quote_id']['enum'] if key == 'claims' else slot['enum']
            self.assertIn('e1-q1', enum)
            if key == 'quote_ids':
                self.assertEqual(enum, [None, 'e1-q1'])

    def test_openai_adapter_snapshot_completion_usage_and_safe_request(self):
        class FakeHTTP:
            def __init__(self): self.calls = []
            def request(self, url, body=None, headers=None):
                self.calls.append((url, body, headers))
                if body is None:
                    return {'data': [{'id': OpenAIProvider.default_model}]}
                return {'model': OpenAIProvider.default_model, 'choices': [{'message': {
                    'content': fixtures.Model().raw}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 123, 'completion_tokens': 45}}
        http = FakeHTTP()
        provider = OpenAIProvider('offline-placeholder', 'gpt-4.1-mini', http=http, max_tokens=1000)
        self.assertTrue(provider.doctor()['available'])
        generation = provider.generate(self.prepared['messages'])
        self.assertTrue(generation.complete)
        self.assertEqual((generation.input_tokens, generation.output_tokens), (123, 45))
        url, body, headers = http.calls[-1]
        self.assertEqual(url, 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(body['max_completion_tokens'], 1000)
        self.assertFalse(body['store'])
        self.assertNotIn('reasoning_effort', body)
        self.assertEqual(headers['Authorization'], 'Bearer offline-placeholder')
        with self.assertRaises(ProviderError):
            OpenAIProvider('offline-placeholder', 'unsupported')

    def test_openai_bad_outputs_and_refusals_cannot_pass_as_valid_rag(self):
        baseline = {'model': OpenAIProvider.default_model, 'choices': [{'message': {
            'content': fixtures.Model().raw}, 'finish_reason': 'stop'}], 'usage': {}}
        for kind in ('wrong_model', 'empty', 'refusal', 'usage', 'shape', 'incomplete'):
            response = deepcopy(baseline)
            if kind == 'wrong_model': response['model'] = 'gpt-4o-mini-2024-07-18'
            if kind == 'empty': response['choices'][0]['message']['content'] = ''
            if kind == 'refusal':
                response['choices'][0]['message'].update(content=None, refusal='Provider refusal')
            if kind == 'usage': response['usage'] = []
            if kind == 'shape': response['choices'] = []
            if kind == 'incomplete': response['choices'][0]['finish_reason'] = 'length'
            with self.subTest(kind=kind), patch('cloud28.HTTP.request', return_value=response):
                provider = OpenAIProvider('offline-placeholder')
                if kind == 'incomplete':
                    self.assertFalse(provider.generate(self.prepared['messages']).complete)
                else:
                    with self.assertRaises(ProviderError): provider.generate(self.prepared['messages'])
        with patch('cloud28.HTTP.request', side_effect=ProviderError('HTTP 401. Check GROQ_API_KEY.')):
            with self.assertRaisesRegex(ProviderError, 'OPENAI_API_KEY'):
                OpenAIProvider('offline-placeholder').doctor()

    def test_small_openai_questions_preserve_original_rubrics_and_retry_backend_identity(self):
        original = json.loads((Path(__file__).parent / 'questions.json').read_text())
        small = json.loads((Path(__file__).parent / 'questions-openai-small.json').read_text())
        self.assertEqual([c['id'] for c in small], ['base-03', 'base-10', 'rewrite-ru-02'])
        self.assertEqual(len(small), 3)
        for case in small: self.assertIn(case, original)


if __name__ == '__main__':
    unittest.main()
