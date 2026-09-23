"""No network or Groq usage; tests persistence, schedule, aggregation, MCP and agent."""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

from agent import BublikMcpAgent
from mcp_client import connect_mcp
from scheduler import Scheduler
from worker import run


class FakeApi:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def get_repository(self, owner, repo):
        self.calls += 1
        if self.fail:
            raise RuntimeError("API offline")
        return {"stars": 10 + self.calls, "forks": 2, "open_issues": 3 - self.calls}


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "schedule.db"
        self.now = datetime(2026, 9, 23, tzinfo=timezone.utc)
        self.api = FakeApi()
        self.scheduler = Scheduler(self.path, self.api, lambda: self.now)

    def test_schedule_runs_recurs_persists_and_aggregates(self):
        self.scheduler.schedule("Ly41k", "ai-advent-llm-api", 60)
        self.assertEqual(len(self.scheduler.jobs()), 1)
        self.assertEqual(self.scheduler.run_due()[0]["status"], "ok")
        self.assertEqual(self.scheduler.run_due(), [])
        self.now += timedelta(minutes=60)
        self.assertEqual(self.scheduler.run_due()[0]["status"], "ok")
        restored = Scheduler(self.path, self.api, lambda: self.now)
        summary = restored.summary("Ly41k", "ai-advent-llm-api")
        self.assertEqual(summary["samples"], 2)
        self.assertEqual(summary["latest"], {"stars": 12, "forks": 2, "open_issues": 1})
        self.assertEqual(summary["change"], {"stars": 1, "forks": 0, "open_issues": -1})
        self.assertEqual(restored.run_due(), [])

    def test_failure_persists_and_worker_recovers(self):
        self.scheduler.schedule("Ly41k", "test", 1)
        self.api.fail = True
        self.assertEqual(self.scheduler.run_due()[0]["status"], "error")
        self.assertEqual(self.scheduler.summary("Ly41k", "test")["samples"], 0)
        self.assertIn("API offline", self.scheduler.jobs()[0]["last_error"])
        self.now += timedelta(minutes=1)
        self.api.fail = False
        run(once=True, scheduler=self.scheduler)
        self.assertEqual(self.scheduler.summary("Ly41k", "test")["samples"], 1)
        self.assertIsNone(self.scheduler.jobs()[0]["last_error"])

    def test_validation(self):
        for value in (0, 10081, True, 1.2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.scheduler.schedule("Ly41k", "test", value)
        with self.assertRaises(RuntimeError):
            self.scheduler.schedule("bad/name", "test", 1)


class DemoCompletions:
    def create(self, **request):
        last_tool = next((m for m in reversed(request["messages"]) if m["role"] == "tool"), None)
        if last_tool is None:
            call = SimpleNamespace(id="1", function=SimpleNamespace(
                name="get_github_summary",
                arguments=json.dumps({"owner": "Ly41k", "repo": "test"})))
            message = SimpleNamespace(content=None, tool_calls=[call])
        else:
            summary = json.loads(last_tool["content"])
            message = SimpleNamespace(content=f"Stars: {summary['latest']['stars']}", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_schema_persistence_and_agent_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "schedule.db"
            with patch.dict(os.environ, {"BUBLIK_DB_PATH": str(path)}):
                async with connect_mcp() as session:
                    names = {tool.name: tool for tool in (await session.list_tools()).tools}
                    self.assertEqual(set(names), {"schedule_github_summary", "get_github_summary", "list_scheduled_jobs"})
                    self.assertIn("interval_minutes", names["schedule_github_summary"].inputSchema["properties"])
                    registered = await session.call_tool("schedule_github_summary", arguments={
                        "owner": "Ly41k", "repo": "test", "interval_minutes": 60})
                    self.assertFalse(registered.isError)
                    self.assertEqual(len(Scheduler(path).jobs()), 1)
                    # Fake API: end-to-end persistence without GitHub traffic.
                    worker = Scheduler(path, api=FakeApi())
                    self.assertEqual(worker.run_due()[0]["status"], "ok")
                    llm = SimpleNamespace(chat=SimpleNamespace(completions=DemoCompletions()))
                    result = await BublikMcpAgent(llm, session).process("Какая сводка?")
                    self.assertEqual(result.answer, "Stars: 11")
                    self.assertEqual(result.tool_calls[0].name, "get_github_summary")


class ProcessTests(unittest.TestCase):
    def test_real_cli_and_worker_processes_with_local_http_api(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "name": "test", "full_name": "Ly41k/test", "owner": {"login": "Ly41k"},
                    "stargazers_count": 7, "forks_count": 2, "open_issues_count": 1,
                    "default_branch": "main", "html_url": "https://github.com/Ly41k/test",
                }).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as folder:
            env = {**os.environ, "BUBLIK_DB_PATH": str(Path(folder) / "schedule.db"),
                   "GITHUB_API_BASE_URL": f"http://127.0.0.1:{server.server_port}"}
            directory = Path(__file__).parent

            def invoke(script, *args):
                return subprocess.run([sys.executable, str(directory / script), *args],
                                      env=env, capture_output=True, text=True,
                                      check=True, timeout=15).stdout

            created = json.loads(invoke("mcp_cli.py", "schedule", "Ly41k", "test", "1"))
            self.assertEqual(created["interval_minutes"], 1)
            run_output = json.loads(invoke("worker.py", "--once"))
            self.assertEqual(run_output["status"], "ok")
            summary = json.loads(invoke("mcp_cli.py", "summary", "Ly41k", "test"))
            self.assertEqual(summary["samples"], 1)
            self.assertEqual(summary["latest"]["stars"], 7)


if __name__ == "__main__":
    unittest.main()
