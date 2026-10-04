"""CLI for grounded answers and the 10-question assignment evaluation."""

import argparse
import json
from pathlib import Path
import sys

from support24 import DAY21, HERE, KnowledgeBase, Settings
from grounded_agent import Day24RAGAgent, StructuredOllama
from strict_agent import StrictRAGAgent
from evaluate24 import QUESTIONS, evaluate, load_questions, save_report


def main():
    parser = argparse.ArgumentParser(description="Day 24: validated citations, quotes and abstention")
    parser.add_argument("--db", type=Path, default=DAY21 / "knowledge.db")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="bge-m3")
    parser.add_argument("--answer-model", default="qwen2.5:14b")
    parser.add_argument("--verifier-model", help="Optional second Ollama model; default: answer model")
    parser.add_argument("--answer-style", choices=("extractive", "paraphrase"), default="extractive",
                        help="Default: exact source passages; paraphrase is the historical v9 mode")
    parser.add_argument("--coverage-policy", choices=("strict", "diagnostic"), default="strict",
                        help="Extractive only: strict gates publication; diagnostic publishes exact source passages for manual review and preserves negative coverage judgments")
    parser.add_argument("--num-ctx", type=int, default=16384)
    parser.add_argument("--num-predict", type=int, default=2500)
    parser.add_argument("--timeout", type=int, default=600, help="HTTP timeout in seconds for local Ollama")
    parser.add_argument("--strategy", choices=("fixed", "structural"), default="fixed")
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--final-k", type=int, default=5)
    parser.add_argument("--min-similarity", type=float, default=0.50,
                        help="Inclusive raw cosine; reuse Day 23 calibration for your exact index")
    parser.add_argument("--rewrite-method", choices=("heuristic", "llm"), default="heuristic")
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--output", type=Path)
    check = commands.add_parser("evaluate")
    check.add_argument("--questions", type=Path, default=QUESTIONS)
    check.add_argument("--output", type=Path, default=HERE / "reports/check/evaluate.json")
    commands.add_parser("questions")
    args = parser.parse_args()
    if args.command == "questions":
        print(json.dumps(load_questions(), ensure_ascii=False, indent=2))
        return
    try:
        settings = Settings(args.candidate_k, args.final_k, args.min_similarity,
                            args.strategy, args.rewrite_method)
        if not args.db.is_file():
            parser.error(f"Missing Day 21 index: {args.db}; run Day 21 build first")
        options = dict(num_ctx=args.num_ctx, num_predict=args.num_predict, timeout=args.timeout)
        provider = StructuredOllama(args.url, args.model, args.answer_model, **options)
        verifier = (StructuredOllama(args.url, args.model, args.verifier_model, **options)
                    if args.verifier_model else provider)
        kb = KnowledgeBase(args.db)
        try:
            agent_type = StrictRAGAgent if args.answer_style == "extractive" else Day24RAGAgent
            agent_options = ({"coverage_policy": args.coverage_policy}
                             if args.answer_style == "extractive" else {})
            if args.answer_style == "paraphrase" and args.coverage_policy != "strict":
                raise ValueError("diagnostic coverage requires extractive answer style")
            agent = agent_type(kb, provider, settings, verifier, **agent_options,
                                 progress=lambda message: print(message, file=sys.stderr, flush=True))
            if args.command == "ask":
                payload = agent.ask(args.question).to_dict()
                if args.output:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2,
                                                      allow_nan=False) + "\n", encoding="utf-8")
                print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))
            else:
                report = evaluate(agent, load_questions(args.questions),
                                  progress=lambda message: print(message, file=sys.stderr, flush=True))
                save_report(args.output, report)
                print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
                print(f"Saved: {args.output} and {args.output.with_suffix('.md')}", file=sys.stderr)
                if not report["summary"]["all_contract_checks_pass"]:
                    parser.exit(1, "Some questions did not pass; inspect the saved report.\n")
        finally:
            kb.close()
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()
