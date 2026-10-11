"""API v1 and HTTPS Web UI. One process owns inference; explicit private proxy mode.

All sync SQLite/password work is offloaded as complete operations. Never log
validation input, cookie/auth headers, upstream exceptions, prompts or replies.
"""
import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
import ipaddress
import hashlib
import json
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit,parse_qsl
import uuid

from fastapi import Depends, FastAPI, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.security import APIKeyCookie, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException

from .domain import (CapacityExceeded, Conflict, DEFAULT_PROMPT_VERSION, InvalidInput, ModelProfile, ModelUnavailable,
                     NotFound, ServiceError, StorageUnavailable, TERMINAL_STATUSES)
from .inference.coordinator import Coordinator, durable_call
from .inference.ollama import OllamaAdapter
from .security import AuthError, COOKIE, Forbidden, RateLimited, SecurityStore, digest
from .storage import ChatRepository

PREFIX = "/api/v1"
SAFE_CONTEXT = {"policy_version", "omitted_turns", "input_token_upper_bound", "model_identity", "memory"}
UI_FILES = {"/": ("index.html", "text/html"),
            "/assets/app.js": ("app.js", "text/javascript"),
            "/assets/app.css": ("app.css", "text/css"),
            "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
            "/assets/icon-180.png": ("icon-180.png", "image/png"),
            "/assets/icon-192.png": ("icon-192.png", "image/png"),
            "/assets/icon-512.png": ("icon-512.png", "image/png")}
UI_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
          "connect-src 'self'; img-src 'self'; manifest-src 'self'; worker-src 'none'; frame-ancestors 'none'; "
          "base-uri 'none'; form-action 'self'; object-src 'none'")


@dataclass(frozen=True)
class HTTPSettings:
    database: Path
    origins: tuple = ("https://localhost:8000", "https://127.0.0.1:8000")
    ollama_url: str = "http://127.0.0.1:11434"
    generation_limit: int = 10
    body_limit: int = 32768
    body_timeout: float = 10
    sse_poll: float = .5
    sse_lifetime: float = 900
    trusted_loopback_proxy: bool = False
    prompt_version: str = DEFAULT_PROMPT_VERSION

    def __post_init__(self):
        ModelProfile(prompt_version=self.prompt_version).validate()
        if not self.origins:
            raise ValueError("explicit HTTPS origins required")
        for origin in self.origins:
            parsed = urlsplit(origin)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.path or parsed.query or parsed.fragment or parsed.netloc != parsed.netloc.lower()):
                raise ValueError("origin must be canonical HTTPS origin without path")
        if not 1024 <= self.body_limit <= 32768 or self.body_timeout <= 0 or self.sse_poll <= 0 or self.sse_lifetime <= 0:
            raise ValueError("invalid HTTP limits")


def error_response(error, request_id):
    code = error.code
    if isinstance(error, AuthError):
        status = 401
    elif isinstance(error, Forbidden):
        status = 403
    elif isinstance(error, NotFound):
        status = 404
    elif isinstance(error, RateLimited):
        status = 429
    elif isinstance(error, CapacityExceeded):
        status = 503 if code == "global_queue_full" else 429
    elif isinstance(error, Conflict):
        status = 503 if code == "inference_recovery_required" else 409
    elif isinstance(error, InvalidInput):
        status = {"request_body_too_large":413,"request_body_timeout":408,"unsupported_media_type":415,
                  "invalid_host":400,"secure_transport_required":400,"not_found":404,
                  "method_not_allowed":405}.get(code,422)
    elif isinstance(error, (StorageUnavailable, ModelUnavailable)):
        status = 503
        # Collapse adapter/OS diagnostics at the HTTP boundary.
        code = "storage_unavailable" if isinstance(error, StorageUnavailable) else "model_unavailable"
    else:
        status, code = 503, "service_unavailable"
    messages = {401:"Authentication required.",403:"Request denied.",404:"Resource not found.",
                409:"Reload the chat before retrying.",429:"Retry after the indicated delay.",
                503:"Service is temporarily unavailable."}
    headers = {"Cache-Control":"no-store", "X-Request-ID":request_id}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    if status in {429,503}:
        headers["Retry-After"] = str(getattr(error,"retry_after",5))
    return JSONResponse({"error":{"code":code,"message":messages.get(status,"Invalid request."),
                        "retryable":status in {408,429,503}},"request_id":request_id},status_code=status,headers=headers)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


