"""End-to-end MCP tests with a local fake GitHub HTTP endpoint (no API key)."""

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
from unittest.mock import patch

from agent import BublikPipelineAgent
from mcp_client import connect_mcp


REPOSITORY = {
    "full_name": "Ly41k/ai-advent-llm-api",
    "description": "Day 19 composition example",
    "stargazers_count": 12,
    "forks_count": 3,
    "open_issues_count": 2,
    "default_branch": "main",
    "html_url": "https://github.com/Ly41k/ai-advent-llm-api",
}


class GitHubHandler(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):
        if self.path != "/repos/Ly41k/ai-advent-llm-api":
            self.send_error(404)
            return
        body = json.dumps(REPOSITORY).encode("utf-8")
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@contextmanager
def mock_github():
    server = ThreadingHTTPServer(("127.0.0.1", 0), GitHubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class Day19Tests(unittest.IsolatedAsyncioTestCase):
    async def test_one_command_runs_full_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp, mock_github() as base:
            environment = {**os.environ, "GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("main.py")),
                 "Ly41k", "ai-advent-llm-api"],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            output = completed.stdout
            self.assertLess(output.index("[MCP] search_repository"),
                            output.index("[MCP] summarize_repository"))
            self.assertLess(output.index("[MCP] summarize_repository"),
                            output.index("[MCP] save_report"))
            report = Path(tmp) / "Ly41k-ai-advent-llm-api-summary.md"
            self.assertIn("Saved report:", output)
            self.assertIn("Stars: 12", report.read_text(encoding="utf-8"))

    async def test_real_mcp_chain_and_exact_data_transfer(self):
        with tempfile.TemporaryDirectory() as tmp, mock_github() as base:
            with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                async with connect_mcp() as session:
                    tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                    self.assertEqual(set(tools), {"search_repository", "summarize_repository", "save_report"})
                    self.assertIn("repository", tools["summarize_repository"].inputSchema["properties"])
                    self.assertIn("summary", tools["save_report"].inputSchema["properties"])

                    result = await BublikPipelineAgent(session).run("Ly41k", "ai-advent-llm-api")
                    self.assertEqual([step.tool for step in result.steps],
                                     ["search_repository", "summarize_repository", "save_report"])
                    fetch, summarize, save = result.steps
                    self.assertEqual(summarize.input, {"repository": fetch.output})
                    self.assertEqual(save.input, {"summary": summarize.output})
                    self.assertEqual(fetch.output["stars"], 12)
                    self.assertIn("Stars: 12", summarize.output["markdown"])
                    target = Path(result.report["path"])
                    self.assertEqual(target.parent.resolve(), Path(tmp).resolve())
                    self.assertEqual(target.read_text(encoding="utf-8"), summarize.output["markdown"])
                    self.assertEqual(result.report["bytes_written"], len(summarize.output["markdown"].encode()))

                    # Repeat the automatic chain; report is safely replaced, not appended.
                    second = await BublikPipelineAgent(session).run("Ly41k", "ai-advent-llm-api")
                    self.assertEqual(target.read_text(encoding="utf-8"), second.steps[1].output["markdown"])
                    self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    async def test_fetch_error_stops_pipeline_before_write(self):
        with tempfile.TemporaryDirectory() as tmp, mock_github() as base:
            GitHubHandler.status = 503
            try:
                with patch.dict(os.environ, {"GITHUB_API_BASE_URL": base, "BUBLIK_REPORT_DIR": tmp}):
                    async with connect_mcp() as session:
                        with self.assertRaisesRegex(RuntimeError, "search_repository failed"):
                            await BublikPipelineAgent(session).run("Ly41k", "ai-advent-llm-api")
                self.assertEqual(list(Path(tmp).iterdir()), [])
            finally:
                GitHubHandler.status = 200

    async def test_invalid_input_never_starts_a_tool(self):
        class NoCalls:
            async def list_tools(self):
                raise AssertionError("No tool should be called")

        with self.assertRaises(ValueError):
            await BublikPipelineAgent(NoCalls()).run("../bad", "repo")

    async def test_malformed_intermediate_values_are_rejected_by_mcp_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"BUBLIK_REPORT_DIR": tmp}):
                async with connect_mcp() as session:
                    malformed = await session.call_tool(
                        "summarize_repository",
                        arguments={"repository": {
                            "full_name": "Ly41k/ai-advent-llm-api",
                            "description": "example",
                            "stars": "twelve",
                            "forks": 3,
                            "open_issues": 2,
                            "default_branch": "main",
                            "url": "https://github.com/Ly41k/ai-advent-llm-api",
                        }},
                    )
                    self.assertTrue(malformed.isError)
                    bad_destination = await session.call_tool(
                        "save_report",
                        arguments={"summary": {
                            "full_name": "../outside",
                            "markdown": "# Repository summary: ../outside\n",
                        }},
                    )
                    self.assertTrue(bad_destination.isError)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
