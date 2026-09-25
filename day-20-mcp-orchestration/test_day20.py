"""Integration checks: real MCP subprocesses and a local fake GitHub endpoint."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agent import BublikOrchestrator, FLOW
from mcp_registry import connect_servers, ToolRegistry
from offline_model import OfflineModel

REPO = {"full_name": "Ly41k/ai-advent-llm-api", "description": "Multi-server example",
        "stargazers_count": 12, "forks_count": 3, "open_issues_count": 2,
        "default_branch": "main", "html_url": "https://github.com/Ly41k/ai-advent-llm-api"}


class Handler(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):
        if self.path != "/repos/Ly41k/ai-advent-llm-api":
            self.send_error(404)
            return
        body = json.dumps(REPO).encode()
        self.send_response(type(self).status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@contextmanager
def fake_github():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class WrongOrder(OfflineModel):
    def create(self, *, messages, **kwargs):
        response = super().create(messages=messages, **kwargs)
        if 'Completed operations: []' in messages[1]['content']:
            response.choices[0].message.content = json.dumps({"operation": "SAVE"})
        return response


class WrongData(OfflineModel):
    def create(self, *, messages, **kwargs):
        response = super().create(messages=messages, **kwargs)
        if 'Completed operations: ["FETCH"]' in messages[1]['content']:
            response.choices[0].message.content = json.dumps({"operation": "SUMMARIZE", "repository": {}})
        return response


class PrematureVerify(OfflineModel):
    def create(self, *, messages, **kwargs):
        response = super().create(messages=messages, **kwargs)
        if 'Completed operations: ["FETCH", "SUMMARIZE"]' in messages[1]['content']:
            response.choices[0].message.content = json.dumps({"operation": "VERIFY"})
        return response


class EarlyStop(OfflineModel):
    def create(self, *, messages, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="Report saved"))])


class GroqParserFailure(OfflineModel):
    def create(self, *, messages, **kwargs):
        if 'Completed operations: ["FETCH", "SUMMARIZE", "SAVE"]' in messages[1]['content']:
            error = RuntimeError("Groq attempted a native tool call")
            error.status_code = 400
            error.body = {"error": {"code": "tool_use_failed"}}
            raise error
        return super().create(messages=messages, **kwargs)


class Day20Tests(unittest.IsolatedAsyncioTestCase):
    async def test_real_servers_model_selection_routing_data_and_order(self):
        with tempfile.TemporaryDirectory() as tmp, fake_github() as base:
            with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                async with connect_servers() as registry:
                    self.assertEqual(set(registry.routes), set(FLOW))
                    self.assertEqual({alias for alias, _ in registry.routes.values()},
                                     {"github", "analysis", "storage"})
                    self.assertIn("repository", next(item for item in registry.schemas
                        if item["function"]["name"] == FLOW[1])["function"]["parameters"]["properties"])
                    model = OfflineModel()
                    result = await BublikOrchestrator(model, registry).run(
                        "Ly41k", "ai-advent-llm-api")
                    self.assertEqual(len(model.requests), 5)
                    self.assertTrue(all(call["response_format"]["json_schema"]["strict"] is True
                                        for call in model.requests))
                    self.assertTrue(all(set(call["response_format"]["json_schema"]["schema"]
                                                ["properties"]["operation"]["enum"]) ==
                                        {"FETCH", "SUMMARIZE", "SAVE", "READ", "VERIFY"}
                                        for call in model.requests))
                    self.assertTrue(all("github__" not in call["messages"][0]["content"]
                                        for call in model.requests))
                    self.assertTrue(all(step.selection_source == "model" for step in result.steps))
                    self.assertTrue(all("tools" not in call for call in model.requests))
                    self.assertEqual([item.tool for item in result.steps], list(FLOW))
                    self.assertEqual([item.server for item in result.steps],
                                     ["github", "analysis", "storage", "storage", "analysis"])
                    fetch, summary, saved, read, verified = result.steps
                    self.assertEqual(summary.arguments, {"repository": fetch.output})
                    self.assertEqual(saved.arguments, {"summary": summary.output})
                    self.assertEqual(verified.arguments,
                                     {"summary": summary.output, "saved_report": read.output})
                    self.assertEqual(fetch.output["stars"], 12)
                    self.assertTrue(verified.output["verified"])
                    self.assertEqual(read.output["markdown"], summary.output["markdown"])
                    self.assertEqual(Path(saved.output["path"]).read_text(encoding="utf-8"),
                                     summary.output["markdown"])
                    self.assertIn(saved.output["path"], result.answer)
                    # Unknown tool must never be sent to a server.
                    with self.assertRaisesRegex(ValueError, "Unknown MCP tool"):
                        await registry.call("unknown__save_report", {})

    async def test_command_line_one_run_three_servers(self):
        with tempfile.TemporaryDirectory() as tmp, fake_github() as base:
            proc = subprocess.run([sys.executable, str(Path(__file__).with_name("main.py")),
                                   "Ly41k", "ai-advent-llm-api", "--offline"],
                                  env={**os.environ, "GITHUB_API_BASE_URL": base,
                                       "BUBLIK_REPORT_DIR": tmp}, text=True,
                                  capture_output=True, timeout=30, check=True)
            self.assertEqual([line.split(" ", 1)[0] for line in proc.stdout.splitlines()[:5]],
                             ["1.", "2.", "3.", "4.", "5."])
            self.assertIn("Verified Ly41k/ai-advent-llm-api", proc.stdout)
            self.assertIn("Stars: 12", (Path(tmp) / "Ly41k-ai-advent-llm-api-summary.md").read_text())

    async def test_agent_selects_different_tools_for_different_requests(self):
        with tempfile.TemporaryDirectory() as tmp, fake_github() as base:
            with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                async with connect_servers() as registry:
                    agent = BublikOrchestrator(OfflineModel(), registry)
                    info = await agent.run("Ly41k", "ai-advent-llm-api", task="info")
                    self.assertEqual([step.tool for step in info.steps], [FLOW[0]])
                    self.assertIn("Repository Ly41k/ai-advent-llm-api", info.answer)
                    summary = await agent.run("Ly41k", "ai-advent-llm-api", task="summary")
                    self.assertEqual([step.tool for step in summary.steps], list(FLOW[:2]))
                    self.assertIn("Stars: 12", summary.answer)
                    self.assertEqual(list(Path(tmp).iterdir()), [])

    async def test_model_wrong_order_is_corrected_and_bad_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, fake_github() as base:
            with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                async with connect_servers() as registry:
                    wrong = await BublikOrchestrator(WrongOrder(), registry).run(
                        "Ly41k", "ai-advent-llm-api")
                    self.assertEqual([step.tool for step in wrong.steps], list(FLOW))
                    self.assertEqual(wrong.steps[0].selection_source,
                                     "agent correction (model chose SAVE)")
                    with self.assertRaisesRegex(RuntimeError, "invalid operation selection"):
                        await BublikOrchestrator(WrongData(), registry).run("Ly41k", "ai-advent-llm-api")
                    with self.assertRaisesRegex(RuntimeError, "invalid operation JSON"):
                        await BublikOrchestrator(EarlyStop(), registry).run("Ly41k", "ai-advent-llm-api")

    async def test_premature_verification_is_corrected_before_mcp_call(self):
        with tempfile.TemporaryDirectory() as tmp, fake_github() as base:
            with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                async with connect_servers() as registry:
                    result = await BublikOrchestrator(PrematureVerify(), registry).run(
                        "Ly41k", "ai-advent-llm-api")
                    self.assertEqual([step.tool for step in result.steps], list(FLOW))
                    self.assertEqual(result.steps[2].selection_source,
                                     "agent correction (model chose VERIFY)")
                    self.assertTrue(result.steps[-1].output["verified"])

    async def test_github_failure_stops_before_storage(self):
        with tempfile.TemporaryDirectory() as tmp, fake_github() as base:
            Handler.status = 503
            try:
                with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                    async with connect_servers() as registry:
                        with self.assertRaisesRegex(RuntimeError, "github__get_repository_info failed"):
                            await BublikOrchestrator(OfflineModel(), registry).run("Ly41k", "ai-advent-llm-api")
                self.assertEqual(list(Path(tmp).iterdir()), [])
            finally:
                Handler.status = 200

    async def test_groq_parser_failure_uses_visible_guarded_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, fake_github() as base:
            with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                async with connect_servers() as registry:
                    result = await BublikOrchestrator(GroqParserFailure(), registry).run(
                        "Ly41k", "ai-advent-llm-api")
                    self.assertEqual([step.tool for step in result.steps], list(FLOW))
                    self.assertEqual(result.steps[3].selection_source,
                                     "agent fallback (Groq tool parser error)")
                    self.assertTrue(result.steps[4].output["verified"])

    async def test_duplicate_catalog_name_rejected(self):
        fake_tool = SimpleNamespace(name="same", description="", inputSchema={})
        fake_session = SimpleNamespace(list_tools=lambda: None)

        async def list_tools():
            return SimpleNamespace(tools=[fake_tool, fake_tool])

        fake_session.list_tools = list_tools
        with self.assertRaisesRegex(RuntimeError, "Duplicate MCP tool"):
            await ToolRegistry({"server": fake_session}).discover()


if __name__ == "__main__":
    unittest.main()
