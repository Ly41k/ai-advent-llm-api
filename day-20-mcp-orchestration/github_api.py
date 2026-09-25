"""Fetch one public GitHub repository, following the Day 17/18 API pattern."""

import os
import re

import httpx


NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"Invalid GitHub {field}: {value!r}")
    return value


def get_repository(owner: str, repo: str) -> dict:
    owner = validate_name(owner, "owner")
    repo = validate_name(repo, "repo")
    base_url = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com").rstrip("/")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "bublik-day-20-mcp"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with httpx.Client(timeout=10, trust_env=False) as client:
        response = client.get(f"{base_url}/repos/{owner}/{repo}", headers=headers)
        response.raise_for_status()
        data = response.json()
    return {
        "full_name": data["full_name"],
        "description": data.get("description") or "No description",
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "open_issues": data["open_issues_count"],
        "default_branch": data["default_branch"],
        "url": data["html_url"],
    }
