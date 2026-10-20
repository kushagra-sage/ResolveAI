import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from resolveai.models import OutboxEvent

Publisher = Callable[[str, dict[str, object]], None]


def enqueue(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    topic: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict[str, object],
) -> OutboxEvent:
    event = OutboxEvent(
        tenant_id=tenant_id,
        topic=topic,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload_json=payload,
        available_at=datetime.now(tz=UTC),
    )
    session.add(event)
    session.flush()
    return event


def dispatch_pending(session: Session, publisher: Publisher, limit: int = 100) -> int:
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    events = session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.status == "pending", OutboxEvent.available_at <= datetime.now(tz=UTC))
        .order_by(OutboxEvent.created_at)
        .limit(limit)
    ).all()
    published = 0
    for event in events:
        event.attempts += 1
        try:
            publisher(event.topic, event.payload_json)
        except Exception:
            event.status = "pending"
            continue
        event.status = "published"
        published += 1
    session.flush()
    return published
