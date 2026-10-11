"""Storage administration and local inference console; HTTP API and inference console."""
import argparse
import json
from pathlib import Path

from .domain import DEFAULT_PROMPT_VERSION, SYSTEM_PROMPTS, ServiceError
from .settings import default_database
from .storage import ChatRepository


def port_number(value):
    port = int(value)
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be 1024..65535")
    return port


def main():
    parser = argparse.ArgumentParser(description="Bublik Day 30 — local operator tools (stages 1–8)")
    parser.add_argument("--db", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("storage-status")
    backup = sub.add_parser("backup")
    backup.add_argument("destination", type=Path)
    for name in ("doctor", "chat", "recover-inference"):
        command = sub.add_parser(name)
        command.add_argument("--ollama-url", default="http://127.0.0.1:11434")
        command.add_argument("--prompt-version", choices=tuple(SYSTEM_PROMPTS), default=DEFAULT_PROMPT_VERSION)
        if name == "chat":
            command.add_argument("--username", default="local-stage3-operator")
            command.add_argument("--chat-id")
    for name in ("user-add", "password-set", "token-create", "token-list", "token-revoke"):
        command = sub.add_parser(name)
        command.add_argument("username")
        if name == "token-create":
            command.add_argument("--label", default="personal-client")
            command.add_argument("--scopes", help="Comma-separated scopes; default all personal scopes")
            command.add_argument("--days", type=int, default=30)
            command.add_argument("--output", type=Path, help="NEW private JSON file; secret printed once otherwise")
        if name == "token-revoke":
            command.add_argument("token_id")
    server = sub.add_parser("serve")
    server.add_argument("--port", type=port_number, default=8000, metavar="PORT")
    server.add_argument("--origin", action="append", help="Explicit canonical HTTPS origin, repeatable")
    server.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    server.add_argument("--prompt-version", choices=tuple(SYSTEM_PROMPTS), default=DEFAULT_PROMPT_VERSION)
    server.add_argument("--tls-cert", type=Path)
    server.add_argument("--tls-key", type=Path)
    server.add_argument("--trusted-loopback-proxy", action="store_true",
                        help="Require HTTPS proxy headers from raw loopback peer; API still binds 127.0.0.1")
    args = parser.parse_args()
    path = args.db if args.db is not None else default_database()
    if args.command != "init-db" and not path.is_file():
        print(json.dumps({"error": "database_not_initialized"}))
        return 1
    try:
        repository = ChatRepository(path)
        if args.command in {"doctor", "chat", "recover-inference"}:
            import asyncio
            from .local_cli import local_main
            try:
                return asyncio.run(local_main(repository, args))
            except KeyboardInterrupt:
                return 130
        if args.command == "serve":
            from .admin_cli import serve
            return serve(repository,args)
        if args.command in {"user-add","password-set","token-create","token-list","token-revoke"}:
            from .admin_cli import admin_main
            return admin_main(repository,args)
        result = (repository.backup(args.destination) if args.command == "backup"
                  else repository.storage_status())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        return 130
    except EOFError:
        print(json.dumps({"error":"operator_input_cancelled"}))
        return 1
    except ServiceError as error:
        print(json.dumps({"error": error.code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
