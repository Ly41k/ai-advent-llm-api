"""Regression: conflicting roots, real HTTP dispatch and immutable legacy jobs.

The loopback engine is synthetic; no language-quality claim about real Qwen.
"""
from copy import deepcopy
from dataclasses import asdict
import json
import unittest

from bublik_service.domain import ModelProfile
from bublik_service.inference.context import ContextBuilder, upper_bound
from bublik_service.inference.ollama import InferenceError
from bublik_service.languages import language_messages, system_prompt_for_reply, user_content_for_reply, language_hint_metadata
import test_inference


class LanguagePolicyTests(unittest.TestCase):
    def test_explicit_roots_have_no_user_language_conflict_in_both_profiles(self):
        for version in ('private-chat-v1','private-chat-v2'):
            profile=ModelProfile(prompt_version=version);original=profile.system_prompt
            for lang,name in (('ru','Russian'),('en','English')):
                root=system_prompt_for_reply(profile,lang)
                self.assertIn('Reply in '+name+' only.',root)
                self.assertNotIn("Reply in the user's language.",root)
                self.assertIn('overrides',root)
                self.assertEqual(profile.system_prompt,original)
            self.assertEqual(system_prompt_for_reply(profile,None),original)


class LanguagePolicyProtocolTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_inference.ProtocolTests.asyncSetUp
    asyncTearDown=test_inference.ProtocolTests.asyncTearDown

    async def job(self,language='en',legacy=False):
        profile=self.adapter.profile;doctor=await self.adapter.doctor()
        messages=[{'role':'system','content':profile.system_prompt},
                  {'role':'user','content':'Привет, расскажи в одном предложении, чем можешь помочь.'}]
        if legacy:messages[1:1]=language_messages(language)
        else:
            messages[0]['content']=system_prompt_for_reply(profile,language)
            messages[-1]['content']=user_content_for_reply(messages[-1]['content'],language)
        job={'profile':profile.to_dict(),'context':{
            'messages':messages,'input_token_upper_bound':upper_bound(messages),
            'model_identity':asdict(doctor.identity),'reply_language':language,
            'language_policy':'reply-language-v1' if legacy else 'reply-language-v4'}}
        if not legacy:
            original='Привет, расскажи в одном предложении, чем можешь помочь.'
            job['context']['original_user_content']=original
            job['context']['language_hint']=language_hint_metadata(original,language)
        return job

    async def checkpoint(self,value):pass

    async def test_new_english_root_is_sent_unchanged_over_real_loopback_http(self):
        job=await self.job();before=deepcopy(job)
        answer=await self.adapter.generate(job,self.checkpoint)
        self.assertEqual(answer.status,'completed')
        self.assertEqual(self.server.requests[-1]['messages'],before['context']['messages'])
        self.assertEqual(job,before)
        systems=[m for m in self.server.requests[-1]['messages'] if m['role']=='system']
        self.assertEqual(len(systems),1)
        self.assertIn('RESPONSE LANGUAGE: English.',systems[0]['content'])
        self.assertNotIn("Reply in the user's language.",systems[0]['content'])

    async def test_legacy_v1_language_snapshot_is_dispatched_without_rewriting(self):
        job=await self.job(legacy=True);before=deepcopy(job)
        await self.adapter.generate(job,self.checkpoint)
        self.assertEqual(self.server.requests[-1]['messages'],before['context']['messages'])
        self.assertEqual(job,before)
        self.assertIn("Reply in the user's language.",job['context']['messages'][0]['content'])

    async def test_tampered_policy_root_or_legacy_language_never_dispatches(self):
        original=await self.job();legacy=await self.job(legacy=True)
        cases=[]
        root=deepcopy(original);root['context']['messages'][0]['content']=ModelProfile().system_prompt;cases.append(root)
        policy=deepcopy(original);policy['context']['language_policy']='unknown';cases.append(policy)
        missing=deepcopy(original);missing['context'].pop('reply_language');cases.append(missing)
        mismatch=deepcopy(legacy);mismatch['context']['reply_language']='ru';cases.append(mismatch)
        for job in cases:
            job['context']['input_token_upper_bound']=upper_bound(job['context']['messages'])
            with self.assertRaises(InferenceError) as caught:await self.adapter.generate(job,self.checkpoint)
            self.assertFalse(caught.exception.uncertain)
        self.assertEqual(self.server.requests,[])

    async def test_stored_v1_history_and_replay_survive_new_language_admission(self):
        profile=self.adapter.profile;doctor=await self.adapter.doctor();text='Old Russian request.'
        plan=ContextBuilder(profile,doctor.identity).build(self.repo.context_candidates(self.owner,self.chat),text,reply_language='en')
        receipt=self.repo.accept_message(self.owner,self.chat,text,expected_revision=0,key='legacy-key',context=plan)
        with self.repo.database.connect(write=True) as db:
            context=json.loads(db.execute('SELECT context_json FROM generations WHERE id=?',(receipt.generation_id,)).fetchone()[0])
            context['messages'][0]['content']=profile.system_prompt
            context['messages'][-1]['content']=context.pop('original_user_content')
            context.pop('language_hint')
            context['messages'][1:1]=language_messages('en')
            context['language_policy']='reply-language-v1'
            context['input_token_upper_bound']=upper_bound(context['messages'])
            db.execute('UPDATE generations SET context_json=? WHERE id=?',(json.dumps(context),receipt.generation_id))
        # Synthetic fixture simulates a pre-upgrade completed job, not production rewriting.
        with self.repo.worker_session() as worker:
            worker.claim_next();worker.finish(receipt.generation_id,content='Legacy answer.')
        before=self.repo.get_generation(self.owner,receipt.generation_id)
        replay=self.repo.replay_message(self.owner,self.chat,text,expected_revision=0,key='legacy-key',reply_language='en')
        self.assertTrue(replay.replayed);self.assertEqual(replay.generation_id,receipt.generation_id)
        plan=ContextBuilder(profile,doctor.identity).build(self.repo.context_candidates(self.owner,self.chat),'New turn.',reply_language='en')
        new=self.repo.accept_message(self.owner,self.chat,'New turn.',expected_revision=2,key='new-key',context=plan)
        self.assertEqual(self.repo.get_generation(self.owner,receipt.generation_id),before)
        self.assertEqual(self.repo.get_generation(self.owner,new.generation_id)['context']['language_policy'],'reply-language-v4')
