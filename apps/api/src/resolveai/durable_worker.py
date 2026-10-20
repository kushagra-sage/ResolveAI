import time
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from resolveai.config import get_settings
from resolveai.database import TenantSession, create_database_engine, create_session_factory
from resolveai.evaluation import process_online_evaluations
from resolveai.models import Tenant
from resolveai.outbox import dispatch_pending


def evaluate_online_payload(payload: dict[str, object]) -> dict[str, object]:
    required = {"run_id", "intent", "risk_level", "status", "has_approval"}
    missing = sorted(required - payload.keys())
    return {
        "evaluator": "online-deterministic-v1",
        "schema_valid": not missing,
        "missing_fields": missing,
        "completed": payload.get("status") == "completed",
        "approval_path": bool(payload.get("has_approval")),
    }


def log_publisher(topic: str, payload: dict[str, object]) -> None:
    aggregate_reference = next(
        (str(value) for key, value in payload.items() if key.endswith("_id")),
        "none",
    )
    print(f"outbox published topic={topic} aggregate={aggregate_reference}", flush=True)


def run_due_once(
    factory: sessionmaker[TenantSession],
    *,
    publisher: Callable[[str, dict[str, object]], None] = log_publisher,
) -> tuple[int, int, int]:
    with factory() as root_session:
        tenant_ids = list(root_session.scalars(select(Tenant.id)).all())
    completed = failed = published = 0
    for tenant_id in tenant_ids:
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            tenant_completed, tenant_failed = process_online_evaluations(
                session,
                evaluate_online_payload,
                limit=100,
            )
            tenant_published = dispatch_pending(session, publisher, limit=1000)
            session.commit()
            completed += tenant_completed
            failed += tenant_failed
            published += tenant_published
    return completed, failed, published


def main() -> None:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    factory = create_session_factory(engine)
    print("ResolveAI durable worker started", flush=True)
    try:
        while True:
            completed, failed, published = run_due_once(factory)
            if completed or failed or published:
                print(
                    "durable worker cycle "
                    f"evaluations_completed={completed} evaluations_failed={failed} "
                    f"outbox_published={published}",
                    flush=True,
                )
            time.sleep(5)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
