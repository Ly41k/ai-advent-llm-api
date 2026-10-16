"""Scoped developer CLI: help, read-only Git, project retrieval and answer pipeline."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from time import perf_counter

from . import __version__
from .contracts import Role, TaskEnvelope
from .errors import DeveloperError, ErrorCode
from .preflight import DoctorFailure

HELP_RU = """Bublik Developer Assistant — день 31, этапы 1–6

/help                         Возможности без модели и профиля
/help branch                  Текущая ветка через реальный MCP
/help status                  Изменённые файлы
/help files                   Разрешённые файлы проекта
/help diff                    Метаданные unstaged diff
/help вопрос                  Project pipeline: Git, документы или их сочетание
ask "вопрос"                  Тот же pipeline с ответом Qwen и источниками

index build --mode fts         Создать Project RAG без модели
index verify                  Проверить текущую версию и источники
search "вопрос" --mode fts     Вернуть документальные выдержки
models prepare / confirm      Отдельная сессия Ollama для embeddings
models status                 Состояние gate без model/HTTP запросов
agents demo                   Documentation + Git → Verification → Main merge

CLI: doctor; git branch|status|files|diff; console.
Содержимое diff: git diff --path README.md --include-content.
Project RAG возвращает выдержки. Runtime делегирует отдельные задачи.
Qwen2.5:14b Q4_K_M отвечает по источникам. Git-запросы не требуют модели.
--pipeline-mode fts|dense|hybrid задаётся перед командой; default fts.
Commit/push и изменения исходников не поддерживаются.
"""
HELP_EN = """Bublik Developer Assistant — Day 31, stages 1–6

/help                         Capabilities without a model or profile
/help branch                  Actual branch through MCP
/help status                  Changed file metadata
/help files                   Allowed project files
/help diff                    Unstaged diff metadata
/help question                Project pipeline: Git, documentation or both
ask "question"                Same pipeline with a Qwen answer and sources

index build --mode fts         Build Project RAG without a model
index verify                  Verify the current index and sources
search "question" --mode fts   Retrieve source excerpts
models prepare / confirm      Reserve a fresh Ollama session
models status                 Inspect the gate without model/HTTP requests
agents demo                   Documentation + Git → Verification → Main merge

