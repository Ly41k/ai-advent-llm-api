"""CLI: four RAG modes, relevance threshold calibration and held-out evaluation."""

import argparse
import json
from pathlib import Path
import sys

from bridge import DAY21, HERE, Ollama, KnowledgeBase
from quality import QUESTIONS, calibrate, evaluate, load_questions, markdown_report, save_json
from rag23 import Day23RAGAgent, MODES, Settings


def main():
    parser = argparse.ArgumentParser(description="Day 23 relevance filtering and query rewrite")
    parser.add_argument("--db", type=Path, default=DAY21 / "knowledge.db")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="bge-m3")
    parser.add_argument("--answer-model", default="llama3.2")
    parser.add_argument("--strategy", choices=("fixed", "structural"), default="structural")
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=5)
    parser.add_argument("--min-similarity", type=float, default=0.35,
                        help="Inclusive RAW cosine threshold; initial value, calibrate on your index")
    parser.add_argument("--rewrite-method", choices=("heuristic", "llm"), default="heuristic")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("search", "ask", "compare"):
        command = commands.add_parser(name)
        command.add_argument("question")
        if name != "compare":
            command.add_argument("--mode", choices=MODES, default="rewrite_filter")
        else:
            command.add_argument("--retrieval-only", action="store_true")
        command.add_argument("--output", type=Path)
    for name in ("evaluate", "calibrate", "questions"):
        command = commands.add_parser(name)
        command.add_argument("--questions", type=Path, default=QUESTIONS)
        if name != "questions":
            command.add_argument("--output", type=Path, default=HERE / f"{name}_results.json")
        if name == "evaluate":
            command.add_argument("--retrieval-only", action="store_true")
            command.add_argument("--split", choices=("evaluation", "calibration", "all"), default="evaluation")
        if name == "calibrate":
            command.add_argument("--thresholds", type=float, nargs="+",
                                 default=[0.15, 0.25, 0.35, 0.45, 0.55, 0.65])
    args = parser.parse_args()
    if args.command == "questions":
        print(json.dumps(load_questions(args.questions), ensure_ascii=False, indent=2))
        return
    try:
        settings = Settings(args.candidate_k, args.final_k, args.min_similarity,
                            args.strategy, args.rewrite_method)
    except ValueError as error:
        parser.error(str(error))
    if not args.db.is_file():
        parser.error(f"Missing Day 21 index: {args.db}. Run day-21-document-indexing/main.py build")
    provider = Ollama(args.url, args.model, args.answer_model)
    kb = KnowledgeBase(args.db)
    try:
        agent = Day23RAGAgent(kb, provider, settings)
        if args.command in ("ask", "search"):
            payload = agent.run(args.question, args.mode, generate=args.command == "ask").to_dict()
        elif args.command == "compare":
            payload = {m: result.to_dict() for m, result in
                       agent.compare(args.question, generate=not args.retrieval_only).items()}
        elif args.command == "calibrate":
            payload = calibrate(agent, load_questions(args.questions), args.thresholds)
        else:
            items = load_questions(args.questions)
            items = [q for q in items if args.split == "all" or q["split"] == args.split]
            if not items:
                parser.error("Selected question split is empty")
            payload = evaluate(agent, items, generate=not args.retrieval_only,
                               progress=lambda msg: print(msg, file=sys.stderr, flush=True))
        if args.output:
            save_json(args.output, payload)
            if args.command == "evaluate":
                args.output.with_suffix(".md").write_text(markdown_report(payload), encoding="utf-8")
            print(f"Saved: {args.output}", file=sys.stderr)
        print(json.dumps(payload if args.command not in ("evaluate", "calibrate") else
                         {k: v for k, v in payload.items() if k not in ("details", "sweep")},
                         ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, RuntimeError) as error:
        parser.exit(2, f"Error: {error}\n")
    finally:
        kb.close()


if __name__ == "__main__":
    main()
