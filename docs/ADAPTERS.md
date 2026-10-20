# External adapters

ResolveAI depends on stable application ports rather than provider SDKs. The contracts in
`apps/api/src/resolveai/interfaces/` cover ERP inventory/transfers, WMS fulfillment, payment
refunds, shipment status/rescheduling, and model completion. Implementations live under
`adapters/mock/` and `adapters/provider/`.

## Local mode

`RESOLVEAI_EXTERNAL_ADAPTER_MODE=mock` uses deterministic, in-memory sandbox adapters. Their
references and responses are reproducible, write-like operations enforce idempotency payload
matching, and references containing `timeout` or `error` exercise normalized 504/503 paths. Mock
results are synthetic and are never represented as provider confirmations.

`RESOLVEAI_MODEL_PROVIDER_MODE=deterministic` is the default and needs no API key. It produces a
stable response keyed to the prompt hash. `ollama`, `openai_compatible`, and `hosted` use the same
OpenAI-compatible HTTP contract. Ollama can use `http://localhost:11434/v1`; another local or
hosted endpoint is selected with `RESOLVEAI_MODEL_BASE_URL` and `RESOLVEAI_MODEL_NAME`.

## Provider mode

Set `RESOLVEAI_EXTERNAL_ADAPTER_MODE=rest` and configure the relevant ERP, WMS, payment, and
shipment base URLs. Base URLs must be absolute HTTP(S) URLs. Requests have configured timeouts,
one to three bounded attempts, exponential backoff, bearer credentials supplied only through the
environment, and `Idempotency-Key` on writes. Missing URLs report the provider as unavailable.

Provider credentials are never checked into code. The status endpoint reports configuration
availability without returning credentials:

`GET /v1/integrations/status`

Authenticated read diagnostics are available for inventory, fulfillment, and shipment status.
Write diagnostics are namespaced under `/v1/integrations/sandbox`, require `tenant:admin`, and are
disabled outside local/test. Production side effects continue to enter through the governed
policy/approval/tool workflow; the diagnostic routes are not an authorization bypass.

## Replacement procedure

1. Implement the appropriate protocol from `resolveai.interfaces`.
2. Normalize provider errors to `AdapterTimeout`, `AdapterUnavailable`, or `AdapterConflict`.
3. Preserve tenant propagation, stable idempotency, authoritative read-back, and redacted audit.
4. Register the adapter in `build_adapter_registry` without changing workflow/domain code.
5. Add contract tests for success, timeout, upstream error, retry exhaustion, replay, and payload
   conflict before enabling the provider outside a sandbox.

MCP can be added as another transport facade over the same ports. It is not treated as a security
boundary; service identity, permissions, policy, and idempotency remain server-side controls.
