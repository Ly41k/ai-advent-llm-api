"""Behavioral tests: citation spoofing, semantic rejection, gates and real CLI/HTTP/SQLite."""

from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from support24 import HERE, Hit, KnowledgeBase, Settings
from corpus import Document
from chunking import chunk_documents
from evidence import (EvidenceError, parse_json, validate_draft, validate_verdict, validate_scope_audit, validate_claim_audit,
                      repair_evidence_options)
from grounded_agent import Day24RAGAgent, StructuredOllama
from strict_agent import StrictRAGAgent, extract_claims, normalize_negative_excerpts
from strict_reference_check import ExtractiveFixtureProvider
from evaluate24 import evaluate, load_questions
from reference_check import FixtureKB, FixtureProvider, reference_inputs, with_quote_ids, with_coverage, scope_fixture, with_group_ids
from quote_catalog import build_catalog, quote_structure
from planning import (validate_plan, compact_catalog, coverage_requirements, validate_coverage, bind_grouped_draft, evidence_groups)
from role_guard import validate_explicit_roles, split_statements

QUOTE = "An independent worker stores snapshots in SQLite."
HIT = Hit("chunk-a", "worker.md", "Background jobs", QUOTE, 0.8, 10, 10)


def draft(statement="An independent worker stores snapshots in SQLite.", quote=QUOTE, chunk_id="chunk-a"):
    return {"status": "answered", "claims": [
        {"text": statement, "citations": [{"chunk_id": chunk_id, "quote": quote}]}]}


class GroundingTests(unittest.TestCase):
    def agent(self, value=None, hits=None, verdict=None):
        provider = FixtureProvider(value if value is not None else draft(), verdict)
        return Day24RAGAgent(FixtureKB([HIT] if hits is None else hits), provider), provider


    def test_answer_contains_answer_sources_quotes_and_claim_links(self):
        result = self.agent()[0].ask("Which process stores snapshots?").to_dict()
        self.assertEqual(result["status"], "answered")
        self.assertIn("[1]", result["answer"])
        self.assertEqual(result["sources"][0]["source"], "worker.md")
        self.assertEqual(result["sources"][0]["section"], "Background jobs")
        self.assertEqual(result["quotes"][0]["quote"], QUOTE)
        self.assertEqual(result["quotes"][0]["claim_id"], 1)
        self.assertTrue(result["validation"]["semantic_supported"])


    def test_source_spoof_and_extra_unvalidated_answer_rejected(self):
        for added in ({"source": "fake.md"}, {"answer": "Uncited invented command"}):
            value = draft()
            value.update(added)
            with self.subTest(added=added):
                result = self.agent(value)[0].ask("Which worker?")
                self.assertEqual(result.status, "unknown")
                self.assertFalse(result.sources)


    def test_quote_must_be_exact_and_from_its_own_selected_chunk(self):
        for value in (draft(quote="Invented command: systemctl restart missing"),
                      draft(chunk_id="other-chunk"),
                      draft(quote=QUOTE.replace("SQLite", "PostgreSQL")),
                      draft(quote="SQLite")):
            with self.subTest(value=value):
                result = self.agent(value)[0].ask("Who stores snapshots?")
                self.assertEqual(result.status, "unknown")
                self.assertEqual(result.reason, "evidence_validation_failed")
                self.assertEqual(result.validation["attempts"], 2)


    def test_every_claim_requires_evidence(self):
        value = draft()
        value["claims"].append({"text": "The interval is always 60 minutes.", "citations": []})
        self.assertEqual(self.agent(value)[0].ask("Interval?").status, "unknown")


    def test_semantic_mismatch_rejected_even_with_real_quote(self):
        verdict = {"answers_question": True, "claims": [
            {"id": 1, "supported": False, "reason": "Quote says SQLite, not PostgreSQL."}]}
        result = self.agent(draft(statement="The worker stores snapshots in PostgreSQL."),
                            verdict=verdict)[0].ask("Which database?")
        self.assertEqual(result.status, "unknown")
        self.assertFalse(result.validation["semantic_supported"])
        self.assertNotIn("PostgreSQL", result.answer)
        self.assertFalse(result.quotes)


    def test_related_but_incomplete_answer_rejected(self):
        verdict = {"answers_question": False, "claims": [
            {"id": 1, "supported": True, "reason": "True but does not answer the question."}]}
        self.assertEqual(self.agent(verdict=verdict)[0].ask("What are the stages?").status, "unknown")


    def test_no_context_or_below_threshold_skips_generation_and_verification(self):
        weak = Hit("weak", "x", "y", QUOTE, 0.499999, 1, 1)
        for hits in ([], [weak]):
            agent, provider = self.agent(hits=hits)
            result = agent.ask("Кто выполняет сбор?")
            self.assertEqual(result.reason, "below_threshold")
            self.assertIn("Не знаю", result.answer)
            self.assertTrue(result.clarification)
            self.assertFalse(result.sources or result.quotes)
            self.assertEqual(provider.calls, [])


    def test_threshold_equality_is_accepted_and_weak_hits_are_not_used(self):
        equal = Hit("chunk-a", "worker.md", "Jobs", QUOTE, 0.50, 1, 1)
        weak = Hit("weak", "leak.md", "Jobs", "Secret rejected text", 0.49, 1, 1)
        agent, provider = self.agent(hits=[weak, equal])
        result = agent.ask("Who stores snapshots?")
        self.assertEqual(result.status, "answered")
        self.assertNotIn("Secret rejected text", "\n".join(provider.calls))
        self.assertEqual(len(result.retrieval["sources"]), 1)


    def test_abstention_with_high_similarity_has_clarification(self):
        agent, provider = self.agent({"status": "unknown", "claims": []})
        result = agent.ask("Exact revenue?")
        self.assertEqual(result.reason, "insufficient_context")
        self.assertTrue(result.clarification)
        self.assertEqual(len(provider.calls), 1)


    def test_strict_json_rejects_duplicate_keys_nonfinite_and_wrappers(self):
        for raw in ('{"status":"unknown","status":"answered"}', '{"x":NaN}',
                    '```json\n{}\n```', '[]', '{} trailing'):
            with self.subTest(raw=raw), self.assertRaises(EvidenceError):
                parse_json(raw)


    def test_verifier_must_judge_each_id_exactly_once(self):
        claims = validate_draft(json.dumps(draft()), [HIT]) * 2
        for ids in ((1, 1), (1, 3), (True, 2)):
            raw = json.dumps(with_coverage({"answers_question": True, "claims": [
                {"id": i, "supported": True, "reason": "supported"} for i in ids]}))
            with self.subTest(ids=ids), self.assertRaises(EvidenceError):
                validate_verdict(raw, claims)


    def test_quote_lines_are_derived_from_chunk(self):
        value = "Heading\n" + QUOTE + "\nMore"
        hit = Hit("chunk-a", "worker.md", "Section", value, 0.8, 20, 22)
        claims = validate_draft(json.dumps(draft()), [hit])
        self.assertEqual(claims[0]["citations"][0]["start_line"], 21)
        self.assertEqual(claims[0]["citations"][0]["end_line"], 21)


    def test_multiple_sources_and_shared_source_number(self):
        value = draft()
        value["claims"].append(deepcopy(value["claims"][0]))
        result = self.agent(value)[0].ask("Which process?")
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(len(result.quotes), 2)
        self.assertEqual(result.answer.count("[1]"), 2)


    def test_embedding_model_dimension_and_normalization_guards(self):
        for vector in ([1.0], [2.0, 0.0], [float("nan"), 0.0]):
            agent, provider = self.agent()
            provider.embed = lambda texts, vector=vector: [vector]
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                agent.ask("Who?")
        agent, provider = self.agent()
        provider.model = "wrong-model"
        with self.assertRaises(ValueError):
            agent.ask("Who?")


    def test_invalid_questions_and_settings(self):
        agent, _ = self.agent()
        for question in ("", " ", None, "x" * 4001):
            with self.subTest(question=str(question)[:20]), self.assertRaises(ValueError):
                agent.ask(question)
        with self.assertRaises(ValueError):
            Settings(min_similarity=float("nan"))


    def test_catalog_fragments_are_literal_source_substrings(self):
        for content in ("Header\n\n" + QUOTE, "x" * 3300,
                        "\n".join([QUOTE] * 50), "# table\n\n| a | value |\n| b | value |"):
            hit = Hit("chunk-a", "worker.md", "Jobs", content, 0.8, 1, 100)
            catalog = build_catalog([hit])
            self.assertTrue(catalog)
            for row in catalog.values():
                self.assertIn(row["quote"], content)
                self.assertTrue(12 <= len(row["quote"]) <= 1600)


    def test_production_validator_does_not_accept_freeform_quotes(self):
        catalog = build_catalog([HIT])
        with self.assertRaises(EvidenceError):
            validate_draft(json.dumps(draft()), [HIT], catalog)


    def test_file_source_path_can_identify_name_but_does_not_prove_behavior(self):
        hit = Hit("chunk-a", "day-18-scheduled-mcp/worker.py", "Worker", QUOTE, 0.8, 1, 1)
        value = draft(statement="worker.py stores snapshots in SQLite.")
        self.assertEqual(self.agent(value, hits=[hit])[0].ask("Which file stores snapshots?").status, "answered")
        value = draft(statement="worker.py stores snapshots in PostgreSQL.")
        verdict = {"answers_question": True, "claims": [{"id": 1, "supported": False,
                   "reason": "The filename matches but the cited database is SQLite."}]}
        result = self.agent(value, hits=[hit], verdict=verdict)[0].ask("Which database does worker.py use?")
        self.assertEqual(result.status, "unknown")
        self.assertTrue(result.validation["quotes_exact"])
        self.assertFalse(result.validation["semantic_supported"])


    def test_verifier_must_explain_missing_requested_facts_consistently(self):
        claims = validate_draft(json.dumps(draft()), [HIT])
        base = {"claims": [{"id": 1, "reason": "The quoted worker stores snapshots in SQLite.", "supported": True}],
                "coverage_reason": "The requested process is identified.",
                "missing_information": [], "answers_question": True}
        for complete, missing in ((False, []), (True, ["The process name is missing."]),
                                  (False, [""]), (False, "process")):
            value = {**base, "answers_question": complete, "missing_information": missing}
            with self.subTest(complete=complete, missing=missing), self.assertRaises(EvidenceError):
                validate_verdict(json.dumps(value), claims)
        legacy = {"answers_question": True, "claims": base["claims"]}
        with self.assertRaises(EvidenceError):
            validate_verdict(json.dumps(legacy), claims)  # Production never invents a coverage reason.
        verdict, accepted = validate_verdict(json.dumps(base), claims)
        self.assertTrue(accepted)
        incomplete = {**base, "coverage_reason": "The process name is missing.",
                      "missing_information": ["The process name is missing."], "answers_question": False}
        _, accepted = validate_verdict(json.dumps(incomplete), claims)
        self.assertFalse(accepted)
        unsupported = deepcopy(base)
        unsupported["claims"][0]["supported"] = False
        _, accepted = validate_verdict(json.dumps(unsupported), claims)
        self.assertFalse(accepted)  # Complete attempted coverage cannot override false claims.


    def test_lesson_number_cannot_prove_actual_execution_on_calendar_date(self):
        lesson = Hit("chunk-a", "day-18-scheduled-mcp/README.md", "README.md", QUOTE, 0.8, 1, 1)
        value = draft(statement="The worker ran and collected data on 2025-01-18.")
        verdict = {"answers_question": True, "claims": [{"id": 1, "supported": False,
                   "reason": "Lesson 18 is not evidence of an actual run on that date."}]}
        result = self.agent(value, hits=[lesson], verdict=verdict)[0].ask("Did the worker run on 2025-01-18?")
        self.assertEqual(result.reason, "evidence_validation_failed")
        self.assertTrue(result.validation["quotes_exact"])
        self.assertFalse(result.validation["semantic_supported"])
        self.assertFalse(result.sources or result.quotes)


    def test_scope_audit_requires_literal_own_fragments_and_consistent_all_claims(self):
        claims = validate_draft(json.dumps(draft()), [HIT])
        valid = scope_fixture(claims)
        bad_values = []
        for change in ({"id": True}, {"id": 2}, {"reason": ""}, {"supported": "true"},
                       {"supported": False}, {"unsupported_spans": ["PostgreSQL"]},
                       {"unsupported_spans": ["SQLite"]}, {"unsupported_spans": "SQLite"},
                       {"unsupported_spans": [""], "supported": False}):
            value = deepcopy(valid)
            value["claims"][0].update(change)
            bad_values.append(value)
        bad_values.extend([{"claims": []}, {"claims": valid["claims"] * 2},
                           {**valid, "answers_question": True}])
        for value in bad_values:
            with self.subTest(value=value), self.assertRaises(EvidenceError):
                validate_scope_audit(json.dumps(value), claims)
        _, accepted = validate_scope_audit(json.dumps(valid), claims)
        self.assertTrue(accepted)
        rejected = deepcopy(valid)
        rejected["claims"][0].update(supported=False, unsupported_spans=["SQLite"])
        _, accepted = validate_scope_audit(json.dumps(rejected), claims)
        self.assertFalse(accepted)


    def test_single_claim_judgment_is_strict_and_ids_are_assigned_by_caller(self):
        claim = {"id": 7, "text": "The collector starts separately."}
        for value in ({}, {"reason": "Yes"}, {"reason": "", "supported": True},
                      {"reason": "Yes", "supported": "true"},
                      {"reason": "Yes", "supported": True, "id": 1},
                      {"reason": "Yes", "supported": True, "unsupported_spans": []}):
            with self.subTest(value=value), self.assertRaises(EvidenceError):
                validate_claim_audit(json.dumps(value), claim)
        rejected = validate_claim_audit(json.dumps({"reason": "No proof", "supported": False}), claim)
        self.assertEqual(rejected["id"], 7)
        self.assertEqual(rejected["unsupported_spans"], [claim["text"]])
        accepted = validate_claim_audit(json.dumps({"reason": "Quoted", "supported": True}), claim)
        self.assertEqual(accepted["unsupported_spans"], [])


    def test_catalog_heading_and_kind_are_derived_without_changing_quote_ids(self):
        content = "# Results summary\n\nContexts persist between runs.\n\n## Mechanism\n\nSelect messages by conversation identity.\n\n```sh\n# not a heading\necho check\n```\n\n[Guide](VERIFY.md)"
        hit = Hit("chunk-a", "lesson.md", "README", content, 0.8, 1, 14)
        catalog = build_catalog([hit])
        by_text = {row["quote"]: row for row in catalog.values()}
        self.assertEqual(by_text["Select messages by conversation identity."]["heading"], "Mechanism")
        self.assertEqual(by_text["[Guide](VERIFY.md)"]["kind"], "reference")
        self.assertEqual(by_text["[Guide](VERIFY.md)"]["heading"], "Mechanism")
        self.assertEqual(by_text["# Results summary"]["kind"], "heading")
        self.assertEqual(quote_structure(HIT, QUOTE)["kind"], "prose")
        for row in catalog.values():
            self.assertIn(row["quote"], content)


    def test_namespace_identity_in_qualified_route_is_not_an_absent_name(self):
        quote = "The route calls analysis.summarize_repository and analysis.verify_report."
        hit = Hit("chunk-a", "routes.md", "Routes", quote, 0.8, 1, 1)
        value = draft("The `analysis` namespace contains `summarize_repository` and `verify_report`.", quote)
        result = self.agent(value, hits=[hit])[0].ask("Which namespace contains the verifier?")
        self.assertEqual(result.status, "answered")
        # Namespacing is literal identity only: it cannot establish transport mode.
        value = draft("The `analysis` server uses HTTP transport.", quote)
        verdict = {"answers_question": True, "claims": [{"id": 1, "supported": False,
                   "reason": "The route names the namespace but does not establish transport."}]}
        result = self.agent(value, hits=[hit], verdict=verdict)[0].ask("Which transport?")
        self.assertEqual(result.status, "unknown")
        for other in ("analysis_extra.verify_report", "analysis-backup.verify_report"):
            bad_hit = Hit("chunk-a", "routes.md", "Routes", other + " validates a report.", 0.8, 1, 1)
            result = self.agent(draft("The `analysis` namespace verifies reports.", bad_hit.text),
                                hits=[bad_hit])[0].ask("Which namespace?")
            self.assertEqual(result.status, "unknown")


    def test_repair_options_only_repeat_existing_literal_evidence(self):
        quote = "- `conversations` stores topics.\n- `messages` stores their messages."
        hit = Hit("chunk-a", "schema.md", "Tables", quote, 0.8, 1, 2)
        catalog = build_catalog([hit])
        raw = json.dumps(draft("The tables are `conversations`, `messages`, and `invented_table`.", quote))
        options = repair_evidence_options(raw, catalog)
        self.assertEqual({r["identifier"] for r in options}, {"conversations", "messages"})
        for row in options:
            self.assertEqual(row["quote"], catalog[row["quote_id"]]["quote"])
            self.assertEqual(row["chunk_id"], catalog[row["quote_id"]]["chunk_id"])
        self.assertLessEqual(sum(len(row["quote"]) for row in options), 4000)
        self.assertEqual(repair_evidence_options("invalid JSON", catalog), [])


    def test_positive_abstention_is_not_a_correct_negative_control(self):
        agent, provider = self.agent(hits=[])
        items = [{"id": "positive", "question": "Who stores snapshots?", "answerable": True},
                 {"id": "negative", "question": "Unknown fact?", "answerable": False}]
        report = evaluate(agent, items)
        first, second = report["details"]
        self.assertTrue(first["checks"]["well_formed_refusal"])
        self.assertFalse(first["checks"]["correct_refusal"] or first["contract_pass"])
        self.assertTrue(second["checks"]["correct_refusal"] and second["contract_pass"])
        self.assertFalse(report["summary"]["all_contract_checks_pass"])
        self.assertEqual(provider.calls, [])


    def test_ten_real_corpus_reference_answers_and_two_negative_controls(self):
        items, inputs = load_questions(), reference_inputs()
        self.assertEqual(sum(item["answerable"] for item in items), 10)
        self.assertEqual(sum(not item["answerable"] for item in items), 2)
        for item in items:
            hits, value = inputs.get(item["id"], ([], {"status": "unknown", "claims": []}))
            with self.subTest(question=item["id"]):
                agent = Day24RAGAgent(FixtureKB(hits), FixtureProvider(value))
                report = evaluate(agent, [item])
                self.assertTrue(report["summary"]["all_contract_checks_pass"])
                if item["answerable"]:
                    self.assertTrue(report["details"][0]["checks"]["expected_source_hit"])


