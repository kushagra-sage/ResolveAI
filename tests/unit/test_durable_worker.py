import uuid

from resolveai.database import create_database_engine, create_session_factory
from resolveai.durable_worker import run_due_once
from resolveai.evaluation import enqueue_online_evaluation
from resolveai.models import EvaluationJob, OutboxEvent
from resolveai.outbox import enqueue
from resolveai.seed import seed_id
from sqlalchemy import select


def test_durable_worker_drains_evaluation_and_outbox(database_url: str) -> None:
    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    tenant_id = seed_id("tenant:acme")
    request_key = f"durable-worker-test:{uuid.uuid4()}"
    aggregate_id = uuid.uuid4()
    with factory() as session:
        session.info["tenant_id"] = tenant_id
        enqueue_online_evaluation(
            session,
            tenant_id=tenant_id,
            request_key=request_key,
            payload={
                "run_id": str(uuid.uuid4()),
                "intent": "order_status",
                "risk_level": "low",
                "status": "completed",
                "has_approval": False,
            },
        )
        event = enqueue(
            session,
            tenant_id=tenant_id,
            topic="test.completed",
            aggregate_type="test",
            aggregate_id=aggregate_id,
            payload={"test_id": str(aggregate_id)},
        )
        event_id = event.id
        session.commit()

    delivered: list[str] = []
    assert run_due_once(factory, publisher=lambda topic, _payload: delivered.append(topic)) == (
        1,
        0,
        1,
    )

    with factory() as session:
        session.info["tenant_id"] = tenant_id
        job = session.scalar(select(EvaluationJob).where(EvaluationJob.request_key == request_key))
        event = session.get(OutboxEvent, event_id)
        assert job is not None and job.status == "completed"
        assert job.result_json["schema_valid"] is True
        assert event is not None and event.status == "published"
    assert delivered == ["test.completed"]
    engine.dispose()
