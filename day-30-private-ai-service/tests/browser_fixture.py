"""Isolated synthetic engine for browser checks. Never imported by production CLI."""
import asyncio
from pathlib import Path
import socket
import subprocess
import threading
import time

import uvicorn

from bublik_service.domain import ContextPlan, ModelIdentity, ModelProfile, ModelUnavailable
from bublik_service.http_api import HTTPSettings, create_app
from bublik_service.inference.context import TEMPLATE_SHA256
from bublik_service.inference.ollama import Answer, Doctor, InferenceError
from bublik_service.security import SecurityStore, password_hash
from bublik_service.storage import ChatRepository

PASSWORD="Synthetic-browser-password-123"


class BrowserAdapter:
    profile=ModelProfile()

    def __init__(self):
        self.available=True
        self.failed=set()
        self.calls=0

    async def doctor(self):
        if not self.available:
            raise ModelUnavailable()
        return Doctor(ModelIdentity(self.profile.model,"a"*64,TEMPLATE_SHA256,"0.0.0"),"b"*64,(),0)

    async def generate(self, job, checkpoint):
        self.calls+=1
        question=job["context"]["messages"][-1]["content"]
        if question=="FAIL_ONCE" and job["user_message_id"] not in self.failed:
            self.failed.add(job["user_message_id"])
            raise InferenceError("model_unavailable",uncertain=False)
        answer="Synthetic reply: "+question
        for size in (10,len(answer)//2,len(answer)):
            await asyncio.sleep(.4)
            await checkpoint(answer[:size])
        return Answer(answer,"completed",{"input_tokens":1,"output_tokens":1})

    async def aclose(self):
        pass


class BrowserFixture:
    def __init__(self, root):
        self.root=Path(root)
        self.cert,self.key=self.root/"cert.pem",self.root/"key.pem"
        config=self.root/"tls.cnf"
        config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature,keyEncipherment,keyCertSign\nextendedKeyUsage=serverAuth\n')
        subprocess.run(["openssl","req","-x509","-nodes","-newkey","rsa:2048","-days","1",
            "-config",str(config),"-keyout",str(self.key),"-out",str(self.cert)],check=True,capture_output=True)
        self.key.chmod(0o600)
        self.repo=ChatRepository(self.root/"chats.sqlite3")
        self.owner=self.repo.create_user("ui-test",password_hash(PASSWORD))
        self.other=self.repo.create_user("other",password_hash(PASSWORD))
        self.auth=SecurityStore(self.repo)
        self.seed=self.repo.create_chat(self.owner,"Ранние сообщения",key="seed").chat_id
        with self.repo.worker_session() as worker:
            for n in range(60):
                receipt=self.repo.accept_message(self.owner,self.seed,"seed "+str(n),
                    expected_revision=self.repo.get_chat(self.owner,self.seed)["revision"],
                    key=str(n),context=ContextPlan(input_token_upper_bound=512))
                worker.claim_next()
                worker.finish(receipt.generation_id,status="completed",content="seed reply "+str(n))
        self.adapter=BrowserAdapter()
        self.listener=socket.socket()
        self.listener.bind(("127.0.0.1",0)); self.port=self.listener.getsockname()[1]
        self.listener.listen(64)
        self.url=f"https://localhost:{self.port}"
        self.app=create_app(HTTPSettings(self.repo.database.path,origins=(self.url,),sse_poll=.1),
            adapter_factory=lambda:self.adapter,repository=self.repo,security=self.auth)
        self.server=uvicorn.Server(uvicorn.Config(self.app,host="127.0.0.1",port=self.port,
            ssl_certfile=str(self.cert),ssl_keyfile=str(self.key),access_log=False,
            log_level="critical",proxy_headers=False,timeout_graceful_shutdown=2))
        self.thread=threading.Thread(target=lambda:self.server.run(sockets=[self.listener]),daemon=True)
        self.thread.start()
        deadline=time.monotonic()+10
        while not self.server.started and self.thread.is_alive() and time.monotonic()<deadline:
            time.sleep(.02)
        if not self.server.started:
            self.close()
            raise RuntimeError("fixture_server_failed")

    def close(self):
        self.server.should_exit=True
        self.thread.join(10)
        self.listener.close()
        if self.thread.is_alive():
            raise RuntimeError("fixture_server_did_not_stop")
