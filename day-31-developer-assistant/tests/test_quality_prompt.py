"""Prompt parity/admission only; synthetic replies do not establish model quality."""
import json
from pathlib import Path
import unittest

import test_pipeline as fixtures
from bublik_developer.baseline import BaselineQwen, validate_baseline_output
from bublik_developer.contracts import Role
from bublik_developer.generation import Qwen, ModelOutputError, SOURCE_RULES_EN, SOURCE_RULES_RU, context_budget, validate_output

ROOT=Path(__file__).resolve().parents[1]


class QualityPromptTests(unittest.TestCase):
    def test_single_and_multi_share_the_same_source_coverage_rules(self):
        for language,rules in (('ru',SOURCE_RULES_RU),('en',SOURCE_RULES_EN)):
            context=fixtures.documentation_context(language)
            doc=Qwen.__new__(Qwen).system_prompt(Role.DOCUMENTATION,context)
            baseline=BaselineQwen.__new__(BaselineQwen).system_prompt(Role.MAIN,context)
            self.assertIn(rules,doc)
            self.assertIn(rules,baseline)
            self.assertNotIn('quartz_retention_54827',rules)
            self.assertNotIn('project/docs/',rules)

    def test_prior_and_native_input_budgets_preserve_all_evidence(self):
        for filename,count in (('prompt_input_regression_v073.json',40),('prompt_input_regression_v083.json',54),('prompt_input_regression_v085.json',49),('prompt_input_regression_v087.json',33),('prompt_input_regression_v088.json',11),('prompt_input_regression_v089.json',33),('prompt_input_regression_v090.json',21),('prompt_input_regression_v091.json',1),('prompt_input_regression_v092.json',55),('prompt_input_regression_v093.json',55),('prompt_input_regression_v094.json',1),('prompt_input_regression_v095.json',11),('prompt_input_regression_v096.json',17),('prompt_input_regression_v097.json',55)):
            fixture=json.loads((ROOT/'evaluation'/filename).read_text())
            self.assertEqual(len(fixture['inputs']),count)
            for row in fixture['inputs']:
                cls,role=((Qwen,Role.DOCUMENTATION) if row['mode']=='multi_documentation' else
                          (Qwen,Role.MAIN) if row['mode']=='multi_main' else (BaselineQwen,Role.MAIN))
                client=cls.__new__(cls);context=row['context'];client.context_validator(role,context)
                messages=[{'role':'system','content':client.system_prompt(role,context)},
                          {'role':'user','content':json.dumps(context,ensure_ascii=False,sort_keys=True)}]
                self.assertLessEqual(context_budget(messages)['estimated_total'],8192,(row['case_id'],row['mode']))
                self.assertEqual(json.loads(messages[1]['content']),context)
                self.assertNotIn(row['case_id'],messages[0]['content'])

    def test_valid_partial_is_retained_not_automatically_upgraded_or_retried(self):
        context=fixtures.documentation_context()
        reply={'status':'partial','language':'en','claims':[{'text':'Memory history uses SQLite.','evidence_ids':['e1']}]}
        transport,calls=fixtures.GenerationTests().server(reply)
        client=Qwen(fixtures.FakeLease(),transport=transport)
        value=client.generate(Role.DOCUMENTATION,context)
        self.assertEqual(value,reply)
        self.assertEqual(client.metrics['output_validation'],'passed')
        self.assertEqual(sum(endpoint=='/api/chat' for endpoint,_ in calls),1)

    def test_question_identifier_is_not_support_even_in_a_refusal_claim(self):
        for language in ('ru', 'en'):
            context=fixtures.documentation_context(language)
            context['question']='What are the ghost_cache_31415 retention parameters?'
            text=('Параметры ghost_cache_31415 не описаны.' if language=='ru' else
                  'The ghost_cache_31415 retention parameters are not documented.')
            refusal={'status':'answered','language':language,'claims':[{
                'text':text,'evidence_ids':['e1']}]}
            single_context={**context,'documentation_question':context['question'],'git_facts':[]}
            for cls,role,value,task_context in (
                (Qwen,Role.DOCUMENTATION,refusal,context),
                (BaselineQwen,Role.MAIN,{**refusal,'git_fact_ids':[]},single_context)):
                transport,calls=fixtures.GenerationTests().server(value)
                lease=fixtures.FakeLease();client=cls(lease,transport=transport)
                with self.subTest(language=language,role=role):
                    with self.assertRaises(ModelOutputError) as raised:
                        client.generate(role,task_context)
                    self.assertEqual(raised.exception.validation_reason,'unsupported_identifier')
                    self.assertTrue(lease.started and lease.finished)
                    self.assertFalse(lease.invalidated)
                    self.assertEqual(client.metrics['output_validation_reason'],'unsupported_identifier')
                    self.assertEqual(client.metrics['llm_calls'],1)
                    self.assertEqual(sum(endpoint=='/api/chat' for endpoint,_ in calls),1)
                    self.assertNotIn('ghost_cache_31415',json.dumps(client.metrics,ensure_ascii=False))
                unknown={'status':'unknown','language':language,'claims':[]}
                if cls is BaselineQwen:unknown['git_fact_ids']=[]
                self.assertEqual(client.output_validator(role,unknown,task_context),unknown)

    def test_transport_grammar_emits_prose_before_citations_for_both_modes(self):
        for cls,role in ((Qwen,Role.DOCUMENTATION),(BaselineQwen,Role.MAIN)):
            for language in ('ru','en'):
                context=fixtures.documentation_context(language)
                reply={'status':'unknown','language':language,'claims':[]}
                if cls is BaselineQwen:
                    context={**context,'documentation_question':context['question'],'git_facts':[]}
                    reply['git_fact_ids']=[]
                transport,calls=fixtures.GenerationTests().server(reply)
                client=cls(fixtures.FakeLease(),transport=transport)
                client.generate(role,context)
                body=next(body for endpoint,body in calls if endpoint=='/api/chat')
                for branch in body['format']['oneOf']:
                    item=branch['properties']['claims']['items']
                    self.assertEqual(item['required'],['text','evidence_ids'])
                    self.assertEqual(list(item['properties']),['text','evidence_ids'])
                    self.assertEqual(item['properties']['evidence_ids']['items']['enum'],['e1'])
                    self.assertIn('{0,599}' if language=='ru' else '{1,600}',item['properties']['text']['pattern'])
                self.assertEqual(sum(endpoint=='/api/chat' for endpoint,_ in calls),1)

    def test_supported_ascii_names_with_substituted_letters_reject_both_modes(self):
        context=fixtures.documentation_context('ru')
        context['evidence'][0]['quote']='Main calls API and foo_worker. Проверенные сведения.'
        single={**context,'documentation_question':context['question'],'git_facts':[]}
        for text in ('Компонент Мain.', 'Компонент Mаin.', 'Компонент АPI.', 'Компонент foo_wоrker.'):
            reply={'status':'answered','language':'ru','claims':[{'text':text,'evidence_ids':['e1']}]}
            for validator,role,value,task_context in (
                (validate_output,Role.DOCUMENTATION,reply,context),
                (validate_baseline_output,Role.MAIN,{**reply,'git_fact_ids':[]},single)):
                with self.subTest(text=text,role=role):
                    with self.assertRaises(ModelOutputError) as raised:
                        validator(role,value,task_context)
                    self.assertEqual(raised.exception.validation_reason,'identifier_script_mismatch')

    def test_exact_ascii_names_and_Russian_words_are_preserved_without_rewrite(self):
        context=fixtures.documentation_context('ru')
        context['evidence'][0]['quote']='Main uses foo_worker and API. Проверенные сведения.'
        for text in ('Компонент Main.', 'Вызов foo_worker через API.', 'Модель читает данные.'):
            reply={'status':'answered','language':'ru','claims':[{'text':text,'evidence_ids':['e1']}]}
            self.assertIs(validate_output(Role.DOCUMENTATION,reply,context),reply)
            single={**context,'documentation_question':context['question'],'git_facts':[]}
            self.assertEqual(validate_baseline_output(Role.MAIN,{**reply,'git_fact_ids':[]},single)['claims'],reply['claims'])
        # Limited script integrity is neither full transliteration nor entailment.
        from bublik_developer.generation import substituted_ascii_name
        self.assertFalse(substituted_ascii_name('Слово Мeta.','Main'))
        self.assertFalse(substituted_ascii_name('Название Мэйн.','Main'))

    def test_substituted_name_terminal_reply_closes_lease_without_text_repair_or_retry(self):
        context=fixtures.documentation_context('ru')
        context['evidence'][0]['quote']='Main uses checked claims.'
        reply={'status':'answered','language':'ru','claims':[{'text':'Компонент Мain.','evidence_ids':['e1']}]}
        transport,calls=fixtures.GenerationTests().server(reply)
        lease=fixtures.FakeLease();client=Qwen(lease,transport=transport)
        with self.assertRaises(ModelOutputError) as raised:
            client.generate(Role.DOCUMENTATION,context)
        self.assertEqual(raised.exception.validation_reason,'identifier_script_mismatch')
        self.assertTrue(lease.started and lease.finished)
        self.assertFalse(lease.invalidated)
        self.assertEqual(client.metrics['output_validation_reason'],'identifier_script_mismatch')
        self.assertEqual(client.metrics['llm_calls'],1)
        self.assertEqual(sum(endpoint=='/api/chat' for endpoint,_ in calls),1)
        self.assertNotIn('Мain',json.dumps(client.metrics,ensure_ascii=False))