class Scripted(FixtureProvider):
    """Explicitly scripted decisions; tests gates, never the accuracy of a real LLM."""
    def __init__(self, value=None, responses=None):
        super().__init__(value or draft())
        self.responses = deepcopy(responses or {})
        self.events = []

    def structured(self, prompt, schema):
        props = schema['properties']
        stage = ('evidence_selector' if 'parts' in props else 'coverage_auditor' if 'checks' in props
                 else 'fact_auditor' if 'supported' in props else 'draft')
        data, _ = json.JSONDecoder().raw_decode(prompt.split('DATA:\n', 1)[1])
        self.events.append((stage, data, schema))
        if self.responses.get(stage):
            self.calls.append(prompt)
            result = self.responses[stage].pop(0)
            if isinstance(result, BaseException):
                raise result
            if stage == 'draft':
                value = json.loads(result) if isinstance(result, str) and result.startswith('{') else result
                if isinstance(value, dict) and any('citations' in c for c in value.get('claims', []) if isinstance(c, dict)):
                    result = with_group_ids(value, prompt)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return super().structured(prompt, schema)


class EvidenceFirstTests(unittest.TestCase):
    def run_agent(self, provider=None, question='Who stores snapshots?', hits=None):
        provider = provider or Scripted()
        result = Day24RAGAgent(FixtureKB(hits or [HIT]), provider).ask(question)
        return result, provider

    def test_evidence_precedes_draft_and_coverage_is_after_fact_audit(self):
        result, provider = self.run_agent()
        self.assertEqual(result.status, 'answered')
        self.assertEqual([r['stage'] for r in result.validation['model_calls']],
                         ['evidence_selector', 'draft', 'fact_auditor', 'coverage_auditor'])
        self.assertTrue(result.validation['evidence_plan_valid'])
        self.assertTrue(result.validation['coverage_supported'])
        self.assertEqual(result.retrieval['grounding_protocol'], 'bound-evidence-v9')
        for _, _, schema in provider.events:
            self.assertFalse(schema['additionalProperties'])

    def test_selector_unknown_is_not_misreported_as_threshold_refusal(self):
        result, provider = self.run_agent(Scripted(responses={'evidence_selector': [{'status':'unknown','parts':[]}]}))
        self.assertEqual(result.reason, 'insufficient_context')
        self.assertTrue(result.clarification)
        self.assertEqual(len(provider.calls), 1)

    def test_invalid_plan_is_fail_closed_and_no_draft_is_called(self):
        bad = {'status':'ready','parts':[{'need':'Identify the process','quote_ids':['invented']} ]}
        result, provider = self.run_agent(Scripted(responses={'evidence_selector':[bad,bad]}))
        self.assertEqual(result.status, 'unknown')
        self.assertEqual([e[0] for e in provider.events], ['evidence_selector'] * 2)

    def test_plan_rejects_unknown_smuggling_duplicates_extra_fields_and_empty_parts(self):
        catalog=build_catalog([HIT]); good={'status':'ready','parts':[{'need':'Requested process','quote_ids':['q1_1']} ]}
        for bad in ({'status':'unknown','parts':good['parts']}, {'status':'ready','parts':[]},
                    {**good,'answer':'Unverified answer'}, {'status':'ready','parts':good['parts']*2},
                    {'status':'ready','parts':[{'need':'Name','quote_ids':['q1_1','q1_1']}]},
                    {'status':'ready','parts':[{'need':'Name','quote_ids':[True]}]}):
            with self.subTest(value=bad), self.assertRaises(EvidenceError):
                validate_plan(json.dumps(bad), catalog)

    def test_selector_repairs_invalid_structure_with_fresh_evidence(self):
        result, provider = self.run_agent(Scripted(responses={'evidence_selector':['not JSON']}))
        self.assertEqual(result.status, 'answered')
        self.assertEqual(result.validation['attempts'], 2)
        second_plan=provider.events[1][1]
        self.assertEqual(second_plan['correction_feedback']['stage'],'evidence_selector')
        self.assertNotIn('previous_draft',second_plan)

    def test_compact_catalog_keeps_complete_list_and_exact_source_ids(self):
        source='- A worker collects observations.\n- Failed calls retry at the next interval.'
        hit=Hit('x','README.md','Jobs',source,.8,1,2)
        catalog=build_catalog([hit]);compact=compact_catalog(catalog)
        self.assertGreater(len(catalog),len(compact))
        self.assertEqual([r['quote'] for r in compact.values()],[source])
        for ident,row in compact.items():self.assertEqual(row,catalog[ident])

    def test_draft_receives_only_selected_evidence(self):
        other='A different process reads chat messages.'
        hit=Hit('chunk-a','worker.md','Jobs',QUOTE+'\n\n'+other,.8,1,3)
        result, provider=self.run_agent(hits=[hit])
        selector=provider.events[0][1];generator=provider.events[1][1]
        self.assertIn(other,json.dumps(selector))
        self.assertNotIn(other,json.dumps(generator))
        self.assertEqual(len(generator['chunks'][0]['quotes']),1)
        self.assertEqual(result.quotes[0]['quote'],QUOTE)

    def test_draft_cannot_cite_a_real_but_unselected_quote(self):
        other='A viewer reads messages from the selected conversation.'
        hit=Hit('chunk-a','worker.md','Jobs',QUOTE+'\n\n'+other,.8,1,3)
        bad={'status':'answered','claims':[{'text':other,'evidence_group':'unselected'}]}
        result, _=self.run_agent(Scripted(responses={'draft':[bad,bad]}),hits=[hit])
        self.assertEqual(result.status,'unknown')
        self.assertTrue(any('Unknown evidence_group' in e['message'] for e in result.validation['errors']))

    def test_fact_audit_has_only_own_quotes_full_cited_chunks_and_no_question(self):
        hit=Hit('chunk-a','worker.md','Jobs',QUOTE+'\n\nThis worker never pushes chat messages.',.8,1,3)
        other=Hit('other','private.md','Other','Another process reads profile memory.',.7,1,1)
        _,provider=self.run_agent(hits=[hit,other])
        data=next(d for stage,d,_ in provider.events if stage=='fact_auditor')
        self.assertEqual(data['evidence'][0]['text'],QUOTE)
        self.assertEqual([c['chunk_id'] for c in data['chunks']],['chunk-a'])
        self.assertIn('never pushes',data['chunks'][0]['text'])
        self.assertNotIn('question',data)
        self.assertNotIn('verdict',data)
        self.assertNotIn('private.md',json.dumps(data))

    def test_false_fact_cannot_be_overridden_by_coverage(self):
        rejection={'reason':'The quote says SQLite, not PostgreSQL.','supported':False}
        provider=Scripted(draft('The worker stores snapshots in PostgreSQL.'),
                          {'fact_auditor':[rejection,rejection]})
        result,_=self.run_agent(provider)
        self.assertEqual(result.status,'unknown')
        self.assertNotIn('coverage_auditor',[e[0] for e in provider.events])
        self.assertFalse(result.sources or result.quotes)

    def test_each_claim_has_separate_fact_audit_and_every_claim_must_pass(self):
        value=draft();value['claims'].append(deepcopy(value['claims'][0]))
        positive={'reason':'Scripted exact support','supported':True}
        negative={'reason':'Scripted second claim failure','supported':False}
        provider=Scripted(value,{'fact_auditor':[positive,negative,positive,negative]})
        result,_=self.run_agent(provider)
        self.assertEqual(result.status,'unknown')
        rows=[r for r in result.validation['model_calls'] if r['stage']=='fact_auditor']
        self.assertEqual([r['claim_id'] for r in rows],[1,2,1,2])

    def test_task_state_does_not_become_evidence_for_dialogue_isolation(self):
        quote='The task stage is saved in SQLite and restored after restart.'
        hit=Hit('chunk-a','task.md','Task state',quote,.8,1,1)
        value=draft('Dialogue histories are isolated by the saved task stage.',quote)
        verdict={'reason':'Task stage persistence does not establish dialogue isolation.','supported':False}
        result,_=self.run_agent(Scripted(value,{'fact_auditor':[verdict,verdict]}),hits=[hit],
                               question='How are dialogue histories isolated?')
        self.assertEqual(result.status,'unknown');self.assertFalse(result.sources)

    def test_grouped_subject_cannot_inherit_worker_only_service_launch(self):
        quote='The service ExecStart runs worker.py. main.py starts the interactive agent separately.'
        hit=Hit('chunk-a','README.md','Processes',quote,.8,1,1)
        value=draft('worker.py and main.py both start through the service ExecStart.',quote)
        verdict={'reason':'ExecStart launches only worker.py, not main.py.','supported':False}
        result,_=self.run_agent(Scripted(value,{'fact_auditor':[verdict,verdict]}),hits=[hit])
        self.assertEqual(result.status,'unknown');self.assertFalse(result.quotes)

    def test_malformed_fact_judgments_and_missing_coverage_fail_closed(self):
        for stage,bad in [('fact_auditor',{}),('fact_auditor',{'reason':'Yes','supported':'true'}),
                          ('coverage_auditor',{'checks':[]})]:
            with self.subTest(stage=stage):
                result,_=self.run_agent(Scripted(responses={stage:[bad,bad]}))
                self.assertEqual(result.status,'unknown')
                self.assertFalse(result.validation['coverage_supported'])

    def test_coverage_has_answer_text_and_requirements_without_source_passages(self):
        _,provider=self.run_agent(question='How does the process store snapshots?')
        data=next(d for stage,d,_ in provider.events if stage=='coverage_auditor')
        self.assertEqual(data['answer_text'],QUOTE)
        self.assertNotIn('chunks',data);self.assertNotIn('quotes',data);self.assertNotIn('supported',data)
        self.assertIn('mechanism',[r['id'] for r in data['requirements']])

    def test_coverage_requires_all_ids_boolean_and_literal_answer_excerpt(self):
        requirements=[{'id':'question','need':'Identify the process'}]
        claims=[{'text':QUOTE}]
        good={'checks':[{'id':'question','reason':'Identified','covered':True,'answer_excerpt':QUOTE}]}
        for change in ({'id':'other'},{'covered':'true'},{'answer_excerpt':'Made-up explanation'},
                       {'answer_excerpt':''},{'covered':False},{'reason':''}):
            bad=deepcopy(good);bad['checks'][0].update(change)
            with self.subTest(change=change),self.assertRaises(EvidenceError):
                validate_coverage(json.dumps(bad),requirements,claims)
        for bad in ({'checks':good['checks']*2},{'checks':[]},{**good,'answers_question':True}):
            with self.assertRaises(EvidenceError):validate_coverage(json.dumps(bad),requirements,claims)
        _,passed=validate_coverage(json.dumps(good),requirements,claims);self.assertTrue(passed)
        good['checks'][0].update(covered=False,answer_excerpt='')
        _,passed=validate_coverage(json.dumps(good),requirements,claims);self.assertFalse(passed)

    def test_verification_criteria_are_generic_and_not_only_for_day18(self):
        plan={'parts':[{'need':'Check the documented behavior','quote_ids':['q1_1']}]}
        for question in ('How can I verify recurring image imports?', 'Как проверить повторные выгрузки?'):
            ids={r['id'] for r in coverage_requirements(question,plan)}
            self.assertIn('verification-action',ids);self.assertIn('verification-observation',ids)
        ids={r['id'] for r in coverage_requirements('Where is input checked?',plan)}
        self.assertNotIn('verification-observation',ids)

    def test_verification_cannot_reuse_command_excerpt_as_observation(self):
        req=[{'id':'verification-action','need':'Check'},{'id':'verification-observation','need':'Observe'}]
        value={'checks':[{'id':r['id'],'reason':'Yes','covered':True,'answer_excerpt':'Run the check command.'} for r in req]}
        with self.assertRaisesRegex(EvidenceError,'separate'):
            validate_coverage(json.dumps(value),req,[{'text':'Run the check command.'}])

    def test_count_frequency_and_name_questions_do_not_require_a_mechanism(self):
        plan={'parts':[{'need':'Requested value','quote_ids':['q1_1']}]}
        for question in ('How many stages are there?', 'How often are jobs run?', 'Как называется инструмент?'):
            with self.subTest(question=question):
                self.assertNotIn('mechanism',[r['id'] for r in coverage_requirements(question,plan)])

    def test_evidence_plan_limits_total_proof_size(self):
        catalog={f'q{i}':{'chunk_id':'x','quote':str(i)*1550} for i in range(1,7)}
        value={'status':'ready','parts':[{'need':'One part','quote_ids':['q1','q2','q3']},
                                      {'need':'Another part','quote_ids':['q4','q5','q6']}]}
        with self.assertRaisesRegex(EvidenceError,'8000'):
            validate_plan(json.dumps(value),catalog)

    def test_literal_identifier_prefix_and_wrong_commands_are_rejected_before_fact_audit(self):
        quote='systemctl status report-worker-backup'
        hit=Hit('chunk-a','README.md','VPS',quote,.8,1,1)
        for statement in ('Check `report-worker` with `systemctl`.', 'Run `systemctl restart report-worker-backup`.'):
            result,provider=self.run_agent(Scripted(draft(statement,quote)),hits=[hit])
            self.assertEqual(result.status,'unknown')
            self.assertNotIn('fact_auditor',[e[0] for e in provider.events])

    def test_diagram_edge_cannot_override_a_source_state_enum(self):
        diagram='```text\nplanning → execution → validation → done\nexecution ← fail ← validation\n```'
        enum='| `state` | `planning`, `execution`, `validation`, or `done` |'
        hit=Hit('chunk-a','README.md','FSM',diagram+'\n\n'+enum,.8,1,6)
        result,_=self.run_agent(Scripted(draft('The machine has a fail state.',diagram)),hits=[hit])
        self.assertEqual(result.status,'unknown')
        self.assertTrue(any('diagram label' in e['message'] for e in result.validation['errors']))

    def test_true_but_incomplete_answer_reselects_evidence_before_second_draft(self):
        class MissingThenRepair(Scripted):
            def structured(self,prompt,schema):
                if 'checks' in schema['properties'] and not any(e[0]=='coverage_auditor' for e in self.events):
                    data,_=json.JSONDecoder().raw_decode(prompt.split('DATA:\n',1)[1])
                    self.responses['coverage_auditor']=[{'checks':[{'id':r['id'],'reason':'Missing selection rule',
                        'answer_excerpt':'','covered':False} for r in data['requirements']]}]
                return super().structured(prompt,schema)
        result,provider=self.run_agent(MissingThenRepair(),question='How are messages selected?')
        self.assertEqual(result.status,'answered')
        self.assertEqual([e[0] for e in provider.events],
                         ['evidence_selector','draft','fact_auditor','coverage_auditor']*2)
        second=provider.events[4][1]
        self.assertEqual(second['correction_feedback']['stage'],'coverage_auditor')
        self.assertTrue(second['correction_feedback']['missing_requirements'])
        self.assertNotIn('previous_draft',second)
        self.assertNotIn('correction_feedback',provider.events[5][1])

    def test_language_file_identity_commands_and_cross_chunk_guards_survive_v8(self):
        bad_values=[draft('Invented worker.py stores snapshots.'),draft('Check `imaginary_service`.'),
                    draft('Run `sudo imaginary-command`.'),draft('English explanation only.')]
        for value in bad_values:
            with self.subTest(value=value):
                result,_=self.run_agent(Scripted(value),question='Какая программа сохраняет снимки?')
                self.assertEqual(result.status,'unknown');self.assertFalse(result.sources)
        bad={'status':'unknown','claims':[{'text':'Smuggled claim','citations':[]}]}
        result,_=self.run_agent(Scripted(responses={'draft':[bad,bad]}))
        self.assertEqual(result.reason,'evidence_validation_failed')
        two=Hit('chunk-b','other.md','Other','A reader loads saved snapshots.',.7,1,1)
        foreign={'status':'answered','claims':[{'text':QUOTE,'citations':[{'chunk_id':'chunk-b','quote_id':'q1_1'}]}]}
        result,_=self.run_agent(Scripted(responses={'draft':[foreign,foreign]}),hits=[HIT,two])
        self.assertEqual(result.status,'unknown')

    def test_model_transport_failure_remains_a_technical_error_at_every_stage(self):
        for stage in ('evidence_selector','draft','fact_auditor','coverage_auditor'):
            provider=Scripted(responses={stage:[RuntimeError('Transport unavailable')]})
            with self.subTest(stage=stage),self.assertRaisesRegex(RuntimeError,'Transport unavailable'):
                self.run_agent(provider)

    def test_generation_limit_is_recorded_and_blocks_publication(self):
        class Limited(Scripted):
            def structured(self,prompt,schema):
                raw=super().structured(prompt,schema)
                self.last_call_metadata={'done_reason':'length','eval_count':2500}
                return raw
        result,_=self.run_agent(Limited())
        self.assertEqual(result.status,'unknown')
        self.assertEqual(len(result.validation['model_calls']),2)
        self.assertEqual(result.validation['model_calls'][0]['ollama']['done_reason'],'length')

    def test_separate_verifier_receives_only_fact_and_coverage_calls(self):
        generator,verifier=Scripted(),Scripted()
        result=Day24RAGAgent(FixtureKB([HIT]),generator,verifier=verifier).ask('Who stores snapshots?')
        self.assertEqual(result.status,'answered')
        self.assertEqual([e[0] for e in generator.events],['evidence_selector','draft'])
        self.assertEqual([e[0] for e in verifier.events],['fact_auditor','coverage_auditor'])

    def test_current_v7_worker_quotes_are_available_as_complete_evidence(self):
        report=json.loads((HERE/'reports/live/evaluate_v7_both14b_original.json').read_text())
        row=next(d for d in report['details'] if d['id']=='positive-07')
        hits=[Hit(**h) for h in row['result']['retrieval']['sources']]
        available=compact_catalog(build_catalog(hits))
        self.assertTrue(any('повторный запуск будет через заданный интервал' in r['quote'] for r in available.values()))
        value=draft('worker.py periodically collects GitHub repository snapshots into SQLite.',
                    quote='- `worker.py` берёт просроченные задания, вызывает GitHub REST API и сохраняет `stars`, `forks`, `open_issues` и время в SQLite. Ошибки также записываются; повторный запуск будет через заданный интервал.',
                    chunk_id='b165333c1d1e56698605')
        result,_=self.run_agent(Scripted(value),question=row['question'],hits=hits)
        self.assertEqual(result.status,'answered')
        self.assertNotIn('verifier',[r['stage'] for r in result.validation['model_calls']])

    def test_v7_bare_commands_are_refused_when_observation_coverage_is_missing(self):
        report=json.loads((HERE/'reports/live/evaluate_v7_both14b_original.json').read_text())
        row=next(d for d in report['details'] if d['id']=='positive-10')
        hits=[Hit(**h) for h in row['result']['retrieval']['sources']]
        raw=next(c['raw_response'] for c in row['result']['validation']['model_calls'] if c['stage']=='draft')
        value=json.loads(raw)
        # IDs belong to the full old catalog; adapt literals to the compact one.
        for c in value['claims']:
            for ref in c['citations']:
                ref['quote']=row['result']['retrieval']['quote_catalog'][ref.pop('quote_id')]['quote']
        class MissingObservation(Scripted):
            def structured(self,prompt,schema):
                if 'checks' in schema['properties']:
                    data,_=json.JSONDecoder().raw_decode(prompt.split('DATA:\n',1)[1])
                    self.responses['coverage_auditor']=[{'checks':[{'id':r['id'],
                        'answer_excerpt':'' if r['id']=='verification-observation' else data['answer_text'],
                        'reason':'No observed recurring output' if r['id']=='verification-observation' else 'Literal commands',
                        'covered':r['id']!='verification-observation'} for r in data['requirements']]}]
                return super().structured(prompt,schema)
        result,_=self.run_agent(MissingObservation(value),question=row['question'],hits=hits)
        self.assertEqual(result.status,'unknown')
        self.assertTrue(result.validation['semantic_supported'])
        self.assertFalse(result.validation['coverage_supported'])
        self.assertFalse(result.sources or result.quotes)
        class Rejected:
            def ask(self,question):return result
        evaluated=evaluate(Rejected(),[{'id':'control','question':row['question'],'answerable':True}])
        self.assertEqual(evaluated['summary']['positive_semantic_verifier_pass'],0)
        self.assertFalse(evaluated['details'][0]['checks']['scope_supported_by_auditor'])

