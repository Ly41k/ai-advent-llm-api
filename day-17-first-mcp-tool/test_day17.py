"""End-to-end checks for Day 17 without network access or an API key."""

import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent import BublikMcpAgent
from demo import DemoLlmClient
from github_api import GitHubApi


def check_github_api_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/Ly41k/ai-advent-llm-api"
        return httpx.Response(
            200,
            json={
                "name": "ai-advent-llm-api",
                "full_name": "Ly41k/ai-advent-llm-api",
                "owner": {"login": "Ly41k"},
                "description": "Learning project",
                "stargazers_count": 7,
                "forks_count": 2,
                "open_issues_count": 1,
                "default_branch": "main",
                "html_url": "https://github.com/Ly41k/ai-advent-llm-api",
            },
        )

    api = GitHubApi(transport=httpx.MockTransport(handler))
    result = api.get_repository("Ly41k", "ai-advent-llm-api")
    assert result["stars"] == 7
    assert result["forks"] == 2
    assert result["default_branch"] == "main"


class GitHubFixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        assert self.path == "/repos/Ly41k/ai-advent-llm-api"
        body = json.dumps(
            {
                "name": "ai-advent-llm-api",
                "full_name": "Ly41k/ai-advent-llm-api",
                "owner": {"login": "Ly41k"},
                "description": "Learning project",
                "stargazers_count": 7,
                "forks_count": 2,
                "open_issues_count": 1,
                "default_branch": "main",
                "html_url": "https://github.com/Ly41k/ai-advent-llm-api",
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        pass


async def check_mcp_agent_flow(api_url: str) -> None:
    server_path = Path(__file__).with_name("server.py")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env={**os.environ, "GITHUB_API_BASE_URL": api_url},
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            github_tool = next(
                tool for tool in tools.tools if tool.name == "get_github_repo"
            )
            properties = github_tool.inputSchema["properties"]
            assert set(properties) == {"owner", "repo"}
            assert set(github_tool.inputSchema["required"]) == {"owner", "repo"}

            agent = BublikMcpAgent(DemoLlmClient(), session)
            result = await agent.process(
                "Расскажи о репозитории Ly41k/ai-advent-llm-api"
            )
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "get_github_repo"
            assert "Ly41k/ai-advent-llm-api" in result.answer
            assert "7 stars" in result.answer


if __name__ == "__main__":
    check_github_api_mapping()
    fixture_server = ThreadingHTTPServer(("127.0.0.1", 0), GitHubFixtureHandler)
    fixture_thread = threading.Thread(
        target=fixture_server.serve_forever,
        daemon=True,
    )
    fixture_thread.start()
    try:
        host, port = fixture_server.server_address
        asyncio.run(check_mcp_agent_flow(f"http://{host}:{port}"))
    finally:
        fixture_server.shutdown()
        fixture_server.server_close()
    print("OK: agent called GitHub MCP tool, received and used its result.")
