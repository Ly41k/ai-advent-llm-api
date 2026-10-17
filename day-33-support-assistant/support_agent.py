"""MCP -> FTS5 -> bounded LLM plan -> evidence validation -> user text."""
import asyncio
import json
from common import PRODUCT, SupportError, require, safe_text, validate_request
from mcp_client import fetch_context
from retrieval import retrieve

TICKET_KEYS = {'ticket_id','user_id','product','description','status','device','observed_error','session_state','tailscale_state','diagnostic','synthetic'}
USER_KEYS = {'user_id','display_name','product','device','access_route','synthetic'}
ACTIONS = {
    'sign_in': ('auth', 'Откройте исходный HTTPS-адрес чата и повторно войдите через интерфейс Bublik.'),
    'check_auth': ('auth', 'Уточните, используется браузерная сессия или Bearer-доступ; сообщите точный код ошибки без credentials.'),
    'connect_tailscale': ('phone', 'Подключите Tailscale на телефоне к той же tailnet, затем откройте HTTPS-адрес Mac и войдите в Bublik.'),
    'check_host': ('phone', 'Проверьте, что Mac не спит, подключён к сети и API доступен; не запускайте второй экземпляр сервиса.'),
    'same_conversation': ('history', 'Проверьте, что открыт тот же диалог под тем же пользователем на исходном HTTPS-адресе.'),
    'check_model': ('outage', 'Попросите оператора проверить готовность Ollama и хранилища. Сохранённая история не требует работающей модели.'),
    'collect_details': (None, 'Передайте оператору время сбоя, устройство, адрес доступа и точный код ошибки. Не передавайте пароль, cookie или токены.')
}
ASSESSMENTS = {
    'session_expired': 'По данным синтетического тикета браузерная сессия истекла. Это подтверждает тикет, а не один HTTP 401.',
    'tailscale_disconnected': 'В тикете явно зафиксирован отключённый Tailscale на телефоне; это препятствует указанному доступу через Tailscale HTTPS.',
    'undetermined': 'Точная причина неизвестна: имеющихся данных недостаточно для подтверждённого диагноза.'
}
ACTION_SOURCES = {
    'sign_in': {'FAQ-AUTH','DOC-AUTH'},
    'check_auth': {'FAQ-AUTH','DOC-AUTH','FAQ-ERRORS','DOC-ERRORS'},
    'connect_tailscale': {'FAQ-PHONE','DOC-PHONE'},
    'check_host': {'FAQ-PHONE','DOC-PHONE','FAQ-ACCESS','DOC-ACCESS'},
    'same_conversation': {'FAQ-HISTORY','DOC-HISTORY'},
    'check_model': {'FAQ-OUTAGE','DOC-OUTAGE'},
    'collect_details': set(),
}


def validate_context(ticket, user):
    for record, allowed, needed in ((ticket,TICKET_KEYS,{'ticket_id','user_id','product','description','status','device','observed_error','diagnostic','synthetic'}), (user,USER_KEYS,USER_KEYS)):
        require(isinstance(record,dict) and needed <= set(record) <= allowed, 'mcp_invalid_context', 502)
        require(record['synthetic'] is True and record['product'] == PRODUCT, 'non_synthetic_context', 502)
        for key,value in record.items():
            if key != 'synthetic':
                safe_text(value)
    require(ticket['user_id'] == user['user_id'] and ticket['device'] == user['device'], 'mcp_identity_mismatch', 502)


def prepare(question, ticket=None, user=None):
    sources, retrieval = retrieve(question, ticket)
    facts = {}
    if ticket:
        for prefix, record in (('ticket',ticket),('user',user)):
            facts.update({prefix+'.'+k:v for k,v in record.items() if isinstance(v,str)})
    topics = {s['topic'] for s in sources}
    assessments = ['undetermined']
    if ticket and ticket.get('session_state') == 'expired' and 'auth' in topics:
        assessments.append('session_expired')
    if ticket and ticket.get('tailscale_state') == 'disconnected_on_phone' and 'phone' in topics:
        assessments.append('tailscale_disconnected')
    actions = {}
    for key, (topic, text) in ACTIONS.items():
        ids = [s['id'] for s in sources if s['id'] in ACTION_SOURCES[key]]
        if topic is None or ids:
            actions[key] = {'text':text,'source_ids':ids}
    # A specific ticket is evidence of its stated issue, not authority over unrelated questions.
    return {'question':question,'ticket_id':ticket['ticket_id'] if ticket else None,
            'context':facts,'sources':sources,'retrieval':retrieval,
            'allowed_assessments':assessments,'allowed_actions':actions}


def action_evidence(plan, payload):
    """Application-owned action text is grounded by the application, not recited as a model claim."""
    sources = {source['id']: source for source in payload['sources']}
    evidence = []
    for action in plan['action_ids']:
        ids = payload['allowed_actions'][action]['source_ids']
        require(all(source_id in sources and source_id in ACTION_SOURCES[action]
                    for source_id in ids), 'invalid_action_evidence', 502)
        require(bool(ids) or action == 'collect_details', 'missing_action_evidence', 502)
        if ids:
            source = sources[ids[0]]
            evidence.append({'action_id':action, 'source_id':source['id'],
                             'quote':source['text'], 'assigned_by':'application'})
    return evidence


