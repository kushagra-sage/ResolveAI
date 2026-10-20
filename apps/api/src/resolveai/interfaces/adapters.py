from dataclasses import dataclass
from typing import Protocol


class AdapterError(RuntimeError):
    """Base error safe to translate at an API boundary."""


class AdapterTimeout(AdapterError):
    pass


class AdapterUnavailable(AdapterError):
    pass


class AdapterConflict(AdapterError):
    pass


class ERPAdapter(Protocol):
    name: str

    def inventory(self, *, tenant_id: str, store_ref: str, sku_ref: str) -> dict[str, object]: ...

    def create_transfer(
        self,
        *,
        tenant_id: str,
        sku_ref: str,
        source_store: str,
        destination_store: str,
        quantity: int,
        idempotency_key: str,
    ) -> dict[str, object]: ...


class WMSAdapter(Protocol):
    name: str

    def fulfillment(self, *, tenant_id: str, order_ref: str) -> dict[str, object]: ...


class PaymentAdapter(Protocol):
    name: str

    def refund(
        self,
        *,
        tenant_id: str,
        payment_ref: str,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> dict[str, object]: ...


class ShipmentAdapter(Protocol):
    name: str

    def status(self, *, tenant_id: str, shipment_ref: str) -> dict[str, object]: ...

    def reschedule(
        self,
        *,
        tenant_id: str,
        shipment_ref: str,
        delivery_date: str,
        idempotency_key: str,
    ) -> dict[str, object]: ...


class ModelAdapter(Protocol):
    name: str
    model: str

    def complete(self, prompt: str) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class AdapterRegistry:
    erp: ERPAdapter
    wms: WMSAdapter
    payment: PaymentAdapter
    shipment: ShipmentAdapter
    model: ModelAdapter
    mode: str
