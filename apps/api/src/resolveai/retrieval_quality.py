import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedItem:
    item_id: str
    score: float


def rewrite_query(query: str) -> str:
    """Normalize conversational requests into a stable lexical/dense search query."""
    normalized = re.sub(r"[^\w\s-]", " ", query.lower())
    stop_words = {
        "a",
        "an",
        "can",
        "could",
        "i",
        "me",
        "please",
        "tell",
        "the",
        "you",
    }
    tokens = [token for token in normalized.split() if token not in stop_words]
    aliases = {"eta": "delivery estimate", "rma": "return merchandise authorization"}
    return " ".join(aliases.get(token, token) for token in tokens) or normalized.strip()


def rerank_score(query: str, content: str, title: str, fused_score: float) -> float:
    """Deterministic local reranker used when no paid cross-encoder is configured."""
    content_overlap = lexical_score(query, content)
    title_overlap = lexical_score(query, title)
    return 0.55 * content_overlap + 0.25 * title_overlap + 0.20 * fused_score


def reciprocal_rank_fusion(
    ranked_lists: list[list[RankedItem]], *, k: int = 60
) -> list[RankedItem]:
    if k <= 0:
        raise ValueError("k must be positive")
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            scores[item.item_id] = scores.get(item.item_id, 0.0) + 1.0 / (k + rank)
    return [
        RankedItem(item_id, score)
        for item_id, score in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def lexical_score(query: str, content: str) -> float:
    query_tokens = {token.lower() for token in query.split() if token.strip()}
    content_tokens = {token.lower().strip(".,:;!?()[]") for token in content.split()}
    if not query_tokens:
        return 0.0
    return len(query_tokens & content_tokens) / len(query_tokens)


def classify_retrieval_failure(
    *,
    result_count: int,
    top_score: float | None,
    minimum_score: float,
    reranker_score: float | None = None,
    minimum_reranker_score: float | None = None,
    has_conflict: bool = False,
    stale_policy: bool = False,
    expected_category_found: bool = True,
    dense_top_id: str | None = None,
    keyword_top_id: str | None = None,
    timed_out: bool = False,
    embedding_failed: bool = False,
    vector_db_failed: bool = False,
    citation_supported: bool = True,
) -> str | None:
    checks = (
        (embedding_failed, "EMBEDDING_FAILURE"),
        (vector_db_failed, "VECTOR_DB_FAILURE"),
        (timed_out, "RETRIEVAL_TIMEOUT"),
        (result_count == 0, "ZERO_RESULTS"),
        (top_score is not None and top_score < minimum_score, "LOW_RELEVANCE"),
        (
            minimum_reranker_score is not None
            and reranker_score is not None
            and reranker_score < minimum_reranker_score,
            "LOW_RERANKER_SCORE",
        ),
        (has_conflict, "CONFLICTING_DOCUMENTS"),
        (stale_policy, "STALE_POLICY_VERSION"),
        (not expected_category_found, "MISSING_EXPECTED_POLICY_CATEGORY"),
        (
            dense_top_id is not None
            and keyword_top_id is not None
            and dense_top_id != keyword_top_id,
            "DENSE_KEYWORD_DISAGREEMENT",
        ),
        (not citation_supported, "CITATION_NOT_SUPPORTED"),
    )
    for condition, category in checks:
        if condition:
            return category
    return None
