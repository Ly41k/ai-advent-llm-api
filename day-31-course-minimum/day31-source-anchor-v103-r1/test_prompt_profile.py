"""Exact-anchor negative controls, native frames, budgets and guard parity."""
import os,sys,json,re,unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,os.environ['DAY31_TEST_APP'])
import runner as c,prompt_profile as p,source_anchors as a
from bublik_developer.contracts import Role
from bublik_developer.generation import Qwen,ModelOutputError,context_budget
from bublik_developer.baseline import BaselineQwen
HERE=Path(__file__).resolve().parent

class SourceAnchorTests(unittest.TestCase):
    def context(self,mode='multi',case='EN-3'):
        return deepcopy(next(x['context'] for x in c.read_json(HERE/'expected-contexts.json') if x['mode']==mode and x['case_id']==case))
    def anchor(self,ctx,prefix='If Groq returns HTTP 400'):
        return min((r for r in a.catalogs(ctx)['e1'] if r['quote'].startswith(prefix)),key=lambda r:len(r['quote']))['quote']
    def frame(self,mode='multi',quote=None,text='The agent labels this step `agent fallback`.'):
        ctx=self.context(mode);value={'status':'answered','language':'en','claims':[{'source_quote':quote if quote is not None else self.anchor(ctx),'text':text,'evidence_ids':['e1']}]}
        if mode=='single':value['git_fact_ids']=[]
        return value
    def validate(self,value,mode='multi',ctx=None):
        return p.validate_anchor_output(Role.MAIN if mode=='single' else Role.DOCUMENTATION,value,ctx or self.context(mode),single=mode=='single')
    def test_literal_quote_and_text_preserved_with_provenance_in_both_modes(self):
        for mode in ['single','multi']:
            frame=self.frame(mode);before=deepcopy(frame);value=self.validate(frame,mode)
            self.assertEqual(frame,before);self.assertEqual(value['claims'],[{'text':frame['claims'][0]['text'],'evidence_ids':['e1']}])
            self.assertEqual(value['status'],'answered')
    def test_invented_reworded_empty_partial_or_wrong_id_quote_is_rejected(self):
        original=self.frame()['claims'][0]['source_quote']
        for quote in ['',original.replace('HTTP 400','any operation failure'),original[3:],original[:-1],original+' ','The model selects an operation that fails']:
            with self.subTest(quote=quote),self.assertRaises(ModelOutputError):self.validate(self.frame(quote=quote))
        value=self.frame();value['claims'][0]['evidence_ids']=['e2']
        with self.assertRaises(ModelOutputError):self.validate(value)
    def test_negation_cannot_be_removed_from_the_source_anchor(self):
        ctx=self.context(case='RU-1');row=next(r for r in a.catalogs(ctx)['e2'] if r['quote'].startswith('Так прерванный'))
        valid={'status':'answered','language':'ru','claims':[{'source_quote':row['quote'],'text':'Прерванный запрос не становится частью будущего контекста LLM.','evidence_ids':['e2']}]}
        self.validate(valid,ctx=ctx)
        for quote in [row['quote'].replace(' не ', ' '),row['quote'].split(' не ',1)[-1]]:
            bad=deepcopy(valid);bad['claims'][0]['source_quote']=quote
            with self.assertRaises(ModelOutputError):self.validate(bad,ctx=ctx)
    def test_selected_span_not_elsewhere_in_chunk_must_support_identifiers(self):
        ctx=self.context();quote=self.anchor(ctx,'Neither step can be counted')
        value=self.frame(quote=quote,text='The agent uses `tool_use_failed` for this step.')
        self.assertIn('tool_use_failed',ctx['evidence'][0]['quote']);self.assertNotIn('tool_use_failed',quote)
        with self.assertRaises(ModelOutputError) as error:self.validate(value)
        self.assertEqual(error.exception.validation_reason,'unsupported_identifier')
    def test_original_language_encoding_paths_ids_status_and_bounds_remain_enforced(self):
        cases=[]
        for text in ['The agent uses `invented_hidden_state`.','The report is in `/private/invented_file`.','Неверный язык.','The line\nis split.','x'*601]:
            cases.append(self.frame(text=text))
        for field,value in [('status','unknown'),('status','bad'),('language','ru'),('claims',[])]:
            frame=self.frame();frame[field]=value;cases.append(frame)
        for frame in cases:
            with self.subTest(frame=frame),self.assertRaises(ModelOutputError):self.validate(frame)
        frame=self.frame('single');frame['git_fact_ids']=['g99']
        with self.assertRaises(ModelOutputError):self.validate(frame,'single')
        frame=self.frame();frame.update(status='unknown',claims=[]);self.assertEqual(self.validate(frame),frame)
    def test_missing_quote_extra_fields_multiple_ids_and_claim_count_fail_closed(self):
        for kind in ['missing','extra','multiple_ids','wrong_type','six']:
            frame=self.frame();claim=frame['claims'][0]
            if kind=='missing':del claim['source_quote']
            elif kind=='extra':claim['condition']='free paraphrase'
            elif kind=='multiple_ids':claim['evidence_ids']=['e1','e2']
            elif kind=='wrong_type':claim['source_quote']=42
            else:frame['claims']*=6
            with self.subTest(kind=kind),self.assertRaises(ModelOutputError):self.validate(frame)
    def test_full_document_boundaries_exclude_clipped_first_and_last_sentences(self):
        ctx=self.context();e2=ctx['evidence'][1]['quote'];units=a.evidence_units(e2)
        self.assertTrue(units);self.assertTrue(all(r['relative_start']>0 for r in units))
        e1=ctx['evidence'][0]['quote'];self.assertTrue(e1.endswith('agent enforces'))
        self.assertTrue(all(not r['quote'].endswith('agent enforces') for r in a.evidence_units(e1)))
    def test_structured_blocks_stay_whole_and_inline_code_punctuation_is_protected(self):
        text='# Header\n\nNever use `a.b`. Use `c.d` instead.\n\n| A | B |\n|---|---|\n| x | no |\n\n```python\na.b()\n```\n'
        units=a.document_units(text);quotes=[x['quote'] for x in units]
        self.assertIn('Never use `a.b`.',quotes);self.assertNotIn('Never use `a.',quotes)
        tables=[q for q in quotes if q.startswith('|')];self.assertEqual(len(tables),1);self.assertIn('| x | no |',tables[0])
        self.assertTrue(any(q.startswith('```python') and q.endswith('```') for q in quotes))
    def test_all_units_have_exact_offsets_digests_line_ranges_and_no_scope_expansion(self):
        for row in c.read_json(HERE/'expected-contexts.json'):
            for evidence in row['context']['evidence']:
                for unit in a.evidence_units(evidence['quote']):
                    raw=(HERE/'public-corpus54'/unit['source']).read_bytes();text=raw.decode().replace('\r\n','\n').replace('\r','\n')
                    self.assertEqual(c.sha256(raw).hexdigest(),unit['raw_digest']);self.assertEqual(c.sha256(text.encode()).hexdigest(),unit['text_digest'])
                    self.assertEqual(text[unit['start']:unit['end']],unit['quote'])
                    self.assertEqual(evidence['quote'][unit['relative_start']:unit['relative_end']],unit['quote'])
                    self.assertEqual(text.count('\n',0,unit['start'])+1,unit['start_line'])
                    self.assertLessEqual(len(unit['quote']),600)
    def test_schema_binds_quote_enum_to_one_source_and_preserves_existing_text_guards(self):
        import jsonschema
        for row in c.read_json(HERE/'expected-contexts.json'):
            single=row['mode']=='single';cls=p.CoverageBaseline if single else p.CoverageQwen;role=Role.MAIN if single else Role.DOCUMENTATION
            schema=cls.schema_builder(role,row['context']);jsonschema.Draft202012Validator.check_schema(schema)
            for branch in schema['oneOf']:
                for choice in branch['properties']['claims']['items']['oneOf']:
                    self.assertEqual(choice['required'],['source_quote','text','evidence_ids']);self.assertFalse(choice['additionalProperties'])
                    self.assertEqual(choice['properties']['evidence_ids']['maxItems'],1);self.assertIn('not',choice['properties']['text'])
            if row['case_id']=='EN-3':
                jsonschema.validate(self.frame(row['mode']),schema)
                bad=self.frame(row['mode']);bad['claims'][0]['evidence_ids']=['e2']
                with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(bad,schema)
    def test_all_known_budgets_fit_main_schema_and_prompt_remain_identical(self):
        for row in c.read_json(HERE/'known-inputs-55.json')['inputs']:
            single=row['mode']=='single';main=row['mode']=='multi_main';role=Role.MAIN if single or main else Role.DOCUMENTATION
            old_cls=BaselineQwen if single else Qwen;new_cls=p.CoverageBaseline if single else p.CoverageQwen
            old=old_cls.__new__(old_cls);new=new_cls.__new__(new_cls);ctx=row['context'];new.context_validator(role,ctx)
            if main:
                self.assertEqual(new.system_prompt(role,ctx),old.system_prompt(role,ctx));self.assertEqual(new.schema_builder(role,ctx),old.schema_builder(role,ctx))
            budget=context_budget([{'role':'system','content':new.system_prompt(role,ctx)},{'role':'user','content':json.dumps(ctx,ensure_ascii=False,sort_keys=True)}])
            self.assertLessEqual(budget['estimated_total'],8192)
        self.assertTrue(all(x['status']=='fits' for x in c.read_json(HERE/'expected-contexts.json')))
    def test_same_frozen_questions_criteria_contexts_and_target_four_only(self):
        prior=c.read_json(HERE/'research-review.json')['raw_native_reports_subset']['day31-source-anchor-mac-v102-result.json']['data']
        contexts=c.read_json(HERE/'expected-contexts.json')
        for row in prior['requests']:
            new=next(x for x in contexts if x['case_id']==row['case_id'] and x['mode']==row['mode']);task,=row['result']['inference_tasks']
            self.assertEqual(new['context_digest'],task['context_digest']);self.assertNotEqual(new['output_schema_digest'],task['output_schema_digest'])
        prior_plan=c.read_json(HERE/'research-review.json')['raw_native_reports_subset']['day31-source-anchor-mac-v102-plan.json']['data']
        self.assertEqual(c.sha256((HERE/'criteria.frozen.json').read_bytes()).hexdigest(),prior_plan['preparation_binding']['criteria_sha256'])
        self.assertEqual(c.read_json(HERE/'task-selection.frozen.json')['case_ids'],['RU-1','EN-3'])
    def test_exact_quote_is_not_a_semantic_proof_of_paraphrased_outcome(self):
        # Deliberately wrong broadening remains a semantic-review failure.
        value=self.frame(text='The agent uses `agent fallback` whenever an operation fails.')
        result=self.validate(value);self.assertEqual(result['claims'][0]['text'],value['claims'][0]['text'])
    def test_ambiguous_or_unpinned_source_does_not_create_fake_boundaries(self):
        with self.assertRaises(c.Stop):a.evidence_units('A source absent from the pinned project.')
        self.assertIsNone(a.select({'e1':[{'quote':'same'},{'quote':'same'}]},['e1'],'same'))
        with self.assertRaises(c.Stop):p.replace_rules('unrecognized parent prompt','en')

if __name__=='__main__':unittest.main()
