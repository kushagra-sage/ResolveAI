# ResolveAI CommerceOps Architecture

## Purpose

CommerceOps extends—rather than replaces—the customer-resolution system. Each resolved support
interaction may emit a minimized structured signal. Aggregates of those signals can reveal an
operational pattern, support an evidence-grounded root-cause investigation, propose a bounded
corrective action, reuse the existing policy/HITL system, and measure the outcome.

```text
Customer issue -> individual resolution -> structured signal -> aggregation
  -> anomaly -> evidence-grounded hypothesis -> recommended action
  -> policy / approval -> corrective action -> outcome measurement
```

## Bounded contexts

1. **Signal capture** — maps resolved tickets and tool outcomes to controlled categories.
2. **Operational facts** — inventory snapshots, fulfillment milestones, store capacity, delivery
   events, product/batch metadata, and payment health.
3. **Detection** — rolling baseline, robust z-score, EWMA, and rate-change detectors.
4. **Investigation** — ranks hypotheses supported by signal and operational evidence.
5. **Action planning** — produces typed action proposals; existing policy returns `ALLOW`,
   `REQUIRE_APPROVAL`, or `DENY`.
6. **Outcome tracking** — compares a declared target metric before and after an approved action.

## Initial data model

### `customer_signals`

`id`, `tenant_id`, `ticket_id`, `customer_id`, `order_id`, nullable `store_id`/`sku_id`, controlled
`category`, `severity`, `confidence`, `occurred_at`, `source`, minimized `evidence_json`, model and
rule versions, timestamps. Raw message content is not copied by default.

### Operational facts

- `stores`, `skus`, `inventory_snapshots`
- `fulfillment_events` (placed, picking, packed, assigned, dispatched, delivered)
- `product_batches` and `quality_reports`
- `operational_metric_points`

### Intelligence records

- `anomalies`: metric, entity, window, baseline, observed, deviation, confidence, detector version.
- `root_cause_hypotheses`: ranked cause, supporting and contradicting evidence, confidence.
- `recommended_actions`: typed parameters, expected impact, policy decision, approval reference.
- `action_outcomes`: target metric, before/after windows, effect estimate, limitations.

Every table is tenant-scoped and receives PostgreSQL row-level security consistent with the
existing schema.

## Initial explainable detection

Start with deterministic detectors rather than an opaque model:

- volume and rate baselines by category/store/SKU;
- robust z-score using median and MAD for outlier resistance;
- EWMA for sustained drift;
- rate-change detection for short spikes;
- minimum-support thresholds to suppress unstable alerts.

Every detector emits the exact baseline, observed value, window, threshold, and version used.

## Root-cause constraints

The root-cause workflow may summarize and rank only candidate causes linked to evidence. Each
hypothesis must include supporting evidence, contradicting evidence, affected entities, time
alignment, and confidence. Absence of sufficient evidence produces `INSUFFICIENT_EVIDENCE`, not
an invented cause.

## Action safety

Low-impact actions such as opening an incident may be allowed. Customer credits, inventory
transfers, delivery-radius changes, SKU disabling, and batch quarantine require action-specific
policy. High-impact mutations require digest-bound approval and idempotent execution using the
existing approval and tool framework.

## APIs to add incrementally

- `POST/GET /v1/customer-signals`
- `GET /v1/commerce/overview`
- `GET /v1/commerce/anomalies`
- `GET /v1/commerce/inventory-risk`
- `GET /v1/commerce/delivery-risk`
- `GET /v1/commerce/product-quality`
- `POST /v1/commerce/investigations`
- `POST /v1/commerce/recommended-actions`
- `GET /v1/commerce/action-outcomes`

List endpoints use bounded time windows, cursor pagination, tenant filters applied server-side,
and explicit permissions. APIs return provenance and `NOT_MEASURED` state instead of inferred
values.

## Delivery phases

1. Signal taxonomy, schema, migration, ingestion, tests.
2. Synthetic operational dataset and aggregation queries.
3. Explainable anomaly detectors with offline precision/recall evaluation.
4. Inventory, delivery, and quality dashboards.
5. Evidence-grounded root-cause engine.
6. Recommended actions integrated with policy, HITL, execution, and outcomes.

## Local implementation status

**Verified 2026-10-06.** All six delivery phases have a working local contract:

- controlled signal ingestion plus automatic minimized signals from eligible resolution runs;
- tenant-scoped stores, SKUs, inventory snapshots, fulfillment events, product batches, quality
  reports, and operational metric points;
- robust-z, EWMA, and rate-change detectors with persisted offline precision/recall evaluation;
- inventory, delivery, and product-quality risk APIs consumed by the React operations workspace;
- ranked root-cause hypotheses using signal concentration and time-aligned operational facts;
- policy-evaluated actions, digest-bound human approval, separation of duty, idempotent local
  execution, outbox events, and before/after outcome records;
- a Docker detector worker that claims due schedules with bounded batches and tenant isolation.

The local dataset and adapters are synthetic. Production commerce event streams, managed
infrastructure, provider credentials, and independent acceptance testing remain deployment inputs.
