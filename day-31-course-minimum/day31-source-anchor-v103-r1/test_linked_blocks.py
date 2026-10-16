"""Generic Markdown dependency tests; the original native rejection stays intact."""
import json,sys,os,unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,os.environ['DAY31_TEST_APP'])
import source_anchors as a,prompt_profile as p,runner as c
from bublik_developer.contracts import Role
from bublik_developer.generation import ModelOutputError
HERE=Path(__file__).resolve().parent

class LinkedBlockTests(unittest.TestCase):
    def quotes(self,text):return [r['quote'] for r in a.document_units(text)]
    def test_generic_english_and_russian_leadin_stays_with_unordered_list(self):
        for lead in ['Available flags:','Допустимые флаги:']:
            body=lead+'\n\n- `alpha` means ready;\n- `beta` means waiting.\n'
            quotes=self.quotes(body);self.assertEqual(quotes,[body.rstrip()]);self.assertNotIn(lead,quotes)
    def test_ordered_list_table_and_fence_are_kept_with_their_leadin(self):
        for tail in ['1. first\n2. second','| A | B |\n|---|---|\n| x | y |','```text\nraw block\n```']:
            body='# Scope\n\nAllowed data:\n\n'+tail+'\n'
            self.assertEqual(self.quotes(body),['Allowed data:\n\n'+tail])
    def test_no_blank_line_list_or_table_is_indivisible(self):
        for tail in ['- item one.\n- item two.','| A | B |\n|---|---|\n| x | y |']:
            body='Only these are forbidden:\n'+tail
            self.assertEqual(self.quotes(body),[body])
    def test_independent_prose_before_leadin_remains_available(self):
        body='An independent fact. The permitted choices:\n\n- `alpha`;\n- `beta`.'
        quotes=self.quotes(body);self.assertIn('An independent fact.',quotes);self.assertIn(body,quotes)
        self.assertNotIn('The permitted choices:',quotes)
    def test_does_not_merge_across_heading_or_intervening_paragraph(self):
        for between in ['\n\n## Other scope\n\n','\n\nUnrelated prose.\n\n']:
            body='Old lead-in:'+between+'- new block.'
            quotes=self.quotes(body);self.assertIn('Old lead-in:',quotes);self.assertIn('- new block.',quotes)
            self.assertNotIn(body,quotes)
    def test_over_limit_pair_never_falls_back_to_orphan_leadin_or_list(self):
        body='Independent fact.\n\nOnly these entries:\n\n- '+('x'*601)
        self.assertEqual(self.quotes(body),['Independent fact.'])
    def test_links_are_contiguous_exact_spans_and_do_not_cross_excerpt_boundary(self):
        from unittest.mock import patch
        body='# Scope\n\nAllowed flags:\n\n- `alpha`;\n- `beta`.\n'
        units=a.document_units(body);doc={'text':body,'source':'synthetic.md','raw_digest':'synthetic','text_digest':'synthetic','units':units}
        for unit in units:self.assertEqual(body[unit['start']:unit['end']],unit['quote'])
        with patch.object(a,'documents',return_value=[doc]):
            self.assertEqual(a.evidence_units('- `alpha`;\n- `beta`.'),[])
            self.assertEqual(len(a.evidence_units(body)),1)
    def test_native_v102_frame_is_not_repaired_or_reclassified_as_pass(self):
        review=c.read_json(HERE/'research-review.json');frame=deepcopy(review['raw_frame']);before=c.canonical(frame)
        ctx=next(x['context'] for x in c.read_json(HERE/'expected-contexts.json') if x['case_id']=='RU-1' and x['mode']=='single')
        with self.assertRaises(ModelOutputError) as error:p.validate_anchor_output(Role.MAIN,frame,ctx,single=True)
        self.assertEqual(error.exception.validation_reason,'source_anchor_not_exact_complete_span');self.assertEqual(c.canonical(frame),before)
        self.assertEqual(review['rejection']['reason'],'unsupported_identifier')
    def test_synthetic_counterfactual_anchor_has_all_status_tokens_without_guard_relaxation(self):
        review=c.read_json(HERE/'research-review.json');frame=deepcopy(review['raw_frame'])
        ctx=next(x['context'] for x in c.read_json(HERE/'expected-contexts.json') if x['case_id']=='RU-1' and x['mode']=='single')
        choices=a.catalogs(ctx)['e1'];old=frame['claims'][0]['source_quote']
        linked=next(r['quote'] for r in choices if r['quote'].startswith(old+'\n\n'))
        for token in ['pending','completed','failed']:self.assertIn('`'+token+'`',linked)
        # This is a constructed offline fixture, never a replacement native result.
        frame['claims'][0]['source_quote']=linked
        normalized=p.validate_anchor_output(Role.MAIN,frame,ctx,single=True)
        self.assertEqual(normalized['claims'][0]['text'],review['raw_frame']['claims'][0]['text'])
    def test_prompt_text_and_every_guard_are_identical_to_v102(self):
        old=(HERE/'prompt_profile.v102.reference.txt').read_text()
        new=(HERE/'prompt_profile.py').read_text()
        self.assertEqual(old.replace("SCHEMA_VERSION='status-source-quote-text-v1'","SCHEMA_VERSION='status-source-quote-text-v2-linked-blocks'"),new)

if __name__=='__main__':unittest.main()
