"""Offline contract/integration tests. Fake vectors/models are not live evidence."""
from dataclasses import replace
import hashlib
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from bridge28 import KnowledgeBase, Settings, ProviderError, OllamaProvider, GroqProvider
from corpus import Document, load_documents, revision, ROOT
from chunking import Chunk, chunk_documents
from providers import Generation
from rag28 import ExistingIndex, LocalEmbeddings, ReliableHTTP, StructuredHTTP, prepare, prepare_synthesis, parse_answer, observe, summarize, percentile
from quotes28 import catalog_for, model_excerpts
from verify_report import verify
from main import load_cases, run, parser, atomic_text

CASE = {'id': 'worker', 'question': 'Which process runs jobs?', 'answerable': True,
        'expected_terms': ['worker'], 'expected_sources': ['worker.py']}
TEXT = 'The independent worker runs scheduled jobs.'


class Embed:
    model = 'bge-m3'
    calls = 0
    def embed(self, texts):
        self.calls += 1
        return [[1., 0.] for _ in texts]
    def doctor(self):
        return {'model': self.model, 'installed': True}


class Model:
    name = 'local'
    model = 'qwen2.5:14b'
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.raw = json.dumps({'claims': {
            'c1': {'quote_id': 'e1-q1', 'statement': 'The worker runs jobs.'},
            'c2': None, 'c3': None, 'c4': None}, 'abstained': False})
        self.complete = True
    def doctor(self):
        return {'installed': True, 'digest': 'offline-test-only'}
    def running(self):
        return [{'name': self.model}]
    def generate(self, messages):
        self.calls.append(messages)
        return Generation(self.name, self.model, self.raw, .2, 100, 30, 'stop', self.complete)


