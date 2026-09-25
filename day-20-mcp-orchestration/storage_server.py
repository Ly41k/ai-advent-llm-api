"""Report persistence and readback on a separate MCP server."""

import os
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from github_api import validate_name

mcp = FastMCP("Bublik Storage")


def target_for(name: str) -> Path:
    if not isinstance(name, str) or name.count("/") != 1:
        raise ValueError("Invalid repository identity")
    owner, repo = name.split("/")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    directory = Path(os.getenv("BUBLIK_REPORT_DIR", str(Path(__file__).parent / "reports")))
    return directory / f"{owner}-{repo}-summary.md"


@mcp.tool()
def save_report(summary: dict) -> dict:
    """Atomically save the report produced by the analysis server."""
    name = summary["full_name"]
    target = target_for(name)
    markdown = summary["markdown"]
    if not isinstance(markdown, str) or not markdown.startswith(f"# Repository summary: {name}\n"):
        raise ValueError("Invalid report text")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=target.parent, prefix=".report-", delete=False) as file:
            temporary = Path(file.name)
            file.write(markdown)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"full_name": name, "path": str(target.resolve()),
            "bytes_written": len(markdown.encode("utf-8"))}


@mcp.tool()
def read_report(owner: str, repo: str) -> dict:
    """Read the stored report back before independent verification."""
    name = f"{validate_name(owner, 'owner')}/{validate_name(repo, 'repo')}"
    target = target_for(name)
    return {"full_name": name, "path": str(target.resolve()),
            "markdown": target.read_text(encoding="utf-8")}


if __name__ == "__main__":
    mcp.run(transport="stdio")
