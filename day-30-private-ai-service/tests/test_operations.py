"""Supervisor config, independent restart witnesses and PWA privacy boundaries."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest

import httpx

from bublik_service.domain import ContextPlan
from bublik_service.storage import ChatRepository
from bublik_service.security import password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
from configure_launchd import generate, API_LABEL
from check_launchd_live import baseline_checks, launch_pid, boot_fingerprint
from check_storage import manifest
from bublik_service.http_api import runtime_manifest
from install_launchd import install


class OperationsTests(unittest.TestCase):
    def test_launch_agent_preserves_venv_arguments_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            database = directory/"chats.sqlite3"
            database.write_bytes(b"unchanged database")
            interpreter = directory/"venv python"
            interpreter.symlink_to(sys.executable)
            output = directory/"generated"
            generate(interpreter, ROOT, database, ["https://node.tail123.ts.net"], output)
            p = output/(API_LABEL+".plist")
            value = plistlib.loads(p.read_bytes())
            self.assertEqual(value["ProgramArguments"][0], str(interpreter))
            self.assertEqual(value["ProgramArguments"][4], str(database))
            self.assertNotIn("sh", value["ProgramArguments"])
            self.assertTrue(value["KeepAlive"])
            self.assertGreaterEqual(value["ExitTimeOut"], 60)
            self.assertEqual(value["StandardErrorPath"], "/dev/null")
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            before = p.read_bytes()
            with self.assertRaises(FileExistsError):
                generate(interpreter, ROOT, database, ["https://node.tail123.ts.net"], output)
            self.assertEqual(p.read_bytes(), before)
            self.assertEqual(database.read_bytes(), b"unchanged database")
            with self.assertRaises(ValueError):
                generate(interpreter, ROOT, database, ["http://node.tail123.ts.net"], directory/"bad")
            self.assertFalse((directory/"bad").exists())
            with self.assertRaises(ValueError):
                generate(interpreter, ROOT, database, ["https://node.tail123.ts.net"], directory/"bad", caddy=sys.executable)

    def test_restart_and_reboot_require_independent_witness_and_same_history(self):
        before = {"format":"bublik-stage7-launchd-live-v1", "status":"passed",
                  "source_sha256":{}, "url":"https://node.tail.ts.net", "chat_id":"chat",
                  "plist_sha256":"config", "history_sha256":"history", "message_count":4,
                  "model_identity":{}, "profile":{}, "api_pid":10, "os_boot_sha256":"boot"}
        after = {**before, "api_pid":20}
        self.assertTrue(all(p for _,p in baseline_checks(before, after, "restart")))
        self.assertFalse(all(p for _,p in baseline_checks(before, before, "restart")))
        self.assertFalse(all(p for _,p in baseline_checks(before, after, "reboot")))
        self.assertTrue(all(p for _,p in baseline_checks(before, {**after,"os_boot_sha256":"next"}, "reboot")))
        for changed in ({"history_sha256":"changed"}, {"message_count":6}, {"source_sha256":{"x":"y"}},
                        {"plist_sha256":"other"}, {"chat_id":"other"}, {"profile":{"num_ctx":1}}):
            self.assertFalse(all(p for _,p in baseline_checks(before, {**after,**changed}, "restart")))
        self.assertEqual(launch_pid("\tstate = running\n\tpid = 123\n"), 123)
        for text in ("state = waiting\npid = 123", "state = running", "state = running\npid = 0"):
            with self.assertRaises(ValueError): launch_pid(text)
        self.assertEqual(boot_fingerprint("{ sec = 123, usec = 456 } date"),
                         boot_fingerprint("{ sec = 123, usec = 456 } other timezone"))
        with self.assertRaises(ValueError): boot_fingerprint("unknown")

    def test_install_is_private_exclusive_and_never_loads_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp); database=directory/"chats.sqlite3"
            database.write_bytes(b"database")
            source=directory/"generated"; destination=directory/"LaunchAgents"
            generate(sys.executable,ROOT,database,["https://node.tail.ts.net"],source)
            result=install(source,destination)
            self.assertEqual(result["status"],"installed_not_loaded")
            p=destination/(API_LABEL+".plist")
            self.assertEqual(p.read_bytes(),(source/p.name).read_bytes())
            self.assertEqual(p.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):install(source,destination)
            p.unlink();p.symlink_to(source/p.name)
            with self.assertRaises(FileExistsError):install(source,destination)

    def test_manifest_packaged_icons_and_source_hashes(self):
        root = ROOT/"bublik_service/web_ui"
        value = json.loads((root/"manifest.webmanifest").read_bytes())
        self.assertEqual((value["id"],value["scope"],value["start_url"]), ("/","/","/"))
        self.assertEqual(value["display"], "standalone")
        for size in (180,192,512):
            icon = root/f"icon-{size}.png"
            raw = icon.read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", raw[16:24]), (size,size))
            self.assertEqual(manifest()[str(icon.relative_to(ROOT))], hashlib.sha256(raw).hexdigest())
            self.assertIn("web_ui/"+icon.name, runtime_manifest())
        self.assertIn("web_ui/manifest.webmanifest", runtime_manifest())

    def test_sigterm_releases_lease_and_restart_preserves_completed_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp)/"chat.sqlite3"
            repo = ChatRepository(database)
            owner = repo.create_user("operator", password_hash("Synthetic-operator-password-123"))
            chat = repo.create_chat(owner,key="seed").chat_id
            receipt = repo.accept_message(owner,chat,"synthetic question",expected_revision=0,
                                          key="question",context=ContextPlan(input_token_upper_bound=512))
            with repo.worker_session() as worker:
                worker.claim_next()
                worker.finish(receipt.generation_id,status="completed",content="synthetic answer")
            before = repo.history(owner,chat)
            with socket.socket() as s:
                s.bind(("127.0.0.1",0)); port = s.getsockname()[1]
            code = '''import sys,uvicorn
from pathlib import Path
from bublik_service.http_api import HTTPSettings,create_app
from bublik_service.domain import ModelUnavailable
class Offline:
 async def doctor(self): raise ModelUnavailable()
 async def aclose(self): pass
app=create_app(HTTPSettings(Path(sys.argv[1]),origins=("https://localhost:"+sys.argv[2],),trusted_loopback_proxy=True),adapter_factory=Offline)
uvicorn.run(app,host="127.0.0.1",port=int(sys.argv[2]),proxy_headers=False,access_log=False,log_level="critical",timeout_graceful_shutdown=1)
'''
            for _ in range(2):
                process = subprocess.Popen([sys.executable,"-c",code,str(database),str(port)],cwd=ROOT,
                                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    deadline = time.monotonic()+10
                    with httpx.Client(trust_env=False,timeout=.5) as client:
                        while time.monotonic()<deadline and process.poll() is None:
                            try:
                                response = client.get(f"http://127.0.0.1:{port}/api/v1/health/live",
                                    headers={"Host":f"localhost:{port}","X-Forwarded-Proto":"https"})
                                if response.status_code == 200: break
                            except httpx.HTTPError: pass
                            time.sleep(.02)
                        else: self.fail("fixture failed to start")
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=10)
                    self.assertEqual(repo.history(owner,chat), before)
                    self.assertFalse(repo.queue_status()["inference_recovery_required"])
                    with repo.worker_session(): pass
                finally:
                    if process.poll() is None:
                        process.kill(); process.wait(timeout=5)
