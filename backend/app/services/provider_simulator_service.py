import json
import time
import uuid

from app.services.webhook_security_service import (
    generate_signature,
)


def create_payment_webhook(
    *,
    payment_id: uuid.UUID,
    provider_payment_id: str | None = None,
    event_type: str = "payment.succeeded",
    secret: str = "change-me",
    provider_event_id: str | None = None,
):
    """
    Build a signed simulator webhook for a payment.
    """

    if provider_payment_id is None:
        provider_payment_id = (
            f"sim_{payment_id.hex}"
        )

    if provider_event_id is None:
        provider_event_id = (
            f"evt_{uuid.uuid4().hex}"
        )

    timestamp = int(time.time())

    payload = {
        "event_type": event_type,
        "payment_id": str(payment_id),
        "provider_payment_id": provider_payment_id,
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    signature = generate_signature(
        body,
        secret,
        timestamp,
    )

    return {
        "body": body,
        "payload": payload,
        "provider": "SIMULATOR",
        "provider_event_id": provider_event_id,
        "timestamp": timestamp,
        "signature": signature,
        "headers": {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp),
            "X-Provider": "SIMULATOR",
            "X-Provider-Event-Id": provider_event_id,
        },
    }


def create_payment_failed_webhook(
    *,
    payment_id: uuid.UUID,
    failure_code: str = "PAYMENT_FAILED",
    failure_message: str = "Payment failed.",
    secret: str = "change-me",
    provider_event_id: str | None = None,
):
    """
    Build a signed failed-payment webhook.
    """

    if provider_event_id is None:
        provider_event_id = (
            f"evt_{uuid.uuid4().hex}"
        )

    timestamp = int(time.time())

    payload = {
        "event_type": "payment.failed",
        "payment_id": str(payment_id),
        "failure_code": failure_code,
        "failure_message": failure_message,
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    signature = generate_signature(
        body,
        secret,
        timestamp,
    )

    return {
        "body": body,
        "payload": payload,
        "provider": "SIMULATOR",
        "provider_event_id": provider_event_id,
        "timestamp": timestamp,
        "signature": signature,
        "headers": {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp),
            "X-Provider": "SIMULATOR",
            "X-Provider-Event-Id": provider_event_id,
        },
    }


def create_refund_webhook(
    *,
    refund_id: uuid.UUID,
    provider_refund_id: str | None = None,
    secret: str = "change-me",
    provider_event_id: str | None = None,
):
    """
    Build a signed successful refund webhook.
    """

    if provider_refund_id is None:
        provider_refund_id = (
            f"sim_refund_{refund_id.hex}"
        )

    if provider_event_id is None:
        provider_event_id = (
            f"evt_{uuid.uuid4().hex}"
        )

    timestamp = int(time.time())

    payload = {
        "event_type": "refund.succeeded",
        "refund_id": str(refund_id),
        "provider_refund_id": provider_refund_id,
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode("utf-8")

    signature = generate_signature(
        body,
        secret,
        timestamp,
    )

    return {
        "body": body,
        "payload": payload,
        "provider": "SIMULATOR",
        "provider_event_id": provider_event_id,
        "timestamp": timestamp,
        "signature": signature,
        "headers": {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": str(timestamp),
            "X-Provider": "SIMULATOR",
            "X-Provider-Event-Id": provider_event_id,
        },
    }