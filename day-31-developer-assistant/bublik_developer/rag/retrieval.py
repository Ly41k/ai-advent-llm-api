"""FTS/dense ranking and RRF; raw scores do not claim semantic correctness."""
import math
import re
from time import perf_counter

from ..errors import DeveloperError, ErrorCode
from .index import read_vector, vector_bytes

STOP = frozenset("what which where how does do is are the a an of to and в на как что какой какая какие где это устроена устроен".split())
# Vocabulary expansion adapted from Day 23; never uses golden expected answers.
GLOSSARY = ((r"памят|memory", ("память", "memory", "история", "history")),
            (r"владел|owner", ("owner", "владелец")), (r"ветк|branch", ("branch", "ветка")),
            (r"инструмент|tool|mcp", ("MCP", "tool", "инструмент")),
            (r"язык|language", ("language", "язык", "ru", "en")),
            (r"схем|schema", ("schema", "схема")), (r"очеред|queue", ("queue", "очередь")),
            (r"эмбеддинг|embedding", ("embedding", "bge-m3")))

POLICY_VERSION = "markdown-body-v1"
DENSE_QUERY_POLICIES = frozenset({"auto", "raw", "vocabulary"})
QUERY_DEFAULTS_VERSION = "mode-query-defaults-v1"
ENDPOINT_POLICY_VERSION = "literal-endpoint-heading-v1"


def explicit_endpoints(question):
    """Standalone HTTP-style paths only; preserve case and never resolve URLs.

    Sentence punctuation is excluded. Endpoint matching is a lexical signal,
    not evidence that a section answers the question. No expected answers or
    preferred source paths participate in ranking.
    """
    pattern = r"(?<![\w/])/[A-Za-z0-9_~-]+(?:/[A-Za-z0-9_.~-]*[A-Za-z0-9_~-])*(?![\w/])"
    return list(dict.fromkeys(re.findall(pattern, question)))


def endpoint_heading_matcher(endpoints):
    patterns = [re.compile(r"(?<![\w/.-])" + re.escape(path) + r"(?![\w/.-])") for path in endpoints]
    return lambda heading: sum(bool(pattern.search(heading)) for pattern in patterns)


def resolve_dense_query(mode, policy):
    """Fixed per-mode defaults selected on calibration, not runtime labels."""
    if mode not in {"fts", "dense", "hybrid"} or not isinstance(policy, str) or policy not in DENSE_QUERY_POLICIES:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    return ("vocabulary" if mode == "dense" else "raw") if policy == "auto" else policy


def has_body(text, kind):
    """Reject Markdown ATX headings alone, without claiming semantic relevance.

    Code fences and schema text remain eligible. Stored chunks and their exact
    spans are unchanged; this predicate only controls retrieval candidates.
    """
    if kind != "markdown":
        return True
    return any(line.strip() and not re.fullmatch(r"[ ]{0,3}#{1,6}\s+.*", line)
               for line in text.splitlines())


def query_terms(question):
    if not isinstance(question, str) or not question.strip() or len(question.encode()) > 2048:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    words = re.findall(r"[^\W]+", question.casefold(), re.UNICODE)
    words += [word.casefold() for pattern, additions in GLOSSARY if re.search(pattern, question, re.I) for word in additions]
    selected = []
    for word in words:
        if 2 <= len(word) <= 64 and word not in STOP and word not in selected:
            selected.append(word)
        if len(selected) == 24:
            break
    return selected


def fts_query(terms):
    # MATCH operators never come from the user. Quoted literal tokens only.
    return " OR ".join('"' + word.replace('"', '""') + '"' + ("*" if re.fullmatch(r"[а-яё]{6,}", word) else "") for word in terms)


def dense_query_text(question, terms, policy):
    """Keep the semantic question intact; legacy expansion is explicit.

    FTS vocabulary is designed for literal OR matching, not for embeddings.
    Preserve the old query to allow a paired comparison on the same vectors.
    """
    if not isinstance(policy, str) or policy not in {"raw", "vocabulary"}:
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    return question if policy == "raw" else question + "\nSearch vocabulary: " + " ".join(terms)


