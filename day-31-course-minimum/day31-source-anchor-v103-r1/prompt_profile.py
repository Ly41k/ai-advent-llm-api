"""Source quote first; exact span and unchanged answer text, no factual repair."""
from copy import deepcopy
from hashlib import sha256
import json
from bublik_developer.generation import (Qwen,SOURCE_RULES_RU,SOURCE_RULES_EN,
    context_budget,validate_output,ModelOutputError)
from bublik_developer.baseline import BaselineQwen,validate_baseline_output,doc_context
from bublik_developer.contracts import Role,ContextEnvelope
from runner import Stop,digest
from source_anchors import catalogs,select,MAX_QUOTE_CHARS
DOC_VERSION='project-answers-v25-source-anchor'
SINGLE_VERSION='snapshot-single-v26-source-anchor'
SCHEMA_VERSION='status-source-quote-text-v2-linked-blocks'
RENDER_VERSION='source-anchor-text-identity-v1'
RULES_RU=(
    'Вопрос не источник; общие факты не доказывают имена/параметры. Нет поддержки: unknown, claims=[]; без неподтверждённых имён/описаний пробелов.\n'
    'claim: source_quote — точная цитата из schema; text — ответ только по ней; один evidence_id. Цитату не меняй.\n'
    'Русская проза; переведи EN, сохрани ASCII имена/API. Без дублей.\n'
    'Ответь на всё, включая причины. Сохрани субъект/этап/время, отрицания, условия/исходы. Разные случаи разделяй. Запрет не условное разрешение.\n'
    'Каждая часть text следует из source_quote. Нужен другой фрагмент: отдельный claim. Молчание не доказательство.\n'
    'Всё поддержано: answered; пробел: partial. Git/язык/отрицание не пробел.\n'
)
RULES_EN=(
    'The question is not evidence; generic facts do not establish names/parameters. No support: unknown, claims=[]; no unsupported names or gap descriptions.\n'
    'Each claim: source_quote first, copied exactly from evidence using schema choices; then text answering only from that quote; one evidence_id. Never alter the quote.\n'
    'English text; translate RU, preserve names/API; no duplicate meanings/languages.\n'
    'Answer every part/cause. Preserve subject, stage, time, negations and exact trigger/outcome. Separate different cases. Never make a prohibition conditional.\n'
    'Every text clause must follow source_quote. Other support: another claim. Silence is not proof.\n'
    'All supported: answered; a support gap: partial. Git/language/negation is not a gap.\n'
)
def replace_rules(text,language):
    original=SOURCE_RULES_RU if language=='ru' else SOURCE_RULES_EN
    if text.count(original)!=1:raise Stop('Original shared source rules changed; no dispatch.')
    return text.replace(original,RULES_RU if language=='ru' else RULES_EN,1).replace('claims[{text,evidence_ids}]','claims[{source_quote,text,evidence_ids}]')

def anchor_schema(schema,context):
    value=deepcopy(schema);catalog=catalogs(context);available=[]
    for evidence_id,rows in catalog.items():
        quotes=[q for q in dict.fromkeys(r['quote'] for r in rows) if sum(r['quote']==q for r in rows)==1]
        if quotes:available.append((evidence_id,quotes))
    for branch in value['oneOf']:
        original=branch['properties']['claims']['items'];items=[]
        for evidence_id,quotes in available:
            item=deepcopy(original);item['required']=['source_quote','text','evidence_ids']
            ids=deepcopy(original['properties']['evidence_ids']);ids.update(minItems=1,maxItems=1)
            ids['items']['enum']=[evidence_id]
            item['properties']={'source_quote':{'type':'string','minLength':1,'maxLength':MAX_QUOTE_CHARS,'enum':quotes},
                'text':deepcopy(original['properties']['text']),'evidence_ids':ids}
            items.append(item)
        # No supported branch can be decoded when no complete in-window unit exists.
        branch['properties']['claims']['items']={'oneOf':items} if items else deepcopy(original)
    if not available:value['oneOf']=value['oneOf'][:1]
    return value

