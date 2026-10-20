# Evaluation-Driven Production Controls for an Agentic RAG Customer-Operations System

**Draft status:** complete evidence-first manuscript; venue formatting and verified related-work citations remain pre-submission work.

## Abstract

ResolveAI is an agentic retrieval-augmented generation system that connects customer-support reasoning to operational actions while preserving deterministic control boundaries. The system combines tenant-scoped retrieval, input and output guardrails, deterministic policy evaluation, role-separated human approval, idempotent tool execution, verification reads, durable workflow state, audit evidence, cost accounting, and offline/online evaluation. We evaluate these controls against a minimal keyword baseline on 168 fixed-seed synthetic customer-operations cases, then add external intent and prompt-injection tracks. On the synthetic benchmark, ResolveAI obtains 1.0000 answer accuracy and faithfulness, compared with 0.1786 and 0.2143 for the baseline; the paired mean quality improvement is 0.5491 with a 95% bootstrap confidence interval of [0.5097, 0.5863]. A word+character TF-IDF LinearSVC reaches 0.9094 accuracy and macro-F1 on BANKING77. On an independent 116-case injection test, the production regex has zero recall, while a domain-adapted research candidate reaches 0.8000 recall, 0.9796 precision, and 0/3,080 false positives on BANKING77. A local fault-injection experiment recovers 5/5 worker, provider, idempotency, dead-letter, and outbox failures. These results improve external and resilience evidence, but do not establish production business impact, hosted-model latency/cost, or human-review outcomes.

## 1. Introduction

An AI support system becomes operationally consequential when it moves beyond answering a question and changes a refund, order, ticket, shipment, or account. At that boundary, fluent generation is insufficient. The system must identify the authenticated actor and tenant, distinguish evidence from instruction, apply business policy to server-derived facts, obtain independent approval for risky changes, execute a side effect exactly once, verify the authoritative result, and preserve enough evidence to explain the outcome later.

ResolveAI studies this control-plane problem. Its research claim is deliberately narrower than a claim about a new foundation model: **evaluation-driven deterministic controls can improve the reliability, safety, and observability of an agentic RAG workflow on a controlled customer-operations benchmark.** The implementation exposes the same state through an authenticated operations workspace so an operator can inspect the customer context, retrieval lineage, workflow trace, policy decision, approval, tool receipt, cost event, guardrail event, and evaluation result.

The work makes three contributions:

1. An implemented control architecture that joins hybrid retrieval, policy, independent approval, idempotent execution, verification, audit, and evaluation without allowing model output to directly authorize a side effect.
2. A reproducible 168-case paired benchmark with four safety ablations plus external validation on 13,083 public banking-support queries and 662 independent prompt-injection/benign examples.
3. An operational evidence surface that reports stored values, unknown measurements, retries, dead letters, and recovery actions rather than replacing missing evidence with favorable defaults.

The strongest result is not a production-impact claim. It is a controlled finding: on the fixed synthetic cases, the explicit controls raise the paired composite quality score by 0.5491. Evaluation repair also separates direct input-guardrail behavior from broader policy interventions; the previously reported 0.1538 “guardrail false-positive rate” was a metric-definition and amount-unit error and is superseded by the corrected results below.

## 2. Problem formulation

Each benchmark case contains a user message, expected intent, expected context type, expected action, expected risk level, expected policy decision, and a malicious-input label where applicable. A system maps a case to predictions and safety outcomes. We measure intent accuracy, action success, risk accuracy, policy compliance, context recall, answer accuracy, faithfulness, hallucination rate, malicious-input block rate, benign-input false-positive rate, deterministic execution latency, and estimated token usage.

The evaluation treats missing production measurements honestly. Cost per request remains null because the deterministic runner makes no billed provider call. Recovery is measured separately by a local fault-injection experiment rather than being inferred from the task benchmark. The runner never converts missing provider evidence into zero, success, or failure.

The baseline uses simple keyword routing for refunds and orders and has no explicit input safety inspection. ResolveAI uses the checked-in deterministic routing logic, `inspect_input` guardrail, and `evaluate_action` policy engine. Both systems receive the same 168 cases in the same order, enabling a paired comparison.

## 3. System design

### 3.1 Trust and tenancy

The browser authenticates with Keycloak through Authorization Code with PKCE. The API validates the signed token, maps the external subject to an active database user, and loads effective permissions from PostgreSQL. Tenant identity is derived from authenticated state rather than a client-controlled request field. Tenant-owned queries execute through a tenant-aware session, and database constraints and row-level controls form an additional boundary.

