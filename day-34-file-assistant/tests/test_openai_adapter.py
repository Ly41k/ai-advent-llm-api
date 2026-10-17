"""All provider responses here are simulated; these tests make ZERO real POSTs."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from file_tools import FileTools, Rejected, digest, strict_json
from agent import GOALS, run
from main import replay, cli
from llm_adapter import ReplayAdapter
from openai_adapter import (OpenAIAdapter, MODEL, NATIVE_SYSTEM, function_tools, decode_native,
                            compact, MAX_REQUEST_BYTES, MAX_RESERVED_USD, MAX_POSTS)

MANIFEST = strict_json((HERE/'inputs.json').read_bytes())
FIXTURES = strict_json((HERE/'offline_fixtures.json').read_bytes())


def native(decision, turn=0):
    return {'role':'assistant', 'content':None, 'tool_calls':[
        {'id':f'simulated_call_{turn}_{i}', 'type':'function',
         'function':{'name':action['tool'],'arguments':json.dumps(action['args'],ensure_ascii=False)}}
        for i,action in enumerate(decision['actions'])]}


class OpenAITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'day-34-file-assistant').mkdir()
        for name in MANIFEST['files']:
            target=self.root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(HERE.parent/name,target)
        self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'sk_SYNTHETIC_NOT_REAL_12345'})
        self.env.start();self.addCleanup(self.env.stop)
        self.which=patch('openai_adapter.shutil.which',return_value='curl')
        self.which.start();self.addCleanup(self.which.stop)

    def tools(self, name='test'):
        return FileTools(self.root,name,MANIFEST)

    def transport(self, decisions, sizes=None):
        iterator=iter(enumerate(decisions))
        def respond(cmd, **kwargs):
            turn, decision=next(iterator)
            request=json.loads(Path(cmd[cmd.index('--data-binary')+1][1:]).read_bytes())
            if sizes is not None:sizes.append(len(json.dumps(request,ensure_ascii=False).encode()))
            self.assertEqual(request['model'],MODEL)
            self.assertEqual(request['tool_choice'],'required')
            self.assertEqual(request['reasoning_effort'],'none')
            self.assertEqual(request['service_tier'],'default')
            self.assertNotIn('response_format',request)
            self.assertEqual(len(request['tools']),4)
            self.assertNotIn(os.environ['OPENAI_API_KEY'],' '.join(cmd))
            self.assertNotIn('OPENAI_API_KEY',kwargs['env'])
            self.assertNotIn('GROQ_API_KEY',kwargs['env'])
            if turn:
                self.assertTrue(any(m['role']=='tool' for m in request['messages']))
                ids=[c['id'] for m in request['messages'] if m['role']=='assistant'
                     for c in m.get('tool_calls',[])]
                outputs=[m['tool_call_id'] for m in request['messages'] if m['role']=='tool']
                self.assertEqual(ids,outputs)
            response={'id':'SIMULATED-NOT-REAL-'+str(turn),'model':MODEL,
                      'usage':{'prompt_tokens':100,'completion_tokens':100,'total_tokens':200},
                      'choices':[{'finish_reason':'tool_calls','message':native(decision,turn)}]}
            Path(cmd[cmd.index('--output')+1]).write_text(json.dumps(response,ensure_ascii=False))
            return type('Response',(),{'returncode':0,'stdout':b'200'})()
        return respond

    def test_native_both_scenarios_and_saved_decision_replay(self):
        before={n:digest((self.root/n).read_bytes()) for n in MANIFEST['files']}
        for scenario in GOALS:
            tools=self.tools('sim-'+scenario)
            sizes=[]
            adapter=OpenAIAdapter(approved=True)
            with patch('openai_adapter.subprocess.run',side_effect=self.transport(FIXTURES[scenario],sizes)) as transport:
                trace,accepted=run(GOALS[scenario],tools,adapter)
            self.assertEqual(trace['status'],'completed',trace['error'])
            self.assertEqual(accepted['file_operation'],'PASS')
            self.assertEqual(accepted['new_openai_posts'],3)
            self.assertEqual(accepted['new_groq_posts'],0)
            self.assertEqual(transport.call_count,3)
            self.assertTrue(all(n<=MAX_REQUEST_BYTES for n in sizes))
            self.assertEqual(trace['events'][0]['action']['tool'],'list_files')
            self.assertEqual(trace['system_prompt'],NATIVE_SYSTEM)
            for call in trace['model_calls']:
                self.assertEqual(decode_native(call['native_message']),json.loads(call['response_text']))
            with patch('openai_adapter.subprocess.run',side_effect=AssertionError('replay cannot call provider')):
                repeated,receipt=replay(self.root,tools.output_rel+'/trace.json','replay-'+scenario)
            self.assertEqual(repeated['status'],'completed',repeated['error'])
            self.assertEqual(repeated['events'],trace['events'])
            self.assertEqual(receipt['new_openai_posts'],receipt['new_groq_posts'],0)
            print(f'SIMULATED {scenario}: payload bytes {sizes}',file=sys.stderr)
        self.assertEqual(before,{n:digest((self.root/n).read_bytes()) for n in MANIFEST['files']})

    def test_strict_schemas_have_exact_fields(self):
        tools=function_tools()
        self.assertEqual({t['function']['name'] for t in tools},{'list_files','search_files','read_file','write_file'})
        def check(node):
            if isinstance(node,dict):
                if node.get('type')=='object':
                    self.assertIs(node['additionalProperties'],False)
                    self.assertEqual(set(node['required']),set(node['properties']))
                for item in node.values():check(item)
            elif isinstance(node,list):
                for item in node:check(item)
        for tool in tools:
            self.assertIs(tool['function']['strict'],True)
            check(tool['function']['parameters'])

    def test_native_contract_rejects_unknown_duplicate_and_mixed_write(self):
        base=native({'actions':[{'tool':'list_files','args':{}}]})
        cases=[]
        wrong=copy.deepcopy(base);wrong['tool_calls'][0]['function']['name']='shell';cases.append(wrong)
        wrong=copy.deepcopy(base);wrong['tool_calls'][0]['function']['arguments']='{"x":1}';cases.append(wrong)
        wrong=copy.deepcopy(base);wrong['tool_calls'][0]['function']['arguments']='{"x":1,"x":2}';cases.append(wrong)
        wrong=copy.deepcopy(base);wrong['tool_calls']*=2;cases.append(wrong)
        wrong=native({'actions':[{'tool':'write_file','args':{'path':'x.md','content':'x','evidence':[]}},
                                  {'tool':'list_files','args':{}}]});cases.append(wrong)
        cases.append({'role':'assistant','content':'done'})
        for item in cases:
            with self.subTest(item=item),self.assertRaises(Rejected):decode_native(item)

    def test_traversal_from_actual_native_arguments_rejected_by_executor(self):
        decision={'actions':[{'tool':'read_file','args':{'path':'../private.txt','start':1,'end':1}}],'done':False}
        with patch('openai_adapter.subprocess.run',side_effect=self.transport([decision])):
            trace,accepted=run('Read inputs',self.tools(),OpenAIAdapter(approved=True))
        self.assertEqual(trace['error'],'unsafe_path')
        self.assertEqual(trace['events'][0]['status'],'rejected')
        self.assertEqual(accepted['new_openai_posts'],1)
        self.assertEqual(trace['documents'],{})

    def test_http_400_stops_without_retry_or_tools(self):
        def respond(cmd, **kwargs):
            Path(cmd[cmd.index('--output')+1]).write_text('{"error":{"code":"invalid_request_error"}}')
            return type('Response',(),{'returncode':0,'stdout':b'400'})()
        with patch('openai_adapter.subprocess.run',side_effect=respond) as transport:
            trace,accepted=run('Test',self.tools(),OpenAIAdapter(approved=True))
        self.assertEqual(transport.call_count,1)
        self.assertEqual(trace['error'],'openai_http_failed_no_retry')
        self.assertEqual(trace['events'],[])
        self.assertEqual(accepted['new_openai_posts'],1)
        self.assertTrue((self.root/'day-34-file-assistant/results/openai-post-budget/post-01.json').exists())

    def test_global_post_slots_stop_ninth_across_instances(self):
        tools=self.tools()
        for i in range(8):
            adapter=OpenAIAdapter(approved=True)
            slot,data=adapter.reserve(tools,str(i),1000)
            self.assertTrue(slot.endswith(f'post-{i+1:02}.json'))
        with self.assertRaisesRegex(Rejected,'openai_global_post_budget_exhausted'):
            OpenAIAdapter(approved=True).reserve(tools,'ninth',1000)
        self.assertEqual(len(list((self.root/'day-34-file-assistant/results/openai-post-budget').glob('*.json'))),8)

    def test_request_size_and_scenario_limit_stop_before_post(self):
        tools=self.tools()
        adapter=OpenAIAdapter(approved=True)
        with patch('openai_adapter.subprocess.run') as transport:
            with self.assertRaisesRegex(Rejected,'openai_request_budget_exceeded_before_post'):
                adapter.choose([{'role':'system','content':NATIVE_SYSTEM},{'role':'user','content':'x'*MAX_REQUEST_BYTES}],tools)
            self.assertEqual(adapter.posts,0)
            self.assertFalse((self.root/'day-34-file-assistant/results/openai-post-budget').exists())
            adapter.posts=MAX_POSTS
            with self.assertRaisesRegex(Rejected,'openai_scenario_post_limit'):
                adapter.choose([],tools)
            transport.assert_not_called()
        self.assertLessEqual(MAX_RESERVED_USD,.50)

    def test_global_cost_reservations_stop_before_fifty_cents(self):
        tools=self.tools()
        for i in range(5):
            OpenAIAdapter(approved=True).reserve(tools,str(i),100000)
        with self.assertRaisesRegex(Rejected,'openai_global_cost_budget_exhausted_before_post'):
            OpenAIAdapter(approved=True).reserve(tools,'over-budget',100000)
        receipts=list((self.root/'day-34-file-assistant/results/openai-post-budget').glob('post-*.json'))
        self.assertEqual(len(receipts),5)
        self.assertLess(sum(json.loads(p.read_text())['reserved_usd'] for p in receipts),.5)

    def test_modified_native_record_fails_replay_without_execution(self):
        tools=self.tools()
        with patch('openai_adapter.subprocess.run',side_effect=self.transport(FIXTURES['usage'])):
            trace,_=run(GOALS['usage'],tools,OpenAIAdapter(approved=True))
        function=trace['model_calls'][0]['native_message']['tool_calls'][0]['function']
        function['name']='search_files'
        function['arguments']='{"query":"changed","paths":null}'
        replay_tools=self.tools('tampered-replay')
        repeated,_=run(GOALS['usage'],replay_tools,ReplayAdapter(trace),expected=trace)
        self.assertEqual(repeated['error'],'replay_native_decision_mismatch')
        self.assertEqual(repeated['events'],[])

    def test_preflight_no_key_no_subprocess(self):
        with patch.dict(os.environ,{},clear=True),patch('sys.argv',['main.py','--root',str(self.root),'plan-openai']),patch('openai_adapter.subprocess.run') as transport,redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(cli(),0)
            result=json.loads(stdout.getvalue())
            self.assertEqual(result['provider_posts'],0)
            self.assertEqual(result['model'],MODEL)
            self.assertLessEqual(result['max_reserved_list_cost_usd'],.5)
            transport.assert_not_called()

    def test_approval_and_key_required(self):
        with self.assertRaisesRegex(Rejected,'openai_not_approved'):OpenAIAdapter()
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            with self.assertRaisesRegex(Rejected,'missing_or_invalid_openai_key'):OpenAIAdapter(approved=True)

    def test_compact_read_output_keeps_exact_source_text(self):
        tools=self.tools()
        output=tools.execute({'tool':'read_file','args':{'path':'day-33-support-assistant/mcp_client.py','start':57,'end':60}})
        numbered=compact(output)['lines']
        self.assertEqual(numbered,[[row['line'],row['text']] for row in output['lines']])
        self.assertEqual(compact({'matches':[]}),{'matches':[]})


if __name__=='__main__':unittest.main()
