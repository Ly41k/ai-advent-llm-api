"""Bounded local Ollama embeddings; Day 21 normalize + Day 26 HTTP safeguards."""
import json
import math
import re
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from ..errors import DeveloperError, ErrorCode


class TransportUnavailable(DeveloperError):
    """Connection/IO failure, distinct from HTTP status or malformed content."""
    def __init__(self):
        super().__init__(ErrorCode.EMBEDDING_UNAVAILABLE)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def normalize(vector):
    if (not isinstance(vector, list) or len(vector) != 1024
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector)):
        raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm or not math.isfinite(norm):
        raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
    return [value / norm for value in vector]


class LocalEmbeddings:
    name = "bge-m3"

    def __init__(self, lease, *, transport=None):
        self.lease, self.transport = lease, transport
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.events = []

    def request(self, endpoint, body=None):
        if self.transport is not None:
            return self.transport(endpoint, body)
        request = Request("http://127.0.0.1:11434" + endpoint,
            data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
            headers={"Content-Type": "application/json", "Accept": "application/json", "Accept-Encoding": "identity"})
        try:
            with self.opener.open(request, timeout=180) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024 or response.status != 200:
                    raise ValueError
                value = json.loads(raw)
            if not isinstance(value, dict) or value.get("error"):
                raise ValueError
            return value
        except HTTPError:
            raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE) from None
        except (URLError, OSError):
            raise TransportUnavailable() from None
        except (ValueError, UnicodeError):
            raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE) from None

    def identity(self):
        self.lease.validate()
        tags = self.request("/api/tags").get("models")
        info = self.request("/api/show", {"model": self.name})
        if not isinstance(tags, list) or info.get("remote_host") or info.get("remote_model"):
            raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
        selected = [row for row in tags if isinstance(row, dict) and row.get("name") in {self.name, self.name + ":latest"}]
        if len(selected) != 1 or not isinstance(selected[0].get("digest"), str):
            raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
        digest = selected[0]["digest"].removeprefix("sha256:")
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
        return {"name": self.name, "digest": digest, "dimension": 1024}

    def embed(self, texts, *, final=True):
        if (not isinstance(texts, list) or not 1 <= len(texts) <= 8
                or any(not isinstance(text, str) or not text.strip() or len(text.encode()) > 16000 for text in texts)):
            raise DeveloperError(ErrorCode.INVALID_INPUT)
        self.lease.validate()
        started = perf_counter()
        try:
            self.lease.begin()
            value = self.request("/api/embed", {"model": self.name, "input": texts, "truncate": False,
                                               "keep_alive": "0s" if final else "30s"})
            if value.get("model") not in {self.name, self.name + ":latest"}:
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            vectors = value.get("embeddings")
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
            normalized = [normalize(vector) for vector in vectors]
            self.lease.finish()
        except BaseException:
            # No retry: a lost response does not prove the old operation ended.
            self.lease.uncertain()
            raise
        def count(name):
            value_ = value.get(name)
            return value_ if type(value_) is int and value_ >= 0 else None
        self.events.append({"kind": "embedding", "texts": len(texts), "seconds": perf_counter() - started,
                            "prompt_eval_count": count("prompt_eval_count"), "total_duration_ns": count("total_duration"),
                            "load_duration_ns": count("load_duration"), "transport": "ollama_loopback_http"})
        return normalized
