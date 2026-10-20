import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from resolveai.commerce import detect_signal_volume_anomaly
from resolveai.config import get_settings
from resolveai.database import TenantSession, create_database_engine, create_session_factory
from resolveai.models import AuditEvent, DetectorSchedule, Tenant


def run_due_once(
    factory: sessionmaker[TenantSession], *, now: datetime | None = None
) -> tuple[int, int]:
    run_at = now or datetime.now(tz=UTC)
    with factory() as root_session:
        tenant_ids = list(root_session.scalars(select(Tenant.id)).all())
    completed = failed = 0
    for tenant_id in tenant_ids:
        with factory() as session:
            session.info["tenant_id"] = tenant_id
            schedules = session.scalars(
                select(DetectorSchedule)
                .where(
                    DetectorSchedule.tenant_id == tenant_id,
                    DetectorSchedule.enabled.is_(True),
                    DetectorSchedule.next_run_at <= run_at,
                )
                .order_by(DetectorSchedule.next_run_at)
                .limit(20)
                .with_for_update(skip_locked=True)
            ).all()
            for schedule in schedules:
                try:
                    config = schedule.configuration_json
                    result = detect_signal_volume_anomaly(
                        session,
                        tenant_id=tenant_id,
                        category=schedule.category,
                        detector=schedule.detector_name,
                        entity_type=schedule.entity_type,
                        entity_id=schedule.entity_id,
                        window_end=run_at,
                        window_minutes=cast(int, config["window_minutes"]),
                        baseline_windows=cast(int, config["baseline_windows"]),
                        minimum_support=cast(int, config["minimum_support"]),
                        threshold=cast(float, config["threshold"]),
                    )
                    schedule.last_run_at = run_at
                    schedule.next_run_at = run_at + timedelta(minutes=schedule.interval_minutes)
                    session.add(
                        AuditEvent(
                            tenant_id=tenant_id,
                            actor_user_id=None,
                            event_type="commerce.detector.schedule.executed",
                            resource_type="detector_schedule",
                            resource_id=schedule.id,
                            trace_id=uuid.uuid4().hex,
                            outcome="success",
                            details_json={
                                "state": result.state,
                                "worker": "detector-worker-v1",
                            },
                        )
                    )
                    session.commit()
                    completed += 1
                except Exception as exc:
                    session.rollback()
                    failed += 1
                    print(
                        f"detector schedule {schedule.id} failed: {type(exc).__name__}",
                        flush=True,
                    )
    return completed, failed


def main() -> None:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    factory = create_session_factory(engine)
    print("ResolveAI detector worker started", flush=True)
    try:
        while True:
            completed, failed = run_due_once(factory)
            if completed or failed:
                print(
                    f"detector worker cycle completed={completed} failed={failed}",
                    flush=True,
                )
            time.sleep(30)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
