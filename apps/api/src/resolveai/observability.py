import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

from resolveai.telemetry import safe_attributes, tracer

REQUEST_TOTAL = Counter(
    "resolveai_request_total", "HTTP requests", ("method", "route", "status_class")
)
REQUEST_ERROR_TOTAL = Counter(
    "resolveai_request_error_total", "HTTP request errors", ("method", "route")
)
REQUEST_LATENCY = Histogram(
    "resolveai_request_latency_seconds", "HTTP request latency", ("method", "route")
)
RETRIEVAL_FAILURE_TOTAL = Counter(
    "resolveai_retrieval_failure_total", "Retrieval failures", ("category",)
)
GUARDRAIL_TRIGGER_TOTAL = Counter(
    "resolveai_guardrail_trigger_total", "Guardrail decisions", ("guardrail", "decision")
)
TOOL_CALL_TOTAL = Counter("resolveai_tool_call_total", "Tool calls", ("tool", "outcome"))
APPROVAL_TOTAL = Counter("resolveai_approval_total", "Approval outcomes", ("outcome",))
APPROVAL_LATENCY = Histogram(
    "resolveai_approval_latency_seconds", "Time from approval request to decision", ("outcome",)
)
RETRIEVAL_LATENCY = Histogram(
    "resolveai_retrieval_latency_seconds", "Retrieval latency", ("stage", "outcome")
)
RETRIEVAL_RESULT_COUNT = Histogram(
    "resolveai_retrieval_result_count", "Accepted retrieval results", ("stage",)
)
AGENT_NODE_LATENCY = Histogram(
    "resolveai_agent_node_latency_seconds", "Agent node latency", ("node", "outcome")
)
TOOL_LATENCY = Histogram(
    "resolveai_tool_latency_seconds", "Tool execution latency", ("tool", "outcome")
)
LLM_REQUEST_TOTAL = Counter(
    "resolveai_llm_request_total", "Model requests", ("provider", "model", "outcome")
)
LLM_TOKEN_TOTAL = Counter(
    "resolveai_llm_token_total", "Model tokens", ("provider", "model", "direction")
)
COST_MICROS_TOTAL = Counter(
    "resolveai_cost_usd_micros_total", "Attributed model/tool cost in USD micros", ("feature",)
)
EVALUATION_SCORE = Histogram(
    "resolveai_evaluation_score", "Evaluation scores", ("evaluator", "metric")
)
BUSINESS_EVENT_TOTAL = Counter(
    "resolveai_business_event_total",
    "Synthetic/local business outcome events; environment label prevents production inference",
    ("environment", "event"),
)


def _bounded_route(path: str) -> str:
    return re.sub(
        r"/[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}(?=/|$)",
        "/{id}",
        path,
    )


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        trace_id = request.headers.get("traceparent", "").split("-")[1:2]
        request.state.trace_id = trace_id[0] if trace_id else uuid.uuid4().hex
        route = _bounded_route(request.url.path)
        with tracer().start_as_current_span("api.request") as span:
            for key, value in safe_attributes(
                {"http.method": request.method, "http.route": route}
            ).items():
                span.set_attribute(key, value)
            try:
                response = await call_next(request)
            except Exception as exc:
                REQUEST_ERROR_TOTAL.labels(request.method, route).inc()
                span.record_exception(exc)
                raise
            span.set_attribute("http.status_code", response.status_code)
        status_class = f"{response.status_code // 100}xx"
        REQUEST_TOTAL.labels(request.method, route, status_class).inc()
        if response.status_code >= 500:
            REQUEST_ERROR_TOTAL.labels(request.method, route).inc()
        REQUEST_LATENCY.labels(request.method, route).observe(time.perf_counter() - started)
        response.headers["X-Trace-Id"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
