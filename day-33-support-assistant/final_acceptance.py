"""Attempt-03: current Mac tests + retained replay, then at most one approved curl POST."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
from unittest.mock import patch

from common import ROOT, SupportError, parse_json, require
import support_agent
import llm_adapter
import live_acceptance as first
import retry_acceptance as curl_runner
from replay_acceptance import replay

ATTEMPT = Path('/tmp/day33-live-attempt-03')
OFFLINE_REPORT = Path('/tmp/day33-final-offline-mac.json')
PREVIOUS = {
    Path('/tmp/day33-live-mac.json'): '0030fa6c427986ee766704ee5542fb5356fe02e10749b7b4c7304ea439a99545',
    Path('/tmp/day33-live-attempt-02/result.json'): '0e1184ad6904ca8804f81bc803d760dc4966d835bfdfe26adb6edfde4a6f7bb3',
    Path('/tmp/day33-live-attempt-02/replay-result.json'): '9355491e3acac90a47445ecafa003d5d8d60173a2f7c3fea7de18b5b7ed6666a',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_sources():
    expected = parse_json((ROOT/'final_acceptance_sources.json').read_bytes())
    require(len(expected)==19,'invalid_final_source_manifest')
    for name,sha in expected.items():
        source=(ROOT/name).resolve()
        require(source.is_relative_to(ROOT) and digest(source)==sha,
                'final_source_manifest_mismatch')
    require(Path(support_agent.__file__).resolve()==ROOT/'support_agent.py'
            and Path(llm_adapter.__file__).resolve()==ROOT/'llm_adapter.py',
            'unexpected_import_location')
    return {**expected, 'final_acceptance.py':digest(Path(__file__)),
            'final_acceptance_sources.json':digest(ROOT/'final_acceptance_sources.json')}


def preflight():
    require(platform.system()=='Darwin','Mac_required')
    require(not ATTEMPT.exists(),'attempt_03_already_exists')
    sources=current_sources()
    require(shutil.which('curl') is not None,'curl_missing')
    key=os.environ.get('GROQ_API_KEY','')
    require(bool(re.fullmatch(r'[A-Za-z0-9_-]{10,256}',key)),'export_GROQ_API_KEY_required')
    report=parse_json(OFFLINE_REPORT.read_bytes())
    require(report.get('status')=='passed' and report.get('tests_run')==25
            and report.get('failures')==report.get('errors')==report.get('skipped')==0
            and report.get('real_generation_calls')==report.get('real_provider_http_posts')==0,
            'current_Mac_25_tests_required')
    require(report.get('environment',{}).get('platform','').startswith('macOS-'),
            'Mac_test_report_required')
    manifest=report.get('source_sha256',{})
    for name,sha in sources.items():
        require(manifest.get(name)==sha,'Mac_test_manifest_mismatch')
    for path,sha in PREVIOUS.items():
        require(digest(path)==sha,'previous_attempt_changed')
    second=next(path for path in PREVIOUS if path.name=='result.json')
    saved_replay=next(path for path in PREVIOUS if path.name=='replay-result.json')
    old=parse_json(saved_replay.read_bytes())
    require(old['status']=='passed' and old['model_plan_unchanged'] is True
            and old['new_provider_posts']==0 and old['fresh_live_acceptance'] is False,
            'saved_replay_not_accepted')
    checked=replay(second)  # pure offline processing of the existing response
    require(checked['result']==old['result'] and checked['model_plan']==old['model_plan'],
            'current_replay_mismatch')
    return {'status':'passed','tests_run':25,'source_sha256':sources,
            'offline_report_sha256':digest(OFFLINE_REPORT),'replay_passed':True,
            'key_source':'environment:GROQ_API_KEY','key_present':True,
            'support_agent_path':str(Path(support_agent.__file__).resolve()),
            'previous_receipts':[{'path':str(p),'sha256':sha} for p,sha in PREVIOUS.items()]}


def evaluate(receipt):
    result=receipt.get('result')
    trace=receipt.get('mcp_calls',[])
    http=receipt.get('http',{})
    usage=http.get('usage') or {}
    expected_calls=[('get_ticket',{'ticket_id':'T-101'}),('get_user',{'user_id':'U-001'})]
    checks={
        'real_MCP_execution':len(trace)==2 and all(
            (event['tool'],event['arguments'])==expected_calls[i] and event['completed']
            and event['user_id']=='U-001' for i,event in enumerate(trace)),
        'RAG_three_expected_sources':[s['id'] for s in receipt.get('model_input',{}).get('sources',[])]==first.EXPECTED_SOURCES,
        'real_Groq_response':http.get('status')==200 and http.get('post_attempts')==1
                             and http.get('transport')=='curl' and http.get('curl_exit')==0,
        'measured_usage':all(type(usage.get(k)) is int and usage[k]>=0
                             for k in ('prompt_tokens','completion_tokens','total_tokens'))
                         and usage.get('completion_tokens',1801)<=1800,
        'no_retry_or_fallback':receipt.get('automatic_retries')==receipt.get('fallback_calls')==0,
        'validated_answer':isinstance(result,dict) and all(result.get('validation',{}).values())
                           and bool(result.get('validation')),
        'evidence_provenance':False,
        'previous_attempts_unchanged':all(digest(path)==sha for path,sha in PREVIOUS.items()),
    }
    if result:
        sources={s['id']:s for s in result['sources']}
        evidence=result.get('application_evidence',[])
        checks['evidence_provenance']=(result['document_facts']==receipt['model_plan']['document_facts']
            and result['context_facts']==receipt['model_plan']['context_facts']
            and all(e['assigned_by']=='application' and e['source_id'] in sources
                    and e['quote']==sources[e['source_id']]['text'] for e in evidence)
            and all(all(source_id in sources for source_id in action['source_ids'])
                    for action in result['recommendations']))
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true')
    group.add_argument('--approve-one-final-post',action='store_true')
    args=parser.parse_args()
    try:
        checked=preflight()
        if args.prepare:
            preview=curl_runner.preview_request()
            print(json.dumps({'status':'ready','mode':'preflight_only','provider_posts':0,
                              'offline_checks':checked,'prepared_request':preview,
                              'new_attempt_directory':str(ATTEMPT)},ensure_ascii=False,indent=2))
            return 0
        ATTEMPT.mkdir(mode=0o700,exist_ok=False)
        fd=os.open(ATTEMPT/'result.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except Exception as error:
        code=error.code if isinstance(error,SupportError) else 'local_preflight_failed'
        print(json.dumps({'status':'stopped','error':code,'provider_posts':0},indent=2))
        return 1
    with os.fdopen(fd,'w',encoding='utf-8') as output:
        output.write('{"status":"pending_or_interrupted","instruction":"STOP. Do not rerun."}\n')
        output.flush()
        os.fsync(output.fileno())
        transport=curl_runner.CurlOpener()
        try:
            with patch.object(llm_adapter.urllib.request,'build_opener',return_value=transport):
                receipt=first.execute_once()  # unchanged MCP -> RAG -> Groq -> corrected validator/render
            receipt.setdefault('http',{}).update(transport.metrics)
            checks=evaluate(receipt)
            receipt['technical_checks']=checks
            receipt['full_live_E2E']='PASS' if receipt['status']=='passed' and all(checks.values()) else 'FAIL'
            if receipt['full_live_E2E']=='FAIL':
                receipt['status']='failed'
        except BaseException:
            receipt={'status':'failed','full_live_E2E':'FAIL',
                     'error':{'code':'interrupted_or_local_error_unknown_outcome'},'http':transport.metrics}
        usage=receipt.get('http',{}).get('usage') or {}
        cost=None
        if all(type(usage.get(k)) is int for k in ('prompt_tokens','completion_tokens')):
            cost=round((usage['prompt_tokens']*.15+usage['completion_tokens']*.60)/1_000_000,10)
        receipt.update(attempt_id='attempt-03',fresh_live_acceptance=True,
                       offline_acceptance=checked,human_semantic_quality='pending_review',
                       estimated_list_cost_usd=cost,actual_billed_usd=None,
                       pricing_basis='planning snapshot: USD 0.15 input / 0.60 output per 1M tokens',
                       instruction='STOP. Do not rerun.')
        output.seek(0)
        output.truncate()
        output.write(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({'status':receipt['status'],'full_live_E2E':receipt['full_live_E2E'],
                      'human_semantic_quality':'pending_review','output':str(ATTEMPT/'result.json'),
                      'http':receipt.get('http'),'instruction':'STOP. Do not rerun.'},ensure_ascii=False,indent=2))
    return 0 if receipt['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
