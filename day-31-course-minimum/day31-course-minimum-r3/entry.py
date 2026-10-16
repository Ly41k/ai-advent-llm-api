#!/usr/bin/env python3
"""Course minimum: preflight is offline; live is a separate explicit operation."""
import argparse,asyncio,fcntl,json,os,subprocess,sys
import traceback
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from bootstrap_course import HERE,load


def history(core):
    path=HERE/'inputs/r2-mac-preflight-stopped.json'
    pins=core.read_json(HERE/'dependency-pins.json')
    if sha256(path.read_bytes()).hexdigest()!=pins['r2_failed_bundle_sha256']:raise core.Stop('Prior failed preflight bundle differs.')
    prior=core.read_json(path)
    if prior.get('schema')!='day31-evidence-bundle-v1':raise core.Stop('Prior failed preflight schema differs.')
    for row in prior['files'].values():
        if sha256((core.canonical(row['data'])+'\n').encode()).hexdigest()!=row['sha256']:raise core.Stop('Prior report digest differs.')
    old=core.read_json(HERE/'inputs/reviewed-mac83.json')
    if any(prior['files'].get(k)!=v for k,v in old['files'].items()):raise core.Stop('Prior source evidence differs.')
    return deepcopy(prior['files'])


def export(folder,core,error=None):
    # Retain original native data and append separately named reports.
    files=history(core);values={}
    for path in sorted(folder.glob('*.json')):
        if path.name.startswith('bundle-'):continue
        values[path.stem]=core.read_json(path)
    for sub in ['raw','publication','reviews']:
        for path in sorted((folder/sub).glob('*.json')):values[sub+'-'+path.stem]=core.read_json(path)
    if error:values['export-error']={'error':str(error) or type(error).__name__,'automatic_retry':False}
    dispatches=[v for k,v in values.items() if k.startswith('raw-dispatch-')]
    raws=[v for k,v in values.items() if k.startswith('raw-raw-')]
    terminal={r['task_id'] for r in raws if r.get('response',{}).get('done') is True}
    receipt=values.get('preflight',{})
    values['summary']={'version':'course-minimum-r3','preflight_status':receipt.get('status','not_passed'),
        'known_terminal_calls':len(terminal),'dispatch_records':len(dispatches),
        'unknown_dispatch_outcomes':sorted({d['task_id'] for d in dispatches}-terminal),
        'generation_slots_reserved':int('reservation' in values),'generation_cap':1,
        'current_operation_qwen_calls':0 if not dispatches else 'see_terminal_and_unknown_counts',
        'old_qwen_calls_excluded':True,'old_61_reports_retained':True,'prior_r2_failure_retained':True,
        'course_minimum':'not_accepted','extended_stage7':'paused_incomplete','stage8':'not_started'}
    for label,value in values.items():
        name='day31-course-minimum-r3-'+label+'.json'
        if name in files:raise core.Stop('Report collision.')
        files[name]={'data':value,'sha256':sha256((core.canonical(value)+'\n').encode()).hexdigest()}
    directory=core.private_dir(folder/'exports')
    output=directory/f'bundle-{len(list(directory.glob("bundle-*.json")))+1:04d}.json'
    core.write_new(output,{'schema':'day31-evidence-bundle-v1','files':files})
    return output,values['summary']


