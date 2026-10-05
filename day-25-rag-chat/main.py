"""CLI chat, durable sessions and repeatable long-dialogue evaluation."""
import argparse
import json
from pathlib import Path
import shlex
import sys

from support25 import HERE, ROOT, KnowledgeBase, Settings, StructuredOllama, revision
from chat_store import ChatStore
from chat_agent import ChatAgent, render_response
from memory import forget, update


HELP = """/new [title]    /use SESSION    /sessions    /state    /history
/goal TEXT     /constraint TEXT    /clarify TEXT    /term NAME=DEFINITION
/forget goal | /forget constraints|clarifications|terms KEY
/export PATH   /recover (only after an interrupted process)    /quit
Ordinary messages run fresh RAG. Commands manage your conversation."""


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def memory_command(store, session, command, text):
    state = store.get(session)["state"]
    if command == "/forget":
        parts = shlex.split(text)
        if not parts or len(parts) > 2 or (parts[0] != "goal" and len(parts) != 2):
            raise ValueError("Use /forget goal or /forget FIELD KEY")
        state = forget(state, parts[0], parts[1] if len(parts) == 2 else "")
    else:
        kind = {"/goal": "goal", "/constraint": "constraints", "/clarify": "clarifications", "/term": "terms"}[command]
        key, value = "", text.strip()
        if kind == "terms":
            if "=" not in text:
                raise ValueError("Use /term NAME=DEFINITION")
            key, value = (part.strip() for part in text.split("=", 1))
            if not key:
                raise ValueError("Term name cannot be empty")
        state = update(state, kind, key, value, text, text, 0, origin="command")
    store.set_state(session, state, {"command": command, "text": text})
    return state


def interactive(agent, store, session):
    print(f"Bublik Day 25 | session={session}\n{HELP}", flush=True)
    while True:
        try:
            message = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\nSaved session: {session}")
            return
        if not message:
            continue
        try:
            if not message.startswith("/"):
                print("\nBublik>\n" + render_response(agent.ask(session, message)), flush=True)
                continue
            command, _, text = message.partition(" ")
            if command in ("/quit", "/exit"):
                print(f"Saved session: {session}")
                return
            if command == "/help":
                print(HELP)
            elif command == "/new":
                session = store.create(text or "Bublik RAG chat")
                print(f"New session: {session}")
            elif command == "/use":
                store.get(text.strip())
                session = text.strip()
                print(f"Session: {session}")
            elif command == "/sessions":
                print(json.dumps(store.sessions(), ensure_ascii=False, indent=2))
            elif command == "/state":
                print(json.dumps(store.get(session)["state"], ensure_ascii=False, indent=2))
            elif command == "/history":
                for row in store.history(session):
                    print(f"\nYou> {row['question']}")
                    print(render_response(row["response"]) if row["response"] else f"[{row['status']}] {row['error'] or ''}")
            elif command == "/export":
                if not text.strip():
                    raise ValueError("Use /export PATH.json")
                write_json(text.strip(), store.export(session))
                print(f"Saved: {text.strip()}")
            elif command == "/recover":
                print(f"Interrupted turns marked as errors: {store.recover(session)}")
            elif command in ("/goal", "/constraint", "/clarify", "/term", "/forget"):
                print(json.dumps(memory_command(store, session, command, text), ensure_ascii=False, indent=2))
            else:
                raise ValueError("Unknown command; use /help")
        except (ValueError, RuntimeError, OSError) as error:
            print(f"Error: {error}\nИсточники / Sources: нет подтверждённых источников (technical/command error).", file=sys.stderr)
        except KeyboardInterrupt:
            print(f"\nInterrupted turn saved as an error. Saved session: {session}")
            return


