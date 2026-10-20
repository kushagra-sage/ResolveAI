"""Inject recoverable worker failures and record measured recovery outcomes."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from resolveai.adapters.mock import MockPaymentAdapter
from resolveai.config import get_settings
from resolveai.database import create_database_engine, create_session_factory
from resolveai.evaluation import enqueue_online_evaluation, process_online_evaluations
from resolveai.models import EvaluationJob, OutboxEvent
from resolveai.outbox import dispatch_pending, enqueue
from resolveai.providers import FallbackRouter, ModelResponse
from resolveai.seed import seed_id


def make_due(job: EvaluationJob) -> None:
    job.available_at = datetime.now(tz=UTC)


def run(research_dir: Path) -> dict[str, object]:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    factory = create_session_factory(engine)
    tenant_id = seed_id("tenant:acme")
    experiment_id = uuid.uuid4().hex
    created_job_ids: list[uuid.UUID] = []
    created_event_ids: list[uuid.UUID] = []
    scenarios: list[dict[str, object]] = []
    try:
        # Transient evaluator errors should recover within the bounded retry budget.
        attempts = 0
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            job = enqueue_online_evaluation(
                session,
                tenant_id=tenant_id,
                request_key=f"resilience-transient-{experiment_id}",
                payload={"experiment": experiment_id},
            )
            assert job is not None
            created_job_ids.append(job.id)
            session.commit()
        for _ in range(3):
            with factory() as session:
                session.info["tenant_id"] = tenant_id

                def transient(_payload: dict[str, object]) -> dict[str, object]:
                    nonlocal attempts
                    attempts += 1
                    if attempts < 3:
                        raise TimeoutError("injected evaluator timeout")
                    return {"recovered": True}

                process_online_evaluations(session, transient, limit=1)
                current = session.get(EvaluationJob, created_job_ids[-1])
                assert current is not None
                if current.status == "pending":
                    make_due(current)
                session.commit()
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            current = session.get(EvaluationJob, created_job_ids[-1])
            assert current is not None
            scenarios.append(
                {
                    "scenario": "evaluation_transient_timeout",
                    "recovered": current.status == "completed" and current.attempts == 3,
                    "attempts": current.attempts,
                    "final_status": current.status,
                }
            )

        # A bounded model retry must fail over without returning an empty response.
        provider_calls: list[str] = []

        def unavailable(_prompt: str) -> ModelResponse:
            provider_calls.append("primary")
            raise TimeoutError("injected model timeout")

        def fallback(_prompt: str) -> ModelResponse:
            provider_calls.append("fallback")
            return ModelResponse("safe fallback", "local", "fallback-v1", 3, 2)

        response = FallbackRouter(
            [("primary", unavailable), ("fallback", fallback)],
            max_attempts_per_provider=2,
        ).complete("research fault injection")
        scenarios.append(
            {
                "scenario": "model_provider_fallback",
                "recovered": response.text == "safe fallback"
                and provider_calls == ["primary", "primary", "fallback"],
                "attempts": len(provider_calls),
                "final_status": "fallback_completed",
            }
        )

        # Duplicate side-effect retries must return one stable provider receipt.
        payment = MockPaymentAdapter()
        refund = {
            "tenant_id": str(tenant_id),
            "payment_ref": "PAY-RESILIENCE-001",
            "amount_minor": 2_500,
            "currency": "INR",
            "idempotency_key": f"resilience-refund-{experiment_id}",
        }
        first = payment.refund(**refund)
        replay = payment.refund(**refund)
        scenarios.append(
            {
                "scenario": "idempotent_side_effect_retry",
                "recovered": first["replayed"] is False
                and replay["replayed"] is True
                and first["refund_ref"] == replay["refund_ref"],
                "attempts": 2,
                "final_status": "single_stable_receipt",
            }
        )

        # Exhaust retries, then exercise the same state transition used by admin replay.
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            job = enqueue_online_evaluation(
                session,
                tenant_id=tenant_id,
                request_key=f"resilience-dead-letter-{experiment_id}",
                payload={"experiment": experiment_id},
            )
            assert job is not None
            created_job_ids.append(job.id)
            session.commit()
        for _ in range(3):
            with factory() as session:
                session.info["tenant_id"] = tenant_id

                def permanent(_payload: dict[str, object]) -> dict[str, object]:
                    raise ConnectionError("injected provider outage")

                process_online_evaluations(session, permanent, limit=1)
                current = session.get(EvaluationJob, created_job_ids[-1])
                assert current is not None
                if current.status == "pending":
                    make_due(current)
                session.commit()
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            current = session.get(EvaluationJob, created_job_ids[-1])
            assert current is not None and current.status == "dead_letter"
            current.status = "pending"
            current.attempts = 0
            current.error_category = None
            make_due(current)
            session.commit()
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            process_online_evaluations(session, lambda _payload: {"replayed": True}, limit=1)
            current = session.get(EvaluationJob, created_job_ids[-1])
            assert current is not None
            session.commit()
            scenarios.append(
                {
                    "scenario": "dead_letter_manual_replay",
                    "recovered": current.status == "completed",
                    "attempts_after_replay": current.attempts,
                    "final_status": current.status,
                }
            )

        # A publisher failure must retain the outbox event and later publish it once.
        publisher_calls = 0
        delivered: list[str] = []
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            event = enqueue(
                session,
                tenant_id=tenant_id,
                topic="research.resilience",
                aggregate_type="experiment",
                aggregate_id=uuid.uuid4(),
                payload={"experiment": experiment_id},
            )
            created_event_ids.append(event.id)
            session.commit()

        def flaky_publisher(topic: str, _payload: dict[str, object]) -> None:
            nonlocal publisher_calls
            publisher_calls += 1
            if publisher_calls == 1:
                raise ConnectionError("injected broker outage")
            delivered.append(topic)

        for _ in range(2):
            with factory() as session:
                session.info["tenant_id"] = tenant_id
                dispatch_pending(session, flaky_publisher, limit=1)
                session.commit()
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            event = session.get(OutboxEvent, created_event_ids[-1])
            assert event is not None
            scenarios.append(
                {
                    "scenario": "outbox_publisher_outage",
                    "recovered": (
                        event.status == "published" and delivered == ["research.resilience"]
                    ),
                    "attempts": event.attempts,
                    "final_status": event.status,
                    "deliveries": len(delivered),
                }
            )
        recovered = sum(bool(item["recovered"]) for item in scenarios)
        summary: dict[str, object] = {
            "benchmark": "resolveai-resilience-v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "scenario_count": len(scenarios),
            "recovered_count": recovered,
            "fallback_recovery_success": recovered / len(scenarios),
            "scenarios": scenarios,
            "limitations": [
                "The experiment runs against local PostgreSQL and injected exceptions.",
                "It does not measure cloud-region loss, real provider outages, or load contention.",
            ],
        }
        results = research_dir / "results"
        report = research_dir / "report"
        results.mkdir(parents=True, exist_ok=True)
        report.mkdir(parents=True, exist_ok=True)
        (results / "resilience-v1-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        (report / "ResolveAI_Resilience_Report.md").write_text(
            "# ResolveAI resilience experiment\n\n"
            f"Measured recovery success: **{recovered}/{len(scenarios)} "
            f"({summary['fallback_recovery_success']:.2%})**.\n\n"
            + "\n".join(
                f"- {item['scenario']}: recovered={item['recovered']}, "
                f"final_status={item['final_status']}"
                for item in scenarios
            )
            + "\n\nThis local fault-injection result does not establish production availability.\n",
            encoding="utf-8",
        )
        return summary
    finally:
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            for identifier in created_job_ids:
                item = session.get(EvaluationJob, identifier)
                if item is not None:
                    session.delete(item)
            for identifier in created_event_ids:
                item = session.get(OutboxEvent, identifier)
                if item is not None:
                    session.delete(item)
            session.commit()
        engine.dispose()


if __name__ == "__main__":
    print(json.dumps(run(Path("research")), indent=2))
