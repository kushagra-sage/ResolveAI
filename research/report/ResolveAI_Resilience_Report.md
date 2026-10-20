# ResolveAI resilience experiment

Measured recovery success: **5/5 (100.00%)**.

- evaluation_transient_timeout: recovered=True, final_status=completed
- model_provider_fallback: recovered=True, final_status=fallback_completed
- idempotent_side_effect_retry: recovered=True, final_status=single_stable_receipt
- dead_letter_manual_replay: recovered=True, final_status=completed
- outbox_publisher_outage: recovered=True, final_status=published

This local fault-injection result does not establish production availability.
