"""Private bounded raw capture; replays the external source-anchor validator."""
from copy import deepcopy
import json,re
from pathlib import Path
import runner as core

HERE=Path(__file__).resolve().parent
MAX_CONTENT_BYTES=65536


def reference(mode,context_digest=None):
    rows=core.read_json(HERE/'expected-contexts.json')
    matches=[x for x in rows if x['mode']==mode and (x['context_digest']==context_digest if context_digest else x['case_id']=='RU-3')]
    if len(matches)!=1:raise core.Stop('Exact prepared regression context required.')
    row=matches[0]
    return row,row['context']


def capture_client(parent,mode,payload,raw_dir):
    """Subclass changes only local recording around the original HTTP method."""
    expected,context=reference(mode,payload['context_digest'])
    if payload['context']!=context or payload['context_digest']!=expected['context_digest']:
        raise core.Stop('Only the exact prepared regression context is admitted.')
    if payload['role']!=('main' if mode=='single' else 'documentation') or payload['final'] is not True:
        raise core.Stop('Unexpected role or keep-alive policy.')
    for key in ['task_id','request_id']:
        if not re.fullmatch('[a-f0-9]{32}',payload.get(key,'')):raise core.Stop('Invalid task identity.')
    raw_dir=core.private_dir(raw_dir)
    class Captured(parent):
        def request(self,endpoint,body=None):
            if endpoint!='/api/chat':return super().request(endpoint,body)
            messages=body['messages']
            message_digest=core.sha256(json.dumps(messages,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            if (message_digest!=expected['message_digest'] or core.digest(body['format'])!=expected['output_schema_digest']):
                raise core.Stop('Original model messages/schema changed before dispatch.')
            dispatch={'format':'day31-selection-regression-dispatch-capture-v1','task_id':payload['task_id'],'request_id':payload['request_id'],
                'mode':mode,'context_digest':payload['context_digest'],'message_digest':message_digest,
                'output_schema_digest':core.digest(body['format']),
                'request_body_sha256':core.digest(body),'created_at':core.utc(),
                'scope':'Instrumentation witness; original model session checkpoint remains authoritative.'}
            core.write_new(raw_dir/('dispatch-'+payload['task_id']+'.json'),dispatch)
            value=super().request(endpoint,body)  # Same object, endpoint, body and original transport.
            content=value.get('message',{}).get('content') if isinstance(value.get('message'),dict) else None
            if not isinstance(content,str) or len(content.encode())>MAX_CONTENT_BYTES:
                raise core.Stop('Response cannot be captured exactly within the fixed bound; no retry.')
            witness={'format':'day31-selection-regression-raw-response-v1','task_id':payload['task_id'],'request_id':payload['request_id'],
                'mode':mode,'context_digest':payload['context_digest'],'message_digest':message_digest,
                'output_schema_digest':core.digest(body['format']),'request_body_sha256':core.digest(body),
                'content_sha256':core.sha256(content.encode()).hexdigest(),'content_bytes':len(content.encode()),
                'response':{k:deepcopy(value[k]) for k in ['model','done','done_reason','message','prompt_eval_count','eval_count'] if k in value},
                'captured_at':core.utc(),'scope':'New post-change development regression; none of the original twelve observations are replaced.'}
            if len(core.canonical(witness).encode())>131072:
                raise core.Stop('Full response capture exceeds private record bound; no retry.')
            core.write_new(raw_dir/('raw-'+payload['task_id']+'.json'),witness)
            return value
    return Captured


def analyze(witness,mode):
    from bublik_developer.contracts import Role
    from bublik_developer.generation import validate_output,strict_json,ModelOutputError
    from prompt_profile import validate_anchor_output,RENDER_VERSION
    preview,context=reference(mode,witness['context_digest'])
    response=witness['response'];content=response['message']['content']
    if (core.sha256(content.encode()).hexdigest()!=witness['content_sha256']
            or len(content.encode())!=witness['content_bytes'] or witness['mode']!=mode
            or witness['context_digest']!=preview['context_digest'] or witness['message_digest']!=preview['message_digest']
            or witness['output_schema_digest']!=preview['output_schema_digest']):
        raise core.Stop('Capture provenance/content differs.')
    frame=None;normalized=None;reason=None;anchors=[]
    try:
        if response.get('done_reason')=='length':raise ModelOutputError('output_truncated')
        frame=strict_json(content)
        normalized=validate_anchor_output(Role.MAIN if mode=='single' else Role.DOCUMENTATION,frame,context,single=mode=='single')
        from source_anchors import catalogs,select
        for i,claim in enumerate(frame['claims'],1):
            anchor=select(catalogs(context),claim['evidence_ids'],claim['source_quote'])
            anchors.append({'claim_id':f'c{i}','evidence_id':claim['evidence_ids'][0],**anchor})
    except ModelOutputError as error:reason=error.validation_reason
    unmatched=[]
    if reason=='unsupported_identifier':
        catalog={x['id']:x['quote'] for x in context['evidence']}
        for i,claim in enumerate(frame['claims']):
            support=claim['source_quote']
            text=claim['text'];code=re.findall(r'`([^`]+)`',text);prose=re.sub(r'`[^`]+`',' ',text)
            names=re.findall(r'\b([A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+)\b',prose)
            paths=re.findall(r'(?<!\w)(/[A-Za-z0-9_./-]+)',prose)
            for kind,tokens in [('inline_code',code),('underscore_name',names),('path',paths)]:
                for token in tokens:
                    if token not in support and not (kind=='path' and token.rstrip('.') in support):
                        unmatched.append({'claim_index':i,'token_kind':kind,'token':token,'evidence_ids':claim['evidence_ids']})
    return {'format':'day31-selection-regression-exact-validation-analysis-v1','mode':mode,'task_id':witness['task_id'],
        'request_id':witness['request_id'],'content_sha256':witness['content_sha256'],
        'validation_reason':reason,'validation_passed':reason is None,'unmatched_identifiers':unmatched,
        'render_version':RENDER_VERSION,'normalized_output':normalized,'source_anchors':anchors,
        'scope':'Exact source-span validation and original v099 guards on unchanged text against the selected anchor and original evidence; no factual repair or semantic acceptance.'}
