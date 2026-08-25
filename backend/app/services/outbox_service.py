import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.outbox_event import (
    OutboxEvent,
    OutboxEventStatus,
)


def create_outbox_event(
    db: Session,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: dict,
) -> OutboxEvent:
    event = OutboxEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        status=OutboxEventStatus.PENDING,
        attempts=0,
    )

    db.add(event)
    db.flush()

    return event
