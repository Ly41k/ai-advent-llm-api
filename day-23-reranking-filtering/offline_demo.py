"""Reproducible retrieval-only exercise on the REAL corpus, without Ollama.

This local lexical TF-IDF model is NOT bge-m3 and is NOT a semantic quality test.
Its threshold cannot be transferred to a different embedding model.
"""

from collections import Counter
import hashlib
import math
from pathlib import Path
import re
import tempfile

from bridge import HERE, ROOT, KnowledgeBase, normalize
from chunking import chunk_documents
from corpus import load_documents, revision
from quality import calibrate, evaluate, load_questions, markdown_report, save_json
from rag23 import Day23RAGAgent, Settings


def tokens(text):
    return re.findall(r"[a-zа-яё0-9_]+", text.casefold())


class LexicalDemoProvider:
    model = "offline-lexical-tfidf-hash-1024-v1"
    answer_model = None

    def __init__(self, texts):
        counts = Counter(term for text in texts for term in set(tokens(text)))
        self.idf = {term: math.log((1 + len(texts)) / (1 + count)) + 1
                    for term, count in counts.items()}

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 1024
            for term, count in Counter(tokens(text)).items():
                digest = hashlib.sha256(term.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % 1024
                sign = 1 if digest[4] % 2 else -1
                vector[index] += sign * (1 + math.log(count)) * self.idf.get(term, 1.0)
            vectors.append(normalize(vector))
        return vectors

    def answer(self, prompt):
        raise RuntimeError("Offline demo does not generate or imitate LLM answers")


def main(output_dir=HERE / "reports"):
    documents = load_documents(ROOT)
    chunks = chunk_documents(documents, "structural")
    provider = LexicalDemoProvider([c.text for c in chunks])
    questions = load_questions()
    with tempfile.TemporaryDirectory() as directory:
        kb = KnowledgeBase(Path(directory) / "lexical_demo.db")
        try:
            kb.save(documents, "structural", chunks, provider.embed([c.text for c in chunks]),
                    provider.model, 500, 75, revision(ROOT))
            agent = Day23RAGAgent(kb, provider)
            calibration = calibrate(agent, questions, [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5])
            agent = Day23RAGAgent(kb, provider,
                                 Settings(min_similarity=calibration["selected_threshold"]))
            report = evaluate(agent, [q for q in questions if q["split"] == "evaluation"],
                              generate=False, progress=print)
            report["run_type"] = "offline lexical retrieval only; real source files; no LLM"
            report["limitations"].insert(0, "Offline lexical scores and threshold do NOT measure bge-m3/llama3.2 quality.")
            save_json(Path(output_dir) / "offline_calibration.json", calibration)
            save_json(Path(output_dir) / "offline_comparison.json", report)
            (Path(output_dir) / "offline_comparison.md").write_text(markdown_report(report), encoding="utf-8")
            print(markdown_report(report))
        finally:
            kb.close()


if __name__ == "__main__":
    main()
