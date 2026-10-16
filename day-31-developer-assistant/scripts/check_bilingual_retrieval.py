"""Actual-index FTS evidence/admission regression. Zero model or embedding calls."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bublik_developer import __version__
from bublik_developer.baseline import BaselineQwen
from bublik_developer.contracts import Role
from bublik_developer.errors import DeveloperError
from bublik_developer.generation import Qwen, context_budget
from bublik_developer.rag.corpus import ProjectCorpus
from bublik_developer.rag.index import ProjectIndex
from bublik_developer.rag.retrieval import search
from bublik_developer.rag.state import ProjectState
from bublik_developer.research import conditions, load_cases, new_output, write_new
from bublik_developer.routing import route
from bublik_developer.workspace import ProjectWorkspace

# Regression labels only. Source names never enter query, ranking or inference.
FOCUS = {'main-authority-branch-ru','main-authority-branch-en',
         'path-limit-branch-ru','path-limit-branch-en',
         'dense-private-branch-ru','dense-private-branch-en'}


def focus_keyword_hit(case, hit):
    # Annotation only, evaluated after production search. Not semantic entailment.
    text=' '.join(hit['quote'].casefold().split())
    if hit['source'] not in case['rubric_sources']:
        return False
    if case['id'].startswith('main-authority'):
        return 'main' in text and ('checked claims' in text or 'проверенные утверждения' in text)
    if case['id'].startswith('path-limit'):
        return ('four changed paths' in text or 'четыре изменённых пути' in text) and 'association' in text
    if case['id'].startswith('dense-private'):
        return 'dense' in text and ('day 30' in text or 'дня 30' in text)
    return False


def admission(context, client, role):
    client.context_validator(role,context)
    messages = [{'role':'system','content':client.system_prompt(role,context)},
                {'role':'user','content':json.dumps(context,ensure_ascii=False,sort_keys=True)}]
    budget=context_budget(messages)
    return {'budget':budget,'admitted':budget['estimated_total']<=budget['context_window'],
            'message_digest':sha256(json.dumps(messages,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()}


def collect(index, cases, branch, language_when):
    rows=[]
    for case in cases:
        plan=route(case['question'])
        result=search(index,plan.documentation_question,mode='fts',candidate_k=20,final_k=3,context_bytes=4096)
        evidence=[{'id':f'e{i}','quote':hit['quote']} for i,hit in enumerate(result['sources'],1)]
        budgets={}
        if evidence:
            context={'question':plan.documentation_question,'language':case['language'],'evidence':evidence}
            budgets['multi_documentation']=admission(context,Qwen.__new__(Qwen),Role.DOCUMENTATION)
            facts=[{'id':'g1','text':('Ветка: ' if case['language']=='ru' else 'Branch: ')+(branch or 'detached HEAD')+('. Наблюдение: ' if case['language']=='ru' else '. Observed: ')+language_when}] if plan.git_operation else []
            combined={'question':case['question'],'documentation_question':plan.documentation_question,
                      'language':case['language'],'evidence':evidence,'git_facts':facts}
            budgets['single']=admission(combined,BaselineQwen.__new__(BaselineQwen),Role.MAIN)
        rows.append({'case_id':case['id'],'focus':case['id'] in FOCUS,'language':case['language'],
            'search':result,'expected_source_present':any(h['source'] in case['rubric_sources'] for h in result['sources']) if case['rubric_sources'] else None,
            'focus_source_keyword_hit':any(focus_keyword_hit(case,h) for h in result['sources']) if case['id'] in FOCUS else None,
            'admission':budgets,'admission_git_text_scope':'Read-only frozen branch and current timestamp estimate; no MCP request or actual pipeline synthesis.'})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT.parent)
    parser.add_argument('--state-dir',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=new_output(args.output)
    report={'format':'day31-bilingual-retrieval-v1','version':__version__,
        'created_at':datetime.now(timezone.utc).isoformat(),'status':'running','error':None,
        'scope':'Known FTS source/admission checks; not semantic or dense/hybrid acceptance.',
        'answer_model_calls':0,'embedding_calls':0,'model_http_calls':0,'results':[],
        'conditions_valid_after':False}
    try:
        workspace=ProjectWorkspace.open(args.root,'ai-advent-llm-api')
        output=new_output(output,workspace)
        state=ProjectState(workspace,args.state_dir)
        cases_path=ROOT/'evaluation/research_bilingual_regression_v073.json'
        catalog,_=load_cases(cases_path)
        before=conditions(workspace,state,cases_path=cases_path)
        report['conditions']=before
        with ProjectIndex.current(state,ProjectCorpus(workspace)) as index:
            report['results']=collect(index,catalog['cases'],before['git_branch'],report['created_at'])
            old=json.loads((ROOT/'evaluation/retrieval_cases.json').read_bytes())['cases']
            calibration_path=ROOT/'evaluation/retrieval_bilingual_v073.json'
            new=json.loads(calibration_path.read_bytes())['cases']
            report['calibration_cases_sha256']=sha256(calibration_path.read_bytes()).hexdigest()
            report['calibration_results']=[]
            for preceding,case in zip(old,new,strict=True):
                result=search(index,case['question'],mode='fts')
                def hit(allowed):
                    return any(s['source'] in allowed and all(term.casefold() in s['quote'].casefold() for term in case['terms']) for s in result['sources'])
                report['calibration_results'].append({'case_id':case['id'],
                    'source_keyword_hit_at_5':hit(case['sources']) if case['sources'] else None,
                    'preceding_fixture_source_hit_at_5':hit(preceding['sources']) if preceding['sources'] else None,
                    'negative_no_candidates':not result['sources'] if not case['sources'] else None,
                    'search':result})
            index.verify()
        report['conditions_valid_after']=before==conditions(workspace,state,cases_path=cases_path)
        focus=[r for r in report['results'] if r['focus']]
        checks={'complete_catalog':len(report['results'])==20,
                'focus_sources_and_keywords':len(focus)==6 and all(r['focus_source_keyword_hit'] for r in focus),
                'all_nonempty_contexts_admitted':all(b['admitted'] for r in report['results'] for b in r['admission'].values()),
                'calibration_positive_sources':sum(r['source_keyword_hit_at_5'] is True for r in report['calibration_results'])==10,
                'calibration_negative_empty':sum(r['negative_no_candidates'] is True for r in report['calibration_results'])==2,
                'conditions_unchanged':report['conditions_valid_after']}
        report['checks']=checks
        report['status']='passed' if all(checks.values()) else 'failed'
    except DeveloperError as error:
        report['status'],report['error']='failed',error.code.value
    write_new(output,report)
    print(json.dumps({'status':report['status'],'checks':report.get('checks'),
        'cases_completed':len(report['results']),'answer_model_calls':0,'embedding_calls':0,'error':report['error']},indent=2))
    return 0 if report['status']=='passed' else 2


if __name__=='__main__':
    raise SystemExit(main())
