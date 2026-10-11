"""Bounded async Ollama streaming; literal loopback only, no redirects/proxies/retries."""
import asyncio
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from time import perf_counter
from urllib.parse import urlsplit

import httpx

from bublik_service.domain import InvalidInput, ModelIdentity, ModelProfile, ModelUnavailable, ServiceError
from bublik_service.storage.repository import MAX_RESPONSE_BYTES
from .context import TEMPLATE_SHA256, upper_bound
from .engine import engine_epoch


class InferenceError(ServiceError):
    def __init__(self, code="invalid_model_response", *, uncertain=True):
        super().__init__(code)
        self.uncertain = uncertain


@dataclass(frozen=True)
class Doctor:
    identity: ModelIdentity
    engine_epoch: str
    loaded_models: tuple
    installed_bytes: int

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Answer:
    content: str
    status: str
    metrics: dict


def digest(value):
    if not isinstance(value, str):
        raise ModelUnavailable("invalid_model_metadata")
    value = value.removeprefix("sha256:")
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ModelUnavailable("invalid_model_metadata")
    return value


def nonnegative(value, *, integer=False):
    if (type(value) not in ((int,) if integer else (int, float))
            or not math.isfinite(value) or value < 0):
        raise InferenceError()
    return value


async def records(response):
    buffer, total = bytearray(), 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        buffer.extend(chunk)
        if total > 2 * 1024 * 1024:
            raise InferenceError()
        while b"\n" in buffer:
            line, _, rest = buffer.partition(b"\n")
            buffer = bytearray(rest)
            if len(line) > 96 * 1024:
                raise InferenceError()
            if line.strip():
                yield json.loads(line)
        if len(buffer) > 96 * 1024:
            raise InferenceError()
    if buffer.strip():
        yield json.loads(buffer)


