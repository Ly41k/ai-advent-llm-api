import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import ROOT, SupportError, parse_json
from support_agent import prepare, render, validate_plan


class ActionEvidence(unittest.TestCase):
    def setUp(self):
        ticket=parse_json((ROOT/'data/tickets.json').read_bytes())[0]
        user=parse_json((ROOT/'data/users.json').read_bytes())[0]
        self.payload=prepare('Почему не работает авторизация?',ticket,user)
        self.plan={'assessment':'session_expired',
                   'document_facts':[{'source_id':'DOC-ERRORS','quote':'| 401 | authentication_required / expired credential |'}],
                   'context_facts':[{'key':'ticket.observed_error','quote':'HTTP 401 authentication_required'},
                                    {'key':'user.device','quote':'Android Chrome'},
                                    {'key':'ticket.session_state','quote':'expired'}],
                   'action_ids':['sign_in','check_auth']}

    def test_application_evidence_is_explicit_and_model_plan_unchanged(self):
        original=copy.deepcopy(self.plan)
        validate_plan(self.plan,self.payload)
        result=render(self.plan,self.payload,{'mode':'offline_test'})
        self.assertEqual(self.plan,original)
        self.assertEqual(result['document_facts'],original['document_facts'])
        sign_in=next(e for e in result['application_evidence'] if e['action_id']=='sign_in')
        self.assertEqual(sign_in['source_id'],'FAQ-AUTH')
        self.assertEqual(sign_in['assigned_by'],'application')
        self.assertIn('добавлено приложением',result['answer'])
        self.assertTrue(all(s in {v['id'] for v in result['sources']} for r in result['recommendations'] for s in r['source_ids']))

    def test_model_fabrication_is_still_rejected(self):
        self.plan['document_facts'][0]['quote']='Invented authentication policy and password diagnosis.'
        with self.assertRaisesRegex(SupportError,'unsupported_document_fact'):
            validate_plan(self.plan,self.payload)

    def test_catalog_evidence_must_be_retrieved_and_match_action(self):
        for ids in ([],['DOC-FAKE'],['DOC-ERRORS']):
            changed=copy.deepcopy(self.payload)
            changed['allowed_actions']['sign_in']['source_ids']=ids
            with self.assertRaises(SupportError):
                validate_plan(self.plan,changed)


if __name__=='__main__':
    unittest.main(verbosity=2)
