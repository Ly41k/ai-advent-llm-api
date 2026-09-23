"""Small client for the public GitHub repository API."""

import os
import re
from typing import Any

import httpx


GITHUB_API_URL = "https://api.github.com"
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class GitHubApiError(RuntimeError):
    """Raised when GitHub cannot return the requested repository."""


class GitHubApi:
    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        selected_url = base_url or os.getenv("GITHUB_API_BASE_URL", GITHUB_API_URL)
        self._base_url = selected_url.rstrip("/")
        self._token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self._transport = transport

    def get_repository(self, owner: str, repo: str) -> dict[str, Any]:
        """Load and normalize public repository information from GitHub."""
        prepared_owner = self._validate_name("owner", owner)
        prepared_repo = self._validate_name("repo", repo)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "bublik-day-17-mcp",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            with httpx.Client(
                timeout=10.0,
                follow_redirects=True,
                transport=self._transport,
                trust_env=False,
            ) as client:
                response = client.get(
                    f"{self._base_url}/repos/{prepared_owner}/{prepared_repo}",
                    headers=headers,
                )
        except httpx.HTTPError as error:
            raise GitHubApiError(f"GitHub API request failed: {error}") from error

        if response.status_code == 404:
            raise GitHubApiError(
                f"Repository {prepared_owner}/{prepared_repo} was not found"
            )
        if response.status_code >= 400:
            raise GitHubApiError(
                f"GitHub API returned HTTP {response.status_code}"
            )

        data = response.json()
        return {
            "name": data["name"],
            "full_name": data["full_name"],
            "owner": data["owner"]["login"],
            "description": data.get("description"),
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "open_issues": data["open_issues_count"],
            "default_branch": data["default_branch"],
            "url": data["html_url"],
        }

    @staticmethod
    def _validate_name(parameter: str, value: str) -> str:
        prepared = value.strip()
        if not prepared or not NAME_PATTERN.fullmatch(prepared):
            raise GitHubApiError(f"Invalid GitHub {parameter}: {value!r}")
        return prepared
