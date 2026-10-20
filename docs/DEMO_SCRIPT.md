# ResolveAI faculty demo script

This is a 2–3 minute, evidence-led walkthrough. Use the synthetic-data disclaimer in the first sentence: **the workflow is real and locally executed; the customers and benchmark cases are synthetic.**

## 1. Product problem (20 seconds)

“Customer-support AI often stops at generating text. ResolveAI turns a support request into a governed operational workflow: it retrieves evidence, proposes an action, applies deterministic policy, pauses for independent approval when required, executes idempotently, and records the trace, cost, guardrail, and evaluation evidence.”

Open `http://localhost:3000` and sign in through Keycloak.

## 2. Customer context (20 seconds)

Open **Customer 360**. Show one synthetic customer’s orders, payments, shipments, tickets, conversation messages, notes, refunds, and outcomes. Explain that every query is tenant-scoped and that the interface labels the dataset as synthetic and free of real PII.

## 3. Governed resolution (35 seconds)

Open **Resolution workspace** and submit a refund or shipment request. Explain the runtime path:

```text
authenticate → guard input → retrieve evidence → plan → evaluate policy
→ execute or request approval → verify result → audit → enqueue evaluation
```

For a higher-risk request, show **Approval center**. A supervisor can approve, edit, or reject; the action digest and policy are checked again after resume.

## 4. Evidence and operations (35 seconds)

Open **Trace explorer** to show persisted workflow steps, then **Evaluation lab**, **RAG evolution**, and **Cost & reliability**. State that these pages now read live tenant data from the backend; empty or unknown values remain explicit instead of becoming invented zeros.

Open **System health** to show queue depth, retry counts, worker jobs, outbox delivery, dead-letter replay, and stalled-work reconciliation.

## 5. Research result (30 seconds)

Show `research/figures/baseline-vs-resolveai.png`. The fixed 168-case synthetic benchmark reports:

- answer accuracy: 17.86% baseline vs 96.43% ResolveAI;
- hallucination rate: 78.57% vs 3.57%;
- policy compliance: 46.43% vs 85.71%;
- paired mean quality delta: +0.5089, bootstrap 95% CI [0.4628, 0.5528].

Immediately state the limitation: these values establish behavior on a controlled synthetic benchmark, not production business impact. The 15.38% false-positive rate also identifies a concrete guardrail-calibration target.

## 6. Closing impact (20 seconds)

“The project’s contribution is the control plane around an agentic RAG system: tenant isolation, evidence lineage, policy and human oversight, safe side effects, replayable operations, and reproducible evaluation in one workflow. The next research step is external-domain data, paid-model baselines, fault injection, and a human-review study.”

## Useful commands

```powershell
docker compose --profile identity --profile storage up -d --build
cd apps/web
npm run test:e2e -- --project=chromium
cd ../..
.\.venv\Scripts\python.exe scripts\run_research_benchmark.py
```
