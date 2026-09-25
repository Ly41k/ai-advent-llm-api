"""Run the five-call orchestration with Groq or a local deterministic model."""

import argparse
import asyncio
import os
import sys

from agent import BublikOrchestrator
from mcp_registry import connect_servers
from offline_model import OfflineModel


async def main():
    parser = argparse.ArgumentParser(description="Orchestrate three MCP servers")
    parser.add_argument("owner")
    parser.add_argument("repo")
    parser.add_argument("--task", choices=("info", "summary", "report"), default="report",
                        help="Choose the user request; default: verified report")
    parser.add_argument("--offline", action="store_true", help="Run without Groq; GitHub is still live")
    arguments = parser.parse_args()
    if arguments.offline:
        model = OfflineModel()
    else:
        from dotenv import load_dotenv
        from groq import Groq
        load_dotenv()
        if not os.getenv("GROQ_API_KEY"):
            parser.error("Set GROQ_API_KEY or pass --offline")
        model = Groq(api_key=os.environ["GROQ_API_KEY"])
    async with connect_servers() as registry:
        result = await BublikOrchestrator(model, registry).run(arguments.owner, arguments.repo,
                                                                task=arguments.task)
    for index, step in enumerate(result.steps, 1):
        print(f"{index}. [{step.server}] {step.tool} "
              f"(selected by {step.selection_source}): {step.output}")
    print(f"Bublik: {result.answer}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        # AsyncExitStack and MCP task groups wrap the original error in layers.
        def leaves(value):
            nested = getattr(value, "exceptions", None)
            if nested:
                for child in nested:
                    yield from leaves(child)
            else:
                yield value

        for cause in leaves(error):
            print(f"Error: {cause}", file=sys.stderr)
        raise SystemExit(1) from None