class BoundEvidenceTests(unittest.TestCase):
    run_agent = EvidenceFirstTests.run_agent
    # Separate new tests without inheriting/rerunning the v8 tests below.
    def test_source_labels_do_not_create_unasked_requirements(self):
        plan={'parts':[{'need':'Discuss pending/completed API statuses','quote_ids':['q1_1']} ]}
        req=coverage_requirements('How are dialogues isolated after restart?',plan)
        self.assertEqual([r['id'] for r in req],['question','mechanism'])
        self.assertNotIn('pending',json.dumps(req))
        _,provider=self.run_agent()
        data=next(d for stage,d,_ in provider.events if stage=='draft')
        self.assertNotIn('requested_parts',data)
        self.assertNotIn('Author-scripted requested evidence',json.dumps(data))

    def test_inflected_verification_question_still_requires_action_and_observation(self):
        plan={'parts':[]}
        for question in ('How is the saved report verified?', 'How are the results checked?'):
            with self.subTest(question=question):
                self.assertEqual([r['id'] for r in coverage_requirements(question,plan)],
                                 ['question','verification-action','verification-observation'])

    def test_group_binding_keeps_entire_selected_joint_proof_from_real_v8_09(self):
        report=json.loads((HERE/'reports/live/recheck_v8_original.json').read_text())
        row=next(d for d in report['details'] if d['id']=='positive-09')['result']
        calls=row['validation']['model_calls'];plan=json.loads([c['raw_response'] for c in calls if c['stage']=='evidence_selector'][-1])
        selected={qid:row['retrieval']['quote_catalog'][qid] for part in plan['parts'] for qid in part['quote_ids']}
        raw={'status':'answered','claims':[{'text':'The report flow is routed across MCP servers.','evidence_group':'e1'}]}
        bound=json.loads(bind_grouped_draft(json.dumps(raw),evidence_groups(plan),selected))
        self.assertEqual([r['quote_id'] for r in bound['claims'][0]['citations']],['q1_2','q1_3','q1_4'])
        # Provenance assembly only: this test does not script a live fact approval.
        hits=[Hit(**h) for h in row['retrieval']['sources']]
        claims=validate_draft(json.dumps(bound),hits,selected)
        self.assertIn('MCP servers',claims[0]['citations'][0]['quote'])

    def test_group_contract_rejects_arbitrary_citations_unknown_ids_and_extra_fields(self):
        selected=build_catalog([HIT]);groups=[{'id':'e1','quote_ids':['q1_1']}]
        for bad in ({'status':'answered','claims':[{'text':QUOTE,'evidence_group':'invented'}]},
                    {'status':'answered','claims':[{'text':QUOTE,'citations':[{'chunk_id':'chunk-a','quote_id':'q1_1'}]}]},
                    {'status':'answered','claims':[{'text':QUOTE,'evidence_group':'e1','answer':'extra'}]},
                    {'status':'unknown','claims':[{'text':QUOTE,'evidence_group':'e1'}]}):
            with self.subTest(value=bad),self.assertRaises(EvidenceError):
                bind_grouped_draft(json.dumps(bad),groups,selected)

    def test_real_v8_05_coverage_accepts_changed_line_breaks_with_identical_words(self):
        report=json.loads((HERE/'reports/live/recheck_v8_original.json').read_text())
        row=next(d for d in report['details'] if d['id']=='positive-05')['result']
        calls=row['validation']['model_calls']
        draft=json.loads(next(c['raw_response'] for c in calls if c['stage']=='draft'))
        verdict=next(c['raw_response'] for c in calls if c['stage']=='coverage_auditor')
        req=row['retrieval']['coverage_requirements']
        _,passed=validate_coverage(verdict,req,draft['claims'])
        self.assertTrue(passed)

    def test_coverage_whitespace_tolerance_does_not_allow_changed_words_case_or_punctuation(self):
        req=[{'id':'question','need':'Check result'}];claims=[{'text':'Run the check.\nTwo snapshots appear.'}]
        base={'id':'question','reason':'Scripted format test','covered':True}
        good={'checks':[{**base,'answer_excerpt':'Run the check.  Two snapshots appear.'}]}
        self.assertTrue(validate_coverage(json.dumps(good),req,claims)[1])
        for excerpt in ('Run the check. Three snapshots appear.','Run the check Two snapshots appear.',
                        'run the check. Two snapshots appear.','Run the check.\u200bTwo snapshots appear.'):
            with self.subTest(excerpt=excerpt),self.assertRaises(EvidenceError):
                validate_coverage(json.dumps({'checks':[{**base,'answer_excerpt':excerpt}]}),req,claims)

    def test_observation_cannot_reuse_action_after_whitespace_normalization(self):
        req=[{'id':'verification-action','need':'Action'},{'id':'verification-observation','need':'Observation'}]
        value={'checks':[{'id':req[0]['id'],'reason':'Scripted','covered':True,'answer_excerpt':'Run the check.'},
                         {'id':req[1]['id'],'reason':'Scripted','covered':True,'answer_excerpt':'Run  the check.'}]}
        with self.assertRaisesRegex(EvidenceError,'separate action'):
            validate_coverage(json.dumps(value),req,[{'text':'Run the check.'}])

    def test_real_v8_07_role_transfer_is_blocked_even_with_positive_llm_decisions(self):
        report=json.loads((HERE/'reports/live/recheck_v8_original.json').read_text())
        row=next(d for d in report['details'] if d['id']=='positive-07')['result']
        with self.assertRaisesRegex(EvidenceError,'assigns.*worker'):
            validate_explicit_roles(row['claims'])
        bad=row['claims'][2];ref=bad['citations'][0]
        value={'status':'answered','claims':[{'text':bad['text'],'citations':[{'chunk_id':ref['chunk_id'],'quote':ref['quote']}]}]}
        hits=[Hit(**h) for h in row['retrieval']['sources']]
        result,provider=self.run_agent(Scripted(value),question=row['question'],hits=hits)
        self.assertEqual(result.status,'unknown');self.assertFalse(result.sources or result.quotes)
        self.assertNotIn('fact_auditor',[e[0] for e in provider.events])
        self.assertTrue(any('assigns' in e['message'] for e in result.validation['errors']))

    def test_correct_agent_role_from_same_real_quotes_is_allowed(self):
        report=json.loads((HERE/'reports/live/recheck_v8_original.json').read_text())
        row=next(d for d in report['details'] if d['id']=='positive-07')['result']
        claims=deepcopy(row['claims']);claims[2]['text']=claims[2]['text'].replace('The worker','The agent')
        validate_explicit_roles(claims)

    def test_explicit_actor_contradictions_in_both_languages_are_supplementary_not_general_entailment(self):
        for quote,statement in (
                ('The client can list available tools.','The server can list available tools.'),
                ('Агент может читать сохранённую сводку.','Worker может читать сохранённую сводку.')):
            with self.subTest(statement=statement),self.assertRaises(EvidenceError):
                validate_explicit_roles([{'id':1,'text':statement,'citations':[{'quote':quote}]}])
        # An implicit/paraphrased action is left to semantic audit; this guard
        # cannot be honestly described as proof of all possible actor relations.
        validate_explicit_roles([{'id':1,'text':'The worker retrieves a report.',
                                 'citations':[{'quote':'The agent can read the persisted summary.'}]}])

    def test_sentence_boundaries_preserve_backticks_file_names_and_original_words(self):
        value='Run `worker.py` with `python -m module`. It writes snapshots to SQLite. Read them.'
        self.assertEqual(split_statements(value),['Run `worker.py` with `python -m module`.',
                                                  'It writes snapshots to SQLite.','Read them.'])

    def test_every_sentence_is_audited_and_a_later_negative_blocks_the_claim(self):
        quote='A process stores observations. It never sends chat notifications.'
        hit=Hit('chunk-a','README.md','Processes',quote,.8,1,1)
        value=draft('A process stores observations. It sends chat notifications.',quote)
        yes={'reason':'Scripted supported first sentence','supported':True}
        no={'reason':'Scripted contradicted second sentence','supported':False}
        result,provider=self.run_agent(Scripted(value,{'fact_auditor':[yes,no,yes,no]}),hits=[hit])
        self.assertEqual(result.status,'unknown')
        calls=[c for c in result.validation['model_calls'] if c['stage']=='fact_auditor']
        self.assertEqual([c['sentence_id'] for c in calls],[1,2,1,2])
        self.assertNotIn('coverage_auditor',[e[0] for e in provider.events])

    def test_only_requested_answer_is_needed_even_if_plan_contains_more_optional_groups(self):
        class ExtraGroup(Scripted):
            def structured(self,prompt,schema):
                if 'parts' in schema['properties']:
                    self.responses['evidence_selector']=[{'status':'ready','parts':[
                        {'need':'Requested responsible process','quote_ids':['q1_1']},
                        {'need':'Unrequested API statuses','quote_ids':['q1_2']}]}]
                return super().structured(prompt,schema)
        text=QUOTE+'\n\nAPI requests use pending and completed statuses.'
        hit=Hit('chunk-a','README.md','Processes',text,.8,1,3)
        result,_=self.run_agent(ExtraGroup(),hits=[hit])
        self.assertEqual(result.status,'answered')
        self.assertEqual([r['id'] for r in result.retrieval['coverage_requirements']],['question'])
        self.assertNotIn('pending',result.answer)


