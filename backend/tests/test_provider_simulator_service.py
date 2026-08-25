import json
import uuid

from app.services.provider_simulator_service import (
    create_payment_failed_webhook,
    create_payment_webhook,
)
from app.services.webhook_security_service import (
    verify_signature,
)


SECRET = "change-me"


def test_payment_webhook_contains_required_data():
    payment_id = uuid.uuid4()

    event = create_payment_webhook(
        payment_id=payment_id,
        secret=SECRET,
    )

    assert event["provider"] == "SIMULATOR"
    assert event["provider_event_id"]
    assert event["timestamp"]
    assert event["signature"]

    assert event["payload"]["event_type"] == (
        "payment.succeeded"
    )

    assert event["payload"]["payment_id"] == (
        str(payment_id)
    )


def test_payment_webhook_signature_is_valid():
    payment_id = uuid.uuid4()

    event = create_payment_webhook(
        payment_id=payment_id,
        secret=SECRET,
    )

    assert verify_signature(
        event["body"],
        event["signature"],
        SECRET,
        event["timestamp"],
        now=event["timestamp"],
    )


def test_payment_webhook_body_matches_payload():
    payment_id = uuid.uuid4()

    event = create_payment_webhook(
        payment_id=payment_id,
        secret=SECRET,
    )

    decoded = json.loads(
        event["body"].decode("utf-8")
    )

    assert decoded == event["payload"]


def test_failed_payment_webhook():
    payment_id = uuid.uuid4()

    event = create_payment_failed_webhook(
        payment_id=payment_id,
        secret=SECRET,
    )

    assert event["payload"]["event_type"] == (
        "payment.failed"
    )

    assert event["payload"]["payment_id"] == (
        str(payment_id)
    )

    assert (
        event["payload"]["failure_code"]
        == "PAYMENT_FAILED"
    )

    assert verify_signature(
        event["body"],
        event["signature"],
        SECRET,
        event["timestamp"],
        now=event["timestamp"],
    )


def test_provider_event_ids_are_unique():
    payment_id = uuid.uuid4()

    first = create_payment_webhook(
        payment_id=payment_id,
        secret=SECRET,
    )

    second = create_payment_webhook(
        payment_id=payment_id,
        secret=SECRET,
    )

    assert (
        first["provider_event_id"]
        != second["provider_event_id"]
    )