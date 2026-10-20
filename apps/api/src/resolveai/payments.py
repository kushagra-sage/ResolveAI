import hashlib
import hmac
import time
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class RefundStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProviderRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_reference: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    idempotency_key: str = Field(min_length=1, max_length=200)


class ProviderRefundResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refund_id: str
    status: RefundStatus
    amount_minor: int
    currency: str


class PaymentProvider(Protocol):
    def create_refund(self, request: ProviderRefundRequest) -> ProviderRefundResult: ...

    def get_refund(self, refund_id: str) -> ProviderRefundResult: ...


class WebhookReplayStore(Protocol):
    def claim_event(self, event_id: str, timestamp: int) -> bool: ...


class PaymentWebhookVerifier:
    def __init__(
        self,
        *,
        secret: bytes,
        replay_store: WebhookReplayStore,
        tolerance_seconds: int = 300,
    ):
        self.secret = secret
        self.replay_store = replay_store
        self.tolerance_seconds = tolerance_seconds

    def verify(
        self,
        *,
        event_id: str,
        timestamp: int,
        payload: bytes,
        signature: str,
        now: int | None = None,
    ) -> None:
        current = int(time.time()) if now is None else now
        if abs(current - timestamp) > self.tolerance_seconds:
            raise ValueError("payment webhook timestamp outside tolerance")
        signed = str(timestamp).encode() + b"." + payload
        expected = hmac.new(self.secret, signed, hashlib.sha256).hexdigest()
        supplied = signature.removeprefix("sha256=")
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("invalid payment webhook signature")
        if not self.replay_store.claim_event(event_id, timestamp):
            raise ValueError("duplicate payment webhook event")
