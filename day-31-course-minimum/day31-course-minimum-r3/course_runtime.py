"""One prepared Documentation scenario, existing orchestrator and strict gate."""
import asyncio,os,socket
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch

import runner as core
import run as base
from publication_adapter import PublicationSnapshotPipeline
from bublik_developer import paired_research as pr

VERSION='course-minimum-r3'
CASE_ID='RU-1'
NEGATIVE='qxzvnonexistentmodule7319'
_day30_probe=ContextVar('course_day30_port_probe',default=False)


@contextmanager
def no_network():
    """Deny model/network connections; retain the original Day30 OFF probe.

    Only the trusted synchronous port_check(8000) may attempt TCP handshakes
    with the two literal loopback addresses. It sends no application data.
    Calling the same address directly remains forbidden.
    """
    from bublik_developer import preflight
    original=socket.socket.connect
    original_probe=preflight.port_check
    def guarded(sock,address):
        if sock.family in {socket.AF_INET,socket.AF_INET6}:
            allowed=(_day30_probe.get() and sock.type==socket.SOCK_STREAM
                     and type(address) is tuple and len(address)==2
                     and type(address[1]) is int and address[1]==8000
                     and ((sock.family==socket.AF_INET and address[0]=='127.0.0.1')
                          or (sock.family==socket.AF_INET6 and address[0]=='::1')))
            if not allowed:raise AssertionError('No model/network calls in offline checks. Only scoped Day30 loopback:8000 probe is permitted.')
        return original(sock,address)
    def scoped_probe(port):
        if type(port) is not int or port!=8000:
            raise AssertionError('Offline Day30 probe is restricted to port 8000.')
        token=_day30_probe.set(True)
        try:return original_probe(port)
        finally:_day30_probe.reset(token)
    with patch.object(preflight,'port_check',scoped_probe),patch.object(socket.socket,'connect',guarded):yield


class CourseNative(base.IndependentNative):
    def configure(self,folder,identity):
        self.folder=folder;self.identity=identity;self.raw_dir=core.private_dir(folder/'raw')
        self.anchor_contexts={p['context_digest']:p['context'] for p in core.read_json(base.HERE/'expected-contexts.json')}
        self.case=next(c for c in self.document['cases'] if c['id']==CASE_ID)

    async def execute(self,case,mode,snapshot,slots):
        if case!=self.case or mode!='multi':raise core.Stop('Only frozen RU-1 Documentation, one call, is admitted.')
        def factory(*args,**kwargs):
            pipeline=PublicationSnapshotPipeline(*args,**kwargs,anchor_raw_dir=self.raw_dir,
                anchor_report_dir=self.folder/'publication',anchor_contexts=self.anchor_contexts,
                anchor_result_version={'runner_version':VERSION,'package_sha256':self.identity['package_sha256'],
                                       'case_id':CASE_ID,'mode':'multi'})
            self.last_pipeline=pipeline
            return pipeline
        with patch.object(self.pr,'SnapshotPipeline',factory):
            return await super().execute(case,mode,snapshot,slots)


def index_bytes(state):
    path,_=state.current()
    return {'current_sha256':core.sha256((state.path/'CURRENT.json').read_bytes()).hexdigest(),
            'sqlite_sha256':core.sha256(path.read_bytes()).hexdigest(),'index_file':str(path)}


def child_pids():
    # OS inventory only, no extra dependency. Includes descendants present now;
    # inherited unrelated children are subtracted before checking our cleanup.
    import subprocess,sys
    if sys.platform=='linux':
        # /proc can expose host PIDs inside a nested PID namespace. Use the
        # same namespace for the inventory root and every parent relation.
        root=int(Path('/proc/self/stat').read_text().split(' ',1)[0]);pairs=[]
        for path in Path('/proc').glob('[0-9]*/stat'):
            try:
                text=path.read_text();tail=text.rsplit(')',1)[1].split()
                pairs.append((int(path.parent.name),int(tail[1])))
            except FileNotFoundError:continue
    else:
        root=os.getpid()
        out=subprocess.run(['ps','-A','-o','pid=','-o','ppid='],check=True,capture_output=True,text=True).stdout
        pairs=[tuple(map(int,line.split())) for line in out.splitlines() if len(line.split())==2]
    descendants={root};changed=True
    while changed:
        found={pid for pid,parent in pairs if parent in descendants};changed=bool(found-descendants);descendants|=found
    descendants.discard(root)
    # The ps helper itself has already exited and is not a lingering worker.
    alive=[]
    for pid in descendants:
        if sys.platform=='linux':
            if Path('/proc',str(pid)).exists():alive.append(pid)
            continue
        try:os.kill(pid,0)
        except ProcessLookupError:continue
        alive.append(pid)
    return sorted(alive)