def validate_plan(plan, payload):
    require(isinstance(plan,dict) and set(plan)=={'assessment','document_facts','context_facts','action_ids'}, 'invalid_llm_json', 502)
    require(isinstance(plan['assessment'],str) and plan['assessment'] in payload['allowed_assessments'], 'unsupported_assessment', 502)
    require(isinstance(plan['action_ids'],list) and 1 <= len(plan['action_ids']) <= 4 and all(isinstance(a,str) and a in payload['allowed_actions'] for a in plan['action_ids']), 'unsupported_action', 502)
    require(len(set(plan['action_ids'])) == len(plan['action_ids']), 'invalid_llm_json', 502)
    source_map = {s['id']:s for s in payload['sources']}
    for name, upper in (('document_facts',3),('context_facts',6)):
        require(isinstance(plan[name],list) and len(plan[name]) <= upper, 'invalid_llm_json', 502)
    cited = set()
    for fact in plan['document_facts']:
        require(isinstance(fact,dict) and set(fact)=={'source_id','quote'} and isinstance(fact['source_id'],str) and fact['source_id'] in source_map, 'invalid_source_id', 502)
        require(isinstance(fact['quote'],str) and 20 <= len(fact['quote']) <= 1600 and fact['quote'] in source_map[fact['source_id']]['text'], 'unsupported_document_fact', 502)
        cited.add(fact['source_id'])
    used_keys = set()
    for fact in plan['context_facts']:
        require(isinstance(fact,dict) and set(fact)=={'key','quote'} and isinstance(fact['key'],str) and fact['key'] in payload['context'], 'invalid_context_fact', 502)
        require(fact['quote']==payload['context'][fact['key']], 'unsupported_context_fact', 502)
        used_keys.add(fact['key'])
    require(bool(plan['document_facts']) == bool(payload['sources']), 'missing_document_evidence', 502)
    if payload['ticket_id']:
        require({'ticket.observed_error','user.device'} <= used_keys, 'missing_context_evidence', 502)
    action_evidence(plan,payload)
    if plan['assessment'] != 'undetermined':
        key='ticket.session_state' if plan['assessment']=='session_expired' else 'ticket.tailscale_state'
        topic='auth' if plan['assessment']=='session_expired' else 'phone'
        require(key in used_keys and any(source_map[i]['topic']==topic for i in cited), 'missing_assessment_evidence', 502)
    return plan


def render(plan, payload, meta):
    application_evidence = action_evidence(plan,payload)
    cited = {f['source_id'] for f in plan['document_facts']}
    cited.update(f['source_id'] for f in application_evidence)
    sources = [s for s in payload['sources'] if s['id'] in cited]
    gaps=[]
    if plan['assessment']=='undetermined':
        gaps.append('Точная причина не установлена.')
    if not payload['sources']:
        gaps.append('В ограниченном FAQ и корпусе Day 30 нет релевантного подтверждения.')
    if payload['ticket_id'] is None:
        gaps.append('Контекст тикета не запрашивался; это общий FAQ-ответ.')
    actions=[{'id':a,'text':payload['allowed_actions'][a]['text'],
              'source_ids':[f['source_id'] for f in application_evidence if f['action_id']==a]}
             for a in plan['action_ids']]
    text='Факты FAQ/документации:\n'+ ('\n'.join(f"[{f['source_id']}] {f['quote']}" for f in plan['document_facts']) or 'Релевантные источники не найдены.')
    text+='\n\nФакты MCP-тикета и пользователя:\n'+ ('\n'.join(f"{f['key']}: {f['quote']}" for f in plan['context_facts']) or 'Нет контекста тикета.')
    text+='\n\nВывод по доступным данным:\n'+ASSESSMENTS[plan['assessment']]
    if application_evidence:
        quotes = dict.fromkeys((f['source_id'],f['quote']) for f in application_evidence)
        text+='\n\nПодтверждение рекомендаций (добавлено приложением):\n'+'\n'.join(
            f'[{source_id}] {quote}' for source_id,quote in quotes)
    text+='\n\nРекомендации модели (следующие проверки, результат не гарантирован):\n'+'\n'.join('- '+a['text'] for a in actions)
    return {'ticket_id':payload['ticket_id'],'answer':text,'assessment':plan['assessment'],
            'document_facts':plan['document_facts'],'context_facts':plan['context_facts'],
            'application_evidence':application_evidence,
            'recommendations':actions,'sources':sources,'context_used':bool(plan['context_facts']),
            'context_user_id':payload['context'].get('user.user_id'), 'evidence_gaps':gaps,
            'retrieval':payload['retrieval'],'llm':meta,'validation':{'source_ids':True,'exact_quotes':True,'context_binding':True,'bounded_claims':True}}


async def answer_async(request, adapter, mcp_command=None):
    validate_request(request)
    ticket=user=None
    if request.get('ticket_id'):
        ticket,user=await fetch_context(request['ticket_id'],mcp_command)
        validate_context(ticket,user)
    payload=prepare(request['question'],ticket,user)
    plan,meta=await asyncio.to_thread(adapter.generate,payload)
    return render(validate_plan(plan,payload),payload,meta)


def answer(request, adapter, mcp_command=None):
    return asyncio.run(answer_async(request,adapter,mcp_command))
