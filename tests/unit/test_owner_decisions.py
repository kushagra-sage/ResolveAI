import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from resolveai.artifacts import S3ArtifactStore, tenant_object_key
from resolveai.break_glass import BreakGlassRequest
from resolveai.config import Settings
from resolveai.governance import (
    DataClassification,
    load_provider_data_policy,
    load_retention_policy,
)
from resolveai.payments import PaymentWebhookVerifier

ROOT = Path(__file__).parents[2]


class FakeObjectStore:
    def __init__(self) -> None:
        self.put: dict[str, object] | None = None

    def put_object(self, **kwargs: object) -> object:
        self.put = kwargs
        return {"etag": "local"}

    def generate_presigned_url(self, operation_name: str, **kwargs: object) -> str:
        return f"https://objects.example.test/{operation_name}/{kwargs['Params']}"


def test_production_rejects_development_signing_mode() -> None:
    with pytest.raises(ValidationError, match="local HS256"):
        Settings(environment="production", auth_mode="local_hs256")
    configured = Settings(
        environment="production",
        auth_mode="oidc",
        oidc_jwks_url="https://identity.example.test/.well-known/jwks.json",
        jwt_issuer="https://identity.example.test/",
    )
    assert configured.auth_mode == "oidc"


def test_retention_policy_includes_derived_embeddings_and_legal_hold_is_caller_control() -> None:
    policy = load_retention_policy(ROOT / "config" / "retention-policy.json")
    created = datetime(2026, 1, 1, tzinfo=UTC)
    assert policy.expires_at("temporary_documents", created) == datetime(2026, 1, 31, tzinfo=UTC)
    assert policy.deletion_classes("temporary_documents") == (
        "temporary_documents",
        "knowledge_embeddings",
    )
    assert policy.expires_at("knowledge_source_documents", created) is None


def test_provider_policy_never_allows_restricted_data() -> None:
    policy = load_provider_data_policy(ROOT / "config" / "provider-data-policy.json")
    assert policy.allows("openai_compatible", DataClassification.CONFIDENTIAL)
    assert not policy.allows("openai_compatible", DataClassification.SENSITIVE_PII)
    assert not policy.allows("local", DataClassification.RESTRICTED)


def test_break_glass_requires_mfa_and_second_write_elevation() -> None:
    with pytest.raises(ValidationError, match="MFA"):
        BreakGlassRequest(
            reason="Investigate tenant incident", ticket_reference="INC-1", mfa_verified=False
        )
    with pytest.raises(ValidationError, match="second explicit elevation"):
        BreakGlassRequest(
            reason="Repair tenant incident record",
            ticket_reference="INC-2",
            mfa_verified=True,
            write_access=True,
        )
    request = BreakGlassRequest(
        reason="Repair tenant incident record",
        ticket_reference="INC-2",
        mfa_verified=True,
        write_access=True,
        second_elevation_reference="CHG-2",
    )
    assert request.write_access


def test_s3_artifacts_are_tenant_prefixed_and_presigned_reads_are_scoped() -> None:
    tenant_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    client = FakeObjectStore()
    store = S3ArtifactStore(client, "resolveai-artifacts")
    stored = store.put(
        tenant_id=tenant_id,
        artifact_id=artifact_id,
        filename="evaluation report.html",
        content=b"verified",
        content_type="text/html",
        classification=DataClassification.INTERNAL,
    )
    assert stored.object_key == tenant_object_key(tenant_id, artifact_id, "evaluation report.html")
    assert client.put is not None
    assert store.presigned_get(tenant_id=tenant_id, object_key=stored.object_key)
    with pytest.raises(PermissionError):
        store.presigned_get(tenant_id=uuid.uuid4(), object_key=stored.object_key)


def test_payment_webhook_requires_valid_hmac_timestamp_and_unique_event() -> None:
    class ReplayStore:
        def __init__(self) -> None:
            self.events: set[str] = set()

        def claim_event(self, event_id: str, _timestamp: int) -> bool:
            if event_id in self.events:
                return False
            self.events.add(event_id)
            return True

    import hashlib
    import hmac

    payload = b'{"status":"succeeded"}'
    timestamp = 1_800_000_000
    secret = b"local-webhook-secret"
    signature = hmac.new(
        secret, str(timestamp).encode() + b"." + payload, hashlib.sha256
    ).hexdigest()
    verifier = PaymentWebhookVerifier(secret=secret, replay_store=ReplayStore())
    verifier.verify(
        event_id="evt-1",
        timestamp=timestamp,
        payload=payload,
        signature=f"sha256={signature}",
        now=timestamp,
    )
    with pytest.raises(ValueError, match="duplicate"):
        verifier.verify(
            event_id="evt-1",
            timestamp=timestamp,
            payload=payload,
            signature=signature,
            now=timestamp,
        )
