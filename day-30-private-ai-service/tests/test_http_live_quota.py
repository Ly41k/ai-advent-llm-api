"""Harness regression: synthetic HTTP and real SQLite quotas on a virtual clock.

No real server/model/network proof. The failure depends on distributed admission
TIMES: the old Retry-After wait frees one slot, not a three-request batch.
"""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

from bublik_service.http_api import runtime_manifest
from bublik_service.security import RateLimited,SecurityStore
from bublik_service.storage import ChatRepository

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_http_live import CheckFailed,run_checks


class Protocol:
    def __init__(self,path):
        self.now=1000
        self.repo=ChatRepository(path)
        self.owner=self.repo.create_user("synthetic-quota","disabled:synthetic")
        self.auth=SecurityStore(self.repo,clock=lambda:self.now)
        self.chats,self.generations,self.receipts={},{},{}
        self.batch_statuses=[]
        self.sleep_total=0
        self.external_load=False

    def debit(self):
        with self.repo.database.connect(write=True) as db:
            self.auth.generation_admission(db,self.owner)

    async def sleep(self,seconds):
        self.now+=seconds
        self.sleep_total+=seconds
        if self.external_load and self.sleep_total>=61:
            for _ in range(9):
                self.debit()
            self.external_load=False

    def handle(self,request):
        path=request.url.path.removeprefix("/api/v1")
        if path=="/health/ready":
            return httpx.Response(200,json={"status":"ready","runtime_source_sha256":runtime_manifest(),
                "runtime_source_unchanged":True,"model":{"identity":{"digest":"synthetic"}}})
        if path=="/chats" and request.method=="GET":
            return httpx.Response(401,json={"error":{"code":"authentication_required"}})
        if path=="/chats" and request.method=="POST":
            ident=f"{len(self.chats)+1:032x}"
            self.chats[ident]={"revision":0,"history":[]}
            return httpx.Response(201,json={"chat_id":ident})
        if path.startswith("/generations/"):
            return httpx.Response(200,json=self.generations[path.split("/")[2]])
        if path.startswith("/chats/"):
            chat=path.split("/")[2]
            current=self.chats[chat]
            if not path.endswith("/messages"):
                return httpx.Response(200,json={"revision":current["revision"]})
            if request.method=="GET":
                return httpx.Response(200,json={"items":current["history"],"next_after_sequence":None})
            key=request.headers["Idempotency-Key"]
            body=json.loads(request.content)
            if (chat,key) in self.receipts:
                return httpx.Response(200,json=self.receipts[(chat,key)])
            if len(body["content"])>6656:
                return httpx.Response(422,json={"error":{"code":"context_budget_exceeded"}})
            try:
                self.debit()
            except RateLimited as error:
                if key.startswith("parallel-"):
                    self.batch_statuses.append(429)
                return httpx.Response(429,json={"error":{"code":"rate_limit_exceeded","message":"PRIVATE-SENTINEL"}},
                                      headers={"Retry-After":str(error.retry_after)})
            ident=f"{len(self.generations)+1000:032x}"
            self.receipts[(chat,key)]={"generation_id":ident}
            if key.startswith("sequential-"):
                answer=["запомнил","мандарин","remembered","lantern","принято","сапфир","4","lantern","сапфир","OK"][int(key.split("-")[1])]
            else:
                answer="queue-"+key.split("-")[1]
                self.batch_statuses.append(202)
            current["revision"]+=2
            current["history"] += [{"role":"user","content":body["content"]},{"role":"assistant","content":answer}]
            self.generations[ident]={"id":ident,"status":"completed","error_code":None,"assistant":{"content":answer},
                "metrics":{"input_tokens":12,"queue_seconds":.5},"context":{"input_token_upper_bound":512}}
            # Ten admissions are spread across 20 seconds, as on the real Mac.
            self.now+=2
            return httpx.Response(202,json={"generation_id":ident})
        return httpx.Response(404)


class QuotaHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.protocol=Protocol(Path(self.temp.name)/"quota.sqlite3")

    async def test_old_wait_frees_only_one_slot(self):
        for _ in range(10):
            self.protocol.debit()
            self.protocol.now+=2
        with self.assertRaises(RateLimited) as caught:
            self.protocol.debit()
        self.assertEqual(caught.exception.retry_after,40)
        self.protocol.now+=caught.exception.retry_after+1
        self.protocol.debit()
        with self.assertRaises(RateLimited):
            self.protocol.debit()

    async def test_full_live_flow_waits_for_three_slots(self):
        report={"run_id":"synthetic-quota"}
        with patch("check_http_live.asyncio.sleep",self.protocol.sleep),patch("builtins.print"):
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",transport=httpx.MockTransport(self.protocol.handle)) as client:
                await run_checks(client,report)
        self.assertTrue(all(c["passed"] for c in report["checks"]))
        self.assertEqual(report["quota_wait"]["retry_after_seconds"],40)
        self.assertEqual(report["quota_wait"]["wait_seconds"],61)
        self.assertEqual(self.protocol.batch_statuses,[202,202,202])
        self.assertEqual(len(report["generations"]),13)

    async def test_batch_rejection_records_status_without_private_message(self):
        report={"run_id":"synthetic-contention"}
        self.protocol.external_load=True
        with patch("check_http_live.asyncio.sleep",self.protocol.sleep),patch("builtins.print"):
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",transport=httpx.MockTransport(self.protocol.handle)) as client:
                with self.assertRaises(CheckFailed) as caught:
                    await run_checks(client,report)
        self.assertEqual(caught.exception.name,"three_concurrent_admissions")
        self.assertEqual([r["http_status"] for r in report["concurrent_admissions"]],[202,429,429])
        self.assertNotIn("PRIVATE-SENTINEL",json.dumps(report))
        self.assertEqual(report["concurrent_admissions"][1]["error_code"],"rate_limit_exceeded")
