# ResolveAI synthetic benchmark v1

This directory contains generated development and research-evaluation fixtures. Every row is
fictional, carries `synthetic: true`, uses reserved `.test` identities when an address is needed,
and must not be presented as customer data or production evidence.

Regenerate deterministically from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\generate_synthetic_benchmark.py
```

The JSONL schema includes an ID, generator version, fixed seed, scenario category, input, and
expected labels for intent, action, risk, safety decision, and retrieval target. The suite covers
support, refunds, payment issues, order status, inventory, delivery, quality, prompt injection,
PII leakage, policy violations, tool use, agent handoff, anomaly detection, and root-cause
analysis. These labels support repeatable experiments; they do not establish real-world impact.

## Customer and support workspace

The local database seed also loads `synthetic-support-v1` from
`apps/api/src/resolveai/synthetic_support.py`. It contains 12 fictional customer profiles, 12
orders, 12 support tickets, 24 ticket messages, and 12 linked operational signals. Identifiers
are UUIDv5 values, timestamps are fixed, addresses use the reserved `.test` domain, and every
record is safe to regenerate with:

```powershell
.\.venv\Scripts\python.exe -m resolveai.seed
```

The `/v1/customers` tenant-scoped endpoint and the Customer 360 page read these records from the
database. Re-running the seed updates the same deterministic records instead of duplicating them.
