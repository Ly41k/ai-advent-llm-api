"""Bounded stage-8 HTTP observations; no retries of ambiguous POST outcomes."""
import asyncio
from datetime import datetime
import math
import os
import re
import statistics
import time

from check_http_live import CheckFailed, fingerprint, admission_observation
from bublik_service.http_api import runtime_manifest

P = "/api/v1"


def new_report(parser, path):
    try:
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        return os.fdopen(fd,"w",encoding="utf-8")
    except OSError:
        parser.error("NEW writable report path required; earlier reports are preserved")


def literal(answer, expected):
    return answer.strip().casefold() == expected.casefold()


def russian_only(answer):
    # A language regression screen, not a semantic judge.
    return bool(re.search(r"[А-Яа-яЁё]",answer)) and not re.search(r"[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]",answer)


def distribution(values):
    if not values:
        return {"n":0,"median":None,"p95_nearest_rank":None,"max":None}
    values = sorted(values)
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in values):
        raise ValueError("invalid_metric")
    return {"n":len(values),"median":statistics.median(values),
            "p95_nearest_rank":values[math.ceil(.95*len(values))-1],"max":values[-1]}


def observed_overlap(generations):
    events = []
    for g in generations:
        if not g.get("started_at") or not g.get("finished_at"):
            raise ValueError("missing_generation_timestamps")
        begin, end = (datetime.fromisoformat(g[k]) for k in ("started_at","finished_at"))
        if begin.tzinfo is None or end.tzinfo is None or end < begin:
            raise ValueError("invalid_generation_timestamps")
        events.extend([(begin,1),(end,-1)])
    active = peak = 0
    for _, change in sorted(events, key=lambda e:(e[0],e[1])):
        active += change
        peak = max(peak,active)
    return peak


def latency_summary(generations):
    statuses = {s:sum(g["status"]==s for g in generations)
                for s in ("completed","truncated","failed","interrupted")}
    groups = {}
    for group in {g.get("group","unknown") for g in generations}:
        rows = [g for g in generations if g.get("group","unknown")==group]
        groups[group] = {field:distribution([g["metrics"][field] for g in rows
                         if type(g["metrics"].get(field)) in (int,float)])
                        for field in ("queue_seconds","first_token_seconds","total_seconds",
                                      "inference_seconds","load_seconds","tokens_per_second")}
        groups[group]["terminal_status_counts"] = {s:sum(g["status"]==s for g in rows) for s in statuses}
    return {"n":len(generations),"terminal_status_counts":statuses,"groups":groups,
            "method":"Nearest-rank p95 with n; missing metrics excluded per field with n shown. Errors counted separately.",
            "cold_warm":"First request classified by observed pre-run loaded models only. No forced eviction; warm group is subsequent requests."}


class API:
    def __init__(self, client, report, *, poll_interval=2, deadline=1800, quota_pause=asyncio.sleep):
        self.client, self.report = client, report
        self.poll_interval, self.deadline, self.pause = poll_interval, deadline, quota_pause
        report.setdefault("checks",[])
        report.setdefault("generations",[])
        report.setdefault("requests",[])
        report.setdefault("quota_pauses",[])

    def check(self, name, value):
        self.report["checks"].append({"name":name,"passed":bool(value)})
        if not value:
            raise CheckFailed(name)

    async def request(self, method, path, *, quota_retry=True, **kwargs):
        # Retry only explicit 429. For POST, server rejected admission; the SAME
        # idempotency key/body is reused. HTTP/network ambiguity is never retried.
        for attempt in range(4):
            response = await self.client.request(method,P+path,**kwargs)
            if len(response.content)>8*1024*1024:
                raise CheckFailed("response_size_limit")
            if response.status_code != 429 or not quota_retry or attempt==3:
                return response
            self.check("retry_after_present",response.headers.get("retry-after","").isdecimal())
            wait = int(response.headers["retry-after"])+1
            self.check("bounded_quota_pause",1<=wait<=61)
            self.report["quota_pauses"].append({"method":method,"seconds":wait})
            print(f'{{"quota_pause_seconds":{wait}}}',flush=True)
            # Keep waits cancellable and short; never use blocking sleep.
            for _ in range(wait):
                await self.pause(1)
        raise CheckFailed("quota_retry_limit")

    async def get(self, path):
        response = await self.request("GET",path)
        response.raise_for_status()
        return response.json()

    async def ready(self, name="ready_current_runtime"):
        value = await self.get("/health/ready")
        self.check(name,value["status"]=="ready" and value["runtime_source_unchanged"]
                   and value["runtime_source_sha256"]==runtime_manifest())
        return value

    async def create(self, case):
        key = self.report["run_id"]+"-chat-"+case
        r = await self.request("POST","/chats",json={"title":"Stage 8 synthetic: "+case},headers={"Idempotency-Key":key})
        self.check("created_"+case,r.status_code==201)
        return r.json()["chat_id"]

    async def send(self, chat, content, case, *, revision=None):
        if revision is None:
            revision = (await self.get("/chats/"+chat))["revision"]
        key = self.report["run_id"]+"-message-"+case
        record = {"case":case,"chat_id":chat,"idempotency_key":key,"revision":revision}
        self.report["requests"].append(record)
        r = await self.request("POST",f"/chats/{chat}/messages",json={"content":content,"expected_revision":revision},
                               headers={"Idempotency-Key":key})
        record.update(admission_observation(r,case))
        self.check("accepted_"+case,r.status_code==202)
        return r.json()

    async def history(self, chat):
        items, cursor = [], 0
        for _ in range(100):
            page = await self.get(f"/chats/{chat}/messages?limit=100&after_sequence={cursor}")
            items += page["items"]
            next_cursor = page["next_after_sequence"]
            if next_cursor is None:
                return items
            self.check("increasing_history_cursor",type(next_cursor) is int and next_cursor>cursor)
            cursor = next_cursor
        raise CheckFailed("history_page_limit")

    async def wait_many(self, receipts, cases, group):
        remaining = dict(zip((r["generation_id"] for r in receipts),cases))
        results = {}
        started = time.monotonic()
        while remaining and time.monotonic()-started < self.deadline:
            # One ready request per batch iteration; do not multiply polling by 3.
            state = await self.get("/health/ready")
            self.check("running_at_most_one",state["running"]<=1)
            self.report["observed_queue_max"] = max(self.report.get("observed_queue_max",0),state["queued"])
            for ident, case in list(remaining.items()):
                value = await self.get("/generations/"+ident)
                if value["status"] not in {"queued","running"}:
                    results[case] = value
                    self.report["generations"].append({"case":case,"group":group,"id":ident,
                        "status":value["status"],"error_code":value["error_code"],"answer":value["assistant"]["content"],
                        "metrics":value["metrics"],"context":value["context"],
                        "started_at":value["started_at"],"finished_at":value["finished_at"]})
                    del remaining[ident]
                    print(f'{{"completed_case":"{case}","status":"{value["status"]}"}}',flush=True)
            if remaining:
                await asyncio.sleep(self.poll_interval)
        self.check("all_requests_terminal",not remaining)
        return [results[c] for c in cases]


def history_record(chat, items):
    return {"id":chat,"history_sha256":fingerprint(items),"message_count":len(items)}
