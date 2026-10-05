"""Lesson namespace retrieval with transparent metadata query expansion.

No history answer, task-memory fact, canned answer or synthetic similarity is
added to evidence. Both branches use fresh query embeddings and the unchanged
Day 23 cosine gate; Day 24 still verifies the selected answer against sources.
"""
import re

from support25 import Day23RAGAgent
from conversation import LESSON_PATTERN
from query_rewrite import rewrite_query


def source_lesson(source):
    match = re.match(r"^day-0*(\d+)-[^/]+/", source)
    return match.group(1) if match else None


class LessonIndex:
    def __init__(self, kb, lesson, strategy):
        self.kb, self.lesson = kb, lesson
        # Enumerate only indexed metadata. Never read a newer filesystem source.
        rows = kb.db.execute("SELECT source,count(*) AS n FROM chunks WHERE strategy=? "
                             "GROUP BY source", (strategy,)).fetchall()
        self.count = sum(row["n"] for row in rows)
        self.sources = [row["source"] for row in rows if source_lesson(row["source"]) == lesson]

    def __getattr__(self, name):
        return getattr(self.kb, name)

    def search(self, strategy, vector, top_k):
        # Namespace restriction BEFORE candidate/final limits, with raw scores.
        hits = self.kb.search(strategy, vector, self.count)
        return [hit for hit in hits if hit.source in self.sources][:top_k]

    def overview_query(self, question):
        headings = []
        for source in sorted(self.sources, key=lambda s: (not s.endswith("README.ru.md"), s)):
            if not source.endswith(".md"):
                continue
            row = self.kb.db.execute("SELECT text FROM documents WHERE source=?", (source,)).fetchone()
            if row:
                heading = next((line.strip('# ').strip() for line in row["text"].splitlines()
                                if line.startswith("# ")), "")
                if heading:
                    headings.append(heading[:200])
            if len(headings) == 2:
                break
        if not headings:
            return None
        # Titles describe the user-selected namespace, not an expected answer.
        return question + "\nIndexed document titles: " + " | ".join(headings)


class ScopedResult:
    def __init__(self, result, trace):
        self.result, self.trace = result, trace

    def __getattr__(self, name):
        return getattr(self.result, name)

    def to_dict(self):
        return {**self.result.to_dict(), "lesson_retrieval": self.trace}


class LessonRetriever(Day23RAGAgent):
    def run(self, question, mode="rewrite_filter", generate=True):
        lessons = set(re.findall(LESSON_PATTERN, question, re.I))
        if len(lessons) != 1 or not hasattr(self.kb, "db"):
            return super().run(question, mode, generate)
        if mode != "rewrite_filter":
            return super().run(question, mode, generate)
        lesson = str(int(next(iter(lessons))))
        index = LessonIndex(self.kb, lesson, self.settings.strategy)
        if not index.sources:
            return super().run(question, mode, generate)
        rewritten = rewrite_query(question, self.settings.rewrite_method, self.provider)
        scoped = Day23RAGAgent(index, self.provider, self.settings)
        queries = [rewritten.query]
        overview = index.overview_query(rewritten.query)
        if overview and overview != rewritten.query:
            queries.append(overview)
        merged, branches = {}, []
        for query in queries:
            candidates = scoped._candidates(query)
            branches.append({"query": query, "candidates": [
                {"chunk_id": h.chunk_id, "source": h.source, "cosine": h.score} for h in candidates]})
            for hit in candidates:
                if hit.chunk_id not in merged or hit.score > merged[hit.chunk_id].score:
                    merged[hit.chunk_id] = hit
        result = self._result(mode, rewritten, list(merged.values()), generate)
        return ScopedResult(result, {"lesson": lesson, "namespace_sources": index.sources,
                                    "policy": "namespace_before_limits; maximum_actual_cosine_across_queries",
                                    "branches": branches})