from fixture_proofs import scripted_proof_response


class StrictExtractionTests(unittest.TestCase):
    def run_strict(self, responses=None, hits=None, question='Which process stores snapshots?'):
        class Provider:
            answer_model='scripted; NOT an LLM';model='controlled-fixture';last_call_metadata={}
            def __init__(self):self.events=[];self.responses=deepcopy(responses or {});self.last={}
            def embed(self,texts):return [[1.,0.] for _ in texts]
            def structured(self,prompt,schema):
                stage='extractive_selector' if 'quote_ids' in schema['properties'] else 'coverage_auditor'
                data,_=json.JSONDecoder().raw_decode(prompt.split('DATA:\n',1)[1]);self.events.append((stage,data,prompt))
                if self.responses.get(stage) or stage in self.last:
                    value=self.responses[stage].pop(0) if self.responses.get(stage) else self.last[stage]
                    self.last[stage]=value
                    if isinstance(value,Exception):raise value
                    if isinstance(value,dict) and stage=='coverage_auditor' and isinstance(value.get('checks'),list) and len(value['checks'])==1:
                        row=value['checks'][0]
                        if set(row)=={'id','reason','answer_excerpt','covered'}:
                            value={k:v for k,v in row.items() if k!='id'}
                    if stage=='coverage_auditor':value=scripted_proof_response(data,value)
                    return value if isinstance(value,str) else json.dumps(value)
                if stage=='extractive_selector':return json.dumps({'status':'answered','quote_ids':['q1_1']})
                return json.dumps({'reason':'SCRIPTED coverage judgment','covered':True,'proof_ids':[p['id'] for p in data['proof_units']][:8]})
        provider=Provider();return StrictRAGAgent(FixtureKB(hits or [HIT]),provider).ask(question),provider

    def test_default_cli_style_is_extractive(self):
        run=subprocess.run([sys.executable,str(HERE/'main.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0);self.assertIn('--answer-style {extractive,paraphrase}',run.stdout)

    def test_answer_identity_and_report_support_are_not_called_semantic_approval(self):
        result,provider=self.run_strict();self.assertEqual(result.status,'answered')
        self.assertEqual(result.claims[0]['text'],result.quotes[0]['quote'])
        self.assertTrue(result.validation['verbatim_answer']);self.assertFalse(result.validation['semantic_supported'])
        self.assertFalse(result.validation['semantic_verifier_used'])
        self.assertEqual([e[0] for e in provider.events],['extractive_selector','coverage_auditor'])
        class Agent:
            def ask(self,q):return result
        report=evaluate(Agent(),[{'id':'q','question':result.question,'answerable':True}])
        self.assertTrue(report['summary']['all_contract_checks_pass'])
        self.assertEqual(report['summary']['positive_evidence_support_pass'],1)
        self.assertEqual(report['summary']['positive_semantic_verifier_pass'],0)

    def test_freeform_synthesis_unknown_ids_duplicate_ids_and_extra_fields_are_rejected(self):
        bads=[{'status':'answered','claims':[{'text':'Invented causal relationship','evidence_group':'e1'}]},
              {'status':'answered','quote_ids':['invented']}, {'status':'answered','quote_ids':['q1_1','q1_1']},
              {'status':'answered','quote_ids':['q1_1'],'answer':'Invented'},
              {'status':'unknown','quote_ids':['q1_1']}, {'status':'answered','quote_ids':[True]}]
        for bad in bads:
            with self.subTest(bad=bad):
                result,provider=self.run_strict({'extractive_selector':[bad,bad]})
                self.assertEqual(result.status,'unknown');self.assertFalse(result.sources or result.quotes)
                self.assertNotIn('coverage_auditor',[e[0] for e in provider.events])

    def test_real_v9_09_unsupported_synthesis_cannot_be_published(self):
        p=json.loads((HERE/'reports/live/recheck_v9_original.json').read_text())
        row=next(d for d in p['details'] if d['id']=='positive-09')['result']
        bad=next(c['raw_response'] for c in row['validation']['model_calls'] if c['stage']=='draft')
        hits=[Hit(**h) for h in row['retrieval']['sources']]
        result,_=self.run_strict({'extractive_selector':[bad,bad]},hits=hits,question=row['question'])
        self.assertEqual(result.status,'unknown')
        catalog=compact_catalog(build_catalog(hits))
        claims=extract_claims(json.dumps({'status':'answered','quote_ids':['q1_4']}),hits,catalog)
        self.assertEqual(claims[0]['text'],claims[0]['citations'][0]['quote'])
        self.assertNotIn('without model selection errors',claims[0]['text'])
        self.assertIn('agent correction',claims[0]['text'])

    def test_course_scope_is_given_to_coverage_without_uncited_content(self):
        hit=Hit('chunk-a','day-18-scheduled-mcp/README.md','Worker',QUOTE,.8,1,1)
        result,p=self.run_strict(hits=[hit],question='Which process stores snapshots on Day 18?')
        _,data,prompt=next(e for e in p.events if e[0]=='coverage_auditor')
        self.assertIn('not a calendar date',prompt)
        self.assertEqual(data['lesson_scope'][0]['course_lesson'],18)
        self.assertNotIn('chunks',data);self.assertNotIn('quote_catalog',data)
        self.assertTrue(result.validation['coverage_supported'])

    def test_negative_nonempty_excerpt_keeps_false_and_feedback_reason(self):
        raw={'checks':[{'id':'question','covered':False,'reason':'Missing the observable result',
                        'answer_excerpt':QUOTE}]}
        normalized,adjusted=normalize_negative_excerpts(json.dumps(raw))
        value=json.loads(normalized);self.assertEqual(adjusted,['question'])
        self.assertFalse(value['checks'][0]['covered']);self.assertEqual(value['checks'][0]['answer_excerpt'],'')
        result,p=self.run_strict({'coverage_auditor':[raw,raw]})
        self.assertEqual(result.status,'unknown')
        selector=[e[1] for e in p.events if e[0]=='extractive_selector'][1]
        self.assertIn('Missing the observable result',selector['correction_feedback']['problems'])
        self.assertTrue(all(not a['decisions_changed'] for a in result.validation['format_adjustments']))

    def test_malformed_false_string_or_missing_requirements_are_not_repaired(self):
        for bad in ({'checks':[]},{'checks':[{'id':'question','covered':'false','reason':'No','answer_excerpt':QUOTE}]}):
            with self.subTest(bad=bad):
                result,_=self.run_strict({'coverage_auditor':[bad,bad]})
                self.assertEqual(result.status,'unknown');self.assertFalse(result.validation['coverage_supported'])

    def test_below_threshold_skips_structured_calls_and_returns_clarification(self):
        hit=Hit('chunk-a','worker.md','Jobs',QUOTE,.49,1,1)
        result,p=self.run_strict(hits=[hit]);self.assertEqual(result.reason,'below_threshold')
        self.assertEqual(p.events,[]);self.assertTrue(result.clarification);self.assertFalse(result.sources or result.quotes)

    def test_high_similarity_unknown_is_distinct_and_has_no_fake_proof(self):
        result,_=self.run_strict({'extractive_selector':[{'status':'unknown','quote_ids':[]}]})
        self.assertEqual(result.reason,'insufficient_context');self.assertTrue(result.clarification)
        self.assertFalse(result.sources or result.quotes)

    def test_strict_limits_for_long_passages_and_six_quotes(self):
        prose='The worker stores snapshots in SQLite. '+('The process preserves saved observations. '*23)
        hit=Hit('long','README.md','Jobs',prose,.8,1,1);catalog=build_catalog([hit])
        claims=extract_claims(json.dumps({'status':'answered','quote_ids':['q1_1']}),[hit],catalog)
        self.assertGreater(len(claims[0]['text']),800);self.assertLess(len(claims[0]['text']),1600)
        many=Hit('many','README.md','Jobs','\n\n'.join('Passage %d explains a different process.'%i for i in range(7)),.8,1,13)
        catalog=build_catalog([many])
        with self.assertRaises(EvidenceError):extract_claims(json.dumps({'status':'answered','quote_ids':list(catalog)[:7]}),[many],catalog)

    def test_real_v9_correct_worker_draft_uses_source_quotes_without_actor_transfer(self):
        p=json.loads((HERE/'reports/live/recheck_v9_original.json').read_text())
        row=next(d for d in p['details'] if d['id']=='positive-07')['result']
        hits=[Hit(**h) for h in row['retrieval']['sources']]
        claims=extract_claims(json.dumps({'status':'answered','quote_ids':['q1_3','q1_5']}),hits,compact_catalog(build_catalog(hits)))
        self.assertTrue(any('worker.py' in c['text'] for c in claims))
        self.assertTrue(any('The agent can read' in c['text'] for c in claims))
        self.assertFalse(any('The worker can read' in c['text'] for c in claims))

    def test_ten_real_corpus_cases_and_two_negative_controls_with_scripted_selection(self):
        inputs=reference_inputs()
        for item in load_questions():
            with self.subTest(id=item['id']):
                if item['answerable']:
                    hits,value=inputs[item['id']]
                    agent=StrictRAGAgent(FixtureKB(hits),ExtractiveFixtureProvider(value))
                else:
                    score=.8 if item['id']=='negative-01' else .49
                    h=Hit('negative','README.md','Course',QUOTE,score,1,1)
                    agent=StrictRAGAgent(FixtureKB([h]),ExtractiveFixtureProvider({'status':'unknown','claims':[]}))
                report=evaluate(agent,[item]);self.assertTrue(report['summary']['all_contract_checks_pass'])
                if item['answerable']:
                    for c in report['details'][0]['result']['claims']:self.assertEqual(c['text'],c['citations'][0]['quote'])

    def test_transport_failures_remain_errors_in_both_strict_stages(self):
        for stage in ('extractive_selector','coverage_auditor'):
            with self.subTest(stage=stage),self.assertRaisesRegex(RuntimeError,'unavailable'):
                self.run_strict({stage:[RuntimeError('unavailable')]})

    def test_strict_length_stop_cannot_publish_a_well_formed_selection(self):
        class Truncated(ExtractiveFixtureProvider):
            last_call_metadata={'done_reason':'length'}
        provider=Truncated(draft())
        result=StrictRAGAgent(FixtureKB([HIT]),provider).ask('Which process stores snapshots?')
        self.assertEqual(result.status,'unknown');self.assertFalse(result.sources or result.quotes)
        self.assertEqual(result.validation['attempts'],2)
        self.assertTrue(all(c['stage']=='extractive_selector' for c in result.validation['model_calls']))

    def test_code_fence_source_marker_is_outside_fence(self):
        quote='```text\nFetch → summarize → save → read → verify\n```'
        hit=Hit('chunk-a','README.md','Flow',quote,.8,1,3)
        result,_=self.run_strict(hits=[hit])
        self.assertIn('```\n[1]',result.answer)
        self.assertEqual(result.claims[0]['text'],quote)

    def test_default_cli_strict_uses_real_sqlite_http_and_two_model_stages(self):
        records=[]
        document=Document('worker.md','worker.md',QUOTE,'fixture');chunks=chunk_documents([document],'fixed')
        authored=draft(chunk_id=chunks[0].chunk_id);provider=ExtractiveFixtureProvider(authored)
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));records.append((self.path,body))
                result=({'embeddings':[[1.,0.] for _ in body['input']]} if self.path=='/api/embed' else
                        {'response':provider.structured(body['prompt'],body['format']),'done':True,'done_reason':'stop'})
                data=json.dumps(result).encode();self.send_response(200);self.end_headers();self.wfile.write(data)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);db=root/'knowledge.db';kb=KnowledgeBase(db)
                kb.save([document],'fixed',chunks,[[1.,0.]],'fixture-embedding',500,75,'fixture');kb.close()
                qs=root/'qs.json';qs.write_text(json.dumps([{'id':'q','question':'Which process stores snapshots?','answerable':True}]))
                output=root/'report.json'
                args=[sys.executable,str(HERE/'main.py'),'--db',str(db),'--url',f'http://127.0.0.1:{server.server_port}',
                      '--model','fixture-embedding','evaluate','--questions',str(qs),'--output',str(output)]
                run=subprocess.run(args,capture_output=True,text=True,timeout=20)
                self.assertEqual(run.returncode,0,run.stderr);report=json.loads(output.read_text())
                self.assertEqual(report['details'][0]['result']['retrieval']['grounding_protocol'],'verbatim-extractive-v14')
                self.assertEqual([p for p,b in records],['/api/embed','/api/generate','/api/generate'])
                self.assertTrue(all(b['model']=='qwen2.5:14b' for p,b in records[1:]))
                self.assertTrue(output.with_suffix('.md').is_file())
                provider.draft={'status':'unknown','claims':[]}
                run=subprocess.run(args,capture_output=True,text=True,timeout=20)
                self.assertEqual(run.returncode,1);self.assertFalse(json.loads(output.read_text())['summary']['all_contract_checks_pass'])
        finally:server.shutdown();server.server_close();t.join()


