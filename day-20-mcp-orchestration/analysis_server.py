"""Report preparation and independent saved-content verification."""

import hashlib

from mcp.server.fastmcp import FastMCP
from github_api import validate_name

mcp = FastMCP("Bublik Analysis")


def valid_full_name(value: str) -> str:
    if not isinstance(value, str) or value.count("/") != 1:
        raise ValueError("Invalid repository identity")
    owner, repo = value.split("/")
    validate_name(owner, "owner")
    validate_name(repo, "repo")
    return value


@mcp.tool()
def summarize_repository(repository: dict) -> dict:
    """Convert GitHub repository metadata into a Markdown report for storage."""
    name = valid_full_name(repository["full_name"])
    if repository["url"] != f"https://github.com/{name}":
        raise ValueError("Invalid repository URL")
    if not isinstance(repository["description"], str):
        raise ValueError("Invalid description")
    for key in ("stars", "forks", "open_issues"):
        if type(repository[key]) is not int or repository[key] < 0:
            raise ValueError(f"Invalid {key}")
    branch = validate_name(repository["default_branch"], "branch")
    description = repository["description"].replace("\n", " ").replace("\r", " ")
    markdown = "\n".join([
        f"# Repository summary: {name}", "",
        f"- URL: {repository['url']}", f"- Description: {description}",
        f"- Default branch: {branch}", f"- Stars: {repository['stars']}",
        f"- Forks: {repository['forks']}", f"- Open issues: {repository['open_issues']}", "",
    ])
    return {"full_name": name, "markdown": markdown}


@mcp.tool()
def verify_report(summary: dict, saved_report: dict) -> dict:
    """Verify the report read back from storage matches the original summary."""
    name = valid_full_name(summary["full_name"])
    if saved_report["full_name"] != name:
        raise ValueError("Repository identity changed")
    expected, actual = summary["markdown"], saved_report["markdown"]
    if not isinstance(expected, str) or not isinstance(actual, str):
        raise ValueError("Report must contain text")
    digest = hashlib.sha256(actual.encode("utf-8")).hexdigest()
    return {"full_name": name, "verified": expected == actual, "sha256": digest}


if __name__ == "__main__":
    mcp.run(transport="stdio")
