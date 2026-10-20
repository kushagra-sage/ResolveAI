import uuid

from fastapi.testclient import TestClient
from resolveai.chunking import chunk_document
from resolveai.database import create_database_engine, create_session_factory
from resolveai.embeddings import HashEmbeddingProvider
from resolveai.models import KnowledgeChunk, KnowledgeDocumentVersion
from resolveai.rag import ingest_document, retrieve
from resolveai.seed import seed_id
from sqlalchemy import func, select


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _document_payload(content: str) -> dict[str, object]:
    return {
        "source_uri": "kb://shipping/delays",
        "title": "Shipment delay policy",
        "content": content,
        "document_type": "policy",
        "audience": "internal",
        "policy_category": "shipping",
        "metadata": {"owner": "support-operations"},
    }


def test_chunking_strategies_are_deterministic() -> None:
    content = "# Refunds\nRefunds take five days.\n\n## Delays\nEscalate after ten days."
    fixed = chunk_document("fixed_token", content, 4, 1)
    recursive = chunk_document("recursive", content, 8, 1)
    headings = chunk_document("heading_aware", content, 8, 1)

    assert fixed == chunk_document("fixed_token", content, 4, 1)
    assert len(recursive) == 2
    assert headings[0].heading_path == ("Refunds",)
    assert headings[1].heading_path == ("Refunds", "Delays")


def test_admin_ingestion_is_idempotent_and_agent_gets_citations(
    client: TestClient,
    admin_token: str,
    agent_token: str,
) -> None:
    payload = _document_payload(
        "# Shipping delays\nA shipment delayed more than ten days must be escalated."
    )
    first = client.post("/v1/knowledge/documents", json=payload, headers=_headers(admin_token))
    second = client.post("/v1/knowledge/documents", json=payload, headers=_headers(admin_token))

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert first.json()["document_version_id"] == second.json()["document_version_id"]

    response = client.post(
        "/v1/knowledge/search",
        json={"query": "shipment delayed ten days", "audience": "internal"},
        headers=_headers(agent_token),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["abstained"] is False
    assert body["rag_version"] == "rag_v001"
    assert body["citations"][0]["document_version_id"] == first.json()["document_version_id"]
    assert body["citations"][0]["source_uri"] == "kb://shipping/delays"


def test_cost_summary_is_tenant_admin_only(
    client: TestClient,
    admin_token: str,
    agent_token: str,
) -> None:
    payload = _document_payload("# Returns\nReturns require a receipt.")
    assert (
        client.post(
            "/v1/knowledge/documents", json=payload, headers=_headers(admin_token)
        ).status_code
        == 200
    )
    forbidden = client.get("/v1/operations/cost-summary", headers=_headers(agent_token))
    summary = client.get("/v1/operations/cost-summary", headers=_headers(admin_token))
    assert forbidden.status_code == 403
    assert summary.status_code == 200
    assert summary.json()[0]["operation_type"] == "embedding"


def test_changed_content_creates_an_immutable_version(
    client: TestClient,
    admin_token: str,
    database_url: str,
) -> None:
    first = client.post(
        "/v1/knowledge/documents",
        json=_document_payload("# Policy\nEscalate after ten days."),
        headers=_headers(admin_token),
    )
    second = client.post(
        "/v1/knowledge/documents",
        json=_document_payload("# Policy\nEscalate after seven days."),
        headers=_headers(admin_token),
    )
    assert first.json()["version_number"] == 1
    assert second.json()["version_number"] == 2
    assert first.json()["document_version_id"] != second.json()["document_version_id"]

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        session.info["tenant_id"] = seed_id("tenant:acme")
        count = session.scalar(select(func.count(KnowledgeDocumentVersion.id)))
        assert count == 2
    engine.dispose()


def test_customer_cannot_ingest_or_search(client: TestClient, customer_token: str) -> None:
    ingest = client.post(
        "/v1/knowledge/documents",
        json=_document_payload("No access"),
        headers=_headers(customer_token),
    )
    search = client.post(
        "/v1/knowledge/search",
        json={"query": "anything"},
        headers=_headers(customer_token),
    )
    assert ingest.status_code == 403
    assert search.status_code == 403


def test_tenant_and_audience_filters_prevent_leakage(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    embeddings = HashEmbeddingProvider()
    acme_id = seed_id("tenant:acme")
    other_id = seed_id("tenant:other")

    with factory() as session:
        session.info["tenant_id"] = other_id
        ingested = ingest_document(
            session,
            embeddings,
            tenant_id=other_id,
            source_uri="kb://other/private",
            title="Other tenant secret policy",
            content="The other tenant uses the amber private procedure.",
            document_type="policy",
            audience="internal",
        )
        session.commit()
        assert ingested.created is True

    with factory() as session:
        session.info["tenant_id"] = acme_id
        result = retrieve(
            session,
            embeddings,
            tenant_id=acme_id,
            query="amber private procedure",
            audience="internal",
        )
        assert result.evidence == ()
        assert result.failure_category == "ZERO_RESULTS"
        visible_chunks = session.scalar(select(func.count(KnowledgeChunk.id)))
        assert visible_chunks == 0
        session.rollback()
    engine.dispose()


def test_wrong_audience_abstains(
    client: TestClient,
    admin_token: str,
    agent_token: str,
) -> None:
    payload = _document_payload("# Customer policy\nUse the cobalt verification phrase.")
    payload["audience"] = "customer"
    assert (
        client.post(
            "/v1/knowledge/documents", json=payload, headers=_headers(admin_token)
        ).status_code
        == 200
    )
    response = client.post(
        "/v1/knowledge/search",
        json={"query": "cobalt verification phrase", "audience": "internal"},
        headers=_headers(agent_token),
    )
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["failure_category"] == "ZERO_RESULTS"


def test_embedding_dimensions_are_checked(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        session.info["tenant_id"] = seed_id("tenant:acme")
        try:
            ingest_document(
                session,
                HashEmbeddingProvider(dimensions=8),
                tenant_id=seed_id("tenant:acme"),
                source_uri=f"kb://test/{uuid.uuid4()}",
                title="Bad dimensions",
                content="This must fail.",
                document_type="test",
                audience="internal",
            )
        except ValueError as exc:
            assert "does not match" in str(exc)
        else:
            raise AssertionError("dimension mismatch was accepted")
    engine.dispose()