class CriterionCoverageTests(unittest.TestCase):
    run_strict = StrictExtractionTests.run_strict

    def test_real_v10_09_duplicate_batch_cannot_enter_single_verdict_contract(self):
        report=json.loads((HERE/'reports/live/recheck_v10_original.json').read_text())
        row=next(r for r in report['details'] if r['id']=='positive-09')['result']
        raw=next(c['raw_response'] for c in row['validation']['model_calls'] if c['stage']=='coverage_auditor')
        result,_=self.run_strict({'coverage_auditor':[raw,raw]})
        self.assertEqual(result.status,'unknown')
        self.assertTrue(all('exactly these keys' in e['message'] for e in result.validation['errors']))

    def test_real_v10_09_selection_can_publish_with_one_valid_verdict_per_requirement(self):
        report=json.loads((HERE/'reports/live/recheck_v10_original.json').read_text())
        row=next(r for r in report['details'] if r['id']=='positive-09')['result']
        selection=next(c['raw_response'] for c in row['validation']['model_calls'] if c['stage']=='extractive_selector')
        class Provider:
            answer_model='scripted valid criterion proof; NOT an LLM';model='controlled-fixture';last_call_metadata={}
            def __init__(self):self.events=[]
            def embed(self,texts):return [[1.,0.] for _ in texts]
            def structured(self,prompt,schema):
                data,_=json.JSONDecoder().raw_decode(prompt.split('DATA:\n',1)[1]);self.events.append((data,schema))
                if 'quote_ids' in schema['properties']:return selection
                key=data['coverage_requirement']['id']
                excerpt={'question':'The registry discovers tools and routes each selected call to the correct server session.',
                         'verification-action':'The final verification compares the report read from disk with the original summary.',
                         'verification-observation':'the agent only reports success after `verified=true`.'}[key]
                return json.dumps(scripted_proof_response(data,{'covered':True,'reason':'AUTHOR-SCRIPTED fixture, NOT an LLM judgment','answer_excerpt':excerpt}))
        provider=Provider();hits=[Hit(**h) for h in row['retrieval']['sources']]
        result=StrictRAGAgent(FixtureKB(hits),provider).ask(row['question'])
        self.assertEqual(result.status,'answered')
        calls=[c for c in result.validation['model_calls'] if c['stage']=='coverage_auditor']
        self.assertEqual([c['requirement_id'] for c in calls],['question','verification-action','verification-observation'])
        self.assertEqual([c['id'] for c in result.validation['coverage_verdict']['checks']],['question','verification-action','verification-observation'])
        for data,schema in provider.events[1:]:
            self.assertNotIn('requirements',data)
            self.assertEqual(set(schema['properties']),{'covered','reason','proof_ids'})
        self.assertTrue(all(c['text']==c['citations'][0]['quote'] for c in result.claims))

    def test_model_cannot_assign_a_criterion_id_or_inject_an_additional_judgment(self):
        bad={'id':'other','reason':'Scripted','covered':True,'answer_excerpt':QUOTE}
        result,_=self.run_strict({'coverage_auditor':[bad,bad]})
        self.assertEqual(result.status,'unknown');self.assertFalse(result.validation['coverage_supported'])

    def test_real_v10_10_command_subset_does_not_prove_observed_result(self):
        report=json.loads((HERE/'reports/live/recheck_v10_original.json').read_text())
        row=next(r for r in report['details'] if r['id']=='positive-10')['result']
        raw=json.dumps(row['validation']['coverage_verdict'])
        _,legacy=validate_coverage(raw,row['retrieval']['coverage_requirements'],row['claims'])
        self.assertTrue(legacy) # Demonstrates the actual prior weakness, not a scripted refusal.
        with self.assertRaisesRegex(EvidenceError,'contained'):
            validate_coverage(raw,row['retrieval']['coverage_requirements'],row['claims'],disjoint_verification=True)

    def test_nested_command_proof_retries_and_needs_a_real_result_excerpt(self):
        command='```bash\njournalctl -u example -f\n```'
        observation='Two snapshots with different timestamps appear after scheduled runs.'
        hit=Hit('chunk-a','README.md','Checks',command+'\n\n'+observation,.8,1,5)
        class Provider:
            answer_model='scripted retry; NOT an LLM';model='controlled-fixture';last_call_metadata={}
            def __init__(self):self.attempt=0;self.events=[]
            def embed(self,texts):return [[1.,0.] for _ in texts]
            def structured(self,prompt,schema):
                data,_=json.JSONDecoder().raw_decode(prompt.split('DATA:\n',1)[1]);self.events.append(data)
                if 'quote_ids' in schema['properties']:
                    self.attempt+=1;return json.dumps({'status':'answered','quote_ids':['q1_1','q1_2']})
                ident=data['coverage_requirement']['id']
                excerpt=(observation if self.attempt==2 else 'journalctl -u example -f') if ident=='verification-observation' else command
                return json.dumps(scripted_proof_response(data,{'covered':True,'answer_excerpt':excerpt,'reason':'AUTHOR-SCRIPTED criterion verdict'}))
        provider=Provider();result=StrictRAGAgent(FixtureKB([hit]),provider).ask('How can I verify recurring snapshots?')
        self.assertEqual(result.status,'answered');self.assertEqual(result.validation['attempts'],2)
        self.assertIn('ineligible',result.validation['errors'][0]['message'])
        self.assertNotIn('previous_answer',next(d for d in provider.events if d.get('correction_feedback')))

    def test_python_rendering_preserves_claim_and_quote_identity(self):
        code='tools_result = await session.list_tools()'
        hit=Hit('chunk-a','client.py','Discovery',code,.8,1,1)
        result,_=self.run_strict(hits=[hit])
        self.assertEqual(result.status,'answered')
        self.assertEqual(result.claims[0]['text'],code);self.assertEqual(result.quotes[0]['quote'],code)
        self.assertEqual(result.answer,'```python\n'+code+'\n```\n[1]')



