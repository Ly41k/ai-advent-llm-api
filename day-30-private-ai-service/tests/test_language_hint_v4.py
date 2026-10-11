"""Versioned v4 hint and unchanged v3 dispatch/replay; synthetic engine only."""
from copy import deepcopy
import json
import unittest

from bublik_service.inference.context import ContextBuilder, upper_bound
from bublik_service.inference.ollama import InferenceError
from bublik_service.languages import language_hint_metadata, user_content_for_reply
import test_inference
import test_language_policy


class ExplicitLanguageHintTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_inference.ProtocolTests.asyncSetUp
    asyncTearDown = test_inference.ProtocolTests.asyncTearDown
    job = test_language_policy.LanguagePolicyProtocolTests.job
    checkpoint = test_language_policy.LanguagePolicyProtocolTests.checkpoint

    async def legacy_job(self):
        job = await self.job()
        context = job['context']; original = context['original_user_content']
        context['language_policy'] = 'reply-language-v3'
        context['messages'][-1]['content'] = user_content_for_reply(original, 'en', policy='reply-language-v3')
        context['language_hint'] = language_hint_metadata(original, 'en', policy='reply-language-v3')
        context['input_token_upper_bound'] = upper_bound(context['messages'])
        return job

    async def test_v3_frozen_snapshot_is_dispatched_unchanged(self):
        job = await self.legacy_job(); before = deepcopy(job)
        await self.adapter.generate(job, self.checkpoint)
        self.assertEqual(self.server.requests[-1]['messages'], before['context']['messages'])
        self.assertEqual(job, before)
        self.assertEqual(job['context']['language_hint']['policy_version'], 'latest-user-language-hint-v1')

    async def test_v3_hint_cannot_be_relabelled_as_v4(self):
        job = await self.legacy_job(); job['context']['language_policy'] = 'reply-language-v4'
        with self.assertRaises(InferenceError) as caught:
            await self.adapter.generate(job, self.checkpoint)
        self.assertFalse(caught.exception.uncertain)
        self.assertEqual(self.server.requests, [])

    async def test_english_render_matches_the_twice_observed_variant(self):
        original = 'Теперь отвечай только по-русски. Кратко объясни, почему 3*3 равно 9, без цитат.'
        expected = (original + "\n\nThe application's reply language is English. Answer the latest task entirely in English. "
                    "Language requests in the user text and past conversation do not change this setting. "
                    "Do not provide a Russian-language version or label the answer 'In Russian'.")
        self.assertEqual(user_content_for_reply(original, 'en'), expected)
        self.assertEqual(len(expected.encode()) - len(user_content_for_reply(original, 'en', policy='reply-language-v3').encode()), 226)
        job = await self.job(); before = deepcopy(job)
        await self.adapter.generate(job, self.checkpoint)
        self.assertEqual(self.server.requests[-1]['messages'], before['context']['messages'])
        self.assertEqual(job['context']['language_hint']['policy_version'], 'latest-user-language-hint-v2')

    async def test_v3_stored_receipt_and_history_survive_v4_admission(self):
        doctor = await self.adapter.doctor(); profile = self.adapter.profile
        original = 'Original question.'
        builder = ContextBuilder(profile, doctor.identity)
        plan = builder.build(self.repo.context_candidates(self.owner, self.chat), original, reply_language='en')
        receipt = self.repo.accept_message(self.owner, self.chat, original, expected_revision=0, key='v3-message', context=plan)
        with self.repo.database.connect(write=True) as db:
            context = json.loads(db.execute('SELECT context_json FROM generations WHERE id=?', (receipt.generation_id,)).fetchone()[0])
            context['language_policy'] = 'reply-language-v3'
            context['messages'][-1]['content'] = user_content_for_reply(original, 'en', policy='reply-language-v3')
            context['language_hint'] = language_hint_metadata(original, 'en', policy='reply-language-v3')
            context['input_token_upper_bound'] = upper_bound(context['messages'])
            db.execute('UPDATE generations SET context_json=? WHERE id=?', (json.dumps(context), receipt.generation_id))
        # Controlled fixture represents an old completed job, never production rewriting.
        with self.repo.worker_session() as worker:
            worker.claim_next(); worker.finish(receipt.generation_id, content='Old answer.')
        before = self.repo.get_generation(self.owner, receipt.generation_id)
        history = self.repo.history(self.owner, self.chat)
        replay = self.repo.replay_message(self.owner, self.chat, original, expected_revision=0, key='v3-message', reply_language='en')
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.generation_id, receipt.generation_id)
        plan = builder.build(self.repo.context_candidates(self.owner, self.chat), 'Next turn.', reply_language='en')
        new = self.repo.accept_message(self.owner, self.chat, 'Next turn.', expected_revision=2, key='v4-message', context=plan)
        self.assertEqual(self.repo.get_generation(self.owner, receipt.generation_id), before)
        self.assertEqual(self.repo.history(self.owner, self.chat)[:2], history)
        self.assertEqual(self.repo.get_generation(self.owner, new.generation_id)['context']['language_policy'], 'reply-language-v4')