Model output is treated as an untrusted proposal. External documents and retrieved chunks are treated as data rather than executable instructions. The application validates typed action schemas, derives sensitive facts from authoritative records, and sends only the normalized action to the policy engine.

### 3.2 Retrieval and knowledge lifecycle

The knowledge subsystem versions documents and chunks, records checksums and metadata, enforces audience and tenant filtering, and preserves source identifiers for citations. Operators can ingest a source, inspect its versions and chunks, run a retrieval test, archive it, and reactivate it. Retrieval records structured failure categories such as zero results, low similarity, conflicting documents, stale policy, or unsupported citations. The resolution workflow can abstain when the evidence does not support an answer.

### 3.3 Policy and approval

The deterministic policy engine returns `ALLOW`, `REQUIRE_APPROVAL`, or `DENY` with a policy version, reason, risk level, approver requirement, facts digest, and action digest. Deny conditions take precedence. An approval authorizes only the exact snapshot and digest presented to the reviewer. Resume revalidates authentication, authorization, current resource state, and policy; an edited action becomes a new proposal rather than silently modifying an authorized one.

The local demonstration thresholds are configuration, not claimed company policy. Low-value refunds can execute autonomously, medium values require one or more reviewers according to the configured band, and values above the hard ceiling are denied inside the AI flow.

### 3.4 Execution and recovery

Before a side effect, the system stores an execution record with a unique idempotency key. A replay checks the stored record or provider receipt instead of blindly issuing the call again. Verification reads determine the final status, including unknown-outcome reconciliation.

The transactional outbox couples committed business state to asynchronous evaluation work. Evaluation jobs use bounded attempts, exponential backoff, and a dead-letter state. The admin health surface displays queue depth, retry counts, job errors, and outbox delivery. It can explicitly replay a dead-letter job, replay a failed outbox event, or requeue work left in a running state by an interrupted worker. Every recovery action creates an audit event.

### 3.5 Evidence and observability

Agent runs and steps preserve the selected versions and node outcomes. Retrieval, tool, cost, guardrail, policy, approval, execution, evaluation, and audit records remain queryable. OpenTelemetry exports traces to a collector; Prometheus stores bounded-cardinality service metrics; Grafana provides dashboards. The web workspace reads these backend records and represents unknown cost separately from known zero cost.

## 4. Experimental method

### 4.1 Dataset

The checked-in dataset `resolveai-benchmark-v1.jsonl` contains 168 synthetic cases generated with seed 20261006. The data represent customer-support and commerce-operation situations without real personally identifiable information. The fixed dataset enables repeatable local testing but does not approximate a statistically sampled production population.

### 4.2 Compared systems

The baseline performs limited keyword mapping and lacks explicit policy and guardrail controls. It is intentionally minimal and should not be interpreted as a state-of-the-art agentic baseline. ResolveAI applies the implemented router, input inspection, action selection, risk classification, and policy evaluation. This comparison isolates the effect of the checked-in controls but does not separate their individual contributions.

### 4.3 Metrics and statistics

For each case, the runner emits raw JSON and CSV predictions. Aggregate metrics are proportions over the applicable cases. Hallucination rate is the complement of faithfulness in this deterministic benchmark. Guardrail block rate uses malicious cases; false-positive rate uses benign cases. Latency measures only local Python logic using a high-resolution clock. Estimated tokens are derived from the deterministic input/output representation and are not provider billing records.

The primary statistic is the per-case difference in a composite quality score covering intent, action, risk, policy, context, answer, and faithfulness. The runner performs 2,000 paired bootstrap resamples using the fixed experiment seed and reports the 2.5th and 97.5th percentiles.

### 4.4 Reproducibility

Running `python scripts/run_research_benchmark.py` regenerates raw JSON/CSV, the summary JSON, comparison table, figure, and evaluation report. The repository also contains the API, seed data, Compose topology, and automated tests needed to reproduce the local application state.

### 4.5 External-data and resilience tracks

We selected BANKING77 because its official repository is CC BY 4.0 and provides 10,003 training and 3,080 held-out online-banking support queries over 77 intents [Casanueva et al., 2020]. The acquisition script pins the upstream commit, verifies both SHA-256 checksums, records provenance, and performs a limited email/long-number privacy scan. We compare word/bigram Multinomial Naive Bayes with a stronger word+character TF-IDF LinearSVC, while applying the ResolveAI input guardrail to the test split as benign traffic. BANKING77 does not contain action, retrieval, approval, or business-outcome labels, so it is not used to claim end-to-end product accuracy.

