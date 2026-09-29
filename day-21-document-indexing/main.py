"""Build and explore one knowledge base for the retrieval lessons of this week."""

import argparse
import json
from pathlib import Path

from agent import BublikKnowledgeAgent
from chunking import chunk_documents
from corpus import ROOT, corpus_stats, load_documents, revision
from embeddings import Ollama
from evaluation import answer_review, evaluate_retrieval, load_questions
from retrieval import retrieve
from storage import KnowledgeBase


DEFAULT_DB = Path(__file__).with_name("knowledge.db")


def main():
    parser = argparse.ArgumentParser(description="Day 21 local knowledge index")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--model", default="bge-m3", help="Ollama embedding model")
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--answer-model", default="llama3.2")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("corpus")
    build = commands.add_parser("build")
    build.add_argument("--limit", type=int, default=500)
    build.add_argument("--overlap", type=int, default=75)
    build.add_argument("--batch", type=int, default=16)
    commands.add_parser("inspect")
    commands.add_parser("verify")
    for name in ("search", "ask"):
        cmd = commands.add_parser(name)
        cmd.add_argument("question")
        cmd.add_argument("--strategy", choices=("fixed", "structural"), default="structural")
        cmd.add_argument("--top-k", type=int, default=5)
        cmd.add_argument("--rerank-model", help="Optional local Sentence Transformers cross-encoder")
    compare = commands.add_parser("compare")
    compare.add_argument("--questions", type=Path, default=None)
    compare.add_argument("--top-k", type=int, default=5)
    compare.add_argument("--rerank-model")
    review = commands.add_parser("review")
    review.add_argument("--number", type=int, default=1, help="1-based gold question number")
    review.add_argument("--strategy", choices=("fixed", "structural"), default="structural")
    review.add_argument("--rerank-model")
    args = parser.parse_args()
    documents = load_documents(ROOT) if args.command in ("corpus", "build") else []
    if args.command == "corpus":
        print(json.dumps({"revision": revision(ROOT), **corpus_stats(documents),
                          "sources": [d.source for d in documents]}, indent=2))
        return
    provider = Ollama(args.url, args.model, args.answer_model)
    kb = KnowledgeBase(args.db)
    try:
        if args.command == "build":
            if args.batch <= 0 or args.overlap < 0 or args.limit <= args.overlap:
                parser.error("Require batch > 0 and 0 <= overlap < limit")
            stats = corpus_stats(documents)
            if stats["estimated_text_pages"] + stats["estimated_code_pages"] < 20:
                parser.error("Corpus is smaller than the required 20 page equivalent")
            for strategy in ("fixed", "structural"):
                chunks = chunk_documents(documents, strategy, args.limit, args.overlap)
                vectors = []
                for start in range(0, len(chunks), args.batch):
                    batch = chunks[start:start + args.batch]
                    vectors.extend(provider.embed([c.text for c in batch]))
                    print(f"{strategy}: embedded {len(vectors)}/{len(chunks)}")
                kb.save(documents, strategy, chunks, vectors, args.model,
                        args.limit, args.overlap, revision(ROOT))
            print(json.dumps({"corpus": stats, "indexes": kb.stats()}, indent=2))
        elif args.command == "inspect":
            print(json.dumps(kb.stats(), indent=2))
        elif args.command == "verify":
            results = kb.validate()
            current = revision(ROOT)
            if any(item["revision"] != current for item in results):
                raise RuntimeError("Index corpus differs from current source files; rebuild")
            print(json.dumps(results, indent=2))
        elif args.command in ("search", "ask"):
            agent = BublikKnowledgeAgent(kb, provider, args.strategy,
                                         args.top_k, args.rerank_model)
            response = agent.ask(args.question) if args.command == "ask" else None
            hits = list(response.sources) if response else retrieve(
                kb, provider, args.strategy, args.question, args.top_k, args.rerank_model)
            for i, hit in enumerate(hits, 1):
                print(f"{i}. cosine={hit.score:.4f} display_01={hit.score_01:.4f} "
                      f"{hit.source}:{hit.start_line}-{hit.end_line} "
                      f"[{hit.section}]\n{hit.text[:300]}\n")
            if args.command == "ask":
                print("Answer:\n" + response.answer)
        elif args.command == "compare":
            questions = load_questions(args.questions) if args.questions else load_questions()
            if kb.info("fixed")["model"] != kb.info("structural")["model"] or \
               kb.info("fixed")["revision"] != kb.info("structural")["revision"]:
                raise ValueError("Both strategies must use the same embedding model and corpus revision")
            for strategy in ("fixed", "structural"):
                result = evaluate_retrieval(kb, provider, strategy, questions,
                                            args.top_k, args.rerank_model)
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "review":
            questions = load_questions()
            if not 1 <= args.number <= len(questions):
                parser.error("Question number is outside the gold question set")
            print(json.dumps(answer_review(kb, provider, args.strategy,
                  questions[args.number - 1], args.rerank_model),
                  ensure_ascii=False, indent=2))
    finally:
        kb.close()


if __name__ == "__main__":
    main()