class RequestBoundary:
    """ASGI boundary bounds actual received bytes, including chunked requests."""
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.hosts = {urlsplit(o).netloc for o in settings.origins}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id, started = uuid.uuid4().hex, False
        scope.setdefault("state", {})["request_id"] = request_id
        async def safe_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = [(k,v) for k,v in message.get("headers",[]) if k.lower() not in {b"cache-control",b"x-request-id",b"content-security-policy"}]
                headers += [(b"cache-control",b"no-store"),(b"x-request-id",request_id.encode()),
                    (b"x-content-type-options",b"nosniff"),(b"referrer-policy",b"no-referrer"),
                    (b"content-security-policy",(UI_CSP if scope["path"] in UI_FILES else "default-src 'none'; frame-ancestors 'none'; base-uri 'none'").encode()),
                    (b"x-frame-options",b"DENY")]
                if scope["scheme"] == "https":
                    headers.append((b"strict-transport-security",b"max-age=86400"))
                message = {**message,"headers":headers}
            await send(message)
        try:
            headers = {}
            for name, value in scope["headers"]:
                name = name.lower()
                if name in {b"host",b"authorization",b"cookie",b"origin",b"content-length",b"content-type",b"x-csrf-token",b"idempotency-key",b"x-forwarded-proto",b"x-forwarded-host",b"forwarded"} and name in headers:
                    raise InvalidInput("duplicate_header")
                headers[name] = value
            # Explicit operator mode, raw socket peer retained by Uvicorn. Never
            # trust X-Forwarded-For/Tailscale identity for login or authorization.
            # A local OS process is trusted just as one with access to the DB.
            if self.settings.trusted_loopback_proxy:
                peer = (scope.get("client") or ("",0))[0]
                if (peer not in {"127.0.0.1", "::1"} or scope["scheme"] != "http"
                        or headers.get(b"x-forwarded-proto") != b"https"
                        or b"forwarded" in headers):
                    raise InvalidInput("secure_transport_required")
                # Do not use a forwarded hostname to override Host. Both proxies
                # must preserve Host; optional XFH must agree exactly.
                if b"x-forwarded-host" in headers and headers[b"x-forwarded-host"].lower() != headers.get(b"host",b"").lower():
                    raise InvalidInput("invalid_host")
                scope = {**scope, "scheme":"https"}
            host = headers.get(b"host",b"").decode("ascii").lower()
            if host not in self.hosts:
                raise InvalidInput("invalid_host")
            origin = headers.get(b"origin")
            if origin is not None and origin.decode("ascii") not in self.settings.origins:
                raise Forbidden("origin_denied")
            query_keys = {k.lower() for k,_ in parse_qsl(scope.get("query_string",b"").decode("utf-8"),max_num_fields=20)}
            if query_keys & {"token","access_token","api_key","authorization","csrf_token"}:
                raise InvalidInput("credentials_in_query_forbidden")
            # Plain HTTP is an operator loopback API only. Secure browser cookies
            # always require HTTPS; forwarded headers are disabled in CLI by default.
            if scope["scheme"] != "https" and scope["path"] != PREFIX+"/health/live":
                peer = (scope.get("client") or ("",0))[0]
                if scope["path"] in UI_FILES or b"cookie" in headers or scope["path"].startswith(PREFIX+"/auth/") or not ipaddress.ip_address(peer).is_loopback:
                    raise InvalidInput("secure_transport_required")
            if scope["method"] not in {"GET","HEAD","OPTIONS"}:
                if headers.get(b"content-type",b"").split(b";",1)[0].strip().lower() != b"application/json":
                    raise InvalidInput("unsupported_media_type")
                if b"content-length" in headers:
                    length = int(headers[b"content-length"])
                    if length < 0:
                        raise InvalidInput()
                    if length > self.settings.body_limit:
                        raise InvalidInput("request_body_too_large")
                body = bytearray()
                async with asyncio.timeout(self.settings.body_timeout):
                    while True:
                        incoming = await receive()
                        if incoming["type"] == "http.disconnect":
                            return
                        chunk = incoming.get("body",b"")
                        if len(body)+len(chunk) > self.settings.body_limit:
                            raise InvalidInput("request_body_too_large")
                        body.extend(chunk)
                        if not incoming.get("more_body",False):
                            break
                try:
                    json.loads(body.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                except (ValueError, UnicodeError):
                    raise InvalidInput("invalid_json") from None
                delivered = False
                original_receive = receive
                async def buffered_receive():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type":"http.request","body":bytes(body),"more_body":False}
                    return await original_receive()
                receive = buffered_receive
            await self.app(scope, receive, safe_send)
        except TimeoutError:
            if not started:
                await error_response(InvalidInput("request_body_timeout"),request_id)(scope,receive,safe_send)
        except ServiceError as error:
            if not started:
                await error_response(error,request_id)(scope,receive,safe_send)
        except (ValueError,UnicodeError):
            if not started:
                await error_response(InvalidInput(),request_id)(scope,receive,safe_send)
        except Exception:
            # Never allow an unhandled exception carrying a prompt/secret to reach
            # Uvicorn's traceback logger. Stream failures close; GET can resync.
            if not started:
                await error_response(ServiceError(),request_id)(scope,receive,safe_send)


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid",strict=True)


class CreateChat(StrictBody):
    title: str = Field(default="Bublik chat",min_length=1,max_length=120)


class SendMessage(StrictBody):
    content: str = Field(min_length=1,max_length=16384)
    expected_revision: int = Field(ge=0)
    use_memory: bool = False


class RetryMessage(StrictBody):
    expected_revision: int = Field(ge=0)
    use_memory: bool = False


class SearchMemory(StrictBody):
    query: str = Field(min_length=1,max_length=2048)


class Login(StrictBody):
    username: str = Field(min_length=1,max_length=80)
    password: str = Field(min_length=1,max_length=256)


def runtime_manifest():
    root = Path(__file__).resolve().parent
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.suffix in {".py",".sql",".html",".css",".js",".png",".webmanifest"}}


