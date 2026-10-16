#!/usr/bin/env python3
"""Targeted exact-source-anchor schema experiment on RU-1 and EN-3; four bounded calls."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import runner as core

HERE=Path(__file__).resolve().parent
VERSION='source-anchor-v103-r1'
PREPARATION=Path('/tmp/day31-independent-v098-r1-work/preparation-bundle.json')


def package_check():
    manifest=core.read_json(HERE/'manifest.json')
    for name,expected in manifest['files_sha256'].items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or any(x.startswith('.') for x in rel.parts):
            raise core.Stop('Invalid package file name.')
        if sha256(core.no_symlinks(HERE/name).read_bytes()).hexdigest()!=expected:
            raise core.Stop('Execution package differs: '+name)
    return core.digest(manifest)


def load_preparation(path=PREPARATION):
    raw=core.no_symlinks(path).read_bytes();pin=core.read_json(HERE/'preparation_pin.json')
    if sha256(raw).hexdigest()!=pin['bundle_sha256']:
        raise core.Stop('Original preparation bytes differ; no dispatch.')
    bundle=json.loads(raw)
    if bundle.get('schema')!='day31-evidence-bundle-v1' or bundle['preparation_status']['status']!='prepared_no_inference':
        raise core.Stop('Preparation is not admitted.')
    if {n:e['sha256'] for n,e in bundle['files'].items()}!=pin['report_hashes']:
        raise core.Stop('Preparation report set differs.')
    for name,entry in bundle['files'].items():
        if sha256((core.canonical(entry['data'])+'\n').encode()).hexdigest()!=entry['sha256']:
            raise core.Stop('Preparation report digest differs: '+name)
    read=lambda label:bundle['files']['day31-independent-v098-r1-'+label+'.json']['data']
    frozen=read('freeze')
    for field,name in [('questions_sha256','questions.frozen.json'),('cases_sha256','cases.frozen.json'),
                       ('criteria_sha256','criteria.frozen.json'),('source_pins_sha256','source_pins.json')]:
        if frozen[field]!=sha256((HERE/name).read_bytes()).hexdigest():
            raise core.Stop('Frozen question/criteria/source data differs: '+name)
    document=core.read_json(HERE/'regression.cases.json')
    rows=read('expanded54-retrieval')['requests']
    if [r['case_id'] for r in rows]!=[c['id'] for c in document['cases']]:
        raise core.Stop('Prepared question order differs.')
    for case,row in zip(document['cases'],rows):
        snapshot=row['snapshot']
        if (core.digest(snapshot)!=row['snapshot_digest'] or snapshot['question']!=case['question']
                or snapshot['language']!=case['language'] or snapshot['observation']['status']!='completed'):
            raise core.Stop('Prepared snapshot differs.')
        for mode in row['preview']['modes']:
            budget=mode['context_budget']
            # Do not trust r1 diagnostic label "fits": the actual numerical condition is authoritative.
            if budget['estimated_total']>budget['context_window']:
                raise core.Stop('Prepared expanded54 context exceeds its original budget.')
    document=core.read_json(HERE/'regression.cases.json')
    return bundle,frozen,document,{r['case_id']:r for r in rows}


class IndependentNative(core.Native):
    """Explicit research corpus; same original pipeline/model factories/validators."""
    def __init__(self,root,preparation,frozen,document,snapshots):
        self.preparation,self.prepared,self.snapshots=preparation,frozen,snapshots
        self.reference=core.read_json(HERE/'baseline.v099.json')
        app=core.no_symlinks(root/'day-31-developer-assistant')
        self.verify_source(app)
        super().__init__(app,root,core.no_symlinks(frozen['isolated_state_dir']),HERE/'regression.cases.json')
        if self.document!=document:
            raise core.Stop('Catalog differs.')
        from bublik_developer.rag.corpus import ProjectCorpus,SourceSpec
        from bublik_developer.rag.state import ProjectState
        selection=preparation['files']['day31-independent-v098-r1-selection.json']['data']
        self.corpus=ProjectCorpus(self.workspace,[SourceSpec(**s) for s in selection['sources']])
        self.production_state=ProjectState(self.workspace)
        if self.state.path.resolve()==self.production_state.path.resolve():
            raise core.Stop('Research state must not be production state.')
        self.conditions()  # Pure source/index/Git checks; no model metadata or generation.
        self.check_previews()

    def verify_source(self,app):
        binding=core.read_json(HERE/'source-binding.json')
        actual={p.relative_to(app).as_posix():sha256(core.no_symlinks(p).read_bytes()).hexdigest()
                for p in sorted(app.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
        pre=core.read_json('/tmp/day31-stage7-v099-work/native-preflight.json')
        if (len(actual)!=60 or actual!=binding['source_sha256'] or actual!=self.reference['conditions']['source_sha256']
                or core.digest(pre)!=binding['native_preflight_digest'] or pre.get('status')!='passed'
                or pre.get('tests_run')!=276 or pre.get('version')!='0.7.29'
                or sha256((app/'requirements.lock').read_bytes()).hexdigest()!=binding['requirements_sha256']):
            raise core.Stop('Reviewed v099/native276 required; no dispatch.')

    def check_previews(self):
        from prompt_profile import previews
        expected=core.read_json(HERE/'expected-contexts.json')
        selected=core.read_json(HERE/'expected-selection.json')
        rows=[]
        for case in self.document['cases']:rows.extend(previews(case,selected[case['id']]['sources']))
        if rows!=expected or any(r['status']!='fits' for r in rows):raise core.Stop('Frozen regression contexts differ.')

    def index_verify(self):
        from bublik_developer.rag.index import ProjectIndex
        with ProjectIndex.current(self.state,self.corpus) as index:
            report=index.verify()
        if report['index']!=self.prepared['isolated_index']:
            raise core.Stop('Prepared research index differs; no rebuild.')
        return report

    def conditions(self):
        from bublik_developer.rag.corpus import ProjectCorpus
        from bublik_developer.rag.index import ProjectIndex
        from bublik_developer import __version__
        self.verify_source(self.workspace.root/'day-31-developer-assistant')
        current=self.production_state.path/'CURRENT.json'
        if sha256(current.read_bytes()).hexdigest()!=self.prepared['production_CURRENT_sha256_before']:
            raise core.Stop('Production CURRENT changed.')
        with ProjectIndex.current(self.production_state,ProjectCorpus(self.workspace)) as index:
            if index.verify()['index']!=self.prepared['production_index']:
                raise core.Stop('Production corpus/index changed.')
        meta=self.index_verify()['index']
        if self.corpus.collect().manifest()!=self.prepared['source_manifest']:
            raise core.Stop('Prepared source manifest changed.')
        _,head=self.workspace.command('rev-parse','--verify','HEAD')
        code,branch=self.workspace.command('symbolic-ref','--quiet','--short','HEAD',allowed_codes=(0,1))
        head=head.decode().strip();branch=branch.decode().strip() if code==0 else None
        base=self.reference['conditions']
        if head!=base['git_head'] or branch!=base['git_branch'] or __version__!='0.7.29':
            raise core.Stop('Git/version conditions changed.')
        # Installed v099 is unchanged. External prompt/schema/renderer are pinned
        # separately; selected quotes and model/options match the reviewed run.
        return {**deepcopy(base),'version':__version__,'index':meta,
                'cases_sha256':sha256(self.catalog.read_bytes()).hexdigest(),
                'prompt_version':__import__('prompt_profile').DOC_VERSION}

    def binding(self):
        return {'preparation_bundle_sha256':core.read_json(HERE/'preparation_pin.json')['bundle_sha256'],
                'preparation_freeze_digest':core.digest(self.prepared),
                'question_sha256':self.prepared['questions_sha256'],
                'criteria_sha256':self.prepared['criteria_sha256'],
                'selection_sha256':self.prepared['selection_sha256'],
                'source_scope':'explicit expanded54; existing production44 is not replaced',
                'acquisition':'Fresh owned FTS/Verification workers using one explicitly frozen external research selector; same snapshot shared per Single/Multi pair',
                'selection_policy_sha256':sha256((HERE/'selection-policy.frozen.json').read_bytes()).hexdigest(),
                'expected_contexts_sha256':sha256((HERE/'expected-contexts.json').read_bytes()).hexdigest(),
                'expected_selection_sha256':sha256((HERE/'expected-selection.json').read_bytes()).hexdigest(),
                'new_regression_not_original_replacement':True,
                'prompt_profile_sha256':sha256((HERE/'prompt_profile.py').read_bytes()).hexdigest(),
                'reviewed_prior_receipt_sha256':core.read_json(HERE/'reviewed-prior-receipt.json')['sha256'],
                'source_anchor_representation_trial':True,'task_selection_sha256':sha256((HERE/'task-selection.frozen.json').read_bytes()).hexdigest()}

    def experiment_spec(self,digest):
        import prompt_profile as profile
        value=self.pr.comparison_spec(self.document,digest)
        value.update(version='paired-snapshot-source-anchor-v103',baseline=profile.SINGLE_VERSION,
                     scope='Known-question exact-source-anchor schema experiment; identical evidence/model/options; original guards validate text against exact selected anchor and then original evidence; not held-out or E2E.')
        return value

    def plan_labels(self,digest):
        return {'catalog_design':self.pr.catalog_design(self.document,digest),'scope':self.experiment_spec(digest)['scope']}

    def freeze(self):
        conditions=self.conditions();observed=self.inspect()
        if observed['model']!=self.prepared['intended_model']:
            raise core.Stop('Model differs from originally frozen Qwen digest.')
        digest=conditions['cases_sha256']
        return {'format':'bublik-research-freeze-v1','created_at':core.utc(),'conditions':conditions,
                'model':observed['model'],'metadata_http_events':observed['metadata_http_events'],
                'generation_calls':0,'embedding_calls':0,'scope':'Controlled exact-source-anchor representation trial; same research54 evidence/selector/model/options; original validators retained; anchor exactness/source boundaries additionally enforced; not held-out or E2E',
                'comparison_spec':self.experiment_spec(digest),
                'catalog_design':self.pr.catalog_design(self.document,digest),
                'independent_preparation_binding':self.binding()}

    def validate(self,frozen):
        conditions=self.conditions();digest=conditions['cases_sha256']
        if (frozen['format']!='bublik-research-freeze-v1' or frozen['conditions']!=conditions
                or frozen['model']!=self.prepared['intended_model']
                or frozen['comparison_spec']!=self.experiment_spec(digest)
                or frozen['catalog_design']!=self.pr.catalog_design(self.document,digest)
                or frozen['independent_preparation_binding']!=self.binding()):
            raise core.Stop('Frozen conditions differ; no dispatch.')

    async def capture(self,case):
        import bublik_developer.agent_runtime as runtime
        from bublik_developer.routing import route
        from prompt_profile import previews
        original=runtime.run_owned
        async def owned(argv,encoded,**kwargs):
            payload=json.loads(encoded)
            if payload.get('role')=='documentation':
                if argv!=[sys.executable,'-m','bublik_developer.agent_worker']:raise core.Stop('Unexpected acquisition worker.')
                argv=[sys.executable,str(HERE/'retrieval_worker.py')]
            return await original(argv,encoded,**kwargs)
        class NoInference:
            def __init__(self,*args):self.observations=[]
            async def run(self,*args,**kwargs):raise core.Stop('No inference in acquisition.')
        from time import perf_counter
        pipeline=self.pr.CapturePipeline(self.workspace,state_dir=self.state.path,corpus=self.corpus,
            language=case['language'],mode='fts',inference_factory=NoInference)
        pipeline.budget.deadline=pipeline.started+300
        from unittest.mock import patch
        try:
            with patch.object(runtime,'run_owned',owned):
                async with asyncio.timeout(300):await pipeline._run(route(case['question']),case['question'])
        except self.pr.SnapshotReady:pass
        else:raise core.Stop('Capture boundary missing.')
        sources=next((m['data']['sources'] for m in pipeline.snapshot_observed['merged'] if m['role']=='documentation'),None)
        if sources!=core.read_json(HERE/'expected-selection.json')[case['id']]['sources']:
            raise core.Stop('Fresh worker evidence differs from reviewed selection.')
        current=previews(case,sources)
        expected=[p for p in core.read_json(HERE/'expected-contexts.json') if p['case_id']==case['id']]
        if current!=expected:raise core.Stop('Fresh role contexts differ.')
        return {'signature':self.pr.signature(pipeline.snapshot_jobs),'observation':pipeline.snapshot_observed,
            'question':case['question'],'language':case['language'],'common_preparation_seconds':perf_counter()-pipeline.started}

    async def execute(self,case,mode,snapshot,slots):
        import bublik_developer.inference_tasks as tasks
        original=tasks.run_owned
        async def owned(argv,encoded,**kwargs):
            modes={'bublik_developer.model_worker':'multi','bublik_developer.baseline_worker':'single'}
            if len(argv)!=3 or argv[:2]!=[sys.executable,'-m'] or argv[2] not in modes:raise core.Stop('Unexpected model worker.')
            return await original([sys.executable,str(HERE/'capture_worker.py'),'--mode',modes[argv[2]],'--raw-dir',str(self.raw_dir)],encoded,**kwargs)
        factory=(self.pr.single_inference(slots,snapshot) if mode=='single' else self.pr.limited_inference(slots))
        from unittest.mock import patch
        with patch.object(tasks,'run_owned',owned):
            return await self.pr.SnapshotPipeline(self.workspace,state_dir=self.state.path,corpus=self.corpus,
                language=case['language'],mode='fts',snapshot=snapshot,inference_factory=factory).run(case['question'])

    def result_ok(self,result,frozen):
        # Valid partial/unknown answers remain observations, not technical failures or retry triggers.
        return (self.pr.result_models_match(result,frozen['model']) and not self.pr.technical_failure(result)
                and result.get('execution_status') in {'completed','partial'}
                and result.get('metrics',{}).get('unknown_inference_attempts',0)==0)

    def summarize(self,report):
        value=super().summarize(report)
        value.update(single_multi_comparison='source_anchor_targeted_development_snapshot_regression',semantic_acceptance='not_evaluated')
        return value


def export(folder,journal,error=None,plan=None):
    exports=core.private_dir(folder/'exports')
    path=exports/f'bundle-{len(list(exports.glob("bundle-*.json")))+1:04d}.json'
    values={}
    if journal.state:
        state=deepcopy(journal.state);report=state['report']
        if error:report.update(status='stopped',error=str(error) or type(error).__name__)
        values.update({'index-verify':state['index_verify'],'plan':state['plan'],
            'freeze':report['frozen_conditions'],'result':report,
            'runner':{'version':VERSION,'config':state['config'],'journal_events':journal.sequence,
                'journal_tip_sha256':journal.tip,'exported_at':core.utc(),
                'scope':'Application v099 unchanged; external v103 linked-block exact source anchor plus unchanged claim text; same prior research selection; not acceptance or E2E.'}})
        template=core.read_json(HERE/'evaluation.pending.json')
        template['status']='pending_human_review';template['report_sha256']=core.digest(report)
        for review in template['reviews']:
            row=next((x for x in report['requests'] if x['case_id']==review['case_id'] and x['mode']==review['mode'] and 'result' in x),None)
            if row:
                result=row['result'];review.update(answer=result['answer'],claims=result['claims'],
                    citations=result['citations'],answer_status=result['answer_status'],
                    execution_status=result['execution_status'],status='pending_human_review')
        values['human-review-template']=template
    else:
        values['admission']={'status':'stopped_before_dispatch','error':str(error),
            'generation_calls':0,'embedding_calls':0,'plan':plan,
            'preparation_bundle_sha256':core.read_json(HERE/'preparation_pin.json')['bundle_sha256']}
    tests=sorted(folder.glob('offline-tests-*.json'))
    if tests:values['offline-tests']=core.read_json(tests[-1])
    values['selection-policy']=core.read_json(HERE/'selection-policy.frozen.json')
    values['task-selection']=core.read_json(HERE/'task-selection.frozen.json')
    values['prompt-profile']=core.read_json(HERE/'prompt-profile.frozen.json')
    values['research-review']=core.read_json(HERE/'research-review.json')
    import forensic_capture
    raw_dir=folder/'raw'
    if raw_dir.is_dir():
        for path_ in sorted(raw_dir.glob('*.json')):
            witness=core.read_json(path_);values[path_.stem]=witness
            if path_.name.startswith('raw-'):
                try:values['analysis-'+witness['task_id']]=forensic_capture.analyze(witness,witness['mode'])
                except Exception as error_:values['analysis-'+witness['task_id']]={'status':'analysis_error','error':str(error_),'generation_calls':0}
    files={}
    for label,value in values.items():
        files['day31-source-anchor-mac-v103-'+label+'.json']={
            'sha256':sha256((core.canonical(value)+'\n').encode()).hexdigest(),'data':value}
    core.write_new(path,{'schema':'day31-evidence-bundle-v1','files':files})
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['run','export'])
    parser.add_argument('--root',type=Path,default=Path.cwd())
    args=parser.parse_args()
    lock=None;journal=None;folder=None;plan=None
    try:
        package_sha=package_check();root=core.no_symlinks(args.root).resolve()
        if sys.version_info<(3,13):raise core.Stop('Use existing Python 3.13+ venv.')
        folder=core.private_dir(core.no_symlinks('/tmp/day31-source-anchor-v103-r1-work'))
        if folder.resolve().is_relative_to(root):raise core.Stop('Run artifacts must be outside repository.')
        lock=os.open(folder/'run.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        journal=core.Journal(folder/'journal')
        if args.operation=='export':
            path=export(folder,journal)
            print(json.dumps({'bundle':str(path),'inference_performed':False}));return 0
        pin=core.read_json(HERE/'reviewed-prior-receipt.json')
        if sha256(core.no_symlinks(pin['path']).read_bytes()).hexdigest()!=pin['sha256']:
            raise core.Stop('Reviewed stopped v102 regression bundle differs; no dispatch.')
        preparation,frozen,document,snapshots=load_preparation()
        native=IndependentNative(root,preparation,frozen,document,snapshots)
        native.raw_dir=core.private_dir(folder/'raw')
        checks=subprocess.run([sys.executable,str(HERE/'run_tests.py')],capture_output=True,text=True,
            env={**os.environ,'DAY31_TEST_APP':str(root/'day-31-developer-assistant')},timeout=60)
        tests={'status':'passed' if checks.returncode==0 else 'failed','stdout':checks.stdout,'stderr':checks.stderr,
               'exit_code':checks.returncode,'generation_calls':0,'scope':'Offline coordinator fault/signal checks plus selector/capture/native scoped worker smoke; synthetic model replies.'}
        testfile=folder/f'offline-tests-{len(list(folder.glob("offline-tests-*.json")))+1:04d}.json'
        core.write_new(testfile,tests)
        if checks.returncode:raise core.Stop('Runner offline checks failed before generation.')
        target=core.read_json(HERE/'task-selection.frozen.json')
        if target['case_ids']!=['RU-1','EN-3'] or target['max_generation_calls']!=4:raise core.Stop('Targeted four-call bound changed.')
        plan=core.make_plan(native,target['case_ids'],4)
        plan['preparation_binding']=native.binding()
        if plan['pairs']!=2 or plan['generation_upper_bound']!=4:raise core.Stop('Unexpected paired bound.')
        config={'runner_version':VERSION,'package_sha256':package_sha,'root':str(root),'packet':'source-anchor-targeted-development-regression',
                'state_dir':str(native.state.path),'preparation_binding':native.binding()}
        paused=False
        def interrupt(signum,frame):
            nonlocal paused
            if paused:raise KeyboardInterrupt('Forced stop: unresolved requests will not replay.')
            paused=True
            print('Pause requested: finish and save current request. Second Ctrl+C forces stop.',file=sys.stderr,flush=True)
        old=signal.signal(signal.SIGINT,interrupt)
        try:
            report=asyncio.run(core.advance(native,journal,config,plan,native.conditions(),
                should_pause=lambda:paused,reviewed_model=frozen['intended_model']))
        finally:signal.signal(signal.SIGINT,old)
        path=export(folder,journal)
        print(json.dumps({'status':report['status'],'summary':report['summary'],'bundle':str(path),
                          'offline_tests':str(testfile)},indent=2))
        return 0 if report['status']=='completed' else 2
    except (Exception,KeyboardInterrupt) as error:
        path=None
        if folder is not None and journal is not None:
            try:path=export(folder,journal,error,plan)
            except Exception:pass
        print(json.dumps({'status':'paused' if isinstance(error,core.Pause) else 'stopped',
                          'error':str(error) or type(error).__name__,'bundle':str(path) if path else None,
                          'automatic_retry':False}),file=sys.stderr)
        return 130 if isinstance(error,core.Pause) else 2
    finally:
        if lock is not None:os.close(lock)


if __name__=='__main__':raise SystemExit(main())
