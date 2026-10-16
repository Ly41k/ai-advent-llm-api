"""Public corpus/real owned workers; all model responses in these tests synthetic."""
import asyncio,json,os,shutil,sqlite3,subprocess,sys,tempfile,unittest
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,os.environ['DAY31_TEST_APP'])
import runner as core
import run as r
import forensic_capture as f
import selection_policy as policy
HERE=Path(__file__).resolve().parent

class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name).resolve();self.raw=core.private_dir(self.folder/'raw')
    def prepared(self,row=None,text=None):
        from bublik_developer.generation import MODEL,OPTIONS
        from prompt_profile import CoverageQwen as Qwen,CoverageBaseline as BaselineQwen
        from bublik_developer.contracts import Role
        row=row or next(x for x in core.read_json(HERE/'expected-contexts.json') if x['mode']=='multi' and x['case_id']=='RU-3')
        mode=row['mode'];parent=Qwen if mode=='multi' else BaselineQwen;role=Role.DOCUMENTATION if mode=='multi' else Role.MAIN
        client=parent.__new__(parent);ctx=deepcopy(row['context'])
        messages=[{'role':'system','content':client.system_prompt(role,ctx)},{'role':'user','content':json.dumps(ctx,ensure_ascii=False,sort_keys=True)}]
        body={'model':MODEL,'messages':messages,'stream':False,'format':client.schema_builder(role,ctx),'options':deepcopy(OPTIONS),'keep_alive':'0s'}
        token=mode+row['case_id'];payload={'context':ctx,'context_digest':row['context_digest'],'role':role.value,'final':True,'task_id':sha256(token.encode()).hexdigest()[:32],'request_id':sha256(('request'+token).encode()).hexdigest()[:32]}
        from source_anchors import catalogs
        units=catalogs(ctx).get('e1',[])
        selected=next((x['quote'] for x in units if x['quote'].startswith('|')),units[0]['quote'] if units else '')
        frame={'status':'answered' if text else 'unknown','language':ctx['language'],'claims':[{'source_quote':selected,'text':text,'evidence_ids':['e1']}] if text else []}
        if mode=='single':frame['git_fact_ids']=[]
        response={'model':MODEL,'done':True,'done_reason':'stop','message':{'role':'assistant','content':json.dumps(frame,ensure_ascii=False)},'prompt_eval_count':100,'eval_count':20}
        return parent,payload,body,response
    def invoke(self,row=None,text=None):
        parent,payload,body,response=self.prepared(row,text)
        cls=f.capture_client(parent,'single' if 'documentation_question' in payload['context'] else 'multi',payload,self.raw);client=cls.__new__(cls)
        with patch.object(parent,'request',return_value=response) as original:returned=client.request('/api/chat',body)
        return payload,body,response,returned,original
    def test_all_twelve_contexts_and_current_validators_capture_exact_body_and_reply(self):
        for row in core.read_json(HERE/'expected-contexts.json'):
            with self.subTest(case=row['case_id'],mode=row['mode']):
                payload,body,response,returned,original=self.invoke(row)
                self.assertIs(returned,response);self.assertIs(original.call_args.args[1],body)
                witness=core.read_json(self.raw/('raw-'+payload['task_id']+'.json'))
                self.assertEqual(witness['response'],response);self.assertTrue(f.analyze(witness,row['mode'])['validation_passed'])
    def test_invalid_identifier_is_recorded_without_repair_or_extra_dispatch(self):
        payload,body,response,returned,original=self.invoke(text='Для перехода `invented_hidden_state` нужен план.')
        witness=core.read_json(self.raw/('raw-'+payload['task_id']+'.json'))
        self.assertEqual(f.analyze(witness,'multi')['validation_reason'],'unsupported_identifier');self.assertEqual(original.call_count,1)
    def test_accepted_v099_transition_format_stays_accepted(self):
        payload,body,response,returned,original=self.invoke(text='Для перехода `planning → execution` нужен непустой и явно утверждённый план.')
        witness=core.read_json(self.raw/('raw-'+payload['task_id']+'.json'))
        self.assertTrue(f.analyze(witness,'multi')['validation_passed'])
    def test_mutated_context_and_role_block_before_HTTP(self):
        parent,payload,body,response=self.prepared()
        for key in ['context','role']:
            changed=deepcopy(payload)
            if key=='context':changed[key]['question']='changed'
            else:changed[key]='main'
            with self.assertRaises(core.Stop):f.capture_client(parent,'multi',changed,self.raw)
        self.assertEqual(list(self.raw.iterdir()),[])
    def test_mutated_messages_or_schema_block_before_HTTP(self):
        parent,payload,body,response=self.prepared();client=f.capture_client(parent,'multi',payload,self.raw).__new__(f.capture_client(parent,'multi',payload,self.raw))
        for key in ['messages','format']:
            changed=deepcopy(body);changed[key]=[] if key=='messages' else {}
            with patch.object(parent,'request',return_value=response) as original:
                with self.assertRaises(core.Stop):client.request('/api/chat',changed)
                original.assert_not_called()
    def test_raw_collision_prevents_second_dispatch_and_tamper_is_detected(self):
        parent,payload,body,response=self.prepared();cls=f.capture_client(parent,'multi',payload,self.raw);client=cls.__new__(cls)
        with patch.object(parent,'request',return_value=response) as original:
            client.request('/api/chat',body)
            with self.assertRaises(FileExistsError):client.request('/api/chat',body)
            self.assertEqual(original.call_count,1)
        witness=core.read_json(self.raw/('raw-'+payload['task_id']+'.json'));witness['response']['message']['content']='tampered'
        with self.assertRaises(core.Stop):f.analyze(witness,'multi')
    def test_oversize_reply_retains_dispatch_but_never_retries(self):
        parent,payload,body,response=self.prepared();response['message']['content']='x'*(f.MAX_CONTENT_BYTES+1)
        cls=f.capture_client(parent,'multi',payload,self.raw);client=cls.__new__(cls)
        with patch.object(parent,'request',return_value=response) as original:
            with self.assertRaises(core.Stop):client.request('/api/chat',body)
            self.assertEqual(original.call_count,1)
        self.assertEqual(len(list(self.raw.glob('dispatch-*.json'))),1);self.assertEqual(list(self.raw.glob('raw-*.json')),[])
    def test_new_catalog_preserves_exact_six_wordings_and_frozen_rubric(self):
        original=core.read_json(HERE/'cases.frozen.json');new=core.read_json(HERE/'regression.cases.json')
        self.assertEqual([(x['id'],x['language'],x['question']) for x in original['cases']],[(x['id'],x['language'],x['question']) for x in new['cases']])
        self.assertEqual(new['evaluation_kind'],'known_regression')
        expected=core.read_json(HERE/'expected-selection.json')
        for case in new['cases']:
            actual=__import__('prompt_profile').previews(case,expected[case['id']]['sources'])
            self.assertEqual(actual,[x for x in core.read_json(HERE/'expected-contexts.json') if x['case_id']==case['id']])
    def test_source_and_preflight_pins_match_current_app_without_model_access(self):
        n=r.IndependentNative.__new__(r.IndependentNative);n.reference=core.read_json(HERE/'baseline.v099.json')
        pre=core.read_json(HERE/'native-preflight.reference.json');read=core.read_json
        with patch.object(core,'read_json',side_effect=lambda path:pre if str(path)=='/tmp/day31-stage7-v099-work/native-preflight.json' else read(path)):
            n.verify_source(Path(os.environ['DAY31_TEST_APP']))
    def test_real_capture_worker_imports_in_original_minimal_environment(self):
        from bublik_developer.process import minimal_env
        _,payload,_,_=self.prepared();payload.update(root=str(self.folder),workspace_identity=[0,0],project_id='ai-advent-llm-api')
        app=Path(os.environ['DAY31_TEST_APP'])
        result=subprocess.run([sys.executable,str(HERE/'capture_worker.py'),'--mode','multi','--raw-dir',str(self.raw)],input=core.canonical(payload),capture_output=True,text=True,cwd=app,env={**minimal_env(),'PYTHONPATH':str(app)},timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);reply=json.loads(result.stdout);self.assertIsNotNone(reply['error_code']);self.assertEqual(reply['metrics']['llm_calls'],0)
    def test_model_worker_redirection_preserves_exact_payload_and_owned_cleanup(self):
        import bublik_developer.inference_tasks as tasks
        forwarded=[]
        async def original(argv,encoded,**kwargs):forwarded.append((argv,encoded,kwargs));return b'synthetic',7
        class Pipeline:
            def __init__(self,*args,**kwargs):pass
            async def run(self,q):return await tasks.run_owned([sys.executable,'-m','bublik_developer.model_worker'],b'exact',cwd='same',env={'same':'env'})
        n=r.IndependentNative.__new__(r.IndependentNative);n.raw_dir=self.raw;n.workspace='workspace';n.state=SimpleNamespace(path=self.folder);n.corpus='corpus';n.pr=SimpleNamespace(SnapshotPipeline=Pipeline,limited_inference=lambda slots:'factory')
        with patch.object(tasks,'run_owned',original):
            value=asyncio.run(n.execute({'question':'q','language':'en'},'multi',{},None));self.assertIs(tasks.run_owned,original)
        self.assertEqual(value,(b'synthetic',7));self.assertEqual(forwarded[0][1:],(b'exact',{'cwd':'same','env':{'same':'env'}}));self.assertIn(str(HERE/'capture_worker.py'),forwarded[0][0])
    def test_fingerprint_is_diversity_heuristic_without_invented_translation_table(self):
        self.assertEqual(policy.fingerprint('Table `alpha_id` and `beta_id`.'),policy.fingerprint('Таблица `beta_id` и `alpha_id`.'))
        self.assertIsNone(policy.fingerprint('One `alpha_id` only.'))
        self.assertNotEqual(policy.section_key({'source':'x/README.md','section':'Result'}),policy.section_key({'source':'x/README.ru.md','section':'Результат'}))
    def test_fresh_six_owned_documentation_and_verification_workers_on_pinned_corpus(self):
        # Public source bytes are real. A local test copy receives synthetic native
        # metadata identity so the exact prepared-source gate can be exercised.
        from bublik_developer.workspace import ProjectWorkspace
        from bublik_developer.rag.corpus import ProjectCorpus,SourceSpec
        from bublik_developer.rag.state import ProjectState
        from bublik_developer.rag.index import ProjectIndex,build_index
        from bublik_developer import paired_research as pr
        root=self.folder/'repo';shutil.copytree(HERE/'public-corpus54',root)
        subprocess.run(['git','init','-q',str(root)],check=True)
        w=ProjectWorkspace.open(root,'ai-advent-llm-api');freeze=core.read_json(HERE/'source-freeze.json');corpus=ProjectCorpus(w,[SourceSpec(x['source'],x['kind']) for x in freeze['source_manifest']]);state=ProjectState(w,self.folder/'state')
        build=build_index(corpus,state);path,_=state.current();meta=build['index'];meta['index_version']=freeze['isolated_index']['index_version']
        with closing(sqlite3.connect(path)) as db:
            db.execute('UPDATE metadata SET value=?',(core.canonical(meta),));db.commit()
        newpath=path.with_name('index-'+meta['index_version']+'.sqlite3');path.rename(newpath)
        state.publish({'file':newpath.name,'sha256':sha256(newpath.read_bytes()).hexdigest(),'index_version':meta['index_version']})
        with ProjectIndex.current(state,corpus) as index:self.assertEqual(index.verify()['index']['chunks'],510)
        n=r.IndependentNative.__new__(r.IndependentNative);n.workspace=w;n.state=state;n.corpus=corpus;n.pr=pr
        for case in core.read_json(HERE/'regression.cases.json')['cases']:
            with self.subTest(case=case['id']):
                snapshot=asyncio.run(n.capture(case));self.assertEqual(snapshot['observation']['status'],'completed')
                self.assertEqual(snapshot['observation']['metrics']['llm_calls'],0)
                self.assertTrue(any(x['role']=='verification' and x['status']=='success' and any(c['check']=='fresh_exact_source_provenance' and c['status']=='passed' for c in x['data']['checks']) for x in snapshot['observation']['results']))
    def test_export_keeps_raw_rejection_and_never_overwrites_previous_bundle(self):
        payload,body,response,returned,original=self.invoke(text='Для перехода `invented_hidden_state` нужен план.')
        state={'report':{'requests':[],'pairs':[],'generation_slots_reserved':0,'frozen_conditions':{}},'config':{},'plan':{},'index_verify':{}}
        journal=SimpleNamespace(state=state,sequence=1,tip='synthetic')
        a=r.export(self.folder,journal);raw=a.read_bytes();b=r.export(self.folder,journal)
        self.assertNotEqual(a,b);self.assertEqual(a.read_bytes(),raw)
        bundle=core.read_json(b)
        analyses=[x['data'] for n,x in bundle['files'].items() if '-analysis-' in n]
        self.assertEqual(analyses[0]['validation_reason'],'unsupported_identifier')
        for item in bundle['files'].values():self.assertEqual(item['sha256'],sha256((core.canonical(item['data'])+'\n').encode()).hexdigest())
    def test_unreviewed_question_cannot_enter_research_worker(self):
        with self.assertRaises(core.Stop):policy.search(None,'Unreviewed question?',mode='fts',provider=None,sources=None)

    def test_captured_generate_and_bundle_replay_agree_without_changing_raw_anchor(self):
        from bublik_developer.generation import MODEL
        from prompt_profile import CoverageQwen,CoverageBaseline
        from bublik_developer.contracts import Role
        for mode,parent in [('multi',CoverageQwen),('single',CoverageBaseline)]:
            row=next(x for x in core.read_json(HERE/'expected-contexts.json') if x['mode']==mode and x['case_id']=='EN-3')
            _,payload,body,response=self.prepared(row)
            from source_anchors import catalogs
            anchor=next(x['quote'] for x in catalogs(row['context'])['e1'] if x['quote'].startswith('If the model selects a premature step') and x['quote'].count('.')==1)
            frame={'status':'answered','language':'en','claims':[{'source_quote':anchor,'text':'The agent labels it `agent correction`.','evidence_ids':['e1']}]}
            if mode=='single':frame['git_fact_ids']=[]
            response['message']['content']=json.dumps(frame);original_content=response['message']['content']
            cls=f.capture_client(parent,mode,payload,self.raw);client=cls.__new__(cls);client.metrics=None
            client.http=SimpleNamespace(transport='synthetic');client.http_events=[];client.metadata_retries=0;client.dispatched=False
            events=[];client.lease=SimpleNamespace(begin=lambda:events.append('begin'),finish=lambda:events.append('finish'),uncertain=lambda:events.append('uncertain'))
            with patch.object(client,'identity',return_value={'name':MODEL,'digest':'synthetic'}),patch.object(parent,'request',return_value=response) as request:
                normalized=client.generate(Role.MAIN if mode=='single' else Role.DOCUMENTATION,row['context'])
            witness=core.read_json(self.raw/('raw-'+payload['task_id']+'.json'))
            self.assertEqual(events,['begin','finish']);self.assertEqual(request.call_count,1)
            self.assertEqual(witness['response']['message']['content'],original_content)
            replay=f.analyze(witness,mode);self.assertTrue(replay['validation_passed']);self.assertEqual(replay['normalized_output'],normalized)

    def test_missing_source_quote_schema_keeps_raw_rejection_and_known_call_without_retry(self):
        from prompt_profile import CoverageQwen
        from bublik_developer.contracts import Role
        from bublik_developer.generation import MODEL,ModelOutputError
        row=next(x for x in core.read_json(HERE/'expected-contexts.json') if x['mode']=='multi' and x['case_id']=='EN-3')
        _,payload,body,response=self.prepared(row)
        # Old-format answer is not silently upgraded to the experimental schema.
        response['message']['content']=json.dumps({'status':'answered','language':'en','claims':[{'text':'A report is verified.','evidence_ids':['e1']}]})
        cls=f.capture_client(CoverageQwen,'multi',payload,self.raw);client=cls.__new__(cls);client.metrics=None
        client.http=SimpleNamespace(transport='synthetic');client.http_events=[];client.metadata_retries=0;client.dispatched=False
        events=[];client.lease=SimpleNamespace(begin=lambda:events.append('begin'),finish=lambda:events.append('finish'),uncertain=lambda:events.append('uncertain'))
        with patch.object(client,'identity',return_value={'name':MODEL,'digest':'synthetic'}),patch.object(CoverageQwen,'request',return_value=response) as request:
            with self.assertRaises(ModelOutputError):client.generate(Role.DOCUMENTATION,row['context'])
        self.assertEqual(events,['begin','finish']);self.assertEqual(request.call_count,1);self.assertEqual(client.metrics['llm_calls'],1)
        self.assertEqual(client.metrics['output_validation_reason'],'source_anchor_claim_shape')
        witness=core.read_json(self.raw/('raw-'+payload['task_id']+'.json'));analysis=f.analyze(witness,'multi')
        self.assertFalse(analysis['validation_passed']);self.assertIsNone(analysis['normalized_output'])

if __name__=='__main__':unittest.main()
