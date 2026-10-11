"""Local operator console for stage 3, not browser auth or an HTTP server."""
import asyncio
import json
import sys
import uuid

from .domain import InvalidInput, ModelProfile, NotFound, ServiceError
from .inference.coordinator import Coordinator
from .inference.ollama import OllamaAdapter


def operator(repository, username):
    try:
        return repository.user_id(username)
    except NotFound:
        # No password is generated or accepted. Future login must require a valid
        # Argon2 hash; this marker intentionally cannot authenticate a browser.
        return repository.create_user(username, "disabled:local-operator-stage3")


async def local_main(repository, args):
    adapter = OllamaAdapter(ModelProfile(prompt_version=args.prompt_version), url=args.ollama_url)
    input_transport = None
    try:
        if args.command == "doctor":
            print(json.dumps((await adapter.doctor()).to_dict(), ensure_ascii=False, indent=2))
            return 0
        async with Coordinator(repository, adapter) as coordinator:
            if args.command == "recover-inference":
                print(json.dumps(await coordinator.recover_after_restart(), indent=2))
                return 0
            await adapter.doctor()
            owner = await asyncio.to_thread(operator, repository, args.username)
            if args.chat_id:
                await asyncio.to_thread(repository.get_chat, owner, args.chat_id)
                chat = args.chat_id
            else:
                chat = (await asyncio.to_thread(repository.create_chat, owner, key=uuid.uuid4().hex)).chat_id
            print(f"chat_id={chat}\n/new /history /retry /recover /quit (local operator console)")
            reader = asyncio.StreamReader(limit=20 * 1024)
            try:
                input_transport, _ = await asyncio.get_running_loop().connect_read_pipe(
                    lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
            except (OSError, ValueError):
                raise InvalidInput("unsupported_console_input") from None
            last_user = None
            while True:
                print("You> ", end="", flush=True)
                try:
                    line = await reader.readline()
                    if not line:
                        return 0
                    content = line.decode(sys.stdin.encoding or "utf-8").removesuffix("\n").removesuffix("\r")
                except (UnicodeError, ValueError):
                    print("error=invalid_message")
                    continue
                if content.strip() == "/quit":
                    return 0
                try:
                    if content.strip() == "/new":
                        chat = (await asyncio.to_thread(repository.create_chat, owner, key=uuid.uuid4().hex)).chat_id
                        last_user = None
                        print(f"chat_id={chat}")
                        continue
                    if content.strip() == "/history":
                        cursor = 0
                        while rows := await asyncio.to_thread(repository.history, owner, chat, after_sequence=cursor):
                            for row in rows:
                                print(f"{row['role']} [{row['status']}]> {row['content']}")
                            cursor = rows[-1]["sequence"]
                        continue
                    if content.strip() == "/recover":
                        print(json.dumps(await coordinator.recover_after_restart()))
                        continue
                    revision = (await asyncio.to_thread(repository.get_chat, owner, chat))["revision"]
                    if content.strip() == "/retry":
                        if last_user is None:
                            original = await asyncio.to_thread(repository.export_chat, owner, chat)
                            last_user = next((m["id"] for m in reversed(original["messages"]) if m["role"] == "user"), None)
                        if last_user is None:
                            print("error=no_question_to_retry")
                            continue
                        receipt = await coordinator.service.retry(owner, last_user, expected_revision=revision, key=uuid.uuid4().hex)
                    else:
                        receipt = await coordinator.service.send(owner, chat, content, expected_revision=revision, key=uuid.uuid4().hex)
                        last_user = receipt.user_message_id
                    result = await coordinator.wait(owner, receipt.generation_id)
                    print(f"Bublik [{result['status']}]> {result['assistant']['content']}")
                    if result["error_code"]:
                        print(f"error={result['error_code']}")
                    print(json.dumps({"omitted_turns": result["context"]["omitted_turns"], "metrics": result["metrics"]}))
                except ServiceError as error:
                    print(f"error={error.code}")
    finally:
        if input_transport is not None:
            input_transport.close()
        await adapter.aclose()
