"""Counts-only rejection diagnostics, including worker/parent propagation."""
from contextlib import nullcontext
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_pipeline as fixtures
from bublik_developer.baseline import BaselineQwen
from bublik_developer.contracts import ContextEnvelope, Role
from bublik_developer.generation import Qwen, ModelOutputError, valid_language_details
from bublik_developer.inference_tasks import valid_metrics
from bublik_developer.model_worker import execute


class RejectionDiagnosticsTests(unittest.TestCase):
    def test_only_first_wrong_script_claim_counts_are_returned_for_both_clients(self):
        for language,bad in [('ru','LATIN-CANARY-9473 中文'),('en','РУССКИЙ-МАРКЕР-9473')]:
            context=fixtures.documentation_context(language)
            for cls,role,single in ((Qwen,Role.DOCUMENTATION,False),(BaselineQwen,Role.MAIN,True)):
                frame={'status':'answered','language':language,'claims':[
                    {'text':'История использует SQLite.' if language=='ru' else 'History uses SQLite.','evidence_ids':['e1']},
                    {'text':bad,'evidence_ids':['e1']}]}
                task_context={**context,'documentation_question':context['question'],'git_facts':[]} if single else context
                if single:frame['git_fact_ids']=[]
                transport,calls=fixtures.GenerationTests().server(frame);lease=fixtures.FakeLease();client=cls(lease,transport=transport)
                with self.assertRaises(ModelOutputError) as raised:client.generate(role,task_context)
                self.assertEqual(raised.exception.validation_reason,'claim_language')
                details=client.metrics['output_validation_details']
                self.assertTrue(valid_language_details(details));self.assertTrue(valid_metrics(client.metrics))
                self.assertEqual(details['claim_index'],1);self.assertEqual(details['claim_count'],2)
                self.assertEqual(details['text_chars'],len(bad));self.assertEqual(details['evidence_ids'],['e1'])
                if language=='ru':
                    self.assertEqual(details['cyrillic_chars'],0);self.assertEqual(details['latin_chars'],11);self.assertEqual(details['other_letters'],2)
                self.assertNotIn(bad,json.dumps(client.metrics,ensure_ascii=False))
                self.assertTrue(lease.finished);self.assertFalse(lease.invalidated)
                with self.assertRaises(ModelOutputError):
                    client.output_validator(role,frame,task_context)
                self.assertEqual(sum(endpoint=='/api/chat' for endpoint,_ in calls),1)

    def test_parent_rejects_forged_or_unbounded_diagnostic_shapes(self):
        details={'format':'claim-script-counts-v1','expected_language':'ru','claim_index':0,'claim_count':1,
                 'text_chars':12,'cyrillic_chars':0,'latin_chars':10,'other_letters':0,'evidence_ids':['e1']}
        metrics={'llm_calls':1,'output_validation':'rejected','output_validation_reason':'claim_language','output_validation_details':details}
        self.assertTrue(valid_metrics(metrics))
        invalid=[{**details,'text':'PRIVATE-CLAIM-CANARY'}, {**details,'text_chars':601},
                 {**details,'claim_index':1}, {**details,'claim_count':True},
                 {**details,'latin_chars':-1}, {**details,'latin_chars':13},
                 {**details,'cyrillic_chars':1}, {**details,'expected_language':'de'},
                 {**details,'evidence_ids':['PRIVATE-ID']}, {**details,'evidence_ids':['e1','e1']},None]
        for value in invalid:self.assertFalse(valid_metrics({**metrics,'output_validation_details':value}))
        self.assertFalse(valid_metrics({**metrics,'output_validation':'passed'}))
        self.assertFalse(valid_metrics({**metrics,'output_validation_reason':'unsupported_identifier'}))

    def test_worker_preserves_counts_only_with_no_rejected_data_or_text(self):
        context=fixtures.documentation_context('ru');bad='WORKER-CANARY-9473'
        frame={'status':'answered','language':'ru','claims':[{'text':bad,'evidence_ids':['e1']}]}
        transport,calls=fixtures.GenerationTests().server(frame);lease=fixtures.FakeLease()
        payload={'root':'/synthetic','workspace_identity':['synthetic'],'project_id':'ai-advent-llm-api',
                 'role':'documentation','context':context,'context_digest':ContextEnvelope.seal(context).digest,
                 'final':True,'request_id':'a'*32,'task_id':'b'*32}
        with patch('bublik_developer.model_worker.ProjectWorkspace.open',return_value=SimpleNamespace(identity=('synthetic',))),\
             patch('bublik_developer.model_worker.ModelSession',return_value=SimpleNamespace(lease=lambda:nullcontext(lease))):
            reply=execute(payload,client_class=lambda owned_lease:Qwen(owned_lease,transport=transport))
        self.assertEqual(reply['data'],{});self.assertEqual(reply['error_code'],'invalid_model_output')
        self.assertTrue(valid_metrics(reply['metrics']))
        self.assertEqual(reply['metrics']['output_validation_details']['claim_index'],0)
        self.assertNotIn(bad,json.dumps(reply,ensure_ascii=False))
        self.assertEqual(sum(endpoint=='/api/chat' for endpoint,_ in calls),1)
