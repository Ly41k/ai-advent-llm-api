"""Interactive agent for schedules and stored summaries; worker runs separately."""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from agent import BublikMcpAgent
from mcp_client import connect_mcp


async def main():
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise SystemExit("Set GROQ_API_KEY in .env; run worker.py separately")
    async with connect_mcp() as session:
        agent = BublikMcpAgent(Groq(api_key=key), session)
        print("Бублик: планировщик подключён. /exit для выхода.")
        while True:
            question = await asyncio.to_thread(input, "Вы: ")
            if question.strip().lower() in {"/exit", "выход"}:
                break
            try:
                result = await agent.process(question)
                print("Бублик:", result.answer)
                for call in result.tool_calls:
                    print("[MCP]", call.name, call.result)
            except Exception as error:
                print("Ошибка:", error)


if __name__ == "__main__":
    asyncio.run(main())
