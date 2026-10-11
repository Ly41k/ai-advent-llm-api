"""Explicit HTTPS proxy trust boundary, config injection and CSRF isolation."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

import httpx

from bublik_service.admin_cli import serve
from bublik_service.domain import InvalidInput, ModelUnavailable
from bublik_service.http_api import HTTPSettings, create_app
from bublik_service.security import COOKIE, password_hash
from bublik_service.storage import ChatRepository

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from configure_network import generate
from network_common import tailnet_host, private_origin
from check_device_handoff import history_checks,PHONE_QUESTION
from check_http_live import fingerprint

LAN = "https://192.168.1.50:8443"
TAIL = "https://bublik.tail123.ts.net"
PASSWORD = "Synthetic-proxy-password-123"


class OfflineAdapter:
    async def doctor(self): raise ModelUnavailable()
    async def aclose(self): pass


class ProxyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = ChatRepository(Path(self.temp.name)/"chat.sqlite3")
        self.repo.create_user("alice",password_hash(PASSWORD))
        self.settings = HTTPSettings(self.repo.database.path,origins=(LAN,TAIL),trusted_loopback_proxy=True)
        self.app = create_app(self.settings,adapter_factory=OfflineAdapter,repository=self.repo)
        self.lifecycle = self.app.router.lifespan_context(self.app)
        await self.lifecycle.__aenter__()
        self.addAsyncCleanup(self.lifecycle.__aexit__,None,None,None)

    def client(self,peer="127.0.0.1",app=None):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app or self.app,client=(peer,12345)),
                                base_url="http://192.168.1.50:8443")

    async def test_proxy_requires_raw_loopback_single_https_marker_and_matching_host(self):
        async with self.client() as client:
            for headers in ({}, {"X-Forwarded-Proto":"http"}, {"X-Forwarded-Proto":"https,http"},
                    {"X-Forwarded-Proto":"https", "Forwarded":"proto=https"},
                    [("X-Forwarded-Proto","https"),("X-Forwarded-Proto","https")]):
                response = await client.get("/",headers=headers)
                self.assertEqual(response.status_code,400 if headers != [("X-Forwarded-Proto","https"),("X-Forwarded-Proto","https")] else 422)
            for host in ("evil.example", "bublik.tail123.ts.net"):
                response = await client.get("/",headers={"X-Forwarded-Proto":"https","X-Forwarded-Host":host})
                self.assertEqual(response.status_code,400)
            response = await client.get("/",headers={"X-Forwarded-Proto":"https", "Host":"evil.example"})
            self.assertEqual(response.status_code,400)
        for peer in ("192.168.1.2","100.100.1.2","127.0.0.2","::ffff:127.0.0.1"):
            async with self.client(peer) as client:
                self.assertEqual((await client.get("/",headers={"X-Forwarded-Proto":"https"})).status_code,400)

    async def test_default_mode_does_not_trust_headers_or_remote_plaintext(self):
        app=create_app(replace(self.settings,trusted_loopback_proxy=False),adapter_factory=OfflineAdapter)
        async with self.client(app=app) as client:
            response=await client.get("/",headers={"X-Forwarded-Proto":"https"})
            self.assertEqual(response.status_code,400)
            self.assertNotIn("strict-transport-security",response.headers)
        async with self.client("192.168.1.2",app=app) as client:
            self.assertEqual((await client.get("/api/v1/chats",headers={"X-Forwarded-Proto":"https"})).status_code,400)

    async def test_https_cookie_same_origin_csrf_auth_and_spoofed_identity(self):
        # Cookies are sent by real browsers over external HTTPS; the transport
        # presents a raw HTTP socket to the app, as a TLS-terminating proxy does.
        async with self.client() as client:
            header={"X-Forwarded-Proto":"https"}
            self.assertEqual((await client.get("/",headers=header)).status_code,200)
            r=await client.get("/api/v1/auth/session",headers=header)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers["strict-transport-security"],"max-age=86400")
            self.assertIn("Secure",r.headers["set-cookie"])
            self.assertIn("HttpOnly",r.headers["set-cookie"])
            cookie=r.cookies.get(COOKIE); csrf=r.json()["csrf_token"]
            body={"username":"alice","password":PASSWORD}
            header.update({"Cookie":COOKIE+"="+cookie,"X-CSRF-Token":csrf})
            denied=await client.post("/api/v1/auth/login",json=body,headers={**header,"Origin":TAIL})
            self.assertEqual(denied.status_code,403)
            logged=await client.post("/api/v1/auth/login",json=body,headers={**header,"Origin":LAN})
            self.assertEqual(logged.status_code,200)
            cookie=logged.cookies.get(COOKIE); csrf=logged.json()["csrf_token"]
            header.update({"Cookie":COOKIE+"="+cookie,"X-CSRF-Token":csrf,"Idempotency-Key":"proxy-chat"})
            self.assertEqual((await client.post("/api/v1/chats",json={},headers={**header,"Origin":TAIL})).status_code,403)
            self.assertEqual((await client.post("/api/v1/chats",json={},headers={**header,"Origin":LAN})).status_code,201)
            fake={"X-Forwarded-Proto":"https","Tailscale-User-Login":"alice","X-Forwarded-For":"127.0.0.1"}
            client.cookies.clear()
            self.assertEqual((await client.get("/api/v1/chats",headers=fake)).status_code,401)
            # XFF cannot evade the aggregate bootstrap quota behind proxies.
            from bublik_service.security import digest
            # Observe identical peer keys by both requests consuming one bucket.
            count=[]
            original=self.app.state.auth.rate
            def record(key,limit): count.append(key); return original(key,limit)
            self.app.state.auth.rate=record
            await client.get("/api/v1/auth/session",headers={**fake,"X-Forwarded-For":"192.168.1.2"})
            await client.get("/api/v1/auth/session",headers={**fake,"X-Forwarded-For":"192.168.1.3"})
            self.assertEqual([k for k in count if k.startswith("bootstrap:")],["bootstrap:"+digest("127.0.0.1")]*2)


class ConfigTests(unittest.TestCase):
    def test_handoff_requires_unchanged_seed_exact_question_answer_and_count(self):
        seed=[{"id":"u1","role":"user","content":"seed","status":"completed"},
              {"id":"a1","role":"assistant","content":"принято","status":"completed"}]
        challenge={"seed_history_sha256":fingerprint(seed),"control_word":"ромашка"}
        phone=[{"role":"user","content":PHONE_QUESTION},
               {"role":"assistant","content":"ромашка","status":"completed"}]
        self.assertTrue(all(c["passed"] for c in history_checks(challenge,seed+phone)))
        for altered in (seed,seed+phone+phone,seed+phone[:1],
                seed+[phone[0],{**phone[1],"content":"мандарин"}],
                seed+[phone[0],{**phone[1],"status":"running"}],
                [{**seed[0],"id":"other"},seed[1]]+phone):
            self.assertFalse(all(c["passed"] for c in history_checks(challenge,altered)))

    def test_private_config_validates_before_exclusive_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"new"
            data=generate("192.168.1.50","bublik.tail123.ts.net",8000,8443,dest)
            self.assertEqual(data["origins"],[LAN,TAIL])
            self.assertEqual(dest.stat().st_mode & 0o777,0o700)
            self.assertEqual((dest/"Caddyfile").stat().st_mode & 0o777,0o600)
            original=(dest/"Caddyfile").read_bytes()
            with self.assertRaises(FileExistsError): generate("192.168.1.51",None,8000,8443,dest)
            self.assertEqual((dest/"Caddyfile").read_bytes(),original)
            link=Path(tmp)/"link"; link.symlink_to(dest,target_is_directory=True)
            with self.assertRaises(FileExistsError): generate("192.168.1.51",None,8000,8443,link)
            for address in ("0.0.0.0","127.0.0.1","100.64.0.1","8.8.8.8","169.254.1.2","192.168.1.1\n}","::1"):
                with self.assertRaises(ValueError): generate(address,None,8000,8443,Path(tmp)/"bad")
                self.assertFalse((Path(tmp)/"bad").exists())
            with self.assertRaises(ValueError): generate("192.168.1.1",None,8000,8000,Path(tmp)/"bad")

    def test_external_checker_rejects_public_urls_and_config_injection(self):
        self.assertEqual(private_origin(LAN,"lan").hostname,"192.168.1.50")
        self.assertEqual(private_origin(TAIL,"tailnet").hostname,"bublik.tail123.ts.net")
        for host in ("bublik.ts.net","UPPER.tail123.ts.net","node.tail.ts.net/path","node.tail.ts.net\n{}"):
            with self.assertRaises(ValueError): tailnet_host(host)
        for url in ("http://192.168.1.2","https://8.8.8.8","https://user@192.168.1.2","https://192.168.1.2/path","https://192.168.1.2:443","https://192.168.1.2:bad"):
            with self.assertRaises(ValueError): private_origin(url,"lan")
        with self.assertRaises(ValueError): private_origin(TAIL+":8443","tailnet")

    def test_cli_proxy_requires_explicit_origins_without_backend_tls(self):
        for origins,cert in ((None,None),([LAN],Path("cert.pem"))):
            args=SimpleNamespace(tls_cert=cert,tls_key=cert,trusted_loopback_proxy=True,origin=origins)
            with self.assertRaises(InvalidInput): serve(None,args)
