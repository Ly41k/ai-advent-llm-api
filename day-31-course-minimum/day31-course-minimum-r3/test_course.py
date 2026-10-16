"""New-entrypoint regressions. No rebuilding, no network, no Qwen inference."""
import asyncio,json,os,shutil,socket,subprocess,sys,tempfile,unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch,AsyncMock
from types import SimpleNamespace

import runner as core
import course_runtime as rt
from bootstrap_course import HERE
from anchor_acceptance import verify_envelope,digest,semantic_gate
from bublik_developer.workspace import ProjectWorkspace
from bublik_developer.rag.corpus import ProjectCorpus,SourceSpec
from bublik_developer.rag.state import ProjectState
from bublik_developer.rag.index import ProjectIndex
from bublik_developer.errors import DeveloperError

V103=Path(os.environ['DAY31_COURSE_V103']);STATE=Path(os.environ['DAY31_COURSE_STATE'])
SAVED=core.read_json(HERE/'inputs/reviewed-mac83.json')


class CourseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name).resolve()
        self.root=self.folder/'repo';shutil.copytree(V103/'public-corpus54',self.root)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        subprocess.run(['git','-C',str(self.root),'symbolic-ref','HEAD','refs/heads/course-fixture'],check=True)
        self.workspace=ProjectWorkspace.open(self.root,'ai-advent-llm-api')
        freeze=core.read_json(V103/'source-freeze.json')
        self.corpus=ProjectCorpus(self.workspace,[SourceSpec(x['source'],x['kind']) for x in freeze['source_manifest']])
        self.state=ProjectState(self.workspace,STATE);self.index_before=rt.index_bytes(self.state)
        with ProjectIndex.current(self.state,self.corpus) as index:self.metadata=deepcopy(index.metadata);index.verify()
        self.n=rt.CourseNative.__new__(rt.CourseNative);self.n.workspace=self.workspace;self.n.corpus=self.corpus;self.n.state=self.state;self.n.pr=rt.pr
        self.n.document=core.read_json(V103/'regression.cases.json')
        self.work=core.private_dir(self.folder/'work');self.n.configure(self.work,{'package_sha256':'synthetic-course-fixture'})
        self.log=self.folder/'synthetic-calls.jsonl'
        # This index was built in a PREVIOUS task. Its bytes/version are never
        # rewritten here. Local fixtures may have a different UUID from Mac.
        self.local_selection=core.read_json(V103/'expected-selection.json')
        for entry in self.local_selection.values():
            for src in entry['sources']:src['index_version']=self.metadata['index_version']

    def tearDown(self):
        self.assertEqual(rt.index_bytes(self.state),self.index_before)
        self.assertEqual(rt.child_pids(),[])

    @contextmanager
    def fixture_reference(self):
        original=core.read_json
        def read(path):
            if Path(path).resolve()==(V103/'expected-selection.json').resolve():return deepcopy(self.local_selection)
            return original(path)
        import bublik_developer.agent_runtime as runtime
        owned=runtime.run_owned
        async def forward(argv,payload,**kw):
            if len(argv)>1 and argv[1]==str(V103/'retrieval_worker.py'):
                argv=[sys.executable,str(HERE/'fixture_retrieval_worker.py'),'--v103',str(V103),
                      '--index-version',self.metadata['index_version']]
            return await owned(argv,payload,**kw)
        with patch.object(core,'read_json',read),patch.object(runtime,'run_owned',forward):yield

    def acquire(self):
        with self.fixture_reference():return asyncio.run(self.n.capture(self.n.case))

    def native_frame(self):
        rows=SAVED['files']['day31-source-anchor-mac-v103-result.json']['data']['requests']
        row=next(r for r in rows if r['case_id']=='RU-1' and r['mode']=='multi')
        task=row['result']['inference_tasks'][0]['task_id']
        raw=SAVED['files']['day31-source-anchor-mac-v103-raw-'+task+'.json']['data']
        return json.loads(raw['response']['message']['content'])

    def synthetic_worker(self,frame=None):
        import bublik_developer.inference_tasks as tasks
        original=tasks.run_owned;value=frame or self.native_frame()
        frame_path=self.folder/'frame.json';frame_path.write_text(json.dumps(value,ensure_ascii=False))
        async def forward(argv,payload,**kw):
            self.assertEqual(argv[1],str(V103/'capture_worker.py'));self.assertEqual(argv[argv.index('--mode')+1],'multi')
            testargv=[sys.executable,str(HERE/'synthetic_owned_worker.py'),'--v103',str(V103),'--frame',str(frame_path),
                      '--mode','multi','--raw-dir',str(self.n.raw_dir),'--log',str(self.log)]
            return await original(testargv,payload,**kw)
        return patch.object(tasks,'run_owned',forward)

    def collect(self,frame=None):
        with self.fixture_reference(),self.synthetic_worker(frame):
            return asyncio.run(rt.execute_once(self.n,{'scope':'synthetic transport, real workers/index'}))

    def test_real_mcp_orchestrator_no_evidence_and_cleanup(self):
        with self.fixture_reference():result=asyncio.run(rt.mandatory_checks(self.n))
        self.assertEqual(result['status'],'passed');self.assertEqual(result['qwen_calls'],0)
        self.assertEqual(result['independently_observed_branch'],'course-fixture')
        self.assertEqual(result['no_evidence_result']['answer_status'],'unknown')
        self.assertEqual(len(result['path_role_guards']),3)
        self.assertEqual(result['index_before'],result['index_after']);self.assertEqual(result['lingering_new_child_pids'],[])
        core.write_new(Path(os.environ['DAY31_COURSE_EVIDENCE'])/'real-mcp-and-delegation.json',result)

    def test_real_acquisition_matches_frozen_question_context_and_complete_anchors(self):
        snap=self.acquire();self.assertEqual(snap['question'],self.n.case['question'])
        sources=next(r['data']['sources'] for r in snap['observation']['merged'] if r['role']=='documentation')
        from prompt_profile import previews
        expected=core.read_json(V103/'expected-contexts.json')
        self.assertEqual(previews(self.n.case,sources),[p for p in expected if p['case_id']=='RU-1'])

    def test_actual_owned_model_worker_is_synthetic_and_public_output_withheld(self):
        public=self.collect();audit=rt.latest_audit(self.work)
        self.assertTrue(verify_envelope(audit));self.assertEqual(audit['inference_tasks'][0]['transport'],'synthetic_test_transport')
        self.assertEqual(len(self.log.read_text().splitlines()),1);self.assertFalse(public['answer_accepted'])
        self.assertEqual(public['claims'],[]);self.assertEqual(public['semantic_acceptance']['status'],'needs_review')
        self.assertEqual(len(audit['source_anchors']),2)
        for a,c in zip(audit['source_anchors'],audit['claims']):
            self.assertEqual(a['text'],c['text']);self.assertEqual(a['claim_id'],c['id'])
            for key in ['quote','source','start_line','end_line','raw_digest','text_digest','binding_sha256']:self.assertIn(key,a)
        core.write_new(Path(os.environ['DAY31_COURSE_EVIDENCE'])/'synthetic-owned-worker-gate.json',
                       {'scope':'Synthetic transport and preserved RU1 response, real owned subprocess and publication path; not a new Qwen response.',
                        'public':public,'audit':audit,'raw':[core.read_json(p) for p in sorted(self.n.raw_dir.glob('*.json'))]})

    def fixture_review(self,audit):
        b=audit['anchor_binding']
        return {'policy_version':b['version'],'result_binding_sha256':b['binding_sha256'],
                'reviewer':{'id':'synthetic-human','kind':'human'},'decisions':[{'claim_id':a['claim_id'],
                'binding_sha256':a['binding_sha256'],'status':'supported','clauses':[{'text':a['text'],
                 'status':'supported','reason':'Synthetic test-only approval of preserved supported RU1 fixture; not real human acceptance.',
                 'support_spans':[a['quote']]}]} for a in audit['source_anchors']]}

    def test_synthetic_explicit_human_can_publish_same_bound_supported_claims(self):
        self.collect();audit=rt.latest_audit(self.work);before=digest(audit)
        review=self.fixture_review(audit);public=rt.publish_review(self.work,review,'synthetic-human')
        self.assertTrue(public['answer_accepted']);self.assertEqual(public['claims'],audit['claims'])
        self.assertEqual(public['source_anchors'],audit['source_anchors']);self.assertEqual(digest(rt.latest_audit(self.work)),before)
        self.assertEqual(len(self.log.read_text().splitlines()),1)
        core.write_new(Path(os.environ['DAY31_COURSE_EVIDENCE'])/'synthetic-human-publication.json',
                       {'scope':'Synthetic human fixture only; no real human acceptance.',
                        'review':review,'public':public,'original_audit_sha256_before':before,
                        'original_audit_sha256_after':digest(rt.latest_audit(self.work))})

    def test_template_is_pending_and_cannot_autoapprove(self):
        self.collect();template=rt.review_template(self.work)
        self.assertEqual(template['reviewer']['id'],'');self.assertTrue(all(d['status']=='needs_review' for d in template['decisions']))
        template['reviewer']['id']='human'
        public=rt.publish_review(self.work,template,'human');self.assertFalse(public['answer_accepted'])

    def test_mismatching_operator_identity_is_rejected(self):
        self.collect();review=self.fixture_review(rt.latest_audit(self.work))
        with self.assertRaises(core.Stop):rt.publish_review(self.work,review,'someone-else')

    def test_changed_claim_binding_review_stays_pending(self):
        self.collect();review=self.fixture_review(rt.latest_audit(self.work));review['decisions'][0]['binding_sha256']='0'*64
        public=rt.publish_review(self.work,review,'synthetic-human')
        self.assertFalse(public['answer_accepted']);self.assertEqual(public['semantic_acceptance']['status'],'needs_review')

    def test_other_claim_evidence_cannot_be_borrowed(self):
        self.collect();audit=rt.latest_audit(self.work);review=self.fixture_review(audit)
        review['decisions'][0]['clauses'][0]['support_spans']=[audit['source_anchors'][1]['quote']]
        self.assertFalse(rt.publish_review(self.work,review,'synthetic-human')['answer_accepted'])

    def test_runtime_rejection_preserved_even_with_synthetic_positive_review(self):
        frame=self.native_frame();frame['claims'][0]['text']+=' `InventedMechanism`.'
        public=self.collect(frame);audit=rt.latest_audit(self.work)
        self.assertTrue(public['publication']['runtime_refusal_preserved']);self.assertEqual(audit['claims'],[])
        self.assertEqual(audit['inference_tasks'][0]['output_validation'],'rejected')
        reviewed=rt.publish_review(self.work,self.fixture_review(audit),'synthetic-human')
        self.assertFalse(reviewed['answer_accepted']);self.assertEqual(len(self.log.read_text().splitlines()),1)

    def test_started_single_reservation_cannot_be_replayed(self):
        core.write_new(self.work/'reservation.json',{'status':'reserved_before_dispatch'})
        with self.assertRaisesRegex(core.Stop,'cannot be replayed'):
            asyncio.run(rt.execute_once(self.n,{}))
        self.assertFalse(self.log.exists())

    def test_completed_single_request_cannot_generate_again(self):
        self.collect()
        with self.assertRaisesRegex(core.Stop,'cannot be replayed'):asyncio.run(rt.execute_once(self.n,{}))
        self.assertEqual(len(self.log.read_text().splitlines()),1)

    def test_integration_failure_retains_raw_and_reservation_no_next_call(self):
        with patch('publication_adapter.publish_verified',side_effect=ValueError('synthetic publication failure')):
            with self.assertRaisesRegex(ValueError,'publication failure'):self.collect()
        self.assertTrue((self.work/'reservation.json').exists());self.assertTrue((self.work/'live-failure.json').exists())
        self.assertEqual(len(list(self.n.raw_dir.glob('raw-*.json'))),1);self.assertEqual(len(self.log.read_text().splitlines()),1)
        with self.assertRaises(core.Stop):asyncio.run(rt.execute_once(self.n,{}))

    def test_exclusive_persistence_cannot_overwrite_artifact(self):
        path=self.work/'reserved-original.json';core.write_new(path,{'original':True});before=path.read_bytes()
        with self.assertRaises(FileExistsError):core.write_new(path,{'changed':True})
        self.assertEqual(path.read_bytes(),before)

    def test_publication_renderer_has_no_raw_native_answer_escape(self):
        public=self.collect();audit=rt.latest_audit(self.work)
        for key in ['inference_tasks','excerpts','trace','trace_file','anchor_binding','recovery']:self.assertNotIn(key,public)
        self.assertNotIn(audit['claims'][0]['text'],json.dumps(public,ensure_ascii=False))

    def test_real_workspace_rejects_symlink_secret_and_traversal(self):
        link=self.root/'escape.txt';link.symlink_to(self.folder/'outside.txt')
        for path in ['../outside.txt','escape.txt','.env']:
            with self.subTest(path=path),self.assertRaises(DeveloperError):self.workspace.path(path,content=True,missing=True)

    def test_actual_mcp_rejects_untracked_content_even_explicit_path(self):
        from bublik_developer.mcp_client import connect_git,ScopedGitClient
        from bublik_developer.contracts import TaskEnvelope,Role
        (self.root/'untracked.txt').write_text('Public fixture, not a secret.')
        async def call():
            async with connect_git(self.workspace) as registry:
                task=TaskEnvelope.create(Role.GIT,self.workspace.project_id,'Synthetic fixture boundary',{'operation':'diff','arguments':{}})
                with self.assertRaises(DeveloperError):
                    await ScopedGitClient(registry,task).call('git__git_diff',{'paths':['untracked.txt'],'include_content':True})
        asyncio.run(call())

    def test_export_retains_original61_and_counts_no_call_before_live(self):
        from entry import export
        path,summary=export(self.work,core);bundle=core.read_json(path)
        self.assertTrue(all(bundle['files'][k]==v for k,v in SAVED['files'].items()))
        self.assertEqual(summary['known_terminal_calls'],0);self.assertEqual(summary['dispatch_records'],0)
        self.assertEqual(summary['generation_slots_reserved'],0)
        prior=core.read_json(HERE/'inputs/r2-mac-preflight-stopped.json')
        self.assertTrue(all(bundle['files'][k]==v for k,v in prior['files'].items()))
        self.assertTrue(summary['prior_r2_failure_retained'])

    def test_overlay_gate_is_loaded_and_main_bytes_unchanged(self):
        import bublik_developer.pipeline as pipe
        overlay=Path(os.environ['DAY31_COURSE_OVERLAY']);app=Path(os.environ['DAY31_COURSE_APP'])
        self.assertTrue(Path(pipe.__file__).resolve().is_relative_to(overlay));self.assertTrue(hasattr(pipe.Pipeline,'publication_result'))
        self.assertEqual((overlay/'main.py').read_bytes(),(app/'main.py').read_bytes())

    def test_wrong_mode_or_case_is_rejected_without_worker(self):
        with self.assertRaises(core.Stop):asyncio.run(self.n.execute(self.n.case,'single',{},rt.pr.GenerationSlots(1)))
        with self.assertRaises(core.Stop):asyncio.run(self.n.execute({'id':'EN-3'},'multi',{},rt.pr.GenerationSlots(1)))
        self.assertFalse(self.log.exists())

    def test_preflight_failed_session_stops_before_tests_or_inference(self):
        from entry import prepare
        args=SimpleNamespace(v103=V103,root=self.root)
        self.n.conditions=lambda:{'synthetic':'conditions'}
        with patch('bublik_developer.model_session.ModelSession.status',return_value={'gate_open':False}),patch('entry.subprocess.run') as child:
            with self.assertRaisesRegex(core.Stop,'not confirmed'):prepare(self.work,self.n,{},args,core)
        child.assert_not_called();self.assertFalse(self.log.exists())

    def test_preflight_failed_tests_stop_before_real_smoke_or_dispatch(self):
        from entry import prepare
        args=SimpleNamespace(v103=V103,v104=Path('unused'),root=self.root)
        self.n.conditions=lambda:{'synthetic':'conditions'};self.n.prepared={'production_CURRENT_sha256_before':'fixture'}
        with patch('bublik_developer.model_session.ModelSession.status',return_value={'gate_open':True,'epoch_matches':True}),\
             patch('entry.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='synthetic failure',stderr='')),\
             patch('course_runtime.mandatory_checks',new=AsyncMock()) as smoke:
            with self.assertRaisesRegex(core.Stop,'checks failed'):prepare(self.work,self.n,{},args,core)
        smoke.assert_not_called();self.assertFalse(self.log.exists());self.assertTrue((self.work/'targeted-tests-process.json').exists())

    def test_preflight_success_binds_plan_and_reuses_without_model_or_second_test_run(self):
        from entry import prepare
        from prompt_profile import DOC_VERSION
        args=SimpleNamespace(v103=V103,v104=Path('unused'),root=self.root)
        conditions={'source_sha256':{'fixture':'unchanged'},'model_options':{'fixture':True}}
        self.n.conditions=lambda:deepcopy(conditions)
        self.n.prepared={'production_CURRENT_sha256_before':'fixture','intended_model':{'fixture':'model'}}
        def local_check(*args,**kwargs):
            core.write_new(self.work/'targeted-tests.json',{'status':'passed','qwen_calls':0,'tests_run':1})
            return SimpleNamespace(returncode=0)
        with patch('bublik_developer.model_session.ModelSession.status',return_value={'gate_open':True,'epoch_matches':True}),\
             patch('entry.subprocess.run',side_effect=local_check) as checks,\
             patch('course_runtime.mandatory_checks',new=AsyncMock(return_value={'anchor_counts':{'fixture':1}})) as smoke:
            first=prepare(self.work,self.n,{},args,core)
            self.assertEqual(first,prepare(self.work,self.n,{},args,core))
        checks.assert_called_once();smoke.assert_awaited_once()
        plan=core.read_json(self.work/'live-plan.json')
        self.assertEqual(plan['effective_prompt_version'],DOC_VERSION);self.assertEqual(plan['generation_cap'],1)
        self.assertFalse(plan['live_authorized_by_preflight']);self.assertFalse((self.work/'reservation.json').exists())
        self.assertFalse(self.log.exists())

    def test_preflight_changed_receipt_fails_before_tests_or_dispatch(self):
        from entry import prepare
        args=SimpleNamespace(v103=V103,root=self.root)
        self.n.conditions=lambda:{'changed':True};self.n.prepared={'production_CURRENT_sha256_before':'fixture'}
        core.write_new(self.work/'preflight.json',{'binding':{'old':True},'tests_sha256':'old'})
        with patch('bublik_developer.model_session.ModelSession.status',return_value={'gate_open':True,'epoch_matches':True}),patch('entry.subprocess.run') as checks:
            with self.assertRaisesRegex(core.Stop,'binding changed'):prepare(self.work,self.n,{},args,core)
        checks.assert_not_called();self.assertFalse(self.log.exists())

    def test_diagnostic_preserves_native_trace_when_publication_fails(self):
        with patch('publication_adapter.publish_verified',side_effect=ValueError('fixture gate failure')):
            with self.assertRaises(ValueError):self.collect()
        failure=core.read_json(self.work/'live-failure.json')
        self.assertIsNotNone(failure['native_trace']);self.assertEqual(len(failure['observations']),1)
        self.assertFalse(failure['automatic_retry'])

    def test_scoped_original_day30_port_probe_allows_only_two_handshakes(self):
        from bublik_developer import preflight
        with patch.object(socket.socket,'connect',side_effect=ConnectionRefusedError) as transport:
            with rt.no_network():self.assertFalse(preflight.port_check(8000))
        self.assertEqual([c.args[1] for c in transport.call_args_list],[('127.0.0.1',8000),('::1',8000)])

    def test_direct_day30_ollama_and_external_connections_remain_blocked(self):
        targets=[(socket.AF_INET,('127.0.0.1',8000)),(socket.AF_INET6,('::1',8000)),
                 (socket.AF_INET,('127.0.0.1',11434)),(socket.AF_INET6,('::1',11434)),
                 (socket.AF_INET,('192.0.2.1',8000)),(socket.AF_INET,('127.0.0.1',443))]
        with patch.object(socket.socket,'connect') as transport,rt.no_network():
            for family,address in targets:
                with self.subTest(address=address),socket.socket(family,socket.SOCK_STREAM) as s:
                    with self.assertRaisesRegex(AssertionError,'No model/network'):s.connect(address)
        transport.assert_not_called()

    def test_probe_scope_cannot_be_used_for_ollama_or_other_probe_port(self):
        from bublik_developer import preflight
        def wrong_destination(port):
            with socket.socket() as s:s.connect(('127.0.0.1',11434))
        with patch.object(socket.socket,'connect') as transport,patch.object(preflight,'port_check',wrong_destination),rt.no_network():
            with self.assertRaisesRegex(AssertionError,'No model/network'):preflight.port_check(8000)
            with self.assertRaisesRegex(AssertionError,'restricted to port 8000'):preflight.port_check(11434)
        transport.assert_not_called()

    def status_probe(self,transport):
        from bublik_developer import preflight
        from bublik_developer.model_session import ModelSession
        session=ModelSession(self.workspace,state_path=self.folder/'synthetic-session',witness=lambda:'a'*64)
        session._write('confirmed','a'*64)
        with patch.object(preflight,'process_check',return_value=0),\
             patch.object(preflight,'launchd_check',return_value={'loaded':False,'applicable':False}),\
             patch.object(socket.socket,'connect',side_effect=transport),rt.no_network():
            return session.status()

    def test_real_session_status_uses_original_day30_probe_without_model_network(self):
        def refused(sock,address):raise ConnectionRefusedError
        status=self.status_probe(refused)
        self.assertTrue(status['gate_open']);self.assertTrue(status['epoch_matches'])
        self.assertFalse(status['inference_performed']);self.assertFalse(status['session_modified'])
        core.write_new(Path(os.environ['DAY31_COURSE_EVIDENCE'])/'session-port-probe-regression.json',
                       {'status':status,'scope':'Real ModelSession.status/check_day30_off/port_check; socket refusal, OS process/launchd and epoch witness are synthetic; no real TCP or Qwen.'})

    def test_real_session_status_still_rejects_active_day30(self):
        from bublik_developer.preflight import DoctorFailure
        with self.assertRaises(DoctorFailure) as raised:self.status_probe(lambda sock,address:None)
        self.assertEqual(raised.exception.code.value,'day30_service_active')

    def test_real_session_status_still_rejects_unverifiable_probe(self):
        from bublik_developer.preflight import DoctorFailure
        def denied(sock,address):raise PermissionError
        with self.assertRaises(DoctorFailure) as raised:self.status_probe(denied)
        self.assertEqual(raised.exception.code.value,'day30_isolation_unverified')

    def test_probe_permission_scope_resets_after_exception(self):
        from bublik_developer import preflight
        with patch.object(socket.socket,'connect',side_effect=PermissionError),rt.no_network():
            with self.assertRaises(DeveloperError):preflight.port_check(8000)
            self.assertFalse(rt._day30_probe.get())
            with socket.socket() as s:
                with self.assertRaisesRegex(AssertionError,'No model/network'):s.connect(('127.0.0.1',8000))

    def test_nested_offline_guards_preserve_scoped_probe_and_direct_deny(self):
        from bublik_developer import preflight
        with patch.object(socket.socket,'connect',side_effect=ConnectionRefusedError) as transport,rt.no_network(),rt.no_network():
            self.assertFalse(preflight.port_check(8000))
            with socket.socket() as s:
                with self.assertRaises(AssertionError):s.connect(('127.0.0.1',8000))
        self.assertEqual(transport.call_count,2)
