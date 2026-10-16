#!/usr/bin/env python3
"""Offline-only derived v103 report. There is deliberately no run-model command."""
import argparse
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
AUTHORITIES={'codex-v103-offline-audit':'assistant'}


@lru_cache(maxsize=1)
def reviewed_bundle():
    pins=json.loads((HERE/'input-pins.json').read_text())
    path=HERE/'inputs/v103-native-bundle.json'
    if sha256(path.read_bytes()).hexdigest()!=pins['inputs/v103-native-bundle.json']:
        raise ValueError('original_reviewed_bundle_bytes_changed')
    return json.loads(path.read_text())


def result_version(bundle, native, mode):
    files=bundle['files']
    runner=files['day31-source-anchor-mac-v103-runner.json']['data']
    return {'helper_version':runner['config']['runner_version'],
            'pipeline_schema_version':native['schema_version'], 'request_mode':mode,
            'original_result_report_sha256':files['day31-source-anchor-mac-v103-result.json']['sha256']}


def environment(v103, app):
    sys.path[:0]=[str(v103),str(app)]
    import runner as core
    manifest=core.read_json(v103/'manifest.json')
    for name,h in manifest['files_sha256'].items():
        if sha256(core.no_symlinks(v103/name).read_bytes()).hexdigest()!=h:
            raise ValueError('original_v103_package_changed: '+name)
    actual={p.relative_to(app).as_posix():sha256(core.no_symlinks(p).read_bytes()).hexdigest()
            for p in sorted(app.rglob('*.py')) if not {'.venv','__pycache__'}.intersection(p.parts)}
    if actual!=core.read_json(v103/'source-binding.json')['source_sha256']:
        raise ValueError('original_app_source_changed')
    return core


def explicit_review(record, ledger):
    """Transfer explicit assistant findings, never label them as human approval."""
    from anchor_acceptance import VERSION, digest
    # One-time migration of the preserved audit is allowed ONLY for its exact
    # original result/version. Do not mint fresh bindings for an edited result.
    original=reviewed_bundle();files=original['files']
    row=next(r for r in files['day31-source-anchor-mac-v103-result.json']['data']['requests']
             if (r['case_id'],r['mode'])==(ledger['case_id'],ledger['mode']))
    native=row['result'];task,=native['inference_tasks']
    raw=files['day31-source-anchor-mac-v103-raw-'+task['task_id']+'.json']['data']
    import forensic_capture
    _,ctx=forensic_capture.reference(row['mode'],raw['context_digest'])
    frame=json.loads(raw['response']['message']['content'])
    expected={'policy_version':VERSION,'result_version':result_version(original,native,row['mode']),
              'result_sha256':digest(native),'witness_sha256':digest(raw),
              'context_sha256':digest(ctx),'frame_sha256':digest(frame),
              'request_id':native['request_id'],'task_id':task['task_id'],
              'runtime_passed':task['output_validation']=='passed','claim_count':len(frame['claims'])}
    if record['origin']!=expected:
        raise ValueError('cannot_migrate_old_review_to_changed_result_or_version')
    if ledger['frame_sha256']!=record['origin']['frame_sha256']:
        raise ValueError('offline_ledger_frame_changed')
    if len(record['source_anchors'])!=len(ledger['claims']):
        raise ValueError('offline_ledger_claim_count_changed')
    decisions=[]
    for anchor,old in zip(record['source_anchors'],ledger['claims']):
        if (old['id']!=anchor['claim_id'] or old['claim_sha256']!=anchor['claim_sha256']
                or old['source_quote']!=anchor['quote'] or old['evidence_ids']!=[anchor['evidence_id']]):
            raise ValueError('offline_ledger_selected_claim_changed')
        clauses=[]
        for c in old['clauses']:
            state={'supported':'supported','scoped_inference':'supported',
                   'unsupported':'unsupported','incorrect':'unsupported','ambiguous':'needs_review'}[c['verdict']]
            clauses.append({'text':c['text'],'status':state,'support_spans':deepcopy(c['support_spans']),
                            'reason':c['reason']})
        status=('unsupported' if any(c['status']=='unsupported' for c in clauses) else
                'needs_review' if any(c['status']=='needs_review' for c in clauses) else 'supported')
        decisions.append({'claim_id':anchor['claim_id'],'binding_sha256':anchor['binding_sha256'],
                          'status':status,'clauses':clauses})
    return {'policy_version':VERSION,'result_binding_sha256':record['binding_sha256'],
            'reviewer':{'id':'codex-v103-offline-audit','kind':'assistant'},
            'decisions':decisions,'review_scope':'Explicit preserved offline findings; positive decisions still need a human.'}


