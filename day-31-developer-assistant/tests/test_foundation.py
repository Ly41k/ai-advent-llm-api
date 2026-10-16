import dataclasses
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bublik_developer.contracts import AgentResult, ContextEnvelope, Role, TaskEnvelope, TaskStatus
from bublik_developer.errors import DeveloperError, ErrorCode
from bublik_developer.policy import authorize
from bublik_developer.preflight import API_LABEL, DoctorFailure, check_day30_off, day30_process, launchd_check, process_check
from bublik_developer.process import minimal_env, run_bounded
from bublik_developer.workspace import ProjectWorkspace

ROOT = Path(__file__).resolve().parents[1]


class ContractsTests(unittest.TestCase):
    def test_context_snapshot_survives_caller_mutation(self):
        source = {"question": "архитектура", "snippets": [1]}
        context = ContextEnvelope.seal(source)
        source["snippets"].append(2)
        self.assertEqual(context.open()["snippets"], [1])
        context.open()["snippets"].append(3)
        self.assertEqual(context.open()["snippets"], [1])

    def test_context_budget_nonfinite_and_tampering(self):
        for source in ({"v": float("nan")}, {"v": object()}):
            with self.assertRaises(DeveloperError):
                ContextEnvelope.seal(source)
        with self.assertRaises(DeveloperError) as caught:
            ContextEnvelope.seal({"text": "x" * 100}, max_bytes=10)
        self.assertEqual(caught.exception.code, ErrorCode.CONTEXT_BUDGET)
        original = ContextEnvelope.seal({"v": 1})
        with self.assertRaises(DeveloperError):
            dataclasses.replace(original, payload_json='{"v":2}').open()

    def test_tasks_reject_recursion_and_invalid_budgets(self):
        task = TaskEnvelope.create(Role.GIT, "project", "branch", {})
        for values in ({"delegation_depth": 2}, {"timeout_seconds": float("inf")},
                       {"max_tool_calls": 9}, {"role": "git"}):
            with self.assertRaises(DeveloperError):
                dataclasses.replace(task, **values)

    def test_result_distinguishes_refusal_from_failure(self):
        task = TaskEnvelope.create(Role.DOCUMENTATION, "project", "query", {})
        result = AgentResult(task.task_id, TaskStatus.SUCCESS, "insufficient_evidence", ContextEnvelope.seal({}))
        self.assertIsNone(result.error_code)
        with self.assertRaises(DeveloperError):
            AgentResult(task.task_id, TaskStatus.FAILED, "error", ContextEnvelope.seal({}))

    def test_wrong_role_and_unsupported_write_tools_are_denied(self):
        for role, name in ((Role.DOCUMENTATION, "git_status"), (Role.MAIN, "git_status"), (Role.GIT, "git_push")):
            with self.assertRaises(DeveloperError) as caught:
                authorize(role, name, {})
            self.assertEqual(caught.exception.code, ErrorCode.PERMISSION_DENIED)

    def test_invalid_diff_arguments_never_reach_execution(self):
        bad = [{"scope": "--cached"}, {"root": "/tmp"}, {"paths": ["../README.md"]},
               {"paths": ["a.md", "a.md"]}, {"paths": [None]}, {"paths": [{}]},
               {"include_content": True}, {"include_content": "true"}]
        for arguments in bad:
            with self.subTest(arguments=arguments), self.assertRaises(DeveloperError):
                authorize(Role.GIT, "git_diff", arguments)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "проект с пробелом"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.workspace = ProjectWorkspace.open(self.root, "portable-id")

    def test_canonical_root_and_explicit_portable_id(self):
        self.assertEqual(self.workspace.project_id, "portable-id")
        sub = self.root / "src"
        sub.mkdir()
        with self.assertRaises(DeveloperError):
            ProjectWorkspace.open(sub)

    def test_traversal_absolute_and_secret_paths(self):
        for value in ("../x", "/tmp/x", "src/../../x", "src\\x", ".env", "keys/access.key", "secrets/key.py"):
            with self.subTest(value=value), self.assertRaises(DeveloperError):
                self.workspace.path(value, missing=True)

    def test_symlink_outside_and_inside_are_rejected(self):
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("private")
        (self.root / "escape.md").symlink_to(outside)
        (self.root / "real.md").write_text("inside")
        (self.root / "inside.md").symlink_to(self.root / "real.md")
        for value in ("escape.md", "inside.md"):
            with self.assertRaises(DeveloperError):
                self.workspace.path(value, content=True)

    def test_root_replacement_invalidates_workspace(self):
        self.root.rename(self.root.with_name("original"))
        self.root.mkdir()
        with self.assertRaises(DeveloperError) as caught:
            self.workspace.check()
        self.assertEqual(caught.exception.code, ErrorCode.WORKSPACE_CHANGED)

    def test_content_allowlist_is_narrower_than_metadata(self):
        (self.root / "settings.json").write_text("{}")
        self.workspace.path("settings.json")
        with self.assertRaises(DeveloperError):
            self.workspace.path("settings.json", content=True)


