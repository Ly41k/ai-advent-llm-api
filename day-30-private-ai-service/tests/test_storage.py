"""Real SQLite/threads/processes; no HTTP server, model or network is involved."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import select
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from bublik_service.domain import (
    CapacityExceeded, Conflict, ContextPlan, InvalidInput, ModelProfile, NotFound,
    QueueLimits, SchemaError, StorageUnavailable,
)
from bublik_service.storage import ChatRepository
from bublik_service.storage.database import Database

HERE = Path(__file__).resolve().parents[1]
PLAN = ContextPlan(input_token_upper_bound=100)


class RepositoryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "chats.sqlite3"
        self.time = datetime(2026, 10, 9, tzinfo=timezone.utc)
        self.repo = ChatRepository(self.path, clock=lambda: self.time)
        self.owner = self.repo.create_user("owner", "synthetic-password-hash")
        self.other = self.repo.create_user("other", "other-synthetic-hash")
        self.chat = self.repo.create_chat(self.owner, key="first-chat").chat_id

    def message(self, *, chat=None, content="Question", key="message", revision=None, context=PLAN):
        chat = chat or self.chat
        if revision is None:
            revision = self.repo.get_chat(self.owner, chat)["revision"]
        return self.repo.accept_message(self.owner, chat, content,
            expected_revision=revision, key=key, context=context)

    def complete(self, answer="Answer", *, key="message", content="Question"):
        receipt = self.message(key=key, content=content)
        with self.repo.worker_session() as worker:
            self.assertEqual(worker.claim_next()["id"], receipt.generation_id)
            worker.finish(receipt.generation_id, content=answer)
        return receipt


class PersistenceTests(RepositoryCase):
    def test_restart_retains_owner_history_and_receipt(self):
        receipt = self.complete(content="  Привет\n", answer="Hello\n")
        before = self.repo.export_chat(self.owner, self.chat)
        reopened = ChatRepository(self.path)
        self.assertEqual(before, reopened.export_chat(self.owner, self.chat))
        replay = reopened.accept_message(self.owner, self.chat, "  Привет\n",
            expected_revision=0, key="message", context=PLAN)
        self.assertTrue(replay.replayed)
        self.assertEqual(receipt.generation_id, replay.generation_id)
        self.assertEqual(len(reopened.history(self.owner, self.chat)), 2)

    def test_same_key_different_content_or_revision_conflicts(self):
        self.message()
        for content, revision in (("Different", 0), ("Question", 1)):
            with self.subTest(content=content, revision=revision), self.assertRaises(Conflict) as caught:
                self.message(content=content, revision=revision)
            self.assertEqual(caught.exception.code, "idempotency_conflict")
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 2)

    def test_replay_survives_profile_change_and_full_queue(self):
        first = self.message()
        for i in range(2):
            chat = self.repo.create_chat(self.owner, key=f"extra-{i}").chat_id
            self.message(chat=chat, key=f"extra-msg-{i}")
        replay = self.repo.accept_message(self.owner, self.chat, "Question", expected_revision=0,
            key="message", context=PLAN, profile=ModelProfile(max_output=512))
        self.assertTrue(replay.replayed)
        self.assertEqual(first.generation_id, replay.generation_id)
        self.assertEqual(self.repo.get_generation(self.owner, first.generation_id)["profile"]["max_output"], 1024)

    def test_chat_creation_is_idempotent_and_owner_scoped(self):
        replay = self.repo.create_chat(self.owner, key="first-chat")
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.chat_id, self.chat)
        other = self.repo.create_chat(self.other, key="first-chat")
        self.assertNotEqual(other.chat_id, self.chat)
        with self.assertRaises(Conflict):
            self.repo.create_chat(self.owner, "Changed title", key="first-chat")

    def test_owner_checks_cover_reads_send_retry_export_and_cursor(self):
        receipt = self.message()
        actions = [
            lambda: self.repo.get_chat(self.other, self.chat),
            lambda: self.repo.history(self.other, self.chat),
            lambda: self.repo.export_chat(self.other, self.chat),
            lambda: self.repo.context_candidates(self.other, self.chat),
            lambda: self.repo.get_generation(self.other, receipt.generation_id),
            lambda: self.repo.accept_message(self.other, self.chat, "Question", expected_revision=0,
                                             key="message", context=PLAN),
            lambda: self.repo.retry_message(self.other, receipt.user_message_id, expected_revision=1,
                                            key="retry", context=PLAN),
            lambda: self.repo.list_chats(self.other, after=self.chat),
        ]
        for action in actions:
            with self.subTest(action=actions.index(action)), self.assertRaises(NotFound):
                action()

    def test_unauthorized_and_unknown_ids_have_same_error(self):
        for chat in (self.chat, "does-not-exist"):
            with self.assertRaises(NotFound) as caught:
                self.repo.get_chat(self.other, chat)
            self.assertEqual(str(caught.exception), "not_found")

    def test_stale_revision_and_second_turn_leave_no_extra_messages(self):
        self.complete()
        with self.assertRaises(Conflict) as caught:
            self.message(key="stale", revision=0)
        self.assertEqual(caught.exception.code, "stale_revision")
        self.message(key="second")
        with self.assertRaises(Conflict) as caught:
            self.message(key="third")
        self.assertEqual(caught.exception.code, "chat_has_outstanding_generation")
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 4)

    def test_enqueue_and_idempotency_rollback_together(self):
        with patch.object(self.repo, "_remember", side_effect=RuntimeError("synthetic fault")):
            with self.assertRaises(RuntimeError):
                self.message()
        self.assertEqual(self.repo.get_chat(self.owner, self.chat)["revision"], 0)
        self.assertEqual(self.repo.history(self.owner, self.chat), [])
        self.assertEqual(self.repo.storage_status()["queued"], 0)
        self.assertFalse(self.message().replayed)

    def test_finish_revision_conflict_rolls_back_answer(self):
        receipt = self.message()
        with self.repo.worker_session() as worker:
            worker.claim_next()
            with self.repo.database.connect(write=True) as db:
                db.execute("UPDATE chats SET revision=99 WHERE id=?", (self.chat,))
            with self.assertRaises(Conflict):
                worker.finish(receipt.generation_id, content="Must roll back")
            generation = self.repo.get_generation(self.owner, receipt.generation_id)
            self.assertEqual(generation["status"], "running")
            self.assertEqual(generation["assistant"]["content"], "")
            with self.repo.database.connect(write=True) as db:
                db.execute("UPDATE chats SET revision=1 WHERE id=?", (self.chat,))
            worker.finish(receipt.generation_id, content="Committed")

    def test_history_pagination_has_no_overlaps_and_keeps_raw_text(self):
        for i in range(6):
            self.complete(key=f"m-{i}", content=f"Question {i}")
        output, cursor = [], 0
        while page := self.repo.history(self.owner, self.chat, after_sequence=cursor, limit=3):
            output += page
            cursor = page[-1]["sequence"]
        self.assertEqual([m["sequence"] for m in output], list(range(1, 13)))
        self.assertEqual(len({m["id"] for m in output}), 12)

    def test_chat_pagination_is_owner_scoped(self):
        for i in range(4):
            self.time += timedelta(seconds=1)
            self.repo.create_chat(self.owner, key=f"c-{i}")
        self.repo.create_chat(self.other, key="not-mine")
        found, cursor = [], None
        while page := self.repo.list_chats(self.owner, limit=2, after=cursor):
            found += page
            cursor = page[-1]["id"]
        self.assertEqual(len(found), 5)
        self.assertEqual(len({c["id"] for c in found}), 5)
        self.assertTrue(all(c["owner_id"] == self.owner for c in found))

    def test_invalid_request_never_creates_a_turn(self):
        for value in ("", "   ", "\x00", "ё" * 9000, "\ud800", 123):
            with self.subTest(value=type(value).__name__), self.assertRaises(InvalidInput):
                self.message(content=value)
        for key in ("", "bad key", "x" * 129, None):
            with self.subTest(key=key), self.assertRaises(InvalidInput):
                self.message(key=key)
        self.assertEqual(self.repo.history(self.owner, self.chat), [])

    def test_export_excludes_credentials_and_worker_fencing_tokens(self):
        self.complete()
        exported = json.dumps(self.repo.export_chat(self.owner, self.chat))
        self.assertNotIn("password_hash", exported)
        self.assertNotIn("synthetic-password-hash", exported)
        self.assertNotIn("worker_token", exported)
        self.assertIn("bublik-chat-export-v1", exported)

    def test_export_uses_one_snapshot_during_an_actual_concurrent_write(self):
        original = self.repo._chat
        other = ChatRepository(self.path)
        def write(db, owner, chat):
            row = original(db, owner, chat)
            other.accept_message(owner, chat, "Concurrent", expected_revision=0,
                                 key="concurrent", context=PLAN)
            return row
        with patch.object(self.repo, "_chat", side_effect=write):
            snapshot = self.repo.export_chat(self.owner, self.chat)
        self.assertEqual(snapshot["chat"]["revision"], 0)
        self.assertEqual(snapshot["messages"], [])
        self.assertEqual(snapshot["events"], [])
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 2)


class ContextTests(RepositoryCase):
    def test_last_complete_pairs_selected_without_erasing_history(self):
        first = self.complete(key="first", content="Old question")
        second = self.complete(key="second", content="Recent question")
        plan = ContextPlan((second.user_message_id, second.assistant_message_id), 200)
        receipt = self.message(key="third", context=plan)
        snapshot = self.repo.get_generation(self.owner, receipt.generation_id)["context"]
        self.assertEqual(snapshot["omitted_turns"], 1)
        self.assertEqual([m["role"] for m in snapshot["messages"]], ["system", "user", "assistant", "user"])
        self.assertNotIn("Old question", json.dumps(snapshot))
        self.assertIn(first.user_message_id, [m["id"] for m in self.repo.history(self.owner, self.chat)])

    def test_orphan_foreign_duplicate_and_non_suffix_context_rejected(self):
        first = self.complete(key="first")
        self.complete(key="second")
        other_chat = self.repo.create_chat(self.other, key="other").chat_id
        foreign = self.repo.accept_message(self.other, other_chat, "Secret", expected_revision=0, key="other", context=PLAN)
        for ids in ((first.assistant_message_id,), (first.user_message_id, first.assistant_message_id),
                    (foreign.user_message_id, foreign.assistant_message_id),
                    (first.user_message_id, first.user_message_id)):
            with self.subTest(ids=ids), self.assertRaises(InvalidInput):
                self.message(key="rejected", context=ContextPlan(ids, 100))
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 4)

    def test_failed_and_truncated_answers_are_not_context_evidence(self):
        for i, status in enumerate(("failed", "truncated")):
            receipt = self.message(key=f"m-{i}")
            with self.repo.worker_session() as worker:
                worker.claim_next()
                worker.finish(receipt.generation_id, status=status, content="Partial",
                              error_code="model_unavailable" if status == "failed" else None)
        self.assertEqual(self.repo.context_candidates(self.owner, self.chat)["messages"], [])
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 4)

    def test_supplied_context_budget_includes_output_reserve_and_margin(self):
        with self.assertRaises(InvalidInput) as caught:
            self.message(context=ContextPlan(input_token_upper_bound=6657))
        self.assertEqual(caught.exception.code, "context_budget_exceeded")
        self.assertEqual(self.repo.history(self.owner, self.chat), [])
        self.message(context=ContextPlan(input_token_upper_bound=6656))

    def test_bounded_candidate_reads_preserve_total_count(self):
        for i in range(5):
            self.complete(key=f"m-{i}", content=f"Question {i}")
        candidates = self.repo.context_candidates(self.owner, self.chat, limit_turns=2)
        self.assertEqual(candidates["total_completed_turns"], 5)
        self.assertEqual(len(candidates["messages"]), 4)
        self.assertEqual(candidates["messages"][0]["content"], "Question 3")

    def test_invalid_profiles_and_context_metadata_are_rejected(self):
        for profile in (ModelProfile(model="qwen:cloud"), ModelProfile(temperature=float("nan")),
                        ModelProfile(max_output=True), ModelProfile(num_ctx=1000),
                        ModelProfile(prompt_version="unknown")):
            with self.subTest(profile=profile), self.assertRaises(InvalidInput):
                self.repo.accept_message(self.owner, self.chat, "Q", expected_revision=0, key="m",
                                         context=PLAN, profile=profile)
        for plan in (ContextPlan(input_token_upper_bound=True), ContextPlan(input_token_upper_bound=0),
                     ContextPlan(input_token_upper_bound=10, policy_version="unknown")):
            with self.subTest(plan=plan), self.assertRaises(InvalidInput):
                self.message(context=plan)


class WorkerTests(RepositoryCase):
    def test_fifo_and_one_active_generation_for_three_chats(self):
        receipts = []
        for i in range(3):
            chat = self.chat if i == 0 else self.repo.create_chat(self.owner, key=f"chat-{i}").chat_id
            receipts.append(self.message(chat=chat, key=f"message-{i}"))
        with self.repo.worker_session() as worker:
            for receipt in receipts:
                claimed = worker.claim_next()
                self.assertEqual(claimed["id"], receipt.generation_id)
                self.assertIsNone(worker.claim_next())
                worker.finish(claimed["id"], content="Answer")
            self.assertIsNone(worker.claim_next())

    def test_live_worker_blocks_second_worker_even_through_hardlink_alias(self):
        alias = self.root / "alias.sqlite3"
        os.link(self.path, alias)
        with self.repo.worker_session():
            with self.assertRaises(Conflict) as caught:
                self.repo.worker_session()
            self.assertEqual(caught.exception.code, "worker_already_running")
            with self.assertRaises(Conflict):
                ChatRepository(alias).worker_session()

    def test_saved_partial_is_append_only_and_restored_as_interrupted(self):
        receipt = self.message()
        old = self.repo.worker_session()
        old.claim_next()
        old.checkpoint(receipt.generation_id, "Saved part")
        with self.assertRaises(Conflict):
            old.checkpoint(receipt.generation_id, "Replacement")
        old.close()
        reopened = ChatRepository(self.path)
        with reopened.worker_session() as worker:
            self.assertEqual(worker.recovered_count, 1)
            row = reopened.get_generation(self.owner, receipt.generation_id)
            self.assertEqual((row["status"], row["assistant"]["content"]), ("interrupted", "Saved part"))
            with self.assertRaises(Conflict) as caught:
                worker.claim_next()
            self.assertEqual(caught.exception.code, "inference_recovery_required")
            with self.assertRaises(Conflict):
                old.finish(receipt.generation_id, content="Late old answer")

    def test_uncertain_inference_gate_survives_another_restart(self):
        receipt = self.message()
        other_chat = self.repo.create_chat(self.owner, key="second").chat_id
        queued = self.message(chat=other_chat, key="second")
        with self.repo.worker_session() as worker:
            worker.claim_next()
            worker.finish(receipt.generation_id, status="failed", error_code="model_timeout")
        with self.assertRaises(Conflict) as caught:
            self.message(chat=other_chat, key="blocked")
        self.assertEqual(caught.exception.code, "inference_recovery_required")
        with ChatRepository(self.path).worker_session() as worker:
            self.assertEqual(worker.recovered_count, 0)
            with self.assertRaises(Conflict):
                worker.claim_next()
            worker.confirm_inference_idle()
            self.assertEqual(worker.claim_next()["id"], queued.generation_id)
            with self.assertRaises(Conflict):
                worker.confirm_inference_idle()
            worker.finish(queued.generation_id, content="Recovered")

    def test_queued_job_survives_worker_restart_without_auto_answer(self):
        receipt = self.message()
        with self.repo.worker_session():
            pass
        with self.repo.worker_session() as worker:
            self.assertEqual(worker.recovered_count, 0)
            self.assertEqual(worker.claim_next()["id"], receipt.generation_id)
            worker.finish(receipt.generation_id, content="Answer")

    def test_retry_preserves_one_user_message_and_separate_attempts(self):
        first = self.message()
        with self.repo.worker_session() as worker:
            worker.claim_next()
            worker.finish(first.generation_id, status="failed", error_code="model_unavailable")
        second = self.repo.retry_message(self.owner, first.user_message_id, expected_revision=2,
                                         key="retry", context=PLAN)
        replay = self.repo.retry_message(self.owner, first.user_message_id, expected_revision=2,
                                         key="retry", context=PLAN)
        self.assertTrue(replay.replayed)
        self.assertEqual(second.generation_id, replay.generation_id)
        with self.repo.worker_session() as worker:
            worker.claim_next()
            worker.finish(second.generation_id, content="Second answer")
        history = self.repo.history(self.owner, self.chat)
        self.assertEqual([m["role"] for m in history], ["user", "assistant", "assistant"])
        self.assertEqual([m["status"] for m in history], ["accepted", "failed", "completed"])
        self.assertEqual(self.repo.get_generation(self.owner, second.generation_id)["attempt"], 2)
        self.assertEqual(self.repo.context_candidates(self.owner, self.chat)["messages"][1]["content"], "Second answer")

    def test_retry_completed_or_old_question_is_rejected(self):
        first = self.complete()
        with self.assertRaises(Conflict):
            self.repo.retry_message(self.owner, first.user_message_id, expected_revision=2, key="retry", context=PLAN)
        second = self.message(key="second")
        with self.repo.worker_session() as worker:
            worker.claim_next()
            worker.finish(second.generation_id, status="failed", error_code="model_unavailable")
        self.complete(key="third")
        with self.assertRaises(Conflict):
            self.repo.retry_message(self.owner, second.user_message_id, expected_revision=6, key="old", context=PLAN)

    def test_queue_expiry_retains_question_and_does_not_claim_model(self):
        receipt = self.message()
        self.time += timedelta(seconds=601)
        with self.repo.worker_session() as worker:
            self.assertEqual(worker.expire_queued(600), 1)
            self.assertIsNone(worker.claim_next())
        row = self.repo.get_generation(self.owner, receipt.generation_id)
        self.assertEqual((row["status"], row["error_code"]), ("failed", "queue_expired"))
        self.assertEqual(self.repo.history(self.owner, self.chat)[0]["content"], "Question")
        self.assertFalse(self.repo.storage_status()["inference_recovery_required"])

    def test_queue_expiry_uses_utc_for_non_utc_clock(self):
        self.message()
        self.time = (self.time + timedelta(seconds=599)).astimezone(timezone(timedelta(hours=3)))
        with self.repo.worker_session() as worker:
            self.assertEqual(worker.expire_queued(600), 0)
            self.time += timedelta(seconds=2)
            self.assertEqual(worker.expire_queued(600), 1)

    def test_finalization_is_atomic_and_cannot_run_twice(self):
        receipt = self.message()
        with self.repo.worker_session() as worker:
            worker.claim_next()
            worker.checkpoint(receipt.generation_id, "Part")
            worker.finish(receipt.generation_id, content="Part complete", metrics={"output_tokens": 3})
            with self.assertRaises(Conflict):
                worker.finish(receipt.generation_id, content="Part complete")
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 2)
        self.assertEqual(self.repo.get_chat(self.owner, self.chat)["revision"], 2)

    def test_invalid_terminal_and_metrics_cannot_publish_an_answer(self):
        receipt = self.message()
        with self.repo.worker_session() as worker:
            worker.claim_next()
            cases = [dict(content=""), dict(status="queued"), dict(status="failed", error_code="private raw body"),
                     dict(content="Answer", metrics={"content": "private"}),
                     dict(content="Answer", metrics={"output_tokens": True}),
                     dict(content="Answer", metrics={"inference_seconds": float("nan")})]
            for args in cases:
                with self.subTest(args=args), self.assertRaises(InvalidInput):
                    worker.finish(receipt.generation_id, **args)
            self.assertEqual(self.repo.get_generation(self.owner, receipt.generation_id)["status"], "running")
            worker.finish(receipt.generation_id, content="Answer", metrics={"input_tokens": None})


class ConcurrencyTests(RepositoryCase):
    def parallel(self, count, action):
        barrier = threading.Barrier(count)
        def invoke(index):
            barrier.wait(timeout=10)
            try:
                return action(index)
            except (Conflict, CapacityExceeded) as error:
                return error.code
        with ThreadPoolExecutor(max_workers=count) as executor:
            return list(executor.map(invoke, range(count)))

    def test_ten_simultaneous_replays_have_one_durable_message(self):
        receipts = self.parallel(10, lambda _: self.message(revision=0))
        self.assertEqual(len({r.generation_id for r in receipts}), 1)
        self.assertEqual(sum(not r.replayed for r in receipts), 1)
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 2)

    def test_two_devices_with_different_keys_cannot_interleave_one_chat(self):
        results = self.parallel(2, lambda i: self.message(revision=0, key=f"device-{i}"))
        self.assertEqual(sum(not isinstance(r, str) for r in results), 1)
        self.assertIn("stale_revision", results)
        self.assertEqual(len(self.repo.history(self.owner, self.chat)), 2)

    def test_per_user_limit_is_atomic_across_chats_and_threads(self):
        chats = [self.repo.create_chat(self.owner, key=f"c-{i}").chat_id for i in range(6)]
        results = self.parallel(6, lambda i: self.message(chat=chats[i], key=f"m-{i}", revision=0))
        self.assertEqual(sum(not isinstance(r, str) for r in results), 3)
        self.assertEqual(results.count("user_queue_full"), 3)
        self.assertEqual(self.repo.storage_status()["queued"], 3)

    def test_global_queue_limit_is_atomic_across_users(self):
        repo = ChatRepository(self.path, limits=QueueLimits(queued=2, per_user_outstanding=10))
        owners = [self.owner, self.other, self.owner, self.other]
        chats = [repo.create_chat(o, key=f"c-{i}").chat_id for i, o in enumerate(owners)]
        results = self.parallel(4, lambda i: repo.accept_message(owners[i], chats[i], "Q",
                           expected_revision=0, key=f"m-{i}", context=PLAN))
        self.assertEqual(sum(not isinstance(r, str) for r in results), 2)
        self.assertEqual(results.count("global_queue_full"), 2)

    def test_distinct_processes_share_the_same_idempotency_record(self):
        code = ("import json,sys; from dataclasses import asdict; from bublik_service.storage import ChatRepository; "
                "from bublik_service.domain import ContextPlan; r=ChatRepository(sys.argv[1]); "
                "x=r.accept_message(sys.argv[2],sys.argv[3],'Question',expected_revision=0,key='message',"
                "context=ContextPlan(input_token_upper_bound=100)); print(json.dumps(asdict(x)))")
        def invoke(_):
            output = subprocess.run([sys.executable, "-c", code, str(self.path), self.owner, self.chat],
                                    cwd=HERE, capture_output=True, text=True, check=True, timeout=15)
            return json.loads(output.stdout)
        with ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(invoke, range(3)))
        self.assertEqual(len({r["generation_id"] for r in rows}), 1)
        self.assertEqual(sum(not r["replayed"] for r in rows), 1)

    def test_killed_process_releases_lease_but_requires_explicit_engine_recovery(self):
        receipt = self.message()
        code = ("import sys; from bublik_service.storage import ChatRepository; r=ChatRepository(sys.argv[1]); "
                "w=r.worker_session(); g=w.claim_next(); w.checkpoint(g['id'],'Saved before crash'); "
                "print('claimed',flush=True); sys.stdin.read()")
        process = subprocess.Popen([sys.executable, "-c", code, str(self.path)], cwd=HERE,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([process.stdout], [], [], 10)
            self.assertTrue(ready, "child did not reach the durable checkpoint")
            self.assertEqual(process.stdout.readline().strip(), "claimed")
            with self.assertRaises(Conflict):
                self.repo.worker_session()
        finally:
            process.kill()
            process.communicate(timeout=10)
        with self.repo.worker_session() as worker:
            self.assertEqual(worker.recovered_count, 1)
            with self.assertRaises(Conflict):
                worker.claim_next()
            worker.confirm_inference_idle()
        row = self.repo.get_generation(self.owner, receipt.generation_id)
        self.assertEqual(row["assistant"]["content"], "Saved before crash")
        self.assertEqual(row["status"], "interrupted")


class DatabaseTests(RepositoryCase):
    def test_wal_full_sync_foreign_keys_and_private_mode(self):
        status = self.repo.storage_status()
        self.assertEqual((status["journal_mode"], status["synchronous"], status["integrity"]), ("wal", 2, "ok"))
        self.assertTrue(status["foreign_keys"])
        self.assertEqual(status["foreign_key_violations"], 0)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_migration_is_repeatable_but_modified_checksum_is_rejected(self):
        before = self.repo.export_chat(self.owner, self.chat)
        self.assertEqual(ChatRepository(self.path).export_chat(self.owner, self.chat), before)
        directory = self.root / "migrations"
        directory.mkdir()
        for source in (HERE / "bublik_service/storage/migrations").glob("*.sql"):
            (directory / source.name).write_bytes(source.read_bytes())
        raw = (HERE / "bublik_service/storage/migrations/001_initial.sql").read_text()
        (directory / "001_initial.sql").write_text(raw + "\n-- Changed migration\n")
        with self.assertRaises(SchemaError) as caught:
            Database(self.path, migrations=directory)
        self.assertEqual(caught.exception.code, "migration_checksum_mismatch")

    def test_failed_migration_does_not_leave_partial_schema_or_ledger(self):
        directory = self.root / "broken-migrations"
        directory.mkdir()
        (directory / "001_initial.sql").write_text("CREATE TABLE marker(id INTEGER);\nINVALID SQL;\n")
        path = self.root / "failed.sqlite3"
        with self.assertRaises(StorageUnavailable):
            Database(path, migrations=directory)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
            self.assertEqual(db.execute("PRAGMA application_id").fetchone()[0], 0)

    def test_forward_migration_preserves_history_and_receipts(self):
        self.complete()
        before = self.repo.export_chat(self.owner, self.chat)
        directory = self.root / "forward-migrations"
        directory.mkdir()
        for source in (HERE / "bublik_service/storage/migrations").glob("*.sql"):
            (directory / source.name).write_bytes(source.read_bytes())
        (directory / "003_metadata.sql").write_text("CREATE TABLE future_metadata(id INTEGER PRIMARY KEY);\n")
        migrated = Database(self.path, migrations=directory)
        self.assertEqual(migrated.status()["schema_version"], 3)
        self.assertEqual(self.repo.export_chat(self.owner, self.chat), before)
        self.assertTrue(self.message(revision=0).replayed)
        # A previous release must refuse a newer database, not downgrade it.
        with self.assertRaises(SchemaError) as caught:
            ChatRepository(self.path)
        self.assertEqual(caught.exception.code, "newer_database_schema")

    def test_failed_forward_migration_preserves_version_history_and_receipts(self):
        self.complete()
        before = self.repo.export_chat(self.owner, self.chat)
        directory = self.root / "broken-forward-migrations"
        directory.mkdir()
        for source in (HERE / "bublik_service/storage/migrations").glob("*.sql"):
            (directory / source.name).write_bytes(source.read_bytes())
        (directory / "003_broken.sql").write_text("CREATE TABLE partial_upgrade(id INTEGER);\nINVALID SQL;\n")
        with self.assertRaises(StorageUnavailable):
            Database(self.path, migrations=directory)
        reopened = ChatRepository(self.path)
        self.assertEqual(reopened.storage_status()["schema_version"], 2)
        self.assertEqual(reopened.export_chat(self.owner, self.chat), before)
        self.assertTrue(self.message(revision=0).replayed)
        with reopened.database.connect() as db:
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='partial_upgrade'").fetchone())
            self.assertEqual(db.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], 2)

    def test_foreign_database_is_not_adopted_or_changed_to_wal(self):
        path = self.root / "previous-lesson.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE previous_lesson(id INTEGER)")
            db.commit()
        path.chmod(0o600)
        with self.assertRaises(SchemaError) as caught:
            ChatRepository(path)
        self.assertEqual(caught.exception.code, "foreign_database")
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [("previous_lesson",)])

    def test_newer_schema_and_user_version_tampering_are_rejected(self):
        with self.repo.database.connect(write=True) as db:
            db.execute("INSERT INTO schema_migrations VALUES(3,'003_future.sql','future')")
        with self.assertRaises(SchemaError) as caught:
            ChatRepository(self.path)
        self.assertEqual(caught.exception.code, "newer_database_schema")
        with self.repo.database.connect(write=True) as db:
            db.execute("DELETE FROM schema_migrations WHERE version=3")
            db.execute("PRAGMA user_version=99")
        with self.assertRaises(SchemaError) as caught:
            ChatRepository(self.path)
        self.assertEqual(caught.exception.code, "schema_version_mismatch")

    def test_database_replacement_and_symlink_cannot_silently_redirect_store(self):
        replacement = self.root / "replacement.sqlite3"
        self.repo.backup(replacement)
        os.replace(replacement, self.path)
        with self.assertRaises(StorageUnavailable) as caught:
            self.repo.history(self.owner, self.chat)
        self.assertEqual(caught.exception.code, "database_file_changed")
        link = self.root / "symlink.sqlite3"
        link.symlink_to(self.path)
        with self.assertRaises(StorageUnavailable):
            ChatRepository(link)

    def test_foreign_key_violation_is_rolled_back_and_diagnostics_are_redacted(self):
        with self.assertRaises(StorageUnavailable) as caught:
            with self.repo.database.connect(write=True) as db:
                db.execute("INSERT INTO chats VALUES ('bad','secret-owner','secret-title',0,'now','now')")
        self.assertEqual(str(caught.exception), "storage_unavailable")
        self.assertEqual(len(self.repo.list_chats(self.owner)), 1)

    def test_busy_database_fails_without_partial_write(self):
        limited = ChatRepository(self.path, timeout=.01)
        with self.repo.database.connect(write=True):
            with self.assertRaises(StorageUnavailable):
                limited.create_chat(self.owner, key="busy")
        self.assertEqual(len(self.repo.list_chats(self.owner)), 1)
        self.assertFalse(limited.create_chat(self.owner, key="busy").replayed)

    def test_backup_restores_history_ownership_and_idempotency_with_wal_active(self):
        receipt = self.complete()
        before = self.repo.export_chat(self.owner, self.chat)
        target = self.root / "backup.sqlite3"
        self.repo.backup(target)
        restored = ChatRepository(target)
        self.assertEqual(restored.export_chat(self.owner, self.chat), before)
        replay = restored.accept_message(self.owner, self.chat, "Question", expected_revision=0,
                                         key="message", context=PLAN)
        self.assertEqual(replay.generation_id, receipt.generation_id)
        self.assertTrue(replay.replayed)
        with self.assertRaises(NotFound):
            restored.history(self.other, self.chat)

    def test_backup_does_not_overwrite_destination_database_or_sidecars(self):
        existing = self.root / "existing.txt"
        existing.write_bytes(b"keep this")
        paths = [existing, self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-journal")]
        for path in paths:
            with self.subTest(path=path), self.assertRaises(InvalidInput):
                self.repo.backup(path)
        self.assertEqual(existing.read_bytes(), b"keep this")

    def test_backup_publication_race_cannot_overwrite_another_file(self):
        target = self.root / "raced.sqlite3"
        original = os.link
        def racing(source, destination):
            target.write_bytes(b"other writer")
            return original(source, destination)
        with patch("os.link", side_effect=racing), self.assertRaises(StorageUnavailable):
            self.repo.backup(target)
        self.assertEqual(target.read_bytes(), b"other writer")
        self.assertEqual(list(self.root.glob(".bublik-backup-*")), [])


class CliTests(unittest.TestCase):
    def test_storage_cli_initializes_inspects_and_backs_up_without_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path, backup = Path(folder) / "data.sqlite3", Path(folder) / "backup.sqlite3"
            def invoke(*args):
                return subprocess.run([sys.executable, "-m", "bublik_service", "--db", str(path), *args],
                                      cwd=HERE, capture_output=True, text=True, timeout=15)
            absent = invoke("storage-status")
            self.assertEqual(absent.returncode, 1)
            self.assertFalse(path.exists())
            initialized = invoke("init-db")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertEqual(json.loads(initialized.stdout)["schema_version"], 2)
            self.assertEqual(invoke("storage-status").returncode, 0)
            self.assertEqual(invoke("backup", str(backup)).returncode, 0)
            self.assertEqual(invoke("backup", str(backup)).returncode, 1)


if __name__ == "__main__":
    unittest.main()
