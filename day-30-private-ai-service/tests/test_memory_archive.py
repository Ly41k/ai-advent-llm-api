"""Real SQLite, files and separate processes; no inference or production DB."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import memory_archive as archive
from bublik_service.domain import ContextPlan, ServiceError
from bublik_service.storage import ChatRepository


class MemoryArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.db = self.root / "source.sqlite3"
        self.repo = ChatRepository(self.db)
        self.owner = self.repo.create_user("operator", "synthetic-password-hash")
        self.other = self.repo.create_user("other", "other-synthetic-hash")
        self.chat = self.repo.create_chat(self.owner, "История", key="create-chat").chat_id
        self.plan = ContextPlan(input_token_upper_bound=100)
        self.receipt = self.repo.accept_message(self.owner, self.chat, "Привет\n", expected_revision=0,
                                               key="first", context=self.plan)
        with self.repo.worker_session() as worker:
            worker.claim_next()
            worker.finish(self.receipt.generation_id, content="Здравствуйте!\n")
        second = self.repo.create_chat(self.other, "Partial", key="other-chat").chat_id
        receipt = self.repo.accept_message(self.other, second, "Question", expected_revision=0,
                                          key="partial", context=self.plan)
        with self.repo.worker_session() as worker:
            worker.claim_next()
            worker.checkpoint(receipt.generation_id, "Saved partial")
            worker.finish(receipt.generation_id, status="failed", error_code="invalid_model_response")
        with self.repo.database.connect(write=True) as db:
            db.execute("INSERT INTO browser_sessions VALUES (?,?,?,?,?)",
                       ("session-hash", self.owner, "csrf", 1.0, 9999999999.0))
            db.execute("INSERT INTO api_tokens VALUES (?,?,?,?,?,?,?,?)",
                       ("token-id", self.owner, "token-hash", "personal", '["chats:read"]', 1.0, 9999999999.0, 0))
        self.folder = self.root / "archive"
        self.target = self.root / "new-host" / "restored.sqlite3"

    def create(self):
        return archive.create_archive(self.db, self.folder)

    def assert_code(self, code, call):
        with self.assertRaises(ServiceError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def rewrite_manifest(self, change):
        path = self.folder / archive.MANIFEST
        data = json.loads(path.read_text())
        change(data)
        path.write_bytes(archive.canonical(data))

    def test_wal_snapshot_preserves_every_table_and_original_source(self):
        # Keep a reader alive so committed changes remain in a real WAL.
        with closing(sqlite3.connect(self.db)) as pinned:
            pinned.execute("BEGIN")
            pinned.execute("SELECT count(*) FROM users").fetchone()
            self.repo.create_chat(self.owner, "Committed WAL chat", key="wal")
            self.assertGreater(Path(str(self.db) + "-wal").stat().st_size, 0)
            before = self.repo.export_chat(self.owner, self.chat)
            result = self.create()
            self.assertTrue(result["restorable_now"])
            with closing(sqlite3.connect(self.folder / archive.DATABASE)) as backup:
                self.assertEqual(backup.execute("SELECT count(*) FROM chats").fetchone()[0], 3)
            self.assertEqual(before, self.repo.export_chat(self.owner, self.chat))
            self.assertEqual(set(p.name for p in self.folder.iterdir()), {archive.MANIFEST, archive.DATABASE})

    def test_restore_keeps_history_ids_snapshots_receipts_and_ownership(self):
        before = self.repo.export_chat(self.owner, self.chat)
        self.create()
        original_hash = archive.digest(self.folder / archive.DATABASE)
        restored = archive.restore_archive(self.folder, self.target)
        self.assertTrue(restored["history_tables_unchanged"])
        other = ChatRepository(self.target)
        self.assertEqual(other.export_chat(self.owner, self.chat), before)
        replay = other.accept_message(self.owner, self.chat, "Привет\n", expected_revision=0,
                                      key="first", context=self.plan)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.generation_id, self.receipt.generation_id)
        self.assertEqual(len(other.history(self.owner, self.chat)), 2)
        self.assertEqual(original_hash, archive.digest(self.folder / archive.DATABASE))
        self.assertEqual(archive.verify_archive(self.folder)["status"], "verified")

    def test_auth_revoked_only_in_restored_copy_passwords_kept(self):
        self.create()
        archive.restore_archive(self.folder, self.target)
        for path, expected_sessions, expected_revoked in [(self.db, 1, 0), (self.target, 0, 1)]:
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM browser_sessions").fetchone()[0], expected_sessions)
                self.assertEqual(db.execute("SELECT revoked FROM api_tokens").fetchone()[0], expected_revoked)
                self.assertEqual(db.execute("SELECT password_hash FROM users WHERE id=?", (self.owner,)).fetchone()[0],
                                 "synthetic-password-hash")

    def test_continue_restored_chat_without_changing_source(self):
        original = self.repo.export_chat(self.owner, self.chat)
        self.create()
        archive.restore_archive(self.folder, self.target)
        restored = ChatRepository(self.target)
        receipt = restored.accept_message(self.owner, self.chat, "Next question", expected_revision=2,
                                          key="second", context=self.plan)
        with restored.worker_session() as worker:
            self.assertEqual(worker.claim_next()["id"], receipt.generation_id)
            worker.finish(receipt.generation_id, content="New answer")
        self.assertEqual(len(restored.history(self.owner, self.chat)), 4)
        self.assertEqual(self.repo.export_chat(self.owner, self.chat), original)

    def test_permission_and_manifest_do_not_include_dialogue_or_secret_fields(self):
        self.create()
        self.assertEqual(self.folder.stat().st_mode & 0o777, 0o700)
        for member in self.folder.iterdir():
            self.assertEqual(member.stat().st_mode & 0o777, 0o600)
        manifest = (self.folder / archive.MANIFEST).read_text()
        for value in ["Здравствуйте", "synthetic-password-hash", "Saved partial", "session-hash", "token-hash"]:
            self.assertNotIn(value, manifest)

    def test_repeated_create_never_changes_existing_archive(self):
        self.create()
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        self.assert_code("archive_destination_exists", self.create)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.folder.iterdir()})

    def test_restore_rejects_existing_db_or_orphan_sidecar(self):
        self.create()
        self.target.parent.mkdir(mode=0o700)
        for suffix in ("", *archive.SIDECARS):
            with self.subTest(suffix=suffix):
                path = Path(str(self.target) + suffix)
                path.write_bytes(b"do not overwrite")
                self.assert_code("restore_destination_exists_or_protected",
                                 lambda: archive.restore_archive(self.folder, self.target))
                self.assertEqual(path.read_bytes(), b"do not overwrite")
                path.unlink()

    def test_restore_publication_race_keeps_other_file_and_cleans_temporary(self):
        self.create()
        real_link = os.link
        def race(source, target):
            Path(target).write_bytes(b"other writer")
            real_link(source, target)
        with patch.object(archive.os, "link", side_effect=race):
            with self.assertRaises(FileExistsError):
                archive.restore_archive(self.folder, self.target)
        self.assertEqual(self.target.read_bytes(), b"other writer")
        self.assertEqual(list(self.target.parent.glob(".bublik-restore-*")), [])

    def test_corrupt_payload_is_rejected_before_creating_target(self):
        self.create()
        path = self.folder / archive.DATABASE
        with path.open("r+b") as db:
            db.seek(100)
            db.write(b"corruption")
        self.assert_code("archive_checksum_mismatch", lambda: archive.restore_archive(self.folder, self.target))
        self.assertFalse(self.target.parent.exists())

    def test_wrong_logical_manifest_is_rejected(self):
        self.create()
        self.rewrite_manifest(lambda d: d["state"]["tables"]["messages"].update(rows=10000))
        self.assert_code("archive_logical_mismatch", lambda: archive.verify_archive(self.folder))

    def test_duplicate_keys_and_oversize_manifest_are_rejected(self):
        self.create()
        path = self.folder / archive.MANIFEST
        path.write_text('{"format":"x","format":"y"}')
        self.assert_code("archive_manifest_invalid", lambda: archive.verify_archive(self.folder))
        path.write_bytes(b"x" * (archive.MAX_MANIFEST_BYTES + 1))
        self.assert_code("archive_manifest_invalid", lambda: archive.verify_archive(self.folder))

    def test_symlink_members_and_archive_or_target_are_rejected(self):
        self.create()
        self.target.parent.mkdir(mode=0o700)
        self.target.symlink_to(self.db)
        self.assert_code("archive_symlink_forbidden", lambda: archive.restore_archive(self.folder, self.target))
        self.assertTrue(self.db.is_file())
        alias = self.root / "alias"
        alias.symlink_to(self.folder, target_is_directory=True)
        self.assert_code("archive_symlink_forbidden", lambda: archive.verify_archive(alias))
        db = self.folder / archive.DATABASE
        db.rename(self.root / "payload")
        db.symlink_to(self.root / "payload")
        self.assert_code("archive_symlink_forbidden", lambda: archive.verify_archive(self.folder))

    def test_public_archive_or_member_are_rejected(self):
        self.create()
        self.folder.chmod(0o755)
        self.assert_code("archive_must_be_private", lambda: archive.verify_archive(self.folder))
        self.folder.chmod(0o700)
        (self.folder / archive.DATABASE).chmod(0o644)
        self.assert_code("archive_must_be_private", lambda: archive.verify_archive(self.folder))

    def test_unknown_members_including_sidecars_are_rejected(self):
        self.create()
        (self.folder / "snapshot.sqlite3-wal").write_bytes(b"unmerged data")
        self.assert_code("archive_members_invalid", lambda: archive.verify_archive(self.folder))

    def test_pending_or_uncertain_snapshot_is_preserved_but_not_replayed(self):
        for kind in ["queued", "running", "uncertain"]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve(); repo = ChatRepository(root / "source.sqlite3")
                owner = repo.create_user("owner", "synthetic")
                chat = repo.create_chat(owner, key="chat").chat_id
                receipt = repo.accept_message(owner, chat, "Question", expected_revision=0, key="m", context=self.plan)
                if kind != "queued":
                    with repo.worker_session() as worker:
                        worker.claim_next()
                        worker.checkpoint(receipt.generation_id, "partial survives")
                        if kind == "uncertain":
                            worker.finish(receipt.generation_id, status="interrupted", error_code="process_interrupted")
                result = archive.create_archive(root / "source.sqlite3", root / "archive")
                self.assertFalse(result["restorable_now"])
                self.assertEqual(archive.verify_archive(root / "archive")["status"], "verified")
                self.assert_code("restore_requires_idle_snapshot", lambda: archive.restore_archive(root / "archive", root / "new" / "db.sqlite3"))
                self.assertFalse((root / "new").exists())

    def test_foreign_or_changed_schema_is_not_migrated_by_create(self):
        with self.repo.database.connect(write=True) as db:
            db.execute("CREATE TABLE unknown_data (value TEXT)")
        before = self.repo.export_chat(self.owner, self.chat)
        self.assert_code("archive_incompatible_schema", self.create)
        self.assertFalse(self.folder.exists())
        self.assertEqual(self.repo.export_chat(self.owner, self.chat), before)

    def test_failure_during_snapshot_cleans_only_its_new_directory(self):
        with patch.object(archive, "inspect_snapshot", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.create()
        self.assertFalse(self.folder.exists())
        self.assertTrue(self.db.is_file())

    def test_cli_real_separate_process_transfer_and_error_diagnostics(self):
        def run(*args):
            return subprocess.run([sys.executable, str(ROOT / "scripts/memory_archive.py"), *map(str, args)],
                                  capture_output=True, text=True, timeout=30)
        for args in [("create", "--db", self.db, "--output", self.folder),
                     ("verify", "--archive", self.folder),
                     ("restore", "--archive", self.folder, "--db", self.target)]:
            result = run(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(json.loads(result.stdout)["status"], {"created", "verified", "restored"})
        repeated = run("restore", "--archive", self.folder, "--db", self.target)
        self.assertEqual(repeated.returncode, 1)
        self.assertEqual(json.loads(repeated.stdout)["error"], "restore_destination_exists_or_protected")
        self.assertNotIn("synthetic-password", repeated.stdout + repeated.stderr)


if __name__ == "__main__":
    unittest.main()
