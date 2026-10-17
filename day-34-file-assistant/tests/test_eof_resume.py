"""EOF clipping and the separately approved ninth POST; all HTTP is simulated."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import test_openai_adapter as native_tests
from agent import GOALS, run
from file_tools import FileTools, Rejected, digest
from main import replay
from openai_adapter import OpenAIAdapter, function_tools
from resume import resume_run

MANIFEST, FIXTURES = native_tests.MANIFEST, native_tests.FIXTURES


class EOFResumeTests(unittest.TestCase):
    setUp = native_tests.OpenAITests.setUp
    transport = native_tests.OpenAITests.transport

    def source(self):
        # Seed five immutable historical slots so this synthetic failure uses 6/7.
        seed=FileTools(self.root,'seed',MANIFEST)
        adapter=OpenAIAdapter(approved=True)
        for i in range(5):adapter.reserve(seed,'SIMULATED-PRIOR-'+str(i),1000)
        first={'actions':[{'tool':'list_files','args':{}},
                          {'tool':'search_files','args':{'query':'fetch_context','paths':None}}], 'done':False}
        second={'actions':[
            {'tool':'read_file','args':{'path':'day-33-support-assistant/main.py','start':1,'end':140}},
            {'tool':'read_file','args':{'path':'day-33-support-assistant/mcp_client.py','start':1,'end':140}},
            {'tool':'read_file','args':{'path':'day-33-support-assistant/support_agent.py','start':1,'end':156}},
            {'tool':'search_files','args':{'query':'get_ticket','paths':None}},
            {'tool':'search_files','args':{'query':'get_user','paths':None}},
            {'tool':'search_files','args':{'query':'fetch_context','paths':None}},
        ], 'done':False}
        tools=FileTools(self.root,'adr-failed',MANIFEST,read_policy='bounded-v2')
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([first,second])):
            trace,receipt=run(GOALS['adr'],tools,OpenAIAdapter(approved=True,max_posts=3,read_policy='bounded-v2'))
        self.assertEqual(trace['error'],'invalid_line_range')
        self.assertEqual(receipt['new_openai_posts'],2)
        self.assertEqual(len(trace['events']),4)  # Remaining actions were not executed.
        return tools.output_rel+'/trace.json'

    def historical(self):
        base=self.root/'day-34-file-assistant/results'
        files=list((base/'adr-failed').rglob('*'))+list((base/'openai-post-budget').glob('post-*.json'))
        return {p:digest(p.read_bytes()) for p in files if p.is_file()}

    def research(self):
        return {'actions':[{'tool':'read_file','args':{'path':p,'start':1,'end':140}}
                           for p in ('day-33-support-assistant/mcp_server.py',
                                     'day-33-support-assistant/data/tickets.json',
                                     'day-33-support-assistant/data/users.json')], 'done':False}

    def test_eof_clipping_is_explicit_bounded_and_legacy_policy_unchanged(self):
        path='day-33-support-assistant/mcp_client.py'
        tools=FileTools(self.root,'v3',MANIFEST,read_policy='bounded-v3')
        result=tools.read_file(path,1,140)
        self.assertEqual((result['end'],result['requested_end'],result['total_lines']),(68,140,68))
        self.assertTrue(result['truncated']);self.assertTrue(result['end_of_file'])
        self.assertIsNone(result['next_start']);self.assertNotIn((path,69),tools.seen)
        long=tools.read_file('day-33-support-assistant/tests/test_support.py',1,10**20)
        self.assertEqual(len(long['lines']),200);self.assertEqual(long['next_start'],201)
        self.assertFalse(long['end_of_file'])
        old=FileTools(self.root,'v2',MANIFEST,read_policy='bounded-v2')
        with self.assertRaisesRegex(Rejected,'invalid_line_range'):old.read_file(path,1,140)
        self.assertIn('End may exceed EOF',function_tools('bounded-v3')[2]['function']['description'])

    def test_eof_policy_still_rejects_invalid_starts_types_and_paths(self):
        tools=FileTools(self.root,'v3',MANIFEST,read_policy='bounded-v3')
        for start,end in ((0,140),(69,140),(5,4),(True,140),(1,True),(1,1.5)):
            with self.subTest(start=start,end=end),self.assertRaisesRegex(Rejected,'invalid_line_range'):
                tools.read_file('day-33-support-assistant/mcp_client.py',start,end)
        with self.assertRaises(Rejected):tools.read_file('../private',1,140)

    def test_preflight_executes_all_saved_batch_actions_without_post_or_budget_extension(self):
        path=self.source();before=self.historical()
        with patch('openai_adapter.subprocess.run') as post:
            report,ready=resume_run(self.root,path,'adr-check',MANIFEST)
        post.assert_not_called();self.assertTrue(ready,report)
        self.assertEqual(report['status'],'ready_pending_budget_approval')
        self.assertEqual(report['successful_local_operations'],8)
        self.assertEqual(report['saved_decisions_verified'],2)
        self.assertEqual(report['remaining_openai_post_slots'],1)
        self.assertEqual(report['proposed_total_post_cap'],9)
        self.assertTrue(report['budget_extension_approval_required'])
        self.assertEqual(report['provider_posts'],0)
        self.assertEqual(before,{p:digest(p.read_bytes()) for p in before})

    def test_live_adr_requires_separate_extra_post_approval_before_new_directory_or_post(self):
        path=self.source()
        with patch('openai_adapter.subprocess.run') as post,self.assertRaisesRegex(Rejected,'extra_openai_post_not_approved'):
            resume_run(self.root,path,'unapproved',MANIFEST,live=True)
        post.assert_not_called()
        self.assertFalse((self.root/'day-34-file-assistant/results/unapproved').exists())

    def test_explicit_approval_two_fresh_calls_finish_and_replay_without_posts(self):
        path=self.source();before=self.historical()
        decisions=[self.research(),FIXTURES['adr'][-1]]
        with patch('openai_adapter.subprocess.run',side_effect=self.transport(decisions)) as post:
            receipt,ok=resume_run(self.root,path,'adr-continued',MANIFEST,live=True,approve_extra_post=True)
        self.assertTrue(ok,receipt);self.assertEqual(post.call_count,2)
        self.assertEqual(receipt['new_openai_posts'],2)
        self.assertEqual(receipt['historical_openai_posts'],2)
        folder=self.root/'day-34-file-assistant/results/adr-continued'
        trace=json.loads((folder/'trace.json').read_bytes())
        self.assertEqual(len(trace['model_calls']),4)
        self.assertEqual(trace['events'][3]['action']['args']['end'],140)
        self.assertEqual(trace['events'][3]['result']['end'],68)
        self.assertEqual(trace['model_calls'][-1]['meta']['continuation'],'adr-v3')
        slot=self.root/'day-34-file-assistant/results/openai-post-budget/post-09.json'
        self.assertTrue(json.loads(slot.read_bytes())['one_extra_post_explicitly_approved'])
        with patch('openai_adapter.subprocess.run') as post:
            repeated,receipt=replay(self.root,'day-34-file-assistant/results/adr-continued/trace.json','adr-repeat')
        post.assert_not_called();self.assertEqual(repeated['status'],'completed',repeated['error'])
        self.assertEqual(repeated['events'],trace['events']);self.assertEqual(receipt['new_provider_posts'],0)
        self.assertEqual(before,{p:digest(p.read_bytes()) for p in before})

    def test_default_eight_and_approved_nine_slots_cannot_be_reset(self):
        tools=FileTools(self.root,'budget',MANIFEST)
        default=OpenAIAdapter(approved=True)
        for i in range(8):default.reserve(tools,'SIMULATED-'+str(i),1000)
        with self.assertRaisesRegex(Rejected,'openai_global_post_budget_exhausted'):default.reserve(tools,'ninth',1000)
        extended=OpenAIAdapter(approved=True,approve_extra_post=True)
        slot,_=extended.reserve(tools,'approved-ninth',1000);self.assertTrue(slot.endswith('post-09.json'))
        for adapter in (default,extended,OpenAIAdapter(approved=True,approve_extra_post=True)):
            with self.assertRaisesRegex(Rejected,'openai_global_post_budget_exhausted'):
                adapter.reserve(tools,'tenth-not-allowed',1000)

    def test_extra_post_approval_does_not_increase_cost_cap(self):
        tools=FileTools(self.root,'cost',MANIFEST)
        adapter=OpenAIAdapter(approved=True,approve_extra_post=True)
        for i in range(5):adapter.reserve(tools,'SIMULATED-'+str(i),100000)
        with self.assertRaisesRegex(Rejected,'openai_global_cost_budget_exhausted_before_post'):
            adapter.reserve(tools,'still-over-fifty-cents',100000)


if __name__=='__main__':unittest.main()