def parser_for_cli():
    parser = argparse.ArgumentParser(description="Day 25 — persistent RAG chat with task memory")
    parser.add_argument("--db", type=Path, default=ROOT / "day-21-document-indexing/knowledge.db")
    parser.add_argument("--chat-db", type=Path, default=HERE / "chats.db")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="bge-m3")
    parser.add_argument("--answer-model", default="qwen2.5:14b")
    parser.add_argument("--verifier-model")
    parser.add_argument("--num-ctx", type=int, default=32768)
    parser.add_argument("--num-predict", type=int, default=2500)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--strategy", choices=("fixed", "structural"), default="fixed")
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=5)
    parser.add_argument("--min-similarity", type=float, default=0.50)
    parser.add_argument("--rewrite-method", choices=("heuristic", "llm"), default="heuristic")
    parser.add_argument("--history-turns", type=int, default=4)
    parser.add_argument("--coverage-policy", choices=("strict", "diagnostic"), default="strict")
    parser.add_argument("--allow-stale-index", action="store_true",
                        help="Explicitly allow a previous corpus revision; index provenance stays in traces")
    commands = parser.add_subparsers(dest="command", required=True)
    chat = commands.add_parser("chat")
    chat.add_argument("--session")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--session")
    ask.add_argument("--output", type=Path)
    commands.add_parser("sessions")
    for name in ("history", "state", "export"):
        cmd = commands.add_parser(name)
        cmd.add_argument("session")
        if name == "export":
            cmd.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--scenarios", type=Path, default=HERE / "scenarios.json")
    evaluate.add_argument("--output", type=Path, default=HERE / "reports/check/live.json")
    commands.add_parser("offline-demo")
    return parser


def main():
    parser = parser_for_cli()
    args = parser.parse_args()
    store, kb = None, None
    try:
        if args.db.resolve() == args.chat_db.resolve():
            raise ValueError("Knowledge index and chat history must use different database files")
        if args.command == "offline-demo":
            from offline_demo import run_demo
            report = run_demo()
            print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
            return 0 if report["summary"]["all_checks_pass"] else 1
        store = ChatStore(args.chat_db)
        if args.command in ("sessions", "history", "state", "export"):
            payload = store.sessions() if args.command == "sessions" else (
                store.history(args.session) if args.command == "history" else
                store.get(args.session)["state"] if args.command == "state" else store.export(args.session))
            if args.command == "export":
                write_json(args.output, payload)
            else:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        settings = Settings(args.candidate_k, args.final_k, args.min_similarity, args.strategy, args.rewrite_method)
        if not args.db.is_file():
            raise ValueError("Missing Day 21 index; run Day 21 build and verify first")
        kb = KnowledgeBase(args.db)
        info = kb.info(args.strategy)
        if not args.allow_stale_index and info["revision"] != revision(ROOT):
            raise ValueError("Index revision is stale; rebuild/verify Day 21 or explicitly pass --allow-stale-index")
        options = dict(num_ctx=args.num_ctx, num_predict=args.num_predict, timeout=args.timeout)
        provider = StructuredOllama(args.url, args.model, args.answer_model, **options)
        verifier = StructuredOllama(args.url, args.model, args.verifier_model, **options) if args.verifier_model else provider
        agent = ChatAgent(store, kb, provider, settings, verifier, args.history_turns,
                          args.coverage_policy, progress=lambda text: print(text, file=sys.stderr, flush=True))
        if args.command == "evaluate":
            from evaluate25 import evaluate
            def restart():
                nonlocal store, kb
                store.close()
                kb.close()
                store = ChatStore(args.chat_db)
                kb = KnowledgeBase(args.db)
                agent.store, agent.kb = store, kb
            report = evaluate(agent, args.scenarios, backend="live-ollama", restart=restart,
                              progress=lambda text: print(text, file=sys.stderr, flush=True))
            write_json(args.output, report)
            print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
            return 0 if report["summary"]["all_checks_pass"] else 1
        session = args.session or store.create()
        store.get(session)
        if args.command == "chat":
            interactive(agent, store, session)
        else:
            result = agent.ask(session, args.question)
            if args.output:
                write_json(args.output, result)
            print(f"Session: {session}\n" + render_response(result))
        return 0
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Error: {error}\nИсточники / Sources:\nНет подтверждённых источников / No confirmed sources.", file=sys.stderr)
        return 2
    finally:
        if kb:
            kb.close()
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
