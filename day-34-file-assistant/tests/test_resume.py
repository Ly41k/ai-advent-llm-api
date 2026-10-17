"""Synthetic responses only: bounded reads, immutable-prefix continuation and replay."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from agent import GOALS, run
from file_tools import FileTools, Rejected, digest
from main import replay, cli
from openai_adapter import OpenAIAdapter, MAX_REQUEST_BYTES, RESUME_NOTICE, function_tools
from resume import resume_run, verified_source
import test_openai_adapter as native_tests
MANIFEST, FIXTURES = native_tests.MANIFEST, native_tests.FIXTURES


class ResumeTests(unittest.TestCase):
    setUp = native_tests.OpenAITests.setUp
    tools = native_tests.OpenAITests.tools
    transport = native_tests.OpenAITests.transport

    def source(self):
        first = copy.deepcopy(FIXTURES['usage'][0])
        first['actions'][1]['args']['paths'] = None
        reads = [{'tool':'read_file', 'args':{'path':p, 'start':1, 'end':len((self.root/p).read_text().splitlines())}}
                 for p in ('day-33-support-assistant/main.py','day-33-support-assistant/mcp_client.py',
                           'day-33-support-assistant/support_agent.py')]
        last = {'actions':[{'tool':'read_file','args':{
            'path':'day-33-support-assistant/tests/test_support.py','start':1,'end':276}}], 'done':False}
        tools = self.tools('source-failed')
        with patch('openai_adapter.subprocess.run', side_effect=self.transport([first,{'actions':reads,'done':False},last])):
            trace, receipt = run(GOALS['usage'], tools, OpenAIAdapter(approved=True))
        self.assertEqual(trace['error'], 'invalid_line_range')
        self.assertEqual(receipt['new_openai_posts'], 3)
        return tools.output_rel + '/trace.json'

    def old_artifacts(self):
        paths = list((self.root/'day-34-file-assistant/results/source-failed').rglob('*'))
        paths += list((self.root/'day-34-file-assistant/results/openai-post-budget').glob('post-*.json'))
        return {p:digest(p.read_bytes()) for p in paths if p.is_file()}

    def test_bounded_read_returns_only_page_and_marks_unread_tail(self):
        tools = FileTools(self.root,'bounded',MANIFEST,read_policy='bounded-v2')
        path = 'day-33-support-assistant/tests/test_support.py'
        result = tools.execute({'tool':'read_file','args':{'path':path,'start':1,'end':276}})
        self.assertEqual((result['end'],result['requested_end'],result['next_start']), (200,276,201))
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['lines']),200)
        self.assertNotIn((path,201), tools.seen)
        with self.assertRaisesRegex(Rejected,'unread_evidence'):
            tools.write_file('unread.md', 'Unseen citation '+path+':201'+' '*40,
                             [{'path':path,'line':201,'quote':tools.text[path].splitlines()[200]}])
        tail = tools.read_file(path,201,276)
        self.assertEqual(len(tail['lines']),76)
        self.assertNotIn('truncated',tail)
        self.assertIn((path,201),tools.seen)

    def test_bounded_policy_keeps_invalid_bounds_and_paths_rejected(self):
        tools = FileTools(self.root,'bounded',MANIFEST,read_policy='bounded-v2')
        path = 'day-33-support-assistant/tests/test_support.py'
        for start,end in ((0,1),(2,1),(1,277),(True,2),('1',2)):
            with self.subTest(start=start,end=end), self.assertRaisesRegex(Rejected,'invalid_line_range'):
                tools.read_file(path,start,end)
        for path in ('../private','/etc/passwd','day-01/main.py'):
            with self.assertRaises(Rejected): tools.read_file(path,1,1)
        with self.assertRaisesRegex(Rejected,'unknown_read_policy'):
            FileTools(self.root,'bad-policy',MANIFEST,read_policy='unlimited')

    def test_preflight_reuses_three_decisions_without_key_network_or_receipt_changes(self):
        path = self.source()
        before = self.old_artifacts()
        with patch.dict(os.environ,{},clear=True), patch('openai_adapter.subprocess.run') as post:
            report,ready = resume_run(self.root,path,'preflight',MANIFEST)
        post.assert_not_called()
        self.assertTrue(ready,report)
        self.assertEqual(report['provider_posts'],0)
        self.assertEqual(report['saved_decisions_verified'],3)
        self.assertEqual(report['existing_openai_post_slots'],3)
        self.assertLess(report['worst_reserved_usd_using_all_remaining_slots'],.50)
        self.assertLessEqual(report['next_request_utf8_bytes'],MAX_REQUEST_BYTES)
        self.assertEqual(report['new_documents'],[])
        self.assertEqual(before,{p:digest(p.read_bytes()) for p in before})
        preview=json.loads((self.root/'day-34-file-assistant/results/preflight/continuation-request-preview.json').read_bytes())
        self.assertTrue(preview['messages'][0]['content'].endswith(RESUME_NOTICE))
        self.assertEqual(preview['tools'],function_tools('bounded-v2'))

    def test_controlled_two_post_continuation_completes_and_replays_with_zero_posts(self):
        path = self.source()
        before = self.old_artifacts()
        research = {'actions':[{'tool':'read_file','args':{
            'path':'day-33-support-assistant/retry_acceptance.py','start':1,'end':200}}], 'done':False}
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([research,FIXTURES['usage'][2]])) as post:
            receipt,ok = resume_run(self.root,path,'continued',MANIFEST,live=True)
        self.assertTrue(ok,receipt)
        self.assertEqual(post.call_count,2)
        self.assertEqual(receipt['new_openai_posts'],2)
        folder=self.root/'day-34-file-assistant/results/continued'
        trace=json.loads((folder/'trace.json').read_bytes())
        self.assertEqual(len(trace['model_calls']),5)
        self.assertEqual(trace['generation_calls'],2)
        self.assertEqual(trace['resumed_from']['historical_provider_posts'],3)
        paged = [e for e in trace['events'] if e['action']['args'].get('end') == 276]
        self.assertEqual(len(paged),1)
        self.assertEqual(paged[0]['action']['args']['end'],276)
        self.assertEqual(paged[0]['result']['end'],200)
        self.assertTrue(paged[0]['result']['truncated'])
        with patch('openai_adapter.subprocess.run') as post:
            repeated,receipt=replay(self.root,'day-34-file-assistant/results/continued/trace.json','repeated')
        post.assert_not_called()
        self.assertEqual(repeated['status'],'completed',repeated['error'])
        self.assertEqual(repeated['events'],trace['events'])
        self.assertEqual(receipt['new_provider_posts'],0)
        self.assertEqual(before,{p:digest(p.read_bytes()) for p in before})

    def test_continuation_http_error_stops_and_preserves_original(self):
        path=self.source()
        before=self.old_artifacts()
        def failure(command,**kwargs):
            Path(command[command.index('--output')+1]).write_text('{"error":{"code":"test_only"}}')
            return type('Response',(),{'returncode':0,'stdout':b'400'})()
        with patch('openai_adapter.subprocess.run',side_effect=failure) as post:
            receipt,ok=resume_run(self.root,path,'error',MANIFEST,live=True)
        self.assertFalse(ok)
        self.assertEqual(post.call_count,1)
        self.assertEqual(receipt['new_openai_posts'],1)
        self.assertEqual(receipt['error'],'openai_http_failed_no_retry')
        self.assertEqual(before,{p:digest(p.read_bytes()) for p in before})

    def test_mismatched_raw_evidence_blocks_before_new_run_or_post(self):
        path=self.source()
        raw=self.root/'day-34-file-assistant/results/source-failed/provider-3-response.json'
        data=json.loads(raw.read_bytes());data['choices'][0]['message']['tool_calls'][0]['function']['arguments']='{}'
        raw.write_text(json.dumps(data))
        with patch('openai_adapter.subprocess.run') as post, self.assertRaisesRegex(Rejected,'resume_raw_evidence_mismatch'):
            resume_run(self.root,path,'must-not-exist',MANIFEST,live=True)
        post.assert_not_called()
        self.assertFalse((self.root/'day-34-file-assistant/results/must-not-exist').exists())

    def test_other_failure_and_unapproved_cli_do_not_start_continuation(self):
        path=self.source()
        argv=['main.py','--root',str(self.root),'openai-resume','--trace',path,'--run-id','unapproved']
        with patch.object(sys,'argv',argv), redirect_stdout(io.StringIO()) as out, patch('openai_adapter.subprocess.run') as post:
            self.assertEqual(cli(),1)
        post.assert_not_called()
        self.assertEqual(json.loads(out.getvalue())['error'],'openai_resume_not_approved')
        trace=self.root/path;data=json.loads(trace.read_bytes());data['error']='other_failure';trace.write_text(json.dumps(data))
        with self.assertRaisesRegex(Rejected,'unsupported_resume_source'):
            verified_source(self.root,path,MANIFEST)

    def test_two_new_post_cap_cannot_be_extended_by_saved_prefix(self):
        path=self.source()
        research={'actions':[{'tool':'list_files','args':{}}], 'done':False}
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([research,research])) as post:
            receipt,ok=resume_run(self.root,path,'exhausted',MANIFEST,live=True)
        self.assertFalse(ok)
        self.assertEqual(receipt['new_openai_posts'],2)
        self.assertEqual(post.call_count,2)
        self.assertEqual(receipt['error'],'model_round_limit')


if __name__=='__main__': unittest.main()
