"""Real deployed HTTPS/Qwen cross-chat recall checks, using synthetic statements.

Creates four new chats. Does not export private conversation contents or overwrite
reports. A saved report is an observation, not a signature or arbitrary recall proof.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import time
import uuid

import httpx
from check_http_live import read_token
from check_storage import ROOT, manifest


def run(client, record, observations):
    from bublik_service.http_api import runtime_manifest
    ready = client.get('/api/v1/health/ready')
    value = ready.json()
    record('runtime_matches_local_and_ready', ready.status_code == 200
           and value.get('model_ready') is True and value.get('runtime_source_unchanged') is True
           and value.get('runtime_source_sha256') == runtime_manifest())

    def request(path, payload):
        key = uuid.uuid4().hex
        for attempt in range(3):
            response = client.post('/api/v1'+path,json=payload,headers={'Idempotency-Key':key})
            if response.status_code != 429:
                response.raise_for_status()
                return response.json()
            delay = min(65,max(1,int(response.headers.get('Retry-After','60'))))
            if attempt == 2:
                raise RuntimeError('quota_unavailable')
            print(json.dumps({'waiting_for_quota_seconds':delay}),flush=True)
            # Operator-side checker; each wait remains bounded and visible.
            remaining=delay
            while remaining:
                pause=min(30,remaining)
                time.sleep(pause)
                remaining-=pause

    def generate(chat, content, memory=False):
        receipt=request('/chats/'+chat+'/messages',{'content':content,'expected_revision':0,'use_memory':memory})
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            response=client.get('/api/v1/generations/'+receipt['generation_id'])
            response.raise_for_status()
            job=response.json()
            if job['status'] not in {'queued','running'}:
                record('completed-'+receipt['generation_id'],job['status']=='completed')
                observations.append({'id':job['id'],'chat_id':chat,'status':job['status'],
                                     'answer_sha256':hashlib.sha256(job['assistant']['content'].encode()).hexdigest(),
                                     'metrics':job.get('metrics'),
                                     'memory_sources':[{'chat_id':s['chat_id'],'message_id':s['message_id'],
                                                        'source_sha256':s['source_sha256']}
                                                       for s in job.get('context',{}).get('memory',{}).get('sources',[])]})
                return job,receipt
            time.sleep(.5)
        raise RuntimeError('generation_check_deadline')

    for lang in ('ru','en'):
        marker='BublikProject'+uuid.uuid4().hex[:12]
        answer='CopperLantern'+uuid.uuid4().hex[:12]
        seed_text=(f'Для тестового проекта {marker} моё устройство называется {answer}. Ответь только: Запомнил {marker}.'
                   if lang=='ru' else f'For test project {marker}, my device is called {answer}. Reply only: Noted {marker}.')
        query=(f'Как называется моё устройство в проекте {marker}? Найди запись в прошлых разговорах и укажи источник.'
               if lang=='ru' else f'What is my device called in project {marker}? Find the saved conversation and cite the source.')
        seed_chat=request('/chats',{'title':'RAG control source '+lang})['chat_id']
        seed_job,seed=generate(seed_chat,seed_text)
        search=client.post('/api/v1/memory/search',json={'query':marker})
        assistant_source=next((s for s in search.json().get('sources',[]) if s['message_id']==seed['assistant_message_id']),None)
        record('assistant_source_role_and_status-'+lang,search.status_code==200 and assistant_source is not None
               and assistant_source['role']=='assistant' and assistant_source['status']=='completed')
        window=client.get('/api/v1/chats/'+seed_chat+'/messages/'+seed['assistant_message_id']+'/context')
        record('original_conversation_window-'+lang,window.status_code==200
               and [m['role'] for m in window.json().get('items',[])]==['user','assistant']
               and window.json()['items'][-1]['content']==seed_job['assistant']['content'])
        target_chat=request('/chats',{'title':'RAG recall '+lang})['chat_id']
        recalled,_=generate(target_chat,query,True)
        sources=recalled.get('context',{}).get('memory',{}).get('sources',[])
        relevant=next((s for s in sources if s['message_id']==seed['user_message_id']),None)
        record('cross_chat_source-'+lang,relevant is not None and relevant['chat_id']==seed_chat)
        record('exact_control_answer-'+lang,answer.casefold() in recalled['assistant']['content'].casefold())
        label='[M'+str(sources.index(relevant)+1)+']' if relevant else '[NO_SOURCE]'
        record('source_label-'+lang,label in recalled['assistant']['content'])
        history=client.get('/api/v1/chats/'+target_chat+'/messages',params={'latest':'true'}).json()['items']
        record('saved_history_has_sources-'+lang,history[-1].get('memory',{}).get('sources')==sources)
        if relevant:
            original=client.get('/api/v1/chats/'+seed_chat+'/messages/'+seed['user_message_id'])
            record('source_endpoint-'+lang,original.status_code==200 and original.json()['content']==seed_text)
        print(json.dumps({'completed_language':lang}),flush=True)
    unknown='AbsentMemory'+uuid.uuid4().hex
    response=client.post('/api/v1/memory/search',json={'query':unknown})
    record('negative_retrieval',response.status_code==200 and response.json()['sources']==[])
    return observations


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--token-file',type=Path,required=True)
    parser.add_argument('--ca-file',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    from urllib.parse import urlsplit
    url=urlsplit(args.url)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        parser.error('Canonical HTTPS URL required')
    try:
        token=read_token(args.token_file)
        verify=ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else True
        args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(args.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except (OSError,ValueError):
        parser.error('Private token/CA and NEW report path required')
    before=manifest()
    report={'format':'bublik-rag-live-v1','scope':'HTTPS-Qwen-cross-chat-recall-synthetic-statements',
            'created_at':datetime.now(timezone.utc).isoformat(),'status':'failed','tests':[], 'observations':[],
            'not_run':['physical phones','transfer to another computer','arbitrary semantic recall',
                       'guaranteed resistance to model prompt injection','all private production history quality']}
    def record(name,passed):
        report['tests'].append({'id':name,'status':'passed' if passed else 'failed'})
        if not passed:
            raise RuntimeError('controlled_check_failed')
    started=time.monotonic()
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        try:
            with httpx.Client(base_url=args.url.rstrip('/'),headers={'Authorization':'Bearer '+token},
                              verify=verify,trust_env=False,follow_redirects=False,timeout=30) as client:
                run(client,record,report['observations'])
            report['status']='passed'
        except (httpx.HTTPError,RuntimeError,ValueError,KeyError,TypeError,OSError):
            # Neither private response bodies nor tokens enter the report/console.
            report['error']='live_check_failed'
        unchanged=before==manifest()
        if not unchanged:
            report['status']='failed'
        report['source']={'unchanged_during_run':unchanged,'source_sha256':before}
        report['summary']={'tests':len(report['tests']),
                           'failures':sum(t['status']!='passed' for t in report['tests']),
                           'errors':int('error' in report),'skipped':0,
                           'elapsed_seconds':time.monotonic()-started}
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'report':str(args.output),'status':report['status']}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    sys.exit(main())
