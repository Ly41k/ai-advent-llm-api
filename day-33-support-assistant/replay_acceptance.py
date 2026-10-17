"""Reprocess a saved real answer offline; never replace the original live verdict."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from common import ROOT, parse_json, require
from support_agent import prepare, render, validate_context, validate_plan


def replay(path):
    raw=path.read_bytes()
    receipt=parse_json(raw)
    require(receipt.get('attempt_id')=='attempt-02' and receipt['http']['status']==200
            and receipt['http']['post_attempts']==1 and receipt['automatic_retries']==0
            and receipt['fallback_calls']==0, 'wrong_saved_attempt')
    require(receipt['error']['code']=='missing_action_evidence' and receipt['result'] is None,
            'unexpected_original_verdict')
    plan=receipt['model_plan']
    require(parse_json(receipt['model_reply'])==plan,'model_plan_mismatch')
    original=copy.deepcopy(plan)
    ticket=next(row for row in parse_json((ROOT/'data/tickets.json').read_bytes()) if row['ticket_id']=='T-101')
    user=next(row for row in parse_json((ROOT/'data/users.json').read_bytes()) if row['user_id']=='U-001')
    validate_context(ticket,user)
    payload=prepare(receipt['model_input']['question'],ticket,user)
    require(payload['ticket_id']==receipt['model_input']['ticket_id']
            and payload['context']==receipt['model_input']['context']
            and payload['sources']==receipt['model_input']['sources'], 'saved_input_mismatch')
    validate_plan(plan,payload)
    result=render(plan,payload,{'mode':'retained_live_response_replay','model':'openai/gpt-oss-120b',
                              'generation_calls':0,'http_posts':0,
                              'original_usage':receipt['http']['usage'],
                              'original_response_id':receipt['http']['response_id']})
    require(plan==original,'model_plan_changed')
    require(all(r['source_ids']==[] or all(s in {v['id'] for v in result['sources']}
            for s in r['source_ids']) for r in result['recommendations']),'unbound_action_source')
    return {'status':'passed','scope':'offline_replay_of_retained_real_response',
            'original_live_status':receipt['status'],'original_live_error':receipt['error'],
            'original_http':receipt['http'],'original_receipt_sha256':hashlib.sha256(raw).hexdigest(),
            'model_plan_unchanged':True,'model_plan':original,
            'new_provider_posts':0,'new_generation_calls':0,
            'application_evidence_policy':'explicit_catalog_source_binding_separate_from_model_facts',
            'result':result,'fresh_live_acceptance':False,
            'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                for name in ('support_agent.py','replay_acceptance.py')}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with os.fdopen(os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as output:
        result=replay(args.input)
        output.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','scope','model_plan_unchanged','new_provider_posts','fresh_live_acceptance')},ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
