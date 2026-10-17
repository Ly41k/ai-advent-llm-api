"""One explicit model repair; no quote normalization and no real HTTP calls."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import test_openai_adapter as native_tests
import test_eof_resume as eof_tests
from file_tools import FileTools, Rejected, digest
from main import replay
from openai_adapter import OpenAIAdapter
from quote_repair import repair_run
from resume import resume_run

MANIFEST,FIXTURES=native_tests.MANIFEST,native_tests.FIXTURES


class QuoteRepairTests(unittest.TestCase):
    setUp=native_tests.OpenAITests.setUp
    transport=native_tests.OpenAITests.transport

    def source(self):
        parent=eof_tests.EOFResumeTests.source(self)
        bad=copy.deepcopy(FIXTURES['adr'][-1])
        for item in bad['actions'][0]['args']['evidence']:
            if item['path'].endswith(('data/tickets.json','data/users.json')):item['quote']+='{'
        research=eof_tests.EOFResumeTests.research(self)
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([research,bad])):
            receipt,ok=resume_run(self.root,parent,'quote-failed',MANIFEST,live=True,approve_extra_post=True)
        self.assertFalse(ok);self.assertEqual(receipt['error'],'quote_mismatch')
        self.assertEqual(receipt['new_openai_posts'],2)
        return 'day-34-file-assistant/results/quote-failed/trace.json'

    def historical(self):
        base=self.root/'day-34-file-assistant/results'
        files=list((base/'adr-failed').rglob('*'))+list((base/'quote-failed').rglob('*'))
        files+=list((base/'openai-post-budget').glob('post-*.json'))
        return {p:digest(p.read_bytes()) for p in files if p.is_file()}

    def test_preflight_keeps_original_quotes_rejected_and_exposes_read_source_only(self):
        path=self.source();before=self.historical()
        with patch('openai_adapter.subprocess.run') as post:
            report,ready=repair_run(self.root,path,'quote-check',MANIFEST)
        post.assert_not_called();self.assertTrue(ready,report)
        self.assertEqual(report['status'],'ready_pending_tenth_post_approval')
        self.assertEqual(report['saved_decisions_verified'],4)
        self.assertEqual(report['quote_validation'],'EXACT')
        self.assertTrue(report['original_write_still_rejected'])
        self.assertEqual(len(report['mismatches']),2)
        self.assertEqual(report['new_documents'],[])
        self.assertEqual(report['existing_openai_post_slots'],9)
        for mismatch in report['mismatches']:
            self.assertEqual(mismatch['provided_quote'],mismatch['actual_read_source_line']+'{')
        self.assertEqual(before,{p:digest(p.read_bytes()) for p in before})

    def test_repair_requires_explicit_tenth_post_approval(self):
        path=self.source()
        with patch('openai_adapter.subprocess.run') as post,self.assertRaisesRegex(Rejected,'tenth_openai_post_not_approved'):
            repair_run(self.root,path,'unapproved',MANIFEST,live=True)
        post.assert_not_called()
        self.assertFalse((self.root/'day-34-file-assistant/results/unapproved').exists())

    def test_one_fresh_model_submission_completes_and_exact_replay_has_zero_posts(self):
        path=self.source();before=self.historical()
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([FIXTURES['adr'][-1]])) as post:
            receipt,ok=repair_run(self.root,path,'repaired',MANIFEST,live=True,approved=True)
        self.assertTrue(ok,receipt);self.assertEqual(post.call_count,1)
        self.assertEqual(receipt['new_openai_posts'],1)
        self.assertEqual(receipt['historical_openai_posts'],4)
        base=self.root/'day-34-file-assistant/results/repaired'
        trace=json.loads((base/'trace.json').read_bytes())
        self.assertEqual(len(trace['model_calls']),5)
        self.assertEqual(trace['model_calls'][:4],json.loads((self.root/path).read_bytes())['model_calls'])
        failed=[e for e in trace['events'] if e.get('restored_historical_rejection')]
        self.assertEqual(len(failed),1);self.assertEqual(failed[0]['status'],'rejected')
        self.assertFalse(failed[0]['result']['file_written'])
        self.assertEqual(trace['events'][-1]['status'],'ok')
        wire=trace['model_calls'][-1]['wire_request']
        tool_feedback=json.loads([m['content'] for m in wire['messages'] if m['role']=='tool'][-1])
        self.assertEqual(tool_feedback['error'],'quote_mismatch')
        self.assertEqual(len(tool_feedback['quote_mismatches']),2)
        slot=self.root/'day-34-file-assistant/results/openai-post-budget/post-10.json'
        self.assertTrue(json.loads(slot.read_bytes())['one_quote_repair_post_explicitly_approved'])
        with patch('openai_adapter.subprocess.run') as post:
            repeated,receipt=replay(self.root,'day-34-file-assistant/results/repaired/trace.json','repaired-replay')
        post.assert_not_called();self.assertEqual(repeated['status'],'completed',repeated['error'])
        self.assertEqual(repeated['events'],trace['events'])
        self.assertEqual(receipt['new_provider_posts'],0)
        self.assertEqual(before,{p:digest(p.read_bytes()) for p in before})

    def test_fresh_quote_mismatch_stops_without_second_post(self):
        path=self.source();bad=copy.deepcopy(FIXTURES['adr'][-1]);bad['actions'][0]['args']['evidence'][0]['quote']+='{'
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([bad])) as post:
            receipt,ok=repair_run(self.root,path,'bad-again',MANIFEST,live=True,approved=True)
        self.assertFalse(ok);self.assertEqual(receipt['error'],'quote_mismatch')
        self.assertEqual(receipt['new_openai_posts'],1);self.assertEqual(post.call_count,1)
        self.assertFalse((self.root/'day-34-file-assistant/results/bad-again/ADR-001-ticket-context.md').exists())

    def test_new_http_failure_stops_without_retry(self):
        path=self.source()
        def failure(cmd,**kwargs):
            Path(cmd[cmd.index('--output')+1]).write_text('{"error":{"code":"SIMULATED"}}')
            return type('Response',(),{'returncode':0,'stdout':b'400'})()
        with patch('openai_adapter.subprocess.run',side_effect=failure) as post:
            receipt,ok=repair_run(self.root,path,'http-failed',MANIFEST,live=True,approved=True)
        self.assertFalse(ok);self.assertEqual(post.call_count,1)
        self.assertEqual(receipt['new_openai_posts'],1)
        self.assertEqual(receipt['error'],'openai_http_failed_no_retry')

    def test_raw_response_tampering_blocks_before_network(self):
        path=self.source()
        raw=self.root/'day-34-file-assistant/results/quote-failed/provider-2-response.json'
        data=json.loads(raw.read_bytes());data['choices'][0]['message']['tool_calls'][0]['function']['arguments']='{}'
        raw.write_text(json.dumps(data))
        with patch('openai_adapter.subprocess.run') as post,self.assertRaisesRegex(Rejected,'quote_repair_raw_evidence_mismatch'):
            repair_run(self.root,path,'tampered',MANIFEST,live=True,approved=True)
        post.assert_not_called()

    def test_tenth_is_separate_and_eleventh_is_always_blocked(self):
        self.source();tools=FileTools(self.root,'budget-only',MANIFEST)
        ordinary=OpenAIAdapter(approved=True,approve_extra_post=True)
        with self.assertRaisesRegex(Rejected,'openai_global_post_budget_exhausted'):
            ordinary.reserve(tools,'unapproved-tenth',1000)
        approved=OpenAIAdapter(approved=True,approve_extra_post=True,approve_quote_repair_post=True)
        with self.assertRaisesRegex(Rejected,'openai_global_cost_budget_exhausted_before_post'):
            approved.reserve(tools,'cost-cap-still-applies',1_000_000)
        slot,_=approved.reserve(tools,'approved-tenth',1000);self.assertTrue(slot.endswith('post-10.json'))
        with self.assertRaisesRegex(Rejected,'openai_global_post_budget_exhausted'):
            approved.reserve(tools,'eleventh',1000)

    def test_replay_rule_is_bound_to_the_original_failed_action(self):
        path=self.source()
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([FIXTURES['adr'][-1]])):
            receipt,ok=repair_run(self.root,path,'repaired',MANIFEST,live=True,approved=True)
        self.assertTrue(ok)
        trace=self.root/'day-34-file-assistant/results/repaired/trace.json'
        data=json.loads(trace.read_bytes());data['historical_rejections']['4']['action_sha256']='0'*64
        trace.write_text(json.dumps(data))
        with patch('openai_adapter.subprocess.run') as post:
            repeated,_=replay(self.root,'day-34-file-assistant/results/repaired/trace.json','tampered-replay')
        post.assert_not_called();self.assertEqual(repeated['status'],'failed')
        self.assertEqual(repeated['error'],'quote_mismatch')


if __name__=='__main__':unittest.main()