async def mandatory_checks(native):
    from bublik_developer.agent_runtime import demo
    from bublik_developer.pipeline import Pipeline
    from bublik_developer.contracts import Role,TaskEnvelope
    from bublik_developer.mcp_client import connect_git,ScopedGitClient
    from bublik_developer.errors import DeveloperError,ErrorCode
    before=index_bytes(native.state);children=child_pids()
    result=await demo(native.workspace,native.corpus,native.state,question=native.case['question'])
    if result['status']!='completed':raise core.Stop('Real MCP/delegation smoke failed.')
    roles={r['role'] for r in result['results']}
    events={e['event'] for e in result['trace']}
    if roles!={'documentation','git','verification'} or not {'SPAWN','EXECUTE','REPORT','MERGE'}<=events:
        raise core.Stop('Delegation lifecycle missing.')
    if len({r['task_id'] for r in result['results']})!=3 or len({r['context_digest'] for r in result['context_audit']})!=3:
        raise core.Stop('Distinct task/context identities required.')
    git=next(r['data'] for r in result['results'] if r['role']=='git')
    code,branch=native.workspace.command('symbolic-ref','--quiet','--short','HEAD',allowed_codes=(0,1))
    actual=branch.decode().strip() if code==0 else None
    if git['data']['branch']!=actual:raise core.Stop('MCP branch does not match independent Git observation.')
    blocked=[]
    async with connect_git(native.workspace) as registry:
        task=TaskEnvelope.create(Role.GIT,native.workspace.project_id,'Boundary check',{'operation':'branch','arguments':{}})
        client=ScopedGitClient(registry,task)
        for label,name,args in [('unknown_write_tool','git__git_push',{}),
                                ('path_traversal','git__git_diff',{'paths':['../outside'],'include_content':True})]:
            try:await client.call(name,args)
            except DeveloperError as e:
                if e.code not in {ErrorCode.PERMISSION_DENIED,ErrorCode.INVALID_INPUT}:raise
                blocked.append({'check':label,'code':e.code.value,'scope':'client capability/input guard before dispatch'})
            else:raise core.Stop('Forbidden operation was admitted.')
        try:await registry.call(Role.DOCUMENTATION,'git__git_current_branch',{})
        except DeveloperError as e:
            if e.code!=ErrorCode.PERMISSION_DENIED:raise
            blocked.append({'check':'role_escape','code':e.code.value,'scope':'registry role guard before dispatch'})
        else:raise core.Stop('Documentation escaped role restriction.')
    class NoInference:
        def __init__(self,*args):self.observations=[]
        async def run(self,*args,**kwargs):raise AssertionError('No inference permitted for no-evidence probe.')
    negative=await Pipeline(native.workspace,state_dir=native.state.path,corpus=native.corpus,language='en',
                            mode='fts',inference_factory=NoInference).run(NEGATIVE)
    if negative['answer_status']!='unknown' or negative['claims'] or negative['metrics']['llm_calls']!=0:
        raise core.Stop('Expected real empty-evidence refusal was not obtained.')
    snapshot=await native.capture(native.case)  # Original selector/context checks, no model factory.
    from source_anchors import catalogs
    preview=next(p for p in core.read_json(base.HERE/'expected-contexts.json') if p['case_id']==CASE_ID and p['mode']=='multi')
    anchors=catalogs(preview['context'])
    if not anchors or not all(anchors.values()):raise core.Stop('No complete exact source anchors.')
    after=index_bytes(native.state)
    if before!=after:raise core.Stop('Existing index bytes changed.')
    lingering=sorted(set(child_pids())-set(children))
    if lingering:raise core.Stop('Owned child processes remain: '+str(lingering))
    return {'status':'passed','qwen_calls':0,'embedding_calls':0,'real_mcp_and_delegation':result,
            'independently_observed_branch':actual,'path_role_guards':blocked,'no_evidence_result':negative,
            'prepared_snapshot':snapshot,'anchor_counts':{k:len(v) for k,v in anchors.items()},
            'prepared_context_digest':preview['context_digest'],'prepared_message_digest':preview['message_digest'],
            'prepared_schema_digest':preview['output_schema_digest'],'index_before':before,'index_after':after,
            'lingering_new_child_pids':lingering,
            'scope':'Real read-only MCP, original orchestrator, owned FTS/Verification workers and existing index. No synthetic model here; no inference at all.'}


