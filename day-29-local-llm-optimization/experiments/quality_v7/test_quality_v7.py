"""Scripted-contract tests only; no synthetic result is a live quality score."""
from contextlib import ExitStack
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'quality_v6'))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))
import cli29
import engine29
import provider29
import test_focused_v2 as transport_fixture
import test_day29 as fixtures
from selection7 import (FACTUAL, PREFIX, ROLES, candidates, command_role, decode,
                        prepare_selection, render, routed_question, selection_schema)
from http7 import SelectionHTTP
from guard7 import inspect
from rag28 import ReliableHTTP
spec = importlib.util.spec_from_file_location('quality_v7_launcher', HERE / 'main.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def toy_prepared(language='en'):
    question = 'How can I verify periodic archives?' if language == 'en' else 'Как проверить периодическое архивирование?'
    english = '''# Archive service

The worker prints a new archive result to logs after each run.

## Mechanism

- Archive jobs use a configured interval.
- The worker stores archive snapshots with timestamps in SQLite.
- inspect_archives() returns saved archive snapshots.
- inspect_schedule() returns next run times and errors.
- unrelated_agent() uses a remote model.

## Observation

```bash
archivectl enable vault42
archivectl status vault42
archivectl logs vault42
```
'''
    russian = '''# Архивирование

Worker печатает результат создания архива в журнал после каждого запуска.

## Схема

- Задания используют настроенный интервал.
- Worker сохраняет снимки архивов и время в SQLite.
- inspect_archives() возвращает сохранённые снимки.
- inspect_schedule() возвращает время следующего запуска и ошибки.
- unrelated_agent() использует внешнюю модель.

## Наблюдение

```bash
archivectl enable vault42
archivectl status vault42
archivectl logs vault42
```
'''
    excerpts = [{'excerpt': 1, 'source': 'archives/README.md', 'section': 'README.md', 'text': english},
                {'excerpt': 2, 'source': 'archives/README.ru.md', 'section': 'README.ru.md', 'text': russian}]
    from quotes28 import catalog_for
    return {'question': question, 'excerpts': excerpts, 'quote_catalog': catalog_for(excerpts, 'sections_v8'),
            'messages': [{'role': 'system', 'content': 'old'}, {'role': 'user', 'content': '{}'}],
            'retrieval_seconds': .001, 'output_contract': 'evidence_claims_v8'}


def selected_raw(prepared):
    ids = prepared['procedure_selection']['allowed_ids']
    return json.dumps({'selections': {role: ids[role][0] if ids[role] else None for role in ROLES}, 'abstained': False})


class SelectionTests(unittest.TestCase):
    def test_commands_are_exact_read_only_and_no_source_case_names_are_hardcoded(self):
        p = prepare_selection(toy_prepared())
        self.assertTrue(all(p['procedure_selection']['allowed_ids'][r] for r in ROLES))
        commands = [u['quote'] for u in p['quote_catalog'] if u['role'] in ('status', 'logs')]
        self.assertTrue(commands)
        self.assertNotIn('archivectl enable vault42', commands)
        self.assertEqual(command_role('archivectl status vault42'), 'status')
        self.assertIsNone(command_role('archivectl status vault42; delete-data'))
        self.assertNotIn('bublik-day18', (HERE / 'selection7.py').read_text())

    def test_every_unit_is_exact_source_substring_and_unrelated_agent_is_excluded(self):
        p = prepare_selection(toy_prepared())
        for u in p['quote_catalog']:
            x = next(x for x in p['excerpts'] if x['excerpt'] == u['excerpt'])
            self.assertIn(u['quote'], x['text'])
            self.assertNotIn('unrelated_agent', u['quote'])

    def test_question_language_selects_role_candidates_before_model_payload(self):
        for lang, excerpt in (('ru', 2), ('en', 1)):
            p = prepare_selection(toy_prepared(lang))
            payload = json.loads(p['messages'][1]['content'])
            for role in ROLES:
                self.assertTrue(payload['evidence_by_role'][role])
                ids = payload['allowed_ids'][role]
                self.assertTrue(all(u['excerpt'] == excerpt for u in p['quote_catalog'] if u['quote_id'] in ids))

    def test_all_valid_choices_render_deterministically_with_exact_citations(self):
        p = prepare_selection(toy_prepared('ru'))
        raw = selected_raw(p)
        value = render(raw, p['excerpts'], p['quote_catalog'], p['output_contract'])
        self.assertFalse(value['abstained'])
        self.assertIn('сохранённые результаты', value['answer'])
        self.assertEqual(len(value['citations']), 4)
        self.assertIn('Это план проверки', value['answer'])
        self.assertNotIn('enable vault42', value['answer'])
        self.assertEqual(value, render(raw, p['excerpts'], p['quote_catalog'], p['output_contract']))

    def test_missing_phase_does_not_get_filled_by_application(self):
        p = prepare_selection(toy_prepared())
        raw = json.loads(selected_raw(p)); raw['selections']['recurrence'] = None
        encoded = json.dumps(raw)
        value = render(encoded, p['excerpts'], p['quote_catalog'], p['output_contract'])
        self.assertTrue(value['abstained'])
        self.assertEqual(value['citations'], [])
        self.assertIn('missing_role:recurrence', decode(encoded, p['quote_catalog'], p['excerpts'], p['output_contract'])['errors'])

    def test_wrong_role_and_unknown_id_are_quality_failures_not_new_usable_claims(self):
        p = prepare_selection(toy_prepared())
        raw = json.loads(selected_raw(p))
        raw['selections']['status'] = raw['selections']['logs']
        self.assertTrue(render(json.dumps(raw), p['excerpts'], p['quote_catalog'], p['output_contract'])['abstained'])
        raw['selections']['status'] = 'invented-id'
        self.assertTrue(render(json.dumps(raw), p['excerpts'], p['quote_catalog'], p['output_contract'])['abstained'])

    def test_damaged_source_unit_is_rejected_even_if_id_was_allowed(self):
        p = prepare_selection(toy_prepared())
        raw = selected_raw(p)
        qid = json.loads(raw)['selections']['status']
        u = next(u for u in p['quote_catalog'] if u['quote_id'] == qid)
        u['quote'] = 'archivectl status invented_vault'
        self.assertTrue(render(raw, p['excerpts'], p['quote_catalog'], p['output_contract'])['abstained'])

    def test_unit_metadata_cannot_substitute_source_or_parent_quote(self):
        original = prepare_selection(toy_prepared())
        raw = selected_raw(original)
        qid = json.loads(raw)['selections']['status']
        for field, value in (('source', 'invented/README.md'), ('original_quote_id', 'e999-q999'), ('language', 'ru')):
            p = deepcopy(original)
            next(u for u in p['quote_catalog'] if u['quote_id'] == qid)[field] = value
            self.assertTrue(render(raw, p['excerpts'], p['quote_catalog'], p['output_contract'])['abstained'])

    def test_raw_abstention_and_malformed_complete_output_are_not_hidden_repaired(self):
        p = prepare_selection(toy_prepared())
        for raw in ('bad JSON', json.dumps({'selections': {r: None for r in ROLES}, 'abstained': True})):
            self.assertTrue(render(raw, p['excerpts'], p['quote_catalog'], p['output_contract'])['abstained'])

    def test_selector_http_sends_sealed_role_schema_instead_of_legacy_claims_schema(self):
        p = prepare_selection(toy_prepared())
        body = {'model': 'local-test', 'messages': p['messages'], 'options': {'num_predict': 100}, 'stream': False}
        with patch.object(ReliableHTTP, 'request', return_value={'done': True}) as send:
            SelectionHTTP(local=True).request('http://127.0.0.1:11434/api/chat', body)
        payload = send.call_args.args[2]
        self.assertEqual(payload['format'], json.loads(p['messages'][1]['content'])['schema'])
        self.assertIn('selections', payload['format']['properties'])
        self.assertNotIn('format', body)

    def test_router_changes_periodic_verification_only(self):
        self.assertTrue(routed_question('Как на сервере проверить периодический сбор?'))
        self.assertFalse(routed_question('Which process periodically collects snapshots?'))
        self.assertFalse(routed_question('How can I verify a saved report?'))


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.transport = transport_fixture.FocusedTests('test_portable_baseline_import_works_with_an_empty_cache')
        self.transport.setUp()
        self.addCleanup(self.transport.doCleanups)
        self.f = self.transport.fixture
        profiles = engine29.load_profiles(HERE.parent / 'focused_v3/profiles.json')
        self.f.profiles.write_text(json.dumps({k: profiles[k] for k in ('baseline', 'focused-v3-q4')}))
        case = json.loads(self.f.questions.read_text())[0]
        self.procedure = {**case, 'id': 'toy-procedure', 'question': toy_prepared()['question'], 'expected_terms': ['archivectl'], 'expected_sources': ['archives/README.md']}
        self.f.questions.write_text(json.dumps([case, self.procedure]))
        original_request = self.f.http.request
        self.missing = False
        def request(url, body=None, headers=None):
            raw = original_request(url, body, headers)
            if url.endswith('/api/chat') and body['options']['num_predict'] != 1:
                payload = json.loads(body['messages'][1]['content'])
                if str(payload.get('contract', '')).startswith(PREFIX):
                    choices = {r: payload['allowed_ids'][r][0] if payload['allowed_ids'][r] else None for r in ROLES}
                    if self.missing:
                        choices['recurrence'] = None
                    raw['message']['content'] = json.dumps({'selections': choices, 'abstained': False})
            return raw
        self.f.http.request = request

    def prepare(self, kb, embedding, question, settings):
        return toy_prepared() if question == self.procedure['question'] else self.f.prepared

    def execute(self, args):
        with patch.object(transport_fixture, 'main', launcher.main), patch.object(cli29, 'prepare', side_effect=self.prepare):
            return self.transport.execute_focused(args)

    def make_old(self):
        f = self.f
        # Build legacy baseline/factual responses with old claims contract.
        with patch.object(engine29, 'COMPACT', FACTUAL), patch.object(cli29, 'prepare', side_effect=self.prepare):
            f.execute(f.args('run', '--profiles', 'baseline', 'focused-v3-q4'))
        return f.output

    def new_args(self, old):
        f = self.f
        f.output, f.cache_path = f.root / 'v7.json', f.root / 'v7.sqlite3'
        args = f.args('run', '--profiles', 'baseline', 'focused-v3-q4', '--retry-from', str(old))
        del args[1:3]
        return args

    def test_portable_report_parser_and_cached_three_quality_failures_do_not_regenerate(self):
        old = self.make_old()
        original = old.read_bytes()
        args = self.new_args(old)
        self.missing = True
        self.assertEqual(self.execute(args), 1)
        with launcher.task_templates():
            r = cli29.read_report(self.f.output)
        self.assertEqual(r['new_answer_generation_calls'], 3)
        self.assertEqual(sum(e['reused'] for e in r['observations']), 9)
        fresh = [e for e in r['observations'] if not e['reused']]
        self.assertTrue(all(e['result']['status'] == 'ok' and e['result']['response']['abstained'] for e in fresh))
        self.assertTrue(all('selections' in e['result']['generation']['answer'] for e in fresh))
        counts = self.f.http.answer_calls, self.f.http.probe_calls, self.f.http.warmups
        self.assertEqual(self.execute(args), 1)
        self.assertEqual((self.f.http.answer_calls, self.f.http.probe_calls, self.f.http.warmups), counts)
        self.assertEqual(old.read_bytes(), original)

    def test_selected_response_is_reproducible_and_modified_render_is_rejected(self):
        old = self.make_old()
        args = self.new_args(old)
        self.execute(args)
        with launcher.task_templates():
            r = cli29.read_report(self.f.output)
            fresh = next(e for e in r['observations'] if not e['reused'])
            self.assertFalse(fresh['result']['response']['abstained'])
            self.assertEqual(inspect(fresh)['decision'], 'ready_for_manual_review')
            changed = deepcopy(fresh); changed['result']['response']['answer'] += 'Invented success.'
            with self.assertRaisesRegex(ValueError, 'Stored response'):
                engine29.validate_envelope(changed)
        self.assertFalse(r['optimization_verified'])

    def test_adapter_restores_runtime_and_factual_messages_after_exception(self):
        before = engine29.COMPACT, cli29.prompt_for, engine29.parse_answer, provider29.StructuredHTTP
        core = engine29.code_fingerprint()
        profile = engine29.load_profiles(self.f.profiles)['focused-v3-q4']
        with patch.object(engine29, 'COMPACT', FACTUAL):
            expected = engine29.prompt_for(self.f.prepared, profile)
        with self.assertRaises(RuntimeError):
            with launcher.task_templates():
                self.assertEqual(cli29.prompt_for(self.f.prepared, profile), expected)
                raise RuntimeError('scripted')
        self.assertEqual(before, (engine29.COMPACT, cli29.prompt_for, engine29.parse_answer, provider29.StructuredHTTP))
        self.assertEqual(core, engine29.code_fingerprint())


if __name__ == '__main__':
    unittest.main()
