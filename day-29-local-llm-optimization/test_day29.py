"""Offline integration tests: scripted local transport is NOT a live benchmark."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import cli29
from bridge29 import Settings, prepare, ProviderError
from engine29 import (load_profiles, prompt_for, identity_for, reusable, validate_envelope,
                      context_guard, observe, summarize)
from provider29 import MeasuredOllama
from resources29 import ResourceSampler
from store29 import Cache, digest, owned_cache
from storage import Hit

TEXT = 'The independent worker runs scheduled jobs.'
CASE = {'id': 'worker', 'question': 'Which process runs jobs?', 'answerable': True,
        'expected_terms': ['worker'], 'expected_sources': ['worker.py'], 'split': 'calibration'}
PROFILE = {'model': 'qwen2.5:14b', 'temperature': 0, 'max_tokens': 1024, 'num_ctx': 8192, 'prompt': 'baseline'}


class FakeHTTP:
    def __init__(self):
        self.calls = []
        self.answer_calls = 0
        self.probe_calls = 0
        self.warmups = 0
        self.fail_at = None
        self.interrupt_at = None
        self.bad_quality = False
        self.loaded = []
        self.input_count = 100
        self.digest_suffix = 'a'
        self.version = 'offline-only'

    def request(self, url, body=None, headers=None):
        assert url.startswith('http://127.0.0.1:11434/'), 'Unexpected external endpoint'
        self.calls.append((url, deepcopy(body)))
        model = body.get('model') if body else None
        if url.endswith('/api/version'):
            return {'version': self.version}
        if url.endswith('/api/tags'):
            return {'models': [{'name': m, 'digest': self.digest_suffix * 64} for m in
                               ('qwen2.5:14b', 'qwen2.5:14b-instruct-q5_K_M', 'bge-m3')]}
        if url.endswith('/api/show'):
            return {'details': {'family': 'qwen2', 'quantization_level': 'Q4_K_M'},
                    'model_info': {'qwen2.context_length': 131072}, 'template': 'offline-template'}
        if url.endswith('/api/ps'):
            return {'models': self.loaded}
        if url.endswith('/api/generate'):
            if body.get('keep_alive') == 0:
                self.loaded = [x for x in self.loaded if x['name'] != model]
            else:
                self.warmups += 1
            return {'model': model, 'done': True, 'done_reason': 'stop', 'load_duration': 1}
        if url.endswith('/api/chat'):
            if body['options']['num_predict'] == 1:
                self.probe_calls += 1
                return {'model': model, 'message': {'content': '{'}, 'done': True,
                        'done_reason': 'length', 'prompt_eval_count': self.input_count, 'eval_count': 1}
            self.answer_calls += 1
            if self.interrupt_at == self.answer_calls:
                raise KeyboardInterrupt()
            if self.fail_at == self.answer_calls:
                raise ProviderError('Scripted transport failure.')
            self.loaded = [{'name': model, 'model': model, 'digest': self.digest_suffix * 64,
                            'size': 1000, 'size_vram': 900, 'context_length': body['options']['num_ctx']}]
            statement = 'A scheduler runs jobs.' if self.bad_quality else 'The worker runs jobs.'
            answer = json.dumps({'claims': {'c1': {'quote_id': 'e1-q1', 'statement': statement},
                                          'c2': None, 'c3': None, 'c4': None}, 'abstained': False})
            return {'model': model, 'message': {'content': answer}, 'done': True, 'done_reason': 'stop',
                    'prompt_eval_count': self.input_count, 'prompt_eval_cached_count': 0,
                    'eval_count': 30, 'eval_duration': 300000000, 'prompt_eval_duration': 200000000,
                    'total_duration': 501000000, 'load_duration': 1000000}
        raise AssertionError(url)


class FakeIndex:
    def __init__(self, path):
        pass
    def verify(self):
        return {'read_only': True, 'revision': 'offline'}
    def info(self, strategy):
        return {'model': 'bge-m3', 'dimension': 2}
    def search(self, strategy, vector, k):
        return [Hit('one', 'worker.py', 'Worker', TEXT, .9, 1, 1)]
    def close(self):
        pass


class FakeEmbedding:
    model = 'bge-m3'
    calls = 0
    def __init__(self, *args, **kwargs):
        self.http = FakeHTTP()
        self.url = 'http://127.0.0.1:11434'
    def doctor(self):
        return {'digest': 'b' * 64, 'server_version': 'offline-only'}
    def embed(self, texts):
        FakeEmbedding.calls += 1
        return [[1., 0.] for _ in texts]


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.questions = self.root / 'questions.json'
        self.questions.write_text(json.dumps([CASE]))
        self.profiles = self.root / 'profiles.json'
        self.profiles.write_text(json.dumps({'baseline': PROFILE, 'compact': {**PROFILE, 'prompt': 'compact'}}))
        self.index = self.root / 'index.db'
        self.index.write_bytes(b'offline index identity')
        self.cache_path = self.root / 'cache.sqlite3'
        self.output = self.root / 'run.json'
        self.http = FakeHTTP()
        FakeEmbedding.calls = 0
        self.prepared = prepare(FakeIndex(None), FakeEmbedding(), CASE['question'], Settings(20, 5, .5, 'fixed', 'heuristic'))
        FakeEmbedding.calls = 0

    def args(self, command='run', *extra):
        return [command, '--profiles-file', str(self.profiles), '--questions', str(self.questions),
                '--profiles', 'baseline', '--cache', str(self.cache_path), '--db', str(self.index),
                '--output', str(self.output), *extra]

    def execute(self, arguments):
        fake = self.http
        def provider(profile, url, timeout, seed=42, sample_interval=.5):
            return MeasuredOllama(profile, url, timeout, seed, http=fake, sample_interval=sample_interval)
        with ExitStack() as stack:
            stack.enter_context(patch.object(cli29, 'ExistingIndex', FakeIndex))
            stack.enter_context(patch.object(cli29, 'LocalEmbeddings', FakeEmbedding))
            stack.enter_context(patch.object(cli29, 'MeasuredOllama', side_effect=provider))
            stack.enter_context(patch.object(cli29, 'psutil', SimpleNamespace(__version__='offline-test')))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(redirect_stderr(io.StringIO()))
            return cli29.main(arguments)

    def test_three_answers_are_reused_without_probe_or_warmup(self):
        self.assertEqual(self.execute(self.args()), 0)
        self.assertEqual((self.http.answer_calls, self.http.probe_calls, FakeEmbedding.calls), (3, 1, 1))
        warmups = self.http.warmups
        original = json.loads(self.output.read_text())
        self.assertEqual(self.execute(self.args()), 0)
        self.assertEqual((self.http.answer_calls, self.http.probe_calls, self.http.warmups), (3, 1, warmups))
        again = cli29.read_report(self.output)
        self.assertEqual(again['summary']['baseline']['reused_observations'], 3)
        self.assertEqual(again['new_answer_generation_calls'], 0)
        self.assertEqual(again['maintenance_generation_calls'], 0)
        self.assertEqual(again['observations'][0]['result']['created_at'], original['observations'][0]['result']['created_at'])
        self.assertFalse(again['optimization_verified'])

    def test_partial_batch_only_completes_missing_slots(self):
        self.assertEqual(self.execute(self.args('run', '--max-new-observations', '2')), 0)
        self.assertEqual(self.http.answer_calls, 2)
        self.assertEqual(cli29.read_report(self.output)['state'], 'paused')
        self.assertEqual(self.execute(self.args()), 0)
        self.assertEqual(self.http.answer_calls, 3)
        report = cli29.read_report(self.output)
        self.assertEqual(report['summary']['baseline']['reused_observations'], 2)
        self.assertEqual(report['new_answer_generation_calls'], 1)

    def test_interrupt_preserves_completed_turn_and_releases_lock(self):
        self.http.interrupt_at = 2
        self.assertEqual(self.execute(self.args()), 130)
        self.assertEqual(cli29.read_report(self.output)['state'], 'interrupted')
        self.http.interrupt_at = None
        self.assertEqual(self.execute(self.args()), 0)
        self.assertEqual(self.http.answer_calls, 4)  # one interrupted call plus three answers
        self.assertEqual(cli29.read_report(self.output)['summary']['baseline']['reused_observations'], 1)

    def test_transport_failure_is_retained_and_only_failed_missing_slots_retry(self):
        self.http.fail_at = 2
        self.assertEqual(self.execute(self.args()), 1)
        old = cli29.read_report(self.output)
        self.assertEqual(old['state'], 'blocked')
        self.http.fail_at = None
        self.assertEqual(self.execute(self.args()), 0)
        self.assertEqual(self.http.answer_calls, 4)
        report = cli29.read_report(self.output)
        previous = [h for h in report['attempt_history'] if h['trial'] == 2][0]['prior_attempts']
        self.assertEqual(len(previous), 1)
        self.assertEqual(previous[0]['result']['status'], 'error')

    def test_valid_quality_failure_is_not_regenerated_forever(self):
        self.http.bad_quality = True
        self.assertEqual(self.execute(self.args()), 1)
        self.assertEqual(self.execute(self.args()), 1)
        self.assertEqual(self.http.answer_calls, 3)
        report = cli29.read_report(self.output)
        self.assertEqual(report['summary']['baseline']['quality_passes'], 0)
        self.assertEqual(report['summary']['baseline']['quality_denominator'], 3)

    def test_changed_parameters_require_new_answers_but_reuse_token_probe(self):
        self.execute(self.args())
        changed = deepcopy(PROFILE)
        changed['temperature'] = .1
        self.profiles.write_text(json.dumps({'baseline': changed}))
        self.assertEqual(self.execute(self.args()), 0)
        self.assertEqual(self.http.answer_calls, 6)
        self.assertEqual(self.http.probe_calls, 1)

    def test_changed_prompt_requires_new_answers_and_new_probe(self):
        self.execute(self.args())
        self.assertEqual(self.execute(self.args('run', '--profiles', 'compact')), 0)
        self.assertEqual((self.http.answer_calls, self.http.probe_calls), (6, 2))
        prompts = [body['messages'] for url, body in self.http.calls if url.endswith('/api/chat') and body['options']['num_predict'] != 1]
        self.assertEqual(json.loads(prompts[0][1]['content'])['excerpts'], json.loads(prompts[-1][1]['content'])['excerpts'])

    def test_changed_index_or_model_digest_invalidates_completed_observations(self):
        self.execute(self.args())
        self.index.write_bytes(b'changed index')
        self.execute(self.args())
        self.assertEqual(self.http.answer_calls, 6)
        self.http.digest_suffix = 'd'
        self.execute(self.args())
        self.assertEqual(self.http.answer_calls, 9)

    def test_changed_rubric_reuses_retrieval_but_requires_new_experiment(self):
        self.execute(self.args())
        case = {**CASE, 'expected_terms': ['scheduled']}
        self.questions.write_text(json.dumps([case]))
        self.assertEqual(self.execute(self.args()), 1)
        self.assertEqual(FakeEmbedding.calls, 1)
        self.assertEqual(self.http.answer_calls, 6)

    def test_series_is_explicit_fresh_benchmark_switch(self):
        self.execute(self.args())
        self.execute(self.args('run', '--series', 'fresh'))
        self.assertEqual(self.http.answer_calls, 6)

    def test_profile_seed_schedule_is_reproducible(self):
        self.execute(self.args())
        seeds = [body['options']['seed'] for url, body in self.http.calls if url.endswith('/api/chat') and body['options']['num_predict'] != 1]
        self.assertEqual(seeds, [42, 43, 44])

    def test_report_import_reuses_exact_three_answers_in_new_cache(self):
        self.execute(self.args())
        original = self.root / 'original.json'
        original.write_bytes(self.output.read_bytes())
        self.assertEqual(self.execute(self.args('run', '--cache', str(self.root / 'new.sqlite3'), '--retry-from', str(original))), 0)
        self.assertEqual(self.http.answer_calls, 3)
        self.assertEqual(cli29.read_report(self.output)['summary']['baseline']['reused_observations'], 3)

    def test_plan_is_zero_http_and_shows_cache_estimate(self):
        self.execute(self.args())
        count = len(self.http.calls)
        self.assertEqual(self.execute(self.args('plan')), 0)
        self.assertEqual(len(self.http.calls), count)
        plan = json.loads(self.output.read_text())
        self.assertEqual(plan['reuse_estimate'], 3)
        self.assertEqual(plan['new_observations_estimate'], 0)
        self.assertTrue(plan['live_verification_pending'])

    def test_old_day28_reports_are_not_imported_as_new_baseline(self):
        old = self.root / 'old.json'
        old.write_text(json.dumps({'schema_version': 12, 'mode': 'live'}))
        with self.assertRaisesRegex(ValueError, 'Day 28'):
            cli29.read_report(old)

    def test_modified_raw_answer_or_evidence_is_rejected(self):
        self.execute(self.args())
        report = cli29.read_report(self.output)
        bad = deepcopy(report['observations'][0])
        bad['result']['response']['answer'] = 'Changed answer'
        with self.assertRaises(ValueError):
            validate_envelope(bad)
        bad = deepcopy(report['observations'][0])
        bad['prepared']['excerpts'][0]['text'] = 'Changed evidence'
        with self.assertRaises(ValueError):
            validate_envelope(bad)
        report['summary']['baseline']['valid'] = 999
        self.output.write_text(json.dumps(cli29.seal(report)))
        with self.assertRaisesRegex(ValueError, 'summary'):
            cli29.read_report(self.output)

    def test_report_checksum_detects_unsealed_edits(self):
        self.execute(self.args())
        report = json.loads(self.output.read_text())
        report['series'] = 'edited'
        self.output.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            cli29.read_report(self.output)

    def test_context_overflow_does_not_generate_answer(self):
        self.http.input_count = 200
        self.profiles.write_text(json.dumps({'baseline': {**PROFILE, 'num_ctx': 1300}}))
        self.assertEqual(self.execute(self.args()), 1)
        report = cli29.read_report(self.output)
        self.assertEqual(self.http.answer_calls, 0)
        self.assertEqual([e['result']['status'] for e in report['observations']], ['context_overflow'] * 3)
        self.assertEqual(self.http.warmups, 0)

    def test_actual_input_count_mismatch_is_rejected(self):
        provider = MeasuredOllama(PROFILE, 'http://127.0.0.1:11434', 10, http=self.http)
        guard = {'passed': True, 'input_tokens': 99}
        row = observe(provider, self.prepared, CASE, guard)
        self.assertEqual(row['status'], 'context_mismatch')

    def test_application_refusal_is_not_generation_speed_evidence(self):
        case = {**CASE, 'answerable': False, 'expected_terms': [], 'expected_sources': []}
        prepared = deepcopy(self.prepared)
        prepared['excerpts'] = []
        provider = MeasuredOllama(PROFILE, 'http://127.0.0.1:11434', 10, http=self.http)
        row = observe(provider, prepared, case, {'passed': True})
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(self.http.answer_calls, 0)
        report = {'profiles': {'baseline': PROFILE}, 'cases': [case], 'repeats': 1,
                  'observations': [{'identity': {'profile_name': 'baseline', 'case': case}, 'result': row}], 'maintenance': []}
        summarize(report)
        self.assertIsNone(report['summary']['baseline']['generation_median_seconds'])
        self.assertEqual(report['summary']['baseline']['application_abstentions'], 1)

    def test_remote_url_and_cloud_model_are_rejected(self):
        with self.assertRaises(ProviderError):
            MeasuredOllama(PROFILE, 'https://example.com', 10)
        with self.assertRaises(ProviderError):
            MeasuredOllama({**PROFILE, 'model': 'qwen:cloud'}, 'http://127.0.0.1:11434', 10)

    def test_no_rubric_or_expected_answer_enters_prompt(self):
        compact = prompt_for(self.prepared, {**PROFILE, 'prompt': 'compact'})
        text = json.dumps(compact['messages'])
        self.assertNotIn('expected_terms', text)
        self.assertNotIn('expected_sources', text)
        self.assertNotIn('calibration', text)

    def test_invalid_profile_values_are_rejected(self):
        for replacement in ({'temperature': float('nan')}, {'max_tokens': True}, {'num_ctx': 1000}, {'prompt': 'phases'}):
            self.profiles.write_text(json.dumps({'bad': {**PROFILE, **replacement}}))
            with self.assertRaises(ValueError):
                load_profiles(self.profiles)

    def test_cache_checksum_and_competing_writer_are_rejected(self):
        cache = Cache(self.cache_path)
        cache.put('test', {'ok': True})
        with cache.db:
            cache.db.execute("UPDATE metadata SET body='{}' WHERE key='test'")
        with self.assertRaises(ValueError):
            cache.get('test')
        cache.close()
        with owned_cache(self.cache_path):
            with self.assertRaisesRegex(ValueError, 'Another'):
                with owned_cache(self.cache_path):
                    pass

    def test_resource_sampler_reports_missing_metrics_without_fake_zero(self):
        with patch('resources29.psutil', None):
            with ResourceSampler() as sampler:
                pass
            result = sampler.result()
        self.assertFalse(result['available'])
        self.assertIsNone(result['ollama_peak_summed_rss_bytes'])
        self.assertIsNone(result['gpu_utilization_percent'])

    def test_resource_sampler_reports_observed_process_delta_and_shared_rss_separately(self):
        sampler = ResourceSampler()
        sampler.samples = [
            {'elapsed_seconds': 0., 'system_available_bytes': 500, 'swap_used_bytes': 7,
             'python_rss_bytes': 30, 'ollama_processes': [{'pid': 1, 'name': 'ollama', 'rss_bytes': 100, 'cpu_seconds': 2.}]},
            {'elapsed_seconds': 2., 'system_available_bytes': 400, 'swap_used_bytes': 9,
             'python_rss_bytes': 31, 'ollama_processes': [{'pid': 1, 'name': 'ollama', 'rss_bytes': 120, 'cpu_seconds': 3.}]}]
        result = sampler.result()
        self.assertEqual(result['ollama_peak_summed_rss_bytes'], 120)
        self.assertEqual(result['ollama_observed_cpu_seconds'], 1)
        self.assertEqual(result['ollama_average_cpu_percent'], 50)
        self.assertEqual((result['swap_before_bytes'], result['swap_after_bytes']), (7, 9))
        self.assertIsNone(result['gpu_utilization_percent'])

    def test_loaded_model_digest_mismatch_is_not_reusable(self):
        self.execute(self.args())
        envelope = deepcopy(cli29.read_report(self.output)['observations'][0])
        envelope['result']['running_models_after'][0]['digest'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'digest'):
            validate_envelope(envelope)

    def test_input_probe_cannot_exceed_model_limit_or_conservative_bound(self):
        provider = MeasuredOllama(PROFILE, 'http://127.0.0.1:11434', 10, http=self.http)
        cache = Cache(self.cache_path)
        self.addCleanup(cache.close)
        meta = cli29.model_metadata(provider)
        maintenance = []
        with self.assertRaisesRegex(ValueError, 'exceeds the context'):
            context_guard(cache, provider, self.prepared, meta, 262144, maintenance)
        with self.assertRaisesRegex(ValueError, 'conservative'):
            context_guard(cache, provider, self.prepared, meta, 1024, maintenance)
        self.assertEqual(self.http.probe_calls, 0)

    def test_profile_order_alternates_and_three_trials_match_by_seed(self):
        self.execute(self.args('run', '--profiles', 'baseline', 'compact'))
        rows = cli29.read_report(self.output)['observations']
        self.assertEqual([e['identity']['profile_name'] for e in rows],
                         ['baseline', 'compact', 'compact', 'baseline', 'baseline', 'compact'])
        self.assertEqual([e['result']['seed'] for e in rows], [42, 42, 43, 43, 44, 44])
        self.assertEqual(FakeEmbedding.calls, 1)


if __name__ == '__main__':
    unittest.main()