async def execute_once(native,conditions):
    """Prepared for later explicit live authorization; never called by preflight."""
    if (native.folder/'reservation.json').exists():raise core.Stop('Reserved/started/completed single call cannot be replayed. Export only.')
    snapshot=await native.capture(native.case)
    core.write_new(native.folder/'reservation.json',{'version':VERSION,'case_id':CASE_ID,'mode':'multi',
        'generation_cap':1,'status':'reserved_before_dispatch','conditions':conditions,'snapshot_sha256':core.digest(snapshot)})
    try:
        public=await native.execute(native.case,'multi',snapshot,pr.GenerationSlots(1))
        core.write_new(native.folder/'terminal-public.json',public)
        return public
    except BaseException as error:
        native_trace=None
        pipeline=getattr(native,'last_pipeline',None)
        if pipeline is not None:
            path=pipeline.state.path/'traces'/(pipeline.request_id+'.json')
            if path.exists():native_trace=core.read_json(path)
        core.write_new(native.folder/'live-failure.json',{'error':str(error) or type(error).__name__,
            'automatic_retry':False,'original_raw_and_trace_retained':True,'native_trace':native_trace,
            'observations':deepcopy(pipeline.models.observations) if pipeline is not None else []})
        raise


def latest_audit(folder):
    paths=list((folder/'publication').glob('*-audit.json'))
    if len(paths)!=1:raise core.Stop('Exactly one immutable audit is required.')
    return core.read_json(paths[0])


def review_template(folder):
    from anchor_acceptance import VERSION as POLICY
    output=latest_audit(folder)
    return {'policy_version':POLICY,'result_binding_sha256':output['anchor_binding']['binding_sha256'],
        'reviewer':{'id':'','kind':'human'},'decisions':[{'claim_id':a['claim_id'],
            'binding_sha256':a['binding_sha256'],'status':'needs_review','clauses':[{'text':a['text'],
                'status':'needs_review','reason':'','support_spans':[]}]} for a in output['source_anchors']],
        'instructions':'Human must assess each semantic part, preserve exact concatenated text, use only own anchor support spans; filling this template is not approval.'}


def publish_review(folder,review,reviewer_id):
    from anchor_acceptance import semantic_gate,verify_envelope
    from bublik_developer.publication import publish_verified
    if not reviewer_id or review.get('reviewer')!={'id':reviewer_id,'kind':'human'}:
        raise core.Stop('Explicit operator reviewer identity must match human review.')
    output=latest_audit(folder);b=output['anchor_binding']
    record={'version':b['version'],'origin':b['origin'],'binding_sha256':b['binding_sha256'],
            'runtime_passed':b['origin']['runtime_passed'],'source_anchors':output['source_anchors']}
    derived=deepcopy(output);authorities={reviewer_id:'human'}
    derived['semantic_acceptance']=semantic_gate(record,review,authorities=authorities)
    verify_envelope(derived,review,authorities=authorities)
    public=publish_verified(derived,review,authorities=authorities)
    directory=core.private_dir(folder/'reviews');name=core.digest(review)
    for suffix,value in [('decision',review),('reviewed-audit',derived),('public',public)]:
        path=directory/(name+'-'+suffix+'.json')
        if path.exists():
            if core.read_json(path)!=value:raise core.Stop('Existing review artifact differs.')
        else:core.write_new(path,value)
    return public
