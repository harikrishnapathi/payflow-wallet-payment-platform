import uuid

from app.models.provider_event import (
    ProviderEventStatus,
)
from app.services.webhook_processing_service import (
    WebhookProcessingError,
    process_provider_webhook,
)


def test_unknown_event_is_ignored(db):
    event = process_provider_webhook(
        db,
        provider="SIMULATOR",
        provider_event_id=f"evt-{uuid.uuid4()}",
        event_type="unknown.event",
        payload={},
    )

    assert event.status == (
        ProviderEventStatus.IGNORED
    )
    assert event.processed_at is not None


def test_missing_payment_id_fails(db):
    event_id = f"evt-{uuid.uuid4()}"

    try:
        process_provider_webhook(
            db,
            provider="SIMULATOR",
            provider_event_id=event_id,
            event_type="payment.succeeded",
            payload={},
        )
    except WebhookProcessingError:
        pass
    else:
        raise AssertionError(
            "Expected WebhookProcessingError"
        )

    event = db.query(
        __import__(
            "app.models.provider_event",
            fromlist=["ProviderEvent"],
        ).ProviderEvent
    ).filter_by(
        provider="SIMULATOR",
        provider_event_id=event_id,
    ).first()

    assert event is not None
    assert event.status == (
        ProviderEventStatus.FAILED
    )
    assert event.attempts >= 1
    assert event.last_error is not None


def test_duplicate_processed_event_is_not_reprocessed(
    db,
):
    event_id = f"evt-{uuid.uuid4()}"

    first = process_provider_webhook(
        db,
        provider="SIMULATOR",
        provider_event_id=event_id,
        event_type="unknown.event",
        payload={},
    )

    second = process_provider_webhook(
        db,
        provider="SIMULATOR",
        provider_event_id=event_id,
        event_type="unknown.event",
        payload={},
    )

    assert first.id == second.id
    assert second.status == (
        ProviderEventStatus.IGNORED
    )