An independent deepset prompt-injection corpus contributes 546 training and 116 test examples. The repository revision and response checksums are fixed, and both license notices from the source card are preserved. We compare the production regex, a general TF-IDF LinearSVC, and a domain-adapted model trained with BANKING77 training queries as additional benign examples. Learned models remain research candidates rather than silently replacing a production security control.

The resilience track injects evaluator timeout, model-provider timeout, duplicate side-effect retry, dead-letter replay, and publisher outage against the implemented provider, adapter, and PostgreSQL-backed evaluation/outbox functions. This remains a local injected-failure experiment, not a production availability test. A separate 100-request run measures actual deterministic-adapter latency and token counts; it does not represent networked model latency.

## 5. Results

| Metric | Minimal baseline | ResolveAI | Difference |
|---|---:|---:|---:|
| Intent accuracy | 0.2500 | 1.0000 | +0.7500 |
| Action success | 0.2143 | 1.0000 | +0.7857 |
| Risk accuracy | 0.2500 | 0.9643 | +0.7143 |
| Policy compliance | 0.4643 | 1.0000 | +0.5357 |
| Context recall | 0.2143 | 1.0000 | +0.7857 |
| Answer accuracy | 0.1786 | 1.0000 | +0.8214 |
| Faithfulness | 0.2143 | 1.0000 | +0.7857 |
| Hallucination rate ↓ | 0.7857 | 0.0000 | −0.7857 |
| Malicious-input block rate | 0.0000 | 1.0000 | +1.0000 |
| Safety-intervention false-positive rate ↓ | 0.0000 | 0.0000 | 0.0000 |
| Direct input-guardrail block rate | 0.0000 | 0.5000 | +0.5000 |
| Direct input-guardrail false-positive rate ↓ | 0.0000 | 0.0000 | 0.0000 |
| Mean estimated tokens ↓ | 29.82 | 53.82 | +24.00 |

The paired mean composite quality difference is **+0.5491**, with a paired bootstrap 95% confidence interval of **[0.5097, 0.5863]**. The interval excludes zero for this fixed synthetic workload. Because the deterministic rules and cases were developed in the same project, the perfect task metrics should be interpreted as fixture coverage, not estimated production accuracy.

ResolveAI's combined safety controls intervene on 100% of the project-authored malicious inputs. The direct regex recognizes 50.00%, while additional injection, exfiltration, and policy routes account for the remainder. Independent testing changes the conclusion: the same regex recognizes 0/60 injection examples in the deepset test split. A general TF-IDF LinearSVC reaches 83.33% recall but falsely flags 270/3,080 BANKING77 queries. Domain adaptation reduces those banking false positives to zero and obtains 80.00% injection recall, 97.96% precision, and one false positive among 56 generic benign examples. This external result demonstrates that project-authored attack success did not generalize.

On BANKING77, word/bigram Naive Bayes reaches **0.8620 accuracy** and **0.8614 macro-F1**; the word+character TF-IDF LinearSVC reaches **0.9094 accuracy** and **0.9094 macro-F1**. These results evaluate intent classification rather than the entire agentic workflow. The resilience experiment recovers **5/5** scenarios. A 100-request deterministic-adapter run measures P50/P95 latencies of approximately 0.0042/0.0060 ms and mean token counts of 17.19 input and 7.00 output; these values represent only in-process local adapter overhead.

## 6. Operational validation

The project includes 71 passing backend tests that exercise tenant isolation, authentication and authorization, retrieval, policies, approvals, execution, evaluation, CommerceOps, webhooks, outbox behavior, durable workers, and console APIs. A Chromium suite executes 13 authenticated end-to-end, accessibility, and screenshot workflows. These tests validate implementation behavior; they do not substitute for production reliability testing.

The full local topology runs eleven containers: PostgreSQL/pgvector, Redis, Keycloak, SeaweedFS, API, detector worker, durable evaluation/outbox worker, OpenTelemetry Collector, Prometheus, Grafana, and the React web application. The system health page obtains live queue and recovery state from PostgreSQL. Customer 360 obtains deterministic synthetic support records rather than static frontend fixtures.

## 7. Related work

ResolveAI sits at the intersection of retrieval-augmented generation, tool-using language-model agents, AI guardrails, human-in-the-loop decision systems, and LLM evaluation/observability. BANKING77 was introduced as a 13,083-example, 77-intent single-domain benchmark by Casanueva et al. (2020), and provides the external intent and benign-query track used here. TweetSumm provides 1,100 reconstructed real-world customer-support dialogs with human extractive and abstractive summaries [Feigenblat et al., 2021], but ResolveAI defers its use pending a separate review of the underlying Twitter/Kaggle data terms. A submission-quality related-work section still requires verified primary sources for RAG, agent/tool use, guardrails, human approval, and observability.

