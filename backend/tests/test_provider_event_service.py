from app.models.provider_event import (
    ProviderEventStatus,
)
from app.services.provider_event_service import (
    mark_provider_event_failed,
    mark_provider_event_processed,
    receive_provider_event,
)


def test_provider_event_is_received(db):
    event = receive_provider_event(
        db,
        provider="SIMULATOR",
        provider_event_id="evt_001",
        event_type="payment.succeeded",
        payload={
            "payment_id": "pay_001",
        },
    )

    assert event.provider == "SIMULATOR"
    assert event.provider_event_id == "evt_001"
    assert event.status == ProviderEventStatus.RECEIVED
    assert event.attempts == 0


def test_duplicate_provider_event_is_idempotent(db):
    first = receive_provider_event(
        db,
        provider="SIMULATOR",
        provider_event_id="evt_002",
        event_type="payment.succeeded",
        payload={
            "payment_id": "pay_002",
        },
    )

    second = receive_provider_event(
        db,
        provider="SIMULATOR",
        provider_event_id="evt_002",
        event_type="payment.succeeded",
        payload={
            "payment_id": "pay_002",
        },
    )

    assert first.id == second.id


def test_provider_event_can_be_processed(db):
    event = receive_provider_event(
        db,
        provider="SIMULATOR",
        provider_event_id="evt_003",
        event_type="payment.succeeded",
        payload={},
    )

    processed = mark_provider_event_processed(
        db,
        event,
    )

    assert processed.status == ProviderEventStatus.PROCESSED
    assert processed.processed_at is not None
    assert processed.last_error is None


def test_provider_event_failure_is_recorded(db):
    event = receive_provider_event(
        db,
        provider="SIMULATOR",
        provider_event_id="evt_004",
        event_type="payment.succeeded",
        payload={},
    )

    failed = mark_provider_event_failed(
        db,
        event,
        "Temporary processing failure",
    )

    assert failed.status == ProviderEventStatus.FAILED
    assert failed.attempts == 1
    assert failed.last_error == (
        "Temporary processing failure"
    )