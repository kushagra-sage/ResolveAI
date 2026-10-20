import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from resolveai.dependencies import RequestContext, get_request_context
from resolveai.models import KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion
from resolveai.rag import ingest_document, retrieve
from resolveai.rbac import AuthorizationError, require_permission
from resolveai.schemas import (
    CitationResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)

router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


class KnowledgeStatusUpdate(BaseModel):
    status: Literal["active", "archived"]


def _authorize(context: RequestContext, permission: str) -> None:
    try:
        require_permission(context.principal, permission)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc


@router.get("/documents")
def list_knowledge_documents(context: RequestContextDependency) -> dict[str, object]:
    _authorize(context, "knowledge:read")
    documents = context.session.scalars(
        select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc())
    ).all()
    items: list[dict[str, object]] = []
    for document in documents:
        versions = context.session.scalars(
            select(KnowledgeDocumentVersion)
            .where(KnowledgeDocumentVersion.document_id == document.id)
            .order_by(KnowledgeDocumentVersion.version_number.desc())
        ).all()
        items.append(
            {
                "id": str(document.id),
                "source_uri": document.source_uri,
                "title": document.title,
                "document_type": document.document_type,
                "policy_category": document.policy_category,
                "audience": document.audience,
                "status": document.status,
                "current_version_id": (
                    str(document.current_version_id) if document.current_version_id else None
                ),
                "chunk_count": context.session.scalar(
                    select(func.count(KnowledgeChunk.id)).where(
                        KnowledgeChunk.document_id == document.id
                    )
                )
                or 0,
                "updated_at": document.updated_at.isoformat(),
                "versions": [
                    {
                        "id": str(version.id),
                        "version_number": version.version_number,
                        "checksum": version.checksum_sha256,
                        "ingestion_status": version.ingestion_status,
                        "mime_type": version.mime_type,
                        "metadata": version.metadata_json,
                        "created_at": version.created_at.isoformat(),
                    }
                    for version in versions
                ],
            }
        )
    return {"items": items, "total": len(items)}


@router.patch("/documents/{document_id}/status")
def update_knowledge_document_status(
    document_id: uuid.UUID,
    payload: KnowledgeStatusUpdate,
    context: RequestContextDependency,
) -> dict[str, object]:
    _authorize(context, "knowledge:write")
    document = context.session.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    document.status = payload.status
    context.session.commit()
    return {"id": str(document.id), "status": document.status}


@router.post("/documents", response_model=KnowledgeIngestResponse)
def ingest_knowledge_document(
    payload: KnowledgeIngestRequest,
    request: Request,
    context: RequestContextDependency,
) -> KnowledgeIngestResponse:
    _authorize(context, "knowledge:write")
    try:
        result = ingest_document(
            context.session,
            request.app.state.embedding_provider,
            tenant_id=context.principal.tenant_id,
            source_uri=payload.source_uri,
            title=payload.title,
            content=payload.content,
            document_type=payload.document_type,
            audience=payload.audience,
            policy_category=payload.policy_category,
            rag_version_name=payload.rag_version,
            metadata=payload.metadata,
        )
        context.session.commit()
    except ValueError as exc:
        context.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return KnowledgeIngestResponse(
        document_id=result.document_id,
        document_version_id=result.document_version_id,
        version_number=result.version_number,
        chunk_count=result.chunk_count,
        created=result.created,
    )


@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    payload: KnowledgeSearchRequest,
    request: Request,
    context: RequestContextDependency,
) -> KnowledgeSearchResponse:
    _authorize(context, "knowledge:read")
    try:
        result = retrieve(
            context.session,
            request.app.state.embedding_provider,
            tenant_id=context.principal.tenant_id,
            query=payload.query,
            top_k=payload.top_k,
            audience=payload.audience,
            rag_version_name=payload.rag_version,
        )
        context.session.commit()
    except ValueError as exc:
        context.session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    citations = [
        CitationResponse(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            document_version_id=item.document_version_id,
            title=item.title,
            source_uri=item.source_uri,
            content=item.content,
            heading_path=list(item.heading_path),
            score=item.score,
        )
        for item in result.evidence
    ]
    return KnowledgeSearchResponse(
        rag_version=result.rag_version,
        abstained=not citations,
        failure_category=result.failure_category,
        citations=citations,
    )
