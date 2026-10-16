"""Bounded REST calls. Adapted from Day 17 HTTP patterns; no shell commands."""
import json
import socket
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from common import REPOSITORY, MAX_FILES, ReviewError, fail, number, strict_json


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class Transport:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def __call__(self, method, url, headers, body, timeout, limit):
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    fail("http_response_size")
                return response.status, raw, dict(response.headers)
        except HTTPError as error:
            # Do not log body, URL, key, or the exception representation.
            fail("http_" + str(error.code))
        except (TimeoutError, socket.timeout):
            fail("http_timeout")
        except (URLError, OSError):
            fail("http_transport")


class GitHub:
    def __init__(self, token, transport=None):
        if not token:
            fail("missing_github_token")
        self.token = token
        self.transport = transport or Transport()
        self.calls = 0

    def request(self, endpoint, method="GET", value=None):
        patterns = {
            "GET": r"/(?:pulls/[1-9][0-9]*(?:/files\?per_page=10&page=[12])?|issues/[1-9][0-9]*/comments\?per_page=100&page=[123])",
            "POST": r"/issues/[1-9][0-9]*/comments",
            "PATCH": r"/issues/comments/[1-9][0-9]*",
        }
        if method not in patterns or not re.fullmatch(patterns[method], endpoint):
            fail("github_operation_denied")
        self.calls += 1
        if self.calls > 20:
            fail("github_request_limit")
        headers = {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + self.token,
                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "day32-course-review"}
        body = None if value is None else json.dumps(value).encode()
        if body is not None:
            headers["Content-Type"] = "application/json"
        status, raw, _ = self.transport(method, "https://api.github.com/repos/" + REPOSITORY + endpoint,
                                        headers, body, 15, 1048576)
        if not 200 <= status < 300:
            fail("github_http_" + str(status))
        try:
            return strict_json(raw.decode("utf-8"))
        except UnicodeError:
            fail("github_encoding")

    def pr(self, pr_number):
        return self.request("/pulls/" + str(number(pr_number)))

    def files(self, pr):
        count = pr.get("changed_files")
        if type(count) is not int or not 0 < count <= MAX_FILES:
            fail("changed_files_limit")
        # A deliberately bounded page size exercises pagination within the 20-file limit.
        rows = []
        for page in range(1, (count + 9) // 10 + 1):
            values = self.request(f"/pulls/{number(pr['number'])}/files?" + urlencode({"per_page": 10, "page": page}))
            if not isinstance(values, list) or len(values) != min(10, count - len(rows)):
                fail("incomplete_file_list")
            rows.extend(values)
        if len(rows) != count:
            fail("incomplete_file_list")
        return rows

    def comment(self, pr_number, body):
        marker = "<!-- day32-course-review -->"
        matches = []
        for page in range(1, 4):
            rows = self.request(f"/issues/{number(pr_number)}/comments?per_page=100&page={page}")
            if not isinstance(rows, list):
                fail("invalid_comments")
            matches.extend(row for row in rows if row.get("user", {}).get("login") == "github-actions[bot]"
                           and row.get("body", "").startswith(marker))
            if len(rows) < 100:
                break
        else:
            fail("comments_pagination_limit")
        if len(matches) > 1:
            fail("duplicate_bot_comments")
        if matches:
            comment_id = matches[0].get("id")
            if type(comment_id) is not int or comment_id <= 0:
                fail("invalid_comment_id")
            return self.request(f"/issues/comments/{comment_id}", "PATCH", {"body": marker + "\n" + body})
        return self.request(f"/issues/{number(pr_number)}/comments", "POST", {"body": marker + "\n" + body})
