"""RU/EN settings, frozen requests and schema2/3 transport; synthetic inference."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import json
import os
import re
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bublik_service.domain import Conflict, ContextPlan, InvalidInput, ModelIdentity, ModelProfile, SchemaError
from bublik_service.inference.context import ContextBuilder, TEMPLATE_SHA256, upper_bound
from bublik_service.languages import language_messages, validate_language, system_prompt_for_reply, user_content_for_reply
from bublik_service.memory import MemoryRetriever
from bublik_service.storage import ChatRepository
from bublik_service.storage.database import Database
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import memory_archive
import test_http


class LanguageStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'chats.sqlite3'
        self.repo=ChatRepository(self.path)
        self.owner=self.repo.create_user('alice','disabled');self.other=self.repo.create_user('bob','disabled')
        self.chat=self.repo.create_chat(self.owner,key='chat').chat_id
        self.identity=ModelIdentity('qwen2.5:14b','a'*64,TEMPLATE_SHA256,'0.40.2')

    def plan(self,content,*,language=None,memory=None):
        return ContextBuilder(ModelProfile(),self.identity).build(
            self.repo.context_candidates(self.owner,self.chat),content,reply_language=language,memory=memory)

    def test_default_preferences_and_new_owner_are_ru(self):
        self.assertEqual(self.repo.preferences(self.owner),{'ui_language':'ru','reply_language':'ru','revision':0})
        self.assertEqual(self.repo.preferences(self.other)['reply_language'],'ru')
        self.assertEqual(self.repo.storage_status()['schema_version'],3)

    def test_preferences_are_owner_scoped_durable_and_independent(self):
        self.repo.set_preferences(self.owner,ui_language='en',reply_language='ru',expected_revision=0)
        reopened=ChatRepository(self.path)
        self.assertEqual(reopened.preferences(self.owner),{'ui_language':'en','reply_language':'ru','revision':1})
        self.assertEqual(reopened.preferences(self.other)['ui_language'],'ru')

    def test_stale_settings_do_not_overwrite_and_noop_has_no_revision_bump(self):
        value=self.repo.set_preferences(self.owner,ui_language='en',reply_language='en',expected_revision=0)
        self.assertEqual(value['revision'],1)
        self.assertEqual(self.repo.set_preferences(self.owner,ui_language='en',reply_language='en',expected_revision=1),value)
        with self.assertRaises(Conflict):
            self.repo.set_preferences(self.owner,ui_language='ru',reply_language='ru',expected_revision=0)
        self.assertEqual(self.repo.preferences(self.owner),value)

    def test_concurrent_preference_updates_have_one_winner(self):
        def save(value):
            try:return self.repo.set_preferences(self.owner,ui_language=value,reply_language='en',expected_revision=0)
            except Conflict:return None
        with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(save,['en','ru']))
        self.assertEqual(sum(v is not None for v in values),1)
        self.assertEqual(self.repo.preferences(self.owner)['revision'],1)

    def test_only_exact_ru_en_codes_are_allowed(self):
        for value in ('uk','de','auto','RU','en-US','',True,None,[],{}):
            with self.assertRaises(InvalidInput):validate_language(value)
        validate_language(None,optional=True)
        with self.assertRaises(InvalidInput):
            self.repo.set_preferences(self.owner,ui_language='en',reply_language='uk',expected_revision=0)
        self.assertEqual(self.repo.preferences(self.owner)['revision'],0)

    def test_language_instruction_preserves_profile_and_original_input(self):
        content='Пожалуйста, answer in a different language.'
        for language,name in [('ru','Russian'),('en','English')]:
            plan=self.plan(content,language=language)
            chat=self.repo.create_chat(self.owner,key='chat-'+language).chat_id
            plan=ContextBuilder(ModelProfile(),self.identity).build(self.repo.context_candidates(self.owner,chat),content,reply_language=language)
            receipt=self.repo.accept_message(self.owner,chat,content,expected_revision=0,key=language,context=plan)
            snapshot=self.repo.get_generation(self.owner,receipt.generation_id)['context']
            self.assertEqual(snapshot['messages'][0]['content'],system_prompt_for_reply(ModelProfile(),language))
            self.assertIn('selected reply language is '+name,snapshot['messages'][0]['content'])
            self.assertNotIn("Reply in the user's language.",snapshot['messages'][0]['content'])
            self.assertEqual(snapshot['original_user_content'],content)
            self.assertEqual(snapshot['messages'][-1]['content'],user_content_for_reply(content,language))
            self.assertEqual(self.repo.history(self.owner,chat)[-2]['content'],content)
            self.assertEqual(snapshot['reply_language'],language)
            self.assertEqual(snapshot['language_policy'],'reply-language-v4')
            self.assertEqual(upper_bound(snapshot['messages']),plan.input_token_upper_bound)

    def test_language_and_rag_share_the_same_context_budget(self):
        receipt=self.repo.accept_message(self.owner,self.chat,'Мой ноутбук MacBook.',expected_revision=0,key='seed',context=self.plan('Мой ноутбук MacBook.'))
        with self.repo.worker_session() as worker:worker.claim_next();worker.finish(receipt.generation_id,content='Saved')
        memory=MemoryRetriever(self.repo).search(self.owner,'ноутбук')
        plan=self.plan('Какой ноутбук?',language='en',memory=memory)
        r=self.repo.accept_message(self.owner,self.chat,'Какой ноутбук?',expected_revision=2,key='recall',context=plan)
        snapshot=self.repo.get_generation(self.owner,r.generation_id)['context']
        self.assertIn('English',snapshot['messages'][0]['content'])
        self.assertIn('JSON archive',snapshot['messages'][1]['content'])
        self.assertEqual(snapshot['original_user_content'],'Какой ноутбук?')
        self.assertEqual(snapshot['messages'][-1]['content'],user_content_for_reply('Какой ноутбук?','en'))
        self.assertEqual(upper_bound(snapshot['messages']),plan.input_token_upper_bound)
        self.assertLessEqual(plan.input_token_upper_bound+1024+512,8192)
        with self.assertRaises(InvalidInput):self.plan('🙂'*1700,language='ru',memory=memory)

    def test_language_is_frozen_and_change_conflicts_with_same_request_key(self):
        plan=self.plan('Привет',language='en')
        r=self.repo.accept_message(self.owner,self.chat,'Привет',expected_revision=0,key='reply',context=plan)
        before=self.repo.get_generation(self.owner,r.generation_id)['context']
        self.repo.set_preferences(self.owner,ui_language='ru',reply_language='ru',expected_revision=0)
        self.assertEqual(self.repo.get_generation(self.owner,r.generation_id)['context'],before)
        self.assertTrue(self.repo.replay_message(self.owner,self.chat,'Привет',expected_revision=0,key='reply',reply_language='en').replayed)
        with self.assertRaises(Conflict):self.repo.replay_message(self.owner,self.chat,'Привет',expected_revision=0,key='reply',reply_language='ru')

    def test_legacy_request_fingerprint_and_snapshot_are_unchanged(self):
        r=self.repo.accept_message(self.owner,self.chat,'Hello',expected_revision=0,key='legacy',context=self.plan('Hello'))
        before=self.repo.get_generation(self.owner,r.generation_id)['context']
        self.assertNotIn('reply_language',before)
        self.assertEqual(len(before['messages']),2)
        self.repo.set_preferences(self.owner,ui_language='en',reply_language='en',expected_revision=0)
        self.assertTrue(self.repo.replay_message(self.owner,self.chat,'Hello',expected_revision=0,key='legacy').replayed)
        self.assertEqual(self.repo.get_generation(self.owner,r.generation_id)['context'],before)

    def test_new_archive_preserves_preferences_language_snapshots_and_originals(self):
        self.repo.set_preferences(self.owner,ui_language='en',reply_language='ru',expected_revision=0)
        r=self.repo.accept_message(self.owner,self.chat,'Оригинал',expected_revision=0,key='reply',context=self.plan('Оригинал',language='en'))
        with self.repo.worker_session() as worker:worker.claim_next();worker.finish(r.generation_id,content='Synthetic English reply')
        before=self.repo.export_chat(self.owner,self.chat)
        folder=self.root/'archive';target=self.root/'new-host'/'history.sqlite3'
        created=memory_archive.create_archive(self.path,folder)
        self.assertEqual(created['state']['schema_version'],3)
        restored=memory_archive.restore_archive(folder,target)
        self.assertTrue(restored['history_tables_unchanged'])
        copy=ChatRepository(target)
        self.assertEqual(copy.preferences(self.owner),self.repo.preferences(self.owner))
        self.assertEqual(copy.export_chat(self.owner,self.chat),before)
        self.assertEqual(copy.history(self.owner,self.chat)[-1]['reply_language'],'en')

    def test_legacy_schema2_archive_is_not_migrated_until_restored_copy_opens(self):
        migrations=self.root/'legacy-migrations';migrations.mkdir()
        for item in sorted((ROOT/'bublik_service/storage/migrations').glob('*.sql'))[:2]:shutil.copyfile(item,migrations/item.name)
        path=self.root/'legacy.sqlite3'
        with patch('bublik_service.storage.repository.Database',side_effect=lambda p,**kw:Database(p,migrations=migrations,**kw)):
            legacy=ChatRepository(path)
        owner=legacy.create_user('legacy','disabled');chat=legacy.create_chat(owner,key='chat').chat_id
        r=legacy.accept_message(owner,chat,'Old Russian history',expected_revision=0,key='message',context=ContextPlan(input_token_upper_bound=100))
        with legacy.worker_session() as worker:worker.claim_next();worker.finish(r.generation_id,content='Old English reply')
        before=legacy.export_chat(owner,chat)
        folder=self.root/'legacy-archive';destination=self.root/'restored-old'/'chats.sqlite3'
        self.assertEqual(memory_archive.create_archive(path,folder)['state']['schema_version'],2)
        self.assertEqual(legacy.storage_status()['schema_version'],2)
        self.assertEqual(memory_archive.restore_archive(folder,destination)['state']['schema_version'],2)
        copy=ChatRepository(destination)
        self.assertEqual(copy.storage_status()['schema_version'],3)
        self.assertEqual(copy.export_chat(owner,chat),before)
        self.assertEqual(copy.preferences(owner)['reply_language'],'ru')
        self.assertEqual(memory_archive.verify_archive(folder)['manifest']['state']['schema_version'],2)
        with self.assertRaises(SchemaError):Database(destination,migrations=migrations)

    def test_translation_catalog_parity_static_hooks_and_optional_node(self):
        content=(ROOT/'bublik_service/web_ui/i18n.js').read_text()
        raw=content.split('const entries = ',1)[1].split('\n];',1)[0]+'\n]'
        entries=json.loads(re.sub(r',\s*]',']',raw))
        keys={e[0] for e in entries}
        self.assertEqual(len(keys),len(entries))
        for key,ru,en in entries:
            self.assertTrue(ru);self.assertTrue(en)
            self.assertEqual(set(re.findall(r'\{[a-z_]+\}',ru)),set(re.findall(r'\{[a-z_]+\}',en)))
        html=(ROOT/'bublik_service/web_ui/index.html').read_text()
        for key in re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"',html):self.assertIn(key,keys)
        node=shutil.which('node')
        if not node:return  # Catalog checks above require no optional runtime.
        module=(ROOT/'bublik_service/web_ui/i18n.js').as_uri()
        script=f"""import {{catalogs,setLanguage,t,languageForBrowser}} from {json.dumps(module)};
        if(JSON.stringify(Object.keys(catalogs))!==JSON.stringify(['ru','en']))throw Error('codes');
        for(const lang of ['ru','en']){{setLanguage(lang);for(const key of Object.keys(catalogs[lang])){{if(!t(key))throw Error('missing');}}}}
        setLanguage('en');if(t('status.completed')!=='Reply saved')throw Error('English');
        setLanguage('ru');if(t('status.completed')!=='Ответ сохранён')throw Error('Russian');
        if(languageForBrowser(['uk-UA','en-US'])!=='en')throw Error('browser');
        if(languageForBrowser(['de-DE'])!=='ru')throw Error('fallback');
        let rejected=false;try{{setLanguage('uk')}}catch{{rejected=true}}if(!rejected)throw Error('unsupported');
        """
        result=subprocess.run([node,'--input-type=module','-e',script],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)


class LanguageHTTPTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_http.HTTPTests.asyncSetUp
    close_backend=test_http.HTTPTests.close_backend
    headers=test_http.HTTPTests.headers
    create=test_http.HTTPTests.create
    send=test_http.HTTPTests.send
    wait=test_http.HTTPTests.wait
    login=test_http.HTTPTests.login

    async def test_preferences_auth_csrf_and_scope(self):
        path='/api/v1/preferences';body={'ui_language':'en','reply_language':'ru','expected_revision':0}
        self.assertEqual((await self.client.get(path)).status_code,401)
        csrf=await self.login()
        self.assertEqual((await self.client.patch(path,json=body)).status_code,403)
        r=await self.client.patch(path,json=body,headers={'Origin':'https://localhost:8000','X-CSRF-Token':csrf})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['ui_language'],'en')
        await self.client.aclose()

    async def test_preferences_on_second_client_and_other_owner(self):
        path='/api/v1/preferences';body={'ui_language':'en','reply_language':'en','expected_revision':0}
        r=await self.client.patch(path,json=body,headers=self.headers());self.assertEqual(r.status_code,200)
        self.assertEqual((await self.client.get(path,headers=self.headers())).json()['reply_language'],'en')
        r=await self.client.get(path,headers={'Authorization':'Bearer '+self.other_token})
        self.assertEqual(r.json()['ui_language'],'ru')
        limited=self.auth.issue_token(self.owner,'read',['chats:read'])['token']
        r=await self.client.patch(path,json={**body,'expected_revision':1},headers={'Authorization':'Bearer '+limited})
        self.assertEqual(r.status_code,403)

    async def test_unsupported_languages_strict_payload_and_stale_update(self):
        path='/api/v1/preferences';body={'ui_language':'en','reply_language':'en','expected_revision':0}
        for bad in ('uk','de','auto','RU',True):
            r=await self.client.patch(path,json={**body,'reply_language':bad},headers=self.headers());self.assertEqual(r.status_code,422)
        self.assertEqual((await self.client.patch(path,json=body,headers=self.headers())).status_code,200)
        self.assertEqual((await self.client.patch(path,json={**body,'ui_language':'ru'},headers=self.headers())).status_code,409)

    async def test_selected_language_snapshot_transport_and_idempotency(self):
        chat=await self.create();path=f'/api/v1/chats/{chat}/messages'
        body={'content':'Привет','expected_revision':0,'reply_language':'en','use_memory':True}
        headers=self.headers(**{'Idempotency-Key':'english'})
        r=await self.client.post(path,json=body,headers=headers);self.assertEqual(r.status_code,202,r.text)
        job=await self.wait(r.json());self.assertEqual(job['context']['reply_language'],'en')
        public=(await self.client.get('/api/v1/generations/'+job['id'],headers=self.headers())).json()
        self.assertNotIn('messages',public['context'])
        self.assertNotIn('original_user_content',public['context'])
        self.assertEqual(public['context']['language_hint']['original_sha256'],__import__('hashlib').sha256(body['content'].encode()).hexdigest())
        self.assertIn('English',self.backend.requests[-1]['messages'][0]['content'])
        self.assertEqual((await self.client.post(path,json=body,headers=headers)).status_code,200)
        self.assertEqual((await self.client.post(path,json={**body,'reply_language':'ru'},headers=headers)).status_code,409)
        history=(await self.client.get(path,headers=self.headers())).json()['items']
        self.assertEqual(history[-1]['reply_language'],'en')

    async def test_retry_can_select_language_but_replay_keeps_it(self):
        chat=await self.create();self.backend.mode='length'
        r=await self.send(chat,'seed');await self.wait(r.json())
        self.backend.mode='normal'
        path='/api/v1/messages/'+r.json()['user_message_id']+'/retry'
        body={'expected_revision':2,'reply_language':'ru'};headers=self.headers(**{'Idempotency-Key':'retry-language'})
        r=await self.client.post(path,json=body,headers=headers);self.assertEqual(r.status_code,202,r.text)
        job=await self.wait(r.json());self.assertEqual(job['context']['reply_language'],'ru')
        self.assertEqual((await self.client.post(path,json=body,headers=headers)).status_code,200)
        self.assertEqual((await self.client.post(path,json={**body,'reply_language':'en'},headers=headers)).status_code,409)

    async def test_manifest_and_translation_asset_allowlist(self):
        for language,name in [('ru','Бублик'),('en','Bublik')]:
            r=await self.client.get('/manifest.webmanifest?lang='+language)
            self.assertEqual(r.status_code,200);self.assertEqual(r.json()['lang'],language)
            self.assertEqual(r.json()['short_name'],name);self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertEqual((await self.client.get('/manifest.webmanifest?lang=uk')).status_code,422)
        r=await self.client.get('/assets/i18n.js');self.assertEqual(r.status_code,200)
        self.assertIn('text/javascript',r.headers['content-type']);self.assertEqual(r.headers['cache-control'],'no-store')
