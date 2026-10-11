"""Local account/token management; secrets are entered without command-line args."""
import getpass
import json
from pathlib import Path
import os

from .domain import InvalidInput
from .security import SCOPES, SecurityStore, password_hash


def admin_main(repository,args):
    auth = SecurityStore(repository)
    if args.command in {"user-add","password-set"}:
        password = getpass.getpass("Password (12+ characters): ")
        if password != getpass.getpass("Confirm password: "):
            raise InvalidInput("password_confirmation_mismatch")
        if args.command == "user-add":
            owner = repository.create_user(args.username,password_hash(password))
        else:
            owner = repository.user_id(args.username)
            auth.set_password(owner,password)
        print(json.dumps({"user_id":owner,"status":"saved"}))
        return 0
    owner = repository.user_id(args.username)
    if args.command == "token-create":
        scopes = args.scopes.split(",") if args.scopes else sorted(SCOPES)
        # Reserve a PRIVATE output before issuing, and never overwrite an old token.
        fd = None
        if args.output:
            path = Path(args.output).expanduser().absolute()
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            try:
                fd = os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            except OSError:
                raise InvalidInput("token_output_exists_or_unwritable") from None
        try:
            value = auth.issue_token(owner,args.label,scopes,days=args.days)
            if fd is not None:
                with os.fdopen(fd,"w") as stream:
                    fd = None
                    json.dump(value,stream,indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                print(json.dumps({"id":value["id"],"status":"saved_to_private_file"}))
            else:
                print(json.dumps(value,indent=2))
        finally:
            if fd is not None:
                os.close(fd)
        return 0
    if args.command == "token-list":
        print(json.dumps(auth.list_tokens(owner),indent=2))
    else:
        auth.revoke_token(owner,args.token_id)
        print(json.dumps({"status":"revoked"}))
    return 0


def serve(repository,args):
    import uvicorn
    from .http_api import HTTPSettings,create_app
    if bool(args.tls_cert) != bool(args.tls_key):
        raise InvalidInput("tls_certificate_and_key_required")
    if args.trusted_loopback_proxy and (args.tls_cert or not args.origin):
        raise InvalidInput("proxy_requires_explicit_origins_without_backend_tls")
    origins = tuple(args.origin or (f"https://localhost:{args.port}",f"https://127.0.0.1:{args.port}"))
    settings = HTTPSettings(repository.database.path,origins=origins,ollama_url=args.ollama_url,
                            trusted_loopback_proxy=args.trusted_loopback_proxy, prompt_version=args.prompt_version)
    # No reload, multi-process workers, public bind, or implicit forwarded trust.
    uvicorn.run(create_app(settings),host="127.0.0.1",port=args.port,workers=1,
                proxy_headers=False,access_log=False,server_header=False,
                ssl_certfile=str(args.tls_cert) if args.tls_cert else None,
                ssl_keyfile=str(args.tls_key) if args.tls_key else None,
                limit_concurrency=64,timeout_keep_alive=5,timeout_graceful_shutdown=15)
    return 0
