import hashlib
from threading import Lock

from resolveai.interfaces import AdapterConflict, AdapterTimeout, AdapterUnavailable


def _failure(reference: str) -> None:
    lowered = reference.lower()
    if "timeout" in lowered:
        raise AdapterTimeout("simulated upstream timeout")
    if "unavailable" in lowered or "error" in lowered:
        raise AdapterUnavailable("simulated upstream unavailability")


def _stable(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:12].upper()}"


class _IdempotentMock:
    def __init__(self) -> None:
        self._results: dict[str, tuple[tuple[object, ...], dict[str, object]]] = {}
        self._lock = Lock()

    def _once(
        self, key: str, fingerprint: tuple[object, ...], result: dict[str, object]
    ) -> dict[str, object]:
        with self._lock:
            existing = self._results.get(key)
            if existing is not None:
                if existing[0] != fingerprint:
                    raise AdapterConflict("idempotency key reused with different payload")
                return {**existing[1], "replayed": True}
            stored = {**result, "replayed": False}
            self._results[key] = (fingerprint, stored)
            return stored.copy()


class MockERPAdapter(_IdempotentMock):
    name = "mock-erp"

    def inventory(self, *, tenant_id: str, store_ref: str, sku_ref: str) -> dict[str, object]:
        _failure(f"{store_ref}:{sku_ref}")
        digest = hashlib.sha256(f"{tenant_id}:{store_ref}:{sku_ref}".encode()).hexdigest()
        available = 8 + int(digest[:2], 16) % 48
        return {
            "store_ref": store_ref,
            "sku_ref": sku_ref,
            "available_units": available,
            "source": self.name,
        }

    def create_transfer(
        self,
        *,
        tenant_id: str,
        sku_ref: str,
        source_store: str,
        destination_store: str,
        quantity: int,
        idempotency_key: str,
    ) -> dict[str, object]:
        _failure(f"{sku_ref}:{source_store}:{destination_store}")
        if quantity < 1:
            raise AdapterConflict("quantity must be positive")
        fingerprint = (tenant_id, sku_ref, source_store, destination_store, quantity)
        return self._once(
            idempotency_key,
            fingerprint,
            {
                "transfer_ref": _stable("TRF", idempotency_key),
                "status": "accepted",
                "source": self.name,
            },
        )


class MockWMSAdapter:
    name = "mock-wms"

    def fulfillment(self, *, tenant_id: str, order_ref: str) -> dict[str, object]:
        _failure(order_ref)
        return {
            "order_ref": order_ref,
            "status": "in_transit",
            "warehouse_ref": _stable("WH", tenant_id)[:9],
            "source": self.name,
        }


class MockPaymentAdapter(_IdempotentMock):
    name = "mock-payment"

    def refund(
        self,
        *,
        tenant_id: str,
        payment_ref: str,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        _failure(payment_ref)
        if amount_minor < 1:
            raise AdapterConflict("amount must be positive")
        fingerprint = (tenant_id, payment_ref, amount_minor, currency.upper())
        return self._once(
            idempotency_key,
            fingerprint,
            {
                "refund_ref": _stable("RFD", idempotency_key),
                "status": "succeeded",
                "amount_minor": amount_minor,
                "currency": currency.upper(),
                "source": self.name,
            },
        )


class MockShipmentAdapter(_IdempotentMock):
    name = "mock-shipment"

    def status(self, *, tenant_id: str, shipment_ref: str) -> dict[str, object]:
        _failure(shipment_ref)
        return {
            "shipment_ref": shipment_ref,
            "status": "in_transit",
            "carrier": "ResolveAI Sandbox Express",
            "source": self.name,
        }

    def reschedule(
        self,
        *,
        tenant_id: str,
        shipment_ref: str,
        delivery_date: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        _failure(shipment_ref)
        fingerprint = (tenant_id, shipment_ref, delivery_date)
        return self._once(
            idempotency_key,
            fingerprint,
            {
                "shipment_ref": shipment_ref,
                "delivery_date": delivery_date,
                "status": "rescheduled",
                "source": self.name,
            },
        )


class DeterministicModelAdapter:
    name = "deterministic"
    model = "resolveai-deterministic-v1"

    def complete(self, prompt: str) -> dict[str, object]:
        _failure(prompt)
        normalized = " ".join(prompt.split())
        digest = hashlib.sha256(normalized.encode()).hexdigest()[:12]
        return {
            "text": f"Deterministic local response for case {digest}.",
            "provider": self.name,
            "model": self.model,
            "input_tokens": len(normalized.split()),
            "output_tokens": 7,
        }