from coverage_proofs import build_proofs, proof_choices, proof_schema, validate_proof_verdict


class ProofIDCoverageTests(unittest.TestCase):
    def proofs(self, body, source='README.md'):
        hit=Hit('chunk-a',source,'Checks',body,.8,1,body.count('\n')+1)
        cat=compact_catalog(build_catalog([hit]))
        claims=extract_claims(json.dumps({'status':'answered','quote_ids':list(cat)[:6]}),[hit],cat)
        return build_proofs(claims),claims

    def test_proof_units_are_exact_owned_answer_substrings(self):
        body='The client initializes. It lists tools.\n\n| state | PASS |\n|---|---|\n| done | terminal |'
        proofs,claims=self.proofs(body)
        self.assertTrue(proofs)
        for p in proofs.values():
            c=claims[p['claim_id']-1]
            self.assertIn(p['text'],c['text']);self.assertEqual(p['quote_id'],c['citations'][0]['quote_id'])
            self.assertEqual(p['chunk_id'],c['citations'][0]['chunk_id'])

    def test_coverage_ids_cannot_invent_splice_or_reference_unselected_text(self):
        proofs,_=self.proofs('The client initializes. It lists tools.')
        requirement={'id':'question','need':'Explain discovery'}
        for ids in (['invented'],['p1_1','p1_1'],[True],[],['q999'],list(proofs)*5):
            with self.subTest(ids=ids),self.assertRaises(EvidenceError):
                validate_proof_verdict(json.dumps({'reason':'Scripted','covered':True,'proof_ids':ids}),requirement,proofs)
        with self.assertRaises(EvidenceError):
            validate_proof_verdict(json.dumps({'reason':'Scripted','covered':True,'proof_ids':['p1_1'],'answer_excerpt':'Invented'}),requirement,proofs)

    def test_negative_decision_never_becomes_approval_even_with_valid_ids(self):
        proofs,_=self.proofs('The client initializes.')
        row=validate_proof_verdict(json.dumps({'reason':'Missing names','covered':False,'proof_ids':['p1_1']}),{'id':'question'},proofs)
        self.assertFalse(row['covered']);self.assertEqual(row['reason'],'Missing names')
        self.assertEqual(row['proof_ids'],[]);self.assertEqual(row['proofs'],[])

    def test_observation_choices_exclude_every_shell_command_and_selected_action(self):
        body='```bash\nsudo systemctl status example\njournalctl -u example -f\n```\n\nCompare the saved report. Success is returned only when verified=true.'
        proofs,_=self.proofs(body)
        action=[p for p in proofs.values() if p['text']=='Compare the saved report.'][0]
        allowed=proof_choices(proofs,{'id':'verification-observation'},[{'id':'verification-action','proofs':[action]}])
        self.assertNotIn(action['id'],allowed)
        self.assertFalse(any(p['command_only'] for p in allowed.values()))
        self.assertTrue(any('verified=true' in p['text'] for p in allowed.values()))

    def test_real_v11_09_has_available_exact_routing_and_success_proof_units(self):
        report=json.loads((HERE/'reports/live/evaluate_v11_original.json').read_text())
        r=next(d for d in report['details'] if d['id']=='positive-09')['result']
        hits=[Hit(**h) for h in r['retrieval']['sources']];cat=compact_catalog(build_catalog(hits))
        raw=next(c['raw_response'] for c in r['validation']['model_calls'] if c['stage']=='extractive_selector')
        claims=extract_claims(raw,hits,cat);proofs=build_proofs(claims)
        compare=next(p for p in proofs.values() if p['text'].startswith('The final verification compares'))
        allowed=proof_choices(proofs,{'id':'verification-observation'},[{'id':'verification-action','proofs':[compare]}])
        success=next(p for p in allowed.values() if 'verified=true' in p['text'])
        row=validate_proof_verdict(json.dumps({'reason':'AUTHOR-SCRIPTED fixture, not LLM quality','covered':True,'proof_ids':[success['id']]}),{'id':'verification-observation'},allowed)
        self.assertIn(row['answer_excerpt'],claims[2]['text'])
        self.assertEqual(row['proofs'][0]['text'],success['text'])

    def test_real_v11_10_wrong_command_is_ineligible_but_recurring_output_remains(self):
        report=json.loads((HERE/'reports/live/evaluate_v11_original.json').read_text())
        r=next(d for d in report['details'] if d['id']=='positive-10')['result']
        hits=[Hit(**h) for h in r['retrieval']['sources']];cat=compact_catalog(build_catalog(hits))
        raw=next(c['raw_response'] for c in r['validation']['model_calls'] if c['stage']=='extractive_selector')
        claims=extract_claims(raw,hits,cat);proofs=build_proofs(claims)
        command=next(p for p in proofs.values() if p['text']=='journalctl -u bublik-day18 -f')
        allowed=proof_choices(proofs,{'id':'verification-observation'},[])
        self.assertNotIn(command['id'],allowed)
        self.assertTrue(any('after each run' in p['text'] for p in allowed.values()))
        with self.assertRaises(EvidenceError):
            validate_proof_verdict(json.dumps({'reason':'Command is outcome','covered':True,'proof_ids':[command['id']]}),{'id':'verification-observation'},allowed)

    def test_schema_has_only_owned_enum_ids_and_empty_choices_cannot_be_approved(self):
        proofs,_=self.proofs('The client initializes.')
        schema=proof_schema(proofs)
        self.assertEqual(schema['properties']['proof_ids']['items']['enum'],list(proofs))
        self.assertEqual(set(schema['properties']),{'reason','proof_ids','covered'})
        self.assertEqual(proof_schema({})['properties']['proof_ids']['maxItems'],0)
        with self.assertRaises(EvidenceError):
            validate_proof_verdict(json.dumps({'reason':'No evidence','covered':True,'proof_ids':[]}),{'id':'question'}, {})

    def test_format_repair_reuses_answer_and_does_not_reselect_on_single_bad_id(self):
        class Provider:
            answer_model='scripted format repair, NOT an LLM';model='controlled-fixture';last_call_metadata={}
            def __init__(self):self.calls=[]
            def embed(self,texts):return [[1.,0.] for _ in texts]
            def structured(self,prompt,schema):
                self.calls.append(schema)
                if 'quote_ids' in schema['properties']:
                    return json.dumps({'status':'answered','quote_ids':['q1_1']})
                ids=[] if len(self.calls)==2 else [schema['properties']['proof_ids']['items']['enum'][0]]
                return json.dumps({'reason':'AUTHOR-SCRIPTED repair','covered':True,'proof_ids':ids})
        provider=Provider();r=StrictRAGAgent(FixtureKB([HIT]),provider).ask('Which process stores snapshots?')
        self.assertEqual(r.status,'answered');self.assertEqual(r.validation['attempts'],1)
        self.assertEqual(len(provider.calls),3)
        self.assertTrue(r.validation['model_calls'][2]['repair'])
        self.assertEqual(sum('quote_ids' in s['properties'] for s in provider.calls),1)

    def test_false_semantic_verdict_is_not_format_retried_into_approval(self):
        r,p=StrictExtractionTests.run_strict(self, {'coverage_auditor':[{'reason':'Missing mechanism','covered':False,'proof_ids':[]}]})
        self.assertEqual(r.status,'unknown');self.assertFalse(r.sources or r.quotes)
        calls=[c for c in r.validation['model_calls'] if c['stage']=='coverage_auditor']
        self.assertEqual(len(calls),2);self.assertFalse(any(c.get('repair') for c in calls))

    def test_retrieved_unselected_chunk_never_enters_proof_units(self):
        selected=Hit('chunk-a','worker.md','Snapshots',QUOTE,.8,1,1)
        extra=Hit('chunk-b','other.md','Private','An unrelated secret is persisted elsewhere.',.7,1,1)
        r,p=StrictExtractionTests.run_strict(self,hits=[selected,extra])
        self.assertEqual(r.status,'answered')
        data=next(d for stage,d,prompt in p.events if stage=='coverage_auditor')
        self.assertTrue(all(v['chunk_id']=='chunk-a' for v in data['proof_units']))
        self.assertNotIn('unrelated secret',json.dumps(data))


