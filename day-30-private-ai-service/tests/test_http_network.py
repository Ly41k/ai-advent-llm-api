"""Actual TLS socket and process-style app restart. No real Ollama or LAN proof."""
import asyncio
import io
import json
import logging
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest

import httpx
import uvicorn

from bublik_service.domain import ModelProfile,ModelUnavailable,ContextPlan
from bublik_service.http_api import HTTPSettings,create_app
from bublik_service.security import COOKIE,SCOPES,SecurityStore,password_hash
from bublik_service.storage import ChatRepository


class OfflineAdapter:
    profile = ModelProfile()

    async def doctor(self):
        raise ModelUnavailable()

    async def aclose(self):
        pass


class NetworkTests(unittest.TestCase):
    def test_real_tls_login_auth_persistence_restart_and_redacted_logs(self):
        self.assertIsNotNone(shutil.which("openssl"),"OpenSSL required for genuine HTTPS test")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key,cert,config = root/"key.pem",root/"cert.pem",root/"tls.cnf"
            config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\nextendedKeyUsage=serverAuth\n')
            subprocess.run(["openssl","req","-x509","-nodes","-newkey","rsa:2048","-days","1",
                            "-config",str(config),"-keyout",str(key),"-out",str(cert)],check=True,capture_output=True)
            key.chmod(0o600)
            path = root/"chats.sqlite3"
            repo = ChatRepository(path)
            owner = repo.create_user("network",password_hash("Network-synthetic-password-123"))
            auth = SecurityStore(repo)
            token = auth.issue_token(owner,"network",SCOPES)["token"]
            seed = repo.create_chat(owner,"saved synthetic turn",key="seed").chat_id
            receipt = repo.accept_message(owner,seed,"saved question",expected_revision=0,key="seed",context=ContextPlan(input_token_upper_bound=512))
            with repo.worker_session() as worker:
                worker.claim_next()
                worker.finish(receipt.generation_id,status="completed",content="saved answer")
            expected_history = repo.history(owner,seed)
            tls = ssl.create_default_context(cafile=str(cert))
            output = io.StringIO()
            handler = logging.StreamHandler(output)
            logger = logging.getLogger("uvicorn.error")
            logger.addHandler(handler)
            self.addCleanup(logger.removeHandler,handler)
            server = None
            def start_server():
                nonlocal server
                listener = socket.socket()
                listener.bind(("127.0.0.1",0))
                port = listener.getsockname()[1]
                listener.listen(64)
                settings = HTTPSettings(path,origins=(f"https://localhost:{port}",f"https://127.0.0.1:{port}"),body_timeout=.15)
                app = create_app(settings,adapter_factory=OfflineAdapter)
                server = uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,log_config=None,access_log=False,
                    proxy_headers=False,ssl_certfile=str(cert),ssl_keyfile=str(key),timeout_graceful_shutdown=2))
                thread = threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True)
                thread.start()
                deadline = time.monotonic()+5
                while not server.started and thread.is_alive() and time.monotonic()<deadline:
                    time.sleep(.02)
                self.assertTrue(server.started,"TLS server did not start")
                return port,thread,listener
            def stop(thread,listener):
                server.should_exit = True
                thread.join(8)
                listener.close()
                self.assertFalse(thread.is_alive(),"HTTP shutdown leaked its worker")
            port,thread,listener = start_server()
            cookie = chat = None
            try:
                with httpx.Client(base_url=f"https://localhost:{port}",verify=tls,trust_env=False,timeout=5) as client:
                    self.assertEqual(client.get("/api/v1/health/live").status_code,200)
                    self.assertEqual(client.get("/api/v1/chats").status_code,401)
                    bootstrap = client.get("/api/v1/auth/session").json()
                    response = client.post("/api/v1/auth/login",json={"username":"network","password":"Network-synthetic-password-123"},
                        headers={"Origin":f"https://localhost:{port}","X-CSRF-Token":bootstrap["csrf_token"]})
                    self.assertEqual(response.status_code,200,response.text)
                    cookie = client.cookies.get(COOKIE)
                    csrf = response.json()["csrf_token"]
                    response = client.post("/api/v1/chats",json={"title":"PERSONAL-SENTINEL"},headers={"Idempotency-Key":"network",
                        "Origin":f"https://localhost:{port}","X-CSRF-Token":csrf})
                    self.assertEqual(response.status_code,201,response.text)
                    chat = response.json()["chat_id"]
                    client.cookies.clear()
                    bad = client.post("/api/v1/chats",json={"title":"PRIVATE-SENTINEL","owner_id":"PRIVATE-SENTINEL"},headers={"Authorization":"Bearer "+token})
                    self.assertEqual(bad.status_code,422,bad.text)
                    self.assertNotIn("PRIVATE-SENTINEL",bad.text)
                    ready = client.get("/api/v1/health/ready",headers={"Authorization":"Bearer "+token})
                    self.assertEqual(ready.status_code,503)
                import sys
                sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
                from check_browser_https import run_browser
                async def browser_check():
                    async with httpx.AsyncClient(base_url=f"https://localhost:{port}",verify=tls,trust_env=False,timeout=5) as client:
                        report = {}
                        await run_browser(client,report,"network","Network-synthetic-password-123")
                        self.assertTrue(all(c["passed"] for c in report["checks"]))
                asyncio.run(browser_check())
                # Actual chunked receive over TLS: no Content-Length shortcut.
                with tls.wrap_socket(socket.create_connection(("127.0.0.1",port),timeout=5),server_hostname="localhost") as connection:
                    headers = f"POST /api/v1/chats HTTP/1.1\r\nHost: localhost:{port}\r\nAuthorization: Bearer {token}\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
                    connection.sendall(headers.encode()+b"9000\r\n"+b"x"*36864+b"\r\n0\r\n\r\n")
                    response = connection.recv(8192)
                    self.assertIn(b"413",response.split(b"\r\n",1)[0])
                # Incomplete JSON body times out; application emits safe 408.
                with tls.wrap_socket(socket.create_connection(("127.0.0.1",port),timeout=5),server_hostname="localhost") as connection:
                    headers = f"POST /api/v1/chats HTTP/1.1\r\nHost: localhost:{port}\r\nContent-Type: application/json\r\nContent-Length: 100\r\nConnection: close\r\n\r\n"
                    connection.sendall(headers.encode()+b"{")
                    self.assertIn(b"408",connection.recv(8192).split(b"\r\n",1)[0])
            finally:
                stop(thread,listener)
            port,thread,listener = start_server()
            try:
                with httpx.Client(base_url=f"https://localhost:{port}",verify=tls,trust_env=False,timeout=5) as client:
                    client.cookies.set(COOKIE,cookie,domain="localhost.local",path="/")
                    # Cookie persisted in SQLite; fresh process state, same user.
                    r = client.get("/api/v1/chats/"+chat)
                    self.assertEqual(r.status_code,200,r.text)
                    self.assertEqual(r.json()["title"],"PERSONAL-SENTINEL")
                    history = client.get("/api/v1/chats/"+seed+"/messages")
                    self.assertEqual(history.json()["items"],expected_history)
                    client.cookies.clear()
                    r = client.get("/api/v1/chats/"+chat,headers={"Authorization":"Bearer "+token})
                    self.assertEqual(r.status_code,200,r.text)
            finally:
                stop(thread,listener)
            for secret in ("PRIVATE-SENTINEL","PERSONAL-SENTINEL",token,cookie,"Network-synthetic-password-123"):
                self.assertNotIn(secret,output.getvalue())
