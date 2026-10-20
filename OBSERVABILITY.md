# Observability

Every HTTP response includes an `X-Trace-Id`. Request metrics expose bounded method, normalized route, and status-class labels at `/metrics`. No tenant, user, query text, or run ID appears in Prometheus labels. The Grafana dashboard reads Prometheus queries and has no hard-coded performance values.

The durable records—agent runs/steps, retrieval events, guardrail events, policy decisions, tool calls, approvals, audits, and costs—carry correlation fields. OpenTelemetry/Langfuse exporters are optional adapters; exporter failure must never fail the customer path.

Local endpoints: Prometheus `:9090`, Grafana `:3001`, API metrics `:8000/metrics`. Panels without samples are interpreted as `NOT MEASURED YET`.
