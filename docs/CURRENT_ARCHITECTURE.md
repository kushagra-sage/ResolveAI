# ResolveAI implemented architecture

```mermaid
flowchart LR
    U[Customer / support agent / supervisor] --> W[React operations workspace]
    W -->|OIDC Authorization Code + PKCE| K[Keycloak]
    W -->|Bearer token| A[FastAPI control plane]
    A --> G[LangGraph resolution workflow]
    G --> R[Hybrid RAG + knowledge lifecycle]
    G --> P[Deterministic policy engine]
    P --> H[Human approval boundary]
    G --> T[Typed commerce/support tools]
    A --> D[(PostgreSQL + pgvector)]
    A --> Q[(Redis)]
    A --> S[(SeaweedFS S3 artifacts)]
    D --> O[Outbox + evaluation worker]
    O --> D
    A --> C[OpenTelemetry collector]
    C --> M[Prometheus]
    M --> F[Grafana]
```

## End-to-end control flow

```mermaid
sequenceDiagram
    actor User
    participant Web
    participant API
    participant RAG
    participant Policy
    participant Reviewer
    participant Tool
    participant DB

    User->>Web: Submit support request
    Web->>API: Authenticated tenant request
    API->>API: RBAC and input guard
    API->>RAG: Retrieve filtered evidence
    RAG-->>API: Citations or abstention signal
    API->>Policy: Typed action and server facts
    alt Allowed
        Policy-->>API: ALLOW
    else Approval required
        Policy-->>API: REQUIRE_APPROVAL
        API->>DB: Persist checkpoint and action digest
        Reviewer->>API: Approve / edit / reject
        API->>Policy: Reauthorize and reevaluate
    else Denied
        Policy-->>API: DENY
    end
    API->>Tool: Idempotent execution when allowed
    Tool-->>API: Receipt and verification
    API->>DB: Trace, audit, cost, guardrail, outbox
    API-->>Web: Outcome and trace ID
```

The local Docker topology contains PostgreSQL, Redis, Keycloak, SeaweedFS, API, a scheduled detector worker, a durable evaluation/outbox worker, OpenTelemetry Collector, Prometheus, Grafana, and the React web application.
