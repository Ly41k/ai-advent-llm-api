"""Synthetic CRM. stdout belongs exclusively to the MCP stdio transport."""
import json
from mcp.server.fastmcp import FastMCP
from common import ROOT, identifier

mcp = FastMCP('Day 33 Synthetic CRM')


def lookup(filename, key, value, prefix):
    identifier(value, prefix)
    rows = json.loads((ROOT / 'data' / filename).read_text(encoding='utf-8'))
    return next((row for row in rows if row[key] == value), None)


@mcp.tool()
def get_ticket(ticket_id: str) -> dict:
    """Read one synthetic ticket. Never infer identity from a question."""
    return {'ticket': lookup('tickets.json', 'ticket_id', ticket_id, 'T')}


@mcp.tool()
def get_user(user_id: str) -> dict:
    """Read the synthetic user identified by the previously fetched ticket."""
    return {'user': lookup('users.json', 'user_id', user_id, 'U')}


if __name__ == '__main__':
    mcp.run(transport='stdio')
