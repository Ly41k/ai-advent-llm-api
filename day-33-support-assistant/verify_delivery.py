"""Verify retained live evidence and runtime hashes offline. No MCP or model calls."""
import hashlib
import json
from common import ROOT, parse_json, require
from support_agent import prepare, render, validate_context, validate_plan


def verify():
    report=parse_json((ROOT/'reports/accepted.json').read_bytes())
    require(report['overall_status']=='PASS' and report['full_live_E2E']=='PASS'
            and report['fresh_live_acceptance'] is True,'invalid_acceptance')
    hashes=report['runtime_source_sha256']
    for name,sha in hashes.items():
        path=(ROOT/name).resolve()
        require(path.is_relative_to(ROOT) and hashlib.sha256(path.read_bytes()).hexdigest()==sha,
                'runtime_source_changed')
    ticket=next(row for row in parse_json((ROOT/'data/tickets.json').read_bytes()) if row['ticket_id']=='T-101')
    user=next(row for row in parse_json((ROOT/'data/users.json').read_bytes()) if row['user_id']=='U-001')
    validate_context(ticket,user)
    payload=prepare(report['model_input']['question'],ticket,user)
    require(payload['context']==report['model_input']['context'] and payload['sources']==report['model_input']['sources'],
            'saved_context_or_sources_changed')
    plan=report['model_plan']
    validate_plan(plan,payload)
    require(render(plan,payload,report['result']['llm'])==report['result'],'saved_answer_changed')
    require(all(report['technical_checks'].values()) and report['semantic_review']['status']=='PASS',
            'acceptance_not_passed')
    http=report['http']
    require(http['status']==200 and http['post_attempts']==1 and report['automatic_retries']==report['fallback_calls']==0,
            'wrong_live_execution')
    calls=report['mcp_calls']
    require(len(calls)==2 and calls[0]['tool']=='get_ticket'
            and calls[0]['arguments']=={'ticket_id':'T-101'}
            and calls[1]['tool']=='get_user' and calls[1]['arguments']=={'user_id':'U-001'}
            and all(call['completed'] and call['user_id']=='U-001' for call in calls),
            'wrong_saved_MCP_trace')
    usage=http['usage']
    require(usage['prompt_tokens']+usage['completion_tokens']==usage['total_tokens'] and usage['completion_tokens']<=1800,
            'invalid_usage')
    return {'status':'passed','scope':'retained_live_evidence_and_recorded_semantic_review_only',
            'runtime_source_files_verified':len(hashes),'accepted_attempt':'attempt-03',
            'recorded_live_E2E':'PASS','recorded_semantic_review':'PASS',
            'new_generation_calls':0,'new_provider_posts':0,'MCP_calls':0,
            'fresh_live_acceptance':False,'readme_hashes':'historical_acceptance_snapshot'}


if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))
