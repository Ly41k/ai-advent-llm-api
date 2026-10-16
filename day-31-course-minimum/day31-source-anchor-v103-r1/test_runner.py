"""Coordinator fault injection. All inference here is explicitly synthetic."""
import asyncio
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import runner as r


class Slots:
    def __init__(self, limit):
        self.limit, self.used, self.on_reserve = limit, 0, None

    def reserve(self):
        if self.used >= self.limit:
            raise r.Stop('Budget exceeded')
        self.used += 1
        if self.on_reserve:
            self.on_reserve()


class FakeNative:
    def __init__(self, folder, count=6):
        self.document = {'cases': [{'id': f'q{i}', 'language': 'en', 'question': f'Synthetic question {i}',
                         'expected_route': 'fan_out' if i >= 4 else 'documentation'} for i in range(count)]}
        self.catalog = folder / 'catalog.json'
        self.catalog.write_text(json.dumps(self.document))
        self.calls, self.captures, self.active, self.max_active = [], [], 0, 0
        self.conditions, self.model = {'fixture': True}, {'transport': 'synthetic'}
        self.invalid = False; self.fail_mode = None; self.lose_mode = None

    def bound(self, cases):
        return sum(3 if c['expected_route'] == 'fan_out' else 2 for c in cases)

    def order(self, position):
        return ['single', 'multi'] if (position ^ (position >> 1)) % 2 == 0 else ['multi', 'single']

    def plan_labels(self, cases_digest):
        return {'catalog_design': {'kind': 'known_regression'}, 'scope': 'synthetic tests only'}

    def freeze(self):
        return {'conditions': deepcopy(self.conditions), 'model': deepcopy(self.model),
                'comparison_spec': {'version': 'synthetic'}, 'catalog_design': {'kind': 'known_regression'}}

    def validate(self, frozen):
        if self.invalid or self.conditions != frozen['conditions']:
            raise r.Stop('Source changed')

    def inspect(self):
        return {'model': deepcopy(self.model), 'generation_calls': 0}

    def index_verify(self):
        return {'status': 'verified', 'read_only': True, 'index': {'synthetic': True}}

    async def capture(self, case):
        self.captures.append(case['id'])
        return {'question': case['question'], 'language': case['language'],
                'common_preparation_seconds': 0.01,
                'observation': {'status': 'completed', 'metrics': {'capability_calls': 1}}}

    slots = staticmethod(Slots)

    async def execute(self, case, mode, snapshot, slots):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            n = 2 if mode == 'multi' and case['expected_route'] == 'fan_out' else 1
            for _ in range(n):
                slots.reserve(); self.calls.append((case['id'], mode))
                await asyncio.sleep(0)
                if self.lose_mode == (case['id'], mode):
                    raise KeyboardInterrupt('Synthetic lost response')
            bad = self.fail_mode == (case['id'], mode)
            return {'snapshot_digest': r.digest(snapshot), 'execution_status': 'failed' if bad else 'completed',
                'answer_status': 'answered', 'answer': 'SYNTHETIC', 'claims': [], 'diagnostics': [],
                'metrics': {'known_llm_calls': n, 'input_tokens': 10*n, 'output_tokens': 2*n,
                            'unknown_inference_attempts': 0}, 'synthetic': True}
        finally:
            self.active -= 1

    def result_ok(self, result, frozen):
        return result['execution_status'] == 'completed'

    def checks(self, case, result):
        return {'semantic_review': 'pending', 'semantic_support_verified': False}

    def summarize(self, report):
        values = [row['result']['metrics'] for row in report['requests'] if 'result' in row]
        return {**{k: sum(x[k] for x in values) for k in ['known_llm_calls', 'input_tokens', 'output_tokens']},
                'semantic_acceptance': 'not_evaluated', 'embedding_calls': 0}


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = FakeNative(self.root)
        self.ids = [c['id'] for c in self.native.document['cases']]
        self.plan = r.make_plan(self.native, self.ids, 14)
        self.config = {'packet': 'batch1', 'synthetic': True}
        self.journal = r.Journal(self.root / 'journal')

    def run_advance(self, **kwargs):
        return asyncio.run(r.advance(self.native, self.journal, self.config, self.plan,
                                     {'fixture': True}, **kwargs))

    def reopen(self):
        self.journal = r.Journal(self.root / 'journal')

    def interrupt(self, reason):
        fired = False
        def hook(actual, state):
            nonlocal fired
            if actual == reason and not fired:
                fired = True
                raise KeyboardInterrupt('Synthetic process interruption')
        with self.assertRaises(KeyboardInterrupt):
            self.run_advance(on_boundary=hook)
        self.reopen()

    def test_six_questions_twelve_outputs_fourteen_sequential_calls(self):
        report = self.run_advance()
        self.assertEqual(report['status'], 'completed')
        self.assertEqual(len(report['pairs']), 6)
        self.assertEqual(len(report['requests']), 12)
        self.assertEqual(len(self.native.calls), 14)
        self.assertEqual(self.native.max_active, 1)
        self.assertEqual(report['generation_slots_reserved'], 14)
        self.assertEqual(report['summary']['semantic_acceptance'], 'not_evaluated')

    def test_resume_after_question_does_not_recapture_or_regenerate(self):
        self.interrupt('question_completed_and_saved')
        before = {p.name: p.read_bytes() for p in self.journal.folder.glob('*.json')}
        first = deepcopy(self.journal.state['report']['requests'])
        report = self.run_advance()
        self.assertEqual(len(self.native.calls), 14)
        self.assertEqual(self.native.captures, self.ids)
        self.assertEqual(report['requests'][:2], first)
        self.assertTrue(all((self.journal.folder / n).read_bytes() == raw for n, raw in before.items()))

    def test_resume_between_modes_preserves_first_mode_and_snapshot(self):
        self.interrupt('post_request_conditions_verified')
        saved = deepcopy(self.journal.state['report']['requests'][0])
        snapshot = deepcopy(self.journal.state['report']['pairs'][0]['snapshot'])
        report = self.run_advance()
        self.assertEqual(report['requests'][0], saved)
        self.assertEqual(report['pairs'][0]['snapshot'], snapshot)
        self.assertEqual(len(self.native.calls), 14)
        self.assertEqual(self.native.captures.count('q0'), 1)

    def test_resume_after_durable_terminal_before_validation_no_replay(self):
        self.interrupt('terminal_request_result_saved')
        self.assertFalse(self.journal.state['report']['requests'][0]['conditions_valid_after'])
        self.assertEqual(self.run_advance()['status'], 'completed')
        self.assertEqual(len(self.native.calls), 14)

    def test_resume_after_snapshot_makes_no_duplicate_acquisition(self):
        self.interrupt('shared_snapshot_acquired_no_generation')
        self.assertEqual(len(self.native.calls), 0)
        self.run_advance()
        self.assertEqual(self.native.captures, self.ids)

    def test_completed_run_is_idempotent_no_calls_no_journal_writes(self):
        self.run_advance(); before = self.journal.sequence
        self.reopen(); self.run_advance()
        self.assertEqual(len(self.native.calls), 14)
        self.assertEqual(self.journal.sequence, before)

    def test_interrupt_before_dispatch_is_conservatively_blocked(self):
        self.interrupt('request_started_no_automatic_replay_if_interrupted')
        self.assertEqual(self.native.calls, [])
        with self.assertRaisesRegex(r.Stop, 'in-flight'):
            self.run_advance()
        self.assertEqual(self.native.calls, [])

    def test_interrupt_after_reservation_never_replays(self):
        self.interrupt('generation_slot_reserved_before_dispatch')
        self.assertEqual(self.journal.state['report']['generation_slots_reserved'], 1)
        with self.assertRaisesRegex(r.Stop, 'in-flight'):
            self.run_advance()
        self.assertEqual(self.native.calls, [])

    def test_lost_response_blocks_replay_and_keeps_consumed_budget(self):
        self.native.lose_mode = ('q0', 'single')
        with self.assertRaises(KeyboardInterrupt):
            self.run_advance()
        self.reopen(); before = len(self.native.calls)
        with self.assertRaisesRegex(r.Stop, 'in-flight'):
            self.run_advance()
        self.assertEqual(len(self.native.calls), before)
        self.assertEqual(before, 1)

    def test_technical_failure_retained_not_repaired(self):
        self.native.fail_mode = ('q0', 'single')
        report = self.run_advance()
        self.assertEqual(report['status'], 'stopped')
        self.assertEqual(report['error'], 'technical_request_failure')
        self.reopen()
        with self.assertRaisesRegex(r.Stop, 'technical'):
            self.run_advance()
        self.assertEqual(len(self.native.calls), 1)

    def test_changed_source_after_pause_blocks_before_new_call(self):
        self.interrupt('post_request_conditions_verified')
        self.native.invalid = True
        with self.assertRaisesRegex(r.Stop, 'Source changed'):
            self.run_advance()
        self.assertEqual(len(self.native.calls), 1)

    def test_changed_model_after_pause_blocks_before_new_call(self):
        self.interrupt('post_request_conditions_verified')
        self.native.model = {'different': True}
        with self.assertRaisesRegex(r.Stop, 'Model changed'):
            self.run_advance()
        self.assertEqual(len(self.native.calls), 1)

    def test_changed_run_identity_blocks(self):
        self.interrupt('post_request_conditions_verified')
        self.config['packet'] = 'batch2'
        with self.assertRaisesRegex(r.Stop, 'identity differs'):
            self.run_advance()
        self.assertEqual(len(self.native.calls), 1)

    def test_changed_cap_on_resume_blocks(self):
        self.interrupt('post_request_conditions_verified')
        self.plan['max_generation_calls'] = 15
        with self.assertRaisesRegex(r.Stop, 'identity differs'):
            self.run_advance()

    def test_insufficient_cap_refused_before_freeze(self):
        with self.assertRaisesRegex(r.Stop, '14 generation slots'):
            r.make_plan(self.native, self.ids, 13)
        self.assertIsNone(self.journal.state)
        self.assertEqual(self.native.calls, [])

    def test_more_than_six_or_duplicate_questions_refused(self):
        for ids in [self.ids + ['q0'], ['q0', 'q0'], []]:
            with self.assertRaises(r.Stop):
                r.make_plan(self.native, ids, 32)

    def test_catalog_position_order_does_not_reset_per_subset(self):
        plan = r.make_plan(self.native, ['q2', 'q3'], 4)
        self.assertEqual(plan['planned_orders'][0]['catalog_position'], 2)
        self.assertEqual(plan['planned_orders'][0]['order'], ['multi', 'single'])

    def test_duplicate_or_reordered_rows_refused(self):
        report = self.run_advance()
        report['requests'].append(deepcopy(report['requests'][0]))
        with self.assertRaisesRegex(r.Stop, 'Duplicate'):
            r.report_shape(report, self.plan)

    def test_completed_flag_cannot_hide_missing_question(self):
        report = self.run_advance(); report['pairs'].pop()
        report['requests'] = report['requests'][:-2]
        with self.assertRaisesRegex(r.Stop, 'Incomplete packet'):
            r.report_shape(report, self.plan)

    def test_incomplete_pair_cannot_be_marked_complete(self):
        self.interrupt('post_request_conditions_verified')
        report = deepcopy(self.journal.state['report'])
        report['pairs'][0].update(status='completed', conditions_valid_after=True)
        with self.assertRaisesRegex(r.Stop, 'Incomplete pair'):
            r.report_shape(report, self.plan)

    def test_snapshot_change_refused(self):
        self.interrupt('post_request_conditions_verified')
        report = deepcopy(self.journal.state['report'])
        report['pairs'][0]['snapshot']['question'] = 'changed'
        with self.assertRaisesRegex(r.Stop, 'snapshot changed'):
            r.report_shape(report, self.plan)

    def test_graceful_pause_during_request_finishes_saves_and_resumes(self):
        paused = False
        def signal_simulation(reason, state):
            nonlocal paused
            if reason == 'generation_slot_reserved_before_dispatch':
                paused = True
        with self.assertRaises(r.Pause):
            self.run_advance(on_boundary=signal_simulation, should_pause=lambda: paused)
        self.reopen()
        row, = self.journal.state['report']['requests']
        self.assertEqual(row['status'], 'completed')
        self.assertTrue(row['conditions_valid_after'])
        self.assertEqual(self.journal.state['report']['error'], 'operator_pause_between_requests')
        self.assertEqual(self.run_advance()['status'], 'completed')
        self.assertEqual(len(self.native.calls), 14)

    def test_reviewed_model_digest_change_blocks_fresh_dispatch(self):
        with self.assertRaisesRegex(r.Stop, 'Fresh conditions differ'):
            self.run_advance(reviewed_model={'wrong': True})
        self.assertEqual(self.native.calls, [])
        self.assertIsNone(self.journal.state)

    def test_bundle_hashes_native_schema_and_immutable_exports(self):
        self.run_advance()
        a = r.export_bundle(self.root, self.journal)
        before = a.read_bytes(); b = r.export_bundle(self.root, self.journal)
        self.assertNotEqual(a, b); self.assertEqual(a.read_bytes(), before)
        bundle = r.read_json(a)
        self.assertEqual(bundle['schema'], 'day31-evidence-bundle-v1')
        self.assertEqual(len(bundle['files']), 5)
        for entry in bundle['files'].values():
            self.assertEqual(r.sha256((r.canonical(entry['data']) + '\n').encode()).hexdigest(), entry['sha256'])

    def test_error_export_retains_results_without_editing_journal(self):
        self.interrupt('post_request_conditions_verified')
        original = deepcopy(self.journal.state); seq = self.journal.sequence
        bundle = r.read_json(r.export_bundle(self.root, self.journal, 'interrupted'))
        result = next(x['data'] for k, x in bundle['files'].items() if k.endswith('-result.json'))
        self.assertEqual(len(result['requests']), 1)
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(self.journal.state, original); self.assertEqual(self.journal.sequence, seq)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_exclusive_publication_refuses_overwrite(self):
        path = self.root / 'file.json'; r.write_new(path, {'a': 1})
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            r.write_new(path, {'a': 2})
        self.assertEqual(path.read_bytes(), before)

    def test_symlink_file_and_parent_refused(self):
        target = self.root / 'real'; target.mkdir()
        link = self.root / 'link'; link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(r.Stop):
            r.write_new(link / 'out.json', {})

    def test_macos_standard_tmp_var_aliases_are_normalized(self):
        for alias in ['tmp', 'var']:
            for target in ['private/'+alias, '/private/'+alias]:
                with patch.object(r.sys, 'platform', 'darwin'), \
                     patch.object(Path, 'is_symlink', lambda self: str(self) == '/'+alias), \
                     patch.object(r.os, 'readlink', return_value=target):
                    self.assertEqual(r.no_symlinks('/'+alias+'/test'), Path('/private/'+alias+'/test'))

    def test_world_readable_run_directory_refused(self):
        self.root.chmod(0o755)
        with self.assertRaises(r.Stop):
            r.private_dir(self.root)

    def test_hash_chain_tamper_refused(self):
        journal = r.Journal(self.root / 'journal'); journal.save({'a': 1}, 'first'); journal.save({'a': 2}, 'second')
        path = journal.folder / '000001.json'
        value = r.read_json(path); value['state']['a'] = 3; path.write_text(json.dumps(value))
        with self.assertRaisesRegex(r.Stop, 'checksum differs|chain differs'):
            r.Journal(journal.folder)

    def test_missing_journal_event_refused(self):
        journal = r.Journal(self.root / 'journal'); journal.save({}, 'first'); journal.save({}, 'second')
        (journal.folder / '000001.json').unlink()
        with self.assertRaisesRegex(r.Stop, 'gap'):
            r.Journal(journal.folder)

    def test_last_event_checksum_tamper_refused(self):
        journal = r.Journal(self.root / 'journal'); journal.save({'a': 1}, 'first')
        path = journal.folder / '000001.json'; value = r.read_json(path)
        value['state']['a'] = 5; path.write_text(json.dumps(value))
        with self.assertRaisesRegex(r.Stop, 'checksum differs'):
            r.Journal(journal.folder)

    def test_unpublished_temporary_file_is_not_an_event(self):
        journal = r.Journal(self.root / 'journal'); journal.save({}, 'first')
        (journal.folder / '.pending-interrupted-write').write_text('partial')
        self.assertEqual(r.Journal(journal.folder).sequence, 1)

    def test_corrupt_published_file_is_not_ignored(self):
        journal = r.Journal(self.root / 'journal'); journal.save({}, 'first')
        (journal.folder / '000001.json').write_text('{')
        with self.assertRaises(ValueError):
            r.Journal(journal.folder)

    def test_process_lock_excludes_second_coordinator(self):
        path = self.root / 'runner.lock'
        a = os.open(path, os.O_CREAT | os.O_RDWR, 0o600); b = os.open(path, os.O_RDWR)
        try:
            fcntl.flock(a, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                fcntl.flock(b, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(a); os.close(b)


@unittest.skipUnless(os.environ.get('DAY31_TEST_APP'), 'Native adapter integration needs the unchanged app')
class NativeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_compare_and_new_coordinator_use_same_contexts_and_calls(self):
        import sys
        app = Path(os.environ['DAY31_TEST_APP'])
        sys.path[:0] = [str(app), str(app / 'tests')]
        from bublik_developer import paired_research as pr
        from bublik_developer.inference_tasks import InferenceTasks
        from bublik_developer.baseline import BaselineTasks
        from test_paired_research import PairedTests
        fixture = PairedTests('test_bound_and_alternating_order_are_fixed_before_model_access')
        fixture.setUp()
        try:
            native = r.Native.__new__(r.Native)
            native.pr, native.workspace, native.state = pr, fixture.fixture.workspace, fixture.fixture.state
            native.catalog, native.document = fixture.path, fixture.document
            native.freeze = lambda: deepcopy(fixture.frozen)
            snapshot = await fixture.snapshot()
            async def captured(*args): return deepcopy(snapshot)
            native.capture = captured
            contexts = []
            synthetic = fixture.fixture.model_factory()
            async def run(tasks, role, context, *, final=True):
                contexts.append((role.value, deepcopy(context)))
                model = synthetic(tasks.workspace, tasks.request_id, tasks.record, tasks.budget)
                value = await model.run(role, context, final=final)
                tasks.observations.extend(model.observations)
                return value
            baseline = fixture.synthetic_baseline(capture=[])
            async def baseline_run(tasks, role, context, *, final=True):
                contexts.append(('single', deepcopy(context)))
                return await baseline.run(tasks, role, context, final=final)
            with fixture.fixture.controlled_git(), patch.object(InferenceTasks, 'run', new=run), \
                 patch.object(BaselineTasks, 'run', new=baseline_run), \
                 patch.object(pr, 'result_models_match', return_value=True):
                old = await pr.compare(native.workspace, native.state, fixture.frozen, [fixture.case],
                    cases_path=fixture.path, output=fixture.output, max_generation_calls=3, capture=captured)
                old_contexts = deepcopy(contexts); contexts.clear()
                plan = r.make_plan(native, [fixture.case['id']], 3)
                journal = r.Journal(fixture.fixture.parent / 'new-journal')
                new = await r.advance(native, journal, {'packet': 'synthetic'}, plan, fixture.frozen['conditions'])
            self.assertEqual(old['status'], 'completed', old['error'])
            self.assertEqual(new['status'], 'completed')
            self.assertEqual(contexts, old_contexts)
            self.assertEqual(new['generation_slots_reserved'], old['generation_slots_reserved'])
            self.assertEqual(new['summary']['known_llm_calls'], 3)
            self.assertEqual([x['result']['claims'] for x in new['requests']], [x['result']['claims'] for x in old['requests']])
            self.assertEqual([p['order'] for p in new['pairs']], [p['order'] for p in old['pairs']])
        finally:
            # This imported IsolatedAsyncioTestCase is a manually initialized
            # fixture, without its unittest-owned asyncio runner. doCleanups()
            # would record cleanup assertion failures on the *inner* test case
            # instead of closing these resources. Source-pinned setup owns only
            # this patch and this temporary directory.
            try:fixture.metadata.stop()
            finally:fixture.fixture.temp.cleanup()


@unittest.skipUnless(os.environ.get('DAY31_TEST_APP'), 'CLI signal test needs the app for pure catalog planning')
class SignalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def child(self):
        # Synthetic backend only. Keep the real CLI, lock, journal, signal and resume code.
        script = '''
import asyncio,json,os,sys
from pathlib import Path
from types import SimpleNamespace
import runner as r
from test_runner import FakeNative
root=Path(sys.argv[1]); app=Path(os.environ['DAY31_TEST_APP'])
catalog=app/'evaluation/research_quality_regression_v077.json'
class Fake(FakeNative):
 def __init__(self,*args):
  folder=root/'backend';folder.mkdir(exist_ok=True)
  super().__init__(folder)
  self.catalog=catalog;self.document=r.read_json(catalog)
  self.state=SimpleNamespace(path=root/'synthetic-state')
 async def execute(self,*args):
  before=len(self.calls);result=await super().execute(*args)
  with (root/'calls.jsonl').open('a') as f:
   for value in self.calls[before:]:f.write(json.dumps(value)+'\\n')
   f.flush();os.fsync(f.fileno())
  print('SYNTHETIC_REQUEST_RUNNING',flush=True)
  await asyncio.sleep(0.2)
  return result
r.Native=Fake
r.checked_package=lambda:'synthetic-package'
r.checked_environment=lambda *args:(app,catalog,{'conditions':{'fixture':True},'model':{'transport':'synthetic'}})
r.subprocess.run=lambda *args,**kwargs:SimpleNamespace(returncode=0)
sys.argv=['runner.py','run','--root',str(root),'--packet','batch1','--run-dir',str(root.parent/(root.name+'-runs'))]
raise SystemExit(r.main())
'''
        process = subprocess.Popen([sys.executable, '-c', script, str(self.root)],
            cwd=Path(__file__).parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        return process

    def wait_request(self, process):
        if not select.select([process.stdout], [], [], 10)[0]:
            process.kill(); process.communicate(timeout=5)
            self.fail('Synthetic child did not reach the request boundary in time')
        self.assertEqual(process.stdout.readline().strip(), 'SYNTHETIC_REQUEST_RUNNING')

    def test_real_sigint_finishes_request_then_same_cli_resumes_without_duplicate(self):
        process = self.child(); self.wait_request(process); process.send_signal(signal.SIGINT)
        out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 130, (out, err))
        self.assertIn('"status": "paused"', err)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)
        second = self.child(); out, err = second.communicate(timeout=15)
        self.assertEqual(second.returncode, 0, (out, err))
        calls = [json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls), 14)
        self.assertEqual(calls.count(['receipt-ru','single']), 1)
        run = self.root.parent/(self.root.name+'-runs')
        try:
            self.assertEqual(len(list((run/'batch1/exports').glob('bundle-*.json'))), 2)
        finally:
            import shutil
            shutil.rmtree(run)

    def test_second_sigint_forces_stop_then_resume_refuses_inflight(self):
        process = self.child(); self.wait_request(process)
        process.send_signal(signal.SIGINT); time.sleep(0.03); process.send_signal(signal.SIGINT)
        out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 2, (out, err))
        second = self.child(); out, err = second.communicate(timeout=15)
        self.assertEqual(second.returncode, 2, (out, err))
        self.assertIn('in-flight', err)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)
        import shutil
        shutil.rmtree(self.root.parent/(self.root.name+'-runs'))


if __name__ == '__main__':
    unittest.main()