CLI: doctor; git branch|status|files|diff; console.
Diff text: git diff --path README.md --include-content.
Project RAG retrieves excerpts. The runtime delegates separate tasks.
Qwen2.5:14b Q4_K_M answers from sources. Git requests do not need a model.
--pipeline-mode fts|dense|hybrid goes before the command; default fts.
Commit/push and source writes are unsupported.
"""


def emit(value):
    # ASCII escaping prevents filenames/patches from injecting terminal controls.
    print(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2))


async def git_request(root, project_id, operation, arguments):
    from .mcp_client import ScopedGitClient, connect_git
    from .workspace import ProjectWorkspace
    workspace = ProjectWorkspace.open(root, project_id)
    task = TaskEnvelope.create(Role.GIT, workspace.project_id, operation, {"operation": operation, "arguments": arguments})
    started = perf_counter()
    names = {"branch": "git__git_current_branch", "status": "git__git_status",
             "files": "git__project_list_files", "diff": "git__git_diff"}
    async with connect_git(workspace) as registry:
        result = await ScopedGitClient(registry, task).call(names[operation], arguments)
        return {"request_id": task.request_id, "task_id": task.task_id, "transport": "mcp_stdio",
                "discovered_tools": sorted(registry.catalog), "result": result,
                "metrics": {"total_seconds": perf_counter() - started, "tool_calls": len(registry.events),
                            "llm_calls": 0, "input_tokens": 0, "output_tokens": 0}, "tool_events": registry.events}


def help_operation(question):
    value = question.casefold().strip().strip("?")
    return {"branch": "branch", "current branch": "branch", "какая текущая ветка": "branch",
            "текущая ветка": "branch", "status": "status", "files": "files", "diff": "diff"}.get(value)


def parser_for_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Local Git repository root")
    parser.add_argument("--project-id", default="ai-advent-llm-api", help="Stable logical project ID")
    parser.add_argument("--language", choices=("ru", "en"), default="ru")
    parser.add_argument("--state-dir", type=Path, help="Private index state OUTSIDE the project")
    parser.add_argument("--manifest", type=Path, help="Explicit documentation source manifest")
    parser.add_argument("--pipeline-mode", choices=("fts", "dense", "hybrid"), default="fts")
    parser.add_argument("--max-calls", type=int, default=8)
    parser.add_argument("--deadline", type=float, default=300)
    sub = parser.add_subparsers(dest="command")
    help_parser = sub.add_parser("help", aliases=["/help"])
    help_parser.add_argument("question", nargs="*", default=[])
    ask = sub.add_parser("ask", help="Read-only developer pipeline with grounded Qwen claims")
    ask.add_argument("question", nargs="+", help="RU/EN project question")
    doctor = sub.add_parser("doctor", help="Check Day 30 is off; no Ollama request")
    doctor.add_argument("--day30-port", action="append", type=int, default=[], help="Extra Day 30 port; 8000 is always checked")
    git = sub.add_parser("git")
    git.add_argument("operation", choices=("branch", "status", "files", "diff"))
    git.add_argument("--scope", choices=("staged", "unstaged"), default="unstaged")
    git.add_argument("--path", action="append", default=[])
    git.add_argument("--include-content", action="store_true")
    sub.add_parser("console")
    index = sub.add_parser("index")
    index.add_argument("operation", choices=("build", "verify", "info"))
    index.add_argument("--mode", choices=("fts", "dense", "hybrid"), default="fts")
    index.add_argument("--limit-words", type=int, default=250)
    index.add_argument("--overlap-words", type=int, default=40)
    search = sub.add_parser("search")
    search.add_argument("question")
    search.add_argument("--mode", choices=("fts", "dense", "hybrid"), default="fts")
    search.add_argument("--candidate-k", type=int, default=20)
    search.add_argument("--final-k", type=int, default=5)
    search.add_argument("--min-cosine", type=float, default=.5)
    search.add_argument("--dense-query", choices=("auto", "raw", "vocabulary"), default="auto")
    search.add_argument("--diagnostics", action="store_true", help="Top 100 dense scores before the cutoff; not evidence")
    search.add_argument("--source", action="append", help="Restrict the indexed namespace before ranking")
    models = sub.add_parser("models")
    models.add_argument("operation", choices=("prepare", "confirm", "status"))
    agents = sub.add_parser("agents", help="Real task lifecycle; FTS/MCP, zero model calls")
    agents.add_argument("operation", choices=("demo", "docs", "git"))
    agents.add_argument("--question", default="How does memory retrieval work?")
    agents.add_argument("--git-operation", choices=("branch", "status", "files", "diff"), default="branch")
    return parser


def rag_command(args):
    from contextlib import nullcontext
    import sqlite3
    from .workspace import ProjectWorkspace
    from .rag.corpus import ProjectCorpus, load_selection
    from .rag.state import ProjectState
    from .rag.index import ProjectIndex, build_index
    from .rag.retrieval import search
    workspace = ProjectWorkspace.open(args.root, args.project_id)
    if args.command == "models":
        from .model_session import ModelSession
        return getattr(ModelSession(workspace), args.operation)()
    corpus = ProjectCorpus(workspace, load_selection(args.manifest) if args.manifest else None)
    state = ProjectState(workspace, args.state_dir)
    needs_model = args.mode != "fts" and (args.command == "search" or args.operation == "build")
    if needs_model:
        from .model_session import ModelSession
        from .rag.embeddings import LocalEmbeddings
        manager = ModelSession(workspace).lease()
    else:
        manager = nullcontext(None)
    try:
        with manager as lease:
            provider = LocalEmbeddings(lease) if needs_model else None
            if args.command == "index" and args.operation == "build":
                return build_index(corpus, state, provider=provider, limit=args.limit_words, overlap=args.overlap_words)
            with ProjectIndex.current(state, corpus) as index:
                if args.command == "index":
                    return index.verify() if args.operation == "verify" else {"index": index.metadata}
                result = search(index, args.question, mode=args.mode, provider=provider, candidate_k=args.candidate_k,
                                final_k=args.final_k, min_cosine=args.min_cosine, sources=args.source,
                                dense_query=args.dense_query, diagnostics=args.diagnostics)
                result["embedding_metrics"] = provider.events if provider else []
                return result
    except sqlite3.Error:
        raise DeveloperError(ErrorCode.INDEX_UNAVAILABLE) from None


async def pipeline_request(args, question, *, session=None):
    from .pipeline import Pipeline
    from .workspace import ProjectWorkspace
    from .rag.corpus import ProjectCorpus, load_selection
    workspace = ProjectWorkspace.open(args.root, args.project_id)
    corpus = ProjectCorpus(workspace, load_selection(args.manifest)) if args.manifest else None
    result = await Pipeline(workspace, state_dir=args.state_dir, corpus=corpus, language=args.language,
                            mode=args.pipeline_mode, max_calls=args.max_calls, timeout=args.deadline).run(question, session=session)
    result["version"] = __version__
    return result


def main(argv=None):
    args = parser_for_cli().parse_args(argv)
    help_text = HELP_RU if args.language == "ru" else HELP_EN
    try:
        if args.command is None or (args.command in {"help", "/help"} and not args.question):
            print(help_text)
        elif args.command == "doctor":
            from .preflight import check_day30_off
            try:
                checked = check_day30_off(args.day30_port)
            except DoctorFailure as error:
                emit({"status": "failed", "version": __version__, "error": error.to_dict(),
                      "probes": error.checks, "mac_check": sys.platform == "darwin", "model_stage_implemented": True})
                return 2
            emit({"status": "passed", "version": __version__, "checks": checked,
                  "mac_check": sys.platform == "darwin", "model_stage_implemented": True, "inference_readiness_checked": False})
        elif args.command in {"index", "search", "models"}:
            emit(rag_command(args))
        elif args.command == "agents":
            from .agent_runtime import demo
            from .workspace import ProjectWorkspace
            from .rag.corpus import ProjectCorpus, load_selection
            from .rag.state import ProjectState
            workspace = ProjectWorkspace.open(args.root, args.project_id)
            corpus = ProjectCorpus(workspace, load_selection(args.manifest) if args.manifest else None)
            state = ProjectState(workspace, args.state_dir)
            value = asyncio.run(demo(workspace, corpus, state, question=args.question,
                                   operation=args.git_operation, mode=args.operation))
            value["version"] = __version__
            emit(value)
            return 0 if value["status"] == "completed" else 2
        elif args.command == "git":
            if args.operation != "diff" and (args.path or args.include_content or args.scope != "unstaged"):
                raise DeveloperError(ErrorCode.INVALID_INPUT)
            arguments = {"scope": args.scope, "paths": args.path, "include_content": args.include_content} if args.operation == "diff" else {}
            emit(asyncio.run(git_request(args.root, args.project_id, args.operation, arguments)))
        elif args.command in {"help", "/help", "ask"}:
            result = asyncio.run(pipeline_request(args, " ".join(args.question)))
            emit(result)
            return 0 if result["execution_status"] == "completed" else 2
        elif args.command == "console":
            from .routing import ProjectSession
            session = ProjectSession(args.project_id)
            print(help_text)
            while True:
                try:
                    question = input("bublik> ").strip()
                except EOFError:
                    break
                if question in {"/exit", "/quit"}:
                    break
                if question == "/help":
                    print(help_text)
                    continue
                try:
                    emit(asyncio.run(pipeline_request(args, question.removeprefix("/help "), session=session)))
                except DeveloperError as error:
                    emit({"status": "failed", "error": error.to_dict()})
    except DoctorFailure as error:
        emit({"status": "failed", "error": error.to_dict(), "probes": error.checks})
        return 2
    except DeveloperError as error:
        emit({"status": "failed", "error": error.to_dict()})
        return 2
    except ImportError:
        emit({"status": "failed", "error": {"code": "dependencies_missing", "detail": "Install day31 requirements.txt"}})
        return 2
    except (OSError, ExceptionGroup):
        # SDK task group errors may contain private tool bodies; keep them internal.
        emit({"status": "failed", "error": {"code": "mcp_unavailable", "detail": None}})
        return 2
    except KeyboardInterrupt:
        return 130
    return 0
