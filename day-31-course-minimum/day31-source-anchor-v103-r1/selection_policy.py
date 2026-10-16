"""Frozen research-only retrieval; no expected source/answer labels in selection."""
from copy import deepcopy
import json,re
from pathlib import Path,PurePosixPath
from time import perf_counter
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
PATTERN=r'стоимост|затрат|cost|overhead|расход'
VOCABULARY=['стоимость','cost','tokens','prompt','completion','total']
GROUPS=[{'стоимость','cost'},{'tokens','токены'},{'prompt'},{'completion'},{'total'}]
IDENTIFIER=re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
NAME='body-code-cost-facets-code-diversity-v3'


def identifiers(question):
    result=[]
    for match in re.finditer(r'(?<!`)`([^`\n]+)`(?!`)',question):
        for word in IDENTIFIER.findall(match.group(1)):
            if word.casefold() not in result:result.append(word.casefold())
    return result[:24]


def fingerprint(quote):
    words=set()
    for match in re.finditer(r'(?<!`)`([^`\n]+)`(?!`)',quote):words.update(IDENTIFIER.findall(match.group(1).casefold()))
    return frozenset(words) if len(words)>=2 else None


def section_key(e):
    p=PurePosixPath(e['source']);name=p.name
    if name.endswith('.ru.md'):name=name[:-6]+'.md'
    return str(p.with_name(name)),' '.join(e['section'].casefold().split())


def previews(case,sources):
    from bublik_developer.generation import Qwen,context_budget
    from bublik_developer.baseline import BaselineQwen
    from bublik_developer.contracts import Role,ContextEnvelope
    from hashlib import sha256
    from runner import digest
    ctx={'question':case['question'],'language':case['language'],'evidence':[{'id':f'e{i}','quote':e['quote']} for i,e in enumerate(sources,1)]}
    values=[]
    for mode,cls,role,c in [('multi',Qwen,Role.DOCUMENTATION,ctx),('single',BaselineQwen,Role.MAIN,{**ctx,'documentation_question':case['question'],'git_facts':[]})]:
        client=cls.__new__(cls);client.context_validator(role,c)
        messages=[{'role':'system','content':client.system_prompt(role,c)},{'role':'user','content':json.dumps(c,ensure_ascii=False,sort_keys=True)}]
        budget=context_budget(messages)
        values.append({'case_id':case['id'],'mode':mode,'context':c,'context_digest':ContextEnvelope.seal(c).digest,
            'message_digest':sha256(json.dumps(messages,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),
            'output_schema_digest':digest(client.schema_builder(role,c)),'context_budget':budget,
            'status':'fits' if budget['estimated_total']<=budget['context_window'] else 'blocked_before_dispatch'})
    return values


def choose(case,candidates,scores):
    from runner import Stop
    remaining=deepcopy(candidates)
    if len(remaining)>20 or len({r['chunk_id'] for r in remaining})!=len(remaining) or set(scores)!={r['chunk_id'] for r in remaining}:raise Stop('Candidate pool mismatch.')
    anchors=set(identifiers(case['question']));groups=GROUPS if re.search(PATTERN,case['question'],re.I) else []
    words={e['chunk_id']:set(IDENTIFIER.findall(e['quote'].casefold()))|set(re.findall(r'[^\W]+',e['quote'].casefold())) for e in remaining}
    covered=set();coveredgroups=set();families=set();selected=[];used=0;trace=[]
    def group_hits(k):return {str(i) for i,g in enumerate(groups) if words[k]&g}
    def redundant(e):
        fp=fingerprint(e['quote'])
        return section_key(e) in families or fp is not None and any(section_key(x)[0]==section_key(e)[0] and fingerprint(x['quote'])==fp for x in selected)
    def ordering(e):
        k=e['chunk_id'];return (-len((words[k]&anchors)-covered),-len(group_hits(k)-coveredgroups),redundant(e),scores[k],k)
    while remaining and len(selected)<3:
        remaining.sort(key=ordering);e=remaining.pop(0);key=e['chunk_id'];size=len(e['quote'].encode())
        row={'chunk_id':key,'new_literal_identifiers':sorted((words[key]&anchors)-covered),'new_cost_groups':sorted(group_hits(key)-coveredgroups),'topical_repetition_heuristic':redundant(e),'body_bm25':scores[key]}
        if used+size>4096:trace.append({**row,'decision':'byte_budget'});continue
        candidate_previews=previews(case,selected+[e])
        if any(p['status']!='fits' for p in candidate_previews):trace.append({**row,'decision':'role_budget'});continue
        selected.append(e);used+=size;covered|=words[key]&anchors;coveredgroups|=group_hits(key);families.add(section_key(e))
        trace.append({**row,'decision':'selected'})
    trace.extend({'chunk_id':r['chunk_id'],'decision':'final_k3_limit'} for r in remaining)
    return selected,trace


def search(index,question,**kwargs):
    from runner import Stop,read_json
    from bublik_developer.rag import retrieval
    started=perf_counter()
    if kwargs.get('mode')!='fts' or kwargs.get('provider') is not None or kwargs.get('sources') is not None:
        raise Stop('Experimental worker admits only the six scoped FTS documentation questions.')
    cases=read_json(HERE/'regression.cases.json')['cases'];matches=[c for c in cases if c['question']==question]
    if len(matches)!=1:raise Stop('Question not in frozen research catalog.')
    case=matches[0];ordinary_terms=retrieval.query_terms
    def terms(q):
        values=ordinary_terms(q)
        if re.search(PATTERN,q,re.I):
            for word in VOCABULARY:
                if word not in values and len(values)<24:values.append(word)
        return values
    with patch.object(retrieval,'query_terms',terms):result=retrieval.search(index,question,**kwargs)
    pool=[index.evidence(r['chunk_id']) for r in result['decisions']];ids=[e['chunk_id'] for e in pool]
    scores={}
    if ids:
        rows=index.db.execute('SELECT c.chunk_id,bm25(search,0,0,0,1) AS body_bm25 FROM search JOIN chunks c ON c.chunk_id=search.chunk_id WHERE search MATCH ? AND c.chunk_id IN ('+','.join('?' for _ in ids)+')',[retrieval.fts_query(result['terms']),*ids]).fetchall()
        scores={r['chunk_id']:r['body_bm25'] for r in rows}
    selected,trace=choose(case,pool,scores)
    expected=read_json(HERE/'expected-selection.json')[case['id']]
    if selected!=expected['sources'] or result['terms']!=expected['terms']:raise Stop('Actual research selection differs from reviewed exact local corpus; no generation.')
    result['sources']=selected;result['decisions']=trace
    result['settings']={**result['settings'],'research_selection_policy':NAME,'bm25_weights':[0,0,0,1],'topical_redundancy_is_semantic_equivalence':False}
    result['metrics']['context_bytes']=sum(len(x['quote'].encode()) for x in selected)
    result['metrics']['total_seconds']=perf_counter()-started
    if index.fresh().revision!=result['corpus_revision']:raise Stop('Index changed.')
    return result
