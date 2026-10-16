"""Table-bound composite code regression; no model calls or semantic proof."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest
import test_pipeline as fixtures
from bublik_developer.generation import Qwen,ModelOutputError,unsupported_identifier,table_supported_transition,validate_output
from bublik_developer.baseline import BaselineQwen,validate_baseline_output
from bublik_developer.contracts import Role,canonical

ROOT=Path(__file__).resolve().parents[1]
TABLE='''| Current | Allowed transitions | Guard |
|---|---|---|
| planning | execution | Approved plan |
| execution | validation, planning | Every step |
| validation | done, execution | PASS |
| done | none | Terminal |'''


class TransitionTokenTests(unittest.TestCase):
    def test_supported_directed_edges_from_English_and_Russian_tables(self):
        russian=TABLE.replace('Current','Текущее').replace('Allowed transitions','Разрешённые переходы')
        for support in [TABLE,russian]:
            for token in ['planning → execution','validation → done','planning->execution','planning  →  execution']:
                self.assertTrue(table_supported_transition(token,support))
                self.assertFalse(unsupported_identifier('Переход `'+token+'`.',support))

    def test_unknown_states_and_unlisted_directed_edges_stay_rejected(self):
        for token in ['planning → done','done → execution','phantom → done','planning → ghost_state']:
            self.assertTrue(unsupported_identifier('Переход `'+token+'`.',TABLE))

    def test_existing_names_in_prose_are_not_proof_of_an_edge(self):
        self.assertTrue(unsupported_identifier('Переход `planning → execution`.','States: planning, execution.'))

    def test_unrelated_headers_missing_separator_and_malformed_tables_fail_closed(self):
        variants=[TABLE.replace('Current','Name').replace('Allowed transitions','Description'),
                  TABLE.replace('|---|---|---|',''),TABLE.replace('|---|---|---|','|---|---|'),
                  TABLE.replace('| planning | execution | Approved plan |','planning execution Approved plan')]
        for table in variants:self.assertTrue(unsupported_identifier('Переход `planning → execution`.',table))

    def test_target_must_be_defined_as_state_in_same_table(self):
        table=TABLE.replace('execution | Approved plan','waiting | Approved plan')
        self.assertTrue(unsupported_identifier('Переход `planning → waiting`.',table))

    def test_multiple_targets_preserve_direction_and_support_all_declared_edges(self):
        for token in ['execution → validation','execution → planning','validation → execution']:
            self.assertFalse(unsupported_identifier('Переход `'+token+'`.',TABLE))

    def test_unknown_identifiers_paths_and_code_expressions_remain_literal(self):
        for text in ['Вызов `fake_worker`.','Вызов fake_worker.','Путь `/private/db`.',
                     'Путь /api/unknown.','Код `planning(); execution()`.','Код `planning → execution; drop_table`.']:
            self.assertTrue(unsupported_identifier(text,TABLE))
        self.assertFalse(unsupported_identifier('Вызов `foo_worker` по `/api/status`.','foo_worker /api/status'))

    def test_edges_cannot_be_joined_across_separate_tables(self):
        left='| From | To |\n|---|---|\n| first | second |\n| second | none |'
        right='| From | To |\n|---|---|\n| second | last |\n| last | none |'
        self.assertFalse(table_supported_transition('first → last',left+'\n\n'+right))

    def test_terminal_markers_do_not_become_transition_targets(self):
        for marker in ['none','нет','—','-','`none`']:
            table=TABLE.replace('done | none','done | '+marker)
            self.assertTrue(unsupported_identifier('Переход `done → none`.',table))

    def test_already_exact_code_support_is_unchanged(self):
        self.assertFalse(unsupported_identifier('Переход `alpha → beta`.','Example: alpha → beta'))
        self.assertTrue(unsupported_identifier('Переход `alpha → gamma`.','Example: alpha → beta'))

    def test_no_project_specific_state_names_are_required(self):
        table='| From | To |\n|:---|---:|\n| `queued_state` | `running_state` |\n| `running_state` | `finished_state` |\n| `finished_state` | none |'
        self.assertFalse(unsupported_identifier('Переход `queued_state → running_state`.',table))
        self.assertTrue(unsupported_identifier('Переход `queued_state → finished_state`.',table))

    def test_uncited_table_does_not_support_claim_in_either_mode(self):
        context={'question':'Какие переходы разрешены?','language':'ru','evidence':[
            {'id':'e1','quote':'Состояния planning и execution.'},{'id':'e2','quote':TABLE}]}
        value={'status':'answered','language':'ru','claims':[{'text':'Переход `planning → execution` разрешён при условии утверждения плана.','evidence_ids':['e1']}]}
        for single in [False,True]:
            data={**value,'git_fact_ids':[]} if single else value
            ctx={**context,'documentation_question':context['question'],'git_facts':[]} if single else context
            with self.assertRaises(ModelOutputError) as raised:
                if single:validate_baseline_output(Role.MAIN,data,ctx)
                else:validate_output(Role.DOCUMENTATION,data,ctx)
            self.assertEqual(raised.exception.validation_reason,'unsupported_identifier')
        value['claims'][0]['evidence_ids']=['e2'];self.assertEqual(validate_output(Role.DOCUMENTATION,value,context),value)

    def test_captured_two_real_diagnostic_frames_validate_without_text_repair(self):
        fixture=json.loads((ROOT/'evaluation/inline_transition_regression_v099.json').read_text())
        self.assertEqual(len(fixture['rows']),2)
        for row in fixture['rows']:
            self.assertEqual(sha256(row['raw_content'].encode()).hexdigest(),row['content_sha256'])
            frame=json.loads(row['raw_content']);before=deepcopy(frame)
            if row['mode']=='single':validate_baseline_output(Role.MAIN,frame,row['context'])
            else:validate_output(Role.DOCUMENTATION,frame,row['context'])
            self.assertEqual(frame,before)

    def test_captured_contexts_keep_identical_requests_and_single_synthetic_chat(self):
        fixture=json.loads((ROOT/'evaluation/inline_transition_regression_v099.json').read_text())
        for row in fixture['rows']:
            frame=json.loads(row['raw_content']);transport,calls=fixtures.GenerationTests().server(frame)
            cls,role=(Qwen,Role.DOCUMENTATION) if row['mode']=='multi' else (BaselineQwen,Role.MAIN)
            lease=fixtures.FakeLease();client=cls(lease,transport=transport)
            self.assertEqual(client.generate(role,row['context']),frame)
            chats=[body for endpoint,body in calls if endpoint=='/api/chat'];self.assertEqual(len(chats),1)
            self.assertEqual(sha256(canonical(chats[0]).encode()).hexdigest(),row['request_body_sha256'])
            self.assertTrue(lease.finished);self.assertFalse(lease.invalidated)


if __name__=='__main__':unittest.main()