def validate_anchor_output(role,value,context,*,single=False):
    if not single and role==Role.MAIN:return validate_output(role,value,context)
    fields={'status','language','claims'}|({'git_fact_ids'} if single else set())
    if not isinstance(value,dict) or set(value)!=fields:raise ModelOutputError('source_anchor_fields')
    if not isinstance(value['claims'],list) or len(value['claims'])>5:raise ModelOutputError('documentation_claims_shape')
    doc=doc_context(context) if single else context;catalog=catalogs(doc)
    normalized=deepcopy(value);normalized['claims']=[]
    for claim in value['claims']:
        if not isinstance(claim,dict) or set(claim)!={'source_quote','text','evidence_ids'}:
            raise ModelOutputError('source_anchor_claim_shape')
        anchor=select(catalog,claim['evidence_ids'],claim['source_quote'])
        if anchor is None:raise ModelOutputError('source_anchor_not_exact_complete_span')
        plain={'text':claim['text'],'evidence_ids':deepcopy(claim['evidence_ids'])}
        narrowed={**doc,'evidence':[{'id':claim['evidence_ids'][0],'quote':anchor['quote']}]}
        # Existing source/name/path/language/encoding guards now also see only
        # the selected span, so a name elsewhere in the chunk cannot justify it.
        validate_output(Role.DOCUMENTATION,{'status':'answered','language':value['language'],'claims':[plain]},narrowed)
        normalized['claims'].append(plain)
    return validate_baseline_output(role,normalized,context) if single else validate_output(role,normalized,context)

class CoverageQwen(Qwen):
    prompt_version=DOC_VERSION
    def system_prompt(self,role,context):
        value=super().system_prompt(role,context)
        return replace_rules(value,context['language']) if role==Role.DOCUMENTATION else value
    @staticmethod
    def schema_builder(role,context):
        schema=Qwen.schema_builder(role,context)
        return anchor_schema(schema,context) if role==Role.DOCUMENTATION else schema
    output_validator=staticmethod(validate_anchor_output)
    def schema_version(self,role):return SCHEMA_VERSION if role==Role.DOCUMENTATION else super().schema_version(role)

class CoverageBaseline(BaselineQwen):
    prompt_version=SINGLE_VERSION
    def system_prompt(self,role,context):return replace_rules(super().system_prompt(role,context),context['language'])
    @staticmethod
    def schema_builder(role,context):return anchor_schema(BaselineQwen.schema_builder(role,context),doc_context(context))
    @staticmethod
    def output_validator(role,value,context):return validate_anchor_output(role,value,context,single=True)
    def schema_version(self,role):return SCHEMA_VERSION+'-single'

def previews(case,sources):
    ctx={'question':case['question'],'language':case['language'],'evidence':[{'id':f'e{i}','quote':e['quote']} for i,e in enumerate(sources,1)]}
    values=[]
    for mode,cls,role,c in [('multi',CoverageQwen,Role.DOCUMENTATION,ctx),('single',CoverageBaseline,Role.MAIN,{**ctx,'documentation_question':case['question'],'git_facts':[]})]:
        client=cls.__new__(cls);client.context_validator(role,c)
        messages=[{'role':'system','content':client.system_prompt(role,c)},{'role':'user','content':json.dumps(c,ensure_ascii=False,sort_keys=True)}]
        budget=context_budget(messages);schema=client.schema_builder(role,c)
        values.append({'case_id':case['id'],'mode':mode,'context':c,'context_digest':ContextEnvelope.seal(c).digest,
            'message_digest':sha256(json.dumps(messages,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
            'output_schema_digest':digest(schema),'output_schema_bytes':len(json.dumps(schema,ensure_ascii=False,separators=(',',':')).encode()),
            'context_budget':budget,'status':'fits' if budget['estimated_total']<=budget['context_window'] else 'blocked_before_dispatch'})
    return values
