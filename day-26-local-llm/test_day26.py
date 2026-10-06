"""Offline integration checks. The HTTP server is a fixture, never a real LLM."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest
from unittest.mock import patch

from examples import load_examples, validate, calculate_energy
from main import main
from providers import HTTP, GroqProvider, OllamaProvider, ProviderError
from runner import markdown

ANSWERS = ["4", '{"cycles":6,"total_cost":3600,"remaining":0}', json.dumps({
    "worker": "worker.py", "database": "schedule.db", "metrics": ["stars", "forks", "open_issues"],
    "delivery": ["stdout", "systemd journal"],
    "quote": "The worker outputs summaries to stdout or the systemd journal; it does not push messages to a chat."})]


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.respond(None)

            def do_POST(self):
                self.respond(json.loads(self.rfile.read(int(self.headers['Content-Length']))))

            def respond(self, body):
                state = self.server.state
                state['calls'].append((self.path, body, self.headers.get('Authorization')))
                state.setdefault('headers', []).append(dict(self.headers))
                status = state.get('status', 200)
                if status != 200:
                    self.send_response(status)
                    self.send_header('Location', '/elsewhere')
                    self.send_header('Content-Type', state.get('error_content_type', 'text/plain'))
                    self.end_headers()
                    self.wfile.write(state.get('error_body', b'private-key-should-never-appear'))
                    return
                if self.path == '/api/version':
                    result = {'version': 'fixture-only'}
                elif self.path == '/api/tags':
                    result = {'models': [{'name': state.get('installed', 'qwen2.5:7b'), 'digest': 'fixture'}]}
                elif self.path == '/api/show':
                    result = state.get('show', {'details': {'family': 'qwen2'}})
                elif self.path == '/api/ps':
                    result = {'models': [{'name': 'qwen2.5:7b', 'size': 123}] if state.get('loaded', True) else []}
                elif self.path == '/models':
                    result = {'data': [{'id': 'openai/gpt-oss-20b'}]}
                else:
                    index = state['index'].setdefault(self.path, 0)
                    state['index'][self.path] = index + 1
                    answer = state.get('answer', ANSWERS[index % 3])
                    if self.path == '/api/chat':
                        result = {'model': state.get('returned_model', body['model']), 'message': {'content': answer},
                                  'done': state.get('done', True), 'done_reason': state.get('reason', 'stop'),
                                  'prompt_eval_count': 50, 'eval_count': 20, 'load_duration': 100000000,
                                  'eval_duration': 2000000000}
                    else:
                        result = {'model': state.get('returned_model', body['model']), 'choices': [{'message': {'content': answer},
                                  'finish_reason': state.get('reason', 'stop')}],
                                  'usage': {'prompt_tokens': 50, 'completion_tokens': 20}}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'invalid json' if state.get('bad_json') else json.dumps(result).encode())
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.state = {'calls': [], 'index': {}}
        self.key_patch = patch.dict(os.environ, {'GROQ_API_KEY': 'fixture-secret'})
        self.key_patch.start()
        self.url_patch = patch.object(GroqProvider, 'url', self.url)
        self.url_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.addCleanup(self.url_patch.stop)

    def cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def local(self):
        return OllamaProvider(url=self.url)

    def cloud(self):
        return GroqProvider('fixture-secret')

    def test_local_three_requests_and_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'run.json'
            code, _ = self.cli('demo', '--url', self.url, '--output', str(output))
            report = json.loads(output.read_text())
            self.assertEqual(code, 0)
            self.assertTrue(report['summary']['day26_local_three_requests_verified'])
            self.assertEqual(report['summary']['checks_passed'], 3)
            self.assertTrue(output.with_suffix('.md').is_file())
            self.assertNotIn('fixture-secret', output.read_text())

    def test_compare_identical_prompts_and_separate_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'run.json'
            code, _ = self.cli('compare', '--url', self.url, '--output', str(output))
            report = json.loads(output.read_text())
            self.assertEqual(code, 0)
            self.assertEqual(report['summary']['checks_passed'], 6)
            rows = report['results']
            for local, cloud in zip(rows[:3], rows[3:]):
                self.assertEqual(local['messages'], cloud['messages'])
                self.assertEqual(local['prompt_sha256'], cloud['prompt_sha256'])
                self.assertEqual(len(local['messages']), 2)
            requests = [x for x in self.server.state['calls'] if x[0] in ('/api/chat', '/chat/completions')]
            self.assertEqual(len(requests), 6)

    def test_cloud_only_does_not_call_ollama(self):
        self.assertEqual(self.cli('demo', '--provider', 'cloud')[0], 0)
        self.assertFalse(any(x[0].startswith('/api/') for x in self.server.state['calls']))

    def test_local_does_not_read_cloud_key(self):
        with patch('main.cloud_key', side_effect=AssertionError('cloud key requested')):
            self.assertEqual(self.cli('demo', '--url', self.url)[0], 0)

    def test_failed_local_preflight_keeps_cloud_results(self):
        self.server.state['installed'] = 'different:7b'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'run.json'
            code, _ = self.cli('compare', '--url', self.url, '--output', str(output))
            report = json.loads(output.read_text())
            self.assertEqual(code, 1)
            self.assertEqual(report['summary']['complete_answers'], 3)
            self.assertEqual([x['status'] for x in report['results'][:3]], ['error'] * 3)
            self.assertFalse(report['summary']['local_launch_verified'])

    def test_no_cloud_fallback_in_local_mode(self):
        self.server.state['status'] = 429
        code, out = self.cli('demo', '--url', self.url)
        self.assertEqual(code, 1)
        self.assertIn('Rate limit', out)
        self.assertFalse(any(x[0] == '/chat/completions' for x in self.server.state['calls']))

    def test_doctor_does_not_generate(self):
        self.assertEqual(self.cli('doctor', '--url', self.url)[0], 0)
        self.assertFalse(any(x[0] == '/api/chat' for x in self.server.state['calls']))

    def test_ask_completion_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'ask.json'
            self.assertEqual(self.cli('ask', 'Привет', '--url', self.url, '--output', str(output))[0], 0)
            report = json.loads(output.read_text())
            self.assertIn('manual review', report['results'][0]['check']['kind'])
            self.assertFalse(report['summary']['day26_local_three_requests_verified'])

    def test_examples_make_no_network_calls(self):
        self.assertEqual(self.cli('examples')[0], 0)
        self.assertEqual(self.server.state['calls'], [])

    def test_local_payload_and_metrics(self):
        result = self.local().generate([{'role': 'user', 'content': 'test'}])
        payload = self.server.state['calls'][-1][1]
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['options'], {'temperature': 0, 'num_predict': 2048, 'num_ctx': 8192})
        self.assertEqual(payload['keep_alive'], '5m')
        self.assertEqual(result.tokens_per_second, 10)
        self.assertEqual(result.load_seconds, .1)

    def test_cloud_payload_auth_and_usage(self):
        result = self.cloud().generate([{'role': 'user', 'content': 'test'}])
        _, body, auth = self.server.state['calls'][-1]
        self.assertEqual(auth, 'Bearer fixture-secret')
        self.assertEqual(body['max_completion_tokens'], 2048)
        self.assertEqual(body['reasoning_effort'], 'low')
        self.assertEqual(result.output_tokens, 20)
        self.assertIsNone(result.tokens_per_second)

    def test_local_length_is_not_success(self):
        self.server.state['reason'] = 'length'
        self.assertFalse(self.local().generate([]).complete)
        self.assertEqual(self.cli('demo', '--url', self.url)[0], 1)

    def test_cloud_length_is_not_success(self):
        self.server.state['reason'] = 'length'
        self.assertFalse(self.cloud().generate([]).complete)

    def test_local_unfinished_flag_is_not_success(self):
        self.server.state['done'] = False
        self.assertFalse(self.local().generate([]).complete)

    def test_empty_answers_fail(self):
        self.server.state['answer'] = ''
        for provider in (self.local(), self.cloud()):
            with self.subTest(provider=provider.name), self.assertRaises(ProviderError):
                provider.generate([])

    def test_wrong_local_response_model_rejected(self):
        self.server.state['returned_model'] = 'different:7b'
        for provider in (self.local(), self.cloud()):
            with self.subTest(provider=provider.name), self.assertRaisesRegex(ProviderError, 'different model'):
                provider.generate([])

    def test_running_model_missing_does_not_verify_local_launch(self):
        self.server.state['loaded'] = False
        code, out = self.cli('demo', '--url', self.url)
        self.assertEqual(code, 1)
        self.assertIn('"local_launch_verified": false', out)

    def test_remote_model_rejected_in_doctor(self):
        self.server.state['show'] = {'remote_host': 'https://ollama.com'}
        with self.assertRaisesRegex(ProviderError, 'remote host'):
            self.local().doctor()

    def test_cloud_model_missing_key(self):
        with self.assertRaisesRegex(ProviderError, 'GROQ_API_KEY'):
            GroqProvider('')

    def test_http_errors_redact_body_and_key(self):
        for status in (401, 429, 500):
            self.server.state['status'] = status
            with self.subTest(status=status), self.assertRaises(ProviderError) as caught:
                self.cloud().generate([])
            self.assertNotIn('private-key', str(caught.exception))
            self.assertNotIn('fixture-secret', str(caught.exception))
            self.assertIn(str(status), str(caught.exception))

    def test_invalid_http_json(self):
        self.server.state['bad_json'] = True
        with self.assertRaisesRegex(ProviderError, 'invalid JSON'):
            self.local().doctor()

    def test_http_redirect_not_followed(self):
        self.server.state['status'] = 302
        with self.assertRaisesRegex(ProviderError, '302'):
            self.cloud().doctor()
        self.assertEqual(len(self.server.state['calls']), 1)

    def test_explicit_application_headers(self):
        self.cloud().doctor()
        headers = self.server.state['headers'][-1]
        self.assertEqual(headers['User-Agent'], 'Bublik-Day26/1.1')
        self.assertEqual(headers['Accept'], 'application/json')

    def test_upstream_1010_code_diagnostic_without_raw_body(self):
        self.server.state.update(status=403, error_body=b'error code: 1010 private-secret')
        with self.assertRaises(ProviderError) as caught:
            self.cloud().doctor()
        message = str(caught.exception)
        self.assertIn('GET /models', message)
        self.assertIn('upstream_code=1010', message)
        self.assertNotIn('private-secret', message)

    def test_json_error_type_diagnostic_without_message(self):
        self.server.state.update(status=403, error_body=json.dumps({'error': {
            'type': 'permission_error', 'message': 'fixture-secret'}}).encode())
        with self.assertRaises(ProviderError) as caught:
            self.cloud().doctor()
        message = str(caught.exception)
        self.assertIn('response_format=json', message)
        self.assertIn('error_type=permission_error', message)
        self.assertNotIn('fixture-secret', message)

    def test_html_error_diagnostic_without_raw_body(self):
        self.server.state.update(status=403, error_content_type='text/html',
                                 error_body=b'<html>fixture-secret</html>')
        with self.assertRaises(ProviderError) as caught:
            self.cloud().doctor()
        message = str(caught.exception)
        self.assertIn('response_format=html', message)
        self.assertNotIn('fixture-secret', message)

    def test_http_timeout(self):
        http = HTTP()
        with patch.object(http.opener, 'open', side_effect=TimeoutError), self.assertRaisesRegex(ProviderError, 'timed out'):
            http.request(self.url)

    def test_wrong_answer_fails_quality_but_inference_is_verified(self):
        self.server.state['answer'] = 'incorrect'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'run.json'
            code, _ = self.cli('demo', '--url', self.url, '--output', str(output))
            report = json.loads(output.read_text())
            self.assertEqual(code, 1)
            self.assertTrue(report['summary']['day26_local_three_requests_verified'])
            self.assertFalse(report['summary']['all_checks_passed'])


class Validation(unittest.TestCase):
    def test_energy_tool_boundary_and_remainder_cases(self):
        for inputs, expected in [((3600, 1200, 400), (6, 3600, 0)),
                                 ((3650, 1200, 400), (6, 3600, 50)),
                                 ((1200, 1200, 400), (0, 1200, 0)),
                                 ((399, 0, 400), (0, 0, 399))]:
            with self.subTest(inputs=inputs):
                result = calculate_energy(*inputs)
                self.assertEqual((result['cycles'], result['total_cost'], result['remaining']), expected)

    def test_energy_tool_invalid_inputs(self):
        for inputs in [(100, 1200, 400), (3600, 1200, 0), (3600, -1, 400),
                       (3600.0, 1200, 400), (True, 0, 400)]:
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                calculate_energy(*inputs)

    def test_expected_answers(self):
        for case, answer in zip(load_examples(), ANSWERS):
            self.assertTrue(validate(case['id'], answer)['passed'])

    def test_wrong_math_types_and_values(self):
        for text in ['{"cycles":6.0,"total_cost":3600,"remaining":0}',
                     '{"cycles":true,"total_cost":3600,"remaining":0}',
                     '{"cycles":5,"total_cost":3600,"remaining":0}']:
            self.assertFalse(validate('calculation', text)['passed'])

    def test_duplicate_nonfinite_fenced_json_rejected(self):
        for text in ['{"cycles":6,"cycles":6,"total_cost":3600,"remaining":0}',
                     '{"cycles":NaN,"total_cost":3600,"remaining":0}',
                     '```json\n' + ANSWERS[1] + '\n```', '[]']:
            self.assertFalse(validate('calculation', text)['passed'])

    def test_quote_substitution_and_invented_metric_rejected(self):
        for key, value in [('quote', 'worker sends messages to chat'), ('metrics', ['stars', 'forks', 'views'])]:
            data = json.loads(ANSWERS[2])
            data[key] = value
            self.assertFalse(validate('grounded_json', json.dumps(data))['passed'])

    def test_metrics_order_is_irrelevant(self):
        data = json.loads(ANSWERS[2])
        data['metrics'].reverse()
        self.assertTrue(validate('grounded_json', json.dumps(data))['passed'])

    def test_loopback_only_and_cloud_tag_rejected(self):
        for url in ('https://ollama.com', 'http://example.com', 'http://user:secret@localhost', 'http://localhost/path'):
            with self.subTest(url=url), self.assertRaises(ProviderError):
                OllamaProvider(url=url)
        with self.assertRaises(ProviderError):
            OllamaProvider('gpt-oss:20b-cloud')

    def test_context_fixture_matches_repository_snapshot(self):
        root = Path(__file__).resolve().parent.parent
        source_path = root / 'day-18-scheduled-mcp/README.md'
        if not source_path.exists():
            self.skipTest('Standalone delivery: sibling Day 18 is not installed')
        fixture = json.loads((Path(__file__).parent / 'fixtures/day18-context.json').read_text())
        source = fixture['source']
        lines = source_path.read_text().splitlines()
        self.assertEqual(fixture['text'], '\n'.join(lines[source['start_line']-1:source['end_line']]))

    def test_invalid_cli_numbers(self):
        for flag, value in [('--timeout', 'nan'), ('--max-tokens', '0'), ('--num-ctx', '-1'), ('--temperature', 'inf')]:
            with redirect_stdout(io.StringIO()), patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
                main(['demo', flag, value])


if __name__ == '__main__':
    unittest.main()
