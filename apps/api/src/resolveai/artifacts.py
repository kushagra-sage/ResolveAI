import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Protocol, cast

import boto3  # type: ignore[import-untyped]

from resolveai.config import Settings
from resolveai.governance import DataClassification


class ObjectStoreClient(Protocol):
    def put_object(self, **kwargs: object) -> object: ...

    def generate_presigned_url(self, operation_name: str, **kwargs: object) -> str: ...


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    object_key: str
    checksum_sha256: str
    content_type: str
    size_bytes: int
    classification: DataClassification


def tenant_object_key(tenant_id: uuid.UUID, artifact_id: uuid.UUID, filename: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-.") or "artifact.bin"
    return f"tenants/{tenant_id}/artifacts/{artifact_id}/{safe_name}"


class S3ArtifactStore:
    def __init__(self, client: ObjectStoreClient, bucket: str):
        self.client = client
        self.bucket = bucket

    def put(
        self,
        *,
        tenant_id: uuid.UUID,
        artifact_id: uuid.UUID,
        filename: str,
        content: bytes,
        content_type: str,
        classification: DataClassification,
    ) -> StoredArtifact:
        object_key = tenant_object_key(tenant_id, artifact_id, filename)
        checksum = hashlib.sha256(content).hexdigest()
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type,
            Metadata={"sha256": checksum, "classification": classification.value},
        )
        return StoredArtifact(
            object_key=object_key,
            checksum_sha256=checksum,
            content_type=content_type,
            size_bytes=len(content),
            classification=classification,
        )

    def presigned_get(self, *, tenant_id: uuid.UUID, object_key: str, expires: int = 900) -> str:
        prefix = f"tenants/{tenant_id}/"
        if not object_key.startswith(prefix):
            raise PermissionError("artifact object key is outside the tenant prefix")
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=expires,
        )


def create_artifact_store(settings: Settings) -> S3ArtifactStore:
    client = boto3.client(
        "s3",
        endpoint_url=settings.artifact_endpoint_url,
        region_name=settings.artifact_region,
        aws_access_key_id=settings.artifact_access_key.get_secret_value(),
        aws_secret_access_key=settings.artifact_secret_key.get_secret_value(),
    )
    return S3ArtifactStore(cast(ObjectStoreClient, client), settings.artifact_bucket)