def public_generation(value):
    result = {k:v for k,v in value.items() if k != "context"}
    result["context"] = {k:v for k,v in value["context"].items() if k in SAFE_CONTEXT}
    return result


def chat_cursor(ident):
    return base64.urlsafe_b64encode(ident.encode()).decode().rstrip("=")


def parse_cursor(value):
    if value is None:
        return None
    try:
        if len(value) != 43:
            raise ValueError()
        result = base64.b64decode(value+"=",altchars=b"-_",validate=True).decode("ascii")
        if len(result) != 32 or any(c not in "0123456789abcdef" for c in result):
            raise ValueError()
        return result
    except (ValueError,UnicodeError):
        raise InvalidInput("invalid_chat_cursor") from None


def create_app(settings, *, adapter_factory=None, repository=None, security=None):
    """Factory: testing may inject a synthetic adapter, public CLI never can."""
    @asynccontextmanager
    async def lifespan(app):
        repo = repository or await asyncio.to_thread(ChatRepository, settings.database)
        auth = security or await asyncio.to_thread(SecurityStore,repo,generation_limit=settings.generation_limit)
        repo.admission_policy = auth.generation_admission
        adapter = adapter_factory() if adapter_factory else OllamaAdapter(
            ModelProfile(prompt_version=settings.prompt_version), url=settings.ollama_url)
        app.state.repository, app.state.auth = repo, auth
        app.state.streams, app.state.login_active = {}, 0
        app.state.ready_cache, app.state.ready_lock = None, asyncio.Lock()
        app.state.runtime_source = runtime_manifest()
        try:
            async with Coordinator(repo,adapter) as coordinator:
                app.state.coordinator = coordinator
                yield
        finally:
            await adapter.aclose()
            repo.admission_policy = None

    app = FastAPI(title="Bublik Private AI Service",version="1.0.0",lifespan=lifespan,
                  docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(RequestBoundary,settings=settings)
    async def ui_file(request:Request):
        name, media = UI_FILES[request.url.path]
        data = await asyncio.to_thread((Path(__file__).resolve().parent/"web_ui"/name).read_bytes)
        return Response(data,media_type=media)
    for path in UI_FILES:
        app.add_api_route(path,ui_file,methods=["GET","HEAD"],include_in_schema=False)
    bearer_scheme = HTTPBearer(auto_error=False)
    cookie_scheme = APIKeyCookie(name=COOKIE,auto_error=False)

    @app.exception_handler(ServiceError)
    async def service_error(request,error):
        return error_response(error,request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,error):
        # Do not serialize error.errors(): Pydantic includes the submitted input.
        return error_response(InvalidInput("invalid_request"),request.state.request_id)

    @app.exception_handler(HTTPException)
    async def framework_error(request,error):
        return error_response(InvalidInput("not_found" if error.status_code==404 else "method_not_allowed"),request.state.request_id)

    def peer_key(request):
        return digest(request.client.host if request.client else "unknown")

    async def principal(request:Request, bearer=Security(bearer_scheme), cookie=Security(cookie_scheme)):
        auth = request.app.state.auth
        if request.headers.get("authorization") and request.cookies.get(COOKIE):
            raise Forbidden("ambiguous_credentials")
        if request.headers.get("authorization"):
            if bearer is None or bearer.scheme.lower() != "bearer":
                raise AuthError()
            user = await asyncio.to_thread(auth.token_principal,bearer.credentials)
        elif cookie:
            user = await asyncio.to_thread(auth.browser_principal,cookie)
            if request.method not in {"GET","HEAD","OPTIONS"}:
                await csrf(request)
        else:
            await asyncio.to_thread(auth.rate,"unauth:"+peer_key(request),60)
            raise AuthError()
        await asyncio.to_thread(auth.rate,"http:"+user.owner,120)
        return user

    def require(scope):
        async def dependency(user=Depends(principal)):
            if scope not in user.scopes:
                raise Forbidden()
            return user
        return dependency

    async def csrf(request):
        raw = request.cookies.get(COOKIE)
        if request.headers.get("authorization"):
            raise Forbidden("ambiguous_credentials")
        if not raw:
            raise Forbidden("csrf_failed")
        session = await asyncio.to_thread(request.app.state.auth.session,raw)
        origin = request.headers.get("origin")
        supplied = request.headers.get("x-csrf-token","")
        # Same origin, not merely another permitted hostname. Origins may have
        # separate cookies; a LAN page cannot submit to a Tailscale origin.
        if origin not in settings.origins or origin != str(request.base_url).rstrip("/"):
            raise Forbidden("csrf_failed")
        if not secrets.compare_digest(supplied.encode(),session["csrf"].encode()):
            raise Forbidden("csrf_failed")

    def set_cookie(response,raw,age):
        response.set_cookie(COOKIE,raw,max_age=age,httponly=True,secure=True,samesite="strict",path="/")

    @app.get(PREFIX+"/health/live")
    async def live():
        return {"status":"alive"}

    @app.get(PREFIX+"/health/ready")
    async def ready(request:Request,user=Depends(require("service:read"))):
        async with app.state.ready_lock:
            cache = app.state.ready_cache
            if not cache or time.monotonic()-cache[0] > 5:
                model_ready, metadata = False, None
                try:
                    async with asyncio.timeout(5):
                        metadata = (await app.state.coordinator.adapter.doctor()).to_dict()
                        model_ready = True
                except (ServiceError,TimeoutError):
                    pass
                app.state.ready_cache = (time.monotonic(),model_ready,metadata)
            model_ready = app.state.ready_cache[1]
        state = await asyncio.to_thread(app.state.repository.queue_status)
        ok = model_ready and not state["inference_recovery_required"] and app.state.coordinator.last_error != "storage_unavailable"
        return JSONResponse({"status":"ready" if ok else "unavailable","model_ready":model_ready,"model":app.state.ready_cache[2],
                            "profile":app.state.coordinator.adapter.profile.to_dict(),
                            "runtime_source_sha256":app.state.runtime_source,
                            "runtime_source_unchanged":app.state.runtime_source==await asyncio.to_thread(runtime_manifest),**state},
                            status_code=200 if ok else 503,headers={} if ok else {"Retry-After":"5"})

    @app.get(PREFIX+"/auth/session")
    async def session(request:Request):
        if request.headers.get("authorization"):
            raise Forbidden("browser_session_required")
        auth = app.state.auth
        await asyncio.to_thread(auth.rate,"bootstrap:"+peer_key(request),60)
        raw = request.cookies.get(COOKIE)
        try:
            row = await asyncio.to_thread(auth.session,raw)
            fresh = False
        except AuthError:
            raw = await asyncio.to_thread(auth.new_session)
            row = await asyncio.to_thread(auth.session,raw)
            fresh = True
        response = JSONResponse({"user":None if row["owner_id"] is None else {"id":row["owner_id"],"username":row["username"]},
                                 "csrf_token":row["csrf"],"expires_at":row["expires_at"]})
        if fresh:
            set_cookie(response,raw,900)
        return response

    @app.post(PREFIX+"/auth/login")
    async def login(body:Login,request:Request):
        await csrf(request)
        await asyncio.to_thread(app.state.auth.rate,"login:"+peer_key(request),5)
        if app.state.login_active >= 2:
            raise CapacityExceeded("login_busy")
        app.state.login_active += 1
        try:
            raw = await durable_call(app.state.auth.login,body.username,body.password,request.cookies[COOKIE])
        finally:
            app.state.login_active -= 1
        row = await asyncio.to_thread(app.state.auth.session,raw)
        response = JSONResponse({"user":{"id":row["owner_id"],"username":row["username"]},"csrf_token":row["csrf"],"expires_at":row["expires_at"]})
        set_cookie(response,raw,43200)
        return response

    @app.post(PREFIX+"/auth/logout")
    async def logout(request:Request):
        await csrf(request)
        await asyncio.to_thread(app.state.auth.rate,"logout:"+peer_key(request),60)
        await asyncio.to_thread(app.state.auth.logout,request.cookies[COOKIE])
        response = JSONResponse({"logged_out":True})
        response.delete_cookie(COOKIE,path="/",secure=True,httponly=True,samesite="strict")
        return response

    @app.post(PREFIX+"/chats",status_code=201)
    async def create_chat(body:CreateChat,request:Request,user=Depends(require("chats:write"))):
        receipt = await asyncio.to_thread(app.state.repository.create_chat,user.owner,body.title,key=request.headers.get("idempotency-key"))
        return JSONResponse(asdict(receipt),status_code=200 if receipt.replayed else 201)

    @app.get(PREFIX+"/chats")
    async def chats(limit:int=50,cursor:str|None=None,user=Depends(require("chats:read"))):
        rows = await asyncio.to_thread(app.state.repository.list_chats,user.owner,limit=limit,after=parse_cursor(cursor))
        return {"items":rows,"next_cursor":chat_cursor(rows[-1]["id"]) if len(rows)==limit else None}

    @app.get(PREFIX+"/chats/{chat}")
    async def get_chat(chat:str,user=Depends(require("chats:read"))):
        return await asyncio.to_thread(app.state.repository.get_chat,user.owner,chat)

    @app.get(PREFIX+"/chats/{chat}/messages")
    async def history(chat:str,after_sequence:int=0,limit:int=100,latest:bool=False,
                      before_sequence:int|None=None,user=Depends(require("chats:read"))):
        if latest or before_sequence is not None:
            if after_sequence != 0:
                raise InvalidInput("invalid_history_cursor")
            rows = await asyncio.to_thread(app.state.repository.history_tail,user.owner,chat,
                                          before_sequence=before_sequence,limit=limit)
            return {"items":rows,"next_before_sequence":rows[0]["sequence"] if len(rows)==limit else None}
        rows = await asyncio.to_thread(app.state.repository.history,user.owner,chat,after_sequence=after_sequence,limit=limit)
        return {"items":rows,"next_after_sequence":rows[-1]["sequence"] if len(rows)==limit else None}

    @app.post(PREFIX+"/chats/{chat}/messages",status_code=202)
    async def send_message(chat:str,body:SendMessage,request:Request,user=Depends(require("chats:write"))):
        receipt = await app.state.coordinator.service.send(user.owner,chat,body.content,expected_revision=body.expected_revision,key=request.headers.get("idempotency-key"),use_memory=body.use_memory)
        return JSONResponse(asdict(receipt),status_code=200 if receipt.replayed else 202)

    @app.post(PREFIX+"/messages/{message}/retry",status_code=202)
    async def retry_message(message:str,body:RetryMessage,request:Request,user=Depends(require("chats:write"))):
        receipt = await app.state.coordinator.service.retry(user.owner,message,expected_revision=body.expected_revision,key=request.headers.get("idempotency-key"),use_memory=body.use_memory)
        return JSONResponse(asdict(receipt),status_code=200 if receipt.replayed else 202)

    @app.post(PREFIX+"/memory/search")
    async def search_memory(body:SearchMemory,user=Depends(require("chats:read"))):
        # JSON body avoids putting personal search terms in URLs/access logs.
        from .storage.repository import text
        text(body.query,2048,"invalid_memory_query")
        return await asyncio.to_thread(app.state.coordinator.service.memory.search,user.owner,body.query)

    @app.get(PREFIX+"/chats/{chat}/messages/{message}")
    async def source_message(chat:str,message:str,user=Depends(require("chats:read"))):
        return await asyncio.to_thread(app.state.repository.memory_source,user.owner,chat,message)

    @app.get(PREFIX+"/chats/{chat}/messages/{message}/context")
    async def source_context(chat:str,message:str,before:int=4,after:int=4,user=Depends(require("chats:read"))):
        return await asyncio.to_thread(app.state.repository.memory_context,user.owner,chat,message,
                                       before=before,after=after)

    @app.get(PREFIX+"/generations/{generation}")
    async def generation(generation:str,user=Depends(require("chats:read"))):
        return public_generation(await asyncio.to_thread(app.state.repository.get_generation,user.owner,generation))

    @app.get(PREFIX+"/chats/{chat}/export")
    async def export(chat:str,user=Depends(require("chats:export"))):
        # Export can be large; one consistent DB snapshot, no credentials/capability.
        return await asyncio.to_thread(app.state.repository.export_chat,user.owner,chat)

    @app.get(PREFIX+"/openapi.json",include_in_schema=False)
    async def openapi(user=Depends(require("service:read"))):
        return app.openapi()

    @app.get(PREFIX+"/generations/{generation}/events")
    async def events(generation:str,request:Request,user=Depends(require("chats:read"))):
        initial = await asyncio.to_thread(app.state.repository.get_generation,user.owner,generation)
        if app.state.streams.get(user.owner,0)>=2 or sum(app.state.streams.values())>=8:
            raise RateLimited(5)
        app.state.streams[user.owner] = app.state.streams.get(user.owner,0)+1
        async def stream():
            seen, start, heartbeat = None,time.monotonic(),time.monotonic()
            current = initial
            try:
                while True:
                    await asyncio.to_thread(app.state.auth.revalidate,user)
                    version = current["stream_revision"]
                    if seen != version:
                        # Full persisted snapshots even on reconnect. Last-Event-ID
                        # is intentionally not used to manufacture missing deltas.
                        value = json.dumps(public_generation(current),ensure_ascii=False,separators=(",",":"))
                        yield f"id: {version}\nevent: snapshot\ndata: {value}\n\n"
                        seen = version
                    if current["status"] in TERMINAL_STATUSES:
                        return
                    if time.monotonic()-start>=settings.sse_lifetime:
                        yield "event: reconnect\ndata: {}\n\n"
                        return
                    if time.monotonic()-heartbeat>=10:
                        yield ": heartbeat\n\n"
                        heartbeat = time.monotonic()
                    await asyncio.sleep(settings.sse_poll)
                    if await request.is_disconnected():
                        return
                    current = await asyncio.to_thread(app.state.repository.get_generation,user.owner,generation)
            except ServiceError as error:
                code = "authentication_required" if isinstance(error,AuthError) else "service_unavailable"
                yield "event: error\ndata: "+json.dumps({"error":{"code":code}})+"\n\n"
            except Exception:
                yield 'event: error\ndata: {"error":{"code":"service_unavailable"}}\n\n'
        class LeasedStream(StreamingResponse):
            async def __call__(self,scope,receive,send):
                try:
                    await super().__call__(scope,receive,send)
                finally:
                    app.state.streams[user.owner]-=1
                    if app.state.streams[user.owner]==0:
                        del app.state.streams[user.owner]
        return LeasedStream(stream(),media_type="text/event-stream",headers={"X-Accel-Buffering":"no"})

    return app
