# Limitations closure status

| Original limitation | Maximum current mitigation | Evidence and remaining boundary |
|---|---|---|
| Synthetic-only evaluation | Substantially mitigated | BANKING77 adds 13,083 public support queries. The independent deepset corpus adds 662 prompt-injection/benign examples. Real ResolveAI action and business-outcome labels still require authorized organizational data. |
| Weak keyword baseline | Substantially mitigated | Naive Bayes reaches 86.20% accuracy; word+character TF-IDF LinearSVC reaches 90.94% accuracy and 90.94% macro-F1 across 77 BANKING77 intents. A true agentic RAG baseline requires a selected model/provider. |
| No component ablations | Mitigated locally | The benchmark exports baseline, no-safety-controls, no-guardrail, no-policy, and full variants. Routing, retrieval, and approval need a new dataset designed to isolate those components. |
| Local deterministic latency | Measurement path complete | A 100-request local adapter run records actual P50/P95 and token counts. The OpenAI-compatible harness is ready, but network/provider latency requires an endpoint and credentials. |
| Estimated tokens/no monetary cost | Measurement path complete | The provider harness reads returned token counts and accepts dated input/output prices. Local deterministic execution has no provider bill; hosted cost cannot be manufactured without a provider run. |
| No fault injection | Resolved locally | 5/5 evaluator retry, provider fallback, idempotent side-effect retry, dead-letter replay, and outbox outage scenarios recover. Region loss, real outages, and load contention remain production tests. |
| Guardrail false positives/coverage | Independently quantified and candidate built | The production regex has 0% recall on the independent 116-case test, revealing poor generalization. A domain-adapted word+character TF-IDF LinearSVC reaches 80.00% recall, 97.96% precision, 1.79% benchmark FPR, and 0/3,080 BANKING77 false positives. It remains a research candidate until artifact and threshold governance are approved. |
| No human factors study | Execution-ready, not conducted | A 12-participant pilot pack assigns 12 cases per person from a balanced 24-case pool and includes four Google Form variants, a blinding key, consent script, template, and pre-specified analysis. Results require faculty/ethics approval and real consenting participants. |

## What cannot honestly be closed inside this workstation

Three boundaries require new authority or external state: access to organizational customer/action
outcomes, credentials and dated pricing for a hosted model, and approved human participants. The
repository now contains runnable protocols for all three; it deliberately contains no fabricated
traffic, invoices, or participant responses.
