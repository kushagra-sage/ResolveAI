# Evaluation

Evaluation cases contain the question, expected answer terms/documents/action, forbidden action, category, difficulty, and risk. Dataset hashes bind every run to exact inputs. Deterministic evaluators cover term/context recall, citation correctness, action correctness, and the safety invariant. Model-judge adapters can be added, but judge failure must remain distinct from score zero.

Run:

```bash
python scripts/run_eval.py datasets/eval/smoke-v1.json
```

The command writes JSON and Markdown artifacts under the ignored `artifacts/evaluations` directory. These results are synthetic fixture measurements, not production claims. Reports include their completed sample count and dataset hash. Missing cases or interrupted runs must not receive fabricated scores.

Regression gates distinguish `MISSING_METRIC`, `EVALUATOR_FAILURE`, `INSUFFICIENT_SAMPLES`, and `THRESHOLD_BREACH`. Safety failures cannot be offset by aggregate quality.

## Research evidence suite

```bash
python scripts/prepare_banking77.py
python scripts/prepare_prompt_injection_dataset.py
python scripts/run_banking77_validation.py
python scripts/run_guardrail_validation.py
python scripts/run_research_benchmark.py
python scripts/run_resilience_experiment.py
python scripts/run_provider_measurement.py --mode deterministic --sample-size 100
python scripts/prepare_human_study.py
```

The first command downloads the official CC BY 4.0 BANKING77 files at a pinned commit and
verifies their SHA-256 checksums. The prompt-injection acquisition command pins the public
deepset corpus and preserves its mixed license notices. The validation commands evaluate
Naive Bayes and TF-IDF LinearSVC intent baselines plus regex and learned injection detectors.
The paired benchmark exports four safety ablations. The resilience experiment injects worker,
provider, idempotency, dead-letter, and outbox failures. The final commands measure deterministic
adapter overhead and prepare a blinded, counterbalanced human-study assignment pack.

Outputs are written under `research/results`, `research/tables`, `research/figures`, and
`research/report`. Hosted-provider cost/latency remains unmeasured until reviewed credentials and
pricing are configured. Human-study outcomes remain unmeasured until faculty/ethics approval and
participant recruitment.
