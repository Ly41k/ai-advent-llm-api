"""End-to-end demonstration of the agent -> MCP -> GitHub API flow."""

import asyncio
import json
from types import SimpleNamespace

from agent import BublikMcpAgent
from mcp_client import connect_github_mcp


class DemoCompletions:
    """A deterministic Groq-compatible model stub for an offline demo."""

    def create(self, **request):
        tool_messages = [
            message for message in request["messages"] if message["role"] == "tool"
        ]
        if not tool_messages:
            call = SimpleNamespace(
                id="demo-call-1",
                function=SimpleNamespace(
                    name="get_github_repo",
                    arguments=json.dumps(
                        {"owner": "Ly41k", "repo": "ai-advent-llm-api"}
                    ),
                ),
            )
            message = SimpleNamespace(content=None, tool_calls=[call])
        else:
            repository = json.loads(tool_messages[-1]["content"])
            content = (
                f"Репозиторий {repository['full_name']}: "
                f"{repository['stars']} stars, {repository['forks']} forks, "
                f"основная ветка — {repository['default_branch']}."
            )
            message = SimpleNamespace(content=content, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class DemoLlmClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=DemoCompletions())


async def main() -> None:
    question = "Расскажи о репозитории Ly41k/ai-advent-llm-api."
    async with connect_github_mcp() as session:
        agent = BublikMcpAgent(DemoLlmClient(), session)
        result = await agent.process(question)

    print(f"Пользователь: {question}")
    for call in result.tool_calls:
        print(f"Агент вызвал MCP: {call.name}({call.arguments})")
        print(f"MCP вернул: {call.result}")
    print(f"Бублик: {result.answer}")


if __name__ == "__main__":
    asyncio.run(main())
