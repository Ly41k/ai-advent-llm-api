"""Bublik agent with an MCP tool-calling loop."""

import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession


MODEL_NAME = "openai/gpt-oss-20b"
SYSTEM_PROMPT = (
    "You are Bublik. Use schedule_github_summary to create or update periodic "
    "GitHub monitoring. Use get_github_summary to answer questions about collected "
    "observations; use list_scheduled_jobs for schedule status. Do not claim a "
    "snapshot exists until the worker has saved one. Base answers on tool results."
)


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass(frozen=True)
class AgentResult:
    answer: str
    tool_calls: tuple[ToolCallRecord, ...]


class BublikMcpAgent:
    """Give MCP schemas to an LLM and execute the tool calls it requests."""

    def __init__(self, llm_client: Any, mcp_session: ClientSession) -> None:
        self._llm_client = llm_client
        self._mcp_session = mcp_session

    async def process(self, user_input: str) -> AgentResult:
        prepared = user_input.strip()
        if not prepared:
            raise ValueError("User input cannot be empty")

        tools_result = await self._mcp_session.list_tools()
        llm_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in tools_result.tools
        ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prepared},
        ]
        call_records: list[ToolCallRecord] = []

        for _ in range(3):
            response = self._llm_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=llm_tools,
                tool_choice="auto",
                temperature=0.1,
                max_completion_tokens=600,
            )
            message = response.choices[0].message
            requested_calls = message.tool_calls or []
            if not requested_calls:
                answer = (message.content or "").strip()
                if not answer:
                    raise RuntimeError("The model returned an empty answer")
                return AgentResult(answer, tuple(call_records))

            messages.append(self._assistant_message(message, requested_calls))
            for tool_call in requested_calls:
                arguments = json.loads(tool_call.function.arguments or "{}")
                if not isinstance(arguments, dict):
                    raise RuntimeError("Tool arguments must be a JSON object")
                tool_result = await self._mcp_session.call_tool(
                    tool_call.function.name,
                    arguments=arguments,
                )
                result_text = self._tool_result_text(tool_result)
                if getattr(tool_result, "isError", False):
                    raise RuntimeError(result_text)
                call_records.append(
                    ToolCallRecord(
                        name=tool_call.function.name,
                        arguments=arguments,
                        result=result_text,
                    )
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": result_text,
                    }
                )

        raise RuntimeError("The agent exceeded the MCP tool-call limit")

    @staticmethod
    def _assistant_message(message: Any, requested_calls: list[Any]) -> dict:
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in requested_calls
            ],
        }

    @staticmethod
    def _tool_result_text(tool_result: Any) -> str:
        parts = [
            item.text
            for item in tool_result.content
            if getattr(item, "type", None) == "text"
        ]
        return "\n".join(parts) or "{}"