from coverage_proofs import strict_requirements, coverage_task


class ScopedCoverageV13Tests(unittest.TestCase):
    def test_how_has_one_gate_that_still_requires_all_requested_parts(self):
        for q in ('How are dialogues isolated and restored after restart?', 'Как устроены поиск и сохранение?'):
            rows=strict_requirements(q)
            self.assertEqual([r['id'] for r in rows],['mechanism'])
            self.assertIn('ALL parts',rows[0]['need'])
            self.assertIn('concrete operations or rules',rows[0]['need'])
        self.assertEqual([r['id'] for r in coverage_requirements('How are dialogues isolated?',{})],['question','mechanism'])

    def test_names_counts_and_verification_keep_their_required_gates(self):
        for q in ('How many workers run?', 'Как называется процесс?', 'Where is state restored?'):
            self.assertEqual([r['id'] for r in strict_requirements(q)],['question'])
        self.assertEqual([r['id'] for r in strict_requirements('How is the flow routed and verified?')],
                         ['question','verification-action','verification-observation'])

    def test_observation_prompt_judges_only_outcome_and_never_requests_route_again(self):
        prompt=coverage_task({'id':'verification-observation'})
        self.assertIn('ONLY the observable outcome',prompt)
        self.assertIn('Do NOT require the routing',prompt)
        self.assertIn('repeated output/samples',prompt)
        self.assertNotIn('verified=true',prompt) # No course-specific expected flag injected.
        action=coverage_task({'id':'verification-action'})
        self.assertIn('ONLY the concrete verification',action)
        self.assertIn('Do NOT select background routing',action)

    def test_real_v12_01_mechanism_contract_can_publish_without_competing_question_gate(self):
        report=json.loads((HERE/'reports/live/evaluate_v12_original.json').read_text())
        r=next(d for d in report['details'] if d['id']=='positive-01')['result']
        selection=[c for c in r['validation']['model_calls'] if c['stage']=='extractive_selector'][-1]['raw_response']
        mechanism=[c for c in r['validation']['model_calls'] if c.get('requirement_id')=='mechanism'][-1]['raw_response']
        class Replay:
            answer_model='contract replay of v12 selection/positive mechanism; NOT new v13 live';model='controlled-fixture';last_call_metadata={}
            def __init__(self):self.criteria=[]
            def embed(self,texts):return [[1.,0.] for _ in texts]
            def structured(self,prompt,schema):
                if 'quote_ids' in schema['properties']:return selection
                data,_=json.JSONDecoder().raw_decode(prompt.split('DATA:\n',1)[1]);self.criteria.append(data)
                return mechanism
        p=Replay();hits=[Hit(**h) for h in r['retrieval']['sources']]
        result=StrictRAGAgent(FixtureKB(hits),p).ask(r['question'])
        self.assertEqual(result.status,'answered');self.assertEqual(len(p.criteria),1)
        self.assertEqual(p.criteria[0]['coverage_requirement']['id'],'mechanism')
        self.assertIn('ALL parts',p.criteria[0]['coverage_requirement']['need'])
        self.assertEqual(p.criteria[0]['question_context'],r['question'])
        self.assertNotIn('question',p.criteria[0])
        self.assertTrue(all(c['text']==c['citations'][0]['quote'] for c in result.claims))

    def test_real_v12_09_outcome_remains_available_after_actual_action_selection(self):
        report=json.loads((HERE/'reports/live/evaluate_v12_original.json').read_text())
        r=next(d for d in report['details'] if d['id']=='positive-09')['result']
        selection=[c for c in r['validation']['model_calls'] if c['stage']=='extractive_selector'][-1]['raw_response']
        verdicts={c['id']:c for c in r['validation']['coverage_verdict']['checks']}
        class ScriptedOutcome:
            answer_model='authored outcome on saved v12 context, NOT new LLM quality';model='controlled-fixture';last_call_metadata={}
            def embed(self,texts):return [[1.,0.] for _ in texts]
            def structured(self,prompt,schema):
                if 'quote_ids' in schema['properties']:return selection
                data,_=json.JSONDecoder().raw_decode(prompt.split('DATA:\n',1)[1]);ident=data['coverage_requirement']['id']
                if ident=='verification-observation':
                    self.observation_prompt=prompt
                    proof=next(p for p in data['proof_units'] if 'only reports success after `verified=true`' in p['text'])
                    return json.dumps({'reason':'AUTHOR-SCRIPTED valid outcome, not LLM quality','covered':True,'proof_ids':[proof['id']]})
                row=verdicts[ident]
                return json.dumps({k:row[k] for k in ['reason','covered','proof_ids']})
        p=ScriptedOutcome();hits=[Hit(**h) for h in r['retrieval']['sources']]
        result=StrictRAGAgent(FixtureKB(hits),p).ask(r['question'])
        self.assertEqual(result.status,'answered')
        self.assertIn('Do NOT require the routing',p.observation_prompt)
        check=result.validation['coverage_verdict']['checks'][-1]
        self.assertTrue(check['covered']);self.assertIn('verified=true',check['answer_excerpt'])
        self.assertTrue(all(c['text']==c['citations'][0]['quote'] for c in result.claims))

    def test_missing_mechanism_still_refuses_without_a_competing_question_gate(self):
        result,p=StrictExtractionTests.run_strict(self,
            {'coverage_auditor':[{'reason':'Restore part lacks evidence','covered':False,'proof_ids':[]}]},
            question='How are dialogues isolated and restored?')
        self.assertEqual(result.status,'unknown');self.assertFalse(result.sources or result.quotes)
        calls=[c for c in result.validation['model_calls'] if c['stage']=='coverage_auditor']
        self.assertEqual([c['requirement_id'] for c in calls],['mechanism','mechanism'])
        self.assertFalse(any(c.get('repair') for c in calls))



