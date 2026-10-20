from resolveai.adapters.mock import (
    DeterministicModelAdapter,
    MockERPAdapter,
    MockPaymentAdapter,
    MockShipmentAdapter,
    MockWMSAdapter,
)
from resolveai.adapters.provider import (
    OpenAICompatibleModelAdapter,
    RestERPAdapter,
    RestPaymentAdapter,
    RestShipmentAdapter,
    RestWMSAdapter,
)
from resolveai.adapters.provider.rest import _RestClient
from resolveai.config import Settings
from resolveai.interfaces import (
    AdapterRegistry,
    ERPAdapter,
    ModelAdapter,
    PaymentAdapter,
    ShipmentAdapter,
    WMSAdapter,
)


def _client(settings: Settings, base_url: str | None) -> _RestClient:
    return _RestClient(
        base_url,
        api_key=(
            settings.external_adapter_api_key.get_secret_value()
            if settings.external_adapter_api_key
            else None
        ),
        timeout_seconds=settings.adapter_timeout_seconds,
        max_attempts=settings.adapter_max_attempts,
    )


def build_adapter_registry(settings: Settings) -> AdapterRegistry:
    erp: ERPAdapter
    wms: WMSAdapter
    payment: PaymentAdapter
    shipment: ShipmentAdapter
    model: ModelAdapter
    if settings.external_adapter_mode == "rest":
        erp = RestERPAdapter(_client(settings, settings.erp_base_url))
        wms = RestWMSAdapter(_client(settings, settings.wms_base_url))
        payment = RestPaymentAdapter(_client(settings, settings.payment_base_url))
        shipment = RestShipmentAdapter(_client(settings, settings.shipment_base_url))
    else:
        erp = MockERPAdapter()
        wms = MockWMSAdapter()
        payment = MockPaymentAdapter()
        shipment = MockShipmentAdapter()

    if settings.model_provider_mode == "deterministic":
        model = DeterministicModelAdapter()
    else:
        model_key = settings.model_api_key.get_secret_value() if settings.model_api_key else None
        model_name = (
            "ollama"
            if settings.model_provider_mode == "ollama"
            else settings.model_provider_mode.replace("_", "-")
        )
        model = OpenAICompatibleModelAdapter(
            _RestClient(
                settings.model_base_url,
                api_key=model_key,
                timeout_seconds=settings.adapter_timeout_seconds,
                max_attempts=settings.adapter_max_attempts,
            ),
            settings.model_name,
            name=model_name,
        )
    return AdapterRegistry(erp, wms, payment, shipment, model, settings.external_adapter_mode)
