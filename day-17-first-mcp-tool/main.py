"""Interactive Day 17 application using Groq and the local MCP server."""

import asyncio
import os

from dotenv import load_dotenv
from groq import Groq

from agent import BublikMcpAgent
from mcp_client import connect_github_mcp


async def main() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise SystemExit(
            "GROQ_API_KEY is not configured. Run `python3 demo.py` for the "
            "offline demonstration or add the key to .env."
        )

    async with connect_github_mcp() as session:
        agent = BublikMcpAgent(Groq(api_key=api_key), session)
        print("Bublik is connected to the GitHub MCP server. Type /exit to stop.")
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() == "/exit":
                break
            try:
                result = await agent.process(user_input)
                for call in result.tool_calls:
                    print(f"[MCP] {call.name}({call.arguments})")
                print(f"Bublik: {result.answer}\n")
            except Exception as error:
                print(f"Error: {error}\n")


if __name__ == "__main__":
    asyncio.run(main())
