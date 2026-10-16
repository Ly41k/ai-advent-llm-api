"""Synthetic lexical counterexample, not reconstruction of the rejected Mac text."""
import json
import re
import unittest

import test_pipeline as fixtures
from bublik_developer.baseline import BaselineQwen,baseline_schema,validate_baseline_output
from bublik_developer.contracts import Role
from bublik_developer.generation import CLAIM_TEXT_PATTERNS,ModelOutputError,output_schema,validate_output


class ClaimStringBoundaryTests(unittest.TestCase):
    def test_pattern_itself_bounds_length_and_ru_start_for_both_modes(self):
        from jsonschema import Draft202012Validator
        for language, letter in (('ru', 'Я'), ('en', 'a')):
            doc=fixtures.documentation_context(language)
            doc['evidence'][0]['quote']=letter*600+' Инструмент git_diff: правило. git_diff: правило.'
            single={**doc,'documentation_question':doc['question'],'git_facts':[]}
            for schema,validator,role,context,is_single in (
                (output_schema(Role.DOCUMENTATION,doc),validate_output,Role.DOCUMENTATION,doc,False),
                (baseline_schema(Role.MAIN,single),validate_baseline_output,Role.MAIN,single,True)):
                server=Draft202012Validator(schema)
                for size in (0,1,599,600,601,2000):
                    text=letter*size
                    # Check the regex itself: independent of maxLength handling.
                    for branch in schema['oneOf']:
                        pattern=branch['properties']['claims']['items']['properties']['text']['pattern']
                        self.assertEqual(bool(re.fullmatch(pattern,text)),1<=size<=600)
                    frame={'status':'answered','language':language,'claims':[{'text':text,'evidence_ids':['e1']}]}
                    if is_single:frame['git_fact_ids']=[]
                    self.assertEqual(server.is_valid(frame),1<=size<=600)
                    if 1<=size<=600:self.assertEqual(validator(role,frame,context),frame)
                    else:
                        with self.assertRaises(ModelOutputError):validator(role,frame,context)
                if language=='ru':
                    for text in ('git_diff: правило.', ' Я', '🙂Я'):
                        frame={'status':'answered','language':'ru','claims':[{'text':text,'evidence_ids':['e1']}]}
                        if is_single:frame['git_fact_ids']=[]
                        self.assertFalse(server.is_valid(frame))
                        with self.assertRaises(ModelOutputError) as raised:validator(role,frame,context)
                        self.assertEqual(raised.exception.validation_reason,'claim_text_start')
                    frame['claims'][0]['text']='Инструмент git_diff: правило.'
                    self.assertTrue(server.is_valid(frame));self.assertEqual(validator(role,frame,context),frame)

    def test_old_raw_pattern_can_absorb_a_second_json_claim_but_new_pattern_cannot(self):
        russian='Содержимое untracked файлов не читается.'
        english='Untracked file content is not read.'
        crossing=russian+'", "evidence_ids": ["e1"]}, {"text": "'+english
        historical=r'^([^А-Яа-яЁё]*[А-Яа-яЁё])+[^А-Яа-яЁё]*$'
        self.assertIsNotNone(re.fullmatch(historical,crossing))
        # A raw converted string could lexically consume two physical JSON items.
        wire='{"status":"answered","language":"ru","claims":[{"text":"'+crossing+'","evidence_ids":["e2"]}]}'
        decoded=json.loads(wire);self.assertEqual(len(decoded['claims']),2)
        self.assertEqual(decoded['claims'][1]['text'],english)
        self.assertIsNone(re.fullmatch(CLAIM_TEXT_PATTERNS['ru'],crossing))
        for text in (russian,english):
            lang='ru' if text==russian else 'en'
            self.assertIsNotNone(re.fullmatch(CLAIM_TEXT_PATTERNS[lang],text))

    def test_schema_and_both_validators_reject_quote_escape_and_line_controls_without_repair(self):
        unsafe=['"','\\','\n','\r','\t','\x00','\x1f','\x7f','\x85','\u2028','\u2029']
        for language in ('ru','en'):
            doc=fixtures.documentation_context(language)
            single={**doc,'documentation_question':doc['question'],'git_facts':[]}
            for schema,validator,role,context,is_single in (
                (output_schema(Role.DOCUMENTATION,doc),validate_output,Role.DOCUMENTATION,doc,False),
                (baseline_schema(Role.MAIN,single),validate_baseline_output,Role.MAIN,single,True)):
                for char in unsafe:
                    text=('История использует SQLite' if language=='ru' else 'History uses SQLite')+char+'.'
                    frame={'status':'answered','language':language,'claims':[{'text':text,'evidence_ids':['e1']}]}
                    if is_single:frame['git_fact_ids']=[]
                    before=json.dumps(frame,ensure_ascii=False)
                    for branch in schema['oneOf']:
                        spec=branch['properties']['claims']['items']['properties']['text']
                        self.assertIsNone(re.search(spec['pattern'],text))
                        self.assertIsNotNone(re.search(spec['not']['pattern'],text))
                    with self.assertRaises(ModelOutputError) as raised:validator(role,frame,context)
                    self.assertEqual(raised.exception.validation_reason,'claim_text_encoding')
                    self.assertEqual(json.dumps(frame,ensure_ascii=False),before)
                    # End-anchor regex semantics must not permit a final newline.
                    trailing=text[:-2]+char
                    for branch in schema['oneOf']:
                        spec=branch['properties']['claims']['items']['properties']['text']
                        self.assertIsNotNone(re.search(spec['not']['pattern'],trailing))

    def test_source_ascii_prefix_retains_exact_name_and_total_600_boundary_both_modes(self):
        from jsonschema import Draft202012Validator
        doc=fixtures.documentation_context('ru')
        doc['evidence'][0]['quote']='Main uses checked claims. Documentation supplies excerpts.'
        single={**doc,'documentation_question':doc['question'],'git_facts':[]}
        for cls,role,context,is_single in (
            (fixtures.Qwen,Role.DOCUMENTATION,doc,False),
            (BaselineQwen,Role.MAIN,single,True)):
            schema=cls.schema_builder(role,context);server=Draft202012Validator(schema)
            for size in (6,599,600,601):
                text='Main '+'Я'*(size-5)
                frame={'status':'answered','language':'ru','claims':[{'text':text,'evidence_ids':['e1']}]}
                if is_single:frame['git_fact_ids']=[]
                for branch in schema['oneOf']:
                    pattern=branch['properties']['claims']['items']['properties']['text']['pattern']
                    self.assertEqual(bool(re.fullmatch(pattern,text)),size<=600)
                self.assertEqual(server.is_valid(frame),size<=600)
                if size<=600:self.assertIs(cls.output_validator(role,frame,context),frame)
                else:
                    with self.assertRaises(ModelOutputError):cls.output_validator(role,frame,context)
            frame['claims'][0]['text']='Main получает проверенные утверждения.'
            transport,calls=fixtures.GenerationTests().server(frame);lease=fixtures.FakeLease();client=cls(lease,transport=transport)
            self.assertEqual(client.generate(role,context),frame)
            self.assertTrue(lease.finished);self.assertEqual(sum(e=='/api/chat' for e,_ in calls),1)
            self.assertEqual(frame['claims'][0]['text'],'Main получает проверенные утверждения.')
            # Script guard is retained even when the backend ignores its format.
            frame['claims'][0]['text']='Мain получает проверенные утверждения.'
            with self.assertRaises(ModelOutputError) as error:cls.output_validator(role,frame,context)
            self.assertEqual(error.exception.validation_reason,'identifier_script_mismatch')

    def test_source_prefix_is_bounded_source_only_not_question_or_rubric(self):
        from bublik_developer.generation import source_ascii_prefixes,claim_text_pattern,SOURCE_PREFIX_LIMIT
        doc=fixtures.documentation_context('ru');doc['question']='Does QuestionOnly operate?'
        names=['Prefix'+str(i) for i in range(40)]
        doc['evidence'][0]['quote']=' '.join(names)+' Prefix0 '+('Z'*33)
        self.assertEqual(source_ascii_prefixes(doc['evidence']),names[:SOURCE_PREFIX_LIMIT])
        pattern=claim_text_pattern('ru',doc['evidence'])
        self.assertIsNotNone(re.fullmatch(pattern,'Prefix0 работает.'))
        for text in ('QuestionOnly работает.','Prefix39 работает.',('Z'*33)+' работает.','Prefix0 works.','Prefix0: работает.'):
            self.assertIsNone(re.fullmatch(pattern,text))
        for text in ('Prefix0 Я"','Prefix0 Я\\','Prefix0 Я\n','Prefix0 Я\x00'):
            self.assertIsNone(re.fullmatch(pattern,text))
        self.assertIsNotNone(re.fullmatch(pattern,'Компонент Prefix39 работает.'))

    def test_prefix_cannot_bypass_app_start_or_language_when_grammar_is_ignored(self):
        from bublik_developer.baseline import BaselineQwen
        doc=fixtures.documentation_context('ru');doc['evidence'][0]['quote']='Main has checked claims.'
        doc['question']='Does QuestionOnly work?'
        single={**doc,'documentation_question':doc['question'],'git_facts':[]}
        for cls,role,context,is_single in ((fixtures.Qwen,Role.DOCUMENTATION,doc,False),(BaselineQwen,Role.MAIN,single,True)):
            for text,reason in [('QuestionOnly работает.','claim_text_start'),('Main works.','claim_language')]:
                frame={'status':'answered','language':'ru','claims':[{'text':text,'evidence_ids':['e1']}]}
                if is_single:frame['git_fact_ids']=[]
                transport,calls=fixtures.GenerationTests().server(frame);lease=fixtures.FakeLease();client=cls(lease,transport=transport)
                with self.assertRaises(ModelOutputError) as error:client.generate(role,context)
                self.assertEqual(error.exception.validation_reason,reason)
                self.assertTrue(lease.finished);self.assertFalse(lease.invalidated)
                self.assertEqual(sum(e=='/api/chat' for e,_ in calls),1)
                self.assertNotIn(text,json.dumps(client.metrics,ensure_ascii=False))
