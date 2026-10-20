import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from resolveai.chunking import chunk_document
from resolveai.embeddings import EmbeddingProvider, cosine_similarity
from resolveai.models import (
    CostEvent,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    RagVersion,
    RetrievalEvent,
)
from resolveai.observability import (
    RETRIEVAL_FAILURE_TOTAL,
    RETRIEVAL_LATENCY,
    RETRIEVAL_RESULT_COUNT,
)
from resolveai.retrieval_quality import (
    RankedItem,
    classify_retrieval_failure,
    lexical_score,
    reciprocal_rank_fusion,
    rerank_score,
    rewrite_query,
)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_number: int
    chunk_count: int
    created: bool


@dataclass(frozen=True, slots=True)
class RetrievedEvidence:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    title: str
    source_uri: str
    content: str
    heading_path: tuple[str, ...]
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    evidence: tuple[RetrievedEvidence, ...]
    rag_version: str
    failure_category: str | None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_active_rag_version(session: Session, name: str | None = None) -> RagVersion:
    statement = select(RagVersion).where(RagVersion.status == "active")
    if name is not None:
        statement = statement.where(RagVersion.name == name)
    statement = statement.order_by(RagVersion.created_at.desc())
    version = session.scalar(statement)
    if version is None:
        raise ValueError("no active RAG version configured")
    return version


def ingest_document(
    session: Session,
    embedding_provider: EmbeddingProvider,
    *,
    tenant_id: uuid.UUID,
    source_uri: str,
    title: str,
    content: str,
    document_type: str,
    audience: str,
    policy_category: str | None = None,
    rag_version_name: str | None = None,
    metadata: dict[str, object] | None = None,
) -> IngestionResult:
    if not content.strip():
        raise ValueError("document content cannot be empty")
    rag_version = get_active_rag_version(session, rag_version_name)
    if rag_version.embedding_dimensions != embedding_provider.dimensions:
        raise ValueError("embedding provider does not match the RAG version")

    document = session.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.source_uri == source_uri)
    )
    if document is None:
        document = KnowledgeDocument(
            tenant_id=tenant_id,
            source_uri=source_uri,
            title=title,
            document_type=document_type,
            policy_category=policy_category,
            audience=audience,
        )
        session.add(document)
        session.flush()
    checksum = _sha256(content)
    current_version = (
        session.get(KnowledgeDocumentVersion, document.current_version_id)
        if document.current_version_id
        else None
    )
    if current_version is not None and current_version.checksum_sha256 == checksum:
        chunk_count = session.scalar(
            select(func.count(KnowledgeChunk.id)).where(
                KnowledgeChunk.document_version_id == current_version.id,
                KnowledgeChunk.rag_version_id == rag_version.id,
            )
        )
        return IngestionResult(
            document_id=document.id,
            document_version_id=current_version.id,
            version_number=current_version.version_number,
            chunk_count=int(chunk_count or 0),
            created=False,
        )

    maximum_version = session.scalar(
        select(func.max(KnowledgeDocumentVersion.version_number)).where(
            KnowledgeDocumentVersion.document_id == document.id
        )
    )
    version = KnowledgeDocumentVersion(
        tenant_id=tenant_id,
        document_id=document.id,
        version_number=int(maximum_version or 0) + 1,
        checksum_sha256=checksum,
        content=content,
        ingestion_status="indexing",
        metadata_json=metadata or {},
    )
    session.add(version)
    session.flush()

    drafts = chunk_document(
        rag_version.chunker,
        content,
        rag_version.chunk_size,
        rag_version.chunk_overlap,
    )
    if not drafts:
        raise ValueError("chunker produced no content")
    vectors = embedding_provider.embed([draft.content for draft in drafts])
    session.add(
        CostEvent(
            tenant_id=tenant_id,
            provider="local",
            model=embedding_provider.model_name,
            feature="knowledge_ingestion",
            rag_version=rag_version.name,
            endpoint="/v1/knowledge/documents",
            operation_type="embedding",
            quantity=len(drafts),
            unit="embeddings",
            input_tokens=sum(draft.token_count for draft in drafts),
            output_tokens=0,
            cached_tokens=0,
            cost_usd_micros=0,
            pricing_version="local-zero-incremental-v1",
        )
    )
    for ordinal, (draft, vector) in enumerate(zip(drafts, vectors, strict=True)):
        session.add(
            KnowledgeChunk(
                tenant_id=tenant_id,
                document_id=document.id,
                document_version_id=version.id,
                rag_version_id=rag_version.id,
                ordinal=ordinal,
                heading_path=list(draft.heading_path),
                content=draft.content,
                content_sha256=_sha256(draft.content),
                token_count=draft.token_count,
                metadata_json=metadata or {},
                embedding=vector,
            )
        )
    version.ingestion_status = "indexed"
    document.current_version_id = version.id
    session.flush()
    return IngestionResult(
        document_id=document.id,
        document_version_id=version.id,
        version_number=version.version_number,
        chunk_count=len(drafts),
        created=True,
    )


