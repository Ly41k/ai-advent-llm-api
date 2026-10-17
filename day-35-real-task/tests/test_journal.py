"""Offline tests on disposable synthetic Git history. No real LLM calls."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace

spec = importlib.util.spec_from_file_location("journal", Path(__file__).parents[1] / "main.py")
j = importlib.util.module_from_spec(spec)
spec.loader.exec_module(j)


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.metadata = []
        self.metadata_patch = patch.object(j, "github_pr_metadata", side_effect=lambda: list(self.metadata))
        self.metadata_patch.start()
        self.addCleanup(self.metadata_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "Imperz"
        self.repo.mkdir()
        self.g("init", "-b", "main")
        self.g("config", "user.email", "fixture@example.invalid")
        self.g("config", "user.name", "Synthetic fixture")
        self.g("remote", "add", "origin", j.BASE + ".git")
        (self.repo / "README.md").write_text("Synthetic public fixture, no game data.\n")
        self.g("add", ".")
        self.g("commit", "-m", "init", at="2026-10-12T10:00:00Z")
        self.initial = self.g("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.tmp.cleanup()

    def g(self, *args, at="2026-10-13T10:00:00Z"):
        p = subprocess.run(["git", "-C", str(self.repo), *args],
                           env=dict(os.environ, GIT_AUTHOR_DATE=at, GIT_COMMITTER_DATE=at),
                           capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(p.stderr)
        return p.stdout

    def merge(self, n=7, at="2026-10-13T21:01:00Z", name=None):
        branch = f"feature-{n}"
        self.g("checkout", "-b", branch)
        path = self.repo / (name or f"document-{n}.ru.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Synthetic change {n}\nA documentation update, not game mechanics.\n")
        self.g("add", ".")
        self.g("commit", "-m", f"fixture {n}", at="2026-10-12T12:00:00Z")
        self.g("checkout", "main")
        self.g("merge", "--no-ff", branch, "-m", f"Merge pull request #{n} from fixture/{branch}\n\nUpdate synthetic documentation", at=at)
        commit = self.g("rev-parse", "HEAD").strip()
        self.metadata.append(self.pr_metadata(n, commit, at))
        return commit

    def pr_metadata(self, number, commit, at):
        return {"number": number, "state": "closed", "merged_at": at, "merge_commit_sha": commit,
                "base_ref": "main", "base_repository": j.REPO, "html_url": f"{j.BASE}/pull/{number}"}

    def collect(self, expect=None, day="2026-10-14"):
        return j.collect(self.repo, day, "main", expect or [])

    def valid_text(self, evidence):
        lines = ["# Журнал разработки — 14.10.2026", "", "## Краткие итоги"]
        url = evidence["events"][0]["source_urls"][0]
        lines.append(f"Обновлена документация проекта; это синтетический пример для проверки программы. [Источник]({url})")
        lines += ["", "## Подтверждённые изменения"]
        for event in evidence["events"]:
            url = event["source_urls"][0]
            lines.append(f"- Уточнено описание документа, изменения включены в основную ветку. [PR #{event['pr_number']}]({url})")
        lines += ["", "## Результат дня", f"Подготовлены уточнения спецификации; реализация игрового движка здесь не заявляется. [Источник]({url})"]
        return "\n".join(lines)

    def args(self, run_id="test", expected=None, collect_only=False):
        return Namespace(repo=self.repo, date="2026-10-14", ref="main", expect_pr=expected or [],
                         model=j.MODEL, timeout=2, out=self.root / "private" / "results", run_id=run_id,
                         collect_only=collect_only)

    def pipeline(self, args, text=None, done_reason="stop"):
        def fake_http(path, payload=None, timeout=20):
            if path == "/api/tags":
                return 200, j.encoded({"models": [{"name": j.MODEL, "digest": "fixture-only",
                                                 "details": {"quantization_level": "Q4_K_M"}}]})
            self.assertEqual(path, "/api/chat")
            return 200, j.encoded({"model": j.MODEL, "done": True, "done_reason": done_reason,
                                   "message": {"content": text or self.valid_text(self.collect())}})
        with patch.object(j, "http", side_effect=fake_http) as mock, contextlib.redirect_stdout(io.StringIO()):
            result = j.run_pipeline(args)
        return result, mock

    def test_merge_date_kyiv_ignores_branch_date_and_excludes_next_day(self):
        included = self.merge(7, "2026-10-13T21:01:00Z")
        self.merge(8, "2026-10-14T21:01:00Z")
        ev = self.collect([7])
        self.assertEqual([e["pr_number"] for e in ev["events"]], [7])
        self.assertEqual(ev["events"][0]["commit_sha"], included)
        self.assertEqual(ev["source_main_sha"], self.g("rev-parse", "main").strip())

    def test_unmerged_branch_not_in_day(self):
        self.g("checkout", "-b", "closed-unmerged")
        (self.repo / "unmerged.md").write_text("Not included.")
        self.g("add", ".")
        self.g("commit", "-m", "PR #999 closed", at="2026-10-14T10:00:00Z")
        self.g("checkout", "main")
        self.metadata.append(self.pr_metadata(999, self.initial, None))
        self.assertEqual(self.collect()["events"], [])

    def test_controls_missing_before_generation(self):
        self.merge()
        with patch.object(j, "http") as mock:
            with self.assertRaises(j.Stop):
                j.run_pipeline(self.args(expected=[111]))
            mock.assert_not_called()

    def test_no_changes_never_generate_journal(self):
        with patch.object(j, "http") as mock, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(j.run_pipeline(self.args()), 0)
            mock.assert_not_called()
        self.assertFalse((self.args().out / "test" / "development-journal.ru.md").exists())

    def test_source_worktree_refs_and_index_unchanged(self):
        self.merge()
        (self.repo / "untracked.txt").write_text("User-owned untracked content.")
        (self.repo / "README.md").write_text("User-owned uncommitted changes.")
        index = (self.repo / ".git/index").read_bytes()
        before = j.snapshot(self.repo)
        self.collect()
        self.assertEqual(j.snapshot(self.repo), before)
        self.assertEqual((self.repo / ".git/index").read_bytes(), index)

    def test_checkout_root_accepts_symlink_alias(self):
        self.merge()
        alias = self.root / "Imperz-alias"
        alias.symlink_to(self.repo, target_is_directory=True)
        evidence = j.collect(alias, "2026-10-14", "main", [7])
        self.assertEqual([e["pr_number"] for e in evidence["events"]], [7])

    def test_checkout_subdirectory_still_refused(self):
        nested = self.repo / "docs"
        nested.mkdir()
        with self.assertRaises(j.Stop):
            j.check_repo(nested)

    def test_direct_commit_is_recorded_without_asserting_day_of_incorporation(self):
        (self.repo / "README.md").write_text("direct")
        self.g("add", ".")
        self.g("commit", "-m", "update (#7)", at="2026-10-14T10:00:00Z")
        commit = self.g("rev-parse", "HEAD").strip()
        evidence = self.collect()
        self.assertEqual(evidence["events"], [])
        self.assertIn(commit, evidence["unattributed_committer_date_candidates"])

    def test_context_is_bounded_and_changes_are_real(self):
        self.merge(name="large.ru.md")
        # Increase a diff without changing the supported merge provenance.
        self.g("checkout", "-b", "large")
        (self.repo / "large.ru.md").write_text("Private text.\n" * 20000)
        self.g("add", ".")
        self.g("commit", "-m", "large")
        self.g("checkout", "main")
        self.g("merge", "--no-ff", "large", "-m", "Merge pull request #8 from fixture/large", at="2026-10-14T10:00:00Z")
        self.metadata.append(self.pr_metadata(8, self.g("rev-parse", "HEAD").strip(), "2026-10-14T10:00:00Z"))
        ev = self.collect()
        self.assertLessEqual(ev["context_chars"], j.MAX_CONTEXT)
        self.assertGreater(ev["events"][1]["documents"][0]["omitted_chars"], 0)
        self.assertIn("Private text.", ev["context"])

    def test_allowed_links_valid_and_unknown_pr_commit_url_fail(self):
        self.merge()
        ev = self.collect()
        text = self.valid_text(ev)
        self.assertTrue(j.validate(text, ev)["passed"])
        for extra in (" PR #888", " abcdef0123", " https://evil.invalid/a", " [fake](local.md)"):
            self.assertFalse(j.validate(text + extra, ev)["passed"], extra)

    def test_unsourced_claim_and_missing_event_fail(self):
        self.merge(7)
        self.merge(8, "2026-10-14T10:00:00Z")
        ev = self.collect()
        self.assertFalse(j.validate(self.valid_text(ev) + "\nНеподтверждённое утверждение", ev)["passed"])
        text = self.valid_text(ev).replace(ev["events"][1]["source_urls"][0], ev["events"][0]["source_urls"][0])
        self.assertFalse(j.validate(text, ev)["passed"])

    def test_one_generation_and_human_review_pending(self):
        self.merge()
        code, mock = self.pipeline(self.args())
        self.assertEqual(code, 0)
        self.assertEqual(sum(c.args[0] == "/api/chat" for c in mock.call_args_list), 1)
        result = j.load(self.args().out / "test/acceptance.json")
        self.assertEqual(result["technical"], "PASS")
        self.assertEqual(result["ai_generation_evidence"], "PASS")
        self.assertEqual(result["human_review"]["status"], "PENDING")
        self.assertNotEqual(result["course_minimum"], "PASS")

    def test_edited_journal_invalidates_generation_and_human_review(self):
        self.merge()
        self.pipeline(self.args())
        run = self.args().out / "test"
        a = j.load(run / "acceptance.json")
        a["human_review"] = {"status": "PASS", "reviewed_hashes": a["artifact_sha256"]}
        j.write_json(run / "acceptance.json", a)
        self.assertEqual(j.acceptance(run)["course_minimum"], "PASS")
        with (run / "development-journal.ru.md").open("a") as f:
            f.write("\nEdited outside the model.")
        a = j.acceptance(run)
        self.assertEqual(a["human_review"]["status"], "PENDING")
        self.assertNotEqual(a["ai_generation_evidence"], "PASS")

    def test_truncated_llm_response_not_accepted(self):
        self.merge()
        code, _ = self.pipeline(self.args(), done_reason="length")
        self.assertEqual(code, 2)

    def test_output_inside_source_refused(self):
        a = self.args()
        a.out = self.repo / "results"
        with self.assertRaises(j.Stop):
            j.run_pipeline(a)
        self.assertFalse(a.out.exists())

    def test_remote_model_and_wrong_quant_refused(self):
        with self.assertRaises(j.Stop):
            j.model_info("cloud:14b")
        with patch.object(j, "http", return_value=(200, j.encoded({"models": [{"name": j.MODEL, "details": {"quantization_level": "Q8_0"}}]}))):
            with self.assertRaises(j.Stop):
                j.model_info(j.MODEL)

    def test_http_error_preserved_without_retry(self):
        self.merge()
        from urllib.error import HTTPError
        with patch.object(j, "model_info", return_value={}), patch.object(j, "http", side_effect=HTTPError(j.OLLAMA, 500, "fixture", {}, None)) as mock:
            with self.assertRaises(j.Stop), contextlib.redirect_stdout(io.StringIO()):
                j.run_pipeline(self.args())
        self.assertEqual(mock.call_count, 1)
        proof = j.load(self.args().out / "test/generation.json")
        self.assertEqual(proof["http_status"], 500)
        self.assertEqual(proof["generation_calls"], 1)

    def test_existing_run_not_overwritten(self):
        self.merge()
        a = self.args(collect_only=True)
        with contextlib.redirect_stdout(io.StringIO()):
            j.run_pipeline(a)
        with self.assertRaises(FileExistsError):
            j.run_pipeline(a)

    def test_changed_source_during_generation_stays_failed_on_offline_verify(self):
        self.merge()
        self.pipeline(self.args())
        run = self.args().out / "test"
        altered = dict(j.snapshot(self.repo), head="0" * 40)
        self.assertFalse(j.acceptance(run, altered)["imperz_unchanged_during_run"])
        self.assertFalse(j.acceptance(run)["imperz_unchanged_during_run"])

    def test_summary_excludes_private_text_and_source_sha(self):
        self.merge()
        self.pipeline(self.args())
        run = self.args().out / "test"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(j.main(["summary", str(run)]), 0)
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["http_status"], 200)
        self.assertNotIn(j.load(run / "evidence.json")["source_main_sha"], output.getvalue())
        self.assertNotIn("diff_excerpt", output.getvalue())

    def test_context_and_evidence_cannot_diverge(self):
        self.merge()
        self.pipeline(self.args())
        run = self.args().out / "test"
        evidence = j.load(run / "evidence.json")
        evidence["events"][0]["message"] = "Edited evidence outside actual prompt."
        j.write_json(run / "evidence.json", evidence)
        self.assertNotEqual(j.acceptance(run)["ai_generation_evidence"], "PASS")

    def test_github_merge_date_overrides_git_committer_date(self):
        self.merge(7, at="2026-10-13T10:00:00Z")
        self.metadata[0]["merged_at"] = "2026-10-13T21:00:01Z"
        evidence = self.collect([7])
        self.assertEqual(len(evidence["events"]), 1)
        self.assertEqual(evidence["events"][0]["local_date"], "2026-10-14")

    def test_squash_metadata_and_local_delta(self):
        (self.repo / "squash.ru.md").write_text("Synthetic squash documentation change.\n")
        self.g("add", ".")
        self.g("commit", "-m", "Update synthetic documentation (#8)", at="2026-10-14T12:00:00Z")
        commit = self.g("rev-parse", "HEAD").strip()
        self.metadata.append(self.pr_metadata(8, commit, "2026-10-14T12:00:03Z"))
        evidence = self.collect([8])
        event = evidence["events"][0]
        self.assertEqual(event["merge_shape"], "squash_commit")
        self.assertEqual(event["parents"], [self.initial])
        self.assertIn("Synthetic squash documentation change", event["documents"][0]["diff_excerpt"])

    def test_pr_missing_from_local_main_refused(self):
        self.merge()
        self.metadata[0]["merge_commit_sha"] = "f" * 40
        with self.assertRaises(j.Stop):
            self.collect()

    def test_pr_metadata_number_must_match_commit(self):
        self.merge()
        self.metadata[0]["number"] = 8
        self.metadata[0]["html_url"] = f"{j.BASE}/pull/8"
        with self.assertRaises(j.Stop):
            self.collect()

    def test_closed_without_merge_does_not_satisfy_control(self):
        self.merge()
        self.metadata[0]["merged_at"] = None
        with self.assertRaises(j.Stop):
            self.collect([7])

    def test_format_fix_includes_full_links_for_every_event(self):
        self.merge(7)
        self.merge(8, "2026-10-14T10:00:00Z")
        evidence = self.collect()
        messages = j.generation_messages(evidence, 2)
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[1]["content"], evidence["context"])
        for event in evidence["events"]:
            self.assertIn(f"[PR #{event['pr_number']}]({event['source_urls'][0]})", messages[2]["content"])
        self.assertNotIn("diff_excerpt", messages[2]["content"])

    def test_historical_v3_two_message_request_still_verifies(self):
        self.merge()
        self.pipeline(self.args())
        run = self.args().out / "test"
        payload = j.load(run / "ollama-request.json")
        payload["messages"] = payload["messages"][:2]
        j.write_json(run / "ollama-request.json", payload)
        proof = j.load(run / "generation.json")
        proof.pop("prompt_version")
        proof["request_sha256"] = j.sha((run / "ollama-request.json").read_bytes())
        j.write_json(run / "generation.json", proof)
        self.assertEqual(j.acceptance(run)["ai_generation_evidence"], "PASS")


class MetadataTransport(unittest.TestCase):
    def test_get_only_pagination_returns_metadata(self):
        first = "\n".join(json.dumps({"number": n}) for n in range(100))
        second = json.dumps({"number": 100})
        replies = [subprocess.CompletedProcess([], 0, first, ""), subprocess.CompletedProcess([], 0, second, "")]
        with patch.object(j.subprocess, "run", side_effect=replies) as mocked:
            rows = j.github_pr_metadata()
        self.assertEqual(len(rows), 101)
        for call in mocked.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:6], ["gh", "api", "--hostname", "github.com", "--method", "GET"])
            self.assertIn("--jq", command)
        self.assertIn("page=2", mocked.call_args_list[1].args[0][6])

    def test_read_failure_is_sanitized(self):
        with patch.object(j.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "private server error")):
            with self.assertRaises(j.Stop) as caught:
                j.github_pr_metadata()
        self.assertNotIn("private server error", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