def audit(bundle, ledger, core):
    from anchor_acceptance import build_record,attach,verify_envelope
    files=bundle['files']
    if bundle['schema']!='day31-evidence-bundle-v1':raise ValueError('bundle_schema')
    for name,v in files.items():
        if sha256((core.canonical(v['data'])+'\n').encode()).hexdigest()!=v['sha256']:
            raise ValueError('native_report_digest_changed: '+name)
    read=lambda label:files['day31-source-anchor-mac-v103-'+label+'.json']['data']
    report=read('result'); helper=Path(__import__('forensic_capture').__file__).resolve().parent
    if core.digest(core.read_json(helper/'manifest.json'))!=read('runner')['config']['package_sha256']:
        raise ValueError('v103_helper_identity_mismatch')
    previews=core.read_json(helper/'expected-contexts.json'); rows=[]; reviews=[]
    for row in report['requests']:
        native=row['result'];task,=native['inference_tasks']
        witness=read('raw-'+task['task_id'])
        context=next(p['context'] for p in previews if p['context_digest']==witness['context_digest'] and p['mode']==row['mode'])
        version=result_version(bundle,native,row['mode'])
        record=build_record(native,witness,context,version)
        old=next(l for l in ledger['records'] if (l['case_id'],l['mode'])==(row['case_id'],row['mode']))
        review=explicit_review(record,old)
        output=attach(native,witness,context,version,review,authorities=AUTHORITIES)
        verify_envelope(output,review,authorities=AUTHORITIES)
        assert all(output[k]==v for k,v in native.items())
        rows.append({'case_id':row['case_id'],'mode':row['mode'],'result':output,
                     'completeness_review':{'direct_question_complete':old['direct_question_coverage_complete'],
                                          'frozen_rubric_complete':old['frozen_rubric_coverage_complete'],
                                          'note':old['coverage_note']}})
        reviews.append(review)
    return {'format':'day31-v104-offline-anchor-acceptance-v1','requests':rows,
            'original_native_report_sha256':core.digest(report),'native_reports_verified':len(files),
            'qwen_calls':0,'embedding_calls':0,'stage7':'open','stage8':'not_started',
            'scope':'Additive result metadata; no original answer corrected; no automatic entailment; human acceptance pending.'}, reviews


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v103',type=Path,default=Path('/tmp/day31-source-anchor-v103-r1'))
    parser.add_argument('--app',type=Path,default=Path.cwd()/'day-31-developer-assistant')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    core=environment(args.v103.resolve(),args.app.resolve())
    pins=core.read_json(HERE/'input-pins.json')
    for name,h in pins.items():
        if sha256(core.no_symlinks(HERE/name).read_bytes()).hexdigest()!=h:
            raise ValueError('reviewed_input_bytes_changed: '+name)
    path=HERE/'inputs/v103-native-bundle.json'; bundle=core.read_json(path)
    ledger=core.read_json(HERE/'inputs/clause-audit.v103.json')
    if sha256(path.read_bytes()).hexdigest()!=ledger['input_bundle_sha256']:
        raise ValueError('reviewed_ledger_bundle_mismatch')
    report,reviews=audit(bundle,ledger,core)
    folder=core.private_dir(args.output_dir)
    if folder.is_relative_to(args.app.resolve().parent):raise ValueError('audit_artifacts_must_be_outside_repo')
    values=deepcopy(bundle['files'])
    for name,data in [('day31-v104-anchor-acceptance.json',report),('day31-v104-bound-review-decisions.json',reviews)]:
        if name in values:raise ValueError('report_name_collision')
        values[name]={'data':data,'sha256':sha256((core.canonical(data)+'\n').encode()).hexdigest()}
    output=folder/f'bundle-{len(list(folder.glob("bundle-*.json")))+1:04d}.json'
    core.write_new(output,{'schema':'day31-evidence-bundle-v1','files':values})
    print(json.dumps({'status':'offline_audited_human_review_pending','qwen_calls':0,'bundle':str(output),
        'requests':[{'case_id':r['case_id'],'mode':r['mode'],
                     'runtime':r['result']['semantic_acceptance']['runtime_validation'],
                     'semantic':r['result']['semantic_acceptance']['status'],
                     'answer_accepted':r['result']['semantic_acceptance']['answer_accepted']}
                    for r in report['requests']]},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
