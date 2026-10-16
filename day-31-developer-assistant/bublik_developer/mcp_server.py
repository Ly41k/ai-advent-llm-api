"""Real FastMCP stdio Git server with a root fixed by its trusted launcher."""
import argparse
import logging
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .git_tools import GitTools
from .mcp_schema import GitReply
from .workspace import ProjectWorkspace


def create_server(workspace):
    server = FastMCP("Bublik Project Git", log_level="ERROR")
    tools = GitTools(workspace)

    def result(name, arguments):
        return GitReply.model_validate(tools.invoke(name, arguments))

    @server.tool()
    def git_current_branch() -> GitReply:
        """Read actual local branch, HEAD, detached and unborn states."""
        return result("git_current_branch", {})

    @server.tool()
    def git_status() -> GitReply:
        """Read index/worktree metadata; protected names are withheld."""
        return result("git_status", {})

    @server.tool()
    def project_list_files() -> GitReply:
        """List allowed tracked/untracked filenames, without file contents."""
        return result("project_list_files", {})

    @server.tool()
    def git_diff(scope: Literal["staged", "unstaged"] = "unstaged", paths: list[str] | None = None,
                 include_content: bool = False) -> GitReply:
        """Bounded diff metadata; text requires 1–4 explicitly allowed paths."""
        return result("git_diff", {"scope": scope, "paths": paths or [], "include_content": include_content})

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    # Do not log tool argument/body tracebacks through the protocol's stderr.
    logging.disable(logging.CRITICAL)
    create_server(ProjectWorkspace.open(args.root, args.project_id)).run(transport="stdio")


if __name__ == "__main__":
    main()