def prepare(folder,native,identity,args,core):
    from course_runtime import mandatory_checks,no_network,index_bytes
    from bublik_developer.model_session import ModelSession
    now=native.conditions();session=ModelSession(native.workspace).status()
    if not session.get('gate_open') or not session.get('epoch_matches'):raise core.Stop('Read-only model session gate is not confirmed; no dispatch.')
    expected={'root':str(native.workspace.root),'identity':identity,'conditions':now,
              'production_current_sha256':native.prepared['production_CURRENT_sha256_before']}
    receipt=folder/'preflight.json'
    if receipt.exists():
        value=core.read_json(receipt)
        if value['binding']!=expected or value['tests_sha256']!=core.digest(core.read_json(folder/'targeted-tests.json')):
            raise core.Stop('Preflight binding changed; no dispatch.')
        return value
    if (folder/'preflight-failure.json').exists():raise core.Stop('Previous preflight failed. Preserve diagnostics; do not reuse this run directory.')
    before=index_bytes(native.state)
    check=subprocess.run([sys.executable,str(HERE/'check_local.py'),'--v103',str(args.v103),
        '--v104',str(args.v104),'--app',str(args.root/'day-31-developer-assistant'),
        '--state',str(native.state.path),'--output',str(folder/'targeted-tests.json')],
        capture_output=True,text=True,timeout=60)
    if check.returncode:
        core.write_new(folder/'targeted-tests-process.json',{'returncode':check.returncode,'stdout':check.stdout,'stderr':check.stderr})
        raise core.Stop('Targeted offline checks failed; no Qwen dispatch.')
    tests=core.read_json(folder/'targeted-tests.json')
    if tests['status']!='passed' or tests['qwen_calls']!=0:raise core.Stop('Offline checks did not pass.')
    with no_network():checks=asyncio.run(mandatory_checks(native))
    core.write_new(folder/'mandatory-checks.json',checks)
    if native.conditions()!=now or index_bytes(native.state)!=before:raise core.Stop('Conditions/index changed during preflight.')
    preview=next(p for p in core.read_json(args.v103/'expected-contexts.json') if p['case_id']=='RU-1' and p['mode']=='multi')
    from prompt_profile import DOC_VERSION
    plan={'version':'course-minimum-r3','case_id':'RU-1','mode':'multi','question':native.case['question'],
          'generation_cap':1,'embedding_cap':0,'automatic_retry':False,'other_cases_admitted':False,
          'intended_model':native.prepared['intended_model'],'model_options':now['model_options'],
          'effective_prompt_version':DOC_VERSION,'output_schema_digest':preview['output_schema_digest'],
          'prepared_context_digest':preview['context_digest'],'message_digest':preview['message_digest'],
          'source_scope':'existing FTS54/510; production44 unchanged','anchor_counts':checks['anchor_counts'],
          'semantic_review':'explicit_human_decision_on_new_bindings_required','live_authorized_by_preflight':False}
    core.write_new(folder/'live-plan.json',plan)
    value={'status':'passed','binding':expected,'tests_run':tests['tests_run'],'tests_sha256':core.digest(tests),
           'qwen_calls':0,'embedding_calls':0,'inference_performed':False,'model_session':session,
           'model_identity_scope':'intended frozen model only; no model HTTP metadata or generation requested',
           'original_source_sha256_after':native.conditions()['source_sha256'],
           'original_main_unchanged':True,'index_bytes_unchanged':True,'new_index_created':False}
    core.write_new(receipt,value);return value


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['preflight','export','live','review-template','publish'])
    p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--v103',type=Path,default=Path('/tmp/day31-source-anchor-v103-r1'))
    p.add_argument('--v104',type=Path,default=Path('/tmp/day31-anchor-persistence-v104-r1'))
    p.add_argument('--work-dir',type=Path,default=Path('/tmp/day31-course-minimum-r3-work'))
    p.add_argument('--review',type=Path);p.add_argument('--reviewer-id')
    a=p.parse_args();folder=None;core=None;lock=None
    try:
        sys.path.insert(0,str(a.v103.resolve()));import runner as core
        root=core.no_symlinks(a.root.resolve());a.root=root
        a.v103=core.no_symlinks(a.v103.resolve());a.v104=core.no_symlinks(a.v104.resolve())
        candidate=core.no_symlinks(a.work_dir)
        if candidate.resolve().is_relative_to(root):raise core.Stop('Work directory must be outside repository.')
        folder=core.private_dir(candidate)
        lock=os.open(folder/'run.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.operation=='export':
            output,summary=export(folder,core);print(json.dumps({'bundle':str(output),'inference_performed':False,'summary':summary},indent=2));return 0
        core,identity=load(a.v103,a.v104,root/'day-31-developer-assistant',folder)
        import course_runtime as rt
        if a.operation in {'review-template','publish'}:
            if a.operation=='review-template':
                value=rt.review_template(folder);target=folder/'human-review-template.json';core.write_new(target,value)
                print(json.dumps({'template':str(target),'inference_performed':False}));return 0
            if not a.review or not a.reviewer_id:raise core.Stop('Human review path and explicit reviewer ID are required.')
            public=rt.publish_review(folder,core.read_json(a.review),a.reviewer_id)
            output,_=export(folder,core);print(json.dumps({'answer_accepted':public['answer_accepted'],'public_result':public,'bundle':str(output)},ensure_ascii=True,indent=2));return 0 if public['answer_accepted'] else 2
        if sys.platform!='darwin' or sys.version_info<(3,13):raise core.Stop('Mac preflight/live requires the existing Python3.13+ Darwin environment. Use check_local.py for offline Linux checks.')
        preparation,frozen,document,snapshots=rt.base.load_preparation()
        native=rt.CourseNative(root,preparation,frozen,document,snapshots);native.configure(folder,identity)
        if a.operation=='live' and not (folder/'preflight.json').exists():raise core.Stop('A separately completed preflight is required before any live operation.')
        with rt.no_network():receipt=prepare(folder,native,identity,a,core)
        if a.operation=='preflight':
            output,summary=export(folder,core)
            print(json.dumps({'status':'preflight_passed','tests_run':receipt['tests_run'],'qwen_calls':0,
                              'embedding_calls':0,'bundle':str(output),'summary':summary},ensure_ascii=False,indent=2));return 0
        # This branch is prepared for a future separately authorized invocation.
        # Preflight and export never enter it, and never schedule it in background.
        if a.operation=='live':
            if (folder/'reservation.json').exists():raise core.Stop('Single-call reservation exists; export without replay.')
            if native.inspect()['model']!=native.prepared['intended_model']:raise core.Stop('Actual model identity differs; no generation.')
            public=asyncio.run(rt.execute_once(native,native.conditions()))
            core.write_new(folder/'post-live-conditions.json',{'conditions':native.conditions(),'qwen_calls_by_this_check':0})
            output,_=export(folder,core)
            rejected=public['publication']['runtime_refusal_preserved']
            print(json.dumps({'status':'stopped_runtime_rejection' if rejected else 'collected_pending_human_review',
                              'answer_accepted':public['answer_accepted'],'bundle':str(output),'no_automatic_repeat':True},indent=2))
            return 2 if rejected else 0
        raise core.Stop('Unsupported operation.')
    except (Exception,KeyboardInterrupt) as e:
        output=None
        if folder is not None and core is not None:
            try:
                if a.operation=='preflight' and not (folder/'preflight-failure.json').exists():
                    core.write_new(folder/'preflight-failure.json',{'error':str(e) or type(e).__name__,'qwen_calls':0,'automatic_retry':False,
                        'exception_type':type(e).__name__,
                        'stack':[{'file':f.filename,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(e.__traceback__)]})
                output,_=export(folder,core,e)
            except Exception:pass
        print(json.dumps({'status':'stopped','error':str(e) or type(e).__name__,'bundle':str(output) if output else None,
                          'automatic_retry':False},ensure_ascii=False,indent=2),file=sys.stderr);return 2
    finally:
        if lock is not None:os.close(lock)

if __name__=='__main__':raise SystemExit(main())
