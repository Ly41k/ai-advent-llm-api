"""Three independent MCP tools: fetch, summarize, persist."""

import os
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from github_api import get_repository, validate_name


mcp = FastMCP("Bublik Day 19 Composition")


@mcp.tool()
def search_repository(owner: str, repo: str) -> dict:
    """Get public GitHub repository data. Pass this result to summarize_repository."""
    return get_repository(owner, repo)


@mcp.tool()
def summarize_repository(repository: dict) -> dict:
    """Turn search_repository data into a report. Pass this result to save_report."""
    name = repository["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    if not isinstance(repository["description"], str):
        raise ValueError("Invalid description")
    for key in ("stars", "forks", "open_issues"):
        if type(repository[key]) is not int or repository[key] < 0:
            raise ValueError(f"Invalid {key}")
    branch = validate_name(repository["default_branch"], "branch")
    url = repository["url"]
    if url != f"https://github.com/{name}":
        raise ValueError("Invalid repository URL")
    lines = [
        f"# Repository summary: {name}",
        "",
        f"- URL: {url}",
        f"- Description: {repository['description'].replace(chr(10), ' ').replace(chr(13), ' ')}",
        f"- Default branch: {branch}",
        f"- Stars: {repository['stars']}",
        f"- Forks: {repository['forks']}",
        f"- Open issues: {repository['open_issues']}",
        "",
    ]
    return {"full_name": name, "markdown": "\n".join(lines)}


@mcp.tool()
def save_report(summary: dict) -> dict:
    """Save the exact markdown supplied by summarize_repository to a local file."""
    name = summary["full_name"]
    owner, separator, repo = name.partition("/")
    if not separator or "/" in repo:
        raise ValueError("Invalid repository full_name")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    markdown = summary["markdown"]
    if not isinstance(markdown, str) or not markdown.startswith(f"# Repository summary: {name}\n"):
        raise ValueError("Invalid summary markdown")
    output_dir = Path(os.getenv("BUBLIK_REPORT_DIR", str(Path(__file__).parent / "reports")))
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{owner}-{repo}-summary.md"
    # Write fully before replacing the report so an interrupted run cannot truncate it.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output_dir, prefix=".report-", delete=False) as file:
            temporary = Path(file.name)
            file.write(markdown)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"full_name": name, "path": str(target.resolve()), "bytes_written": len(markdown.encode("utf-8"))}


if __name__ == "__main__":
    mcp.run(transport="stdio")
