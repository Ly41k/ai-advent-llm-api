"""Real HTTPS/Qwen RU/EN reply checks; creates two synthetic conversations.

Does not modify account preferences or export conversation text. Saves failures.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
import uuid
from urllib.parse import urlsplit
import httpx
from check_storage import ROOT,manifest
from check_http_live import read_token


def run(client,record,observations):
    from bublik_service.http_api import runtime_manifest
    response=client.get('/api/v1/health/ready');ready=response.json()
    record('runtime_ready_and_matches_local',response.status_code==200 and ready.get('model_ready') is True
           and ready.get('runtime_source_unchanged') is True and ready.get('runtime_source_sha256')==runtime_manifest())
    prefs=client.get('/api/v1/preferences')
    record('two_language_preferences',prefs.status_code==200
           and prefs.json().get('ui_language') in ('ru','en') and prefs.json().get('reply_language') in ('ru','en'))

    def post(path,body):
        key=uuid.uuid4().hex
        for attempt in range(3):
            r=client.post('/api/v1'+path,json=body,headers={'Idempotency-Key':key})
            if r.status_code!=429:r.raise_for_status();return r.json()
            if attempt==2:raise RuntimeError('quota_unavailable')
            delay=min(65,max(1,int(r.headers.get('Retry-After','60'))))
            print(json.dumps({'waiting_for_quota_seconds':delay}),flush=True)
            while delay:pause=min(30,delay);time.sleep(pause);delay-=pause

    for language in ('ru','en'):
        chat=post('/chats',{'title':'Language control '+language})['chat_id']
        for turn in (0,1):
            case=language+('-plain' if turn==0 else '-followup-rag')
            # Explicit language wins over contrary user instructions, including a later RAG turn.
            content=(('Answer in English only. In one sentence, explain why 2+2*2 equals 6.' if language=='ru'
                      else 'Отвечай только по-русски. В одном предложении объясни, почему 2+2*2 равно 6.') if turn==0
                     else ('Now answer only in English. Briefly explain why 3*3 equals 9, without quotations.' if language=='ru'
                           else 'Теперь отвечай только по-русски. Кратко объясни, почему 3*3 равно 9, без цитат.'))
            job=post('/chats/'+chat+'/messages',{'content':content,'expected_revision':2*turn,
                     'use_memory':bool(turn),'reply_language':language})
            deadline=time.monotonic()+300
            while time.monotonic()<deadline:
                r=client.get('/api/v1/generations/'+job['generation_id'])
                if r.status_code==429:
                    delay=min(65,max(1,int(r.headers.get('Retry-After','60'))))
                    while delay:pause=min(30,delay);time.sleep(pause);delay-=pause
                    continue
                r.raise_for_status();value=r.json()
                if value['status'] not in ('queued','running'):break
                time.sleep(2)
            else:raise RuntimeError('generation_check_deadline')
            answer=value['assistant']['content']
            observations.append({'case':case,'chat_id':chat,'generation_id':value['id'],'reply_language':language,
                                 'answer_sha256':hashlib.sha256(answer.encode()).hexdigest(),'metrics':value.get('metrics')})
            record('completed-'+case,value['status']=='completed')
            record('frozen_language-'+case,value.get('context',{}).get('reply_language')==language
                   and value['context'].get('language_policy')=='reply-language-v4')
            hint=value['context'].get('language_hint',{})
            from bublik_service.languages import user_content_for_reply
            rendered=user_content_for_reply(content,language)
            record('frozen_model_input-'+case,hint.get('policy_version')=='latest-user-language-hint-v2'
                   and hint.get('original_sha256')==hashlib.sha256(content.encode()).hexdigest()
                   and hint.get('rendered_sha256')==hashlib.sha256(rendered.encode()).hexdigest())
            if turn:record('memory_enabled-'+case,value['context'].get('memory',{}).get('enabled') is True)
            record('no_cjk_'+case,re.search(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]',answer) is None)
            record('selected_language_'+case, bool(re.search(r'[А-Яа-яЁё]',answer)) if language=='ru'
                   else re.search(r'[А-Яа-яЁё]',answer) is None and bool(re.search(r'[A-Za-z]',answer)))
            pattern=r'\b(6|six|шесть|шести)\b' if turn==0 else r'\b(9|nine|девять|девяти)\b'
            record('control_result_present_'+case,bool(re.search(pattern,answer,re.I)))
            history=client.get('/api/v1/chats/'+chat+'/messages',params={'latest':'true'});history.raise_for_status()
            record('saved_language_and_original_input-'+case,history.json()['items'][-2]['content']==content
                   and history.json()['items'][-1].get('reply_language')==language)
            print(json.dumps({'completed_language':language,'case':case}),flush=True)
    unsupported=client.patch('/api/v1/preferences',json={'ui_language':'uk','reply_language':'en','expected_revision':prefs.json()['revision']})
    record('unsupported_language_rejected',unsupported.status_code==422)
    # Existing RAG checker remains separate: language support does not imply semantic translation.


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True);parser.add_argument('--token-file',type=Path,required=True)
    parser.add_argument('--ca-file',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();url=urlsplit(args.url)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        parser.error('Canonical HTTPS URL required')
    try:
        token=read_token(args.token_file)
        verify=ssl.create_default_context(cafile=str(args.ca_file)) if args.ca_file else True
        args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(args.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except (OSError,ValueError):parser.error('Private token/CA and NEW report path required')
    before=manifest();started=time.monotonic()
    report={'format':'bublik-languages-live-v1','scope':'HTTPS-Qwen-RU-EN-root-and-explicit-user-hint-plain-and-followup-RAG',
      'created_at':datetime.now(timezone.utc).isoformat(),'status':'failed','tests':[],'observations':[],
      'not_run':['physical phones','arbitrary language quality','semantic cross-language retrieval','browser localization','physical hardware transfer']}
    def record(name,passed):
        report['tests'].append({'id':name,'status':'passed' if passed else 'failed'})
        if not passed:raise RuntimeError('controlled_check_failed')
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        try:
            with httpx.Client(base_url=args.url.rstrip('/'),headers={'Authorization':'Bearer '+token},
                              verify=verify,trust_env=False,follow_redirects=False,timeout=30) as client:
                run(client,record,report['observations'])
            report['status']='passed'
        except (httpx.HTTPError,RuntimeError,ValueError,KeyError,TypeError,OSError):report['error']='live_check_failed'
        unchanged=before==manifest()
        if not unchanged:report['status']='failed'
        report['source']={'unchanged_during_run':unchanged,'source_sha256':before}
        report['summary']={'tests':len(report['tests']),'failures':sum(r['status']!='passed' for r in report['tests']),
                          'errors':int('error' in report),'skipped':0,'elapsed_seconds':time.monotonic()-started}
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'report':str(args.output),'status':report['status']}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':sys.exit(main())
