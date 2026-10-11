"""Read-only macOS measurements. Never read argv, unload a model, or claim physical peak RAM."""
import asyncio
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import time

from bublik_service.inference.engine import engine_epoch
from check_launchd_live import launch_pid
from configure_launchd import API_LABEL


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=3,
                            env={**os.environ, "LC_ALL": "C", "TZ": "UTC"})
    if result.returncode or len(result.stdout) > 1024 * 1024:
        raise ValueError("resource_command_failed")
    return result.stdout


def cpu_seconds(value):
    match = re.fullmatch(r"(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", value)
    if not match:
        raise ValueError("invalid_cpu_time")
    days, hours, minutes, seconds = match.groups()
    return int(days or 0)*86400 + int(hours or 0)*3600 + int(minutes)*60 + float(seconds)


def processes(output, api_pid, ollama_pid):
    rows = {}
    for line in output.splitlines():
        parts = line.split(maxsplit=4)
        if len(parts) != 5 or not all(p.isdecimal() for p in parts[:3]):
            raise ValueError("invalid_resource_process_table")
        pid, parent, rss = map(int, parts[:3])
        if pid in rows:
            raise ValueError("duplicate_process")
        rows[pid] = {"pid": pid, "parent": parent, "rss_bytes": rss*1024,
                     "cpu_seconds": cpu_seconds(parts[3]), "name": Path(parts[4]).name}
    if api_pid not in rows or ollama_pid not in rows:
        raise ValueError("observed_process_disappeared")
    selected = []
    for pid, row in rows.items():
        ancestor, seen = pid, set()
        while ancestor in rows and ancestor not in seen and ancestor != ollama_pid:
            seen.add(ancestor)
            ancestor = rows[ancestor]["parent"]
        belongs = ancestor == ollama_pid
        if row["name"] in {"ollama", "ollama_llama_server", "llama-server"} and not belongs:
            raise ValueError("other_or_orphan_ollama")
        if pid == api_pid or belongs:
            selected.append({k:v for k,v in row.items() if k != "name"} |
                            {"role": "api" if pid == api_pid else "ollama"})
    return selected


def memory(vm, swap, total):
    match = re.search(r"page size of (\d+) bytes", vm)
    if not match or not total.strip().isdecimal():
        raise ValueError("invalid_memory_observation")
    page_size = int(match[1])
    if page_size <= 0:
        raise ValueError("invalid_page_size")
    pages = {k:int(v) for k,v in re.findall(r'^([^:\n]+):\s*(\d+)\.\s*$', vm, re.M)}
    fields = {"Pages free":"free_bytes", "Pages inactive":"inactive_bytes",
              "Pages speculative":"speculative_bytes", "Pages wired down":"wired_bytes",
              "Pages occupied by compressor":"compressor_bytes", "File-backed pages":"file_backed_bytes"}
    if "Pages free" not in pages:
        raise ValueError("missing_free_pages")
    converted = {fields[k]:v*page_size for k,v in pages.items() if k in fields}
    swap_values = {}
    for field in ("total", "used", "free"):
        item = re.search(r"\b"+field+r"\s*=\s*(\d+(?:\.\d+)?)([KMG])", swap)
        if not item:
            raise ValueError("invalid_swap_observation")
        swap_values[field+"_bytes"] = round(float(item[1])*1024**("KMG".index(item[2])+1))
    return {"physical_total_bytes":int(total), "page_size_bytes":page_size,
            **converted, "swap":swap_values}


def loaded_models(value, identity):
    models = value.get("models") if isinstance(value, dict) else None
    if not isinstance(models, list) or len(models) > 1:
        raise ValueError("unexpected_loaded_models")
    safe = []
    for item in models:
        if (not isinstance(item, dict) or item.get("name") != identity["model"]
                or str(item.get("digest", "")).removeprefix("sha256:") != identity["digest"]):
            raise ValueError("unexpected_loaded_models")
        row = {k:item.get(k) for k in ("size", "size_vram", "context_length")}
        if any(type(v) is not int or v < 0 for v in row.values()):
            raise ValueError("invalid_loaded_allocation")
        safe.append(row)
    return safe


def summary(samples):
    def peak(values): return max(values) if values else None
    api, engine, api_cpu, engine_cpu = [], [], [], []
    previous = None
    for item in samples:
        for role, rss_values, cpu_values in (("api", api, api_cpu), ("ollama", engine, engine_cpu)):
            rows = [p for p in item["processes"] if p["role"] == role]
            rss_values.append(sum(p["rss_bytes"] for p in rows))
            if previous and item["elapsed_seconds"] > previous["elapsed_seconds"]:
                old = {p["pid"]:p for p in previous["processes"] if p["role"] == role}
                deltas = [p["cpu_seconds"]-old[p["pid"]]["cpu_seconds"] for p in rows
                          if p["pid"] in old and p["cpu_seconds"] >= old[p["pid"]]["cpu_seconds"]]
                if deltas:
                    cpu_values.append(100*sum(deltas)/(item["elapsed_seconds"]-previous["elapsed_seconds"]))
        previous = item
    return {"sample_count":len(samples), "api_rss_sampled_max_bytes":peak(api),
            "ollama_family_rss_sum_sampled_max_bytes":peak(engine),
            "api_interval_cpu_sampled_max_percent":peak(api_cpu),
            "ollama_family_interval_cpu_sampled_max_percent":peak(engine_cpu),
            "system_free_sampled_min_bytes": min((s["memory"]["free_bytes"] for s in samples),default=None),
            "swap_used_sampled_max_bytes":peak([s["memory"]["swap"]["used_bytes"] for s in samples]),
            "swap_used_change_bytes": (samples[-1]["memory"]["swap"]["used_bytes"]-
                                       samples[0]["memory"]["swap"]["used_bytes"]) if samples else None,
            "reported_size_vram_sampled_max_bytes":peak([m["size_vram"] for s in samples for m in s["loaded"]]),
            "limitations":["RSS sums can double-count shared pages; not physical unified-memory usage",
              "CPU is delta of ps cumulative user+system time for surviving PIDs; GPU not measured",
              "Snapshots are sequential, sampled maxima can miss transient peaks",
              "Free/file-backed/inactive counters are separate; no exact available-RAM claim",
              "Ollama size/size_vram allocations are separate from process RSS; never add them"]}


