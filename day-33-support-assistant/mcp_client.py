"""Day 20 ClientSession pattern, one real child process per support request."""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from common import ROOT, SupportError, identifier, parse_json, require


def domain_error(error):
    """anyio task groups may wrap errors raised inside the session context."""
    if isinstance(error, SupportError):
        return error
    if isinstance(error, BaseExceptionGroup):
        for child in error.exceptions:
            found = domain_error(child)
            if found is not None:
                return found
    return None


@asynccontextmanager
async def connect(command=None):
    # Do not forward Groq keys or the operator's environment to the CRM child.
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'SYSTEMROOT', 'WINDIR', 'LANG'}}
    cmd = command or [sys.executable, str(ROOT / 'mcp_server.py')]
    try:
        async with asyncio.timeout(15):
            with open(os.devnull, 'w') as errors:
                async with stdio_client(StdioServerParameters(command=cmd[0], args=cmd[1:], env=env), errlog=errors) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        names = {tool.name for tool in (await session.list_tools()).tools}
                        require(names == {'get_ticket', 'get_user'}, 'mcp_invalid_catalog', 502)
                        yield session
    except SupportError:
        raise
    except Exception as error:
        raise domain_error(error) or SupportError('mcp_unavailable', 503) from None


async def call(session, name, arguments):
    result = await session.call_tool(name, arguments=arguments)
    require(not result.isError, 'mcp_tool_error', 502)
    value = result.structuredContent
    if value is None:
        parts = [item.text for item in result.content if item.type == 'text']
        require(len(parts) == 1, 'mcp_invalid_response', 502)
        value = parse_json(parts[0])
    if isinstance(value, dict) and set(value) == {'result'}:
        value = value['result']
    require(isinstance(value, dict), 'mcp_invalid_response', 502)
    return value


async def fetch_context(ticket_id, command=None):
    async with connect(command) as session:
        ticket = (await call(session, 'get_ticket', {'ticket_id': ticket_id})).get('ticket')
        require(ticket is not None, 'ticket_not_found', 404)
        require(isinstance(ticket, dict) and ticket.get('ticket_id') == ticket_id, 'mcp_identity_mismatch', 502)
        user_id = ticket.get('user_id')
        require(isinstance(user_id, str), 'mcp_identity_mismatch', 502)
        identifier(user_id, 'U')
        # This ID comes only from the MCP ticket. The question is never parsed for IDs.
        user = (await call(session, 'get_user', {'user_id': user_id})).get('user')
        require(isinstance(user, dict) and user.get('user_id') == user_id, 'mcp_identity_mismatch', 502)
        return ticket, user