class OllamaAdapter:
    def __init__(self, profile=None, *, url="http://127.0.0.1:11434", deadline=300,
                 connect_timeout=3, read_timeout=30, transport=None, epoch_probe=engine_epoch):
        parsed = urlsplit(url)
        try:
            port = parsed.port or 11434
        except ValueError:
            raise InvalidInput("invalid_ollama_url") from None
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or not 1 <= port <= 65535):
            raise InvalidInput("ollama_url_must_be_literal_loopback")
        for value in (deadline, connect_timeout, read_timeout):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise InvalidInput("invalid_inference_timeout")
        self.profile = profile or ModelProfile()
        self.profile.validate()
        if self.profile.model != "qwen2.5:14b":
            raise InvalidInput("unsupported_model")
        self.url = url.rstrip("/")
        self.port, self.deadline, self.epoch_probe = port, deadline, epoch_probe
        self.client = httpx.AsyncClient(
            trust_env=False, follow_redirects=False, transport=transport,
            timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
            headers={"Accept": "application/json", "Accept-Encoding": "identity"})

    async def aclose(self):
        await self.client.aclose()

    async def _json(self, path, body=None):
        try:
            async with asyncio.timeout(15):
                async with self.client.stream("GET" if body is None else "POST", self.url + path, json=body) as response:
                    if response.status_code != 200:
                        raise ModelUnavailable()
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 2 * 1024 * 1024:
                            raise ModelUnavailable("model_metadata_too_large")
                    result = json.loads(content)
        except (httpx.HTTPError, TimeoutError, ValueError, UnicodeError):
            raise ModelUnavailable() from None
        if not isinstance(result, dict) or result.get("error"):
            raise ModelUnavailable()
        return result

    async def doctor(self):
        epoch = await asyncio.to_thread(self.epoch_probe, self.port)
        version = (await self._json("/api/version")).get("version")
        tags = (await self._json("/api/tags")).get("models")
        if not isinstance(tags, list):
            raise ModelUnavailable("invalid_model_metadata")
        selected = [m for m in tags if isinstance(m, dict) and m.get("name") == self.profile.model]
        if len(selected) != 1:
            raise ModelUnavailable("model_not_installed")
        tag = selected[0]
        info = await self._json("/api/show", {"model": self.profile.model})
        if info.get("remote_host") or info.get("remote_model"):
            raise ModelUnavailable("remote_model_forbidden")
        details, model_info, template = info.get("details"), info.get("model_info"), info.get("template")
        if (not isinstance(details, dict) or not isinstance(model_info, dict) or not isinstance(template, str)
                or details.get("family") != "qwen2" or details.get("format") != "gguf"
                or details.get("quantization_level") != "Q4_K_M"
                or not re.fullmatch(r"14(?:\.\d+)?B", str(details.get("parameter_size")))
                or model_info.get("general.architecture") != "qwen2"
                or model_info.get("tokenizer.ggml.model") != "gpt2"
                or model_info.get("tokenizer.ggml.pre") != "qwen2"
                or type(model_info.get("qwen2.context_length")) is not int
                or model_info["qwen2.context_length"] < self.profile.num_ctx
                or info.get("messages")):
            raise ModelUnavailable("unsupported_model_metadata")
        sha = hashlib.sha256(template.replace("\r\n", "\n").strip().encode()).hexdigest()
        if sha != TEMPLATE_SHA256:
            raise ModelUnavailable("unsupported_template")
        parameters = info.get("parameters", "")
        if not isinstance(parameters, str) or len(parameters) > 65536:
            raise ModelUnavailable("invalid_model_metadata")
        try:
            identity = ModelIdentity(self.profile.model, digest(tag.get("digest")), sha, version,
                                     parameters_sha256=hashlib.sha256(parameters.encode()).hexdigest())
            identity.validate(self.profile)
        except (InvalidInput, TypeError):
            raise ModelUnavailable("invalid_model_metadata") from None
        loaded = (await self._json("/api/ps")).get("models")
        if not isinstance(loaded, list) or any(not isinstance(m, dict) for m in loaded):
            raise ModelUnavailable("invalid_model_metadata")
        # No silently unloading bge-m3/Revik models to make this check pass.
        if len(loaded) > 1 or any(digest(m.get("digest")) != identity.digest for m in loaded):
            raise ModelUnavailable("unexpected_loaded_model")
        for model in loaded:
            if model.get("name") != self.profile.model:
                raise ModelUnavailable("unexpected_loaded_model")
            for field in ("size", "size_vram", "context_length"):
                if model.get(field) is not None and (type(model[field]) is not int or model[field] < 0):
                    raise ModelUnavailable("invalid_model_metadata")
            if model.get("context_length") not in (None, self.profile.num_ctx):
                raise ModelUnavailable("loaded_context_mismatch")
        safe_loaded = tuple({k: m.get(k) for k in ("name", "digest", "size", "size_vram", "context_length")} for m in loaded)
        if epoch != await asyncio.to_thread(self.epoch_probe, self.port):
            raise ModelUnavailable("engine_changed_during_doctor")
        size = tag.get("size")
        if type(size) is not int or size <= 0:
            raise ModelUnavailable("invalid_model_metadata")
        return Doctor(identity, epoch, safe_loaded, size)

    async def generate(self, job, on_chunk):
        profile = ModelProfile(**job["profile"])
        profile.validate()
        context = job["context"]
        messages = context["messages"]
        from bublik_service.languages import snapshot_system_prompt
        try:
            system = snapshot_system_prompt(profile, context)
        except InvalidInput:
            raise InferenceError("invalid_model_response", uncertain=False) from None
        # Defense in depth against tampered/legacy persisted jobs.
        if (profile != self.profile or not context.get("model_identity")
                or not messages or messages[0] != {"role": "system", "content": system}
                or upper_bound(messages) != context["input_token_upper_bound"]
                or upper_bound(messages) + profile.max_output + profile.margin > profile.num_ctx):
            raise InferenceError("invalid_model_response", uncertain=False)
        body = {"model": profile.model, "messages": messages, "stream": True, "keep_alive": "5m",
                "options": {"temperature": profile.temperature, "num_predict": profile.max_output,
                            "num_ctx": profile.num_ctx}}
        start, first, answer = perf_counter(), None, ""
        terminal_seen = False
        try:
            async with asyncio.timeout(self.deadline):
                async with self.client.stream("POST", self.url + "/api/chat", json=body) as response:
                    if response.status_code != 200:
                        # A server-side request may already have begun even if HTTP fails.
                        raise InferenceError("model_unavailable")
                    async for record in records(response):
                        if (not isinstance(record, dict) or record.get("error")
                                or record.get("model") != profile.model or type(record.get("done")) is not bool):
                            raise InferenceError()
                        message = record.get("message")
                        if (not isinstance(message, dict) or message.get("role") != "assistant"
                                or not isinstance(message.get("content"), str)
                                or message.get("tool_calls") or message.get("thinking") or message.get("images")):
                            raise InferenceError()
                        fragment = message["content"]
                        answer += fragment
                        if "\x00" in answer or len(answer.encode("utf-8")) > MAX_RESPONSE_BYTES:
                            raise InferenceError()
                        if fragment:
                            first = first if first is not None else perf_counter() - start
                            await on_chunk(answer)
                        if record["done"]:
                            terminal_seen = True
                            reason = record.get("done_reason")
                            if reason not in {"stop", "length"} or not answer.strip():
                                raise InferenceError(uncertain=False)
                            inputs = nonnegative(record.get("prompt_eval_count"), integer=True)
                            outputs = nonnegative(record.get("eval_count"), integer=True)
                            if inputs > context["input_token_upper_bound"] or outputs > profile.max_output:
                                raise InferenceError("invalid_model_response", uncertain=False)
                            duration = nonnegative(record.get("eval_duration")) / 1e9
                            load = nonnegative(record.get("load_duration")) / 1e9
                            return Answer(answer, "completed" if reason == "stop" else "truncated",
                                {"input_tokens": inputs, "output_tokens": outputs,
                                 "first_token_seconds": first, "inference_seconds": duration,
                                 "load_seconds": load, "tokens_per_second": outputs / duration if duration else None})
                    # EOF without a terminal done record is an interrupted stream.
                    raise InferenceError()
        except (TimeoutError, httpx.TimeoutException):
            raise InferenceError("model_timeout", uncertain=not terminal_seen) from None
        except httpx.ConnectError:
            raise InferenceError("model_unavailable", uncertain=False) from None
        except (httpx.HTTPError, ValueError, UnicodeError):
            raise InferenceError(uncertain=not terminal_seen) from None
        except InferenceError as error:
            if terminal_seen:
                error.uncertain = False
            raise