class MacObserver:
    def __init__(self, identity, interval=2):
        if platform.system() != "Darwin" or not math.isfinite(interval) or interval < 1:
            raise ValueError("mac_resource_observer_required")
        self.identity, self.interval = identity, interval
        self.samples, self.errors, self.phase = [], [], "idle_before"
        self.stop, self.task = asyncio.Event(), None

    def setup(self):
        self.api_pid = launch_pid(command(["/bin/launchctl", "print", f"gui/{os.getuid()}/{API_LABEL}"]))
        self.epoch = engine_epoch(11434)
        listeners = command(["/usr/sbin/lsof", "-nP", "+c", "0", "-a", "-iTCP:8000", "-sTCP:LISTEN", "-Fpn"])
        if set(re.findall(r"^p(\d+)$",listeners,re.M)) != {str(self.api_pid)} or set(re.findall(r"^n(.+)$",listeners,re.M)) != {"127.0.0.1:8000"}:
            raise ValueError("api_listener_unverified")
        ollama = command(["/usr/sbin/lsof", "-nP", "+c", "0", "-a", "-iTCP:11434", "-sTCP:LISTEN", "-Fp"])
        pids = set(re.findall(r"^p(\d+)$",ollama,re.M))
        if len(pids) != 1:
            raise ValueError("ollama_pid_unverified")
        self.ollama_pid = int(next(iter(pids)))
        self.started = time.perf_counter()

    def os_sample(self):
        # Full process table only in memory. Never persist other executable names/argv.
        rows = processes(command(["/bin/ps", "-axo", "pid=,ppid=,rss=,time=,comm="]), self.api_pid, self.ollama_pid)
        mem = memory(command(["/usr/bin/vm_stat"]), command(["/usr/sbin/sysctl", "-n", "vm.swapusage"]),
                     command(["/usr/sbin/sysctl", "-n", "hw.memsize"]))
        return {"elapsed_seconds":time.perf_counter()-self.started,"phase":self.phase,"processes":rows,"memory":mem}

    async def __aenter__(self):
        import httpx
        try:
            await asyncio.to_thread(self.setup)
        except Exception as error:
            self.errors.append({"phase":"setup","code":"resource_setup_failed","reason":safe_reason(error)})
            raise
        self.client = httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=3)
        try:
            await self.sample()
        except BaseException as error:
            if isinstance(error,Exception):
                self.errors.append({"phase":self.phase,"code":"first_resource_observation_failed","reason":safe_reason(error)})
            await self.client.aclose()
            raise
        self.task = asyncio.create_task(self.loop())
        return self

    async def sample(self):
        if len(self.samples) >= 1800:
            raise ValueError("resource_sample_limit")
        item = await asyncio.to_thread(self.os_sample)
        response = await self.client.get("http://127.0.0.1:11434/api/ps")
        response.raise_for_status()
        if len(response.content) > 65536:
            raise ValueError("resource_metadata_limit")
        item["loaded"] = loaded_models(response.json(),self.identity)
        self.samples.append(item)

    async def loop(self):
        while not self.stop.is_set():
            try:
                await asyncio.wait_for(self.stop.wait(),self.interval)
                return
            except TimeoutError:
                pass
            try:
                await self.sample()
            except Exception as error:
                self.errors.append({"phase":self.phase,"code":"resource_observation_failed",
                                    "reason":safe_reason(error)})
                return

    async def __aexit__(self, *_):
        self.stop.set()
        try:
            if self.task:
                await self.task
            self.phase = "idle_after"
            await self.sample()
            if self.epoch != await asyncio.to_thread(engine_epoch,11434):
                raise ValueError("engine_epoch_changed")
        except Exception as error:
            self.errors.append({"phase":self.phase,"code":"final_resource_observation_failed",
                                "reason":safe_reason(error)})
        finally:
            await self.client.aclose()

    def report(self):
        by_phase = {phase:summary([s for s in self.samples if s["phase"]==phase])
                    for phase in sorted({s["phase"] for s in self.samples})}
        for value in by_phase.values(): value.pop("limitations",None)
        return {"status":"passed" if not self.errors and len(self.samples)>=2 else "failed",
                "interval_seconds":self.interval,"api_pid":getattr(self,"api_pid",None),"ollama_pid":getattr(self,"ollama_pid",None),
                "samples":self.samples,"errors":self.errors,"summary":summary(self.samples),"by_phase":by_phase}


def safe_reason(error):
    # Only controlled observer codes. Never emit command stderr, URLs or a
    # library exception string (which can include private environment details).
    allowed = {"resource_command_failed","invalid_cpu_time","invalid_resource_process_table",
        "duplicate_process","observed_process_disappeared","other_or_orphan_ollama",
        "invalid_memory_observation","invalid_page_size","missing_free_pages","invalid_swap_observation",
        "unexpected_loaded_models","invalid_loaded_allocation","resource_sample_limit",
        "resource_metadata_limit","engine_epoch_changed","api_listener_unverified","ollama_pid_unverified"}
    return str(error) if isinstance(error,ValueError) and str(error) in allowed else type(error).__name__
