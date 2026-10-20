# Security

ResolveAI treats authentication, tenant isolation, authorization, policy, approval, and tool execution as deterministic boundaries. Model output is never accepted as authorization. JWT tenant/user identity is matched to active database records; roles and permissions come from the database. PostgreSQL row-level security and ORM criteria provide defense in depth.

Sensitive actions require a typed action, policy decision, immutable digest, and—when required—a non-self approval by an authorized reviewer. Tools validate strict schemas and idempotency keys before side effects. Raw payment secrets and destination changes are denied.

External knowledge and tool content is untrusted data. Guardrails quarantine embedded instruction patterns and redact known secret/PII forms before downstream boundaries. Telemetry uses hashes and bounded labels rather than prompts, user IDs, or PII.

Report vulnerabilities privately to the repository owner. Do not include real customer data or credentials. Rotate any exposed credential and preserve relevant audit records.

Current limitations: pattern-based detectors are defense-in-depth rather than a complete DLP system; provider credentials and production IdP integration are deployment responsibilities; a formal penetration test has not yet been run.