def _current_chunk_query(rag_version: RagVersion, audience: str | None) -> Any:
    now = datetime.now(tz=UTC)
    statement = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(
            KnowledgeDocument,
            (KnowledgeDocument.id == KnowledgeChunk.document_id)
            & (KnowledgeDocument.tenant_id == KnowledgeChunk.tenant_id),
        )
        .join(
            KnowledgeDocumentVersion,
            (KnowledgeDocumentVersion.id == KnowledgeChunk.document_version_id)
            & (KnowledgeDocumentVersion.tenant_id == KnowledgeChunk.tenant_id),
        )
        .where(
            KnowledgeChunk.rag_version_id == rag_version.id,
            KnowledgeDocument.current_version_id == KnowledgeChunk.document_version_id,
            KnowledgeDocument.status == "active",
            (KnowledgeDocumentVersion.effective_from.is_(None))
            | (KnowledgeDocumentVersion.effective_from <= now),
            (KnowledgeDocumentVersion.effective_to.is_(None))
            | (KnowledgeDocumentVersion.effective_to > now),
        )
    )
    if audience is not None:
        statement = statement.where(KnowledgeDocument.audience == audience)
    return statement


def retrieve(
    session: Session,
    embedding_provider: EmbeddingProvider,
    *,
    tenant_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    audience: str | None = None,
    rag_version_name: str | None = None,
) -> RetrievalResult:
    if not query.strip():
        raise ValueError("query cannot be empty")
    if top_k < 1 or top_k > 50:
        raise ValueError("top_k must be between 1 and 50")
    started = time.perf_counter()
    rag_version = get_active_rag_version(session, rag_version_name)
    rewritten_query = rewrite_query(query)
    try:
        query_vector = embedding_provider.embed([rewritten_query])[0]
    except Exception:
        elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))
        session.add(
            RetrievalEvent(
                tenant_id=tenant_id,
                query_sha256=_sha256(query),
                rag_version_id=rag_version.id,
                stage="query_embedding",
                result_count=0,
                latency_ms=elapsed_ms,
                top_scores_json=[],
                failure_category="EMBEDDING_FAILURE",
                details_json={"rewritten_query_sha256": _sha256(rewritten_query)},
            )
        )
        RETRIEVAL_FAILURE_TOTAL.labels("EMBEDDING_FAILURE").inc()
        RETRIEVAL_LATENCY.labels("query_embedding", "failure").observe(elapsed_ms / 1000)
        return RetrievalResult((), rag_version.name, "EMBEDDING_FAILURE")
    session.add(
        CostEvent(
            tenant_id=tenant_id,
            provider="local",
            model=embedding_provider.model_name,
            feature="knowledge_retrieval",
            rag_version=rag_version.name,
            endpoint="/v1/knowledge/search",
            operation_type="embedding",
            quantity=1,
            unit="embedding",
            input_tokens=len(rewritten_query.split()),
            output_tokens=0,
            cached_tokens=0,
            cost_usd_micros=0,
            pricing_version="local-zero-incremental-v1",
        )
    )
    base_query = _current_chunk_query(rag_version, audience)

    dense_ranked: list[tuple[KnowledgeChunk, KnowledgeDocument, float]] = []
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        distance = KnowledgeChunk.embedding.op("<=>")(query_vector)
        pg_rows = session.execute(
            base_query.add_columns(distance.label("distance")).order_by(distance).limit(top_k * 4)
        )
        dense_ranked = [
            (
                cast(KnowledgeChunk, chunk),
                cast(KnowledgeDocument, document),
                1.0 - float(cast(float, value)),
            )
            for chunk, document, value in pg_rows
        ]
    else:
        local_rows = session.execute(base_query).all()
        dense_ranked = sorted(
            (
                (
                    cast(KnowledgeChunk, chunk),
                    cast(KnowledgeDocument, document),
                    cosine_similarity(query_vector, cast(KnowledgeChunk, chunk).embedding),
                )
                for chunk, document in local_rows
            ),
            key=lambda item: item[2],
            reverse=True,
        )[: top_k * 4]

    all_rows = session.execute(base_query).all()
    lexical_ranked = sorted(
        (
            (
                cast(KnowledgeChunk, chunk),
                cast(KnowledgeDocument, document),
                lexical_score(rewritten_query, cast(KnowledgeChunk, chunk).content),
            )
            for chunk, document in all_rows
        ),
        key=lambda item: (-item[2], str(item[0].id)),
    )[: top_k * 4]
    lookup = {
        str(chunk.id): (chunk, document)
        for chunk, document, _score in [*dense_ranked, *lexical_ranked]
    }
    dense_scores = {str(chunk.id): score for chunk, _document, score in dense_ranked}
    lexical_scores = {str(chunk.id): score for chunk, _document, score in lexical_ranked}
    fused = reciprocal_rank_fusion(
        [
            [RankedItem(str(chunk.id), score) for chunk, _document, score in dense_ranked],
            [RankedItem(str(chunk.id), score) for chunk, _document, score in lexical_ranked],
        ]
    )
    reranked = []
    for item in fused[: top_k * 2]:
        chunk, document = lookup[item.item_id]
        fused_relevance = 0.7 * dense_scores.get(item.item_id, 0.0) + 0.3 * lexical_scores.get(
            item.item_id, 0.0
        )
        score = rerank_score(rewritten_query, chunk.content, document.title, fused_relevance)
        reranked.append((chunk, document, score))
    ranked = sorted(reranked, key=lambda item: (-item[2], str(item[0].id)))[:top_k]

    accepted = [item for item in ranked if item[2] >= rag_version.minimum_relevance]
    failure_category = classify_retrieval_failure(
        result_count=len(ranked),
        top_score=ranked[0][2] if ranked else None,
        minimum_score=rag_version.minimum_relevance,
        reranker_score=ranked[0][2] if ranked else None,
        minimum_reranker_score=rag_version.minimum_relevance,
        dense_top_id=str(dense_ranked[0][0].id) if dense_ranked else None,
        keyword_top_id=str(lexical_ranked[0][0].id) if lexical_ranked else None,
    )
    elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))
    event = RetrievalEvent(
        tenant_id=tenant_id,
        query_sha256=_sha256(query),
        rag_version_id=rag_version.id,
        stage="rewrite_hybrid_rerank",
        result_count=len(accepted),
        latency_ms=elapsed_ms,
        top_scores_json=[round(item[2], 6) for item in ranked],
        failure_category=failure_category,
        details_json={
            "top_k": top_k,
            "audience": audience,
            "rewritten_query_sha256": _sha256(rewritten_query),
            "reranker": "deterministic-overlap-v1",
            "dense_top_id": str(dense_ranked[0][0].id) if dense_ranked else None,
            "keyword_top_id": str(lexical_ranked[0][0].id) if lexical_ranked else None,
        },
    )
    session.add(event)
    outcome = "failure" if failure_category else "success"
    RETRIEVAL_LATENCY.labels("rewrite_hybrid_rerank", outcome).observe(elapsed_ms / 1000)
    RETRIEVAL_RESULT_COUNT.labels("rewrite_hybrid_rerank").observe(len(accepted))
    if failure_category:
        RETRIEVAL_FAILURE_TOTAL.labels(failure_category).inc()
    evidence = tuple(
        RetrievedEvidence(
            chunk_id=chunk.id,
            document_id=document.id,
            document_version_id=chunk.document_version_id,
            title=document.title,
            source_uri=document.source_uri,
            content=chunk.content,
            heading_path=tuple(chunk.heading_path),
            score=score,
        )
        for chunk, document, score in accepted
    )
    return RetrievalResult(
        evidence=evidence,
        rag_version=rag_version.name,
        failure_category=failure_category,
    )
