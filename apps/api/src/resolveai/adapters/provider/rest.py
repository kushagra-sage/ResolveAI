import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from resolveai.interfaces import AdapterConflict, AdapterTimeout, AdapterUnavailable


class _RestClient:
    def __init__(
        self,
        base_url: str | None,
        *,
        api_key: str | None,
        timeout_seconds: float,
        max_attempts: int,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        if self.base_url:
            parsed = urlparse(self.base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("provider base URL must be an absolute HTTP(S) URL")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, object]:
        if self.base_url is None:
            raise AdapterUnavailable("provider base URL is not configured")
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        last_error: Exception = AdapterUnavailable("provider did not run")
        for attempt in range(self.max_attempts):
            try:
                request = Request(
                    f"{self.base_url}{path}", data=body, headers=headers, method=method
                )
                # The constructor enforces an absolute HTTP(S) URL;
                # provider URLs are trusted configuration.
                with urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310
                    decoded: Any = json.loads(response.read().decode())
                    if not isinstance(decoded, dict):
                        raise AdapterUnavailable("provider returned a non-object response")
                    return {str(key): value for key, value in decoded.items()}
            except HTTPError as exc:
                if exc.code == 409:
                    raise AdapterConflict("provider rejected an idempotency conflict") from exc
                if exc.code < 500:
                    raise AdapterUnavailable(f"provider request rejected ({exc.code})") from exc
                last_error = exc
            except TimeoutError as exc:
                last_error = exc
                if attempt + 1 == self.max_attempts:
                    raise AdapterTimeout("provider request timed out") from exc
            except (URLError, json.JSONDecodeError) as exc:
                last_error = exc
            if attempt + 1 < self.max_attempts:
                time.sleep(min(0.2 * (2**attempt), 1.0))
        raise AdapterUnavailable("provider unavailable after bounded retries") from last_error


class RestERPAdapter:
    name = "rest-erp"

    def __init__(self, client: _RestClient) -> None:
        self.client = client

    def inventory(self, *, tenant_id: str, store_ref: str, sku_ref: str) -> dict[str, object]:
        return self.client.request(
            "GET", f"/inventory/{quote(store_ref, safe='')}/{quote(sku_ref, safe='')}"
        )

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
        return self.client.request(
            "POST",
            "/transfers",
            payload={
                "tenant_id": tenant_id,
                "sku_ref": sku_ref,
                "source_store": source_store,
                "destination_store": destination_store,
                "quantity": quantity,
            },
            idempotency_key=idempotency_key,
        )


class RestWMSAdapter:
    name = "rest-wms"

    def __init__(self, client: _RestClient) -> None:
        self.client = client

    def fulfillment(self, *, tenant_id: str, order_ref: str) -> dict[str, object]:
        return self.client.request("GET", f"/fulfillments/{quote(order_ref, safe='')}")


class RestPaymentAdapter:
    name = "rest-payment"

    def __init__(self, client: _RestClient) -> None:
        self.client = client

    def refund(
        self,
        *,
        tenant_id: str,
        payment_ref: str,
        amount_minor: int,
        currency: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        return self.client.request(
            "POST",
            "/refunds",
            payload={
                "tenant_id": tenant_id,
                "payment_ref": payment_ref,
                "amount_minor": amount_minor,
                "currency": currency,
            },
            idempotency_key=idempotency_key,
        )


class RestShipmentAdapter:
    name = "rest-shipment"

    def __init__(self, client: _RestClient) -> None:
        self.client = client

    def status(self, *, tenant_id: str, shipment_ref: str) -> dict[str, object]:
        return self.client.request("GET", f"/shipments/{quote(shipment_ref, safe='')}")

    def reschedule(
        self,
        *,
        tenant_id: str,
        shipment_ref: str,
        delivery_date: str,
        idempotency_key: str,
    ) -> dict[str, object]:
        encoded_ref = quote(shipment_ref, safe="")
        return self.client.request(
            "POST",
            f"/shipments/{encoded_ref}/reschedule",
            payload={"tenant_id": tenant_id, "delivery_date": delivery_date},
            idempotency_key=idempotency_key,
        )


class OpenAICompatibleModelAdapter:
    name = "openai-compatible"

    def __init__(self, client: _RestClient, model: str, *, name: str | None = None) -> None:
        self.client = client
        self.model = model
        if name:
            self.name = name

    def complete(self, prompt: str) -> dict[str, object]:
        result = self.client.request(
            "POST",
            "/chat/completions",
            payload={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
        )
        try:
            choices = result["choices"]
            if not isinstance(choices, list):
                raise TypeError("choices must be a list")
            first = choices[0]
            if not isinstance(first, dict):
                raise TypeError("choice must be an object")
            message = first["message"]
            if not isinstance(message, dict):
                raise TypeError("message must be an object")
            text = str(message["content"])
        except (AssertionError, IndexError, KeyError, TypeError) as exc:
            raise AdapterUnavailable("model provider returned an invalid response") from exc
        raw_usage = result.get("usage")
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        return {
            "text": text,
            "provider": self.name,
            "model": self.model,
            "input_tokens": int(usage.get("prompt_tokens", 0)),
            "output_tokens": int(usage.get("completion_tokens", 0)),
        }
