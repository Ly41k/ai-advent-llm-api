#!/usr/bin/env python3
"""Append-only continuation of the unchanged Day31 v098 paired experiment."""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
VERSION = 'v098-runner-r1'
PACKETS = {
    'batch1': ['receipt-ru', 'receipt-en', 'assistant-facts-ru', 'assistant-facts-en',
               'dense-private-branch-ru', 'dense-private-branch-en'],
    'batch2': ['quote-language-ru', 'quote-language-en', 'path-limit-branch-ru',
               'path-limit-branch-en', 'paraphrase-ru', 'paraphrase-en'],
}


class Stop(RuntimeError):
    pass


class Pause(Stop):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def no_symlinks(path):
    path = Path(path).absolute()
    # macOS exposes these two system aliases; normalize only their exact OS targets.
    if sys.platform == 'darwin' and len(path.parts) > 1 and path.parts[1] in {'tmp', 'var'}:
        alias = Path('/') / path.parts[1]
        if alias.is_symlink() and os.readlink(alias) in {'/private/' + path.parts[1], 'private/' + path.parts[1]}:
            path = Path('/private').joinpath(*path.parts[1:])
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise Stop('Symlink path refused: ' + str(path))
    return path


def read_json(path):
    path = no_symlinks(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r', encoding='utf-8') as stream:
        return json.load(stream)


def private_dir(path):
    path = no_symlinks(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise Stop('Run directory must be owned by this user and mode 0700.')
    return path


def write_new(path, value):
    """Atomic, durable, exclusive publication; never replace an artifact."""
    path = no_symlinks(path)
    fd, temp = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(canonical(value) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path, follow_symlinks=False)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temp).unlink(missing_ok=True)


class Journal:
    def __init__(self, folder):
        self.folder = private_dir(folder)
        self.sequence, self.tip, self.state = 0, None, None
        entries = sorted(self.folder.glob('*.json'))
        for sequence, path in enumerate(entries, 1):
            if path.name != f'{sequence:06d}.json':
                raise Stop('Journal gap or unexpected file; no model dispatch.')
            event = read_json(path)
            if (event.get('schema') != 'day31-regression-journal-v1'
                    or event.get('sequence') != sequence or event.get('previous_sha256') != self.tip):
                raise Stop('Journal chain differs; no model dispatch.')
            unsigned = {k: v for k, v in event.items() if k != 'event_sha256'}
            if event.get('event_sha256') != digest(unsigned):
                raise Stop('Journal event checksum differs; no model dispatch.')
            self.sequence, self.tip, self.state = sequence, digest(event), event['state']

    def save(self, state, reason):
        event = {'schema': 'day31-regression-journal-v1', 'sequence': self.sequence + 1,
                 'previous_sha256': self.tip, 'created_at': utc(), 'reason': reason,
                 'state': deepcopy(state)}
        event['event_sha256'] = digest(event)
        write_new(self.folder / f'{event["sequence"]:06d}.json', event)
        self.sequence, self.tip, self.state = event['sequence'], digest(event), deepcopy(state)


def checked_package():
    manifest = read_json(HERE / 'manifest.json')
    for name, expected in manifest['files_sha256'].items():
        if '/' in name or '\\' in name or name.startswith('.'):
            raise Stop('Invalid package manifest.')
        path = no_symlinks(HERE / name)
        if sha256(path.read_bytes()).hexdigest() != expected:
            raise Stop('Runner package differs: ' + name)
    return digest(manifest)


def checked_environment(root, evidence_dir):
    """Read only, before model/session access; pin all 10 completed questions."""
    app = no_symlinks(root / 'day-31-developer-assistant')
    reviewed = read_json(HERE / 'reviewed_v098.json')
    actual = {p.relative_to(app).as_posix(): sha256(no_symlinks(p).read_bytes()).hexdigest()
              for p in sorted(app.rglob('*.py')) if not {'.venv', '__pycache__'}.intersection(p.parts)}
    pre = read_json(evidence_dir / 'day31-stage7-preflight-mac-v098.json')
    if (len(actual) != 59 or actual != reviewed['conditions']['source_sha256']
            or actual != pre.get('source_sha256') or pre.get('status') != 'passed'
            or pre.get('tests_run') != 262 or pre.get('version') != '0.7.28'):
        raise Stop('Source/native preflight differs; no model dispatch.')
    catalog = no_symlinks(app / 'evaluation/research_quality_regression_v077.json')
    if sha256(catalog.read_bytes()).hexdigest() != reviewed['conditions']['cases_sha256']:
        raise Stop('Catalog differs; no model dispatch.')
    seen = set()
    for receipt in reviewed['completed_reports']:
        path = no_symlinks(evidence_dir / receipt['file'])
        if sha256(path.read_bytes()).hexdigest() != receipt['sha256']:
            raise Stop('Completed native report differs: ' + receipt['file'])
        report = read_json(path)
        if (report['status'] != 'completed' or report['error'] is not None
                or report['frozen_conditions']['conditions'] != reviewed['conditions']
                or report['planned_case_ids'] != receipt['case_ids']):
            raise Stop('Invalid prior completion receipt.')
        for case_id in receipt['case_ids']:
            rows = [r for r in report['requests'] if r['case_id'] == case_id]
            if (case_id in seen or len(rows) != 2 or {r['mode'] for r in rows} != {'single', 'multi'}
                    or any(r['status'] != 'completed' or not r['conditions_valid_after']
                           or r['result']['execution_status'] != 'completed' for r in rows)):
                raise Stop('Duplicate or unfinished prior case.')
            seen.add(case_id)
    if seen != set(reviewed['completed_case_ids']) or len(seen) != 10:
        raise Stop('Prior case coverage differs.')
    remaining = [c for c in read_json(catalog)['cases'] if c['id'] not in seen]
    if {c['id'] for c in remaining} != {x for ids in PACKETS.values() for x in ids}:
        raise Stop('Remaining case partition differs.')
    return app, catalog, reviewed


class Native:
    """Use original capture, model factories, pipeline, checks and accounting."""
    def __init__(self, app, root, state_dir, catalog):
        sys.path.insert(0, str(app))
        from bublik_developer import paired_research as pr
        from bublik_developer.workspace import ProjectWorkspace
        from bublik_developer.rag.state import ProjectState
        self.pr = pr
        self.workspace = ProjectWorkspace.open(root, 'ai-advent-llm-api')
        self.state = ProjectState(self.workspace, state_dir)
        self.catalog = catalog
        self.document, _ = pr.load_cases(catalog)

    def bound(self, cases):
        return self.pr.paired_bound(cases, 1)

    def order(self, position):
        return self.pr.pair_order(position, 0)

    def plan_labels(self, cases_digest):
        return {'catalog_design': self.pr.catalog_design(self.document, cases_digest),
                'scope': self.pr.comparison_spec(self.document, cases_digest)['scope']}

    def freeze(self):
        return self.pr.paired_freeze(self.workspace, self.state, cases_path=self.catalog)

    def validate(self, frozen):
        self.pr.validate_paired_freeze(frozen, self.workspace, self.state, self.catalog)

    def inspect(self):
        return self.pr.inspect_model(self.workspace)

    def index_verify(self):
        from bublik_developer.rag.corpus import ProjectCorpus
        from bublik_developer.rag.index import ProjectIndex
        with ProjectIndex.current(self.state, ProjectCorpus(self.workspace)) as index:
            return index.verify()

    async def capture(self, case):
        return await self.pr.capture_snapshot(self.workspace, self.state, case)

    def slots(self, cap):
        return self.pr.GenerationSlots(cap)

    async def execute(self, case, mode, snapshot, slots):
        factory = (self.pr.single_inference(slots, snapshot) if mode == 'single'
                   else self.pr.limited_inference(slots))
        return await self.pr.SnapshotPipeline(self.workspace, state_dir=self.state.path,
            language=case['language'], mode='fts', snapshot=snapshot,
            inference_factory=factory).run(case['question'])

    def checks(self, case, result):
        return self.pr.structural_outcome(case, result)

    def result_ok(self, result, frozen):
        return (self.pr.result_models_match(result, frozen['model'])
                and not self.pr.technical_failure(result)
                and result.get('execution_status') == 'completed'
                and result.get('metrics', {}).get('unknown_inference_attempts', 0) == 0)

    def summarize(self, report):
        value = self.pr.summarize(report)
        value.update(pairs_completed=sum(p['status'] == 'completed' for p in report['pairs']),
            single_multi_comparison='snapshot_smoke_only', semantic_acceptance='not_evaluated',
            embedding_calls=0,
            common_preparation_seconds=sum(p['snapshot']['common_preparation_seconds'] for p in report['pairs']),
            actual_common_capability_calls=sum(p['snapshot']['observation']['metrics']['capability_calls'] for p in report['pairs']))
        return value


def make_plan(native, ids, cap):
    by_id = {c['id']: c for c in native.document['cases']}
    if not 1 <= len(ids) <= 6 or len(ids) != len(set(ids)) or any(i not in by_id for i in ids):
        raise Stop('A packet must contain 1..6 distinct catalog questions.')
    cases = [by_id[i] for i in ids]
    bound = native.bound(cases)
    if type(cap) is not int or not bound <= cap <= 32:
        raise Stop(f'Packet requires {bound} generation slots, cap must be {bound}..32.')
    positions = {c['id']: i for i, c in enumerate(native.document['cases'])}
    cases_digest = sha256(native.catalog.read_bytes()).hexdigest()
    return {'case_ids': ids, 'pairs': len(ids), 'request_observations': 2 * len(ids),
            'generation_upper_bound': bound, 'max_generation_calls': cap,
            'planned_orders': [{'case_id': i, 'repeat': 1, 'catalog_position': positions[i],
                                'order': native.order(positions[i])} for i in ids],
            'cases_sha256': cases_digest, 'embedding_calls': 0, 'inference_performed': False,
            **native.plan_labels(cases_digest)}


def report_shape(report, plan):
    """Fail closed before resume; no missing/duplicate mode or case prefix."""
    if report['planned_case_ids'] != plan['case_ids'] or report['generation_cap'] != plan['max_generation_calls']:
        raise Stop('Run plan differs; use the original packet and cap.')
    pairs = report['pairs']
    if [p['case_id'] for p in pairs] != plan['case_ids'][:len(pairs)]:
        raise Stop('Invalid case prefix.')
    if len(pairs) > len(plan['case_ids']):
        raise Stop('Too many pairs.')
    expected_rows = []
    for i, pair in enumerate(pairs):
        planned = plan['planned_orders'][i]
        if (pair['pair_id'] != i + 1 or pair['order'] != planned['order']
                or pair['catalog_position'] != planned['catalog_position'] or pair['repeat'] != 1
                or digest(pair['snapshot']) != pair['snapshot_digest']):
            raise Stop('Pair identity, order or snapshot changed.')
        expected_rows.extend((i + 1, pair['case_id'], mode) for mode in pair['order'])
        if i < len(pairs) - 1 and pair['status'] != 'completed':
            raise Stop('An earlier pair is incomplete.')
    actual = [(r['pair_id'], r['case_id'], r['mode']) for r in report['requests']]
    if actual != expected_rows[:len(actual)] or len(actual) > len(expected_rows):
        raise Stop('Duplicate/out-of-order request.')
    for row in report['requests']:
        if row['status'] == 'started' or 'result' not in row:
            raise Stop('Unresolved in-flight request: no automatic replay. Export bundle for review.')
        if row['result'].get('snapshot_digest') != pairs[row['pair_id'] - 1]['snapshot_digest']:
            raise Stop('Result snapshot differs.')
    for pair in pairs:
        rows = [r for r in report['requests'] if r['pair_id'] == pair['pair_id']]
        if pair['status'] == 'completed' and (len(rows) != 2 or not pair['conditions_valid_after']
                or any(not r['conditions_valid_after'] for r in rows)):
            raise Stop('Incomplete pair marked completed.')
    if report['status'] == 'completed' and (len(pairs) != len(plan['case_ids'])
            or any(p['status'] != 'completed' for p in pairs)):
        raise Stop('Incomplete packet marked completed.')


async def advance(native, journal, config, plan, reviewed_conditions, *, on_boundary=None,
                  should_pause=lambda: False, reviewed_model=None):
    """Exactly one sequential pipeline per request; durable result before validation."""
    if journal.state is None:
        frozen = native.freeze()
        if (frozen['conditions'] != reviewed_conditions
                or reviewed_model is not None and frozen['model'] != reviewed_model):
            raise Stop('Fresh conditions differ from reviewed v098; no generation.')
        state = {'config': config, 'plan': plan, 'index_verify': native.index_verify(),
                 'report': {'format': 'bublik-paired-snapshot-v1', 'version': '0.7.29',
                 'status': 'running', 'created_at': utc(), 'frozen_conditions': frozen,
                 'freeze_sha256': digest(frozen), 'comparison_spec': deepcopy(frozen['comparison_spec']),
                 'catalog_design': deepcopy(frozen['catalog_design']), 'planned_case_ids': plan['case_ids'],
                 'repeats': 1, 'planned_generation_upper_bound': plan['generation_upper_bound'],
                 'generation_cap': plan['max_generation_calls'], 'generation_slots_reserved': 0,
                 'pairs': [], 'requests': [], 'metadata_checks': [], 'error': None}}
        journal.save(state, 'fresh_freeze_no_generation')
    state = deepcopy(journal.state)
    if state['config'] != config or state['plan'] != plan:
        raise Stop('Run identity differs; no model dispatch.')
    report = state['report']; frozen = report['frozen_conditions']
    if (digest(frozen) != report['freeze_sha256'] or frozen['conditions'] != reviewed_conditions
            or reviewed_model is not None and frozen['model'] != reviewed_model):
        raise Stop('Frozen identity differs.')
    report_shape(report, plan)
    # A failure is retained, not silently repaired into PASS.
    if any(not native.result_ok(r['result'], frozen) for r in report['requests']):
        raise Stop('A recorded technical/uncertain result needs review; no retry.')
    if report['status'] == 'completed':
        return report
    native.validate(frozen)
    observed = native.inspect()
    if observed['model'] != frozen['model']:
        raise Stop('Model changed; no generation.')
    slots = native.slots(plan['max_generation_calls'])
    slots.used = report['generation_slots_reserved']
    if not 0 <= slots.used <= slots.limit:
        raise Stop('Invalid reserved generation budget.')

    def save(reason):
        report['generation_slots_reserved'] = slots.used
        report['summary'] = native.summarize(report)
        journal.save(state, reason)
        if on_boundary:
            on_boundary(reason, deepcopy(state))

    slots.on_reserve = lambda: save('generation_slot_reserved_before_dispatch')
    def pause_if_requested():
        if should_pause():
            report.update(status='stopped', error='operator_pause_between_requests')
            save('operator_pause_between_requests_no_inflight_request')
            raise Pause('Paused safely between requests; repeat the same command to continue.')

    report.update(status='running', error=None)
    save('continue_without_replaying_completed_requests')
    cases = {c['id']: c for c in native.document['cases']}
    for item in plan['planned_orders']:
        pause_if_requested()
        case = cases[item['case_id']]
        pair = next((p for p in report['pairs'] if p['case_id'] == case['id']), None)
        if pair and pair['status'] == 'completed':
            continue
        if pair is None:
            native.validate(frozen)
            observed = native.inspect()
            if observed['model'] != frozen['model']:
                raise Stop('Model changed; no generation.')
            report['metadata_checks'].append({'case_id': case['id'], 'repeat': 1, **observed})
            save('metadata_only_before_acquisition')
            snapshot = await native.capture(case)
            pair = {'pair_id': len(report['pairs']) + 1, 'case_id': case['id'], 'repeat': 1,
                    'catalog_position': item['catalog_position'], 'order': item['order'],
                    'snapshot_digest': digest(snapshot), 'snapshot': snapshot,
                    'status': 'running', 'conditions_valid_after': False}
            report['pairs'].append(pair)
            save('shared_snapshot_acquired_no_generation')
        if pair['snapshot']['observation']['status'] != 'completed':
            raise Stop('Common acquisition failed; retained for review.')
        for mode in pair['order']:
            pause_if_requested()
            row = next((r for r in report['requests'] if r['pair_id'] == pair['pair_id'] and r['mode'] == mode), None)
            if row is None:
                native.validate(frozen)
                row = {'pair_id': pair['pair_id'], 'case_id': case['id'], 'mode': mode, 'repeat': 1,
                       'status': 'started', 'conditions_valid_after': False,
                       'generation_slots_before': slots.used}
                report['requests'].append(row)
                save('request_started_no_automatic_replay_if_interrupted')
                result = await native.execute(case, mode, pair['snapshot'], slots)
                row.update(status='completed', result=result, structural_checks=native.checks(case, result))
                save('terminal_request_result_saved')
            if row['result'].get('snapshot_digest') != pair['snapshot_digest']:
                raise Stop('Result snapshot mismatch.')
            if not native.result_ok(row['result'], frozen):
                report.update(status='stopped', error='technical_request_failure')
                save('technical_failure_preserved_no_retry')
                return report
            if not row['conditions_valid_after']:
                native.validate(frozen)
                row['conditions_valid_after'] = True
                save('post_request_conditions_verified')
        pair.update(status='completed', conditions_valid_after=True)
        save('question_completed_and_saved')
    report.update(status='completed', error=None)
    save('packet_completed_semantic_review_pending')
    return report


def export_bundle(folder, journal, error=None):
    if not journal.state:
        return None
    state = deepcopy(journal.state); report = state['report']
    if error:
        report.update(status='stopped', error=str(error))
    if 'summary' not in report:
        report['summary'] = {'semantic_acceptance': 'not_evaluated'}
    packet = state['config']['packet']
    prefix = f'day31-paired-{packet}-mac-v098'
    values = {'index-verify': state['index_verify'], 'plan': state['plan'],
              'freeze': report['frozen_conditions'], 'result': report,
              'runner': {'version': VERSION, 'config': state['config'], 'journal_events': journal.sequence,
                         'journal_tip_sha256': journal.tip, 'exported_at': utc(),
                         'scope': 'Original v098 paired snapshot semantics; append-only coordinator. No semantic acceptance.'}}
    bundle = {'schema': 'day31-evidence-bundle-v1', 'files': {}}
    for name, value in values.items():
        raw = (canonical(value) + '\n').encode()
        bundle['files'][prefix + '-' + name + '.json'] = {'sha256': sha256(raw).hexdigest(), 'data': value}
    exports = private_dir(folder / 'exports')
    number = len(list(exports.glob('bundle-*.json'))) + 1
    path = exports / f'bundle-{number:04d}.json'
    write_new(path, bundle)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['plan', 'run', 'export'])
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--packet', choices=list(PACKETS), required=True)
    parser.add_argument('--max-generation-calls', type=int, default=14)
    parser.add_argument('--run-dir', type=Path, default=Path('/tmp/day31-regression-v098-r1-runs'))
    parser.add_argument('--evidence-dir', type=Path, default=Path('/tmp'))
    parser.add_argument('--state-dir', type=Path)
    args = parser.parse_args()
    journal = None; folder = None; lock = None
    try:
        package_digest = checked_package()
        root = no_symlinks(args.root).resolve()
        folder = no_symlinks(args.run_dir).absolute()
        if folder.resolve().is_relative_to(root):
            raise Stop('Run artifacts must be outside the repository.')
        folder = private_dir(folder)
        args.run_dir = folder
        lock = os.open(folder / 'runner.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop('Another coordinator is active; no model dispatch.') from None
        folder = private_dir(folder / args.packet)
        journal = Journal(folder / 'journal')
        if args.operation == 'export':
            path = export_bundle(folder, journal)
            print(json.dumps({'bundle': str(path) if path else None, 'inference_performed': False}))
            return 0 if path else 2
        app, catalog, reviewed = checked_environment(root, no_symlinks(args.evidence_dir))
        sys.path.insert(0, str(app))
        # Plan uses pure catalog routing, without opening a workspace or model lease.
        from bublik_developer import paired_research as pr
        pure = type('PurePlan', (), {'document': read_json(catalog), 'catalog': catalog,
            'bound': staticmethod(pr.paired_bound), 'order': staticmethod(pr.pair_order),
            'plan_labels': lambda self, d: {'catalog_design': pr.catalog_design(self.document, d),
                'scope': pr.comparison_spec(self.document, d)['scope']}})()
        plan = make_plan(pure, PACKETS[args.packet], args.max_generation_calls)
        if args.operation == 'plan':
            print(json.dumps({'already_checked_questions': 10, **plan}, indent=2))
            return 0
        # A partial request in either packet blocks starting a different packet too.
        for packet in PACKETS:
            other_dir = args.run_dir / packet / 'journal'
            if other_dir.exists():
                other = Journal(other_dir)
                if other.state:
                    report_shape(other.state['report'], other.state['plan'])
                    if packet != args.packet and other.state['report']['status'] != 'completed':
                        raise Stop('Finish/review the earlier packet before starting another.')
        tests = subprocess.run([sys.executable, str(HERE / 'test_runner.py'), '-q'], check=False,
            env={**os.environ, 'DAY31_TEST_APP': str(app)})
        if tests.returncode:
            raise Stop('Runner offline self-checks failed; no model dispatch.')
        native = Native(app, root, args.state_dir, catalog)
        config = {'runner_version': VERSION, 'package_sha256': package_digest, 'root': str(root),
                  'state_dir': str(native.state.path), 'packet': args.packet,
                  'reviewed_coverage_sha256': digest(reviewed)}
        paused = False
        def interrupt(signum, frame):
            nonlocal paused
            if paused:
                raise KeyboardInterrupt('Forced interruption; in-flight requests will not be replayed.')
            paused = True
            print('Pause requested: finishing and saving the current request. A second Ctrl+C forces interruption.', file=sys.stderr, flush=True)
        previous_signal = signal.signal(signal.SIGINT, interrupt)
        try:
            report = asyncio.run(advance(native, journal, config, plan, reviewed['conditions'],
                should_pause=lambda: paused, reviewed_model=reviewed['model']))
        finally:
            signal.signal(signal.SIGINT, previous_signal)
        path = export_bundle(folder, journal)
        print(json.dumps({'status': report['status'], 'summary': report['summary'], 'bundle': str(path)}, indent=2))
        return 0 if report['status'] == 'completed' else 2
    except (Exception, KeyboardInterrupt) as error:
        path = None
        if journal and folder:
            try:
                path = export_bundle(folder, journal, error)
            except Exception:
                pass
        print(json.dumps({'status': 'paused' if isinstance(error, Pause) else 'stopped', 'error': str(error) or type(error).__name__,
                          'bundle': str(path) if path else None, 'automatic_retry': False}), file=sys.stderr)
        return 130 if isinstance(error, Pause) else 2
    finally:
        if lock is not None:
            os.close(lock)


if __name__ == '__main__':
    raise SystemExit(main())
