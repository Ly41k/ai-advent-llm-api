"""Script constraints match the old validator; this is not a semantic language detector."""
import json
import re
import unittest

import test_pipeline as fixtures
from bublik_developer.baseline import BaselineQwen, baseline_schema, validate_baseline_output
from bublik_developer.contracts import Role
from bublik_developer.errors import DeveloperError
from bublik_developer.generation import Qwen, DOC_SCHEMA, output_schema, validate_output, ModelOutputError


TEXTS = ['', ' ', 'History uses SQLite.', 'История использует SQLite.', 'Ё', 'ё',
         'ІЇЄієї', '中文', '🙂', 'git_diff', 'SQLite\nИстория\n', 'History\nuses\nSQLite.',
         '"quoted"', '\\', '\r\n', 'Русский "quote" \\ path\n', 'a'*600, 'a'*601,
         'Я'*600, 'Я'*601, 'Я'+chr(0), chr(0), '\n', 'History uses SQLite.\n',
         'История использует SQLite.\n', 'History uses SQLite.\r',
         'История использует SQLite.\u2028', 'git_diff: правило по-русски.', 'Инструмент git_diff: правило.', ' Я', '🙂Я'] + [chr(n) for n in range(0x400,0x500)]


def contexts(language):
    doc=fixtures.documentation_context(language)
    doc['evidence'][0]['quote']='All literal test strings: '+ '\n'.join(TEXTS)
    single={**doc,'documentation_question':doc['question'],'git_facts':[]}
    return doc,single


class LanguageSchemaTests(unittest.TestCase):
    def test_pattern_matches_script_and_json_safe_line_check(self):
        for language in ('ru','en'):
            doc,single=contexts(language)
            for schema in (output_schema(Role.DOCUMENTATION,doc),baseline_schema(Role.MAIN,single)):
                for branch in schema['oneOf']:
                    spec=branch['properties']['claims']['items']['properties']['text']
                    pattern=spec['pattern']
                    for text in TEXTS:
                        expected=any('А'<=c<='я' or c in 'Ёё' for c in text)
                        if language=='en':expected=not expected
                        expected=expected and not any(c in ('"','\\','\x7f','\x85','\u2028','\u2029') or ord(c)<32 for c in text)
                        expected=expected and 1 <= len(text) <= 600
                        if language=='ru':expected=expected and bool(re.match(r'[А-Яа-яЁё]',text))
                        matched=bool(re.search(pattern,text)) and not re.search(spec['not']['pattern'],text)
                        self.assertEqual(bool(matched),expected,(language,repr(text)))

    def test_independent_jsonschema_and_application_agree_on_script_length_and_status(self):
        from jsonschema import Draft202012Validator
        for language in ('ru','en'):
            doc,single=contexts(language)
            for schema,validator,role,context,is_single in (
                (output_schema(Role.DOCUMENTATION,doc),validate_output,Role.DOCUMENTATION,doc,False),
                (baseline_schema(Role.MAIN,single),validate_baseline_output,Role.MAIN,single,True)):
                Draft202012Validator.check_schema(schema);server=Draft202012Validator(schema)
                for status in ('answered','partial','unknown'):
                    for text in TEXTS:
                        frame={'status':status,'language':language,'claims':[{'text':text,'evidence_ids':['e1']}]}
                        if is_single:frame['git_fact_ids']=[]
                        try:validator(role,frame,context);accepted=True
                        except DeveloperError:accepted=False
                        self.assertEqual(server.is_valid(frame),accepted,(language,status,repr(text)))
                unknown={'status':'unknown','language':language,'claims':[]}
                if is_single:unknown['git_fact_ids']=[]
                self.assertTrue(server.is_valid(unknown));self.assertEqual(validator(role,unknown,context),unknown)

    def test_constraint_is_dispatched_for_both_modes_without_mutating_base_schema(self):
        for language in ('ru','en'):
            doc=fixtures.documentation_context(language)
            single={**doc,'documentation_question':doc['question'],'git_facts':[]}
            for cls,role,context,is_single in ((Qwen,Role.DOCUMENTATION,doc,False),(BaselineQwen,Role.MAIN,single,True)):
                frame={'status':'answered','language':language,'claims':[{
                    'text':'История использует SQLite.' if language=='ru' else 'History uses SQLite.',
                    'evidence_ids':['e1']}]}
                if is_single:frame['git_fact_ids']=[]
                transport,calls=fixtures.GenerationTests().server(frame)
                client=cls(fixtures.FakeLease(),transport=transport)
                self.assertEqual(client.generate(role,context),frame)
                chat=[body for endpoint,body in calls if endpoint=='/api/chat'];self.assertEqual(len(chat),1)
                self.assertEqual(chat[0]['format'],client.schema_builder(role,context))
                for branch in chat[0]['format']['oneOf']:
                    self.assertIn('pattern',branch['properties']['claims']['items']['properties']['text'])
        self.assertNotIn('pattern',DOC_SCHEMA['properties']['claims']['items']['properties']['text'])

    def test_ignored_constraint_still_rejects_wrong_script_without_text_leak_or_replay(self):
        for language in ('ru','en'):
            doc=fixtures.documentation_context(language)
            single={**doc,'documentation_question':doc['question'],'git_facts':[]}
            for cls,role,context,is_single in ((Qwen,Role.DOCUMENTATION,doc,False),(BaselineQwen,Role.MAIN,single,True)):
                text='ENGLISH-ONLY-CANARY-9473' if language=='ru' else 'РУССКИЙ-МАРКЕР-9473'
                frame={'status':'answered','language':language,'claims':[{'text':text,'evidence_ids':['e1']}]}
                if is_single:frame['git_fact_ids']=[]
                transport,calls=fixtures.GenerationTests().server(frame);lease=fixtures.FakeLease();client=cls(lease,transport=transport)
                with self.assertRaises(ModelOutputError) as raised:client.generate(role,context)
                self.assertEqual(raised.exception.validation_reason,'claim_language')
                self.assertTrue(lease.finished);self.assertFalse(lease.invalidated)
                self.assertNotIn(text,json.dumps(client.metrics))
                with self.assertRaises(DeveloperError):client.generate(role,context)
                self.assertEqual(sum(endpoint=='/api/chat' for endpoint,_ in calls),1)
