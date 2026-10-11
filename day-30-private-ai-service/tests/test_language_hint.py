"""Model-only language hint: frozen dispatch, budget and legacy compatibility."""
from copy import deepcopy
import unittest

from bublik_service.domain import InvalidInput, ModelProfile
from bublik_service.inference.context import ContextBuilder, upper_bound
from bublik_service.inference.ollama import InferenceError
from bublik_service.languages import system_prompt_for_reply, user_content_for_reply
import test_inference
import test_language_policy


class LanguageHintProtocolTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_inference.ProtocolTests.asyncSetUp
    asyncTearDown = test_inference.ProtocolTests.asyncTearDown
    job = test_language_policy.LanguagePolicyProtocolTests.job
    checkpoint = test_language_policy.LanguagePolicyProtocolTests.checkpoint

    async def test_v4_original_and_hint_are_dispatched_without_late_rewriting(self):
        job = await self.job()
        before = deepcopy(job)
        await self.adapter.generate(job, self.checkpoint)
        self.assertEqual(self.server.requests[-1]['messages'], before['context']['messages'])
        self.assertEqual(job, before)
        self.assertEqual(job['context']['messages'][-1]['content'],
                         user_content_for_reply(job['context']['original_user_content'], 'en'))

    async def test_v2_frozen_job_remains_dispatchable_without_a_hint(self):
        job = await self.job()
        context = job['context']
        context['messages'][-1]['content'] = context.pop('original_user_content')
        context.pop('language_hint')
        context['language_policy'] = 'reply-language-v2'
        context['input_token_upper_bound'] = upper_bound(context['messages'])
        before = deepcopy(job)
        await self.adapter.generate(job, self.checkpoint)
        self.assertEqual(self.server.requests[-1]['messages'], before['context']['messages'])
        self.assertEqual(job, before)

    async def test_tampered_hint_or_original_is_rejected_before_dispatch(self):
        base = await self.job()
        variants = []
        missing = deepcopy(base); missing['context'].pop('original_user_content'); variants.append(missing)
        original = deepcopy(base); original['context']['original_user_content'] += 'changed'; variants.append(original)
        wrong = deepcopy(base); wrong['context']['messages'][-1]['content'] += 'changed'; variants.append(wrong)
        role = deepcopy(base); role['context']['messages'][-1]['role'] = 'assistant'; variants.append(role)
        metadata = deepcopy(base); metadata['context']['language_hint']['rendered_sha256'] = '0' * 64; variants.append(metadata)
        for job in variants:
            job['context']['input_token_upper_bound'] = upper_bound(job['context']['messages'])
            with self.assertRaises(InferenceError) as caught:
                await self.adapter.generate(job, self.checkpoint)
            self.assertFalse(caught.exception.uncertain)
        self.assertEqual(self.server.requests, [])

    async def test_hint_is_budgeted_before_admission_at_window_boundary(self):
        doctor = await self.adapter.doctor()
        profile = self.adapter.profile
        root = {'role': 'system', 'content': system_prompt_for_reply(profile, 'en')}
        budget = profile.num_ctx - profile.max_output - profile.margin
        size = budget - upper_bound([root, {'role': 'user', 'content': ''}])
        original = 'x' * size
        self.assertEqual(upper_bound([root, {'role': 'user', 'content': original}]), budget)
        builder = ContextBuilder(profile, doctor.identity)
        with self.assertRaises(InvalidInput) as caught:
            builder.build({'messages': []}, original, reply_language='en')
        self.assertEqual(caught.exception.code, 'context_budget_exceeded')
        shorter = original[:-len(user_content_for_reply('', 'en'))]
        plan = builder.build({'messages': []}, shorter, reply_language='en')
        self.assertEqual(plan.input_token_upper_bound, budget)
        self.assertEqual(user_content_for_reply(original, None), original)