- Casanueva, I., Temčinas, T., Gerz, D., Henderson, M., & Vulić, I. (2020). Efficient Intent Detection with Dual Sentence Encoders. *NLP4ConvAI*. https://doi.org/10.18653/v1/2020.nlp4convai-1.5
- Feigenblat, G., Gunasekara, C., Sznajder, B., Joshi, S., Konopnicki, D., & Aharonov, R. (2021). TWEETSUMM—A Dialog Summarization Dataset for Customer Service. *Findings of EMNLP*. https://doi.org/10.18653/v1/2021.findings-emnlp.24

The intended distinction is architectural rather than model-centric. ResolveAI does not introduce a new retrieval algorithm, model architecture, or learned policy. It evaluates how explicit, composable production controls change behavior and make failures inspectable in a customer-operations workflow.

## 8. Limitations and threats to validity

**Synthetic end-to-end labels, partially mitigated.** The action/policy benchmark and product records remain synthetic. BANKING77 adds 13,083 public real-world support queries for intent and benign-input validation, but lacks ResolveAI action, retrieval, approval, and business-outcome labels.

**Weak end-to-end baseline, substantially mitigated.** The keyword end-to-end baseline remains weak, but the external intent track now includes a 90.94%-accuracy word+character TF-IDF LinearSVC. A true agentic RAG baseline and reviewed hosted-model comparison still require a selected model endpoint.

**Limited component ablations.** The runner now emits no-safety-controls, no-guardrail, no-policy, and full variants in `component-ablations.csv`. The result reveals overlap between direct guardrails and additional safety routing, but retrieval, approval, and execution ablations still require purpose-built labels.

**Local deterministic latency.** The provider harness now records actual local adapter latency and returned token counts, but the measured sub-millisecond values exclude network calls, hosted models, vector-service contention, approval wait time, and provider tail behavior. They must not appear as end-user service latency.

**Hosted resource use.** The OpenAI-compatible harness records returned usage and calculates cost only when supplied a dated price snapshot. The deterministic run has no provider bill. Hosted monetary cost remains null because no reviewed endpoint credentials or price snapshot were available.

**Local resilience only.** Five injected failures recover successfully, including evaluator retry, model fallback, idempotent side-effect replay, dead-letter replay, and eventual outbox publication. Cloud-region loss, real provider outages, high load, and long-duration soak behavior remain unmeasured.

**Guardrail generalization.** The production regex obtains zero recall on the independent prompt-injection test despite perfect combined safety behavior on project-authored cases. A domain-adapted TF-IDF LinearSVC reaches 80.00% recall with one generic-benign false positive and zero BANKING77 false positives. The candidate requires artifact governance, threshold review, multilingual evaluation, and adaptive-attack testing before deployment.

**Human factors, execution-ready.** The repository includes a blinded protocol, 144 pilot assignments for 12 participants with 12 cases each from a balanced 24-case pool, four Google Form variants, a separated blinding key, consent script, collection template, and pre-specified analysis. No participants have been recruited, so reviewer agreement, decision time, approval fatigue, and trust remain unknown.

## 9. Broader impact and ethics

Governed automation could shorten resolution time and improve consistency, but it could also scale incorrect policy, deny legitimate requests, expose customer data, or create automation bias. ResolveAI limits these risks through tenant boundaries, minimal telemetry, deterministic deny rules, exact-action approval, audit evidence, and explicit abstention. These mechanisms reduce risk; they do not remove organizational responsibility. A real deployment requires privacy review, retention rules, accessibility validation, bias analysis, incident response, human override procedures, and monitoring for differential failure across customer groups.

## 10. Future work

The next externally dependent experiments should run the included provider harness against a reviewed model endpoint, execute the prepared human study after faculty/ethics approval, and obtain an authorized labeled action/outcome dataset. Local next steps should package and govern the learned injection detector, add multilingual and adaptive attacks, and design retrieval/approval labels that isolate each component.

## 11. Conclusion

ResolveAI demonstrates a complete local path from authenticated customer context through retrieval, policy, approval, execution, verification, audit, and evaluation. On 168 fixed synthetic cases, its deterministic controls improve paired composite quality by 0.5491 over a minimal baseline. External intent validation reaches 90.94% accuracy, independent injection testing exposes zero regex recall and yields an 80%-recall domain-adapted candidate, and local resilience testing recovers all five injected failures. The appropriate conclusion remains specific: the controls improve a controlled workload and make previously hidden failure modes measurable. Hosted agentic baselines, real action outcomes, governed detector deployment, and an approved human study remain necessary before claiming general or production impact.
