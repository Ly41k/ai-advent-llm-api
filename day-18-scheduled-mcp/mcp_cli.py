"""Manual MCP smoke test without an LLM or a Groq API key."""
import argparse
import asyncio
import json

from mcp_client import connect_mcp


async def main():
    parser = argparse.ArgumentParser(description="Call the Day 18 tools over MCP stdio")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("schedule", help="Create or update a recurring observation")
    create.add_argument("owner")
    create.add_argument("repo")
    create.add_argument("interval_minutes", type=int)
    commands.add_parser("jobs", help="List saved jobs")
    summary = commands.add_parser("summary", help="Read the aggregate saved result")
    summary.add_argument("owner")
    summary.add_argument("repo")
    summary.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.command == "schedule":
        name = "schedule_github_summary"
        arguments = {"owner": args.owner, "repo": args.repo,
                     "interval_minutes": args.interval_minutes}
    elif args.command == "jobs":
        name, arguments = "list_scheduled_jobs", {}
    else:
        name = "get_github_summary"
        arguments = {"owner": args.owner, "repo": args.repo, "limit": args.limit}

    async with connect_mcp() as session:
        response = await session.call_tool(name, arguments=arguments)
        for item in response.content:
            if item.type == "text":
                try:
                    print(json.dumps(json.loads(item.text), ensure_ascii=False, indent=2))
                except json.JSONDecodeError:
                    print(item.text)
        if response.isError:
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
