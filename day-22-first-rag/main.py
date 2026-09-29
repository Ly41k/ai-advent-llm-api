"""CLI for Day 22: first RAG request and A/B comparison."""

import argparse
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DAY21_DIR = ROOT / "day-21-document-indexing"
if str(DAY21_DIR) not in sys.path:
    sys.path.append(str(DAY21_DIR))

try:
    from embeddings import Ollama
    from storage import KnowledgeBase
except ImportError as error:
    raise SystemExit(
        "Day 21 modules are missing. Extract day-22-first-rag into the "
        "ai-advent-llm-api repository root."
    ) from error

from evaluation import evaluate_questions, load_questions
from rag_agent import Day22RAGAgent


DEFAULT_DB = DAY21_DIR / "knowledge.db"
DEFAULT_REPORT = HERE / "evaluation_results.json"


def _print(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Day 22 first RAG request")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help="Day 21 SQLite index")
    parser.add_argument("--model", default="bge-m3", help="Ollama embedding model")
    parser.add_argument("--answer-model", default="llama3.2",
                        help="The SAME generation model is used in both modes")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--strategy", choices=("fixed", "structural"),
                        default="structural")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--rerank-model", default=None)

    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="Run one mode")
    ask.add_argument("question")
    ask.add_argument("--mode", choices=("rag", "no-rag"), default="rag")

    compare = commands.add_parser("compare", help="Run the same question in both modes")
    compare.add_argument("question")

    evaluate = commands.add_parser("evaluate", help="Run all 10 control questions")
    evaluate.add_argument("--questions", type=Path, default=HERE / "questions.json")
    evaluate.add_argument("--output", type=Path, default=DEFAULT_REPORT)

    commands.add_parser("questions", help="Print the 10 control questions")
    args = parser.parse_args()

    if args.command == "questions":
        _print(load_questions())
        return

    if args.top_k <= 0:
        parser.error("--top-k must be positive")
    if not args.db.is_file():
        parser.error(
            f"Day 21 index not found: {args.db}. "
            "Run: python day-21-document-indexing/main.py build"
        )

    provider = Ollama(args.url, args.model, args.answer_model)
    kb = KnowledgeBase(args.db)
    try:
        # Fail early if the selected strategy was not built. retrieve() also verifies
        # that the query embedding model matches the model stored in the index.
        kb.info(args.strategy)
        agent = Day22RAGAgent(
            kb,
            provider,
            strategy=args.strategy,
            top_k=args.top_k,
            rerank_model=args.rerank_model,
        )
        if args.command == "ask":
            _print(agent.answer(args.question, args.mode).to_dict())
        elif args.command == "compare":
            _print(agent.compare(args.question).to_dict())
        elif args.command == "evaluate":
            questions = load_questions(args.questions)
            report = evaluate_questions(agent, questions)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            _print(report)
            print(f"\nSaved report: {args.output}")
    finally:
        kb.close()


if __name__ == "__main__":
    main()