class DiagnosticPolicyV14Tests(unittest.TestCase):
    def provider(self, value=None, verdict=None):
        return ExtractiveFixtureProvider(value or draft(), verdict=verdict or {'answers_question':False})

    def test_negative_audit_remains_negative_while_exact_source_answer_is_reviewable(self):
        p=self.provider();r=StrictRAGAgent(FixtureKB([HIT]),p,coverage_policy='diagnostic').ask('Which process stores snapshots?')
        self.assertEqual(r.status,'answered');self.assertEqual(r.reason,'coverage_requires_review')
        self.assertFalse(r.validation['coverage_supported']);self.assertTrue(r.validation['manual_review_required'])
        self.assertFalse(r.validation['coverage_verdict']['checks'][0]['covered'])
        self.assertEqual(r.claims[0]['text'],r.quotes[0]['quote']);self.assertTrue(r.sources)
        class Agent:
            def ask(self,q):return r
        report=evaluate(Agent(),[{'id':'q','question':r.question,'answerable':True}])
        self.assertTrue(report['summary']['all_contract_checks_pass'])
        self.assertEqual(report['summary']['positive_coverage_pass'],0)
        self.assertEqual(report['summary']['positive_flagged_for_manual_review'],1)
        self.assertFalse(report['summary']['assignment_complete'])
        self.assertIsNone(report['details'][0]['manual_review']['fully_answers_question'])
        self.assertFalse(report['details'][0]['checks']['contract_includes_model_coverage'])

    def test_strict_remains_default_and_same_negative_verdict_blocks_publication(self):
        r=StrictRAGAgent(FixtureKB([HIT]),self.provider()).ask('Which process stores snapshots?')
        self.assertEqual(r.status,'unknown');self.assertFalse(r.sources or r.quotes)
        self.assertEqual(r.validation['coverage_policy'],'strict')
        with self.assertRaises(ValueError):StrictRAGAgent(FixtureKB([HIT]),self.provider(),coverage_policy='invented')

    def test_below_threshold_and_above_threshold_selector_unknown_still_refuse(self):
        weak=Hit('chunk-a','README.md','Jobs',QUOTE,.49,1,1);p=self.provider()
        r=StrictRAGAgent(FixtureKB([weak]),p,coverage_policy='diagnostic').ask('Which process stores snapshots?')
        self.assertEqual(r.reason,'below_threshold');self.assertEqual(p.calls,[])
        self.assertTrue(r.clarification);self.assertFalse(r.sources or r.quotes)
        p=ExtractiveFixtureProvider({'status':'unknown','claims':[]})
        r=StrictRAGAgent(FixtureKB([HIT]),p,coverage_policy='diagnostic').ask('What is the revenue?')
        self.assertEqual(r.reason,'insufficient_context');self.assertFalse(r.sources or r.quotes)

    def test_diagnostic_does_not_bypass_quote_identity_or_accept_freeform_answer(self):
        for bad in ({'status':'answered','quote_ids':['invented']},
                    {'status':'answered','quote_ids':['q1_1'],'answer':'Invented fact'},
                    {'status':'answered','claims':[{'text':'Invented'}]}):
            class Bad(ExtractiveFixtureProvider):
                def structured(self,prompt,schema):return json.dumps(bad)
            r=StrictRAGAgent(FixtureKB([HIT]),Bad(draft()),coverage_policy='diagnostic').ask('Which process stores snapshots?')
            self.assertEqual(r.status,'unknown');self.assertFalse(r.sources or r.quotes)
            self.assertFalse(r.validation['verbatim_answer'])

    def test_failed_audit_is_logged_and_does_not_get_supported_true(self):
        class BadAudit(ExtractiveFixtureProvider):
            def structured(self,prompt,schema):
                if 'proof_ids' in schema['properties']:return json.dumps({'reason':'Invalid proof','covered':True,'proof_ids':['invented']})
                return super().structured(prompt,schema)
        r=StrictRAGAgent(FixtureKB([HIT]),BadAudit(draft()),coverage_policy='diagnostic').ask('Which process stores snapshots?')
        self.assertEqual(r.status,'answered');self.assertEqual(r.reason,'coverage_check_failed_review_required')
        self.assertFalse(r.validation['coverage_supported']);self.assertTrue(r.validation['manual_review_required'])
        self.assertTrue(r.validation['errors']);self.assertEqual(r.claims[0]['text'],r.quotes[0]['quote'])

    def test_technical_error_remains_error_in_diagnostic_mode(self):
        class Offline(ExtractiveFixtureProvider):
            def structured(self,prompt,schema):
                if 'proof_ids' in schema['properties']:raise RuntimeError('Ollama unavailable')
                return super().structured(prompt,schema)
        with self.assertRaisesRegex(RuntimeError,'unavailable'):
            StrictRAGAgent(FixtureKB([HIT]),Offline(draft()),coverage_policy='diagnostic').ask('Which process stores snapshots?')

    def test_cli_diagnostic_source_contract_is_not_called_assignment_completion(self):
        document=Document('worker.md','worker.md',QUOTE,'fixture');chunks=chunk_documents([document],'fixed')
        p=ExtractiveFixtureProvider(draft(chunk_id=chunks[0].chunk_id),{'answers_question':False})
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                result=({'embeddings':[[1.,0.] for _ in body['input']]} if self.path=='/api/embed' else
                        {'response':p.structured(body['prompt'],body['format']),'done':True,'done_reason':'stop'})
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(result).encode())
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);db=root/'knowledge.db';kb=KnowledgeBase(db)
                kb.save([document],'fixed',chunks,[[1.,0.]],'fixture-embedding',500,75,'fixture');kb.close()
                qs=root/'qs.json';qs.write_text(json.dumps([{'id':'q','question':'Which process stores snapshots?','answerable':True}]))
                output=root/'report.json'
                cmd=[sys.executable,str(HERE/'main.py'),'--db',str(db),'--url',f'http://127.0.0.1:{server.server_port}',
                     '--model','fixture-embedding','--coverage-policy','diagnostic','evaluate','--questions',str(qs),'--output',str(output)]
                run=subprocess.run(cmd,capture_output=True,text=True,timeout=20);self.assertEqual(run.returncode,0,run.stderr)
                report=json.loads(output.read_text());self.assertEqual(report['summary']['positive_coverage_pass'],0)
                self.assertEqual(report['summary']['diagnostic_positive_questions'],1)
                self.assertFalse(report['summary']['assignment_complete'])
                self.assertTrue(report['details'][0]['result']['validation']['manual_review_required'])
                self.assertTrue(output.with_suffix('.md').is_file())
        finally:server.shutdown();server.server_close();t.join()


class HTTPIntegrationTests(unittest.TestCase):
    def test_cli_uses_real_sqlite_http_four_stages_and_saves_report(self):
        records=[]
        document=Document('worker.md','worker.md',QUOTE,'fixture')
        chunks=chunk_documents([document],'fixed')
        provider=FixtureProvider(draft(chunk_id=chunks[0].chunk_id))
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                records.append((self.path,body))
                if self.path=='/api/embed':result={'embeddings':[[1.,0.] for _ in body['input']]}
                else:
                    raw=provider.structured(body['prompt'],body['format'])
                    result={'response':raw,'done':True,'done_reason':'stop','prompt_eval_count':345,'eval_count':55}
                data=json.dumps(result).encode();self.send_response(200)
                self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                directory=Path(tmp);db=directory/'knowledge.db';kb=KnowledgeBase(db)
                kb.save([document],'fixed',chunks,[[1.,0.]],'fixture-embedding',500,75,'fixture');kb.close()
                questions=directory/'questions.json';questions.write_text(json.dumps([{'id':'http-01','question':'Who stores snapshots?','answerable':True}]))
                output=directory/'evaluate.json'
                command=[sys.executable,str(HERE/'main.py'),'--db',str(db),'--url',f'http://127.0.0.1:{server.server_port}',
                         '--model','fixture-embedding','--answer-style','paraphrase','evaluate','--questions',str(questions),'--output',str(output)]
                run=subprocess.run(command,capture_output=True,text=True,timeout=20)
                self.assertEqual(run.returncode,0,run.stderr)
                payload=json.loads(output.read_text())
                self.assertTrue(payload['summary']['all_contract_checks_pass'])
                self.assertTrue(output.with_suffix('.md').is_file())
                self.assertIsNone(payload['details'][0]['manual_review']['answer_matches_quotes'])
                self.assertEqual([p for p,_ in records],['/api/embed']+['/api/generate']*4)
                self.assertTrue(all(body['model']=='qwen2.5:14b' for _,body in records[1:]))
                self.assertEqual(records[1][1]['options']['num_ctx'],16384)
                self.assertIn('OUTPUT JSON SCHEMA',records[1][1]['prompt'])
                self.assertEqual(payload['details'][0]['result']['validation']['model_calls'][0]['ollama']['prompt_eval_count'],345)
                provider.draft={'status':'unknown','claims':[]}
                run=subprocess.run(command,capture_output=True,text=True,timeout=20)
                self.assertEqual(run.returncode,1,run.stderr)
                self.assertFalse(json.loads(output.read_text())['summary']['all_contract_checks_pass'])
                self.assertEqual(len(records),7) # second run: embed + selector only
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_structured_provider_validates_options_and_incomplete_http_response(self):
        for opts in ({'num_ctx':100},{'num_predict':0},{'timeout':0}):
            with self.assertRaises(ValueError):StructuredOllama(**opts)
        class Incomplete(StructuredOllama):
            def _post(self,endpoint,body):return {'done':False,'response':'{}'}
        with self.assertRaises(RuntimeError):Incomplete().structured('Test',{})


if __name__=='__main__':
    unittest.main()
