"""UI resource boundary and owner-scoped reverse pagination, real SQLite/ASGI."""
import tempfile
from pathlib import Path
import unittest

import httpx

from bublik_service.http_api import HTTPSettings, create_app
from bublik_service.domain import ContextPlan, InvalidInput, NotFound
from bublik_service.security import SecurityStore, SCOPES, password_hash
from bublik_service.storage import ChatRepository
from test_http_network import OfflineAdapter


class WebUITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo=ChatRepository(Path(self.temp.name)/"chats.sqlite3")
        self.owner=self.repo.create_user("owner",password_hash("Synthetic-ui-password-123"))
        self.other=self.repo.create_user("other",password_hash("Synthetic-ui-password-123"))
        self.auth=SecurityStore(self.repo)
        self.token=self.auth.issue_token(self.owner,"test",SCOPES)["token"]
        self.chat=self.repo.create_chat(self.owner,"seed",key="seed").chat_id
        with self.repo.worker_session() as worker:
            for n in range(4):
                receipt=self.repo.accept_message(self.owner,self.chat,str(n),expected_revision=self.repo.get_chat(self.owner,self.chat)["revision"],
                    key=str(n),context=ContextPlan(input_token_upper_bound=512))
                worker.claim_next()
                worker.finish(receipt.generation_id,status="completed",content="answer "+str(n))
        self.app=create_app(HTTPSettings(self.repo.database.path),repository=self.repo,security=self.auth,adapter_factory=OfflineAdapter)
        lifecycle=self.app.router.lifespan_context(self.app)
        await lifecycle.__aenter__()
        self.addAsyncCleanup(lifecycle.__aexit__,None,None,None)
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url="https://localhost:8000")
        self.addAsyncCleanup(self.client.aclose)

    async def test_ui_exact_allowlist_https_and_private_headers(self):
        for path,media in (("/","text/html"),("/assets/app.js","text/javascript"),("/assets/app.css","text/css")):
            result=await self.client.get(path)
            self.assertEqual(result.status_code,200)
            self.assertIn(media,result.headers["content-type"])
            self.assertEqual(result.headers["cache-control"],"no-store")
            self.assertIn("script-src 'self'",result.headers["content-security-policy"])
            self.assertNotIn("unsafe-inline",result.headers["content-security-policy"])
            self.assertEqual((await self.client.head(path)).content,b"")
        for path in ("/assets/requirements.lock","/assets/../requirements.lock","/assets/unknown.js","/web_ui/index.html"):
            self.assertEqual((await self.client.get(path)).status_code,404)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url="http://localhost:8000") as plain:
            self.assertEqual((await plain.get("/")).json()["error"]["code"],"secure_transport_required")
        live=await self.client.get("/api/v1/health/live")
        self.assertNotIn("script-src",live.headers["content-security-policy"])

    async def test_pwa_assets_no_store_same_origin_no_worker_or_api_cache(self):
        response=await self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status_code,200)
        self.assertIn("application/manifest+json",response.headers["content-type"])
        self.assertEqual(response.json()["display"],"standalone")
        for path in ("/", "/manifest.webmanifest", "/assets/icon-180.png", "/assets/icon-192.png", "/assets/icon-512.png"):
            r=await self.client.get(path)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers["cache-control"],"no-store")
            self.assertIn("manifest-src 'self'",r.headers["content-security-policy"])
            self.assertIn("worker-src 'none'",r.headers["content-security-policy"])
            self.assertEqual((await self.client.head(path)).content,b"")
        self.assertEqual((await self.client.get("/service-worker.js")).status_code,404)
        self.assertEqual((await self.client.get("/api/v1/chats")).status_code,401)

    async def test_reverse_pagination_no_loss_forward_contract_unchanged(self):
        headers={"Authorization":"Bearer "+self.token}
        path=f"/api/v1/chats/{self.chat}/messages"
        newest=await self.client.get(path+"?latest=true&limit=3",headers=headers)
        self.assertEqual([m["sequence"] for m in newest.json()["items"]],[6,7,8])
        older=await self.client.get(path+"?before_sequence=6&limit=3",headers=headers)
        self.assertEqual([m["sequence"] for m in older.json()["items"]],[3,4,5])
        oldest=await self.client.get(path+"?before_sequence=3&limit=3",headers=headers)
        self.assertEqual([m["sequence"] for m in oldest.json()["items"]],[1,2])
        self.assertIsNone(oldest.json()["next_before_sequence"])
        forward=await self.client.get(path+"?after_sequence=3&limit=3",headers=headers)
        self.assertEqual([m["sequence"] for m in forward.json()["items"]],[4,5,6])
        self.assertEqual(forward.json()["next_after_sequence"],6)
        for query in ("before_sequence=0","latest=true&after_sequence=1","before_sequence=-1","latest=true&limit=101"):
            self.assertEqual((await self.client.get(path+"?"+query,headers=headers)).status_code,422)
        foreign=self.auth.issue_token(self.other,"other",SCOPES)["token"]
        self.assertEqual((await self.client.get(path+"?latest=true",headers={"Authorization":"Bearer "+foreign})).status_code,404)
        self.assertEqual((await self.client.get(path+"?latest=true")).status_code,401)

    async def test_tail_stable_across_new_messages_and_foreign_cursor(self):
        cursor=self.repo.history_tail(self.owner,self.chat,limit=3)[0]["sequence"]
        self.repo.accept_message(self.owner,self.chat,"new",expected_revision=8,key="new",context=ContextPlan(input_token_upper_bound=512))
        self.assertEqual([r["sequence"] for r in self.repo.history_tail(self.owner,self.chat,before_sequence=cursor,limit=3)],[3,4,5])
        with self.assertRaises(NotFound): self.repo.history_tail(self.other,self.chat)
        with self.assertRaises(InvalidInput): self.repo.history_tail(self.owner,self.chat,before_sequence=True)