class SynthesisModel(Model):
    def generate(self, messages):
        generated = super().generate(messages)
        if json.loads(messages[1]['content']).get('contract') == 'quote_slots_v4':
            raw = json.dumps({'answer': 'The worker runs scheduled jobs.', 'abstained': False,
                              'quote_ids': {'q1': 'e1-q1', 'q2': None, 'q3': None, 'q4': None}})
            generated = replace(generated, answer=raw)
        return generated


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'knowledge.db'
        self.kb = KnowledgeBase(self.path)
        self.addCleanup(self.kb.close)
        doc = Document('worker.py', 'Worker', TEXT, hashlib.sha256(TEXT.encode()).hexdigest())
        for strategy in ('fixed', 'structural'):
            chunks = [Chunk(strategy + '-one', doc.source, doc.title, 'worker', strategy, TEXT, 1, 1, 7)]
            self.kb.save([doc], strategy, chunks, [[1., 0.]], 'bge-m3', 500, 75, 'commit@fingerprint')
        self.settings = Settings(20, 5, .5, 'fixed', 'heuristic')
        self.embedding = Embed()
        self.prepared = prepare(self.kb, self.embedding, CASE['question'], self.settings)

    def test_shared_index_read_only_and_missing(self):
        with self.assertRaises(ValueError):
            ExistingIndex(self.path.with_name('missing.db'))
        kb = ExistingIndex(self.path)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                kb.db.execute('DELETE FROM chunks')
            self.assertEqual(kb.search('fixed', [1., 0.], 5)[0].text, TEXT)
        finally:
            kb.close()

    def test_fingerprint_allows_code_only_commit_but_rejects_corpus_change(self):
        kb = ExistingIndex(self.path)
        try:
            doc = Document('worker.py', 'Worker', TEXT, hashlib.sha256(TEXT.encode()).hexdigest())
            with patch('rag28.load_documents', return_value=[doc]), patch('rag28.revision', return_value='newcommit@fingerprint'):
                self.assertTrue(kb.verify()['read_only'])
            with patch('rag28.load_documents', return_value=[replace(doc, digest='changed')]), patch('rag28.revision', return_value='newcommit@fingerprint'):
                with self.assertRaises(ValueError):
                    kb.verify()
        finally:
            kb.close()

    def test_tampered_document_and_chunk_rejected(self):
        kb = ExistingIndex(self.path)
        try:
            with self.kb.db:
                self.kb.db.execute("UPDATE chunks SET text='injected'")
            with self.assertRaisesRegex(ValueError, 'chunk text'):
                kb.verify()
            with self.kb.db:
                self.kb.db.execute("UPDATE documents SET text='injected'")
            with self.assertRaisesRegex(ValueError, 'document text'):
                kb.verify()
        finally:
            kb.close()

    def test_same_prompt_and_context_for_local_cloud(self):
        a, b = Model(), Model()
        b.name = 'cloud'
        x, y = observe(a, self.prepared, CASE), observe(b, self.prepared, CASE)
        self.assertEqual(a.calls, b.calls)
        self.assertEqual(x['prompt_sha256'], y['prompt_sha256'])
        self.assertTrue(x['quality']['passed'])
        self.assertEqual(x['sources'][0]['chunk_id'], 'fixed-one')

    def test_empty_context_never_calls_generation(self):
        prepared = prepare(self.kb, self.embedding, CASE['question'], self.settings, max_context_chars=1)
        model = Model()
        negative = {**CASE, 'answerable': False}
        row = observe(model, prepared, negative)
        self.assertEqual(model.calls, [])
        self.assertTrue(row['response']['abstained'])
        self.assertTrue(row['quality']['passed'])
        self.assertEqual(prepared['dropped_for_budget'], 1)

    def test_filter_and_no_rewrite_use_real_sqlite_search(self):
        filtered = prepare(self.kb, self.embedding, CASE['question'], self.settings, mode='filter')
        self.assertEqual(filtered['retrieval']['rewrite']['method'], 'none')
        self.assertEqual(filtered['excerpts'][0]['source'], 'worker.py')
        self.assertEqual(self.embedding.calls, 2)

    def test_embedding_model_mismatch_and_dimension_fail(self):
        wrong = Embed()
        wrong.model = 'different'
        with self.assertRaises(ValueError):
            prepare(self.kb, wrong, 'question', self.settings)
        wrong.model = 'bge-m3'
        wrong.embed = lambda _: [[1.]]
        with self.assertRaises(ValueError):
            prepare(self.kb, wrong, 'question', self.settings)

    def test_invalid_citations_quotes_json_and_flags(self):
        valid = {'answer': 'The worker runs jobs.', 'abstained': False,
                 'citations': [{'excerpt': 1, 'quote': TEXT}]}
        bad = ['not json', json.dumps([]), json.dumps({**valid, 'extra': 1}),
               json.dumps({**valid, 'abstained': 'false'}), json.dumps({**valid, 'citations': []}),
               json.dumps({**valid, 'citations': [{'excerpt': True, 'quote': TEXT}]}),
               json.dumps({**valid, 'citations': [{'excerpt': 9, 'quote': TEXT}]}),
               json.dumps({**valid, 'citations': [{'excerpt': 1, 'quote': 'invented'}]}),
               json.dumps({**valid, 'abstained': True})]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_answer(raw, self.prepared['excerpts'])

    def test_incomplete_error_invalid_do_not_count_as_success(self):
        model = Model()
        model.complete = False
        self.assertEqual(observe(model, self.prepared, CASE)['status'], 'incomplete')
        model.complete, model.raw = True, 'oops'
        self.assertEqual(observe(model, self.prepared, CASE)['status'], 'invalid')
        model.generate = lambda _: (_ for _ in ()).throw(ProviderError('timeout'))
        self.assertEqual(observe(model, self.prepared, CASE)['status'], 'error')

    def test_statistics_repeats_abstentions_and_failed_trial(self):
        row = observe(Model(), self.prepared, CASE)
        report = {'provider_names': ['local'], 'providers': {'local': {'ready': True}}, 'results': [row, dict(row)]}
        summarize(report)
        self.assertTrue(report['local_rag_verified'])
        self.assertEqual(report['summary']['local']['exactly_stable_cases'], 1)
        report['results'].append({'provider': 'local', 'case_id': CASE['id'], 'status': 'error'})
        summarize(report)
        self.assertFalse(report['all_checks_passed'])
        self.assertEqual(report['summary']['local']['repeated_cases'], 0)

    def test_abstentions_do_not_verify_local_generation(self):
        prepared = {**self.prepared, 'excerpts': []}
        row = observe(Model(), prepared, {**CASE, 'answerable': False})
        report = {'provider_names': ['local'], 'providers': {'local': {'ready': True}}, 'results': [row]}
        summarize(report)
        self.assertFalse(report['local_rag_verified'])
        self.assertIsNone(report['summary']['local']['generation_median_seconds'])

    def test_cloud_failure_and_no_key_keep_local_running(self):
        for key in (None, 'fake-offline-key'):
            with self.subTest(key=key):
                args = parser().parse_args(['compare', '--db', str(self.path), '--repeats', '2',
                    '--output', str(Path(self.tmp.name) / 'compare.json'), '--questions', str(self.cases_file())])
                with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', Model), patch('main.cloud_key', return_value=key), patch('main.GroqProvider', side_effect=ProviderError('cloud unavailable')):
                    code = run(args)
                report = json.loads(args.output.read_text())
                self.assertEqual(report['summary']['local']['valid_responses'], 2)
                self.assertTrue(report['local_rag_verified'])
                self.assertEqual(code, 0 if key is None else 1)
                self.assertTrue(args.output.with_suffix('.md').is_file())

    def cases_file(self):
        path = Path(self.tmp.name) / 'questions.json'
        path.write_text(json.dumps([CASE]))
        return path

    def test_interrupt_saves_partial_report(self):
        args = parser().parse_args(['evaluate', '--db', str(self.path), '--output', str(Path(self.tmp.name) / 'partial.json'), '--questions', str(self.cases_file())])
        model = Model()
        model.generate = lambda _: (_ for _ in ()).throw(KeyboardInterrupt())
        with patch('main.ExistingIndex.verify', return_value={}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', return_value=model):
            self.assertEqual(run(args), 130)
        self.assertEqual(json.loads(args.output.read_text())['state'], 'interrupted')

    def test_local_mode_never_reads_cloud_key(self):
        args = parser().parse_args(['ask', 'Which process?', '--db', str(self.path), '--output', str(Path(self.tmp.name) / 'local.json')])
        with patch('main.ExistingIndex.verify', return_value={}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', Model), patch('main.cloud_key', side_effect=AssertionError('cloud used')):
            self.assertEqual(run(args), 0)

    def test_local_url_cloud_tag_and_remote_host_rejected(self):
        for url in ('https://example.com', 'http://127.0.0.1@evil.com', 'http://127.0.0.1:11434/path'):
            with self.assertRaises(ProviderError):
                LocalEmbeddings(url=url)
        with self.assertRaises(ProviderError):
            LocalEmbeddings(model='embedding:cloud')
        class RemoteHTTP:
            def request(self, url, body=None):
                if url.endswith('/api/tags'):
                    return {'models': [{'name': 'bge-m3:latest'}]}
                if url.endswith('/api/show'):
                    return {'remote_host': 'evil'}
                return {'version': 'test'}
        with self.assertRaises(ProviderError):
            LocalEmbeddings('bge-m3', http=RemoteHTTP()).doctor()

    def test_embed_api_wrong_model_nan_zero_and_count(self):
        class FakeHTTP:
            payload = {}
            def request(self, url, body=None):
                self.body = body
                return self.payload
        http = FakeHTTP()
        provider = LocalEmbeddings('bge-m3', http=http)
        for payload in ({'model': 'wrong', 'embeddings': [[1., 0.]]},
                        {'model': 'bge-m3', 'embeddings': []},
                        {'model': 'bge-m3', 'embeddings': [[float('nan')]]},
                        {'model': 'bge-m3', 'embeddings': [[0., 0.]]}):
            http.payload = payload
            with self.assertRaises(ProviderError):
                provider.embed(['q'])
        http.payload = {'model': 'bge-m3:latest', 'embeddings': [[2., 0.]]}
        self.assertEqual(provider.embed(['q']), [[1., 0.]])
        self.assertIs(http.body['truncate'], False)

    def test_question_schema_and_numeric_inputs(self):
        self.assertEqual(len(load_cases(Path(__file__).with_name('questions.json'))), 20)
        path = self.cases_file()
        for cases in ([], [CASE, CASE], [{**CASE, 'answerable': 'true'}], [{**CASE, 'expected_terms': []}]):
            path.write_text(json.dumps(cases))
            with self.assertRaises(ValueError):
                load_cases(path)
        for args in (['evaluate', '--repeats', '0'], ['evaluate', '--min-similarity', 'nan'], ['evaluate', '--timeout', 'inf']):
            with self.assertRaises(SystemExit):
                parser().parse_args(args)

    def test_percentiles_and_model_loading_evidence(self):
        self.assertEqual(percentile([1, 2, 10], .5), 2)
        self.assertAlmostEqual(percentile([1, 2, 10], .95), 9.2)
        self.assertIsNone(percentile([], .95))
        model = Model()
        model.running = lambda: []
        row = observe(model, self.prepared, CASE)
        report = {'provider_names': ['local'], 'providers': {'local': {'ready': True}}, 'results': [row]}
        summarize(report)
        self.assertFalse(report['local_rag_verified'])

    def test_successful_cloud_pair_alternates_and_retrieves_once_per_trial(self):
        order = []
        class Local(Model):
            def generate(self, messages):
                order.append(self.name)
                return super().generate(messages)
        class Cloud(Local):
            name = 'cloud'
            model = 'openai/gpt-oss-20b'
        embedding = Embed()
        args = parser().parse_args(['compare', '--db', str(self.path), '--repeats', '2',
            '--output', str(Path(self.tmp.name) / 'paired.json'), '--questions', str(self.cases_file())])
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=embedding), patch('main.OllamaProvider', Local), patch('main.GroqProvider', Cloud), patch('main.cloud_key', return_value='offline-placeholder'):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text())
        self.assertEqual(embedding.calls, 2)
        self.assertEqual(order, ['local', 'cloud', 'cloud', 'local'])
        for trial in (1, 2):
            rows = [r for r in report['results'] if r['trial'] == trial]
            self.assertEqual(len({r['prompt_sha256'] for r in rows}), 1)
        self.assertTrue(report['all_checks_passed'])
        self.assertTrue(verify(report)['passed'])
        corrupted = deepcopy(report)
        corrupted['results'][0]['prompt_sha256'] = 'wrong'
        self.assertFalse(verify(corrupted)['passed'])
        corrupted = deepcopy(report)
        corrupted['results'] = corrupted['results'][:-1]
        self.assertFalse(verify(corrupted)['passed'])
        corrupted = deepcopy(report)
        corrupted['summary']['local']['success_rate'] = .5
        self.assertFalse(verify(corrupted)['passed'])

    def test_connection_reset_is_a_safe_reportable_provider_failure(self):
        from http.client import IncompleteRead
        for error in (ConnectionResetError('sensitive-server-details'), IncompleteRead(b'partial-secret')):
            with patch('providers.HTTP.request', side_effect=error):
                with self.assertRaisesRegex(ProviderError, 'connection closed'):
                    ReliableHTTP(local=True).request('http://127.0.0.1:11434/api/embed')

    def test_actual_week6_corpus_chunks_pass_read_only_integrity_checks(self):
        # Real corpus/chunking; synthetic vectors only, never live embedding evidence.
        path = Path(self.tmp.name) / 'corpus.db'
        writer = KnowledgeBase(path)
        try:
            docs = load_documents(ROOT)
            for strategy in ('fixed', 'structural'):
                chunks = chunk_documents(docs, strategy)
                writer.save(docs, strategy, chunks, [[1., 0.] for _ in chunks],
                            'offline-test-vectors', 500, 75, revision(ROOT))
        finally:
            writer.close()
        reader = ExistingIndex(path)
        try:
            self.assertTrue(reader.verify()['read_only'])
        finally:
            reader.close()

    def test_invalid_stored_line_metadata_rejected(self):
        with self.kb.db:
            self.kb.db.execute('UPDATE chunks SET start_line=0')
        reader = ExistingIndex(self.path)
        try:
            with self.assertRaisesRegex(ValueError, 'line metadata'):
                reader.verify()
        finally:
            reader.close()

    def test_real_first_response_remains_invalid_even_if_trailing_quote_removed(self):
        fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('first-live-failure.json').read_text())
        with self.assertRaisesRegex(ValueError, 'JSON object'):
            parse_answer(fixture['raw'], fixture['excerpts'])
        with self.assertRaisesRegex(ValueError, 'exact substring'):
            parse_answer(fixture['raw'][:-1], fixture['excerpts'])

    def test_quote_ids_resolve_original_backticks_and_reject_unknown_or_duplicate(self):
        fixture = json.loads(Path(__file__).with_name('fixtures').joinpath('first-live-failure.json').read_text())
        catalog = catalog_for(fixture['excerpts'])
        ids = [q['quote_id'] for q in catalog if '`worker.py`' in q['quote']]
        raw = json.dumps({'answer': 'worker.py', 'abstained': False, 'quote_ids': ids})
        value = parse_answer(raw, fixture['excerpts'], catalog)
        self.assertEqual(len(value['citations']), 2)
        for citation in value['citations']:
            self.assertIn('`worker.py`', citation['quote'])
            self.assertIn(citation['quote'], fixture['excerpts'][citation['excerpt'] - 1]['text'])
        for selected in (['e999-q999'], [ids[0], ids[0]], [], [True]):
            with self.assertRaises(ValueError):
                parse_answer(json.dumps({'answer': 'worker.py', 'abstained': False, 'quote_ids': selected}), fixture['excerpts'], catalog)

    def test_quote_id_abstention_requires_canonical_text_and_empty_selection(self):
        valid = {'answer': 'I do not know from these excerpts.', 'abstained': True, 'quote_ids': []}
        self.assertTrue(parse_answer(json.dumps(valid), self.prepared['excerpts'], self.prepared['quote_catalog'])['abstained'])
        for value in ({**valid, 'answer': 'Invented fact'}, {**valid, 'quote_ids': ['e1-q1']}):
            with self.assertRaises(ValueError):
                parse_answer(json.dumps(value), self.prepared['excerpts'], self.prepared['quote_catalog'])

    def test_structured_requests_use_native_json_controls_without_changing_prompts(self):
        bodies = []
        def request(_http, url, body=None, headers=None):
            bodies.append(body)
            if url.endswith('/api/chat'):
                return {'model': 'qwen2.5:14b', 'message': {'content': Model().raw},
                        'done': True, 'done_reason': 'stop'}
            return {'model': 'openai/gpt-oss-20b', 'choices': [{'message': {'content': Model().raw}, 'finish_reason': 'stop'}]}
        local = OllamaProvider(http=StructuredHTTP(local=True), model='qwen2.5:14b')
        cloud = GroqProvider('offline-placeholder', http=StructuredHTTP())
        with patch('rag28.ReliableHTTP.request', request):
            self.assertTrue(local.generate(self.prepared['messages']).complete)
            self.assertTrue(cloud.generate(self.prepared['messages']).complete)
        self.assertEqual(bodies[0]['messages'], bodies[1]['messages'])
        self.assertEqual(bodies[0]['format']['required'], ['claims', 'abstained'])
        self.assertEqual(bodies[0]['format']['properties']['claims']['properties']['c1']['properties']['quote_id']['enum'], ['e1-q1'])
        self.assertEqual(bodies[1]['response_format']['type'], 'json_schema')
        self.assertTrue(bodies[1]['response_format']['json_schema']['strict'])
        self.assertEqual(bodies[1]['response_format']['json_schema']['schema'], bodies[0]['format'])
        self.assertNotIn('format', bodies[1])

    def test_catalog_preserves_indentation_and_never_leaks_gold_terms(self):
        excerpt = {'excerpt': 1, 'text': 'def job():\n    return "worker.py"', 'source': 'worker.py', 'section': 'code'}
        catalog = catalog_for([excerpt])
        self.assertEqual(catalog[1]['quote'], '    return "worker.py"')
        prompt = json.loads(self.prepared['messages'][1]['content'])
        self.assertEqual(prompt['excerpts'], model_excerpts(self.prepared['excerpts'], self.prepared['quote_catalog'], 'objects_v8'))
        self.assertNotIn('expected_terms', self.prepared['messages'][1]['content'])

    def test_atomic_report_no_nan(self):
        target = Path(self.tmp.name) / 'report.txt'
        atomic_text(target, 'one')
        atomic_text(target, 'two')
        self.assertEqual(target.read_text(), 'two')
        self.assertEqual(list(target.parent.glob('*.tmp')), [])

    def make_baseline(self, cloud_bad=False, case=None):
        case = case or CASE
        questions = self.cases_file()
        questions.write_text(json.dumps([case]))
        args = parser().parse_args(['compare', '--db', str(self.path), '--repeats', '3',
            '--output', str(Path(self.tmp.name) / 'baseline.json'), '--questions', str(questions)])
        class Cloud(Model):
            name = 'cloud'
            model = 'openai/gpt-oss-20b'
            def generate(self, messages):
                if cloud_bad:
                    self.raw = 'invalid JSON'
                return super().generate(messages)
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', Model), patch('main.GroqProvider', Cloud), patch('main.cloud_key', return_value='offline-placeholder'):
            run(args)
        return args, Cloud

    def test_selective_retry_only_calls_failed_provider_and_preserves_baseline(self):
        from retry28 import retry_plan
        baseline, _ = self.make_baseline(cloud_bad=True)
        original = baseline.output.read_bytes()
        args = parser().parse_args(['compare', '--db', str(self.path), '--retry-from', str(baseline.output),
            '--output', str(Path(self.tmp.name) / 'retry.json'), '--questions', str(baseline.questions)])
        class Cloud(Model):
            name = 'cloud'
            model = 'openai/gpt-oss-20b'
        cloud = Cloud()
        local = Model()
        local.doctor = lambda: (_ for _ in ()).throw(AssertionError('local preflight should be skipped'))
        local.generate = lambda _: (_ for _ in ()).throw(AssertionError('successful local was regenerated'))
        embedding = Embed()
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=embedding), patch('main.OllamaProvider', return_value=local), patch('main.GroqProvider', return_value=cloud), patch('main.cloud_key', return_value='offline-placeholder'):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text())
        self.assertEqual(len(cloud.calls), 3)
        self.assertEqual(embedding.calls, 3)
        self.assertEqual(report['provider_names'], ['cloud'])
        self.assertFalse(report['local_rag_verified'])
        self.assertTrue(verify(report)['passed'])
        self.assertEqual(baseline.output.read_bytes(), original)
        plan = retry_plan(args.output, [CASE], vars(args), 'compare', 3)
        self.assertEqual(plan['planned_observations'], [])
        tampered = deepcopy(report)
        tampered['planned_observations'].pop()
        self.assertFalse(verify(tampered)['passed'])

    def test_plan_only_makes_no_provider_calls_and_rejects_overwrite(self):
        baseline, _ = self.make_baseline(cloud_bad=True)
        argv = ['compare', '--db', str(self.path), '--retry-from', str(baseline.output),
                '--questions', str(baseline.questions), '--output', str(Path(self.tmp.name) / 'plan.json'), '--plan-only']
        args = parser().parse_args(argv)
        with patch('main.ExistingIndex', side_effect=AssertionError('provider/index access')):
            self.assertEqual(run(args), 0)
        self.assertFalse(args.output.exists())
        args.output = baseline.output
        with self.assertRaisesRegex(ValueError, 'differ'):
            run(args)

    def test_retry_reassesses_rubric_without_accepting_invalid_answers(self):
        from retry28 import retry_plan
        baseline, _ = self.make_baseline(cloud_bad=True, case={**CASE, 'expected_terms': ['worker', 'SQLite']})
        plan = retry_plan(baseline.output, [CASE], vars(baseline), 'compare', 3)
        local = next(a for a in plan['assessments'] if a['provider'] == 'local')
        self.assertEqual(local['action'], 'retain')
        self.assertTrue(local['rubric_changed'])
        self.assertEqual(len(local['reassessments']), 3)
        self.assertEqual(plan['generation_upper_bound'], {'local': 0, 'cloud': 3})
        changed = vars(baseline).copy()
        changed['local_model'] = 'different'
        with self.assertRaisesRegex(ValueError, 'local_model'):
            retry_plan(baseline.output, [CASE], changed, 'compare', 3)
        damaged = json.loads(baseline.output.read_text())
        damaged['results'][0]['response']['answer'] = 'tampered'
        baseline.output.write_text(json.dumps(damaged))
        with self.assertRaisesRegex(ValueError, 'internally inconsistent'):
            retry_plan(baseline.output, [CASE], vars(baseline), 'compare', 3)

    def test_missing_baseline_trials_are_planned_after_interrupt(self):
        from retry28 import retry_plan
        from main import save
        baseline, _ = self.make_baseline()
        report = json.loads(baseline.output.read_text())
        report['state'] = 'interrupted'
        report['results'] = report['results'][:2]
        report['retrievals'] = report['retrievals'][:1]
        save(report, baseline.output)
        plan = retry_plan(baseline.output, [CASE], vars(baseline), 'compare', 3)
        self.assertEqual(plan['generation_upper_bound'], {'local': 3, 'cloud': 3})

    def test_cloud_429_retries_are_bounded_logged_and_timed(self):
        body = {'model': 'openai/gpt-oss-20b', 'messages': self.prepared['messages']}
        http = StructuredHTTP(rate_retries=2, retry_delay=30)
        limit = ProviderError('HTTP 429 at POST /openai/v1/chat/completions. Rate limit reached; retry later.')
        with patch('rag28.ReliableHTTP.request', side_effect=[limit, limit, {'ok': True}]) as request, patch('rag28.sleep') as wait:
            self.assertEqual(http.request('https://api.groq.com/openai/v1/chat/completions', body), {'ok': True})
        self.assertEqual(request.call_count, 3)
        self.assertEqual([c.args[0] for c in wait.call_args_list], [30, 60])
        self.assertEqual([a['status'] for a in http.attempts], ['error', 'error', 'ok'])
        self.assertEqual(body.keys(), {'model', 'messages'})
        http = StructuredHTTP(rate_retries=1)
        with patch('rag28.ReliableHTTP.request', side_effect=limit) as request, patch('rag28.sleep'):
            with self.assertRaises(ProviderError):
                http.request('https://api.groq.com/openai/v1/chat/completions', body)
        self.assertEqual(request.call_count, 2)
        for error in [ProviderError('HTTP 400 bad request'), ProviderError('timeout')]:
            with patch('rag28.ReliableHTTP.request', side_effect=error) as request, patch('rag28.sleep') as wait:
                with self.assertRaises(ProviderError):
                    http.request('https://api.groq.com/openai/v1/chat/completions', body)
                self.assertEqual(request.call_count, 1)
                wait.assert_not_called()

    def test_transport_retry_diagnostics_are_part_of_observation(self):
        model = Model()
        class Transport:
            attempts = []
        model.http = Transport()
        original = model.generate
        def generate(messages):
            model.http.attempts.extend([{'attempt': 1, 'status': 'error', 'wait_seconds': 30},
                                        {'attempt': 2, 'status': 'ok'}])
            return original(messages)
        model.generate = generate
        row = observe(model, self.prepared, CASE)
        self.assertEqual(len(row['transport_attempts']), 2)
        self.assertEqual(len(observe(model, self.prepared, CASE)['transport_attempts']), 2)

    def test_complete_mechanism_rubric_accepts_aliases_but_rejects_generic_outcome(self):
        from rag28 import quality
        case = {**CASE, 'expected_term_groups': [['conversation_id', 'UUID', 'identifier']]}
        value = {'answer': 'The worker uses a UUID.', 'abstained': False,
                 'citations': [{'excerpt': 1, 'quote': TEXT}]}
        self.assertTrue(quality(case, value, self.prepared['excerpts'])['passed'])
        value['answer'] = 'The worker supports multiple topics.'
        self.assertFalse(quality(case, value, self.prepared['excerpts'])['passed'])

    def test_non_gpt_oss_cloud_keeps_json_object_mode(self):
        body = {'model': 'other-cloud-model', 'messages': self.prepared['messages']}
        with patch('rag28.ReliableHTTP.request', return_value={}) as request:
            StructuredHTTP().request('https://api.groq.com/openai/v1/chat/completions', body)
        self.assertEqual(request.call_args.args[1]['response_format'], {'type': 'json_object'})

    def test_real_cloud_contract_failures_are_not_repaired_retrospectively(self):
        rows = json.loads(Path(__file__).with_name('fixtures').joinpath('cloud-contract-failures-v2.json').read_text())
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertGreater(len(json.loads(row['raw'])['quote_ids']), 12)
            with self.assertRaisesRegex(ValueError, 'at most 12'):
                parse_answer(row['raw'], [], [])

    def test_missing_cloud_key_does_not_silently_skip_a_required_retry(self):
        baseline, _ = self.make_baseline(cloud_bad=True)
        args = parser().parse_args(['compare', '--db', str(self.path), '--retry-from', str(baseline.output),
            '--output', str(Path(self.tmp.name) / 'no-key.json'), '--questions', str(baseline.questions)])
        local = Model()
        local.generate = lambda _: (_ for _ in ()).throw(AssertionError('passing local called'))
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', return_value=local), patch('main.cloud_key', return_value=None):
            self.assertEqual(run(args), 1)
        report = json.loads(args.output.read_text())
        self.assertEqual(report['summary']['cloud']['errors_or_invalid'], 3)
        self.assertFalse(report['all_checks_passed'])

    def test_persistent_cloud_429_pauses_cloud_but_finishes_local(self):
        args = parser().parse_args(['compare', '--db', str(self.path), '--repeats', '3',
            '--output', str(Path(self.tmp.name) / 'rate-limit.json'), '--questions', str(self.cases_file())])
        class Cloud(Model):
            name = 'cloud'
            model = 'openai/gpt-oss-20b'
            def generate(self, messages):
                self.calls.append(messages)
                raise ProviderError('HTTP 429 at POST /openai/v1/chat/completions. Rate limit reached.')
        local, cloud = Model(), Cloud()
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', return_value=local), patch('main.GroqProvider', return_value=cloud), patch('main.cloud_key', return_value='offline-placeholder'):
            self.assertEqual(run(args), 1)
        self.assertEqual(len(cloud.calls), 1)
        self.assertEqual(len(local.calls), 3)
        report = json.loads(args.output.read_text())
        self.assertEqual(report['summary']['cloud']['errors_or_invalid'], 3)
        self.assertTrue(report['local_rag_verified'])
        self.assertTrue(verify(report, require_success=False)['passed'])

    def test_fixed_slots_enforce_bound_null_refusal_and_unique_known_ids(self):
        base = {'answer': 'The worker runs jobs.', 'abstained': False,
                'quote_ids': {'q1': 'e1-q1', 'q2': None, 'q3': None, 'q4': None}}
        parse = lambda v: parse_answer(json.dumps(v), self.prepared['excerpts'],
                                       self.prepared['quote_catalog'], 'quote_slots_v4')
        self.assertEqual(len(parse(base)['citations']), 1)
        for ids in ({**base['quote_ids'], 'q5': 'e1-q1'},
                    {**base['quote_ids'], 'q2': 'e1-q1'},
                    {**base['quote_ids'], 'q1': True},
                    {**base['quote_ids'], 'q1': 'unknown'}, ['e1-q1']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                parse({**base, 'quote_ids': ids})
        refusal = {'answer': 'I do not know from these excerpts.', 'abstained': True,
                   'quote_ids': {f'q{i}': None for i in range(1, 5)}}
        self.assertTrue(parse(refusal)['abstained'])
        with self.assertRaises(ValueError):
            parse({**refusal, 'quote_ids': base['quote_ids']})

    def test_passages_keep_complete_mechanisms_and_exact_code_without_fences(self):
        text = '# Heading\n\nEach topic has a UUID. Messages are loaded from SQLite.\n\n```python\ndef job():\n    return "worker.py"\n```\n'
        excerpts = [{'excerpt': 1, 'text': text, 'source': 'worker.py', 'section': 'code'}]
        new = catalog_for(excerpts, style='passages_v4')
        old = catalog_for(excerpts)
        self.assertLess(len(new), len(old))
        self.assertEqual(new[0]['quote'], 'Each topic has a UUID. Messages are loaded from SQLite.')
        self.assertEqual(new[1]['quote'], 'def job():\n    return "worker.py"')
        for q in new:
            self.assertIn(q['quote'], text)
            self.assertNotIn('```', q['quote'])
        self.assertEqual(old[0]['quote'], '# Heading')

    def test_schema_has_only_closed_objects_and_nullable_primitives_no_array_limits(self):
        from quotes28 import ANSWER_SCHEMA
        def inspect(schema):
            self.assertNotIn('maxItems', schema)
            self.assertNotEqual(schema.get('type'), 'array')
            if schema.get('type') == 'object' or schema.get('type') == ['object', 'null']:
                self.assertFalse(schema['additionalProperties'])
                self.assertEqual(set(schema['required']), set(schema['properties']))
                for child in schema['properties'].values(): inspect(child)
        inspect(ANSWER_SCHEMA)
        self.assertEqual(len(ANSWER_SCHEMA['properties']['claims']['properties']), 4)

    def test_other_language_source_does_not_make_weak_evidence_pass(self):
        from rag28 import quality
        case = {**CASE, 'expected_sources': ['day7/README.md', 'day7/README.ru.md'],
                'expected_evidence_groups': [['SQLite'], ['UUID', 'conversation_id']]}
        excerpts = [{'excerpt': 1, 'source': 'day7/README.md'}]
        value = {'answer': 'The worker isolates topics with UUIDs in SQLite.', 'abstained': False,
                 'citations': [{'excerpt': 1, 'quote': 'The worker opens SQLite.'}]}
        assessed = quality(case, value, excerpts)
        self.assertTrue(assessed['expected_source_cited'])
        self.assertFalse(assessed['passed'])
        value['citations'][0]['quote'] = 'The worker opens SQLite; each topic has a UUID.'
        self.assertTrue(quality(case, value, excerpts)['passed'])

    def test_cloud_only_filter_keeps_unresolved_local_uninvoked(self):
        baseline, _ = self.make_baseline(case={**CASE, 'expected_terms': ['worker', 'SQLite']})
        args = parser().parse_args(['compare', '--only-provider', 'cloud', '--db', str(self.path),
            '--retry-from', str(baseline.output), '--questions', str(baseline.questions),
            '--output', str(Path(self.tmp.name) / 'cloud-only.json')])
        class Cloud(Model):
            name = 'cloud'
            model = 'openai/gpt-oss-20b'
        cloud = Cloud()
        value = json.loads(cloud.raw); value['claims']['c1']['statement'] = 'The worker uses SQLite.'
        cloud.raw = json.dumps(value)
        local = Model()
        local.generate = lambda _: (_ for _ in ()).throw(AssertionError('local called in cloud-only mode'))
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', return_value=local), patch('main.GroqProvider', return_value=cloud), patch('main.cloud_key', return_value='offline-placeholder'):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text())
        self.assertEqual(report['provider_names'], ['cloud'])
        self.assertEqual(len(cloud.calls), 3)
        self.assertTrue(verify(report)['passed'])

    def test_claims_assemble_only_model_statements_with_matching_exact_evidence(self):
        excerpts = [{'excerpt': 1, 'text': 'SQLite stores messages.\n\nEach topic has a UUID.'}]
        catalog = catalog_for(excerpts, 'passages_v4')
        value = {'claims': {
            'c1': {'quote_id': 'e1-q1', 'statement': 'История хранится в SQLite.'},
            'c2': {'quote_id': 'e1-q2', 'statement': 'Темы разделены по UUID.'},
            'c3': None, 'c4': None}, 'abstained': False}
        parsed = parse_answer(json.dumps(value), excerpts, catalog, 'evidence_claims_v7')
        self.assertEqual(parsed['answer'], 'История хранится в SQLite.\nТемы разделены по UUID.')
        self.assertEqual(parsed['citations'], [
            {'excerpt': 1, 'quote': 'SQLite stores messages.'},
            {'excerpt': 1, 'quote': 'Each topic has a UUID.'}])
        with self.assertRaises(ValueError):
            parse_answer(json.dumps({**value, 'answer': 'Detached invented fact'}),
                         excerpts, catalog, 'evidence_claims_v7')

    def test_claims_reject_unbound_statements_unknown_ids_duplicates_and_false_refusal(self):
        value = json.loads(Model().raw)
        bad_claims = [True, {'statement': 'unbound'}, {'quote_id': 'unknown', 'statement': 'fact'},
                      {'quote_id': 'e1-q1', 'statement': ' '},
                      {'quote_id': 'e1-q1', 'statement': 3}]
        for claim in bad_claims:
            malformed = deepcopy(value); malformed['claims']['c1'] = claim
            with self.assertRaises(ValueError):
                parse_answer(json.dumps(malformed), self.prepared['excerpts'],
                             self.prepared['quote_catalog'], 'evidence_claims_v7')
        for malformed in (dict(value, abstained=True),
                          dict(value, claims={**value['claims'], 'c2': value['claims']['c1']})):
            with self.assertRaises(ValueError):
                parse_answer(json.dumps(malformed), self.prepared['excerpts'],
                             self.prepared['quote_catalog'], 'evidence_claims_v7')

    def test_two_stage_synthesis_report_and_verifier_bind_final_to_selected_evidence(self):
        args = parser().parse_args(['evaluate', '--synthesis', '--db', str(self.path), '--repeats', '1',
            '--output', str(Path(self.tmp.name) / 'synthesis.json'), '--questions', str(self.cases_file())])
        model = SynthesisModel()
        with patch('main.ExistingIndex.verify', return_value={'read_only': True}), patch('main.LocalEmbeddings', return_value=Embed()), patch('main.OllamaProvider', return_value=model), patch('main.cloud_key', side_effect=AssertionError('cloud used')):
            self.assertEqual(run(args), 0)
        report = json.loads(args.output.read_text())
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(report['summary']['local']['generation_calls'], 2)
        self.assertEqual(report['summary']['local']['attempts'], 1)
        self.assertEqual(report['results'][0]['response']['answer'], 'The worker runs scheduled jobs.')
        self.assertTrue(verify(report)['passed'])
        corrupt = deepcopy(report)
        corrupt['results'][0]['synthesis']['messages'][1]['content'] = '{}'
        self.assertFalse(verify(corrupt)['passed'])

    def test_synthesis_has_only_selected_quotes_and_does_not_feed_previous_statements(self):
        prepared = deepcopy(self.prepared)
        prepared['quote_catalog'].append({'quote_id': 'e1-q2', 'excerpt': 1, 'quote': 'Unselected distractor.'})
        selected = json.loads(Model().raw)
        selected['claims']['c1']['statement'] = 'A prior unsupported statement must not become evidence.'
        synthesis = prepare_synthesis(prepared, json.dumps(selected))
        content = json.loads(synthesis['messages'][1]['content'])
        self.assertEqual(synthesis['quote_catalog'], self.prepared['quote_catalog'])
        self.assertNotIn('Unselected distractor', synthesis['messages'][1]['content'])
        self.assertNotIn('unsupported statement', synthesis['messages'][1]['content'])
        self.assertEqual(content['excerpts'][0]['quotations'][0]['quote'], TEXT)
        raw = {'answer': 'A wrong citation.', 'abstained': False,
               'quote_ids': {'q1': 'e1-q2', 'q2': None, 'q3': None, 'q4': None}}
        with self.assertRaises(ValueError):
            parse_answer(json.dumps(raw), prepared['excerpts'], synthesis['quote_catalog'], 'quote_slots_v4')

    def test_synthesis_native_schema_uses_only_selected_ids_and_legacy_answer_contract(self):
        synthesis = prepare_synthesis(self.prepared, Model().raw)
        bodies = []
        def fake_request(http, url, body=None, headers=None):
            bodies.append(body)
            return {'model': 'qwen2.5:14b', 'message': {'content': '{}'}, 'done': True, 'done_reason': 'stop'}
        with patch('rag28.ReliableHTTP.request', fake_request):
            StructuredHTTP(local=True).request('http://127.0.0.1:11434/api/chat',
                {'model': 'qwen2.5:14b', 'messages': synthesis['messages']})
            StructuredHTTP().request('https://api.groq.com/openai/v1/chat/completions',
                {'model': 'openai/gpt-oss-20b', 'messages': synthesis['messages']})
        self.assertEqual(bodies[0]['format']['required'], ['answer', 'abstained', 'quote_ids'])
        self.assertEqual(bodies[0]['format']['properties']['quote_ids']['properties']['q1']['enum'], [None, 'e1-q1'])
        self.assertEqual(bodies[1]['response_format']['json_schema']['schema'], bodies[0]['format'])
        self.assertTrue(bodies[1]['response_format']['json_schema']['strict'])

    def test_synthesis_refusal_and_empty_context_do_not_call_second_stage(self):
        model = SynthesisModel()
        model.raw = json.dumps({'claims': {f'c{i}': None for i in range(1, 5)}, 'abstained': True})
        row = observe(model, self.prepared, {**CASE, 'answerable': False}, synthesize=True)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(row['generation_calls'], 1)
        self.assertNotIn('synthesis', row)
        empty = observe(SynthesisModel(), {**self.prepared, 'excerpts': []},
                        {**CASE, 'answerable': False}, synthesize=True)
        self.assertEqual(empty['generation_calls'], 0)
        self.assertFalse(empty['generation_called'])

    def test_synthesis_failure_records_two_calls_and_keeps_selection_raw(self):
        class FailedSynthesis(Model):
            def generate(self, messages):
                if json.loads(messages[1]['content']).get('contract'):
                    self.calls.append(messages)
                    raise ProviderError('synthesis unavailable')
                return super().generate(messages)
        model = FailedSynthesis()
        row = observe(model, self.prepared, CASE, synthesize=True)
        self.assertEqual(row['status'], 'error')
        self.assertEqual(row['generation_calls'], 2)
        self.assertEqual(row['selection_generation']['answer'], model.raw)
        self.assertIn('synthesis unavailable', row['error'])

    def test_two_stage_wall_time_includes_both_calls(self):
        with patch('rag28.perf_counter', side_effect=[10., 18.]):
            row = observe(SynthesisModel(), self.prepared, CASE, synthesize=True)
        self.assertEqual(row['generation_calls'], 2)
        self.assertEqual(row['generation_wall_seconds'], 8.)
        self.assertEqual(row['pipeline_seconds'], self.prepared['retrieval_seconds'] + 8.)

    def test_invalid_selection_and_incomplete_synthesis_never_become_success(self):
        model = SynthesisModel(); model.raw = 'invalid selection'
        row = observe(model, self.prepared, CASE, synthesize=True)
        self.assertEqual(row['status'], 'invalid')
        self.assertEqual(row['generation_calls'], 1)
        self.assertEqual(row['failed_stage'], 'selection')
        class IncompleteSynthesis(SynthesisModel):
            def generate(self, messages):
                generated = super().generate(messages)
                return replace(generated, complete=False) if json.loads(messages[1]['content']).get('contract') else generated
        row = observe(IncompleteSynthesis(), self.prepared, CASE, synthesize=True)
        self.assertEqual(row['status'], 'incomplete')
        self.assertEqual(row['generation_calls'], 2)
        self.assertNotIn('response', row)

    def test_sections_preserve_mechanism_context_and_ignore_fenced_headings(self):
        text = '# Memory\n\nSQLite stores messages.\n\n## Mechanism\n\nOpen SQLite.\n\n```python\n# This is code\nrestore(conversation_id)\n```\n\nOnly selected UUID history is sent.\n\n## Run\n\npython main.py'
        excerpts = [{'excerpt': 1, 'source': 'README.md', 'section': 'Memory', 'text': text}]
        catalog = catalog_for(excerpts, 'sections_v8')
        self.assertEqual(len(catalog), 3)
        mechanism = catalog[1]['quote']
        self.assertIn('Open SQLite.', mechanism)
        self.assertIn('restore(conversation_id)', mechanism)
        self.assertIn('Only selected UUID history', mechanism)
        for q in catalog:
            self.assertIn(q['quote'], text)
        context = model_excerpts(excerpts, catalog, 'objects_v8')
        self.assertEqual(context[0]['quotations'][1], {'quote_id': 'e1-q2', 'quote': mechanism})

    def test_long_sections_split_at_paragraphs_with_exact_contiguous_text(self):
        from quotes28 import section_passages
        text = '# Heading\n\n' + 'a' * 40 + '\n\n' + 'b' * 40 + '\n\n' + 'c' * 40
        pieces = section_passages(text, soft_limit=60)
        self.assertGreater(len(pieces), 1)
        for piece in pieces:
            self.assertIn(piece, text)
        for word in ('a' * 40, 'b' * 40, 'c' * 40):
            self.assertEqual(sum(word in piece for piece in pieces), 1)

    def test_v8_section_can_support_multiple_claims_without_changing_v7_rules(self):
        value = json.loads(Model().raw)
        value['claims']['c2'] = {'quote_id': 'e1-q1', 'statement': 'Scheduled jobs use the worker.'}
        parsed = parse_answer(json.dumps(value), self.prepared['excerpts'],
                              self.prepared['quote_catalog'], 'evidence_claims_v8')
        self.assertEqual(parsed['answer'], 'The worker runs jobs.\nScheduled jobs use the worker.')
        self.assertEqual(len(parsed['citations']), 2)
        self.assertEqual(parsed['citations'][0], parsed['citations'][1])
        with self.assertRaises(ValueError):
            parse_answer(json.dumps(value), self.prepared['excerpts'],
                         self.prepared['quote_catalog'], 'evidence_claims_v7')

    def test_claims_refusal_and_legacy_contracts_stay_separate(self):
        refusal = {'claims': {f'c{i}': None for i in range(1, 5)}, 'abstained': True}
        parsed = parse_answer(json.dumps(refusal), self.prepared['excerpts'],
                              self.prepared['quote_catalog'], 'evidence_claims_v7')
        self.assertEqual(parsed, {'answer': 'I do not know from these excerpts.',
                                 'abstained': True, 'citations': []})
        with self.assertRaises(ValueError):
            parse_answer(json.dumps(dict(refusal, abstained=False)), self.prepared['excerpts'],
                         self.prepared['quote_catalog'], 'evidence_claims_v7')
        legacy = {'answer': 'The worker runs jobs.', 'abstained': False,
                  'quote_ids': {'q1': 'e1-q1', 'q2': None, 'q3': None, 'q4': None}}
        self.assertEqual(parse_answer(json.dumps(legacy), self.prepared['excerpts'],
            self.prepared['quote_catalog'], 'quote_slots_v4')['answer'], legacy['answer'])
        with self.assertRaises(ValueError):
            parse_answer(json.dumps(legacy), self.prepared['excerpts'],
                         self.prepared['quote_catalog'], 'evidence_claims_v7')


if __name__ == '__main__':
    unittest.main(buffer=True)