class SubprocessTests(unittest.TestCase):
    def test_system_admin_tools_are_on_minimal_path(self):
        with patch("bublik_developer.process.os.defpath", "/bin:/usr/bin"):
            paths = minimal_env()["PATH"].split(":")
        self.assertIn("/usr/sbin", paths)
        self.assertIn("/sbin", paths)
        self.assertNotIn("", paths)
        self.assertNotIn(".", paths)

    def test_timeout_cleans_owned_process(self):
        with self.assertRaises(DeveloperError) as caught:
            run_bounded([sys.executable, "-c", "import time; time.sleep(10)"], timeout=.1)
        self.assertEqual(caught.exception.code, ErrorCode.TIMEOUT)

    def test_output_bound_applies_while_reading(self):
        with self.assertRaises(DeveloperError) as caught:
            run_bounded([sys.executable, "-c", "import sys; sys.stdout.write('x'*1000000)"], limit=1000)
        self.assertEqual(caught.exception.code, ErrorCode.OUTPUT_LIMIT)


class PreflightTests(unittest.TestCase):
    def test_supported_day30_launchers(self):
        for value in ("/usr/bin/python3.13 -m bublik_service --db somewhere serve", "uvicorn bublik_service.http_api:app",
                      "python /project/day-30-private-ai-service/scripts/check_inference_live.py"):
            self.assertTrue(day30_process(value))
        self.assertFalse(day30_process("python -m bublik_developer doctor"))
        self.assertFalse(day30_process("bash -c echo unbalanced'"))

    def test_ps_display_quotes_do_not_require_shell_parsing(self):
        self.assertFalse(day30_process("python -c print(\"it's unrelated\")"))
        self.assertTrue(day30_process("python -m bublik_service serve --db /Users/O'Brien/chats.sqlite3"))

    def test_comm_separates_executable_from_display_arguments(self):
        responses = [(0, b"9001 /Applications/Code Helper\n9002 /Users/Test Name/venv/bin/python3.13\n", b""),
                     (0, b"/Users/Test Name/venv/bin/python3.13 -m bublik_service serve\n", b"")]
        with patch("bublik_developer.preflight.executable", return_value="/bin/ps"), \
             patch("bublik_developer.preflight.run_bounded", side_effect=responses):
            self.assertEqual(process_check(), 1)

    def test_failure_reports_all_probe_statuses_without_raw_process_data(self):
        with patch("bublik_developer.preflight.process_check", side_effect=DeveloperError(ErrorCode.ISOLATION_UNVERIFIED)), \
             patch("bublik_developer.preflight.launchd_check", return_value={"loaded": False}), \
             patch("bublik_developer.preflight.port_check", return_value=False):
            with self.assertRaises(DoctorFailure) as caught:
                check_day30_off()
            checks = caught.exception.checks
            self.assertEqual(checks["processes"]["status"], "unverified")
            self.assertEqual(checks["launchd"]["status"], "passed")
            self.assertEqual(checks["loopback_port_8000"]["status"], "passed")

    def test_autostart_not_disabled_stays_blocked_with_specific_reason(self):
        responses = [(113, b"", b"Could not find service"), (0, ('"' + API_LABEL + '" => false').encode(), b"")]
        with patch("bublik_developer.preflight.platform.system", return_value="Darwin"), \
             patch("bublik_developer.preflight.executable", return_value="/bin/launchctl"), \
             patch("bublik_developer.preflight.Path.exists", return_value=True), \
             patch("bublik_developer.preflight.run_bounded", side_effect=responses):
            with self.assertRaises(DeveloperError) as caught:
                launchd_check()
            self.assertEqual(caught.exception.diagnostic["reason"], "launchd_autostart_not_disabled")

    def test_loaded_launchd_job_is_detected(self):
        with patch("bublik_developer.preflight.platform.system", return_value="Darwin"), \
             patch("bublik_developer.preflight.executable", return_value="/bin/launchctl"), \
             patch("bublik_developer.preflight.run_bounded", return_value=(0, b"loaded", b"")):
            self.assertTrue(launchd_check()["loaded"])

    def test_disabled_unloaded_job_is_accepted(self):
        responses = [(113, b"", b"Could not find service"), (0, ('"' + API_LABEL + '" => true').encode(), b"")]
        with patch("bublik_developer.preflight.platform.system", return_value="Darwin"), \
             patch("bublik_developer.preflight.executable", return_value="/bin/launchctl"), \
             patch("bublik_developer.preflight.Path.exists", return_value=True), \
             patch("bublik_developer.preflight.run_bounded", side_effect=responses):
            result = launchd_check()
            self.assertFalse(result["loaded"])
            self.assertTrue(result["disabled"])

    def test_launchctl_word_and_boolean_formats(self):
        for state in ("disabled", "true", "enabled", "false"):
            text = 'disabled services = {\n  "' + API_LABEL + '" => ' + state + '\n}\n'
            responses = [(113, b"", b"Could not find service"), (0, text.encode(), b"")]
            with self.subTest(state=state), \
                 patch("bublik_developer.preflight.platform.system", return_value="Darwin"), \
                 patch("bublik_developer.preflight.executable", return_value="/bin/launchctl"), \
                 patch("bublik_developer.preflight.Path.exists", return_value=True), \
                 patch("bublik_developer.preflight.run_bounded", side_effect=responses):
                if state in {"disabled", "true"}:
                    self.assertTrue(launchd_check()["disabled"])
                else:
                    with self.assertRaises(DeveloperError) as caught:
                        launchd_check()
                    self.assertEqual(caught.exception.diagnostic["reason"], "launchd_autostart_not_disabled")

    def test_launchctl_ambiguous_unknown_and_other_labels_are_rejected(self):
        outputs = ['"' + API_LABEL + '.other" => disabled', '"' + API_LABEL + '" => unknown',
                   '"' + API_LABEL + '" => disabled_extra',
                   '"' + API_LABEL + '" => disabled\n"' + API_LABEL + '" => enabled']
        for text in outputs:
            responses = [(113, b"", b"Could not find service"), (0, text.encode(), b"")]
            with self.subTest(text=text), \
                 patch("bublik_developer.preflight.platform.system", return_value="Darwin"), \
                 patch("bublik_developer.preflight.executable", return_value="/bin/launchctl"), \
                 patch("bublik_developer.preflight.Path.exists", return_value=True), \
                 patch("bublik_developer.preflight.run_bounded", side_effect=responses):
                with self.assertRaises(DeveloperError) as caught:
                    launchd_check()
                self.assertEqual(caught.exception.diagnostic["reason"], "launchd_disabled_state_unknown")

    def test_loaded_process_or_unverified_launchd_blocks_check(self):
        with patch("bublik_developer.preflight.process_check", return_value=1), \
             patch("bublik_developer.preflight.launchd_check", return_value={"loaded": False}), \
             patch("bublik_developer.preflight.port_check", return_value=False):
            with self.assertRaises(DeveloperError) as caught:
                check_day30_off()
            self.assertEqual(caught.exception.code, ErrorCode.SERVICE_ACTIVE)
        with patch("bublik_developer.preflight.platform.system", return_value="Darwin"), \
             patch("bublik_developer.preflight.executable", return_value="/bin/launchctl"), \
             patch("bublik_developer.preflight.run_bounded", return_value=(1, b"", b"permission denied")):
            with self.assertRaises(DeveloperError):
                launchd_check()

    def test_real_listening_socket_blocks_check(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            with patch("bublik_developer.preflight.process_check", return_value=0), \
                 patch("bublik_developer.preflight.launchd_check", return_value={"loaded": False}):
                with self.assertRaises(DeveloperError) as caught:
                    check_day30_off([port])
                self.assertEqual(caught.exception.code, ErrorCode.SERVICE_ACTIVE)

    def test_service_off_does_not_claim_ollama_idle(self):
        with patch("bublik_developer.preflight.process_check", return_value=0), \
             patch("bublik_developer.preflight.launchd_check", return_value={"loaded": False}), \
             patch("bublik_developer.preflight.port_check", return_value=False):
            result = check_day30_off()
            self.assertTrue(result["day30_off"])
            self.assertFalse(result["ollama_idle_verified"])
            self.assertIn(8000, result["checked_loopback_ports"])


class CLITests(unittest.TestCase):
    def test_model_command_preserves_day30_probe_diagnostics(self):
        from bublik_developer.cli import main
        checks = {"processes": {"status": "unverified", "diagnostic": {"reason": "process_table_malformed"}}}
        output = io.StringIO()
        with patch("bublik_developer.cli.rag_command", side_effect=DoctorFailure(ErrorCode.ISOLATION_UNVERIFIED, checks)), redirect_stdout(output):
            code = main(["models", "prepare"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["probes"], checks)

    def test_bare_help_without_site_packages_or_git(self):
        command = [sys.executable, "-S", str(ROOT / "main.py"), "/help"]
        result = subprocess.run(command, cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertIn("/help branch", result.stdout)

    def test_documentation_help_uses_the_project_pipeline(self):
        from bublik_developer.cli import main
        from unittest.mock import AsyncMock
        output = io.StringIO()
        result = {"execution_status": "completed", "answer_status": "unknown"}
        with patch("bublik_developer.cli.pipeline_request", new=AsyncMock(return_value=result)) as mocked, redirect_stdout(output):
            code = main(["/help", "Как устроена память?"])
        self.assertEqual(code, 0)
        self.assertEqual(mocked.call_args.args[1], "Как устроена память?")
        self.assertEqual(json.loads(output.getvalue()), result)


if __name__ == "__main__":
    unittest.main()