def fuse(fts, dense, k=60):
    scores, ranks = {}, {}
    for name, rows in (("fts", fts), ("dense", dense)):
        for rank, row in enumerate(rows, 1):
            chunk_id = row["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank)
            ranks.setdefault(chunk_id, {})[name] = rank
    return [{"chunk_id": key, "rrf": score, "ranks": ranks[key]} for key, score in
            sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def search(index, question, *, mode="fts", provider=None, candidate_k=20, final_k=5,
           min_cosine=.5, sources=None, context_bytes=16000, dense_query="auto", diagnostics=False):
    started = perf_counter()
    if (mode not in {"fts", "dense", "hybrid"} or type(candidate_k) is not int or type(final_k) is not int
            or not 1 <= final_k <= candidate_k <= 100 or type(context_bytes) is not int or not 1024 <= context_bytes <= 32000
            or type(min_cosine) not in (int, float) or not math.isfinite(min_cosine) or not -1 <= min_cosine <= 1
            or not isinstance(dense_query, str) or dense_query not in DENSE_QUERY_POLICIES or type(diagnostics) is not bool):
        raise DeveloperError(ErrorCode.INVALID_INPUT)
    effective_query = resolve_dense_query(mode, dense_query)
    snapshot = index.fresh()
    available = {doc.source for doc in snapshot.documents}
    if sources is not None and (not isinstance(sources, list) or not sources or any(source not in available for source in sources)):
        raise DeveloperError(ErrorCode.PERMISSION_DENIED, "path")
    terms = query_terms(question)
    endpoints = explicit_endpoints(question)
    condition, params = ("", []) if sources is None else (" AND c.source IN (" + ",".join("?" for _ in sources) + ")", sources)
    # Connection-local predicate: no index/schema/vector mutation. Apply in
    # WHERE before LIMIT, so headings cannot consume the candidate budget.
    index.db.create_function("day31_has_body", 2, has_body, deterministic=True)
    documents_join = " JOIN documents d ON d.source=c.source "
    excluded = index.db.execute("SELECT count(*) FROM chunks c" + documents_join
        + "WHERE NOT day31_has_body(c.text,d.kind)" + condition, params).fetchone()[0]
    body_condition = " AND day31_has_body(c.text,d.kind)"
    fts, dense, vector = [], [], None
    embedding_seconds = 0
    dense_diagnostics = None
    if mode in {"fts", "hybrid"} and terms:
        # Promote explicit endpoint headings before candidate LIMIT. Matching
        # remains inside the permitted namespace and the body filter. Other
        # queries retain their original BM25 order; dense scores are untouched.
        endpoint_column, ordering = "", "bm25,c.chunk_id"
        if endpoints:
            index.db.create_function("day31_endpoint_heading",1,endpoint_heading_matcher(endpoints),deterministic=True)
            endpoint_column = ",day31_endpoint_heading(c.section) AS endpoint_heading_matches"
            ordering = "endpoint_heading_matches DESC,bm25,c.chunk_id"
        sql = ("SELECT c.chunk_id,bm25(search,0,2,3,1) AS bm25" + endpoint_column
               + " FROM search JOIN chunks c ON c.chunk_id=search.chunk_id"
               + documents_join + "WHERE search MATCH ?" + body_condition + condition + " ORDER BY " + ordering + " LIMIT ?")
        fts = [dict(row) for row in index.db.execute(sql, [fts_query(terms), *params, candidate_k])]
    if mode in {"dense", "hybrid"}:
        profile = index.metadata.get("embedding")
        if profile is None or provider is None or provider.identity() != profile:
            raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
        embedding_started = perf_counter()
        values = provider.embed([dense_query_text(question, terms, effective_query)], final=True)
        if len(values) != 1:
            raise DeveloperError(ErrorCode.INVALID_TOOL_OUTPUT)
        vector_bytes(values[0], profile["dimension"])
        vector = values[0]
        embedding_seconds = perf_counter() - embedding_started
        if provider.identity() != profile:
            raise DeveloperError(ErrorCode.EMBEDDING_UNAVAILABLE)
        sql = "SELECT c.chunk_id,c.vector FROM chunks c" + documents_join + "WHERE 1=1" + body_condition + condition
        ranked = []
        for row in index.db.execute(sql, params):
            score = sum(a * b for a, b in zip(vector, read_vector(row["vector"], profile["dimension"])))
            ranked.append({"chunk_id": row["chunk_id"], "cosine": score})
        all_dense = sorted(ranked, key=lambda row: (-row["cosine"], row["chunk_id"]))
        dense = [row for row in all_dense if row["cosine"] >= min_cosine][:candidate_k]
        if diagnostics:
            # Scores below the cutoff are diagnostic data, never admitted evidence.
            candidate_ids = {row["chunk_id"] for row in dense}
            dense_diagnostics = {"scope": "eligible_body_chunks_before_cosine_threshold",
                "limit": 100, "scored_chunks": len(all_dense), "truncated": len(all_dense) > 100,
                "rows": [{**row, "rank": rank, "above_threshold": row["cosine"] >= min_cosine,
                          "in_candidates": row["chunk_id"] in candidate_ids}
                         for rank, row in enumerate(all_dense[:100], 1)]}
    ranked = fuse(fts, dense) if mode == "hybrid" else (fts if mode == "fts" else dense)
    evidence, decisions, used = [], [], 0
    for row in ranked:
        hit = index.evidence(row["chunk_id"])
        size = len(hit["quote"].encode())
        selected = len(evidence) < final_k and used + size <= context_bytes
        decisions.append({**row, "decision": "selected" if selected else "context_or_final_k_limit"})
        if selected:
            evidence.append({**hit, "ranking": row})
            used += size
    if index.fresh().revision != snapshot.revision:
        raise DeveloperError(ErrorCode.INDEX_STALE)
    return {"status": "retrieved" if evidence else "no_evidence", "question": question, "mode": mode,
            "terms": terms, "settings": {"candidate_k": candidate_k, "final_k": final_k,
                "min_cosine": min_cosine, "context_bytes": context_bytes, "rrf_k": 60 if mode == "hybrid" else None,
                "retrieval_policy": POLICY_VERSION,
                "fts_endpoint_policy": ENDPOINT_POLICY_VERSION if mode in {"fts","hybrid"} else None,
                "explicit_endpoints": endpoints,
                "dense_query_policy": effective_query if mode != "fts" else None,
                "requested_dense_query": dense_query if mode != "fts" else None,
                "query_defaults_version": QUERY_DEFAULTS_VERSION},
            "content_filter": {"policy": POLICY_VERSION, "excluded_heading_only": excluded,
                               "scope": "selected_source_namespace"},
            "sources": evidence, "decisions": decisions, "candidate_counts": {"fts": len(fts), "dense": len(dense)},
            "dense_diagnostics": dense_diagnostics,
            "index_version": index.metadata["index_version"], "corpus_revision": snapshot.revision,
            "metrics": {"total_seconds": perf_counter() - started, "embedding_seconds": embedding_seconds,
                        "context_bytes": used, "answer_model_calls": 0},
            "semantic_support_verified": False, "note": "Retrieved source excerpts; no generated answer or claim verification."}
