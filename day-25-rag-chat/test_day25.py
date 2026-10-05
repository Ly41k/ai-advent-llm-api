"""Contract and failure tests; no live Ollama or external API is used."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from support25 import HERE, ROOT, KnowledgeBase, Settings, StructuredOllama, EvidenceError, StrictRAGAgent
from chat_store import ChatStore
from chat_agent import ChatAgent, render_response
from memory import empty_state, update, public_state
from conversation import plan, recent_context, previous_resolution, resolution_state, ContextProvider, proof_identifiers, proof_table_rows, proof_blocks, followup_lesson, goal_lesson, existing_memory_noop, quote_links, validate_fragment_links, table_audit_prompt, quote_table_rows, selection_refinement_prompt, filter_incomplete_tables, incomplete_markdown_table, filter_incomplete_fragments, incomplete_python_fragment
from main import memory_command
from io25 import validate_json_output, write_json
from conversation import literal_semicolon_clauses, proof_conditional_clauses, conditional_audit_prompt, sequence_selection_units, expand_sequence_selection, validate_conditional_action, route_audit_prompt
from requirements25 import coverage_requirements25
from offline_demo import fixture_index, http_fixture, ScriptedModel, run_demo
from evaluate25 import load_scenarios, check_sources


class ChangedModel(ScriptedModel):
    def __init__(self, stage, payload):
        super().__init__()
        self.stage, self.payload = stage, payload

    def respond(self, endpoint, body):
        result = super().respond(endpoint, body)
        if endpoint == "generate" and self.stage in body["format"]["properties"]:
            result["response"] = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return result


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.data = {"question": "Which route does --task info use on day 20?",
                     "requirements": [{"id": "question", "need": "All requested parts"}],
                     "chunks": [{"chunk_id": "actual", "source": "day-20-example/README.md",
                                 "section": "Routes", "course_lesson": 20, "quotes": [
                                     {"quote_id": "q1", "text": "Info calls only GitHub."},
                                     {"quote_id": "q2", "text": "Full report: fetch → save → verify."},
                                     {"quote_id": "q3", "text": "Unselected source passage."}]}]}
        self.schema = {"type": "object", "additionalProperties": False,
                       "required": ["status", "quote_ids"], "properties": {
                           "status": {"type": "string", "enum": ["answered", "unknown"]},
                           "quote_ids": {"type": "array", "maxItems": 6,
                                         "items": {"type": "string", "enum": ["q1", "q2", "q3"]}}}}
        self.prompt = "Select\nDATA:\n" + json.dumps(self.data)

    class Provider:
        def __init__(self, outputs, reasons=None):
            self.outputs, self.calls = list(outputs), []
            self.reasons = list(reasons or ["stop"] * len(outputs))
        def structured(self, prompt, schema):
            self.calls.append((prompt, schema))
            self.last_call_metadata = {"done_reason": self.reasons.pop(0), "eval_count": len(self.calls)}
            value = self.outputs.pop(0)
            return value if isinstance(value, str) else json.dumps(value)

    def initial(self):
        return {"status": "answered", "quote_ids": ["q2", "q1"]}

    def test_refinement_preserves_question_requirements_literals_provenance_and_initial_schema(self):
        original = copy.deepcopy((self.data, self.schema))
        prompt, schema = selection_refinement_prompt(self.prompt, self.schema, json.dumps(self.initial()))
        data = json.loads(prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual(self.data["question"], data["question"])
        self.assertEqual(self.data["requirements"], data["requirements"])
        self.assertEqual([{**self.data["chunks"][0], "quotes": self.data["chunks"][0]["quotes"][:2]}], data["chunks"])
        self.assertEqual(["q2", "q1"], schema["properties"]["quote_ids"]["items"]["enum"])
        self.assertEqual(2, schema["properties"]["quote_ids"]["maxItems"])
        self.assertEqual(original, (self.data, self.schema))

    def test_invalid_unknown_duplicate_single_or_unavailable_initial_selection_is_never_refined(self):
        for raw in ('bad JSON', 'null', '{}', '{"status":"answered","quote_ids":["q1"]}',
                    '{"status":"unknown","quote_ids":[]}',
                    '{"status":"answered","quote_ids":["q1","q1"]}',
                    '{"status":"answered","quote_ids":["q1","forged"]}',
                    '{"status":"answered","quote_ids":["q1",true]}',
                    '{"status":"answered","quote_ids":["q1","q2"],"extra":true}'):
            with self.subTest(raw=raw):
                provider = self.Provider([raw])
                wrapped = ContextProvider(provider, {})
                self.assertEqual(raw, wrapped.structured(self.prompt, self.schema))
                self.assertEqual(1, len(provider.calls))
                self.assertEqual([], wrapped.selection_refinements)
        self.data["chunks"][0]["quotes"].pop(1)
        self.assertIsNone(selection_refinement_prompt("\nDATA:\n" + json.dumps(self.data), self.schema, json.dumps(self.initial())))

    def test_complete_subset_is_returned_without_old_answers_or_memory_and_both_calls_are_traced(self):
        provider = self.Provider([self.initial(), {"status": "answered", "quote_ids": ["q1"]}])
        progress = []
        wrapped = ContextProvider(provider, {"task_state": {"goal": "OLD_GOAL"},
                                            "recent_history": [{"assistant": "OLD_ANSWER"}]}, progress.append)
        result = json.loads(wrapped.structured(self.prompt, self.schema))
        self.assertEqual(["q1"], result["quote_ids"])
        self.assertEqual(2, len(provider.calls))
        self.assertNotIn("OLD_GOAL", provider.calls[1][0])
        self.assertNotIn("OLD_ANSWER", provider.calls[1][0])
        trace = wrapped.selection_refinements[0]
        self.assertEqual(self.initial(), json.loads(trace["initial_raw_response"]))
        self.assertEqual(result, json.loads(trace["raw_response"]))
        self.assertEqual(1, trace["initial_ollama"]["eval_count"])
        self.assertEqual(2, trace["ollama"]["eval_count"])
        self.assertEqual(1, len(progress))

    def test_refiner_unknown_and_malformed_are_not_replaced_with_initial_answer(self):
        for output in ('{"status":"unknown","quote_ids":[]}', 'bad JSON'):
            provider = self.Provider([self.initial(), output])
            self.assertEqual(output, ContextProvider(provider, {}).structured(self.prompt, self.schema))

    def test_refiner_cannot_add_an_unselected_but_otherwise_valid_catalog_id(self):
        provider = self.Provider([self.initial(), {"status": "answered", "quote_ids": ["q3"]}])
        wrapped = ContextProvider(provider, {})
        with self.assertRaisesRegex(EvidenceError, "only initially selected"):
            wrapped.structured(self.prompt, self.schema)
        self.assertIn("only initially selected", wrapped.selection_refinements[0]["error"])

    def test_initial_token_limit_cannot_be_hidden_by_a_successful_refiner(self):
        provider = self.Provider([self.initial(), {"status": "answered", "quote_ids": ["q1"]}], ["length", "stop"])
        wrapped = ContextProvider(provider, {})
        with self.assertRaisesRegex(EvidenceError, "token limit"):
            wrapped.structured(self.prompt, self.schema)
        self.assertEqual(1, len(provider.calls))
        self.assertEqual("length", wrapped.selection_refinements[0]["initial_ollama"]["done_reason"])

    def test_refinement_still_rejects_an_orphaned_command_introduction(self):
        self.data["chunks"][0]["quotes"][:2] = [{"quote_id": "q1", "text": "Run:"},
                                                {"quote_id": "q2", "text": "```bash\npython worker.py\n```"}]
        self.prompt = "\nDATA:\n" + json.dumps(self.data)
        provider = self.Provider([{"status": "answered", "quote_ids": ["q1", "q2"]},
                                  {"status": "answered", "quote_ids": ["q1"]}])
        with self.assertRaisesRegex(EvidenceError, "FOLLOWING code"):
            ContextProvider(provider, {}).structured(self.prompt, self.schema)

    def test_partial_table_detection_preserves_complete_rows_empty_cells_and_escaped_pipes(self):
        for table in ("| Name | Role |\n|---|---|\n| worker | Runs |",
                      "| Name | Role |\n|---|---|\n| worker | Runs",
                      "| Name | Role |\n|---|---|\n| worker | |",
                      "| Name | Role |\n|---|---|\n| worker \\| helper | Runs |"):
            self.assertFalse(incomplete_markdown_table(table))
        self.assertTrue(incomplete_markdown_table("| Name | Role |\n|---|---|\n| worker | Runs |\n| Работает"))
        self.assertTrue(incomplete_markdown_table("| Name | Role |\n|---|---|\n| worker | Runs | extra |"))
        for text in (None, "ordinary text", "| Just one source line |", "```text\n| code |\n```"):
            self.assertFalse(incomplete_markdown_table(text))

    def test_table_filter_excludes_whole_id_without_editing_other_evidence_or_requirements(self):
        self.data["chunks"][0]["quotes"][1]["text"] = "| Name | Role |\n|---|---|\n| worker | Runs |\n| Работает"
        original = copy.deepcopy((self.data, self.schema))
        prompt, schema, excluded = filter_incomplete_tables("Select\nDATA:\n" + json.dumps(self.data), self.schema)
        filtered = json.loads(prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual(["q2"], [r["quote_id"] for r in excluded])
        self.assertEqual(["q1", "q3"], schema["properties"]["quote_ids"]["items"]["enum"])
        self.assertEqual([self.data["chunks"][0]["quotes"][0], self.data["chunks"][0]["quotes"][2]], filtered["chunks"][0]["quotes"])
        self.assertEqual(self.data["question"], filtered["question"])
        self.assertEqual(self.data["requirements"], filtered["requirements"])
        self.assertEqual(original, (self.data, self.schema))
        self.assertEqual(self.data["chunks"][0]["quotes"][1]["text"], excluded[0]["text"])

    def test_excluded_table_id_cannot_bypass_filter_and_complete_answer_is_not_changed(self):
        self.data["chunks"][0]["quotes"][1]["text"] = "| Name | Role |\n|---|---|\n| Работает"
        prompt = "\nDATA:\n" + json.dumps(self.data)
        provider = self.Provider([{"status": "answered", "quote_ids": ["q2"]}])
        wrapped = ContextProvider(provider, {})
        with self.assertRaisesRegex(EvidenceError, "Incomplete source table"):
            wrapped.structured(prompt, self.schema)
        self.assertNotIn('"quote_id": "q2"', provider.calls[0][0])
        self.assertEqual("q2", wrapped.fragment_filters[0]["excluded"][0]["quote_id"])
        provider = self.Provider([{"status": "answered", "quote_ids": ["q1"]}])
        wrapped = ContextProvider(provider, {})
        self.assertEqual(["q1"], json.loads(wrapped.structured(prompt, self.schema))["quote_ids"])
        self.assertEqual(1, len(provider.calls))

    def test_long_introduction_cannot_be_orphaned_by_initial_selector_or_refiner(self):
        intro = (ROOT / "day-20-mcp-orchestration/README.ru.md").read_text().splitlines()[10]
        self.assertGreater(len(intro), 300)
        self.assertTrue(intro.endswith(":"))
        self.data["chunks"][0]["quotes"][:2] = [{"quote_id": "q1", "text": intro},
                                                {"quote_id": "q2", "text": "```text\ngithub.fetch → analysis.summarize\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        links = quote_links(prompt, self.schema)
        self.assertEqual(1, len(links))
        self.assertEqual(intro, links[0]["intro_text"])
        for outputs in ([{"status": "answered", "quote_ids": ["q1"]}],
                        [{"status": "answered", "quote_ids": ["q1", "q2"]},
                         {"status": "answered", "quote_ids": ["q1"]}]):
            provider = self.Provider(outputs)
            with self.assertRaisesRegex(EvidenceError, "FOLLOWING code q2"):
                ContextProvider(provider, {}).structured(prompt, self.schema)

    def test_refiner_receives_all_literal_dependency_ids_and_can_keep_the_complete_pair(self):
        intro = "Actual source context. " * 20 + "Route follows:"
        self.data["chunks"][0]["quotes"][:2] = [{"quote_id": "q1", "text": intro},
                                                {"quote_id": "q2", "text": "```text\nfirst → second\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        pair = {"status": "answered", "quote_ids": ["q1", "q2"]}
        provider = self.Provider([pair, pair])
        wrapped = ContextProvider(provider, {})
        self.assertEqual(pair, json.loads(wrapped.structured(prompt, self.schema)))
        data = json.loads(provider.calls[1][0].rsplit("\nDATA:\n", 1)[1])
        self.assertEqual([{"intro_quote_id": "q1", "following_code_quote_id": "q2", "code_requires_intro": True}], data["fragment_links"])

    def test_refiner_can_remove_unrelated_orphan_without_adding_unselected_code(self):
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": "Registry registers servers and routes calls."},
            {"quote_id": "q2", "text": "For a separate installation run:"},
            {"quote_id": "q3", "text": "```bash\npython install.py\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        initial = {"status": "answered", "quote_ids": ["q1", "q2"]}
        final = {"status": "answered", "quote_ids": ["q1"]}
        provider = self.Provider([initial, final])
        wrapped = ContextProvider(provider, {})
        self.assertEqual(final, json.loads(wrapped.structured(prompt, self.schema)))
        self.assertEqual(2, len(provider.calls))
        trace = wrapped.selection_refinements[0]
        self.assertIn("FOLLOWING code q3", trace["initial_fragment_errors"][0])
        refined_prompt, refined_schema = provider.calls[1]
        data = json.loads(refined_prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual([{"intro_quote_id": "q2", "following_code_quote_id": "q3"}], data["fragment_links"])
        self.assertEqual(["q1", "q2"], refined_schema["properties"]["quote_ids"]["items"]["enum"])
        self.assertEqual(["q1", "q2"], [q["quote_id"] for q in data["chunks"][0]["quotes"]])
        self.assertEqual(self.data["question"], data["question"])
        self.assertEqual(self.data["requirements"], data["requirements"])

    def test_refiner_cannot_keep_orphan_or_add_its_initially_unselected_partner(self):
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": "Registry routes calls."},
            {"quote_id": "q2", "text": "Install:"},
            {"quote_id": "q3", "text": "```bash\npython install.py\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        initial = {"status": "answered", "quote_ids": ["q1", "q2"]}
        for ids, error in ((["q1", "q2"], "FOLLOWING code q3"),
                           (["q1", "q2", "q3"], "only initially selected")):
            with self.subTest(ids=ids):
                provider = self.Provider([initial, {"status": "answered", "quote_ids": ids}])
                wrapped = ContextProvider(provider, {})
                with self.assertRaisesRegex(EvidenceError, error):
                    wrapped.structured(prompt, self.schema)
                self.assertIn(error, wrapped.selection_refinements[0]["error"])

    def test_refinement_does_not_invent_adjacency_after_filtering_selected_quotes(self):
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": "This prose ends in a colon:"},
            {"quote_id": "q2", "text": "An intervening paragraph, not a command."},
            {"quote_id": "q3", "text": "```bash\npython unrelated.py\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        refined_prompt, _ = selection_refinement_prompt(
            prompt, self.schema, json.dumps({"status": "answered", "quote_ids": ["q1", "q3"]}))
        data = json.loads(refined_prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual([], data["fragment_links"])

    def test_live_verify_orphan_has_only_complete_subsets_in_generation_schema(self):
        lines = (ROOT / "day-20-mcp-orchestration/README.ru.md").read_text().splitlines()
        self.data["question"] = "Что делает агент дня 20 при преждевременном выборе VERIFY?"
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": lines[10]},
            {"quote_id": "q2", "text": '\n'.join(lines[12:16])},
            {"quote_id": "q3", "text": lines[17]}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        refined_prompt, schema = selection_refinement_prompt(prompt, self.schema, json.dumps({"status": "answered", "quote_ids": ["q1", "q3"]}))
        self.assertEqual([[], ["q3"]], schema["properties"]["quote_ids"]["enum"])
        data = json.loads(refined_prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual(self.data["question"], data["question"])
        self.assertEqual(lines[17], data["chunks"][0]["quotes"][1]["text"])
        self.assertNotIn("q2", schema["properties"]["quote_ids"]["items"]["enum"])

    def test_live_summary_cannot_select_unlabelled_full_report_sequence(self):
        lines = (ROOT / "day-20-mcp-orchestration/README.ru.md").read_text().splitlines()
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": lines[10]},
            {"quote_id": "q2", "text": '\n'.join(lines[12:16])},
            {"quote_id": "q3", "text": lines[19]}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        initial = {"status": "answered", "quote_ids": ["q2", "q3"]}
        _, schema = selection_refinement_prompt(prompt, self.schema, json.dumps(initial))
        self.assertEqual([[], ["q3"]], schema["properties"]["quote_ids"]["enum"])
        provider = self.Provider([initial, {"status": "answered", "quote_ids": ["q3", "q2"]}])
        with self.assertRaisesRegex(EvidenceError, "requires its original introduction"):
            ContextProvider(provider, {}).structured(prompt, self.schema)

    def test_complete_captioned_sequence_remains_selectable_and_bash_needs_no_reverse_caption(self):
        self.data["chunks"][0]["quotes"][:2] = [
            {"quote_id": "q1", "text": "Report follows:"},
            {"quote_id": "q2", "text": "```text\nfetch → save → verify\n```"}]
        initial = {"status": "answered", "quote_ids": ["q1", "q2"]}
        _, schema = selection_refinement_prompt("\nDATA:\n" + json.dumps(self.data), self.schema, json.dumps(initial))
        self.assertEqual([[], ["q1", "q2"]], schema["properties"]["quote_ids"]["enum"])
        self.data["chunks"][0]["quotes"][1]["text"] = "```bash\npython worker.py\n```"
        _, schema = selection_refinement_prompt("\nDATA:\n" + json.dumps(self.data), self.schema, json.dumps(initial))
        self.assertIn(["q2"], schema["properties"]["quote_ids"]["enum"])

    def test_structural_enum_does_not_silently_reorder_schema_bypassing_provider(self):
        initial = {"status": "answered", "quote_ids": ["q2", "q1"]}
        provider = self.Provider([initial, initial])
        with self.assertRaisesRegex(EvidenceError, "source order"):
            ContextProvider(provider, {}).structured(self.prompt, self.schema)
        self.assertEqual([[], ["q1"], ["q2"], ["q1", "q2"]], provider.calls[1][1]["properties"]["quote_ids"]["enum"])

    def test_overlap_clipped_table_header_is_excluded_as_whole_id(self):
        lines = (ROOT / "day-18-scheduled-mcp/README.ru.md").read_text().splitlines()
        broken = "| Реализация | Проверка |\n" + '\n'.join(lines[61:67])
        self.assertTrue(incomplete_markdown_table(broken))
        self.data["chunks"][0]["quotes"][1]["text"] = broken
        prompt, schema, excluded = filter_incomplete_tables("\nDATA:\n" + json.dumps(self.data), self.schema)
        self.assertEqual(broken, excluded[0]["text"])
        self.assertNotIn("q2", schema["properties"]["quote_ids"]["items"]["enum"])
        self.assertNotIn(broken, prompt)
        self.assertFalse(incomplete_markdown_table("| A | B |\n|---|---|\n| 1 | 2 |"))

    def test_invalid_draft_fragment_cannot_hide_initial_token_exhaustion(self):
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": "Registry routes calls."},
            {"quote_id": "q2", "text": "Install:"},
            {"quote_id": "q3", "text": "```bash\npython install.py\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        provider = self.Provider([{"status": "answered", "quote_ids": ["q1", "q2"]}], ["length"])
        wrapped = ContextProvider(provider, {})
        with self.assertRaisesRegex(EvidenceError, "token limit"):
            wrapped.structured(prompt, self.schema)
        self.assertEqual(1, len(provider.calls))

    def test_navigation_budget_does_not_disable_validation_of_later_dependencies(self):
        quotes = [q for i in range(24) for q in ({"quote_id": f"intro{i}", "text": "Source context. " * 70 + "Run:"},
                                                {"quote_id": f"code{i}", "text": "```text\nfirst → second\n```"})]
        self.data["chunks"][0]["quotes"] = quotes
        self.schema["properties"]["quote_ids"]["items"]["enum"] = [q["quote_id"] for q in quotes]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        self.assertLess(len(quote_links(prompt, self.schema)), 24)
        links = quote_links(prompt, self.schema, navigation=False)
        self.assertEqual(24, len(links))
        self.assertEqual({"intro_quote_id": "intro23", "following_code_quote_id": "code23", "code_requires_intro": True}, links[-1])
        provider = self.Provider([{"status": "answered", "quote_ids": ["intro23"]}])
        with self.assertRaisesRegex(EvidenceError, "FOLLOWING code code23"):
            ContextProvider(provider, {}).structured(prompt, self.schema)

    def test_table_filter_leaves_complete_catalog_and_malformed_data_untouched(self):
        self.assertEqual((self.prompt, self.schema, []), filter_incomplete_tables(self.prompt, self.schema))
        for prompt in ('bad data', '\nDATA:\nnull', '\nDATA:\n{"chunks":[null]}'):
            self.assertEqual((prompt, self.schema, []), filter_incomplete_tables(prompt, self.schema))

    def test_process_refinement_guidance_keeps_original_full_requirements_and_does_not_force_ids(self):
        self.data["question"] = "Which process performs background work? Give its absolute path."
        self.data["requirements"] = [{"id": "question", "need": "Identify process AND absolute path"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        provider = self.Provider([self.initial(), {"status": "unknown", "quote_ids": []}])
        wrapped = ContextProvider(provider, {})
        self.assertEqual("unknown", json.loads(wrapped.structured(prompt, self.schema))["status"])
        compact = provider.calls[1][0]
        data = json.loads(compact.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual(self.data["question"], data["question"])
        self.assertEqual(self.data["requirements"], data["requirements"])
        self.assertIn("короткую команду", compact)
        self.assertIn("таблицы пунктов задания и тестов", compact)
        self.assertIn("Все явно запрошенные детали остаются обязательными", compact)

    def test_python_lexical_filter_detects_unfinished_strings_brackets_and_real_docstring(self):
        actual = "\n".join((ROOT / "day-18-scheduled-mcp/server.py").read_text().splitlines()[9:12])
        self.assertTrue(incomplete_python_fragment(actual, "day-18-scheduled-mcp/server.py"))
        for text in ('value = "unfinished', "value = 'unfinished", 'value = (1,',
                     'items = [1,', 'data = {"a": 1,', 'call(\n    alias,',
                     '"""unfinished documentation', "'''unfinished documentation"):
            with self.subTest(text=text):
                self.assertTrue(incomplete_python_fragment(text, "module.py"))
        self.assertTrue(incomplete_python_fragment('```python\n"""unfinished\n```', "README.md"))
        self.assertTrue(incomplete_python_fragment('```py\nvalue = 1', "README.md"))

    def test_python_lexical_filter_preserves_complete_excerpts_prose_and_other_languages(self):
        for text in ('value = "complete"', "value = 'complete'", 'values = (1, 2)',
                     '"""Closed documentation."""', '    return result',
                     'def method():\n    """A complete function docstring."""',
                     'def method():', '# "quote inside comment',
                     'value = """closing a literal here\nnext line\n"""'):
            with self.subTest(text=text):
                self.assertFalse(incomplete_python_fragment(text, "module.py"))
        for text in ('The literal "first snapshot is due immediately" is documentation.',
                     '```bash\nprintf "unfinished\n```', '```text\n[unfinished\n```', None):
            self.assertFalse(incomplete_python_fragment(text, "README.md"))
        self.assertFalse(incomplete_python_fragment('~~~python\nvalue = "complete"\n~~~', "README.md"))

    def test_indentation_error_cannot_hide_real_dangling_docstring_tail(self):
        actual='\n'.join((ROOT/'day-18-scheduled-mcp/server.py').read_text().splitlines()[25:31]).strip()
        self.assertTrue(actual.startswith('Args:'))
        self.assertTrue(incomplete_python_fragment(actual,'day-18-scheduled-mcp/server.py'))
        self.assertTrue(incomplete_python_fragment('```python\n'+actual+'\n```','README.md'))

    def test_indent_recovery_is_lexical_and_preserves_closed_strings_and_comments(self):
        for text in ('Args:\n        owner: Repository owner.\n    return result',
                     'if valid:\n        value = """closed"""\n    return value',
                     'if valid:\n        value = \'"""\'\n    # """ only a comment\n    return value'):
            with self.subTest(text=text):
                self.assertFalse(incomplete_python_fragment(text,'module.py'))

    def test_python_filter_removes_whole_ids_without_mutating_literals_requirements_or_schema(self):
        self.data["chunks"][0]["source"] = "module.py"
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": '"""first snapshot is due immediately'},
            {"quote_id": "q2", "text": 'value = "complete"'},
            {"quote_id": "q3", "text": 'schedule(owner, repo)'}]
        original = copy.deepcopy((self.data, self.schema))
        prompt = "\nDATA:\n" + json.dumps(self.data)
        filtered_prompt, schema, excluded = filter_incomplete_fragments(prompt, self.schema)
        data = json.loads(filtered_prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual(["q2", "q3"], schema["properties"]["quote_ids"]["items"]["enum"])
        self.assertEqual(self.data["chunks"][0]["quotes"][1:], data["chunks"][0]["quotes"])
        self.assertEqual(self.data["question"], data["question"])
        self.assertEqual(self.data["requirements"], data["requirements"])
        self.assertEqual(original, (self.data, self.schema))
        self.assertEqual("python_unclosed_string_or_delimiter", excluded[0]["reason"])
        self.assertEqual(self.data["chunks"][0]["quotes"][0]["text"], excluded[0]["text"])
        provider = self.Provider([{"status": "answered", "quote_ids": ["q1"]}])
        with self.assertRaisesRegex(EvidenceError, "Incomplete source Python"):
            ContextProvider(provider, {}).structured(prompt, self.schema)
        self.assertNotIn('"quote_id": "q1"', provider.calls[0][0])

    def test_filter_preserves_original_dependency_when_its_code_is_removed(self):
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": "Read this Python excerpt:"},
            {"quote_id": "q2", "text": '```python\nvalue = """unfinished\n```'},
            {"quote_id": "q3", "text": "```text\nUnrelated complete text\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        provider = self.Provider([{"status": "answered", "quote_ids": ["q1", "q3"]},
                                  {"status": "answered", "quote_ids": ["q1", "q3"]}])
        wrapped = ContextProvider(provider, {})
        with self.assertRaisesRegex(EvidenceError, "FOLLOWING code q2"):
            wrapped.structured(prompt, self.schema)
        refined_prompt, _ = provider.calls[1]
        data = json.loads(refined_prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual([{"intro_quote_id": "q1", "following_code_quote_id": "q2"}], data["fragment_links"])
        self.assertNotIn("unfinished", refined_prompt)
        self.assertNotIn("unfinished", provider.calls[0][0])

    def test_filtering_between_prose_and_code_does_not_invent_a_dependency(self):
        self.data["chunks"][0]["quotes"] = [
            {"quote_id": "q1", "text": "Read this prose:"},
            {"quote_id": "q2", "text": "| A | B |\n|---|---|\n| Cut"},
            {"quote_id": "q3", "text": "```text\nUnrelated complete text\n```"}]
        prompt = "\nDATA:\n" + json.dumps(self.data)
        selected = {"status": "answered", "quote_ids": ["q1", "q3"]}
        provider = self.Provider([selected, selected])
        self.assertEqual(selected, json.loads(ContextProvider(provider, {}).structured(prompt, self.schema)))
        refined_prompt, _ = provider.calls[1]
        data = json.loads(refined_prompt.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual([], data["fragment_links"])


class RequirementIntentTests(unittest.TestCase):
    def test_operation_name_is_not_a_verification_request_and_all_parts_remain_required(self):
        messages = [
            'Как агент исправляет преждевременный VERIFY: выбирает шаг и отмечает исправление?',
            'Как обрабатывается операция VERIFY?',
            'How is a premature VERIFY corrected?',
            'How is a Premature VERIFY corrected?',
            'How does the VERIFY operation work?',
            'How does `VERIFY` work?',
            'Как выполняется команда ``CHECK``?']
        for message in messages:
            with self.subTest(message=message):
                rows=coverage_requirements25(message)
                self.assertEqual(['mechanism'],[r['id'] for r in rows])
                self.assertIn('ALL parts',rows[0]['need'])

    def test_actual_verification_requests_keep_independent_action_and_observation(self):
        for message in ('Как проверить исправление преждевременного VERIFY?',
                        'How to test correction of premature VERIFY?',
                        'How do I VERIFY the saved result?',
                        'Как проверить периодические результаты worker?',
                        'How to check `VERIFY` output?'):
            with self.subTest(message=message):
                self.assertEqual(['question','verification-action','verification-observation'],
                                 [r['id'] for r in coverage_requirements25(message)])

    def test_operation_topic_does_not_change_day24_defaults_or_nonhow_questions(self):
        from support25 import strict_requirements
        for message in ('Какие серверы участвуют?', 'Когда отчёт завершён?',
                        'Как выполнить полный маршрут?', 'How often does it run?',
                        'How do I verify a report?'):
            self.assertEqual(strict_requirements(message),coverage_requirements25(message))


class ConditionalAuditTests(unittest.TestCase):
    def setUp(self):
        self.text = ('При HTTP 400 `tool_use_failed` агент выбирает следующий шаг по проверенному порядку '
                     'и пишет `selected by agent fallback`; при преждевременном выборе модели '
                     'пишет `selected by agent correction`.')
        self.data = {'question_context': 'Как исправляется преждевременная операция: действие и метка?',
                     'coverage_requirement': {'id': 'question', 'need': 'All requested parts'},
                     'lesson_scope': ['20'], 'proof_units': [
                         {'id': 'p1', 'text': self.text, 'quote_id': 'q1', 'chunk_id': 'real', 'command_only': False},
                         {'id': 'p2', 'text': 'If a suggestion is premature, choose the next admissible operation.',
                          'quote_id': 'q2', 'chunk_id': 'real', 'command_only': False}]}
        self.schema = {'properties': {'proof_ids': {'items': {'enum': ['p1', 'p2']}}}}
        self.prompt = '\nDATA:\n' + json.dumps(self.data)

    def test_real_compound_source_clause_offsets_do_not_transfer_action(self):
        self.assertIn(self.text, (ROOT / 'day-20-mcp-orchestration/README.ru.md').read_text())
        rows = proof_conditional_clauses(self.prompt, self.schema)
        self.assertEqual(1, len(rows))
        clauses = rows[0]['clauses']
        self.assertEqual(2, len(clauses))
        self.assertIn('выбирает следующий шаг', clauses[0]['text'])
        self.assertNotIn('выбирает', clauses[1]['text'])
        self.assertIn('agent correction', clauses[1]['text'])
        for clause in clauses:
            self.assertEqual(clause['text'], self.text[clause['start']:clause['end']])

    def test_clause_split_preserves_inline_code_semicolons_and_source_bytes(self):
        text = '  If A, print `a;b`; when B, print ``c;d``.  '
        clauses = literal_semicolon_clauses(text)
        self.assertEqual(['If A, print `a;b`', 'when B, print ``c;d``.'], [c['text'] for c in clauses])
        for c in clauses: self.assertEqual(c['text'], text[c['start']:c['end']])
        self.assertEqual(['If A, print `a;b`.'], [c['text'] for c in literal_semicolon_clauses('If A, print `a;b`.')])

    def test_conditional_audit_keeps_all_original_proofs_scope_and_schema(self):
        before = copy.deepcopy((self.data, self.schema))
        index = proof_conditional_clauses(self.prompt, self.schema)
        prompt = conditional_audit_prompt(self.prompt, index)
        self.assertEqual(self.data, json.loads(prompt.rsplit('\nDATA:\n',1)[1]))
        self.assertIn(self.data['proof_units'][1]['text'], prompt)
        self.assertEqual(before, (self.data, self.schema))
        self.assertNotIn('covered', json.dumps(index))

    def test_compact_day24_data_does_not_invent_missing_quote_id(self):
        data=copy.deepcopy(self.data)
        data['proof_units']=[{'id':p['id'],'text':p['text'],'chunk_id':p['chunk_id']} for p in data['proof_units']]
        index=proof_conditional_clauses('\nDATA:\n'+json.dumps(data),self.schema)
        self.assertEqual('real',index[0]['chunk_id'])
        self.assertEqual('p1',index[0]['proof_id'])
        self.assertNotIn('quote_id',index[0])

    def test_index_ignores_unallowed_proofs_commands_tables_and_single_conditions(self):
        self.schema['properties']['proof_ids']['items']['enum'] = ['p2']
        self.assertEqual([], proof_conditional_clauses(self.prompt, self.schema))
        for field,value in [('command_only', True), ('text', '```python\nif a: b(); c()\n```'),
                            ('text','| if A | act; when B | label |'), ('text','If A, choose B; report done.')]:
            data = copy.deepcopy(self.data);data['proof_units'][0][field] = value
            self.assertEqual([], proof_conditional_clauses('\nDATA:\n'+json.dumps(data), {'properties':{'proof_ids':{'items':{'enum':['p1']}}}}))
        self.assertEqual([], proof_conditional_clauses('\nDATA:\nnull', self.schema))

    def test_single_negative_verdict_is_retained_without_history_or_approval_retry(self):
        negative = {'covered': False, 'proof_ids': [], 'reason': 'Marker alone does not prove the corrective action'}
        provider = RefinementTests.Provider([negative])
        wrapped = ContextProvider(provider, {'task_state': {'goal': 'PRIVATE_GOAL'},
                                             'recent_history': [{'assistant':'UNSELECTED_ANSWER'}]})
        self.assertEqual(negative, json.loads(wrapped.structured(self.prompt,self.schema)))
        self.assertEqual(1,len(provider.calls))
        prompt,schema=provider.calls[0]
        self.assertTrue(prompt.startswith('CONDITIONAL EVIDENCE AUDIT'))
        self.assertNotIn('PRIVATE_GOAL',prompt);self.assertNotIn('UNSELECTED_ANSWER',prompt)
        self.assertEqual(self.schema,schema)
        self.assertEqual(negative,json.loads(wrapped.conditional_audits[0]['raw_response']))

    def test_positive_mixed_branch_cannot_prove_requested_corrective_action(self):
        self.data['question_context']='Как агент дня 20 исправляет преждевременный VERIFY: как выбирает допустимый следующий шаг и как отмечает исправление в выводе?'
        raw=json.dumps({'covered':True,'proof_ids':['p1'],'reason':'Wrong cross-branch transfer'})
        with self.assertRaisesRegex(EvidenceError,'mixed-condition'):
            validate_conditional_action(raw,self.data)
        self.data['question_context']='Что делает агент при преждевременном выборе VERIFY?'
        with self.assertRaises(EvidenceError): validate_conditional_action(raw,self.data)
        self.data['question_context']='How does the agent correct a premature step?'
        with self.assertRaises(EvidenceError): validate_conditional_action(raw,self.data)

    def test_direct_condition_action_allows_original_positive_verdict_without_approving_it(self):
        self.data['question_context']='Как выбирает следующий шаг при преждевременном VERIFY?'
        raw=json.dumps({'covered':True,'proof_ids':['p1','p2'],'reason':'Direct action and label'})
        self.assertIsNone(validate_conditional_action(raw,self.data))
        # Available but unselected action does NOT establish an audit premise.
        with self.assertRaises(EvidenceError):
            validate_conditional_action(json.dumps({'covered':True,'proof_ids':['p1']}),self.data)

    def test_branch_guard_preserves_negative_verdict_and_marker_only_intent(self):
        self.data['question_context']='Как выбирает следующий шаг при преждевременном VERIFY?'
        self.assertIsNone(validate_conditional_action(json.dumps({'covered':False,'proof_ids':[]}),self.data))
        self.assertIsNone(validate_conditional_action('bad json',self.data))
        self.data['question_context']='Как отмечает преждевременный VERIFY в выводе?'
        self.assertIsNone(validate_conditional_action(json.dumps({'covered':True,'proof_ids':['p1']}),self.data))


class RouteAuditTests(unittest.TestCase):
    def setUp(self):
        self.data={'question_context':'Какой маршрут выбирается для --task summary на день 20?',
                   'coverage_requirement':{'id':'question','need':'All explicitly requested parts'},
                   'lesson_scope':[{'source':'day-20-mcp-orchestration/README.ru.md','chunk_id':'actual'}],
                   'proof_units':[{'id':'p1','text':(ROOT/'day-20-mcp-orchestration/README.ru.md').read_text().splitlines()[19],'chunk_id':'actual'},
                                  {'id':'p2','text':'Unrelated source sentence.','chunk_id':'actual'}]}
        self.schema={'properties':{'proof_ids':{'items':{'enum':['p1','p2']}}}}
        self.prompt='\nDATA:\n'+json.dumps(self.data)

    def test_route_prompt_preserves_full_original_data_and_literal_task_proof_offsets(self):
        before=copy.deepcopy((self.data,self.schema))
        prompt=route_audit_prompt(self.prompt,self.schema)
        self.assertTrue(prompt.startswith('TASK ROUTE EVIDENCE AUDIT'))
        self.assertEqual(self.data,json.loads(prompt.rsplit('\nDATA:\n',1)[1]))
        index=json.loads(prompt.split('LITERAL TASK FLAG INDEX:\n',1)[1].split('\n\nDATA:\n',1)[0])
        row=index[0];self.assertEqual('p1',row['proof_id'])
        self.assertEqual(row['literal'],self.data['proof_units'][0]['text'][row['start']:row['start']+len(row['literal'])])
        self.assertEqual(before,(self.data,self.schema))

    def test_route_audit_retains_one_negative_verdict_without_private_history(self):
        negative={'covered':False,'proof_ids':[],'reason':'Requested exact functions absent'}
        provider=RefinementTests.Provider([negative])
        wrapper=ContextProvider(provider,{'task_state':{'goal':'PRIVATE_GOAL'},'recent_history':[{'assistant':'OLD_ANSWER'}]})
        self.assertEqual(negative,json.loads(wrapper.structured(self.prompt,self.schema)))
        self.assertEqual(1,len(provider.calls));self.assertEqual(self.schema,provider.calls[0][1])
        self.assertNotIn('PRIVATE_GOAL',provider.calls[0][0]);self.assertNotIn('OLD_ANSWER',provider.calls[0][0])
        self.assertEqual(negative,json.loads(wrapper.route_audits[0]['raw_response']))

    def test_exact_names_order_and_all_question_parts_remain_required(self):
        self.data['question_context']='Какие точные функции и в каком порядке вызываются для --task summary на день 20?'
        prompt=route_audit_prompt('\nDATA:\n'+json.dumps(self.data),self.schema)
        self.assertIn('одного набора серверов недостаточно',prompt)
        self.assertEqual(self.data,json.loads(prompt.rsplit('\nDATA:\n',1)[1]))

    def test_navigation_ignores_unallowed_prefix_collision_and_multiple_tasks(self):
        for question in ('Which route for --task sum?', 'Which route for --task summary-extra?',
                         'Compare --task summary and --task info routes.'):
            self.data['question_context']=question
            self.assertIsNone(route_audit_prompt('\nDATA:\n'+json.dumps(self.data),self.schema))
        self.data['question_context']='Which route for --task summary?'
        self.schema['properties']['proof_ids']['items']['enum']=['p2']
        self.assertIsNone(route_audit_prompt('\nDATA:\n'+json.dumps(self.data),self.schema))

    def test_other_verification_gates_and_malformed_data_keep_existing_audit(self):
        self.data['coverage_requirement']['id']='verification-observation'
        self.assertIsNone(route_audit_prompt('\nDATA:\n'+json.dumps(self.data),self.schema))
        self.assertIsNone(route_audit_prompt('bad json',self.schema))


class SourceUnitTests(unittest.TestCase):
    def test_duplicate_json_keys_cannot_be_normalized_into_an_approved_selection(self):
        raw = '{"status":"unknown","status":"answered","quote_ids":["q1"]}'
        schema = {"properties": {"quote_ids": {"maxItems": 6, "items": {"enum": ["q1", "q2"]}}}}
        units = [{"member_ids": ["q1", "q2"]}]
        self.assertEqual(raw, expand_sequence_selection(raw, units, schema))
        from support25 import parse_json
        with self.assertRaises(EvidenceError):
            parse_json(expand_sequence_selection(raw, units, schema))

    def setUp(self):
        self.data={'question':'Which route?', 'requirements':[], 'chunks':[{'chunk_id':'real','source':'README.md','quotes':[
            {'quote_id':'q1','text':'The complete report follows this sequence:'},
            {'quote_id':'q2','text':'```text\nfetch → save → verify\n```'},
            {'quote_id':'q3','text':'A separately supported fact.'},
            {'quote_id':'q4','text':'Run the worker:'},
            {'quote_id':'q5','text':'```bash\npython worker.py\n```'}]}]}
        self.schema={'properties':{'quote_ids':{'maxItems':6,'items':{'enum':['q1','q2','q3','q4','q5']}}}}
        self.prompt='\nDATA:\n'+json.dumps(self.data)
        self.links=quote_links(self.prompt,self.schema,navigation=False)
        self.units=sequence_selection_units(self.prompt,self.schema,self.links)

    def test_source_units_are_original_same_chunk_caption_and_narrative_sequence_only(self):
        self.assertEqual(1,len(self.units))
        self.assertEqual(['q1','q2'],self.units[0]['member_ids'])
        self.assertEqual(self.data['chunks'][0]['quotes'][:2],self.units[0]['passages'])
        self.assertEqual('real',self.units[0]['chunk_id'])
        shortened=copy.deepcopy(self.schema);shortened['properties']['quote_ids']['items']['enum'].remove('q2')
        self.assertEqual([],sequence_selection_units(self.prompt,shortened,self.links))

    def test_either_declared_member_decodes_to_complete_original_source_order(self):
        for ids in (['q1','q3'],['q2','q3'],['q2','q1','q3']):
            raw=json.dumps({'status':'answered','quote_ids':ids})
            self.assertEqual(['q1','q2','q3'],json.loads(expand_sequence_selection(raw,self.units,self.schema))['quote_ids'])
        raw=json.dumps({'status':'answered','quote_ids':['q4']})
        self.assertEqual(raw,expand_sequence_selection(raw,self.units,self.schema))

    def test_invalid_duplicate_unknown_and_empty_selections_are_not_repaired(self):
        for value in ({'status':'unknown','quote_ids':['q1']}, {'status':'answered','quote_ids':['q1','q1']},
                      {'status':'answered','quote_ids':['invented']}, {'status':'answered','quote_ids':[]},
                      {'status':'answered','quote_ids':['q1'],'extra':True}):
            raw=json.dumps(value)
            self.assertEqual(raw,expand_sequence_selection(raw,self.units,self.schema))
        self.assertEqual('bad json',expand_sequence_selection('bad json',self.units,self.schema))

    def test_expanded_original_quote_limit_cannot_be_bypassed_by_a_unit(self):
        schema=copy.deepcopy(self.schema);schema['properties']['quote_ids']['maxItems']=1
        with self.assertRaisesRegex(EvidenceError,'quote limit'):
            expand_sequence_selection(json.dumps({'status':'answered','quote_ids':['q1']}),self.units,schema)

    def test_model_sees_literal_unit_before_choice_and_refiner_keeps_both_members(self):
        provider=RefinementTests.Provider([{'status':'answered','quote_ids':['q1','q3']},
                                           {'status':'answered','quote_ids':['q1','q2']}])
        wrapper=ContextProvider(provider,{},bundle_sequences=True)
        result=json.loads(wrapper.structured(self.prompt,self.schema))
        self.assertEqual(['q1','q2'],result['quote_ids'])
        self.assertTrue(provider.calls[0][0].startswith('SOURCE SELECTION UNITS'))
        self.assertIn(self.units[0]['passages'][0]['text'],provider.calls[0][0])
        self.assertEqual(['q1','q3'],json.loads(wrapper.source_unit_selections[0]['raw_response'])['quote_ids'])
        self.assertEqual(['q1','q2','q3'],json.loads(wrapper.source_unit_selections[0]['expanded_response'])['quote_ids'])
        options=wrapper.selection_refinements[0]['structurally_valid_selections']
        self.assertNotIn(['q1'],options);self.assertNotIn(['q2'],options)

    def test_unit_presentation_budget_leaves_undeclared_pairs_under_original_guard(self):
        data=copy.deepcopy(self.data);quotes=[]
        for i in range(30):
            quotes.extend([{'quote_id':f'q{i}a','text':'Literal caption '+'x'*1000+':'},
                           {'quote_id':f'q{i}b','text':'```text\nfetch → verify\n```'}])
        data['chunks'][0]['quotes']=quotes
        schema=copy.deepcopy(self.schema);schema['properties']['quote_ids']['items']['enum']=[q['quote_id'] for q in quotes]
        prompt='\nDATA:\n'+json.dumps(data)
        links=quote_links(prompt,schema,navigation=False)
        units=sequence_selection_units(prompt,schema,links)
        self.assertLessEqual(len(units),16)
        self.assertLessEqual(sum(len(json.dumps(u,ensure_ascii=False)) for u in units),8000)
        self.assertLess(len(units),len(links))
        raw=json.dumps({'status':'answered','quote_ids':['q29a']})
        self.assertEqual(raw,expand_sequence_selection(raw,units,schema))
        with self.assertRaises(EvidenceError):validate_fragment_links(raw,links)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "chats.db"
        self.store = ChatStore(self.path)
        self.session = self.store.create()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_restart_keeps_state_and_complete_history(self):
        state = memory_command(self.store, self.session, "/goal", "Prepare the demo")
        turn, current = self.store.begin(self.session, "Question")
        self.store.finish(self.session, turn, current["version"], state, {"answer": "Answer", "sources": []})
        self.store.close()
        self.store = ChatStore(self.path)
        self.assertEqual("Prepare the demo", public_state(self.store.get(self.session)["state"])["goal"])
        self.assertEqual("Answer", self.store.history(self.session)[0]["response"]["answer"])

    def test_second_process_cannot_interleave_same_session(self):
        turn, current = self.store.begin(self.session, "First")
        second = ChatStore(self.path)
        try:
            with self.assertRaisesRegex(ValueError, "pending"):
                second.begin(self.session, "Second")
            with self.assertRaisesRegex(ValueError, "pending"):
                memory_command(second, self.session, "/goal", "Replacement")
        finally:
            second.close()
        self.store.finish(self.session, turn, current["version"], current["state"], error="network")
        self.assertEqual(1, len(self.store.history(self.session)))

    def test_recovery_preserves_unanswered_user_message(self):
        turn, current = self.store.begin(self.session, "Interrupted question")
        self.store.close()
        self.store = ChatStore(self.path)
        self.assertEqual(1, self.store.recover(self.session))
        self.assertEqual("Interrupted question", self.store.history(self.session)[0]["question"])
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.store.finish(self.session, turn, current["version"], current["state"], {"answer": "late"})

    def test_recover_refuses_live_owner_then_succeeds_after_process_is_killed(self):
        code = ("from chat_store import ChatStore; import sys; "
                "s=ChatStore(sys.argv[1]); s.begin(sys.argv[2], 'Interrupted child'); "
                "print('reserved', flush=True); sys.stdin.read()")
        child = subprocess.Popen([sys.executable, "-c", code, str(self.path), self.session],
                                 cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual("reserved", child.stdout.readline().strip())
            with self.assertRaisesRegex(ValueError, "active"):
                self.store.recover(self.session)
            self.assertEqual("pending", self.store.history(self.session)[0]["status"])
            other = self.store.create()
            turn, current = self.store.begin(other, "Other session")
            self.store.finish(other, turn, current["version"], current["state"], error="test")
        finally:
            child.kill()
            child.communicate(timeout=10)
        self.assertEqual(1, self.store.recover(self.session))
        self.assertEqual(0, self.store.recover(self.session))
        self.assertEqual("error", self.store.history(self.session)[0]["status"])
        self.assertEqual("recovery", self.store.export(self.session)["events"][0]["kind"])

    def test_export_uses_one_snapshot_during_concurrent_memory_change(self):
        second = ChatStore(self.path)
        original = self.store.history
        try:
            def interleaved_history(*args, **kwargs):
                memory_command(second, self.session, "/goal", "New goal")
                return original(*args, **kwargs)
            with patch.object(self.store, "history", side_effect=interleaved_history):
                exported = self.store.export(self.session)
            self.assertIsNone(exported["session"]["state"]["goal"])
            self.assertEqual([], exported["events"])
            latest = self.store.export(self.session)
            self.assertEqual("New goal", latest["session"]["state"]["goal"]["value"])
            self.assertEqual(1, len(latest["events"]))
        finally:
            second.close()

    def test_failed_retries_do_not_consume_completed_history_limit(self):
        for question, error in [("Last accepted topic", None)] + [("Retry", "network")] * 6:
            turn, current = self.store.begin(self.session, question)
            self.store.finish(self.session, turn, current["version"], current["state"],
                              {"answer": "Answer"} if error is None else None, error=error)
        turn, _ = self.store.begin(self.session, "Followup")
        self.assertEqual(["Last accepted topic"], [r["question"] for r in self.store.history(self.session, 4, completed_only=True)])
        self.assertEqual(8, len(self.store.history(self.session)))

    def test_version_conflict_rolls_back_answer(self):
        turn, current = self.store.begin(self.session, "Question")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.store.finish(self.session, turn, current["version"] + 1, current["state"], {"answer": "wrong version"})
        self.assertEqual("pending", self.store.history(self.session)[0]["status"])

    def test_sessions_do_not_share_memory(self):
        other = self.store.create()
        memory_command(self.store, self.session, "/goal", "My goal")
        self.assertIsNone(self.store.get(other)["state"]["goal"])
        self.assertEqual([], self.store.history(other))

    def test_explicit_correction_and_forget_are_auditable(self):
        memory_command(self.store, self.session, "/term", "snapshot=GitHub data")
        memory_command(self.store, self.session, "/term", "snapshot=persisted GitHub data")
        self.assertEqual("persisted GitHub data", public_state(self.store.get(self.session)["state"])["terms"]["snapshot"])
        memory_command(self.store, self.session, "/forget", "terms snapshot")
        self.assertEqual({}, self.store.get(self.session)["state"]["terms"])
        self.assertEqual(3, len(self.store.export(self.session)["events"]))

    def test_parallel_memory_command_cannot_erase_new_constraint(self):
        second = ChatStore(self.path)
        try:
            def interleaved_update(*args, **kwargs):
                current = second.get(self.session)
                value = "Используем SQLite."
                new_state = update(current["state"], "constraints", "", value, value, value, 0, origin="command")
                second.set_state(self.session, new_state, {"command": "/constraint", "text": value}, current["version"])
                return update(*args, **kwargs)
            with patch("main.update", side_effect=interleaved_update):
                with self.assertRaisesRegex(ValueError, "memory changed"):
                    memory_command(self.store, self.session, "/goal", "Проверить день 18.")
            current = self.store.get(self.session)
            self.assertIsNone(current["state"]["goal"])
            self.assertEqual(["Используем SQLite."], list(public_state(current["state"])["constraints"].values()))
            self.assertEqual(1, current["version"])
            self.assertEqual(1, len(self.store.export(self.session)["events"]))
            memory_command(self.store, self.session, "/goal", "Проверить день 18.")
            self.assertEqual(["Используем SQLite."], list(public_state(self.store.get(self.session)["state"])["constraints"].values()))
        finally:
            second.close()

    def test_stale_forget_cannot_erase_new_term(self):
        memory_command(self.store, self.session, "/term", "snapshot=data")
        second = ChatStore(self.path)
        try:
            from memory import forget
            def interleaved_forget(*args, **kwargs):
                memory_command(second, self.session, "/term", "report=Markdown")
                return forget(*args, **kwargs)
            with patch("main.forget", side_effect=interleaved_forget):
                with self.assertRaisesRegex(ValueError, "memory changed"):
                    memory_command(self.store, self.session, "/forget", "terms snapshot")
            self.assertEqual({"snapshot": "data", "report": "Markdown"},
                             public_state(self.store.get(self.session)["state"])["terms"])
            self.assertEqual(2, len(self.store.export(self.session)["events"]))
        finally:
            second.close()

    def test_completed_turn_cannot_be_overwritten_by_stale_command(self):
        old = self.store.get(self.session)
        turn, current = self.store.begin(self.session, "Question")
        state = update(current["state"], "goal", "", "New goal", "New goal", "New goal", turn, origin="command")
        self.store.finish(self.session, turn, current["version"], state, {"answer": "Answer"})
        with self.assertRaisesRegex(ValueError, "memory changed"):
            self.store.set_state(self.session, old["state"], {"command": "/forget"}, old["version"])
        self.assertEqual("New goal", public_state(self.store.get(self.session)["state"])["goal"])
        self.assertEqual("complete", self.store.history(self.session)[0]["status"])
        self.assertEqual([], self.store.export(self.session)["events"])

    def test_other_session_update_does_not_block_memory_command(self):
        other = self.store.create()
        old = self.store.get(self.session)
        memory_command(self.store, other, "/goal", "Other goal")
        self.store.set_state(self.session, old["state"], {"command": "/forget"}, old["version"])
        self.assertEqual(1, self.store.get(self.session)["version"])
        self.assertEqual("Other goal", public_state(self.store.get(other)["state"])["goal"])


class JsonOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_database_and_all_sidecars_are_protected_even_before_creation(self):
        database = self.root / "chat.db"
        for suffix in ("", "-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                with self.assertRaisesRegex(ValueError, "database"):
                    write_json(Path(str(database) + suffix), {}, (database,))
                self.assertFalse(Path(str(database) + suffix).exists())

    def test_sqlite_database_is_protected_with_any_filename(self):
        database = self.root / "renamed.json"
        store = ChatStore(database)
        session = store.create("Preserve this session")
        store.close()
        before = database.read_bytes()
        with self.assertRaisesRegex(ValueError, "SQLite"):
            write_json(database, {"replace": True})
        self.assertEqual(before, database.read_bytes())
        reopened = ChatStore(database)
        try:
            self.assertEqual("Preserve this session", reopened.get(session)["title"])
        finally:
            reopened.close()

    def test_symlinks_and_hardlinks_cannot_bypass_database_or_sidecar_protection(self):
        database = self.root / "chat.db"
        database.write_bytes(b"protected")
        sidecar = Path(str(database) + "-wal")
        sidecar.write_bytes(b"WAL must survive")
        for target in (database, sidecar):
            for link_kind in ("symlink", "hardlink"):
                alias = self.root / (target.name + "." + link_kind + ".json")
                alias.symlink_to(target) if link_kind == "symlink" else os.link(target, alias)
                with self.subTest(target=target, kind=link_kind):
                    with self.assertRaisesRegex(ValueError, "database"):
                        write_json(alias, {}, (database,))
                    self.assertEqual(target.read_bytes(), alias.read_bytes())

    def test_invalid_json_does_not_truncate_existing_report(self):
        report = self.root / "report.json"
        report.write_text('{"old":true}\n')
        before = report.read_bytes()
        with self.assertRaises(ValueError):
            write_json(report, {"invalid": float("nan")})
        self.assertEqual(before, report.read_bytes())
        self.assertEqual([report], list(self.root.iterdir()))

    def test_failed_atomic_replace_preserves_report_and_removes_temporary_file(self):
        report = self.root / "report.json"
        report.write_text('{"old":true}\n')
        before = report.read_bytes()
        with patch("io25.os.replace", side_effect=OSError("disk error")):
            with self.assertRaisesRegex(OSError, "disk error"):
                write_json(report, {"new": True})
        self.assertEqual(before, report.read_bytes())
        self.assertEqual([report], list(self.root.iterdir()))

    def test_normal_json_export_replaces_report_and_creates_parents(self):
        report = self.root / "reports" / "dialogue.json"
        write_json(report, {"answer": "Ответ"})
        write_json(report, {"answer": "Новый ответ"})
        self.assertEqual({"answer": "Новый ответ"}, json.loads(report.read_text(encoding="utf-8")))
        self.assertEqual([report], list(report.parent.iterdir()))

    def test_offline_demo_rejects_sqlite_output_before_starting_fixture(self):
        database = self.root / "index.json"
        store = ChatStore(database)
        store.close()
        with patch("offline_demo.http_fixture") as fixture:
            with self.assertRaisesRegex(ValueError, "SQLite"):
                run_demo(database)
            fixture.assert_not_called()


class MemoryTests(unittest.TestCase):
    def test_question_fragment_cannot_be_saved_as_a_confirmed_constraint(self):
        message = "Используем SQLite?"
        with self.assertRaisesRegex(ValueError, "Questions"):
            update(empty_state(), "constraints", "", "SQLite", "SQLite", message, 1)

    def test_extracted_positive_value_cannot_drop_immediate_negation(self):
        for message, value in (("Не используем SQLite.", "используем SQLite."),
                               ("We are not using SQLite.", "using SQLite.")):
            with self.assertRaisesRegex(ValueError, "negation"):
                update(empty_state(), "constraints", "", value, value, message, 1)
            saved = update(empty_state(), "constraints", "", message, message, message, 1)
            self.assertEqual(message, next(iter(saved["constraints"].values()))["value"])

    def test_question_about_goal_does_not_authorize_goal_replacement(self):
        state = update(empty_state(), "goal", "", "Prepare demo", "Prepare demo", "Prepare demo", 0, origin="command")
        with self.assertRaisesRegex(ValueError, "question.*goal"):
            update(state, "goal", "", "цель", "цель", "Какая цель дня 20?", 1)

    def test_planner_duplicate_keys_nan_and_oversized_output_are_rejected_without_memory_loss(self):
        class Provider:
            def structured(self, prompt, schema): return self.raw
        provider = Provider()
        message = "Цель: Проверить день 18.\nКакие поля сохраняет worker на день 18?"
        good = '{"resolved_question":"Какие поля сохраняет worker на день 18?","needs_clarification":false,"updates":[]}'
        for raw in (good[:-1] + ',"updates":[]}', good.replace("false", "NaN"), "x" * 40001):
            provider.raw = raw
            _, state, _, trace = plan(provider, message, empty_state(), [], 1)
            self.assertEqual("Проверить день 18.", public_state(state)["goal"])
            self.assertTrue(any("Planner rejected" in warning for warning in trace["warnings"]))

    def test_process_identity_audit_preserves_negative_verdict_and_explicit_path_requirement(self):
        units = [{"id": "p1_1", "chunk_id": "a", "text": "A separate worker polls the schedule."},
                 {"id": "p2_1", "chunk_id": "a", "text": "| Name | Action |"},
                 {"id": "p2_2", "chunk_id": "a", "text": "|---|---|"},
                 {"id": "p2_3", "chunk_id": "a", "text": "| worker | Poll schedule |"}]
        data = {"question_context": "Which process performs background work? Give its absolute path.",
                "coverage_requirement": {"id": "question", "need": "Identify process AND absolute path"},
                "lesson_scope": [{"source": "day-18-example/README.md", "course_lesson": 18}],
                "proof_units": units}
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}, "covered": {}}}
        negative = {"covered": False, "proof_ids": [], "reason": "The requested absolute path is absent"}
        provider = RefinementTests.Provider([negative])
        raw = ContextProvider(provider, {"task_state": {"goal": "OLD_GOAL_NOT_EVIDENCE"}}).structured(
            "Audit\nDATA:\n" + json.dumps(data), schema)
        self.assertEqual(negative, json.loads(raw))
        self.assertEqual(1, len(provider.calls))
        actual, actual_schema = provider.calls[0]
        self.assertEqual(data, json.loads(actual.rsplit("\nDATA:\n", 1)[1]))
        self.assertEqual(schema, actual_schema)
        self.assertIn("какой процесс выполняет действие", actual)
        self.assertIn("не полного описания алгоритма", actual)
        self.assertIn("Если они явно запрошены", actual)
        self.assertNotIn("OLD_GOAL_NOT_EVIDENCE", actual)

    def test_mixed_table_and_multiline_sequence_audit_keeps_blocks_and_negative_verdict(self):
        class Provider:
            def __init__(self):
                self.calls = []
            def structured(self, prompt, schema):
                self.calls.append((prompt, schema))
                return '{"reason":"Requested route mapping is absent","proof_ids":[],"covered":false}'
        units = [{"id": "p1_1", "chunk_id": "a", "text": "| Server | Tool |"},
                 {"id": "p1_2", "chunk_id": "a", "text": "|---|---|"},
                 {"id": "p1_3", "chunk_id": "a", "text": "| `first` | `fetch` |"},
                 {"id": "p2_1", "chunk_id": "a", "text": "first.fetch → second.summarize"},
                 {"id": "p2_2", "chunk_id": "a", "text": "→ third.save → third.read → second.verify"}]
        data = {"question_context": "What is the order for the full report?",
                "coverage_requirement": {"id": "question", "need": "All requested parts"},
                "lesson_scope": [{"source": "day-20-example/README.md", "course_lesson": 20}],
                "proof_units": units}
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}, "covered": {}}}
        provider = Provider()
        raw = ContextProvider(provider, {"recent_history": [{"assistant": "OLD_ANSWER"}]}).structured(
            "Audit\nDATA:\n" + json.dumps(data), schema)
        self.assertFalse(json.loads(raw)["covered"])
        self.assertEqual(1, len(provider.calls))
        prompt = provider.calls[0][0]
        self.assertEqual(data, json.loads(prompt.rsplit("\nDATA:\n", 1)[1]))
        blocks = json.loads(prompt.split("LITERAL CONSECUTIVE PROOF BLOCKS (original lines and IDs, not new evidence):\n", 1)[1].split("\n\nDATA:\n", 1)[0])
        self.assertEqual([{"proof_id": "p2_1", "text": units[3]["text"]},
                          {"proof_id": "p2_2", "text": units[4]["text"]}], blocks[1]["lines"])
        self.assertIn("перенос строки не завершает цепочку", prompt)
        self.assertIn("связь с маршрутом отсутствует", prompt)
        self.assertNotIn("OLD_ANSWER", prompt)
        # Excluding a unit from the schema must not reintroduce it in navigation.
        schema["properties"]["proof_ids"]["items"]["enum"].remove("p2_2")
        ContextProvider(provider, {}).structured("Audit\nDATA:\n" + json.dumps(data), schema)
        index = provider.calls[-1][0].split("LITERAL CONSECUTIVE PROOF BLOCKS (original lines and IDs, not new evidence):\n", 1)[1].split("\n\nDATA:\n", 1)[0]
        self.assertNotIn('"proof_id": "p2_2"', index)

    def test_selector_scope_does_not_expand_current_question_or_trim_model_selection(self):
        class Provider:
            def structured(self, prompt, schema):
                self.prompt = prompt
                return '{"status":"answered","quote_ids":["q1","q2"]}'
        data = {"question": "Name the tools", "chunks": []}
        schema = {"properties": {"quote_ids": {"items": {"enum": ["q1", "q2"]}}}}
        provider = Provider()
        raw = ContextProvider(provider, {"task_state": {"goal": "Prepare full demonstration"}}).structured(
            "Select\nDATA:\n" + json.dumps(data), schema)
        self.assertEqual(["q1", "q2"], json.loads(raw)["quote_ids"])
        self.assertIn("не расширяют его", provider.prompt)
        self.assertIn("После достаточного ответа не добавляй", provider.prompt)
        self.assertEqual(data, json.loads(provider.prompt.rsplit("\nDATA:\n", 1)[1]))

    def test_table_audit_keeps_entire_original_data_and_one_negative_verdict(self):
        class Provider:
            def __init__(self):
                self.calls = []
            def structured(self, prompt, schema):
                self.calls.append((prompt, schema))
                return '{"reason":"Missing requested path","proof_ids":[],"covered":false}'
        units = [{"id": "p2_1", "chunk_id": "chunk", "text": "| Сервер | Инструменты |"},
                 {"id": "p2_2", "chunk_id": "chunk", "text": "|---|---|"},
                 {"id": "p2_3", "chunk_id": "chunk", "text": "| `github` | `get_repository_info` |"},
                 {"id": "p2_4", "chunk_id": "chunk", "text": "| `analysis` | `verify_report` |"},
                 {"id": "p3_1", "chunk_id": "other", "text": "Other selected evidence stays available."}]
        data = {"question_context": "Назови серверы и точные пути на день 20.",
                "coverage_requirement": {"id": "question", "need": "All requested parts"},
                "lesson_scope": [{"source": "day-20-example/README.ru.md", "course_lesson": 20}],
                "proof_units": units}
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}, "covered": {}}}
        provider = Provider()
        raw = ContextProvider(provider, {"task_state": {"goal": "OLD_GOAL_NOT_EVIDENCE"}}).structured(
            "Original task\nDATA:\n" + json.dumps(data, ensure_ascii=False), schema)
        self.assertFalse(json.loads(raw)["covered"])
        self.assertEqual(1, len(provider.calls))
        actual_prompt, actual_schema = provider.calls[0]
        self.assertEqual(data, json.loads(actual_prompt.rsplit("\nDATA:\n", 1)[1]))
        self.assertEqual(schema, actual_schema)
        self.assertIn('"header": "Сервер", "value": "`analysis`"', actual_prompt)
        self.assertIn("код регистрации", actual_prompt)
        self.assertIn("каждый такой пункт", actual_prompt)
        self.assertNotIn("OLD_GOAL_NOT_EVIDENCE", actual_prompt)

    def test_source_table_navigation_uses_only_allowed_quotes_and_is_bounded(self):
        table = "| Server | Tool |\n|---|---|\n| `first` | `one` |\n| `second` | `two` |"
        data = {"chunks": [{"quotes": [{"quote_id": "q1_1", "text": table},
                                       {"quote_id": "forbidden", "text": table.replace("first", "forged")}]}]}
        schema = {"properties": {"quote_ids": {"items": {"enum": ["q1_1"]}}}}
        rows = quote_table_rows("\nDATA:\n" + json.dumps(data), schema)
        self.assertEqual(2, len(rows))
        self.assertEqual("q1_1", rows[0]["quote_id"])
        self.assertEqual({"header": "Server", "value": "`first`"}, rows[0]["columns"][0])
        self.assertNotIn("forged", json.dumps(rows))
        data["chunks"][0]["quotes"][0]["text"] = "| Name | Role |\n|---|---|\n" + "\n".join(f"| name{i} | role{i} |" for i in range(40))
        self.assertEqual(16, len(quote_table_rows("\nDATA:\n" + json.dumps(data), schema)))
        for malformed in ("bad data", "\nDATA:\nnull", '\nDATA:\n{"chunks":[null]}'):
            self.assertEqual([], quote_table_rows(malformed, schema))
        self.assertIsNone(table_audit_prompt("bad data", rows))

    def test_selector_receives_literal_source_table_navigation_without_fake_answer(self):
        class Provider:
            def structured(self, prompt, schema):
                self.prompt = prompt
                return '{"status":"unknown","quote_ids":[]}'
        data = {"chunks": [{"quotes": [{"quote_id": "q1_1", "text": "| Server | Tool |\n|---|---|\n| `github` | `get_repository_info` |"}]}]}
        schema = {"properties": {"quote_ids": {"items": {"enum": ["q1_1"]}}}}
        provider = Provider()
        raw = ContextProvider(provider, {}).structured("\nDATA:\n" + json.dumps(data), schema)
        self.assertEqual({"status": "unknown", "quote_ids": []}, json.loads(raw))
        self.assertIn("SOURCE TABLE NAVIGATION", provider.prompt)
        self.assertIn('"quote_id": "q1_1"', provider.prompt)
        self.assertEqual(data, json.loads(provider.prompt.rsplit("\nDATA:\n", 1)[1]))

    def test_fragment_links_keep_literal_neighbors_within_schema_and_chunk(self):
        data = {"chunks": [{"quotes": [
            {"quote_id": "q1_1", "text": "В терминале 1:"},
            {"quote_id": "q1_2", "text": "```bash\npython worker.py\n```"},
            {"quote_id": "q1_3", "text": "В терминале 2, с ключом:"},
            {"quote_id": "q1_4", "text": "```bash\npython main.py\n```"},
            {"quote_id": "q1_5", "text": "Not paired across chunks:"}]},
            {"quotes": [{"quote_id": "q2_1", "text": "```bash\nother\n```"}]}]}
        allowed = [q["quote_id"] for c in data["chunks"] for q in c["quotes"]]
        schema = {"properties": {"quote_ids": {"items": {"enum": allowed}}}}
        prompt = '\nDATA:\n' + json.dumps(data, ensure_ascii=False)
        links = quote_links(prompt, schema)
        self.assertEqual([("q1_1", "q1_2"), ("q1_3", "q1_4")],
                         [(l["intro_quote_id"], l["following_code_quote_id"]) for l in links])
        self.assertEqual("В терминале 2, с ключом:", links[1]["intro_text"])
        self.assertEqual("```bash\npython main.py\n```", links[1]["following_code_text"])
        schema["properties"]["quote_ids"]["items"]["enum"].remove("q1_4")
        self.assertEqual(1, len(quote_links(prompt, schema)))

    def test_fragment_guard_rejects_orphan_reverse_and_intervening_quotes_without_rewriting(self):
        links = [{"intro_quote_id": "q1_3", "following_code_quote_id": "q1_4"}]
        for ids in (["q1_2", "q1_3"], ["q1_4", "q1_3"], ["q1_3", "q1_2", "q1_4"]):
            with self.subTest(ids=ids), self.assertRaisesRegex(EvidenceError, "FOLLOWING code q1_4"):
                validate_fragment_links(json.dumps({"status": "answered", "quote_ids": ids}), links)
        for ids in (["q1_2"], ["q1_3", "q1_4"], ["q1_2", "q1_3", "q1_4"]):
            validate_fragment_links(json.dumps({"status": "answered", "quote_ids": ids}), links)
        for malformed in ('not JSON', 'null', '{"status":"unknown","quote_ids":[]}'):
            validate_fragment_links(malformed, links)  # Existing strict validator handles format/unknown.

    def test_fragment_navigation_is_bounded_and_malformed_data_is_safe(self):
        quotes = [q for i in range(20) for q in (
            {"quote_id": f"intro{i}", "text": "Run:"},
            {"quote_id": f"code{i}", "text": "```bash\ncommand\n```"})]
        schema = {"properties": {"quote_ids": {"items": {"enum": [q["quote_id"] for q in quotes]}}}}
        prompt = '\nDATA:\n' + json.dumps({"chunks": [{"quotes": quotes}]})
        self.assertEqual(16, len(quote_links(prompt, schema)))
        for malformed in ('not data', '\nDATA:\nnull', '\nDATA:\n{"chunks":[null]}'):
            self.assertEqual([], quote_links(malformed, schema))

    def test_goal_anchor_requires_explicit_return_and_one_observed_lesson(self):
        state = update(empty_state(), "goal", "", "Check day 18", "Check day 18", "Check day 18", 0, "command")
        self.assertEqual("18", goal_lesson("Вернёмся к нашей цели. Как запустить процесс?", state))
        self.assertEqual("18", goal_lesson("Back to our goal. Which process?", state))
        self.assertIsNone(goal_lesson("А какой процесс запускается?", state))
        self.assertIsNone(goal_lesson("Не возвращаемся к цели. А какой процесс?", state))
        self.assertIsNone(goal_lesson("Если сказать 'Вернёмся к цели', что будет?", state))
        self.assertIsNone(goal_lesson("Вернёмся к цели. Как запускается день 20?", state))
        self.assertIsNone(goal_lesson("Вернёмся к цели. Как запустить процесс?", empty_state()))
        two = update(state, "goal", "", "Compare day 18 and day 20", "Compare day 18 and day 20",
                     "Compare day 18 and day 20", 0, "command")
        self.assertIsNone(goal_lesson("Return to our goal. Which process?", two))

    def test_memory_noop_ignores_identical_proposal_without_accepting_historical_evidence(self):
        state = update(empty_state(), "constraints", "", "Use SQLite.", "Use SQLite.", "Use SQLite.", 0, "command")
        key = next(iter(state["constraints"]))
        row = {"kind": "constraints", "key": key, "value": "Use SQLite.", "evidence": "FORGED_EVIDENCE"}
        self.assertTrue(existing_memory_noop(state, row))
        self.assertTrue(existing_memory_noop(state, dict(row, key="")))
        self.assertFalse(existing_memory_noop(state, dict(row, value="Use PostgreSQL.")))
        self.assertFalse(existing_memory_noop(state, dict(row, key="unknown-key")))
        class Provider:
            def structured(self, prompt, schema):
                return json.dumps({"resolved_question": "Which database on day 18?", "needs_clarification": False,
                                   "updates": [row]})
        _, after, _, trace = plan(Provider(), "Which database on day 18?", state, [], 2)
        self.assertEqual(state, after)
        self.assertEqual([], trace["warnings"])
        self.assertEqual(key, trace["memory_noops"][0]["key"])
        self.assertNotIn("FORGED_EVIDENCE", json.dumps(after))
        # A genuinely changed value still needs literal CURRENT evidence.
        row["value"] = "Use PostgreSQL."
        _, after, _, trace = plan(Provider(), "Which database on day 18?", state, [], 3)
        self.assertEqual(state, after)
        self.assertIn("Memory must be an exact substring of current user evidence", trace["warnings"])

    def test_goal_return_overrides_model_detour_but_keeps_explicit_topic_and_ambiguity(self):
        state = update(empty_state(), "goal", "", "Check day 18", "Check day 18", "Check day 18", 0, "command")
        message = "Return to our goal. Which process and command?"
        class Provider:
            payload = {"resolved_question": "Which MCP servers on day 20?", "needs_clarification": False, "updates": []}
            def structured(self, prompt, schema): return json.dumps(self.payload)
        provider = Provider()
        question, after, ambiguous, trace = plan(provider, message, state, [], 2)
        self.assertEqual(message + " (goal context: day 18)", question)
        self.assertEqual(state, after)
        self.assertFalse(ambiguous)
        self.assertEqual("18", trace["goal_anchor"]["lesson"])
        provider.payload = {"resolved_question": "Which process on day 20?", "needs_clarification": False, "updates": []}
        question, _, _, trace = plan(provider, "Return to our goal. Which process on day 20?", state, [], 3)
        self.assertEqual("Which process on day 20?", question)
        self.assertNotIn("goal_anchor", trace)
        provider.payload = {"resolved_question": message, "needs_clarification": True, "updates": []}
        question, _, ambiguous, trace = plan(provider, message, state, [], 4)
        self.assertTrue(ambiguous)
        self.assertEqual(message, question)
        self.assertNotIn("goal_anchor", trace)

    def test_followup_lesson_uses_latest_topic_without_replacing_saved_goal(self):
        state = update(empty_state(), "goal", "", "Check day 18", "Check day 18", "Check day 18", 0, "command")
        history = [{"user": "Какие MCP-серверы участвуют в оркестрации на день 20?",
                    "resolved_question": "Какие MCP-серверы участвуют в оркестрации на день 20?",
                    "resolution_accepted": True, "resolution_state": resolution_state(state)}]
        message = "А в каком порядке вызываются инструменты для полного отчёта?"
        class Provider:
            def structured(self, prompt, schema):
                self.prompt = prompt
                return json.dumps({"resolved_question": message, "needs_clarification": False, "updates": []})
        provider = Provider()
        question, after, ambiguous, trace = plan(provider, message, state, history, 11)
        self.assertEqual(message + " (контекст: день 20)", question)
        self.assertEqual(state, after)
        self.assertFalse(ambiguous)
        self.assertEqual([], trace["warnings"])
        self.assertEqual("20", trace["topic_anchor"]["lesson"])
        self.assertIn('"latest_followup_lesson": "20"', provider.prompt)
        retry = {"user": message, "resolved_question": message, "resolution_accepted": True,
                 "answer_status": "unknown", "resolution_state": resolution_state(state)}
        self.assertEqual("20", followup_lesson(message, state, history + [retry, retry]))

    def test_followup_anchor_never_guesses_between_topics_or_overrides_ambiguity(self):
        state = empty_state()
        row = {"user": "Day 20 tools", "resolved_question": "Day 20 tools",
               "resolution_accepted": True, "resolution_state": resolution_state(state)}
        for message, history in [("And day 18 storage?", [row]),
                                 ("Вернёмся к нашей цели. А порядок?", [row]),
                                 ("And the order?", []),
                                 ("And the order?", [dict(row, resolved_question="Compare day 18 and day 20")]),
                                 ("And the order?", [dict(row, resolution_accepted=False)]),
                                 ("And the order?", [row, dict(row, resolved_question="Unknown topic", user="Unknown topic")])]:
            with self.subTest(message=message, history=history):
                self.assertIsNone(followup_lesson(message, state, history))
        edited = update(state, "goal", "", "New goal", "New goal", "New goal", 0, "command")
        self.assertIsNone(followup_lesson("And the order?", edited, [row]))
        class Provider:
            def structured(self, prompt, schema):
                return '{"resolved_question":"And the order?","needs_clarification":true,"updates":[]}'
        question, _, ambiguous, trace = plan(Provider(), "And the order?", state, [row], 2)
        self.assertEqual("And the order?", question)
        self.assertTrue(ambiguous)
        self.assertNotIn("topic_anchor", trace)

    def test_proof_blocks_preserve_literals_and_break_at_excluded_or_foreign_units(self):
        units = [{"id": "p1_1", "chunk_id": "a", "text": 'FLOW = ("fetch",'},
                 {"id": "p1_2", "chunk_id": "a", "text": '"save")'},
                 {"id": "p1_3", "chunk_id": "a", "text": 'FORGED_MISSING'},
                 {"id": "p1_4", "chunk_id": "a", "text": 'AFTER_GAP'},
                 {"id": "p1_5", "chunk_id": "b", "text": 'OTHER_CHUNK'},
                 {"id": "p2_1", "chunk_id": "b", "text": 'OTHER_QUOTE'},
                 {"id": "p2_2", "chunk_id": "b", "text": 'SECOND_LITERAL'}]
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units if u["id"] != "p1_3"]}}}}
        rows = proof_blocks('\nDATA:\n' + json.dumps({"proof_units": units}), schema)
        self.assertEqual([["p1_1", "p1_2"], ["p2_1", "p2_2"]],
                         [[p["proof_id"] for p in r["lines"]] for r in rows])
        for row in rows:
            for proof in row["lines"]:
                self.assertEqual(next(u["text"] for u in units if u["id"] == proof["proof_id"]), proof["text"])
        self.assertNotIn("FORGED_MISSING", json.dumps(rows))

    def test_proof_blocks_are_bounded_and_do_not_truncate_incomplete_declarations(self):
        units = [{"id": f"p{group}_{i}", "chunk_id": "a", "text": "x" * 100}
                 for group in range(1, 20) for i in range(1, 3)]
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}}}
        prompt = '\nDATA:\n' + json.dumps({"proof_units": units})
        self.assertEqual(8, len(proof_blocks(prompt, schema)))
        large = [{"id": f"p1_{i}", "chunk_id": "a", "text": "x" * 1800} for i in range(1, 5)]
        schema["properties"]["proof_ids"]["items"]["enum"] = [u["id"] for u in large]
        self.assertEqual([], proof_blocks('\nDATA:\n' + json.dumps({"proof_units": large}), schema))
        for malformed in ('bad data', '\nDATA:\nnull', '\nDATA:\n{"proof_units":[null]}'):
            self.assertEqual([], proof_blocks(malformed, schema))

    def test_sequence_navigation_keeps_reported_negative_verdict_and_audit_isolation(self):
        negative = {"reason": "The provided proof units describe the sequence of operations for generating a full report, but do not explicitly state the order of tool invocation for a full report as requested.",
                    "proof_ids": ["p1_1", "p1_2", "p1_3"], "covered": False}
        class Provider:
            def structured(self, prompt, schema):
                self.prompt = prompt
                return json.dumps(negative)
        units = [{"id": "p1_1", "chunk_id": "a", "text": 'FLOW = ("github__get_repository_info",'},
                 {"id": "p1_2", "chunk_id": "a", "text": '"storage__save_report")'},
                 {"id": "p1_3", "chunk_id": "a", "text": 'FLOWS = {"report": FLOW}'}]
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}, "covered": {}}}
        provider = Provider()
        raw = ContextProvider(provider, {"task_state": {"goal": "SECRET_OLD_GOAL"}}).structured(
            '\nDATA:\n' + json.dumps({"proof_units": units}), schema)
        self.assertEqual(negative, json.loads(raw))
        self.assertIn("Code is admissible evidence", provider.prompt)
        self.assertIn("LITERAL CONSECUTIVE PROOF BLOCKS", provider.prompt)
        self.assertNotIn("SECRET_OLD_GOAL", provider.prompt)

    def test_table_index_keeps_literal_headers_and_only_allowed_same_claim_rows(self):
        units = [{"id": "p3_1", "text": "| Сервер | Инструменты | Задача |"},
                 {"id": "p3_2", "text": "|---|---|---|"},
                 {"id": "p3_3", "text": "| `github` | `get_repository_info` | Получить метаданные GitHub |"},
                 {"id": "p3_4", "text": "| `analysis` | `summarize_repository`, `verify_report` | Подготовить сводку |"},
                 {"id": "p9_1", "text": "| `wrong_claim` | `tool` | Invalid |"}]
        prompt = '\nDATA:\n' + json.dumps({"proof_units": units}, ensure_ascii=False)
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}}}
        rows = proof_table_rows(prompt, schema)
        self.assertEqual(2, len(rows))
        self.assertEqual({"header": "Сервер", "value": "`github`"}, rows[0]["columns"][0])
        self.assertEqual("p3_1", rows[0]["header_proof_id"])
        schema["properties"]["proof_ids"]["items"]["enum"].remove("p3_1")
        self.assertEqual([], proof_table_rows(prompt, schema))

    def test_table_index_requires_separator_matching_width_and_is_bounded(self):
        units = [{"id": "p1_1", "text": "| Name | Role |"},
                 {"id": "p1_2", "text": "|---|---|"}]
        units += [{"id": f"p1_{i+3}", "text": f"| name{i} | role{i} |"} for i in range(30)]
        units.append({"id": "p1_100", "text": "| wrong | width | extra |"})
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}}}
        prompt = '\nDATA:\n' + json.dumps({"proof_units": units})
        self.assertEqual(16, len(proof_table_rows(prompt, schema)))
        no_separator = '\nDATA:\n' + json.dumps({"proof_units": [units[0], units[2], units[-1]]})
        self.assertEqual([], proof_table_rows(no_separator, schema))
        self.assertEqual([], proof_table_rows('bad data', schema))

    def test_table_navigation_does_not_change_negative_auditor_verdict(self):
        class Provider:
            def structured(self, prompt, schema):
                self.prompt = prompt
                return '{"reason":"Missing other requested facts","proof_ids":[],"covered":false}'
        units = [{"id": "p1_1", "text": "| Server | Tool |"},
                 {"id": "p1_2", "text": "|---|---|"},
                 {"id": "p1_3", "text": "| `github` | `get_repository_info` |"}]
        schema = {"properties": {"proof_ids": {"items": {"enum": [u["id"] for u in units]}}, "covered": {}}}
        prompt = '\nDATA:\n' + json.dumps({"proof_units": units, "question_context": "Name all servers and their paths"})
        provider = Provider()
        raw = ContextProvider(provider, {}).structured(prompt, schema)
        self.assertFalse(json.loads(raw)["covered"])
        self.assertIn('"header": "Server", "value": "`github`"', provider.prompt)
        self.assertIn("not their full filesystem paths", provider.prompt)
        self.assertIn("explicitly requested part", provider.prompt)

    def test_audit_isolated_from_history_and_state_and_indexes_only_allowed_proofs(self):
        class Provider:
            def structured(self, prompt, schema):
                self.prompt = prompt
                return '{"reason":"still unproved","proof_ids":[],"covered":false}'
        provider = Provider()
        context = {"task_state": {"goal": "SECRET_OLD_GOAL"},
                   "recent_history": [{"assistant": "SECRET_OLD_REFUSAL"}]}
        data = {"question_context": "Где хранятся снимки?",
                "lesson_scope": [{"source": "misleading-database.db"}],
                "proof_units": [{"id": "p1", "text": "Снимки сохраняются в SQLite."},
                                {"id": "p2", "text": "Данные `schedule.db` сохраняются."},
                                {"id": "bad", "text": "Данные `forged.db` сохраняются."}]}
        schema = {"properties": {"proof_ids": {"items": {"enum": ["p1", "p2"]}}, "covered": {}}}
        prompt = 'Audit\nDATA:\n' + json.dumps(data, ensure_ascii=False)
        self.assertEqual([{"proof_id": "p2", "literal": "schedule.db"}], proof_identifiers(prompt, schema))
        raw = ContextProvider(provider, context).structured(prompt, schema)
        self.assertFalse(json.loads(raw)["covered"])
        self.assertNotIn("SECRET_OLD_GOAL", provider.prompt)
        self.assertNotIn("SECRET_OLD_REFUSAL", provider.prompt)
        self.assertIn('"literal": "schedule.db"', provider.prompt)
        self.assertNotIn('"literal": "misleading-database.db"', provider.prompt)
        self.assertNotIn('"literal": "forged.db"', provider.prompt)

    def test_selector_still_receives_task_memory_and_history(self):
        class Provider:
            def structured(self, prompt, schema):
                self.prompt = prompt
                return '{}'
        provider = Provider()
        ContextProvider(provider, {"task_state": {"goal": "Keep objective"},
                                  "recent_history": [{"user": "Previous topic", "assistant": "OLD_ANSWER_NOT_CURRENT_EVIDENCE"}]}).structured(
                                      'Select\nDATA:\n{}', {"properties": {"quote_ids": {}}})
        self.assertIn("Keep objective", provider.prompt)
        self.assertIn("Previous topic", provider.prompt)
        self.assertNotIn("OLD_ANSWER_NOT_CURRENT_EVIDENCE", provider.prompt)

    def test_identifier_index_is_bounded_and_malformed_data_is_safe(self):
        schema = {"properties": {"proof_ids": {"items": {"enum": ["p1"]}}}}
        data = {"proof_units": [{"id": "p1", "text": ' '.join(f'`file{i}.db`' for i in range(50))}]}
        self.assertEqual(32, len(proof_identifiers('\nDATA:\n' + json.dumps(data), schema)))
        self.assertEqual([], proof_identifiers('not data', schema))
        self.assertEqual([], proof_identifiers('\nDATA:\nnull', schema))

    def test_resolution_reuse_stops_on_topic_switch_and_memory_edit(self):
        message = "А где это хранится?"
        state = update(empty_state(), "goal", "", "Check day 18", "Check day 18", "Check day 18", 0, "command")
        row = {"user": message, "resolved_question": "Где хранятся снимки дня 18?",
               "resolution_accepted": True, "resolution_state": resolution_state(state)}
        self.assertEqual(row["resolved_question"], previous_resolution(message, state, [row]))
        self.assertIsNone(previous_resolution(message, state, [row, {"user": "Какие серверы на день 20?"}]))
        edited = update(state, "goal", "", "Check day 20", "Check day 20", "Check day 20", 0, "command")
        self.assertIsNone(previous_resolution(message, edited, [row]))

    def test_recent_context_keeps_resolution_from_refusal_without_claiming_answer(self):
        state = empty_state()
        rows = [{"status": "complete", "question": "А где это хранится?",
                 "response": {"status": "unknown", "answer": "Не знаю.",
                              "resolved_question": "Где хранятся снимки дня 18?",
                              "conversation": {"effective_needs_clarification": False}, "task_state": state}}]
        context = recent_context(rows)
        self.assertEqual("unknown", context[0]["answer_status"])
        self.assertTrue(context[0]["resolution_accepted"])
        self.assertEqual("Где хранятся снимки дня 18?", previous_resolution(rows[0]["question"], state, context))

    def test_wrong_constraint_key_adds_fact_and_duplicate_keeps_provenance(self):
        state = update(empty_state(), "constraints", "", "Use SQLite.", "Use SQLite.", "Use SQLite.", 0, "command")
        key = next(iter(state["constraints"]))
        result = update(state, "constraints", key, "Separate worker.", "Separate worker.", "Separate worker.", 1)
        self.assertEqual(2, len(result["constraints"]))
        self.assertEqual(state["constraints"][key], result["constraints"][key])
        duplicate = update(result, "constraints", "", "Use SQLite.", "Use SQLite.", "Use SQLite.", 2)
        self.assertEqual(result, duplicate)

    def test_explicit_previous_value_or_key_authorizes_correction(self):
        old, new = "Use SQLite.", "Use PostgreSQL."
        state = update(empty_state(), "constraints", "", old, old, old, 1)
        key = next(iter(state["constraints"]))
        extra = update(state, "constraints", key, new, new, f'{old} Additionally: {new}', 2)
        self.assertEqual(2, len(extra["constraints"]))
        for message in (f'Replace "{old}" with "{new}"', f'Replace {key}: {new}'):
            result = update(state, "constraints", key, new, new, message, 2)
            self.assertEqual(1, len(result["constraints"]))
            self.assertEqual(new, result["constraints"][key]["value"])

    def test_existing_term_cannot_be_changed_without_current_term_name(self):
        state = update(empty_state(), "terms", "snapshot", "GitHub data", "snapshot=GitHub data", "snapshot=GitHub data", 1)
        with self.assertRaisesRegex(ValueError, "term name"):
            update(state, "terms", "snapshot", "manual check", "manual check", "manual check", 2)
        result = update(state, "terms", "snapshot", "persisted data", "snapshot=persisted data", "snapshot=persisted data", 2)
        self.assertEqual("persisted data", result["terms"]["snapshot"]["value"])

    def test_model_cannot_store_facts_absent_from_user_message(self):
        with self.assertRaisesRegex(ValueError, "substring"):
            update(empty_state(), "constraints", "", "Use PostgreSQL", "Use SQLite", "Use SQLite", 1)
        message = "Какой процесс выполняет фоновые задания"
        with self.assertRaisesRegex(ValueError, "Questions"):
            update(empty_state(), "clarifications", "", message, message, message, 1)

    def test_incidental_question_cannot_replace_goal(self):
        state = update(empty_state(), "goal", "", "Prepare demo", "Prepare demo", "Prepare demo", 1)
        with self.assertRaisesRegex(ValueError, "explicit"):
            update(state, "goal", "", "What is SQLite?", "What is SQLite?", "What is SQLite?", 2)
        self.assertEqual("Prepare demo", state["goal"]["value"])

    def test_memory_budget_rejects_update_without_dropping_old_items(self):
        state = empty_state()
        for index in range(20):
            text = str(index) + "a" * 590
            before = copy.deepcopy(state)
            try:
                state = update(state, "constraints", "", text, text, text, index)
            except ValueError as error:
                self.assertIn("full", str(error))
                self.assertEqual(before, state)
                return
        self.fail("Memory budget never applied")

    def test_planner_rejects_forged_memory_and_invented_filename(self):
        class Provider:
            last_call_metadata = {}
            def structured(self, prompt, schema):
                return json.dumps({"resolved_question": "What is SQLite?", "needs_clarification": False,
                    "updates": [{"kind": "constraints", "key": "", "value": "Postgres", "evidence": "Postgres"}]})
        question, state, _, trace = plan(Provider(), "What is SQLite?", empty_state(), [], 1)
        self.assertEqual(empty_state(), state)
        self.assertTrue(trace["warnings"])
        class Inventor(Provider):
            def structured(self, prompt, schema):
                return json.dumps({"resolved_question": "What is secret.py?", "needs_clarification": False, "updates": []})
        question, _, _, trace = plan(Inventor(), "What is SQLite?", empty_state(), [], 1)
        self.assertEqual("What is SQLite?", question)
        self.assertTrue(trace["warnings"])

    def test_recent_context_is_bounded_and_ignores_failed_turns(self):
        rows = [{"status": "complete", "question": str(i) * 1000, "response": {"answer": "x" * 1000}}
                for i in range(10)]
        rows.append({"status": "error", "question": "failed", "response": None})
        packed = recent_context(rows, 2000)
        self.assertLessEqual(len(json.dumps(packed)), 2050)
        self.assertNotIn("failed", str(packed))


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.index_path = Path(cls.shared.name) / "knowledge.db"
        fixture_index(cls.index_path).close()

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ChatStore(Path(self.temp.name) / "chats.db")
        self.kb = KnowledgeBase(self.index_path)
        self.session = self.store.create()

    def tearDown(self):
        self.kb.close()
        self.store.close()
        self.temp.cleanup()

    def agent(self, url, **kwargs):
        provider = StructuredOllama(url, "fixture-hash-256", "scripted-fixture", num_ctx=32768)
        return ChatAgent(self.store, self.kb, provider, Settings(40, 20, 0.0, "fixed", "heuristic"), **kwargs)

    def route_refinement_model(self, omit_requested_mapping=False, truncate=False):
        class RouteModel(ScriptedModel):
            def respond(self, endpoint, body):
                result = super().respond(endpoint, body)
                if endpoint != "generate":
                    return result
                prompt = body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0]
                data = json.loads(prompt.rsplit("\nDATA:\n", 1)[1])
                if "quote_ids" in body["format"]["properties"]:
                    chunk = next(c for c in data["chunks"] if c["source"] == "day-20-mcp-orchestration/README.ru.md")
                    quotes = chunk["quotes"]
                    route = next(q["quote_id"] for q in quotes if "`--task info` вызывает только GitHub" in q["text"])
                    chain = next(q["quote_id"] for q in quotes if q["text"].startswith("```text\ngithub.get_repository_info"))
                    caption = next(q["quote_id"] for q in quotes if q["text"].startswith("`mcp_registry.py` регистрирует")) if omit_requested_mapping else None
                    refined = prompt.startswith("SELECTION REFINEMENT")
                    if omit_requested_mapping:
                        # Complete source context, but the requested info-task
                        # mapping is absent. The strict auditor must reject it.
                        ids = [caption, chain] if refined else [caption, chain, route]
                    else:
                        ids = [route] if refined else [route, chain]
                    result["response"] = json.dumps({"status": "answered", "quote_ids": ids})
                    if refined and truncate:
                        result["done_reason"] = "length"
                elif "proof_ids" in body["format"]["properties"] and omit_requested_mapping:
                    result["response"] = json.dumps({"covered": False, "proof_ids": [], "reason": "Requested info route mapping is absent"})
                return result
        return RouteModel()

    def registry_draft_model(self, omit_registry=False):
        class RegistryModel(ScriptedModel):
            def respond(self, endpoint, body):
                result = super().respond(endpoint, body)
                if endpoint != "generate":
                    return result
                prompt = body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0]
                data = json.loads(prompt.rsplit("\nDATA:\n", 1)[1])
                if "quote_ids" in body["format"]["properties"]:
                    chunk = next(c for c in data["chunks"] if c["source"] == "day-20-mcp-orchestration/README.ru.md")
                    registry = next(q["quote_id"] for q in chunk["quotes"] if q["text"].startswith("`mcp_registry.py` регистрирует"))
                    chain = next(q["quote_id"] for q in chunk["quotes"] if q["text"].startswith("```text\ngithub.get_repository_info"))
                    wrong_fact = next(q["quote_id"] for q in chunk["quotes"] if q["text"].startswith("Последний шаг сравнивает")) if omit_registry else None
                    if prompt.startswith("SELECTION REFINEMENT"):
                        ids = [wrong_fact] if omit_registry else [registry, chain]
                    else:
                        intro = next(q["quote_id"] for q in chunk["quotes"] if q["text"].startswith("Из корня распакованного архива"))
                        ids = [registry, chain, intro]
                        if omit_registry:
                            ids.insert(2, wrong_fact)
                    result["response"] = json.dumps({"status": "answered", "quote_ids": ids})
                elif "proof_ids" in body["format"]["properties"] and omit_registry:
                    result["response"] = json.dumps({"covered": False, "proof_ids": [],
                                                     "reason": "Tool chain does not describe registry registration or routing"})
                return result
        return RegistryModel()

    def first_collection_model(self, missing_schedule=False):
        class CollectionModel(ScriptedModel):
            def respond(self, endpoint, body):
                result = super().respond(endpoint, body)
                if endpoint != "generate":
                    return result
                prompt = body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0]
                data = json.loads(prompt.rsplit("\nDATA:\n", 1)[1])
                if "quote_ids" in body["format"]["properties"]:
                    chunk = next(c for c in data["chunks"] if c["source"] == "day-18-scheduled-mcp/README.ru.md")
                    selected = next(q for q in chunk["quotes"] if (
                        q["text"].startswith("Бублик через MCP") if missing_schedule
                        else "первый сбор назначается сразу" in q["text"]))
                    result["response"] = json.dumps({"status": "answered", "quote_ids": [selected["quote_id"]]})
                elif "proof_ids" in body["format"]["properties"] and missing_schedule:
                    result["response"] = json.dumps({"covered": False, "proof_ids": [],
                                                     "reason": "Worker description does not establish first due time"})
                return result
        return CollectionModel()

    def conditional_reaction_model(self, include_action):
        class ReactionModel(ScriptedModel):
            def respond(self,endpoint,body):
                result=super().respond(endpoint,body)
                if endpoint != 'generate': return result
                prompt=body['prompt'].split('\n\nOUTPUT JSON SCHEMA:\n',1)[0]
                data=json.loads(prompt.rsplit('\nDATA:\n',1)[1])
                if 'quote_ids' in body['format']['properties']:
                    chunk=next(c for c in data['chunks'] if c['source']=='day-20-mcp-orchestration/README.ru.md')
                    compound=next(q['quote_id'] for q in chunk['quotes'] if q['text'].startswith('Последний шаг сравнивает'))
                    ids=[compound]
                    if include_action:
                        caption=next(q['quote_id'] for q in chunk['quotes'] if q['text'].startswith('`mcp_registry.py` регистрирует'))
                        chain=next(q['quote_id'] for q in chunk['quotes'] if q['text'].startswith('```text\ngithub.get_repository_info'))
                        ids=[caption,chain,compound]
                    result['response']=json.dumps({'status':'answered','quote_ids':ids})
                elif 'proof_ids' in body['format']['properties']:
                    # Scripted semantic fixture: a literal premature-condition
                    # action differs from a label-only clause. No Qwen claim.
                    action=next((p for p in data['proof_units'] if 'агент выбирает допустимый следующий шаг' in p['text']),None)
                    label=next(p for p in data['proof_units'] if 'agent correction' in p['text'])
                    observation=data['coverage_requirement']['id']=='verification-observation'
                    proof=label if observation else action
                    result['response']=json.dumps({'covered':bool(proof),'proof_ids':[proof['id']] if proof else [],
                        'reason':'Direct conditional action or requested marker' if proof else 'Premature branch has only a marker; fallback action cannot prove it'})
                return result
        return ReactionModel()

    def test_conditional_audit_does_not_publish_label_only_answer_for_action_question(self):
        memory_command(self.store,self.session,'/goal','Разобрать механизм коррекции дня 20.')
        before=copy.deepcopy(self.store.get(self.session)['state'])
        message='Как агент дня 20 исправляет преждевременный VERIFY: как выбирает допустимый следующий шаг и как отмечает исправление в выводе?'
        with http_fixture(self.conditional_reaction_model(False)) as (url,model):
            result=self.agent(url).ask(self.session,message)
        self.assertEqual('unknown',result['status']);self.assertEqual([],result['sources'])
        self.assertEqual(before,result['task_state'])
        self.assertEqual(2,result['validation']['attempts'])
        audits=[b for e,b in model.calls if e=='generate' and 'proof_ids' in b['format']['properties']]
        self.assertEqual(['mechanism'],[r['id'] for r in result['retrieval']['coverage_requirements']])
        self.assertEqual(2,len(audits))  # One full mechanism gate, two new candidates, no approval retry.
        self.assertEqual(2,len(result['validation']['conditional_audits']))
        for body in audits:
            self.assertTrue(body['prompt'].startswith('CONDITIONAL EVIDENCE AUDIT'))
            data=json.loads(body['prompt'].split('\n\nOUTPUT JSON SCHEMA:\n',1)[0].rsplit('\nDATA:\n',1)[1])
            self.assertEqual(result['resolved_question'],data['question_context'])
            self.assertFalse(any('агент выбирает допустимый следующий шаг' in p['text'] for p in data['proof_units']))
        self.assertEqual(2,sum(e=='embed' for e,_ in model.calls))

    def test_custom_requirements_cannot_disable_full_question_coverage(self):
        invalid_factories = (lambda q: [],
                             lambda q: [{'id':'observation','need':'Only a marker'}],
                             lambda q: [{'id':'question','need':'Full question'}, {'id':'question','need':'Duplicate'}])
        for factory in invalid_factories:
            with self.subTest(factory=factory), http_fixture() as (url,model):
                provider=StructuredOllama(url,'fixture-hash-256','scripted-fixture',num_ctx=32768)
                rag=StrictRAGAgent(self.kb,provider,Settings(40,20,0.0,'fixed','heuristic'),requirements_factory=factory)
                with self.assertRaisesRegex(ValueError,'full-question gate'):
                    rag.ask('Какие MCP-серверы зарегистрированы на день 20?')
                self.assertFalse(any(e=='generate' for e,_ in model.calls))

    def test_conditional_audit_preserves_direct_corrective_action_in_another_quote(self):
        message='Как агент дня 20 исправляет преждевременный VERIFY: как выбирает допустимый следующий шаг и как отмечает исправление в выводе?'
        with http_fixture(self.conditional_reaction_model(True)) as (url,model):
            result=self.agent(url).ask(self.session,message)
        self.assertTrue(check_sources(result))
        self.assertIn('агент выбирает допустимый следующий шаг',result['answer'])
        self.assertIn('agent correction',result['answer'])
        self.assertEqual(1,len(result['validation']['conditional_audits']))
        for check in result['validation']['coverage_verdict']['checks']:
            self.assertTrue(check['covered'])
            if check['id'] != 'verification-observation':
                self.assertTrue(any('агент выбирает допустимый следующий шаг' in p['text'] for p in check['proofs']))
        for q in result['quotes']:
            lines=(ROOT/q['source']).read_text().splitlines()
            self.assertEqual(q['quote'],'\n'.join(lines[q['start_line']-1:q['end_line']]))
        self.assertEqual(result,self.store.history(self.session)[-1]['response'])

    def unit_reaction_model(self, mode):
        class UnitReaction(ScriptedModel):
            def __init__(self):
                super().__init__();self.selections=0
            def respond(self,endpoint,body):
                result=super().respond(endpoint,body)
                if endpoint!='generate': return result
                prompt=body['prompt'].split('\n\nOUTPUT JSON SCHEMA:\n',1)[0]
                data=json.loads(prompt.rsplit('\nDATA:\n',1)[1])
                if 'quote_ids' in body['format']['properties']:
                    refining=prompt.startswith('SELECTION REFINEMENT')
                    if not refining:self.selections+=1
                    quotes=next(c for c in data['chunks'] if c['source']=='day-20-mcp-orchestration/README.ru.md')['quotes']
                    caption=next((q['quote_id'] for q in quotes if q['text'].startswith('`mcp_registry.py` регистрирует')),None)
                    chain=next((q['quote_id'] for q in quotes if q['text'].startswith('```text\ngithub.get_repository_info')),None)
                    marker=next(q['quote_id'] for q in quotes if q['text'].startswith('Последний шаг сравнивает'))
                    good=mode=='unit' or (mode=='recover' and self.selections>1)
                    ids=([caption,chain,marker] if refining else [caption,marker]) if good else [marker]
                    result['response']=json.dumps({'status':'answered','quote_ids':ids})
                elif 'proof_ids' in body['format']['properties']:
                    mixed=next(p for p in data['proof_units'] if 'selected by agent fallback' in p['text'])
                    action=next((p for p in data['proof_units'] if 'агент выбирает допустимый следующий шаг' in p['text']),None)
                    ids=[action['id'],mixed['id']] if action else [mixed['id']]
                    # Deliberately overconfident fixture; the application must
                    # reject its bad cross-branch positive, without trusting it.
                    result['response']=json.dumps({'covered':True,'proof_ids':ids,'reason':'Positive fixture decision'})
                return result
        return UnitReaction()

    def test_live_v20_initial_caption_and_marker_decode_to_complete_declared_unit(self):
        memory_command(self.store,self.session,'/goal','Подготовить демонстрацию полного MCP-флоу дня 20.')
        before=copy.deepcopy(self.store.get(self.session)['state'])
        message='Как агент дня 20 исправляет преждевременный VERIFY: как выбирает допустимый следующий шаг и как отмечает исправление в выводе?'
        with http_fixture(self.unit_reaction_model('unit')) as (url,model):
            result=self.agent(url).ask(self.session,message)
        self.assertTrue(check_sources(result));self.assertEqual(1,result['validation']['attempts'])
        self.assertEqual(before,result['task_state']);self.assertEqual(3,len(result['quotes']))
        self.assertIn('агент выбирает допустимый следующий шаг',result['answer'])
        self.assertIn('selected by agent correction',result['answer'])
        trace=result['validation']['source_unit_selections'][0]
        self.assertEqual(2,len(json.loads(trace['raw_response'])['quote_ids']))
        self.assertEqual(3,len(json.loads(trace['expanded_response'])['quote_ids']))
        self.assertNotIn('initial_fragment_errors',result['validation']['selection_refinements'][0])
        for q in result['quotes']:
            lines=(ROOT/q['source']).read_text().splitlines()
            self.assertEqual(q['quote'],'\n'.join(lines[q['start_line']-1:q['end_line']]))
        self.assertEqual(result,self.store.history(self.session)[-1]['response'])

    def test_positive_fixture_cross_branch_verdict_is_rejected_without_audit_approval_retry(self):
        memory_command(self.store,self.session,'/goal','Проверить механизм дня 20.')
        before=copy.deepcopy(self.store.get(self.session)['state'])
        message='Как агент выбирает следующий шаг при преждевременном VERIFY дня 20?'
        with http_fixture(self.unit_reaction_model('bad')) as (url,model):
            result=self.agent(url).ask(self.session,message)
        self.assertEqual('unknown',result['status']);self.assertEqual([],result['sources'])
        self.assertEqual(before,result['task_state']);self.assertEqual(2,result['validation']['attempts'])
        audits=result['validation']['conditional_audits']
        self.assertEqual(2,len(audits))
        self.assertTrue(all('rejected_by_branch_guard' in a for a in audits))
        self.assertTrue(all(json.loads(a['raw_response'])['covered'] for a in audits))
        self.assertEqual(2,len([b for e,b in model.calls if e=='generate' and 'proof_ids' in b['format']['properties']]))
        self.assertEqual(2,sum(e=='embed' for e,_ in model.calls))

    def test_rejected_cross_branch_candidate_can_be_followed_by_new_complete_candidate(self):
        message='Как агент выбирает следующий шаг при преждевременном VERIFY дня 20?'
        with http_fixture(self.unit_reaction_model('recover')) as (url,model):
            result=self.agent(url).ask(self.session,message)
        self.assertTrue(check_sources(result));self.assertEqual(2,result['validation']['attempts'])
        self.assertIn('агент выбирает допустимый следующий шаг',result['answer'])
        self.assertEqual(1,len(result['validation']['errors']))
        self.assertIn('Conditional action guard',result['validation']['errors'][0]['message'])
        self.assertIn('rejected_by_branch_guard',result['validation']['conditional_audits'][0])
        self.assertNotIn('rejected_by_branch_guard',result['validation']['conditional_audits'][1])

    def test_summary_route_uses_single_compact_audit_and_preserves_goal_memory_and_sources(self):
        memory_command(self.store,self.session,'/goal','Подготовить демонстрацию полного MCP-флоу дня 20.')
        before=copy.deepcopy(self.store.get(self.session)['state'])
        with http_fixture(self.route_refinement_model()) as (url,model):
            result=self.agent(url).ask(self.session,'Какой маршрут выбирается для --task summary на день 20?')
        self.assertTrue(check_sources(result));self.assertEqual(before,result['task_state'])
        self.assertIn('`--task summary` вызывает GitHub и analysis без сохранения файла',result['answer'])
        self.assertEqual(1,len(result['validation']['route_audits']))
        audit=[b for e,b in model.calls if e=='generate' and 'proof_ids' in b['format']['properties']]
        self.assertEqual(1,len(audit));self.assertTrue(audit[0]['prompt'].startswith('TASK ROUTE EVIDENCE AUDIT'))
        data=json.loads(audit[0]['prompt'].split('\n\nOUTPUT JSON SCHEMA:\n',1)[0].rsplit('\nDATA:\n',1)[1])
        self.assertEqual(result['resolved_question'],data['question_context'])
        self.assertEqual(result,self.store.history(self.session)[-1]['response'])
        self.assertEqual(2,sum(e=='embed' for e,_ in model.calls))

    def test_filtered_docstring_tail_cannot_be_returned_even_with_positive_fixture(self):
        class TailModel(ScriptedModel):
            def respond(self,endpoint,body):
                result=super().respond(endpoint,body)
                if endpoint=='generate' and 'quote_ids' in body['format']['properties']:
                    result['response']=json.dumps({'status':'answered','quote_ids':['q4_7']})
                return result
        with http_fixture(TailModel()) as (url,model):
            result=self.agent(url).ask(self.session,'Что возвращает get_github_summary на день 18?')
        self.assertEqual('unknown',result['status']);self.assertEqual([],result['sources'])
        filtered=[r for t in result['validation']['fragment_filters'] for r in t['excluded']]
        self.assertTrue(any(r['text'].startswith('Args:') for r in filtered))
        self.assertFalse(any(e=='generate' and 'proof_ids' in b['format']['properties'] for e,b in model.calls))

    def test_first_collection_filters_real_unclosed_docstring_but_retains_exact_schedule_evidence(self):
        message = "Когда назначается первый сбор на день 18?"
        with http_fixture(self.first_collection_model()) as (url, model):
            result = self.agent(url).ask(self.session, message)
        self.assertTrue(check_sources(result))  # Protocol fixture only, not a live Qwen result.
        self.assertIn("первый сбор назначается сразу", result["answer"])
        self.assertNotIn('"""', result["answer"])
        filters = [row for trace in result["validation"]["fragment_filters"] for row in trace["excluded"]]
        actual = "\n".join((ROOT / "day-18-scheduled-mcp/server.py").read_text().splitlines()[9:12])
        bad = next(row for row in filters if row["text"] == actual)
        self.assertEqual("python_unclosed_string_or_delimiter", bad["reason"])
        self.assertNotIn(bad["quote_id"], result["retrieval"]["answer_quote_ids"])
        self.assertTrue(result["resolved_question"].endswith(message))
        self.assertEqual("18", result["retrieval"]["lesson_retrieval"]["lesson"])
        self.assertEqual(message, result["task_state"]["goal"]["value"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertEqual(result, self.store.history(self.session)[-1]["response"])

    def test_first_collection_filter_does_not_replace_missing_fact_or_negative_verdict(self):
        with http_fixture(self.first_collection_model(missing_schedule=True)) as (url, model):
            result = self.agent(url).ask(self.session, "Когда назначается первый сбор на день 18?")
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], result["sources"])
        self.assertFalse(result["validation"]["coverage_supported"])
        self.assertEqual(2, result["validation"]["attempts"])
        auditors = [b for e, b in model.calls if e == "generate" and "proof_ids" in b["format"]["properties"]]
        self.assertEqual(2, len(auditors))
        for body in auditors:
            data = json.loads(body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0].rsplit("\nDATA:\n", 1)[1])
            self.assertEqual(result["resolved_question"], data["question_context"])
            self.assertNotIn("первый сбор назначается сразу", json.dumps(data["proof_units"], ensure_ascii=False))

    def test_registry_draft_cleanup_keeps_complete_quotes_memory_and_final_audit(self):
        memory_command(self.store, self.session, "/goal", "Подготовить демонстрацию полного MCP-флоу дня 20.")
        memory_command(self.store, self.session, "/constraint", "Без VPS.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        with http_fixture(self.registry_draft_model()) as (url, model):
            result = self.agent(url).ask(self.session, "Вернёмся к нашей цели. Что делает mcp_registry.py?")
        self.assertTrue(check_sources(result))  # Protocol fixture only; live Qwen still required.
        self.assertEqual(before, result["task_state"])
        self.assertEqual("20", result["retrieval"]["lesson_retrieval"]["lesson"])
        self.assertEqual(1, result["validation"]["attempts"])
        self.assertEqual(2, len(result["quotes"]))
        self.assertIn("`mcp_registry.py` регистрирует серверы", result["answer"])
        self.assertIn("```text\ngithub.get_repository_info", result["answer"])
        self.assertNotIn("Из корня распакованного архива", result["answer"])
        trace = result["validation"]["selection_refinements"][0]
        self.assertIn("Incomplete source context", trace["initial_fragment_errors"][0])
        self.assertEqual(3, len(json.loads(trace["initial_raw_response"])["quote_ids"]))
        self.assertEqual(result["retrieval"]["answer_quote_ids"], json.loads(trace["raw_response"])["quote_ids"])
        auditors = [b for e, b in model.calls if e == "generate" and "proof_ids" in b["format"]["properties"]]
        self.assertEqual(1, len(auditors))
        data = json.loads(auditors[0]["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0].rsplit("\nDATA:\n", 1)[1])
        self.assertEqual(result["resolved_question"], data["question_context"])
        self.assertEqual(result, self.store.history(self.session)[-1]["response"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))

    def test_registry_draft_cleanup_cannot_hide_missing_requested_fact_or_negative_audit(self):
        memory_command(self.store, self.session, "/goal", "Подготовить демонстрацию полного MCP-флоу дня 20.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        with http_fixture(self.registry_draft_model(omit_registry=True)) as (url, model):
            result = self.agent(url).ask(self.session, "Вернёмся к нашей цели. Что делает mcp_registry.py?")
        self.assertEqual("unknown", result["status"])
        self.assertFalse(result["validation"]["coverage_supported"])
        self.assertEqual([], result["sources"])
        self.assertEqual(before, result["task_state"])
        self.assertEqual(2, result["validation"]["attempts"])
        self.assertEqual(2, len(result["validation"]["selection_refinements"]))
        auditors = [b for e, b in model.calls if e == "generate" and "proof_ids" in b["format"]["properties"]]
        self.assertEqual(2, len(auditors))  # One strict verdict per new candidate, no approval retry.
        for body in auditors:
            data = json.loads(body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0].rsplit("\nDATA:\n", 1)[1])
            self.assertEqual(result["resolved_question"], data["question_context"])
            self.assertNotIn("mcp_registry.py", json.dumps(data["proof_units"]))

    def test_refined_subset_is_exact_persisted_and_audited_with_full_current_question(self):
        memory_command(self.store, self.session, "/goal", "Подготовить демонстрацию полного MCP-флоу дня 20.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        message = "Какой маршрут выбирается для --task info на день 20?"
        with http_fixture(self.route_refinement_model()) as (url, model):
            result = self.agent(url).ask(self.session, message)
        self.assertTrue(check_sources(result))  # Scripted protocol test, not real Qwen quality.
        self.assertEqual(1, len(result["quotes"]))
        self.assertIn("`--task info` вызывает только GitHub", result["answer"])
        self.assertNotIn("```text", result["answer"])
        self.assertEqual(before, result["task_state"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertEqual(1, len(result["validation"]["selection_refinements"]))
        trace = result["validation"]["selection_refinements"][0]
        self.assertEqual(3, len(json.loads(trace["initial_raw_response"])["quote_ids"]))
        unit_trace = result["validation"]["source_unit_selections"][0]
        self.assertEqual(2, len(json.loads(unit_trace["raw_response"])["quote_ids"]))
        self.assertEqual(3, len(json.loads(unit_trace["expanded_response"])["quote_ids"]))
        self.assertEqual(1, len(json.loads(trace["raw_response"])["quote_ids"]))
        auditors = [b for e, b in model.calls if e == "generate" and "proof_ids" in b["format"]["properties"]]
        data = json.loads(auditors[0]["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0].rsplit("\nDATA:\n", 1)[1])
        self.assertEqual(result["resolved_question"], data["question_context"])
        self.assertEqual(result, self.store.history(self.session)[-1]["response"])

    def test_refiner_omission_does_not_override_negative_coverage_or_restore_initial_answer(self):
        message = "Какой маршрут выбирается для --task info на день 20?"
        with http_fixture(self.route_refinement_model(omit_requested_mapping=True)) as (url, model):
            result = self.agent(url).ask(self.session, message)
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], result["sources"])
        self.assertFalse(result["validation"]["coverage_supported"])
        self.assertEqual(2, result["validation"]["attempts"])
        self.assertEqual(2, len(result["validation"]["selection_refinements"]))
        auditors = [b for e, b in model.calls if e == "generate" and "proof_ids" in b["format"]["properties"]]
        self.assertEqual(2, len(auditors))  # One independent audit per new candidate, no approval retry.
        for body in auditors:
            data = json.loads(body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0].rsplit("\nDATA:\n", 1)[1])
            self.assertEqual(result["resolved_question"], data["question_context"])
            self.assertNotIn("--task info", json.dumps(data["proof_units"]))

    def test_refiner_token_exhaustion_is_refused_by_unchanged_day24_validator(self):
        with http_fixture(self.route_refinement_model(truncate=True)) as (url, model):
            result = self.agent(url).ask(self.session, "Какой маршрут выбирается для --task info на день 20?")
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], result["sources"])
        self.assertTrue(all("token limit" in e["message"] for e in result["validation"]["errors"]))
        self.assertFalse(any(e == "generate" and "proof_ids" in b["format"]["properties"] for e, b in model.calls))
        self.assertTrue(all(t["ollama"]["done_reason"] == "length" for t in result["validation"]["selection_refinements"]))

    def fragment_model(self, repair):
        class FragmentModel(ScriptedModel):
            selections = 0
            def respond(self, endpoint, body):
                result = super().respond(endpoint, body)
                if body.get("prompt", "").startswith("SELECTION REFINEMENT"):
                    # This fixture tests command-introduction repair, not ranking:
                    # preserve the validated intro/command pair in reading order.
                    ids = body["format"]["properties"]["quote_ids"]["items"]["enum"]
                    result["response"] = json.dumps({"status": "answered", "quote_ids": ids})
                    return result
                if endpoint == "generate" and "quote_ids" in body["format"]["properties"]:
                    self.selections += 1
                    data = json.loads(body["prompt"].split("\n\nOUTPUT JSON SCHEMA:\n", 1)[0].rsplit("\nDATA:\n", 1)[1])
                    chunk = next(c for c in data["chunks"] if c["source"] == "day-18-scheduled-mcp/README.ru.md")
                    command = next(q["quote_id"] for q in chunk["quotes"] if q["text"].startswith("```bash") and
                                   q["text"].strip().splitlines()[1] == ".venv/bin/python day-18-scheduled-mcp/worker.py")
                    intro1 = next(q["quote_id"] for q in chunk["quotes"] if q["text"].startswith("В терминале 1"))
                    intro2 = next(q["quote_id"] for q in chunk["quotes"] if q["text"].startswith("В терминале 2"))
                    ids = [intro1, command] if repair and self.selections > 1 else [command, intro2]
                    result["response"] = json.dumps({"status": "answered", "quote_ids": ids})
                return result
        return FragmentModel()

    def test_orphaned_process_setup_is_refused_even_with_positive_fixture_auditor(self):
        with http_fixture(self.fragment_model(False)) as (url, model):
            result = self.agent(url).ask(self.session, "Какой процесс запустить отдельно и какой командой на день 18?")
        self.assertEqual("unknown", result["status"])
        self.assertEqual("evidence_validation_failed", result["reason"])
        self.assertEqual([], result["sources"])
        self.assertEqual(2, result["validation"]["attempts"])
        self.assertTrue(all("Incomplete source context" in e["message"] for e in result["validation"]["errors"]))
        self.assertFalse(any(e == "generate" and "proof_ids" in b["format"]["properties"] for e, b in model.calls))
        self.assertEqual(result, self.store.history(self.session)[-1]["response"])

    def test_orphaned_process_setup_repair_uses_correct_intro_and_preserves_memory(self):
        memory_command(self.store, self.session, "/goal", "Проверить планировщик дня 18.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        with http_fixture(self.fragment_model(True)) as (url, model):
            result = self.agent(url).ask(self.session, "Какой процесс запустить отдельно и какой командой на день 18?")
        self.assertTrue(check_sources(result))  # Scripted repair, not a live-model quality claim.
        self.assertEqual(2, result["validation"]["attempts"])
        self.assertIn("Incomplete source context", result["validation"]["errors"][0]["message"])
        self.assertIn("В терминале 1", result["answer"])
        self.assertIn("day-18-scheduled-mcp/worker.py", result["answer"])
        self.assertNotIn("В терминале 2", result["answer"])
        self.assertNotIn("GROQ_API_KEY", result["answer"])
        self.assertEqual(before, result["task_state"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))

    def test_real_http_sqlite_retrieval_and_exact_sources(self):
        with http_fixture() as (url, model):
            result = self.agent(url).ask(self.session, "Какие поля сохраняет worker на день 18?")
        self.assertTrue(check_sources(result))
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertIn("Источники / Sources:", render_response(result))
        self.assertEqual(result, self.store.history(self.session)[0]["response"])

    def test_reported_unexpanded_followup_keeps_new_topic_after_restart_and_fresh_search(self):
        memory_command(self.store, self.session, "/goal", "Подготовить проверку планировщика дня 18.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        with http_fixture() as (url, _):
            first = self.agent(url).ask(self.session, "Какие MCP-серверы участвуют в оркестрации на день 20?")
        self.assertTrue(check_sources(first))
        self.store.close()
        self.store = ChatStore(Path(self.temp.name) / "chats.db")
        message = "А в каком порядке вызываются инструменты для полного отчёта?"
        payload = {"resolved_question": message, "needs_clarification": False, "updates": []}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, model):
            result = self.agent(url).ask(self.session, message)
        self.assertTrue(check_sources(result))  # Scripted fixture, not a live semantic verdict.
        self.assertEqual(before, result["task_state"])
        self.assertEqual(message + " (контекст: день 20)", result["resolved_question"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertTrue(all(s["source"].startswith("day-20-") for s in result["sources"]))
        self.assertEqual(result, self.store.history(self.session)[-1]["response"])

    def test_reported_goal_return_uses_persistent_goal_after_detour_and_rejects_memory_rewrite(self):
        memory_command(self.store, self.session, "/goal", "Подготовить проверку планировщика дня 18.")
        memory_command(self.store, self.session, "/constraint", "Worker должен работать отдельно от чата.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        with http_fixture() as (url, _):
            self.agent(url, history_turns=1).ask(self.session, "Какие MCP-серверы участвуют в оркестрации на день 20?")
        self.store.close()
        self.store = ChatStore(Path(self.temp.name) / "chats.db")
        message = "Вернёмся к нашей цели. Какой процесс нужно запустить отдельно от чата и какой командой?"
        payload = {"resolved_question": "Какой процесс нужно запустить отдельно от чата и какой командой?",
                   "needs_clarification": False,
                   "updates": [{"kind": "constraints", "key": "78977b5c5ca8",
                                "value": "Worker должен работать отдельно от чата.",
                                "evidence": "Worker должен работать отдельно от чата."}]}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, model):
            result = self.agent(url, history_turns=1).ask(self.session, message)
        self.assertEqual(payload["resolved_question"] + " (контекст цели: день 18)", result["resolved_question"])
        self.assertEqual(before, result["task_state"])
        self.assertEqual([], result["conversation"]["warnings"])
        self.assertEqual("78977b5c5ca8", result["conversation"]["memory_noops"][0]["key"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertTrue(check_sources(result))  # Scripted fixture, not live Qwen.
        self.assertTrue(all(s["source"].startswith("day-18-") for s in result["sources"]))
        self.assertEqual(result, self.store.history(self.session)[-1]["response"])

    def test_early_goal_reaches_model_after_history_window_rolls_over(self):
        with http_fixture() as (url, model):
            agent = self.agent(url, history_turns=1)
            agent.ask(self.session, "Цель: Проверить расписание.\nКакой процесс работает на день 18?")
            agent.ask(self.session, "Какие поля сохраняются на день 18?")
            result = agent.ask(self.session, "Какой у него интервал?")
        self.assertEqual("Проверить расписание.", public_state(result["task_state"])["goal"])
        self.assertEqual(1, len(result["conversation"]["recent_history"]))
        selectors = [b["prompt"] for e, b in model.calls if e == "generate" and "quote_ids" in b["format"]["properties"]
                     and not b["prompt"].startswith("SELECTION REFINEMENT")]
        self.assertIn("Проверить расписание.", selectors[-1])
        self.assertTrue(check_sources(result))

    def test_below_threshold_runs_search_but_not_evidence_generation(self):
        with http_fixture() as (url, model):
            agent = self.agent(url)
            agent.settings = Settings(40, 20, 1.0, "fixed", "heuristic")
            result = agent.ask(self.session, "Какие поля сохраняются на день 18?")
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], result["sources"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertEqual(1, sum(e == "generate" for e, _ in model.calls))  # planner only
        self.assertIn("No confirmed sources", render_response(result))

    def test_invalid_planner_still_retrieves_and_keeps_existing_goal(self):
        memory_command(self.store, self.session, "/goal", "Prepare scheduler demo")
        with http_fixture(ChangedModel("resolved_question", "not JSON")) as (url, model):
            result = self.agent(url).ask(self.session, "Какие поля сохраняются на день 18?")
        self.assertTrue(result["conversation"]["warnings"])
        self.assertTrue(check_sources(result))
        self.assertEqual("Prepare scheduler demo", public_state(result["task_state"])["goal"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))

    def test_ambiguous_reference_never_reuses_old_citations(self):
        payload = {"resolved_question": "А где это?", "needs_clarification": True, "updates": []}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, model):
            result = self.agent(url).ask(self.session, "А где это?")
        self.assertEqual("ambiguous_reference", result["reason"])
        self.assertEqual([], result["sources"])
        self.assertIsNone(result["task_state"]["goal"])
        self.assertEqual(1, sum(e == "embed" for e, _ in model.calls))

    def test_reported_live_false_ambiguity_and_question_memory(self):
        message = "Какой процесс выполняет фоновые задания на день 18?"
        # Exact planner response from the user's first-chat.json, not a newly
        # invented model success. Evidence generation is still an HTTP fixture.
        payload = {"resolved_question": message, "needs_clarification": True,
                   "updates": [{"kind": "clarifications", "key": "", "value": message, "evidence": message}]}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, model):
            result = self.agent(url).ask(self.session, message)
        self.assertTrue(check_sources(result))
        self.assertTrue(result["conversation"]["model_needs_clarification"])
        self.assertFalse(result["conversation"]["effective_needs_clarification"])
        self.assertEqual({}, result["task_state"]["clarifications"])
        self.assertEqual(message, public_state(result["task_state"])["goal"])
        self.assertTrue(any(e == "generate" and "quote_ids" in b["format"]["properties"] for e, b in model.calls))

    def test_reported_live_additional_clarification_preserves_previous_on_restart(self):
        memory_command(self.store, self.session, "/goal", "Подготовить проверку планировщика дня 18.")
        memory_command(self.store, self.session, "/constraint", "Используем SQLite.")
        memory_command(self.store, self.session, "/constraint", "Worker должен работать отдельно от чата.")
        memory_command(self.store, self.session, "/clarify", "Проверяем локальный запуск.")
        memory_command(self.store, self.session, "/term", "снимок=сохранённые данные GitHub")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        message = "Уточнение: Первый сбор проверяем вручную.\nКакие поля входят в снимок, который сохраняет worker на день 18?"
        payload = {"resolved_question": message.split("\n")[1], "needs_clarification": False,
                   "updates": [{"kind": "clarifications", "key": "f561dcbbee5b",
                                "value": "Первый сбор проверяем вручную.", "evidence": "Первый сбор проверяем вручную."}]}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, model):
            result = self.agent(url).ask(self.session, message)
        self.assertTrue(check_sources(result))
        self.assertEqual([], result["conversation"]["warnings"])
        self.assertEqual("Первый сбор проверяем вручную.", result["conversation"]["explicit_declarations"][0]["value"])
        self.assertEqual("f561dcbbee5b", result["conversation"]["declaration_proposals_ignored"][0]["key"])
        self.assertEqual(2, len(result["task_state"]["clarifications"]))
        for field in ("goal", "constraints", "terms"):
            self.assertEqual(before[field], result["task_state"][field])
        self.assertEqual(before["clarifications"]["f561dcbbee5b"], result["task_state"]["clarifications"]["f561dcbbee5b"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        path = Path(self.temp.name) / "chats.db"
        self.store.close()
        self.store = ChatStore(path)
        self.assertEqual(result["task_state"], self.store.get(self.session)["state"])
        self.assertEqual(result, self.store.history(self.session)[0]["response"])

    def test_reported_live_followup_resolves_and_rejects_historical_memory_evidence(self):
        memory_command(self.store, self.session, "/goal", "Подготовить проверку планировщика дня 18.")
        memory_command(self.store, self.session, "/clarify", "Первый сбор проверяем вручную.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        payload = {"resolved_question": "А где хранятся снимки, которые сохраняет worker на день 18?",
                   "needs_clarification": False,
                   "updates": [{"kind": "clarifications", "key": "6f7382f038ef",
                     "value": "Первый сбор проверяем вручную. А где хранятся снимки, которые сохраняет worker на день 18?",
                     "evidence": "Первый сбор проверяем вручную."}]}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, model):
            result = self.agent(url).ask(self.session, "А где это хранится?")
        self.assertEqual(payload["resolved_question"], result["resolved_question"])
        self.assertEqual(before, result["task_state"])
        self.assertIn("Memory must be an exact substring of current user evidence", result["conversation"]["warnings"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertTrue(check_sources(result))  # Scripted evidence calls, not a live model verdict.
        planners = [b["prompt"] for e, b in model.calls if e == "generate" and "resolved_question" in b["format"]["properties"]]
        auditors = [b["prompt"] for e, b in model.calls if e == "generate" and "proof_ids" in b["format"]["properties"]]
        self.assertIn("return updates=[]", planners[0])
        self.assertIn("only when the current question explicitly requests", auditors[0])
        self.assertIn("NOT satisfied by a bare file name", auditors[0])

    def test_storage_scope_prompt_never_overrides_negative_coverage(self):
        payload = {"reason": "Предоставленные доказательства указывают, что снимки сохраняются в SQLite, но конкретный путь к файлу SQLite не указан.",
                   "proof_ids": [], "covered": False}
        with http_fixture(ChangedModel("covered", payload)) as (url, model):
            result = self.agent(url).ask(self.session, "Где хранятся снимки на день 18? Укажи полный путь.")
        self.assertEqual("unknown", result["status"])
        self.assertEqual("evidence_validation_failed", result["reason"])
        self.assertFalse(result["validation"]["coverage_supported"])
        self.assertEqual([], result["sources"])
        self.assertEqual(2, result["validation"]["attempts"])
        self.assertTrue(all(not c["covered"] for c in result["validation"]["coverage_verdict"]["checks"]))

    def test_reported_repeated_followup_after_refusal_reuses_resolution_and_searches_fresh(self):
        message = "А где это хранится?"
        resolved = "А где хранятся снимки, которые сохраняет worker на день 18?"
        memory_command(self.store, self.session, "/goal", "Подготовить проверку планировщика дня 18.")
        before = copy.deepcopy(self.store.get(self.session)["state"])
        class ResolvedButRejected(ChangedModel):
            def respond(self, endpoint, body):
                result = super().respond(endpoint, body)
                if endpoint == "generate" and "covered" in body["format"]["properties"]:
                    result["response"] = json.dumps({"reason": "Full path missing", "proof_ids": [], "covered": False})
                return result
        payload = {"resolved_question": resolved, "needs_clarification": False, "updates": []}
        with http_fixture(ResolvedButRejected("resolved_question", payload)) as (url, _):
            first = self.agent(url).ask(self.session, message)
        self.assertEqual("evidence_validation_failed", first["reason"])
        self.assertEqual([], first["sources"])
        # Exact planner output from the user's followup-v3.json.
        ambiguous_payload = {"resolved_question": message, "needs_clarification": True, "updates": []}
        path = Path(self.temp.name) / "chats.db"
        self.store.close()
        self.store = ChatStore(path)
        with http_fixture(ChangedModel("resolved_question", ambiguous_payload)) as (url, model):
            result = self.agent(url).ask(self.session, message)
        self.assertEqual(resolved, result["resolved_question"])
        self.assertTrue(result["conversation"]["model_needs_clarification"])
        self.assertFalse(result["conversation"]["effective_needs_clarification"])
        self.assertIn("resolution_reused", result["conversation"])
        self.assertEqual(before, result["task_state"])
        self.assertEqual(2, sum(e == "embed" for e, _ in model.calls))
        self.assertTrue(check_sources(result))  # Fresh scripted selector/auditor.

    def test_false_ambiguity_override_still_requires_source_evidence(self):
        message = "Какие секретные пароли сохранены на день 18?"
        class NoEvidence(ChangedModel):
            def respond(self, endpoint, body):
                result = super().respond(endpoint, body)
                if endpoint == "generate" and "quote_ids" in body["format"]["properties"]:
                    result["response"] = json.dumps({"status": "unknown", "quote_ids": []})
                return result
        payload = {"resolved_question": message, "needs_clarification": True, "updates": []}
        with http_fixture(NoEvidence("resolved_question", payload)) as (url, _):
            result = self.agent(url).ask(self.session, message)
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], result["sources"])
        self.assertEqual("insufficient_context", result["reason"])

    def test_elliptical_followup_without_pronoun_can_still_require_clarification(self):
        message = "А допустимый интервал?"
        payload = {"resolved_question": message, "needs_clarification": True, "updates": []}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, _):
            result = self.agent(url).ask(self.session, message)
        self.assertEqual("ambiguous_reference", result["reason"])

    def test_first_question_goal_fallback_does_not_replace_existing_goal(self):
        memory_command(self.store, self.session, "/goal", "Подготовить демонстрацию.")
        message = "Какой процесс выполняет фоновые задания на день 18?"
        payload = {"resolved_question": message, "needs_clarification": False, "updates": []}
        with http_fixture(ChangedModel("resolved_question", payload)) as (url, _):
            result = self.agent(url).ask(self.session, message)
        self.assertEqual("Подготовить демонстрацию.", public_state(result["task_state"])["goal"])

    def test_forged_quote_ids_block_publication(self):
        with http_fixture(ChangedModel("quote_ids", {"status": "answered", "quote_ids": ["q99999_1"]})) as (url, _):
            result = self.agent(url).ask(self.session, "Какие поля сохраняются на день 18?")
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], result["sources"])
        self.assertEqual("evidence_validation_failed", result["reason"])

    def test_negative_coverage_strict_refuses_diagnostic_stays_flagged(self):
        negative = {"reason": "Missing requested facts", "proof_ids": [], "covered": False}
        with http_fixture(ChangedModel("proof_ids", negative)) as (url, _):
            strict = self.agent(url).ask(self.session, "Какие поля сохраняются на день 18?")
            diagnostic = self.agent(url, coverage_policy="diagnostic").ask(self.session, "Какие поля сохраняются на день 18?")
        self.assertEqual("unknown", strict["status"])
        self.assertEqual("answered", diagnostic["status"])
        self.assertFalse(diagnostic["validation"]["coverage_supported"])
        self.assertTrue(diagnostic["validation"]["manual_review_required"])
        self.assertIn("manual review", render_response(diagnostic))

    def test_embedding_mismatch_records_technical_error_and_user_message(self):
        with http_fixture() as (url, _):
            agent = self.agent(url)
            agent.provider.model = "wrong-model"
            with self.assertRaisesRegex(ValueError, "model"):
                agent.ask(self.session, "Какие поля сохраняются на день 18?")
        row = self.store.history(self.session)[0]
        self.assertEqual("error", row["status"])
        self.assertIsNone(row["response"])
        self.assertIn("day", row["error"].casefold())

    def test_transport_error_does_not_become_answer(self):
        with http_fixture() as (url, _):
            pass  # server is deliberately closed
        with self.assertRaises(RuntimeError):
            self.agent(url).ask(self.session, "Какие поля сохраняются на день 18?")
        self.assertEqual("error", self.store.history(self.session)[0]["status"])

    def test_cli_ask_resume_export_and_interactive_commands(self):
        chat_db = str(Path(self.temp.name) / "cli.db")
        export = Path(self.temp.name) / "export.json"
        output = Path(self.temp.name) / "answer.json"
        with http_fixture() as (url, _):
            base = [sys.executable, str(HERE / "main.py"), "--db", str(self.index_path), "--chat-db", chat_db,
                    "--url", url, "--model", "fixture-hash-256", "--answer-model", "scripted-fixture",
                    "--candidate-k", "40", "--final-k", "20", "--min-similarity", "0"]
            first = subprocess.run(base + ["ask", "Цель: Демонстрация.\nКакие поля сохраняются на день 18?", "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(0, first.returncode, first.stderr)
            session = json.loads(output.read_text())["session_id"]
            second = subprocess.run(base + ["chat", "--session", session],
                input="/state\n/term snapshot=data\nКакие инструменты есть на день 18?\n/export " + str(export) + "\n/quit\n", capture_output=True, text=True)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertIn("Демонстрация.", second.stdout)
            payload = json.loads(export.read_text())
            self.assertEqual(2, len(payload["turns"]))
            self.assertEqual("data", public_state(payload["session"]["state"])["terms"]["snapshot"])

    def test_cli_output_collision_rejected_before_question_and_network(self):
        before_state = self.store.export(self.session)
        index_before = self.index_path.read_bytes()
        with http_fixture() as (url, model):
            base = [sys.executable, str(HERE / "main.py"), "--db", str(self.index_path),
                    "--chat-db", str(self.store.path), "--url", url]
            for command in (["ask", "Which process on day 18?", "--session", self.session],
                            ["export", self.session], ["evaluate"]):
                for target in (self.store.path, self.index_path, Path(str(self.store.path) + "-wal")):
                    with self.subTest(command=command[0], target=target):
                        result = subprocess.run(base + command + ["--output", str(target)], capture_output=True, text=True)
                        self.assertEqual(2, result.returncode, result.stderr)
                        self.assertIn("JSON output cannot replace", result.stderr)
            self.assertEqual([], model.calls)
        self.assertEqual(before_state, self.store.export(self.session))
        self.assertEqual(index_before, self.index_path.read_bytes())

    def test_interactive_export_rejects_databases_and_continues_session(self):
        output = Path(self.temp.name) / "safe.json"
        with http_fixture() as (url, model):
            result = subprocess.run([sys.executable, str(HERE / "main.py"),
                "--db", str(self.index_path), "--chat-db", str(self.store.path),
                "--url", url, "--model", "fixture-hash-256", "chat", "--session", self.session],
                input=f"/export {self.store.path}\n/export {self.index_path}\n/state\n/export {output}\n/quit\n",
                capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(2, result.stderr.count("JSON output cannot replace"))
            self.assertIn(f"Saved: {output}", result.stdout)
            self.assertEqual([], model.calls)
        self.assertEqual(self.store.export(self.session), json.loads(output.read_text()))

    def test_same_database_hardlink_is_rejected_before_chat_schema_mutation(self):
        alias = Path(self.temp.name) / "index-alias.db"
        os.link(self.index_path, alias)
        before = self.index_path.read_bytes()
        result = subprocess.run([sys.executable, str(HERE / "main.py"), "--db", str(self.index_path),
            "--chat-db", str(alias), "sessions"], capture_output=True, text=True)
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn("different database files", result.stderr)
        self.assertEqual(before, self.index_path.read_bytes())

    def test_cli_unavailable_ollama_keeps_failed_question_and_sources_block(self):
        import socket
        # Reserve a local port without listening: deterministic refused connection.
        with socket.socket() as port:
            port.bind(("127.0.0.1", 0))
            result = subprocess.run([sys.executable, str(HERE / "main.py"),
                "--db", str(self.index_path), "--chat-db", str(self.store.path),
                "--url", f"http://127.0.0.1:{port.getsockname()[1]}", "--timeout", "2",
                "--model", "fixture-hash-256", "ask", "Which process on day 18?",
                "--session", self.session], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("Источники / Sources:", result.stderr)
        self.assertIn("No confirmed sources", result.stderr)
        history = self.store.history(self.session)
        self.assertEqual(1, len(history))
        self.assertEqual("error", history[0]["status"])
        self.assertIsNone(history[0]["response"])
        self.assertIn("Ollama", history[0]["error"])
        self.assertEqual(empty_state(), self.store.get(self.session)["state"])
        self.assertEqual(0, self.store.recover(self.session))

    def test_cli_history_requires_neither_ollama_nor_index(self):
        cmd = [sys.executable, str(HERE / "main.py"), "--chat-db", str(self.store.path),
               "--db", str(Path(self.temp.name) / "absent.db"), "history", self.session]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], json.loads(result.stdout))

    def test_stale_index_rejected_before_model_call(self):
        stale = Path(self.temp.name) / "stale.db"
        stale.write_bytes(self.index_path.read_bytes())
        kb = KnowledgeBase(stale)
        with kb.db:
            kb.db.execute("UPDATE indexes SET revision='old-source'")
        kb.close()
        with http_fixture() as (url, model):
            result = subprocess.run([sys.executable, str(HERE / "main.py"), "--db", str(stale),
                "--chat-db", str(Path(self.temp.name) / "stale-chat.db"), "--url", url,
                "--model", "fixture-hash-256", "ask", "Question"], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("stale", result.stderr)
        self.assertEqual([], model.calls)

    def test_empty_input_and_shared_database_are_rejected(self):
        with http_fixture() as (url, model):
            with self.assertRaisesRegex(ValueError, "1–4000"):
                self.agent(url).ask(self.session, " ")
        self.assertEqual([], model.calls)
        self.assertEqual([], self.store.history(self.session))
        result = subprocess.run([sys.executable, str(HERE / "main.py"), "--db", str(self.index_path),
            "--chat-db", str(self.index_path), "sessions"], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("different", result.stderr)

    def test_explicit_goal_change_is_persisted_and_injected(self):
        memory_command(self.store, self.session, "/goal", "Проверить планировщик.")
        with http_fixture() as (url, model):
            result = self.agent(url).ask(self.session,
                "Цель: Изучить серверы MCP.\nКакие серверы зарегистрированы на день 20?")
        self.assertEqual("Изучить серверы MCP.", public_state(result["task_state"])["goal"])
        self.assertTrue(check_sources(result))
        selectors = [b["prompt"] for e, b in model.calls if e == "generate" and "quote_ids" in b["format"]["properties"]
                     and not b["prompt"].startswith("SELECTION REFINEMENT")]
        self.assertIn("Изучить серверы MCP.", selectors[-1])

    def test_two_twelve_turn_scenarios_include_store_reopens(self):
        report = run_demo(Path(self.temp.name) / "long.json")
        self.assertTrue(report["summary"]["all_checks_pass"], str([
            (d["scenario"], d["checks"]) for d in report["details"]]))
        self.assertEqual(48, report["fixture"]["embedding_calls"])
        self.assertEqual(24, report["summary"]["user_turns"])
        self.assertEqual(6, report["summary"]["restart_after_turn"])
        self.assertEqual("store_reopen", report["summary"]["restart_kind"])
        self.assertFalse(report["summary"]["model_quality_verified"])

    def test_scenarios_have_required_length(self):
        scenarios = load_scenarios(HERE / "scenarios.json")
        self.assertEqual([12, 12], [len(s["turns"]) for s in scenarios])

    def test_failed_retries_keep_latest_topic_and_next_question_runs_fresh_search(self):
        memory_command(self.store, self.session, "/goal", "Проверить день 18.")
        with http_fixture() as (url, model):
            agent = self.agent(url)
            first = agent.ask(self.session, "Какие серверы зарегистрированы на день 20?")
            for _ in range(6):
                turn, current = self.store.begin(self.session, "Retry failed")
                self.store.finish(self.session, turn, current["version"], current["state"], error="network")
            second = agent.ask(self.session, "А какие у него инструменты?")
        self.assertIn("20", second["resolved_question"])
        self.assertEqual(4, sum(endpoint == "embed" for endpoint, _ in model.calls))
        self.assertNotEqual(first["retrieval_trace"]["request_id"], second["retrieval_trace"]["request_id"])
        self.assertEqual(8, len(self.store.history(self.session)))
        self.assertEqual("Проверить день 18.", public_state(second["task_state"])["goal"])

    def test_first_success_after_network_failure_initializes_goal(self):
        turn, current = self.store.begin(self.session, "Network failed before planning")
        self.store.finish(self.session, turn, current["version"], current["state"], error="network")
        message = "Какие поля сохраняет worker на день 18?"
        with http_fixture() as (url, _):
            result = self.agent(url).ask(self.session, message)
        self.assertEqual(message, public_state(result["task_state"])["goal"])

    def test_long_initial_request_is_not_silently_truncated_into_a_goal(self):
        with http_fixture() as (url, _):
            message = "Какие поля сохраняет worker на день 18? " + "Подробности запроса. " * 35
            result = self.agent(url).ask(self.session, message)
        self.assertIsNone(result["task_state"]["goal"])
        self.assertTrue(any("1–600" in warning for warning in result["conversation"]["warnings"]))
        self.assertEqual(message, self.store.history(self.session)[0]["question"])

    def test_failure_to_save_a_transport_error_does_not_claim_successful_persistence(self):
        with http_fixture() as (url, _):
            pass
        with patch.object(self.store, "finish", side_effect=RuntimeError("disk unavailable")):
            with self.assertRaisesRegex(RuntimeError, "failure could not be saved"):
                self.agent(url).ask(self.session, "Какие поля сохраняет worker на день 18?")
        self.assertEqual("pending", self.store.history(self.session)[0]["status"])

    def test_empty_fresh_retrieval_is_traced_without_inventing_sources(self):
        from evaluate25 import check_retrieval
        with http_fixture() as (url, _), patch.object(self.kb, "search", return_value=[]):
            result = self.agent(url).ask(self.session, "Какие поля сохраняет worker на день 18?")
        self.assertEqual("unknown", result["status"])
        self.assertEqual([], result["sources"])
        self.assertTrue(check_retrieval(result, set()))
        self.assertTrue(all(row["hits"] == 0 for row in result["retrieval_trace"]["search_calls"]))
        seen = set()
        self.assertTrue(check_retrieval(result, seen))
        self.assertFalse(check_retrieval(result, seen))

    def test_checkpoint_resume_skips_completed_turns_and_rejects_changed_configuration(self):
        from evaluate25 import evaluate
        checkpoint = Path(self.temp.name) / "checkpoint.json"
        def save(report):
            write_json(checkpoint, report)
            if report["summary"]["user_turns"] == 6:
                raise KeyboardInterrupt
        with http_fixture() as (url, model):
            agent = self.agent(url)
            with self.assertRaises(KeyboardInterrupt):
                evaluate(agent, HERE / "scenarios.json", "scripted-http-fixture", checkpoint=save)
            partial = json.loads(checkpoint.read_text())
            self.assertEqual("running", partial["run_status"])
            self.assertFalse(partial["summary"]["all_checks_pass"])
            self.assertEqual(12, sum(e == "embed" for e, _ in model.calls))
            # The process may stop after DB commit but before saving its report.
            partial["details"][0]["turns"].pop()
            report = evaluate(agent, HERE / "scenarios.json", "scripted-http-fixture", resume_report=partial)
            self.assertTrue(report["summary"]["all_checks_pass"])
            self.assertTrue(report["details"][0]["turns"][5]["checkpoint_reconciled_from_history"])
            self.assertEqual(48, sum(e == "embed" for e, _ in model.calls))
            with self.assertRaisesRegex(ValueError, "configuration differ"):
                evaluate(agent, HERE / "scenarios.json", "scripted-http-fixture", resume_report=partial,
                         configuration={"model": "different"})
            calls = len(model.calls)
            report["details"][0]["turns"][0]["checks"] = {"invented": False}
            repeated = evaluate(agent, HERE / "scenarios.json", "scripted-http-fixture", resume_report=report)
            self.assertTrue(repeated["summary"]["all_checks_pass"])
            self.assertEqual(calls, len(model.calls))
            bad = copy.deepcopy(report)
            bad["details"][0]["turns"][0]["result"]["answer"] = "Forged report answer"
            with self.assertRaisesRegex(ValueError, "differs from persistent"):
                evaluate(agent, HERE / "scenarios.json", "scripted-http-fixture", resume_report=bad)

    def test_cli_long_scenarios_use_24_independent_processes_and_resume_without_network(self):
        output = Path(self.temp.name) / "process-report.json"
        chat_db = Path(self.temp.name) / "process-chat.db"
        with http_fixture() as (url, model):
            base = [sys.executable, str(HERE / "main.py"), "--db", str(self.index_path), "--chat-db", str(chat_db),
                    "--url", url, "--model", "fixture-hash-256", "--answer-model", "scripted-fixture",
                    "--candidate-k", "40", "--final-k", "20", "--min-similarity", "0",
                    "evaluate", "--process-per-turn", "--output", str(output)]
            completed = subprocess.run(base, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, completed.returncode, completed.stderr)
            report = json.loads(output.read_text())
            pids = [row["result"]["retrieval_trace"]["process_id"] for d in report["details"] for row in d["turns"]]
            self.assertEqual(24, len(set(pids)))
            self.assertNotIn(os.getpid(), pids)
            self.assertEqual("process_per_turn", report["summary"]["restart_kind"])
            self.assertEqual(48, sum(e == "embed" for e, _ in model.calls))
            before = len(model.calls)
            resumed = subprocess.run(base + ["--resume"], capture_output=True, text=True, timeout=15)
            self.assertEqual(0, resumed.returncode, resumed.stderr)
            self.assertEqual(before, len(model.calls))

    def test_source_report_rejects_tampered_lines_quote_claim_or_added_answer(self):
        with http_fixture() as (url, _):
            result = self.agent(url).ask(self.session, "Какие поля сохраняет worker на день 18?")
        self.assertTrue(check_sources(result))
        for target in ("lines", "quote", "claim", "answer", "cosine", "source"):
            bad = copy.deepcopy(result)
            if target == "lines": bad["quotes"][0]["start_line"] += 1
            elif target == "quote": bad["quotes"][0]["quote"] = "Invented unsupported source quotation"
            elif target == "claim": bad["claims"][0]["text"] = "Invented claim"
            elif target == "answer": bad["answer"] += "\nInvented uncited answer"
            elif target == "cosine": bad["sources"][0]["cosine"] = 999.0
            else: bad["sources"][0]["source"] = "invented.py"
            with self.subTest(target=target):
                self.assertFalse(check_sources(bad))

    def test_corrupt_chat_database_is_a_cli_error_with_sources_and_no_traceback(self):
        broken = Path(self.temp.name) / "corrupt.db"
        broken.write_text("not a database")
        completed = subprocess.run([sys.executable, str(HERE / "main.py"), "--chat-db", str(broken), "sessions"],
                                   capture_output=True, text=True)
        self.assertEqual(2, completed.returncode)
        self.assertIn("Источники / Sources:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)



class LongScenarioRegressionTests(unittest.TestCase):
    class Provider:
        def __init__(self, *payloads):
            self.payloads = list(payloads)
            self.prompts = []
        def structured(self, prompt, schema):
            self.prompts.append(prompt)
            item = self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]
            return json.dumps(item, ensure_ascii=False)

    @staticmethod
    def payload(question, ambiguous=False, updates=None):
        return {"resolved_question": question, "needs_clarification": ambiguous,
                "updates": updates or []}

    def test_reported_truncated_goal_and_constraint_are_stored_as_literal_lines(self):
        message = "Цель: Подготовить демонстрацию полного MCP-флоу дня 20.\nОграничение: Без VPS.\nКакие серверы на день 20?"
        proposals = [
            {"kind": "goal", "key": "", "value": "Подготовить демонстрацию полного MCP-флоу дня 20", "evidence": message.splitlines()[0]},
            {"kind": "constraints", "key": "", "value": "Без VPS", "evidence": message.splitlines()[1]}]
        _, state, ambiguous, trace = plan(self.Provider(self.payload("Какие серверы на день 20?", updates=proposals)), message, empty_state(), [], 1)
        self.assertEqual("Подготовить демонстрацию полного MCP-флоу дня 20.", state["goal"]["value"])
        self.assertEqual(["Без VPS."], list(public_state(state)["constraints"].values()))
        self.assertFalse(ambiguous)
        self.assertEqual([], trace["warnings"])

    def test_explicit_clarification_survives_model_paraphrase_without_accepting_it(self):
        message = "Уточнение: Нужен полный маршрут report.\nКакой порядок на день 20?"
        proposal = {"kind": "clarifications", "key": "полный маршрут report", "value": "полный MCP-флоу дня 20", "evidence": message.splitlines()[0]}
        _, state, _, trace = plan(self.Provider(self.payload("Какой порядок на день 20?", updates=[proposal])), message, empty_state(), [], 1)
        self.assertEqual(["Нужен полный маршрут report."], list(public_state(state)["clarifications"].values()))
        self.assertNotIn("полный MCP-флоу дня 20", json.dumps(state, ensure_ascii=False))
        self.assertEqual([], trace["warnings"])

    def test_literal_labels_work_when_model_omits_updates_or_is_malformed(self):
        message = "Term: count=a=b\nConstraint: Keep punctuation!\nWhich field on day 18?"
        provider = self.Provider(self.payload("Which field on day 18?"))
        _, state, _, _ = plan(provider, message, empty_state(), [], 1)
        self.assertEqual("a=b", public_state(state)["terms"]["count"])
        self.assertEqual(["Keep punctuation!"], list(public_state(state)["constraints"].values()))
        class Malformed:
            def structured(self, prompt, schema): return "invalid JSON"
        _, fallback, _, trace = plan(Malformed(), message, empty_state(), [], 1)
        self.assertEqual(state, fallback)
        self.assertTrue(trace["warnings"])

    def test_labels_in_fences_blockquotes_and_quoted_text_are_not_memory(self):
        from conversation import explicit_declarations
        message = 'Example:\n```text\nЦель: invented goal\n```\n> Ограничение: invented preference\n"Термин: fake=value"\nWhat happens?'
        declarations, request = explicit_declarations(message)
        self.assertEqual([], declarations)
        self.assertEqual(message, request)

    def test_question_label_cannot_bypass_fact_evidence_guard(self):
        message = "Уточнение: Какие серверы участвуют?\nКакие серверы на день 20?"
        _, state, _, trace = plan(self.Provider(self.payload("Какие серверы на день 20?")), message, empty_state(), [], 1)
        self.assertEqual({}, state["clarifications"])
        self.assertTrue(trace["warnings"])

    def test_reworded_followup_after_term_declaration_keeps_latest_lesson(self):
        state = empty_state()
        history = [{"user": "Какие поля сохраняет worker дня 18?", "resolved_question": "Какие поля сохраняет worker дня 18?",
                    "resolution_accepted": True, "resolution_state": resolution_state(state)}]
        message = "Термин: снимок = сохранённые данные GitHub\nА где это хранится?"
        question, after, ambiguous, trace = plan(self.Provider(self.payload("А где хранятся снимки GitHub?")), message, state, history, 2)
        self.assertIn("день 18", question)
        self.assertFalse(ambiguous)
        self.assertEqual("сохранённые данные GitHub", public_state(after)["terms"]["снимок"])
        self.assertEqual("18", trace["topic_anchor"]["lesson"])

    def test_current_declared_topic_overrides_a_previous_different_lesson(self):
        state = empty_state()
        history = [{"user": "Какие серверы на день 20?", "resolved_question": "Какие серверы на день 20?",
                    "resolution_accepted": True, "resolution_state": resolution_state(state)}]
        message = "Уточнение: Речь о worker дня 18.\nКак запустить его?"
        question, _, ambiguous, _ = plan(self.Provider(self.payload("Как запустить worker?")), message, state, history, 2)
        self.assertIn("день 18", question)
        self.assertNotIn("день 20", question)
        self.assertFalse(ambiguous)

    def test_current_explicit_lesson_cannot_be_dropped_or_replaced_by_detour(self):
        message = "Вернёмся к цели дня 20: что делает mcp_registry.py?"
        for proposed in ("Что делает mcp_registry.py?", "Что делает mcp_registry.py на день 18?"):
            question, _, _, trace = plan(self.Provider(self.payload(proposed)), message, empty_state(), [], 2)
            self.assertIn("день 20", question)
            self.assertNotIn("день 18", question)
            self.assertEqual("20", trace["current_topic_anchor"]["lesson"])
        _, _, _, trace = plan(self.Provider(self.payload("Compare day 18 and day 20")), "Compare day 18 and day 20", empty_state(), [], 2)
        self.assertNotIn("current_topic_anchor", trace)

    def test_reference_review_does_not_force_a_repeated_negative_decision(self):
        state = empty_state()
        history = [{"user": "Какой полный флоу дня 20?", "resolved_question": "Какой полный флоу дня 20?",
                    "resolution_accepted": True, "resolution_state": resolution_state(state)}]
        message = "А что сравнивает последний шаг?"
        provider = self.Provider(self.payload(message, True), self.payload(message, True))
        question, _, ambiguous, trace = plan(provider, message, state, history, 2)
        self.assertTrue(ambiguous)
        self.assertEqual(message, question)
        self.assertEqual(2, len(provider.prompts))
        self.assertIn("reference_review_raw", trace)

    def test_compact_reference_review_sees_current_term_and_preserves_memory_provenance(self):
        state = update(empty_state(), "goal", "", "Проверить день 18.", "Проверить день 18.", "Проверить день 18.", 1)
        history = [{"user": "Какие поля GitHub сохраняет worker на день 18?",
                    "resolved_question": "Какие поля GitHub сохраняет worker на день 18?",
                    "resolution_accepted": True, "resolution_state": resolution_state(state)}]
        message = "Термин: снимок = сохранённые данные GitHub\nА где это хранится?"
        provider = self.Provider(self.payload("А где это хранится?", True),
                                 self.payload("Где хранятся сохранённые данные GitHub на день 18?"))
        question, after, ambiguous, trace = plan(provider, message, state, history, 2)
        self.assertFalse(ambiguous)
        self.assertIn("день 18", question)
        review = provider.prompts[1]
        self.assertTrue(review.startswith("REFERENCE REVIEW"))
        data = json.loads(review.rsplit("\nDATA:\n", 1)[1])
        self.assertEqual("А где это хранится?", data["current_request"])
        self.assertEqual("сохранённые данные GitHub", data["current_literal_declarations"][0]["value"])
        self.assertEqual(after['terms']['снимок']['value'], data['task_state']['terms']['снимок'])
        self.assertEqual(state['goal'], after['goal'])
        self.assertEqual([], trace['warnings'])

    def test_compact_reference_review_keeps_ambiguous_term_question_unanswered(self):
        state = empty_state()
        history = [{"user": "Сравни хранение данных и хранение отчёта на день 18.",
                    "resolved_question": "Сравни хранение данных и хранение отчёта на день 18.",
                    "resolution_accepted": True, "resolution_state": resolution_state(state)}]
        message = "Термин: данные = наблюдения\nА где это хранится?"
        provider = self.Provider(self.payload("А где это хранится?", True), self.payload("А где это хранится?", True))
        question, after, ambiguous, trace = plan(provider, message, state, history, 2)
        self.assertTrue(ambiguous)
        self.assertEqual("А где это хранится?", question)
        self.assertEqual("наблюдения", after['terms']['данные']['value'])
        self.assertTrue(trace['effective_needs_clarification'])

    def test_reference_review_can_resolve_observed_topic_but_cannot_invent_filename(self):
        state = empty_state()
        history = [{"user": "Какой полный флоу дня 20?", "resolved_question": "Какой полный флоу дня 20?",
                    "resolution_accepted": True, "resolution_state": resolution_state(state)}]
        message = "А что сравнивает последний шаг?"
        provider = self.Provider(self.payload(message, True), self.payload("Что сравнивает последний шаг полного флоу дня 20?"))
        question, _, ambiguous, trace = plan(provider, message, state, history, 2)
        self.assertFalse(ambiguous)
        self.assertIn("дня 20", question)
        bad = self.Provider(self.payload(message, True), self.payload("Что делает invented.py на день 20?"))
        question, _, ambiguous, trace = plan(bad, message, state, history, 2)
        self.assertTrue(ambiguous)
        self.assertEqual(message, question)
        self.assertTrue(trace["warnings"])

    def test_namespace_before_top_k_and_real_score_threshold_across_both_queries(self):
        import sqlite3
        from storage import Hit
        from retrieval25 import LessonRetriever
        class KB:
            def __init__(self, score):
                self.db = sqlite3.connect(":memory:")
                self.db.row_factory = sqlite3.Row
                self.db.executescript("CREATE TABLE chunks(source,strategy); CREATE TABLE documents(source,text);")
                self.hits = [Hit("other", "day-18-other/README.md", "doc", "Other lesson evidence", .99, 1, 1),
                             Hit("wanted", "day-20-demo/README.md", "doc", "Requested lesson evidence", score, 1, 1)]
                for h in self.hits:
                    self.db.execute("INSERT INTO chunks VALUES(?, 'fixed')", (h.source,))
                    self.db.execute("INSERT INTO documents VALUES(?,?)", (h.source, "# Namespace title"))
            def info(self, strategy): return {"model": "test", "dimension": 1}
            def search(self, strategy, vector, top_k): return self.hits[:top_k]
        class Provider:
            model = "test"
            def embed(self, queries): return [[1.0] for q in queries]
        for score in (.6, .49):
            kb = KB(score)
            try:
                result = LessonRetriever(kb, Provider(), Settings(1, 1, .5, "fixed", "heuristic")).run("Which process on day 20?", generate=False)
                self.assertEqual(["wanted"] if score >= .5 else [], [h.chunk_id for h in result.sources])
                self.assertEqual(2, len(result.to_dict()["lesson_retrieval"]["branches"]))
                self.assertEqual(score, result.to_dict()["candidates"][0]["cosine"])
                self.assertNotIn("other", json.dumps(result.to_dict()["candidates"]))
            finally:
                kb.db.close()


if __name__ == "__main__":
    unittest.main()
