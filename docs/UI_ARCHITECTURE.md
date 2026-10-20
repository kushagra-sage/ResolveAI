# ResolveAI React UI Architecture

## Current-state audit

The frontend is a **React 19 / TypeScript / Vite** application under `apps/web`.
The resolution and approval workflows call FastAPI directly. CommerceOps signals, anomalies,
inventory risk, delivery risk, product quality, root causes, actions, and outcomes now use live
tenant-scoped APIs with authenticated empty, loading, and error states. The frontend contains no
domain authority and that boundary remains intact.

The backend is retained without unnecessary contract changes:

- FastAPI routers expose health, identity, customers/orders, knowledge ingestion/search,
  resolutions, approvals, and cost summaries.
- Authentication, RBAC, tenant isolation, policy evaluation, guardrails, tool execution,
  approval validity, audit, evaluation jobs, and cost calculation remain server-side.
- PostgreSQL/pgvector, Redis, Keycloak, SeaweedFS, OpenTelemetry, Prometheus, and Grafana remain
  the operational platform.

## Migration decision

Replace Next.js with a client-side application using **React 19, TypeScript, and Vite**.
React Router owns navigation; TanStack Query owns server state; Zustand owns small UI-only state
(theme, sidebar, command palette); React Hook Form and Zod validate user input before it reaches
the API. No policy or authorization logic is duplicated in the browser.

Vite runs on port 3000 in local Docker to preserve the existing developer URL. The API remains
on port 8000. `VITE_API_URL` is the only public backend configuration.

## Page hierarchy

```text
Overview
Customer Operations
  Customer Resolution
  Tickets / Customers / Orders / Refunds / Approvals
Commerce Intelligence
  Operations Overview / Customer Signals / Inventory Intelligence
  Delivery Intelligence / Product Quality / Anomalies
  Root Cause Analysis / Recommended Actions
AI Platform
  Traces / Evaluations / RAG Lab / Experiments / Datasets
  Prompt Versions / Model Versions
Safety
  Guardrails / Policy Engine / Red Team / Audit Log
Analytics
  AI Quality / Reliability / Cost / Business Impact
Developer
  Tools / MCP / Integrations / API / Settings
```

## Application shell

- `AppShell`: responsive landing-to-workspace shell and route outlet.
- `FloatingNav`: capsule navigation for primary product areas, environment, search, and theme.
- `Sidebar`: on-demand product map containing every secondary operational route.
- `ContextBar`: tenant, environment, current route, and operator identity.
- `CommandPalette`: keyboard-first navigation and future entity search.
- `ThemeProvider`: light/dark system preference with explicit override.
- `RouteBoundary`: loading, permission-denied, not-found, and recoverable error states.

## Component architecture

```text
src/
  app/            router, providers, query client
  components/
    shell/        AppShell, Sidebar, TopBar, CommandPalette
    ui/           Button, Card, Badge, EmptyState, DataTable, Metric
    charts/       TimeSeries, Comparison, Distribution, Scatter
    evidence/     CitationList, PolicyResult, ToolCall, RationalePanel
  features/
    overview/
    resolutions/
    approvals/
    traces/
    evaluations/
    rag/
    commerce/
    safety/
    analytics/
  lib/            typed API client, schemas, formatting
  stores/         UI-only Zustand stores
```

Feature modules own page composition and query hooks, not authorization decisions. Shared UI
components remain domain-neutral. API response schemas should be generated from or checked
against FastAPI OpenAPI as the contract surface grows.

## Visual system

The October 2026 interface adopts a **Brainfish-inspired visual language** without copying its
brand, logo, text, or proprietary illustrations. ResolveAI retains its own domain model and
content while applying these design principles:

- sky-to-electric-blue environmental gradient with large rounded sections;
- floating white capsule navigation and compact black outlines;
- lime as the primary action, success, and agent-core color;
- warm pastel cards for knowledge, approval, evidence, execution, and outcome categories;
- outlined cloud motifs and diagram-led product explanations;
- oversized rounded typography for product narrative, paired with compact operational labels;
- deliberate hard shadows and borders instead of generic glassmorphism;
- responsive conversion from the architecture diagram into a vertical workflow.

Operational pages inherit the same system but remain information-dense and accessible. Decorative
elements never replace status text, evidence, or form labels.

## Information design

- Product-first visual storytelling with an on-demand enterprise navigation map.
- Trace and evaluation drill-down patterns inspired by observability products.
- Customer/order/payment detail density inspired by operational finance interfaces.
- No generic chatbot landing page and no decorative metrics without a measured source.
- Every metric includes state: measured value, `NOT MEASURED`, unavailable, or permission denied.
- Safe rationale shows evidence, policy reason, and structured workflow summaries—never hidden
  chain-of-thought.

## Migration sequence

1. Replace Next scripts/configuration with Vite while preserving port 3000.
2. Add the application shell, theme system, route registry, command palette, and query provider.
3. Port the current support workspace and approval center.
4. Add typed query surfaces for traces, evaluations, RAG, safety, and cost as backend endpoints
   become available.
5. Add CommerceOps routes behind the same tenant and permission model.
6. Remove transitional static snapshots only after corresponding measured APIs exist.

Steps 1–5 and the CommerceOps portion of step 6 are locally complete. Model registry, policy,
audit, reports, health, settings, and knowledge administration remain explicit planned surfaces.

## Acceptance gates

- `npm run typecheck`, `npm run build`, and frontend tests pass.
- Existing FastAPI tests and API contracts remain green.
- Keyboard navigation, responsive layout, empty states, and light/dark themes work.
- No token, restricted PII, or policy authority is persisted in frontend application state.
- Pages never fabricate a metric when the API has no measurement.
