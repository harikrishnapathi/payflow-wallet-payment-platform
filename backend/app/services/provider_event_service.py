import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.provider_event import (
    ProviderEvent,
    ProviderEventStatus,
)


class DuplicateProviderEvent(Exception):
    pass


def receive_provider_event(
    db: Session,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload: dict,
) -> ProviderEvent:
    """
    Persist a provider webhook exactly once.

    The database unique constraint on
    (provider, provider_event_id) is the final
    idempotency guarantee.
    """

    existing = db.scalar(
        select(ProviderEvent)
        .where(
            ProviderEvent.provider == provider,
            ProviderEvent.provider_event_id
            == provider_event_id,
        )
    )

    if existing:
        return existing

    event = ProviderEvent(
        id=uuid.uuid4(),
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        payload=payload,
        status=ProviderEventStatus.RECEIVED,
        attempts=0,
    )

    db.add(event)
    db.flush()

    return event


def mark_provider_event_processed(
    db: Session,
    event: ProviderEvent,
) -> ProviderEvent:
    event.status = ProviderEventStatus.PROCESSED
    event.processed_at = datetime.now(
        timezone.utc
    )
    event.last_error = None

    db.flush()

    return event


def mark_provider_event_failed(
    db: Session,
    event: ProviderEvent,
    error: str,
) -> ProviderEvent:
    event.status = ProviderEventStatus.FAILED
    event.attempts += 1
    event.last_error = error

    db.flush()

    return event