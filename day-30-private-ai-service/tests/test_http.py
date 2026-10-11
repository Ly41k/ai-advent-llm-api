"""Real SQLite + ASGI API + synthetic inference over loopback; NOT real Qwen/LAN."""
import asyncio
from dataclasses import replace
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import httpx

from bublik_service.http_api import HTTPSettings,create_app
from bublik_service.security import COOKIE,SCOPES,SecurityStore,password_hash,AuthError,RateLimited
from bublik_service.storage import ChatRepository
from bublik_service.storage.database import Database
from test_inference import Handler,FAKE_TEMPLATE,FAKE_SHA,DIGEST
from bublik_service.inference.ollama import OllamaAdapter

P = "/api/v1"
PASSWORD = "Synthetic-password-123"


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = ChatRepository(Path(self.temp.name)/"chat.sqlite3")
        self.owner = self.repo.create_user("alice",password_hash(PASSWORD))
        self.other = self.repo.create_user("bob",password_hash(PASSWORD))
        self.auth = SecurityStore(self.repo,generation_limit=10)
        self.token = self.auth.issue_token(self.owner,"test",SCOPES)["token"]
        self.other_token = self.auth.issue_token(self.other,"other",SCOPES)["token"]
        self.backend = ThreadingHTTPServer(("127.0.0.1",0),Handler)
        for name,value in {"offline":False,"remote":False,"loaded":False,"foreign":False,
                           "digest":DIGEST,"template":FAKE_TEMPLATE,"requests":[],
                           "active":0,"maximum":0,"guard":threading.Lock(),"mode":"normal"}.items():
            setattr(self.backend,name,value)
        self.thread = threading.Thread(target=self.backend.serve_forever,daemon=True)
        self.thread.start()
        self.addAsyncCleanup(self.close_backend)
        for module in ("bublik_service.inference.ollama","bublik_service.inference.context"):
            self.enterContext(patch(module+".TEMPLATE_SHA256",FAKE_SHA))
        self.adapter = OllamaAdapter(url=f"http://127.0.0.1:{self.backend.server_port}",epoch_probe=lambda _:"a"*64)
        self.settings = HTTPSettings(self.repo.database.path,sse_poll=.01,sse_lifetime=.2)
        self.app = create_app(self.settings,adapter_factory=lambda:self.adapter,repository=self.repo,security=self.auth)
        self.lifecycle = self.app.router.lifespan_context(self.app)
        await self.lifecycle.__aenter__()
        self.addAsyncCleanup(self.lifecycle.__aexit__,None,None,None)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url="https://localhost:8000")
        self.addAsyncCleanup(self.client.aclose)

    async def close_backend(self):
        await asyncio.to_thread(self.backend.shutdown)
        self.backend.server_close()
        self.thread.join(2)

    def headers(self,**extra):
        return {"Authorization":"Bearer "+self.token,**extra}

    async def create(self,key="chat",token=None):
        response = await self.client.post(P+"/chats",json={"title":"synthetic"},headers={"Authorization":"Bearer "+(token or self.token),"Idempotency-Key":key})
        self.assertIn(response.status_code,(200,201),response.text)
        return response.json()["chat_id"]

    async def send(self,chat,key="message",content="hello",revision=0):
        return await self.client.post(P+f"/chats/{chat}/messages",json={"content":content,"expected_revision":revision},headers=self.headers(**{"Idempotency-Key":key}))

    async def wait(self,receipt):
        return await self.app.state.coordinator.wait(self.owner,receipt["generation_id"],timeout=5)

    async def login(self):
        bootstrap = await self.client.get(P+"/auth/session")
        self.assertEqual(bootstrap.status_code,200,bootstrap.text)
        csrf = bootstrap.json()["csrf_token"]
        response = await self.client.post(P+"/auth/login",json={"username":"alice","password":PASSWORD},headers={"Origin":"https://localhost:8000","X-CSRF-Token":csrf})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()["csrf_token"]

    async def test_private_routes_unauthorized_and_live_minimal(self):
        live = await self.client.get(P+"/health/live")
        self.assertEqual(live.json(),{"status":"alive"})
        for path in ("/chats","/chats/unknown","/chats/unknown/messages","/chats/unknown/export","/generations/unknown","/generations/unknown/events","/health/ready","/openapi.json"):
            r = await self.client.get(P+path)
            self.assertEqual(r.status_code,401,r.text)
            self.assertEqual(r.headers["cache-control"],"no-store")
            self.assertEqual(r.json()["request_id"],r.headers["x-request-id"])

    async def test_login_rotates_cookie_csrf_and_logout_revokes(self):
        bootstrap = await self.client.get(P+"/auth/session")
        old = self.client.cookies.get(COOKIE)
        cookie = bootstrap.headers["set-cookie"]
        for attribute in ("Secure","HttpOnly","SameSite=strict","Path=/"):
            self.assertIn(attribute,cookie)
        self.assertNotIn("Domain=",cookie)
        csrf = await self.login()
        current = self.client.cookies.get(COOKIE)
        self.assertNotEqual(old,current)
        with self.assertRaises(AuthError):
            self.auth.session(old)
        created = await self.client.post(P+"/chats",json={},headers={"Origin":"https://localhost:8000","X-CSRF-Token":csrf,"Idempotency-Key":"browser"})
        self.assertEqual(created.status_code,201,created.text)
        r = await self.client.post(P+"/auth/logout",json={},headers={"Origin":"https://localhost:8000","X-CSRF-Token":csrf})
        self.assertEqual(r.status_code,200)
        with self.assertRaises(AuthError):
            self.auth.session(current)
        self.assertEqual((await self.client.get(P+"/chats")).status_code,401)

    async def test_csrf_and_origin_required_including_login(self):
        bootstrap = await self.client.get(P+"/auth/session")
        for headers in ({},{"Origin":"https://localhost:8000"},{"Origin":"https://evil.example","X-CSRF-Token":bootstrap.json()["csrf_token"]},
                        {"Origin":"https://127.0.0.1:8000","X-CSRF-Token":bootstrap.json()["csrf_token"]}):
            r = await self.client.post(P+"/auth/login",json={"username":"alice","password":PASSWORD},headers=headers)
            self.assertEqual(r.status_code,403,r.text)
        await self.login()
        self.assertEqual((await self.client.post(P+"/chats",json={},headers={"Idempotency-Key":"no-csrf"})).status_code,403)

    async def test_scopes_and_ambiguous_credentials(self):
        token = self.auth.issue_token(self.owner,"read",["chats:read"])["token"]
        for path,method in (("/chats","post"),("/health/ready","get"),("/chats/unknown/export","get"),("/openapi.json","get")):
            kwargs = {"json":{}} if method=="post" else {}
            r = await getattr(self.client,method)(P+path,headers={"Authorization":"Bearer "+token},**kwargs)
            self.assertEqual(r.status_code,403,r.text)
        await self.login()
        self.assertEqual((await self.client.get(P+"/chats",headers=self.headers())).status_code,403)
        self.assertEqual((await self.client.get(P+"/chats",headers={"Authorization":"Bearer bad"})).status_code,403)

    async def test_expiry_reset_and_revocation_preserve_history(self):
        chat = await self.create()
        csrf = await self.login()
        raw = self.client.cookies.get(COOKIE)
        now = self.auth.clock()
        self.auth.clock = lambda:now+43201
        self.assertEqual((await self.client.get(P+"/chats")).status_code,401)
        self.auth.clock = time.time
        self.auth.set_password(self.owner,"New-synthetic-password-123")
        with self.assertRaises(AuthError):
            self.auth.session(raw)
        self.client.cookies.clear()
        self.assertEqual((await self.client.get(P+"/chats",headers=self.headers())).status_code,401)
        self.assertEqual(self.repo.get_chat(self.owner,chat)["revision"],0)

    async def test_credentials_are_hashed_and_tokens_revocable(self):
        token = self.auth.issue_token(self.owner,"revoke",["chats:read"])
        self.auth.revoke_token(self.owner,token["id"])
        with self.assertRaises(AuthError):
            self.auth.token_principal(token["token"])
        raw = self.auth.new_session(self.owner)
        with self.repo.database.connect() as db:
            dump = "\n".join(db.iterdump())
        for secret in (self.token,token["token"],raw,PASSWORD):
            self.assertNotIn(secret,dump)
        self.assertNotIn("secret_hash",json.dumps(self.auth.list_tokens(self.owner)))
        restarted = SecurityStore(ChatRepository(self.repo.database.path))
        self.assertEqual(restarted.browser_principal(raw).owner,self.owner)
        self.assertEqual(restarted.token_principal(self.token).owner,self.owner)

    async def test_foreign_resources_return_same_404_as_unknown(self):
        chat = await self.create(token=self.other_token)
        for suffix in ("","/messages","/export"):
            r = await self.client.get(P+f"/chats/{chat}"+suffix,headers=self.headers())
            self.assertEqual(r.status_code,404,r.text)
        r = await self.send(chat)
        self.assertEqual(r.status_code,404)
        other_chat = await self.create()
        sent = (await self.send(other_chat)).json()
        await self.wait(sent)
        for suffix in ("","/events"):
            r = await self.client.get(P+f"/generations/{sent['generation_id']}"+suffix,headers={"Authorization":"Bearer "+self.other_token})
            self.assertEqual(r.status_code,404,r.text)
        r = await self.client.post(P+f"/messages/{sent['user_message_id']}/retry",json={"expected_revision":2},headers={"Authorization":"Bearer "+self.other_token,"Idempotency-Key":"foreign"})
        self.assertEqual(r.status_code,404)

    async def test_send_replay_conflict_snapshots_and_export(self):
        chat = await self.create()
        r = await self.send(chat)
        self.assertEqual(r.status_code,202,r.text)
        receipt = r.json()
        await self.wait(receipt)
        self.backend.offline = True
        replay = await self.send(chat)
        self.assertEqual(replay.status_code,200,replay.text)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(replay.json()["generation_id"],receipt["generation_id"])
        changed = await self.send(chat,content="changed")
        self.assertEqual(changed.status_code,409,changed.text)
        snapshot = await self.client.get(P+f"/generations/{receipt['generation_id']}",headers=self.headers())
        self.assertEqual(snapshot.status_code,200)
        self.assertNotIn("messages",snapshot.json()["context"])
        self.assertNotIn("worker_token",snapshot.text)
        export = await self.client.get(P+f"/chats/{chat}/export",headers=self.headers())
        self.assertEqual(export.json()["format"],"bublik-chat-export-v1")
        self.assertEqual(len(export.json()["messages"]),2)
        self.assertNotIn("password_hash",export.text)

    async def test_context_budget_rejection_preserves_history(self):
        chat = await self.create()
        before = self.repo.export_chat(self.owner,chat)
        response = await self.send(chat,content="x"*7000)
        self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(response.json()["error"]["code"],"context_budget_exceeded")
        self.assertEqual(before,self.repo.export_chat(self.owner,chat))
        self.assertEqual(self.backend.requests,[])

    async def test_quotas_survive_restart_replay_is_free(self):
        self.auth.generation_limit = 2
        chat = await self.create()
        first = (await self.send(chat)).json()
        await self.wait(first)
        second = await self.send(chat,key="second",revision=2)
        self.assertEqual(second.status_code,202,second.text)
        await self.wait(second.json())
        r = await self.send(chat,key="third",revision=4)
        self.assertEqual(r.status_code,429,r.text)
        self.assertGreater(int(r.headers["retry-after"]),0)
        self.assertEqual((await self.send(chat)).status_code,200)
        restarted = SecurityStore(ChatRepository(self.repo.database.path),generation_limit=2)
        with restarted.database.connect(write=True) as db:
            with self.assertRaises(RateLimited):
                restarted.generation_admission(db,self.owner)
        self.assertEqual(len(self.repo.history(self.owner,chat)),4)

    async def test_atomic_admission_quota_rollback_and_window_expiry(self):
        self.auth.clock = lambda:1000
        self.auth.generation_limit = 1
        chat = await self.create()
        self.assertEqual((await self.send(chat,content="x"*7000)).status_code,422)
        with self.repo.database.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM rate_events WHERE bucket=?",("generation:"+self.owner,)).fetchone()[0],0)
        # Token expiry follows actual timestamp: the earlier clock cannot expire it.
        r = await self.send(chat)
        self.assertEqual(r.status_code,202,r.text)
        await self.wait(r.json())
        self.auth.clock = lambda:1061
        r = await self.send(chat,key="later",revision=2)
        self.assertEqual(r.status_code,202,r.text)
        await self.wait(r.json())

    async def test_model_offline_history_available_and_ready_recovers(self):
        chat = await self.create()
        self.backend.offline = True
        self.assertEqual((await self.client.get(P+"/health/ready",headers=self.headers())).status_code,503)
        self.assertEqual((await self.send(chat)).status_code,503)
        self.assertEqual((await self.client.get(P+f"/chats/{chat}/messages",headers=self.headers())).status_code,200)
        self.backend.offline = False
        self.app.state.ready_cache = None
        self.assertEqual((await self.client.get(P+"/health/ready",headers=self.headers())).status_code,200)
        r = await self.send(chat)
        self.assertEqual(r.status_code,202,r.text)
        await self.wait(r.json())

    async def test_ten_sequential_and_three_concurrent_api_requests(self):
        chat = await self.create()
        for i in range(10):
            r = await self.send(chat,key=str(i),content=f"synthetic-{i}",revision=i*2)
            self.assertEqual(r.status_code,202,r.text)
            result = await self.wait(r.json())
            self.assertEqual(result["status"],"completed")
        # Another owner has an independent quota; concurrent different chats.
        chats = [await self.create(key="concurrent-"+str(i),token=self.other_token) for i in range(3)]
        responses = await asyncio.gather(*(self.client.post(P+f"/chats/{c}/messages",json={"content":f"queue-{i}","expected_revision":0},headers={"Authorization":"Bearer "+self.other_token,"Idempotency-Key":f"parallel-{i}"}) for i,c in enumerate(chats)))
        self.assertEqual([r.status_code for r in responses],[202]*3)
        for response in responses:
            result = await self.app.state.coordinator.wait(self.other,response.json()["generation_id"],timeout=5)
            self.assertEqual(result["status"],"completed")
        self.assertEqual(self.app.state.coordinator.max_active,1)
        self.assertEqual(self.backend.maximum,1)
        self.assertEqual(len(self.repo.history(self.owner,chat)),20)

    async def test_sse_durable_snapshot_reconnect_and_auth(self):
        chat = await self.create()
        receipt = (await self.send(chat)).json()
        result = await self.wait(receipt)
        url = P+f"/generations/{receipt['generation_id']}/events"
        for last in ("0","999999","garbage"):
            r = await self.client.get(url,headers=self.headers(**{"Last-Event-ID":last}))
            self.assertEqual(r.status_code,200,r.text)
            self.assertIn("event: snapshot",r.text)
            self.assertIn("id: "+str(result["stream_revision"]),r.text)
            data = json.loads(next(line[6:] for line in r.text.splitlines() if line.startswith("data: ")))
            self.assertEqual(data["assistant"]["content"],result["assistant"]["content"])
        self.assertEqual(self.app.state.streams,{})
        self.app.state.streams[self.owner]=2
        self.assertEqual((await self.client.get(url,headers=self.headers())).status_code,429)
        self.app.state.streams.clear()

    async def test_running_stream_revocation_disconnects_without_cancel_job(self):
        chat = await self.create()
        receipt = (await self.send(chat)).json()
        self.auth.revoke_token(self.owner,self.auth.list_tokens(self.owner)[0]["id"])
        # Request auth denies a revoked token; inference remains independent.
        r = await self.client.get(P+f"/generations/{receipt['generation_id']}/events",headers=self.headers())
        self.assertEqual(r.status_code,401)
        self.assertEqual((await self.wait(receipt))["status"],"completed")

    async def test_retry_latest_failed_question_no_duplicate_user(self):
        self.backend.mode="counter"
        chat = await self.create()
        r = (await self.send(chat)).json()
        self.assertEqual((await self.wait(r))["status"],"failed")
        self.backend.mode="normal"
        retry = await self.client.post(P+f"/messages/{r['user_message_id']}/retry",json={"expected_revision":2},headers=self.headers(**{"Idempotency-Key":"retry"}))
        self.assertEqual(retry.status_code,202,retry.text)
        self.assertEqual((await self.wait(retry.json()))["status"],"completed")
        self.assertEqual([m["role"] for m in self.repo.history(self.owner,chat)],["user","assistant","assistant"])

    async def test_strict_payload_no_input_echo_or_trusted_roles(self):
        chat = await self.create()
        for payload in ({"content":"SECRET","expected_revision":True},{"content":"SECRET","expected_revision":0,"owner_id":self.other},
                        {"content":"SECRET","expected_revision":0,"model":"cloud"},{"content":"SECRET","expected_revision":0,"role":"system"}):
            r = await self.client.post(P+f"/chats/{chat}/messages",json=payload,headers=self.headers(**{"Idempotency-Key":"invalid"}))
            self.assertEqual(r.status_code,422,r.text)
            self.assertNotIn("SECRET",r.text)
        for raw in (b'{"content":"SECRET","content":"duplicated","expected_revision":0}', b'{"expected_revision":NaN}',b"not-json-SECRET"):
            r = await self.client.post(P+f"/chats/{chat}/messages",content=raw,headers=self.headers(**{"Content-Type":"application/json"}))
            self.assertEqual(r.status_code,422,r.text)
            self.assertNotIn("SECRET",r.text)

    async def test_actual_chunked_body_limit_and_content_type(self):
        async def chunks():
            yield b'{"content":"'
            yield b"x"*18000
            yield b"x"*18000
            yield b'"}'
        r = await self.client.post(P+"/chats",content=chunks(),headers=self.headers(**{"Content-Type":"application/json"}))
        self.assertEqual(r.status_code,413,r.text)
        r = await self.client.post(P+"/chats",content="{}",headers=self.headers())
        self.assertEqual(r.status_code,415,r.text)
        r = await self.client.post(P+"/chats",content=b"{}",headers=self.headers(**{"Content-Type":"application/json","Content-Length":"40000"}))
        self.assertEqual(r.status_code,413,r.text)

    async def test_host_origin_query_and_duplicate_header_guards(self):
        for headers,status in ((self.headers(Host="evil.example"),400),(self.headers(Origin="https://localhost:8000.evil"),403)):
            self.assertEqual((await self.client.get(P+"/chats",headers=headers)).status_code,status)
        self.assertEqual((await self.client.get(P+"/chats?token=SECRET",headers=self.headers())).status_code,422)
        r = await self.client.get(P+"/chats",headers=[("Authorization","Bearer "+self.token),("Authorization","Bearer "+self.other_token)])
        self.assertEqual(r.status_code,422)

    async def test_plain_http_browser_denied_but_loopback_bearer_works(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url="http://127.0.0.1:8000") as client:
            self.assertEqual((await client.get(P+"/auth/session")).status_code,400)
            self.assertEqual((await client.get(P+"/chats",headers=self.headers())).status_code,200)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app,client=("192.168.1.5",5)),base_url="http://127.0.0.1:8000") as client:
            self.assertEqual((await client.get(P+"/chats",headers=self.headers())).status_code,400)

    async def test_login_throttled_and_errors_generic(self):
        bootstrap = (await self.client.get(P+"/auth/session")).json()
        for index in range(6):
            r = await self.client.post(P+"/auth/login",json={"username":"missing" if index%2 else "alice","password":"INCORRECT-SECRET"},headers={"Origin":"https://localhost:8000","X-CSRF-Token":bootstrap["csrf_token"]})
            self.assertEqual(r.status_code,401 if index<5 else 429,r.text)
            self.assertNotIn("INCORRECT-SECRET",r.text)
            if index<5:
                self.assertEqual(r.json()["error"]["code"],"invalid_credentials")

    async def test_pagination_openapi_and_headers(self):
        ids = [await self.create(key=str(i)) for i in range(3)]
        first = await self.client.get(P+"/chats?limit=2",headers=self.headers())
        next_page = await self.client.get(P+"/chats",params={"limit":2,"cursor":first.json()["next_cursor"]},headers=self.headers())
        self.assertEqual([r["id"] for r in first.json()["items"]+next_page.json()["items"]],ids)
        self.assertEqual((await self.client.get(P+"/chats?limit=101",headers=self.headers())).status_code,422)
        r = await self.client.get(P+"/openapi.json",headers=self.headers())
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn("HTTPBearer",r.json()["components"]["securitySchemes"])
        self.assertIn("/api/v1/chats",r.json()["paths"])
        self.assertIn("default-src 'none'",r.headers["content-security-policy"])
        self.assertEqual(r.headers["x-content-type-options"],"nosniff")
        self.assertEqual((await self.client.get("/docs")).status_code,404)

    async def test_schema1_upgrade_preserves_messages_receipts_and_backup(self):
        old_migrations = Path(self.temp.name)/"old-migrations"
        old_migrations.mkdir()
        source = Path(__file__).resolve().parents[1]/"bublik_service/storage/migrations/001_initial.sql"
        (old_migrations/source.name).write_bytes(source.read_bytes())
        path = Path(self.temp.name)/"old.sqlite3"
        old = Database(path,migrations=old_migrations)
        with old.connect(write=True) as db:
            db.execute("INSERT INTO users VALUES('owner','old','disabled','now')")
            db.execute("INSERT INTO chats VALUES('chat','owner','old-title',0,'now','now')")
            db.execute("INSERT INTO messages VALUES('msg','chat',1,'user','saved-secret','accepted','now','now')")
        upgraded = ChatRepository(path)
        self.assertEqual(upgraded.storage_status()["schema_version"],3)
        self.assertEqual(upgraded.history("owner","chat")[0]["content"],"saved-secret")
        with upgraded.database.connect() as db:
            self.assertEqual(db.execute("SELECT version FROM message_stream_versions WHERE message_id='msg'").fetchone()[0],0)
        backup = Path(self.temp.name)/"backup.sqlite3"
        upgraded.backup(backup)
        self.assertEqual(ChatRepository(backup).history("owner","chat"),upgraded.history("owner","chat"))

    async def test_stream_revoked_mid_subscription_and_cancel_cleanup(self):
        self.backend.mode = "timeout"
        chat = await self.create()
        receipt = (await self.send(chat)).json()
        url = P+f"/generations/{receipt['generation_id']}/events"
        task = asyncio.create_task(self.client.get(url,headers=self.headers()))
        async with asyncio.timeout(3):
            while not self.app.state.streams.get(self.owner):
                await asyncio.sleep(.001)
        self.auth.revoke_token(self.owner,self.auth.list_tokens(self.owner)[0]["id"])
        response = await task
        self.assertEqual(response.status_code,200)
        self.assertIn("authentication_required",response.text)
        self.assertEqual(self.app.state.streams,{})
        self.assertEqual((await self.wait(receipt))["status"],"completed")
        self.token = self.auth.issue_token(self.owner,"new",SCOPES)["token"]
        other_chat = await self.create(key="disconnect")
        receipt = (await self.send(other_chat,key="disconnect")).json()
        task = asyncio.create_task(self.client.get(P+f"/generations/{receipt['generation_id']}/events",headers=self.headers()))
        async with asyncio.timeout(3):
            while not self.app.state.streams.get(self.owner):
                await asyncio.sleep(.001)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.app.state.streams,{})
        self.assertEqual((await self.wait(receipt))["status"],"completed")

    async def test_inference_gate_503_history_and_replay_available(self):
        chat = await self.create()
        receipt = (await self.send(chat)).json()
        await self.wait(receipt)
        with self.repo.database.connect(write=True) as db:
            db.execute("UPDATE service_state SET inference_uncertain=1 WHERE id=1")
        blocked = await self.send(chat,key="blocked",revision=2)
        self.assertEqual(blocked.status_code,503,blocked.text)
        self.assertEqual(blocked.json()["error"]["code"],"inference_recovery_required")
        self.assertEqual((await self.send(chat)).status_code,200)
        self.assertEqual((await self.client.get(P+f"/chats/{chat}/messages",headers=self.headers())).status_code,200)
        self.assertEqual((await self.client.get(P+"/health/ready",headers=self.headers())).status_code,503)

    async def test_http_live_harness_rejects_fixture_quality_and_verifies_resume(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
        from check_http_live import run_checks,fingerprint
        report = {"run_id":"fixture"}
        self.client.headers.update(self.headers())
        with self.assertRaises(ValueError):
            await run_checks(self.client,report)
        self.assertFalse(report["checks"][-1]["passed"])
        self.assertEqual(report["checks"][-1]["name"],"literal_sequential-0")
        self.assertEqual(len(report["generations"]),1)
        chat = await self.create(key="resume")
        history = (await self.client.get(P+f"/chats/{chat}/messages")).json()
        resume = {"server_before":report["server_before"],"chats":[{"id":chat,"history_sha256":fingerprint(history)}]}
        resumed = {"run_id":"resume-fixture"}
        await run_checks(self.client,resumed,resume=resume)
        self.assertTrue(all(c["passed"] for c in resumed["checks"]))
