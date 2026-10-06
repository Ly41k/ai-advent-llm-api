"""Small HTTP adapters: Ollama runs locally; Groq runs in the cloud."""

from dataclasses import dataclass, asdict
import json
import math
import re
import socket
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class ProviderError(RuntimeError):
    """A safe diagnostic without request headers or provider response bodies."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HTTP:
    def __init__(self, timeout=180, local=False):
        handlers = [NoRedirect()]
        if local:
            handlers.append(ProxyHandler({}))
        self.opener = build_opener(*handlers)
        self.timeout = timeout

    def request(self, url, body=None, headers=None):
        request = Request(url, data=None if body is None else
                          json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          headers={"Content-Type": "application/json", "Accept": "application/json",
                                   "User-Agent": "Bublik-Day26/1.1", **(headers or {})})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as error:
            # Classify only known diagnostic values, never echo response text or credentials.
            try:
                content_type = error.headers.get("Content-Type", "") if error.headers else ""
                body_text = error.read(8192).decode("utf-8", errors="replace")
            except (OSError, ValueError):
                body_text, content_type = "", ""
            finally:
                error.close()
            diagnostic = ""
            if re.search(r"error code\s*:\s*1010\b", body_text, re.IGNORECASE):
                diagnostic = " upstream_code=1010."
            else:
                try:
                    payload = json.loads(body_text)
                except ValueError:
                    payload = None
                if isinstance(payload, dict):
                    diagnostic = " response_format=json."
                    err = payload.get("error")
                    known_types = {"invalid_request_error", "authentication_error", "permission_error",
                                   "permission_denied", "rate_limit_error"}
                    if isinstance(err, dict) and isinstance(err.get("type"), str) and err["type"] in known_types:
                        diagnostic += f" error_type={err['type']}."
                elif "text/html" in content_type or body_text.lstrip().lower().startswith(("<!doctype html", "<html")):
                    diagnostic = " response_format=html."
                elif body_text:
                    diagnostic = " response_format=text."
            endpoint = urlsplit(url).path
            known_endpoints = {"/api/version", "/api/tags", "/api/show", "/api/ps", "/api/chat",
                               "/openai/v1/models", "/openai/v1/chat/completions",
                               "/models", "/chat/completions"}
            location = f" at {request.get_method()} {endpoint}" if endpoint in known_endpoints else ""
            hints = {400: "Check the model and request parameters.",
                     401: "Check GROQ_API_KEY.", 403: "Request was refused; check network restrictions and account/API permissions.",
                     404: "Check the endpoint and installed model.",
                     429: "Rate limit reached; retry later."}
            raise ProviderError(f"HTTP {error.code}{location}.{diagnostic} {hints.get(error.code, 'Provider request failed.')}") from None
        except (TimeoutError, socket.timeout):
            raise ProviderError("Request timed out; increase --timeout or use a smaller local model.") from None
        except URLError:
            raise ProviderError("Cannot reach the provider. For Ollama, start the app or ollama serve.") from None
        except (ValueError, UnicodeError):
            raise ProviderError("Provider returned invalid JSON.") from None
        if not isinstance(result, dict):
            raise ProviderError("Provider response must be a JSON object.")
        if result.get("error"):
            raise ProviderError("Provider returned an error; check server logs/model availability.")
        return result


def count(value):
    return value if type(value) is int and value >= 0 else None


def seconds(value):
    return value / 1_000_000_000 if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def model_matches(actual, requested):
    return actual == requested or (":" not in requested and actual == requested + ":latest")


@dataclass(frozen=True)
class Generation:
    provider: str
    model: str
    answer: str
    latency_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    finish_reason: str | None
    complete: bool
    load_seconds: float | None = None
    generation_seconds: float | None = None
    tokens_per_second: float | None = None

    def to_dict(self):
        return asdict(self)


class OllamaProvider:
    name = "local"

    def __init__(self, model="qwen2.5:7b", url="http://127.0.0.1:11434", timeout=180,
                 temperature=0, max_tokens=2048, num_ctx=8192, http=None):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ProviderError("--url must be a loopback Ollama HTTP URL, e.g. http://127.0.0.1:11434")
        if "cloud" in model.lower():
            raise ProviderError("A cloud-tagged Ollama model cannot demonstrate local inference.")
        self.model, self.url = model, url.rstrip("/")
        self.temperature, self.max_tokens, self.num_ctx = temperature, max_tokens, num_ctx
        self.http = http or HTTP(timeout, local=True)

    def doctor(self):
        version = self.http.request(self.url + "/api/version").get("version")
        tags = self.http.request(self.url + "/api/tags").get("models")
        if not isinstance(tags, list):
            raise ProviderError("Ollama returned an invalid model list.")
        installed = [x.get("name") for x in tags if isinstance(x, dict)]
        if not any(model_matches(x, self.model) for x in installed):
            raise ProviderError(f"Model {self.model} is not installed. Run: ollama pull {self.model}")
        info = self.http.request(self.url + "/api/show", {"model": self.model})
        if info.get("remote_host") or info.get("remote_model"):
            raise ProviderError("Selected Ollama model uses a remote host; choose a downloaded local model.")
        return {"provider": self.name, "model": self.model, "server_version": version,
                "url": self.url, "installed": True, "digest": next(
                    (x.get("digest") for x in tags if isinstance(x, dict) and model_matches(x.get("name"), self.model)), None),
                "details": info.get("details"), "running_models": self.running(),
                "note": "Installed does not mean loaded. A successful generation plus /api/ps verifies loading."}

    def running(self):
        models = self.http.request(self.url + "/api/ps").get("models")
        if not isinstance(models, list):
            raise ProviderError("Ollama returned an invalid running-model list.")
        return [{k: x.get(k) for k in ("name", "model", "digest", "size", "size_vram", "expires_at")}
                for x in models if isinstance(x, dict)]

    def generate(self, messages):
        start = perf_counter()
        response = self.http.request(self.url + "/api/chat", {
            "model": self.model, "messages": messages, "stream": False, "keep_alive": "5m",
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens,
                        "num_ctx": self.num_ctx}})
        elapsed = perf_counter() - start
        message = response.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError("Ollama response has no text message.")
        if not model_matches(response.get("model"), self.model):
            raise ProviderError("Ollama returned a different model than requested.")
        answer = message["content"].strip()
        if not answer:
            raise ProviderError("Ollama returned an empty answer; increase --max-tokens for reasoning models.")
        reason = response.get("done_reason")
        duration = seconds(response.get("eval_duration"))
        output = count(response.get("eval_count"))
        return Generation(self.name, response["model"], answer, elapsed,
                          count(response.get("prompt_eval_count")), output, reason,
                          response.get("done") is True and reason == "stop",
                          seconds(response.get("load_duration")), duration,
                          output / duration if output is not None and duration else None)


class GroqProvider:
    name = "cloud"
    url = "https://api.groq.com/openai/v1"

    def __init__(self, api_key, model="openai/gpt-oss-20b", timeout=180,
                 temperature=0, max_tokens=2048, http=None):
        if not api_key or not api_key.strip():
            raise ProviderError("GROQ_API_KEY is missing. Set it in the environment or root .env.")
        self.model, self.api_key = model, api_key.strip()
        self.temperature, self.max_tokens = temperature, max_tokens
        self.http = http or HTTP(timeout)

    def request(self, endpoint, body=None):
        return self.http.request(self.url + endpoint, body,
                                 {"Authorization": f"Bearer {self.api_key}"})

    def doctor(self):
        models = self.request("/models").get("data")
        if not isinstance(models, list):
            raise ProviderError("Groq returned an invalid model list.")
        if not any(x.get("id") == self.model for x in models if isinstance(x, dict)):
            raise ProviderError(f"Groq model {self.model} is unavailable; choose --cloud-model from /models.")
        return {"provider": self.name, "model": self.model, "available": True,
                "note": "Model availability is checked; generation is verified separately."}

    def generate(self, messages):
        body = {"model": self.model, "messages": messages, "stream": False,
                "temperature": self.temperature, "max_completion_tokens": self.max_tokens}
        if self.model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
            body["reasoning_effort"] = "low"
        start = perf_counter()
        response = self.request("/chat/completions", body)
        elapsed = perf_counter() - start
        try:
            choice = response["choices"][0]
            answer = choice["message"]["content"]
            reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("Groq returned an invalid completion.") from None
        if not isinstance(answer, str) or not answer.strip():
            raise ProviderError("Groq returned an empty answer; increase --max-tokens.")
        if response.get("model") != self.model:
            raise ProviderError("Groq returned a different model than requested.")
        usage = response.get("usage") or {}
        if not isinstance(usage, dict):
            raise ProviderError("Groq returned invalid usage metadata.")
        return Generation(self.name, response.get("model") or self.model, answer.strip(), elapsed,
                          count(usage.get("prompt_tokens")), count(usage.get("completion_tokens")),
                          reason, reason == "stop")
