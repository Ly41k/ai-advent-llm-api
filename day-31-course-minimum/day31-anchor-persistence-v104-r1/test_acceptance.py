"""Offline native replay + synthetic review/tamper/pipeline integration tests."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,AsyncMock

HERE=Path(__file__).resolve().parent
from offline_audit import environment,explicit_review,audit,AUTHORITIES,result_version
core=environment(Path(os.environ['DAY31_V103_PACKAGE']),Path(os.environ['DAY31_TEST_APP']))
from anchor_acceptance import build_record,semantic_gate,attach,verify_envelope,digest,VERSION
from pipeline_adapter import AnchorSnapshotPipeline,SnapshotPipeline

BUNDLE=core.read_json(HERE/'inputs/v103-native-bundle.json')
LEDGER=core.read_json(HERE/'inputs/clause-audit.v103.json')
read=lambda label:BUNDLE['files']['day31-source-anchor-mac-v103-'+label+'.json']['data']
PREVIEWS=core.read_json(Path(os.environ['DAY31_V103_PACKAGE'])/'expected-contexts.json')
ROWS=read('result')['requests']


class AcceptanceTests(unittest.TestCase):
    def args(self,i):
        row=ROWS[i]; result=deepcopy(row['result']);task=result['inference_tasks'][0]
        witness=deepcopy(read('raw-'+task['task_id']))
        ctx=deepcopy(next(x['context'] for x in PREVIEWS if x['mode']==row['mode'] and x['context_digest']==witness['context_digest']))
        return result,witness,ctx,result_version(BUNDLE,result,row['mode'])

    def pair(self,i=0):
        args=self.args(i);record=build_record(*args)
        return record,explicit_review(record,LEDGER['records'][i])

    def rewrite_frame(self,args,edit,reason=None):
        result,w,ctx,version=args;frame=json.loads(w['response']['message']['content']);edit(frame)
        content=json.dumps(frame,ensure_ascii=False);w['response']['message']['content']=content
        from hashlib import sha256
        w['content_sha256']=sha256(content.encode()).hexdigest();w['content_bytes']=len(content.encode())
        if reason:
            result['claims']=[];result['inference_tasks'][0].update(output_validation='rejected',output_validation_reason=reason)
        return args

    def test_no_review_never_means_supported(self):
        for i in range(4):
            record,_=self.pair(i);g=semantic_gate(record)
            self.assertEqual(g['status'],'needs_review');self.assertFalse(g['answer_accepted'])

    def test_ru1_grounding_findings_not_rejected_for_completeness(self):
        for i in [0,1]:
            record,review=self.pair(i);g=semantic_gate(record,review,authorities=AUTHORITIES)
            self.assertEqual(g['status'],'needs_review')
            self.assertTrue(all(c['review_finding']=='supported' for c in g['claims']))
            self.assertFalse(any(c['status']=='unsupported' for c in g['claims']))

    def test_explicit_trusted_human_can_confirm_ru1_without_claim_edits(self):
        record,review=self.pair();review['reviewer']={'id':'fixture-human','kind':'human'}
        g=semantic_gate(record,review,authorities={'fixture-human':'human'})
        self.assertEqual(g['status'],'supported');self.assertTrue(g['answer_accepted'])
        self.assertEqual(g['completeness'],'evaluated_separately')

    def test_assistant_cannot_self_declare_human(self):
        record,review=self.pair();review['reviewer']['kind']='human'
        g=semantic_gate(record,review,authorities=AUTHORITIES)
        self.assertEqual(g['status'],'needs_review');self.assertIsNotNone(g['review_error'])

    def test_unconfigured_human_does_not_approve(self):
        record,review=self.pair();review['reviewer']={'id':'unknown','kind':'human'}
        self.assertFalse(semantic_gate(record,review,authorities=AUTHORITIES)['answer_accepted'])

    def test_en3_single_compound_claim_blocks_as_unsupported(self):
        record,review=self.pair(3);g=semantic_gate(record,review,authorities=AUTHORITIES)
        self.assertTrue(record['runtime_passed']);self.assertEqual(g['status'],'unsupported')
        self.assertEqual(g['claims'][1]['status'],'unsupported');self.assertFalse(g['answer_accepted'])
        self.assertEqual(g['claims'][0]['review_finding'],'supported')

    def test_multi_original_rejection_and_raw_anchors_persist(self):
        args=self.args(2);record,review=self.pair(2)
        out=attach(*args,review,authorities=AUTHORITIES)
        self.assertEqual(out['claims'],[]);self.assertEqual(out['execution_status'],'partial')
        self.assertEqual(len(out['source_anchors']),2)
        self.assertTrue(all(not a['in_answer'] for a in out['source_anchors']))
        self.assertTrue(all(a['runtime_validation']['reason']=='unsupported_identifier' for a in out['source_anchors']))
        self.assertFalse(out['semantic_acceptance']['answer_accepted'])

    def test_synthetic_human_review_cannot_override_runtime_rejection(self):
        record,review=self.pair(2)
        # Fixture reuses verbatim source as a reviewer support span; no claim is
        # changed. This tests runtime precedence, NOT correctness of that review.
        for decision,anchor in zip(review['decisions'],record['source_anchors']):
            decision['status']='supported';decision['clauses']=[{'text':anchor['text'],'status':'supported','reason':'SYNTHETIC deliberately wrong human decision, runtime must still reject.','support_spans':[anchor['quote']]}]
        review['reviewer']={'id':'fixture-human','kind':'human'}
        g=semantic_gate(record,review,authorities={'fixture-human':'human'})
        self.assertEqual(g['status'],'supported');self.assertEqual(g['runtime_validation'],'rejected')
        self.assertFalse(g['answer_accepted'])

    def test_different_claims_keep_different_anchors_and_line_ranges(self):
        record,_=self.pair();a,b=record['source_anchors']
        self.assertNotEqual(a['evidence_id'],b['evidence_id']);self.assertNotEqual(a['quote'],b['quote'])
        for a in record['source_anchors']:
            text=(Path(os.environ['DAY31_V103_PACKAGE'])/'public-corpus54'/a['source']).read_text()
            self.assertEqual(text[a['start']:a['end']],a['quote'])
            self.assertEqual(text.count('\n',0,a['start'])+1,a['start_line'])
            self.assertEqual(text.count('\n',0,a['end'])+1,a['end_line'])

    def test_full_document_correct_fact_is_not_selected_anchor_support(self):
        record,review=self.pair(3)
        d=review['decisions'][1];d['clauses'][-1].update(status='supported',support_spans=['The final verification compares the report read from disk with the original summary.']);d['status']='supported'
        g=semantic_gate(record,review,authorities=AUTHORITIES)
        self.assertEqual(g['status'],'needs_review');self.assertIn('outside_selected_anchor',g['review_error'])

    def test_evidence_from_another_claim_cannot_be_borrowed(self):
        record,review=self.pair()
        review['decisions'][0]['clauses'][0]['support_spans']=[record['source_anchors'][1]['quote']]
        self.assertIn('outside_selected_anchor',semantic_gate(record,review,authorities=AUTHORITIES)['review_error'])

    def test_incomplete_composite_review_is_invalid(self):
        record,review=self.pair(3);review['decisions'][1]['clauses'].pop()
        self.assertIn('incomplete',semantic_gate(record,review,authorities=AUTHORITIES)['review_error'])

    def test_composite_unsupported_cannot_be_overruled_by_top_level_supported(self):
        record,review=self.pair(3);review['decisions'][1]['status']='supported'
        self.assertIn('composite_status_mismatch',semantic_gate(record,review,authorities=AUTHORITIES)['review_error'])

    def test_ambiguous_manual_decision_remains_needs_review(self):
        record,review=self.pair();review['decisions'][0]['clauses'][0]['status']='needs_review';review['decisions'][0]['status']='needs_review'
        review['reviewer']={'id':'fixture-human','kind':'human'}
        self.assertEqual(semantic_gate(record,review,authorities={'fixture-human':'human'})['status'],'needs_review')

    def test_missing_anchor_stays_unverified_and_cannot_be_approved(self):
        args=self.rewrite_frame(self.args(2),lambda f:f['claims'][0].pop('source_quote'),reason='source_anchor_claim_shape')
        record=build_record(*args)
        self.assertEqual(record['source_anchors'][0]['exact_anchor_check'],'failed')
        self.assertEqual(semantic_gate(record)['status'],'needs_review')

    def test_altered_exact_quote_not_silently_upgraded(self):
        args=self.rewrite_frame(self.args(2),lambda f:f['claims'][0].update(source_quote=f['claims'][0]['source_quote']+' '),reason='source_anchor_not_exact_complete_span')
        record=build_record(*args)
        self.assertEqual(record['source_anchors'][0]['exact_anchor_check'],'failed')

    def test_wrong_evidence_id_is_not_repaired(self):
        args=self.rewrite_frame(self.args(2),lambda f:f['claims'][0].update(evidence_ids=['e3']),reason='source_anchor_not_exact_complete_span')
        record=build_record(*args)
        self.assertEqual(record['source_anchors'][0]['evidence_id'],'e3')
        self.assertEqual(record['source_anchors'][0]['exact_anchor_check'],'failed')

    def test_modified_persisted_anchor_is_detected(self):
        record,review=self.pair();record['source_anchors'][0]['quote']+=' changed'
        with self.assertRaisesRegex(ValueError,'anchor_changed'):semantic_gate(record,review,authorities=AUTHORITIES)

    def test_removed_anchor_cannot_drop_a_bad_claim(self):
        record,_=self.pair(3);record['source_anchors'].pop()
        with self.assertRaisesRegex(ValueError,'claim_set_changed'):semantic_gate(record)

    def test_old_review_not_reused_after_result_version_change(self):
        args=self.args(0);old,review=self.pair();args[-1]['pipeline_schema_version']=2
        new=build_record(*args);g=semantic_gate(new,review,authorities=AUTHORITIES)
        self.assertIsNotNone(g['review_error']);self.assertEqual(g['status'],'needs_review')

    def test_original_audit_migration_cannot_rebind_a_changed_version(self):
        args=self.args(0);args[-1]['pipeline_schema_version']=2
        with self.assertRaisesRegex(ValueError,'cannot_migrate_old_review'):
            explicit_review(build_record(*args),LEDGER['records'][0])

    def test_original_audit_migration_cannot_rebind_a_changed_result(self):
        args=self.args(0);args[0]['answer']+=' Changed.'
        with self.assertRaisesRegex(ValueError,'cannot_migrate_old_review'):
            explicit_review(build_record(*args),LEDGER['records'][0])

    def test_old_review_not_reused_after_answer_change(self):
        args=self.args(0);old,review=self.pair();args[0]['answer']+=' Changed final answer.'
        g=semantic_gate(build_record(*args),review,authorities=AUTHORITIES)
        self.assertEqual(g['status'],'needs_review');self.assertIsNotNone(g['review_error'])

    def test_old_review_not_reused_for_different_valid_anchor(self):
        args=self.args(0);old,review=self.pair()
        from source_anchors import catalogs
        oldquote=json.loads(args[1]['response']['message']['content'])['claims'][1]['source_quote']
        candidates=catalogs(args[2])['e2']
        larger=next(a['quote'] for a in candidates if a['quote']!=oldquote and '`pending`' in a['quote'] and '`completed`' in a['quote'])
        args=self.rewrite_frame(args,lambda f:f['claims'][1].update(source_quote=larger))
        new=build_record(*args)
        self.assertEqual(semantic_gate(new,review,authorities=AUTHORITIES)['status'],'needs_review')

    def test_swapped_claim_reviews_rejected(self):
        record,review=self.pair();review['decisions'][0]['binding_sha256']=record['source_anchors'][1]['binding_sha256']
        self.assertIn('binding_changed',semantic_gate(record,review,authorities=AUTHORITIES)['review_error'])

    def test_duplicate_review_id_is_rejected(self):
        record,review=self.pair();review['decisions'].append(deepcopy(review['decisions'][0]))
        self.assertIn('duplicate',semantic_gate(record,review,authorities=AUTHORITIES)['review_error'])

    def test_missing_review_for_one_claim_does_not_approve_whole_answer(self):
        record,review=self.pair();review['decisions'].pop();review['reviewer']={'id':'fixture-human','kind':'human'}
        g=semantic_gate(record,review,authorities={'fixture-human':'human'})
        self.assertEqual(g['claims'][0]['status'],'supported');self.assertEqual(g['status'],'needs_review')

    def test_original_pipeline_fields_are_unchanged(self):
        for i in range(4):
            args=self.args(i);record,review=self.pair(i);out=attach(*args,review,authorities=AUTHORITIES)
            self.assertEqual({k:v for k,v in out.items() if k not in {'source_anchors','anchor_binding','semantic_acceptance'}},args[0])
            self.assertTrue(verify_envelope(out,review,authorities=AUTHORITIES))

    def test_post_review_answer_edit_invalidates_final_envelope(self):
        out=attach(*self.args(0));out['answer']+=' changed'
        with self.assertRaisesRegex(ValueError,'pipeline_result_changed'):verify_envelope(out)

    def test_post_review_gate_edit_invalidates_final_envelope(self):
        out=attach(*self.args(0));out['semantic_acceptance']['answer_accepted']=True
        with self.assertRaisesRegex(ValueError,'gate_decision_changed'):verify_envelope(out)

    def test_record_runtime_rejection_cannot_be_flipped(self):
        record,_=self.pair(2);record['runtime_passed']=True
        with self.assertRaisesRegex(ValueError,'runtime_status_changed'):semantic_gate(record)

    def test_original_identifier_guard_still_rejects_both_bad_multi_claims(self):
        from prompt_profile import validate_anchor_output
        from bublik_developer.contracts import Role
        from bublik_developer.generation import ModelOutputError
        args=self.args(2);frame=json.loads(args[1]['response']['message']['content'])
        for claim in frame['claims']:
            solo={**frame,'claims':[claim]}
            with self.assertRaises(ModelOutputError) as e:validate_anchor_output(Role.DOCUMENTATION,solo,args[2])
            self.assertEqual(e.exception.validation_reason,'unsupported_identifier')

    def test_changed_raw_content_digest_is_detected(self):
        args=self.args(0);args[1]['response']['message']['content']+=' '
        with self.assertRaises(Exception):build_record(*args)

    def test_changed_request_body_digest_is_detected(self):
        args=self.args(0);args[1]['request_body_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'request_body'):build_record(*args)

    def test_context_and_task_mismatch_detected(self):
        args=self.args(0);args[2]['question']='changed'
        with self.assertRaisesRegex(ValueError,'context_mismatch'):build_record(*args)

    def test_repeated_audit_is_deterministic_and_inputs_unchanged(self):
        before=digest(BUNDLE),digest(LEDGER)
        a,ar=audit(BUNDLE,LEDGER,core);b,br=audit(BUNDLE,LEDGER,core)
        self.assertEqual((a,ar),(b,br));self.assertEqual((digest(BUNDLE),digest(LEDGER)),before)
        self.assertEqual([x['result']['semantic_acceptance']['status'] for x in a['requests']],['needs_review','needs_review','unsupported','unsupported'])

    def test_preexisting_extension_is_not_rewritten(self):
        args=self.args(0);args[0]['source_anchors']=[]
        with self.assertRaisesRegex(ValueError,'already_present'):attach(*args)

    def test_final_pipeline_hook_persists_anchors_without_touching_parent_result(self):
        args=self.args(0);native=deepcopy(args[0])
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);raw=core.private_dir(folder/'raw');reports=folder/'reports'
            core.write_new(raw/('raw-'+args[1]['task_id']+'.json'),args[1])
            obj=AnchorSnapshotPipeline.__new__(AnchorSnapshotPipeline)
            obj.anchor_raw_dir=raw;obj.anchor_report_dir=reports;obj.anchor_contexts={args[1]['context_digest']:args[2]}
            obj.anchor_result_version=args[3];obj.anchor_review=None;obj.anchor_authorities=None
            with patch.object(SnapshotPipeline,'run',new=AsyncMock(return_value=native)) as parent:
                out=asyncio.run(obj.run('question'))
            self.assertEqual(parent.await_count,1);self.assertEqual(native,args[0])
            file,=reports.glob('result-*.json');self.assertEqual(core.read_json(file),out)
            self.assertTrue(verify_envelope(out));self.assertEqual(len(out['source_anchors']),2)
            # A second identical finalization creates no duplicate/overwrite.
            before=file.read_bytes()
            with patch.object(SnapshotPipeline,'run',new=AsyncMock(return_value=native)):
                self.assertEqual(asyncio.run(obj.run('question')),out)
            self.assertEqual(file.read_bytes(),before);self.assertEqual(len(list(reports.iterdir())),1)

    def test_pipeline_hook_never_overwrites_existing_different_result(self):
        args=self.args(0);out=attach(*args)
        with tempfile.TemporaryDirectory() as d:
            raw=core.private_dir(Path(d)/'raw');reports=core.private_dir(Path(d)/'reports')
            core.write_new(raw/('raw-'+args[1]['task_id']+'.json'),args[1])
            target=reports/('result-'+args[0]['request_id']+'-'+out['anchor_binding']['binding_sha256']+'.json')
            core.write_new(target,{'old':'do not overwrite'});before=target.read_bytes()
            obj=AnchorSnapshotPipeline.__new__(AnchorSnapshotPipeline)
            obj.anchor_raw_dir=raw;obj.anchor_report_dir=reports;obj.anchor_contexts={args[1]['context_digest']:args[2]};obj.anchor_result_version=args[3];obj.anchor_review=None;obj.anchor_authorities=None
            with patch.object(SnapshotPipeline,'run',new=AsyncMock(return_value=args[0])):
                with self.assertRaisesRegex(ValueError,'persisted_grounding_result_changed'):asyncio.run(obj.run('question'))
            self.assertEqual(target.read_bytes(),before)

    def test_prompt_context_schema_and_original_package_bytes_stay_pinned(self):
        # environment re-verifies every helper file and all installed .py files.
        environment(Path(os.environ['DAY31_V103_PACKAGE']),Path(os.environ['DAY31_TEST_APP']))


if __name__=='__main__':unittest.main(verbosity=2)
