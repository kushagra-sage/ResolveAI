import os
from dataclasses import dataclass
from typing import Protocol

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

FORBIDDEN_ATTRIBUTE_PARTS = ("email", "phone", "prompt", "message", "secret", "token", "user_id")


def safe_attributes(attributes: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in attributes.items()
        if not any(part in key.lower() for part in FORBIDDEN_ATTRIBUTE_PARTS)
        and isinstance(value, str | bool | int | float)
    }


def tracer() -> trace.Tracer:
    return trace.get_tracer("resolveai", "0.1.0")


def configure_telemetry() -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint or isinstance(trace.get_tracer_provider(), TracerProvider):
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "resolveai-api")})
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))
        )
    )
    trace.set_tracer_provider(provider)


@dataclass(frozen=True, slots=True)
class GenerationObservation:
    trace_id: str
    prompt_version: str
    model_version: str
    input_tokens: int
    output_tokens: int
    cost_usd_micros: int | None


class LLMObservationSink(Protocol):
    def record(self, observation: GenerationObservation) -> None: ...


class NoopLLMObservationSink:
    """Safe adapter used when Langfuse is not configured."""

    def record(self, observation: GenerationObservation) -> None:
        del observation
