"""Two-stage retrieval and a context-limited local answer."""

from functools import lru_cache

from storage import Hit, KnowledgeBase


@lru_cache(maxsize=2)
def _cross_encoder(model_name: str):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(model_name)


def retrieve(kb: KnowledgeBase, provider, strategy: str, question: str,
             top_k: int = 5, rerank_model: str | None = None) -> list[Hit]:
    info = kb.info(strategy)
    if info["model"] != provider.model:
        raise ValueError("Embedding model differs from the model used to build the index")
    query = provider.embed([question])[0]
    candidates = kb.search(strategy, query, max(top_k, 20) if rerank_model else top_k)
    if rerank_model:
        # A cross-encoder scores only the small candidate set, not the whole corpus.
        reranker = _cross_encoder(rerank_model)
        scores = reranker.predict([(question, hit.text) for hit in candidates])
        candidates = [hit for _, hit in sorted(zip(scores, candidates),
                      key=lambda pair: float(pair[0]), reverse=True)]
    return candidates[:top_k]


def context_for(hits: list[Hit]) -> str:
    return "\n\n".join(f"[{i}] {hit.source}:{hit.start_line}-{hit.end_line} "
                       f"({hit.section})\n{hit.text}" for i, hit in enumerate(hits, 1))


def _abstained(answer: str) -> bool:
    value = answer.casefold().strip()
    return any(phrase in value for phrase in (
        "i don't know", "i do not know", "cannot determine", "not enough information",
        "не знаю", "недостаточно информации", "не могу определить"))


def answer_question(provider, question: str, hits: list[Hit]) -> str:
    if not hits:
        return "No relevant context was found."
    prompt = ("You answer questions about this repository by reading the supplied excerpts. "
              "First look for an explicit statement that answers the question. "
              "If one exists, give the specific name or fact in one short sentence "
              "and cite its excerpt number, for example [1]. "
              "Say you do not know only when none of the excerpts contains the answer. "
              "Use no outside knowledge. Answer in the language of the question.\n\n"
              f"Question:\n{question}\n\nExcerpts:\n{context_for(hits)}\n\nAnswer:")
    answer = provider.answer(prompt)
    if not _abstained(answer):
        return answer
    # A small local model may refuse despite a direct answer near the top.
    # Retry once with only the strongest excerpt to reduce distraction.
    focused = ("Read the excerpt and answer the question with the exact name or fact "
               "stated there. Cite [1]. If the excerpt does not state the answer, "
               "reply 'I don't know'. Do not guess.\n\n"
               f"Question: {question}\n\nExcerpt [1]:\n{hits[0].text}\n\nAnswer:")
    return provider.answer(focused)
