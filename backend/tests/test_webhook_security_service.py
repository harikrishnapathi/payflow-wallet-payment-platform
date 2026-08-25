import json

from app.services.webhook_security_service import (
    generate_signature,
    verify_signature,
)


SECRET = "payflow-webhook-secret"


def test_generate_and_verify_signature():
    payload = json.dumps(
        {
            "event": "payment.succeeded",
            "payment_id": "payment-123",
        },
        separators=(",", ":"),
    ).encode()

    timestamp = 1_000_000

    signature = generate_signature(
        payload,
        SECRET,
        timestamp,
    )

    assert signature.startswith("sha256=")

    assert verify_signature(
        payload,
        signature,
        SECRET,
        timestamp,
        now=timestamp,
    )


def test_invalid_signature_is_rejected():
    payload = b'{"event":"payment.succeeded"}'

    timestamp = 1_000_000

    assert not verify_signature(
        payload,
        "sha256=invalid",
        SECRET,
        timestamp,
        now=timestamp,
    )


def test_wrong_secret_is_rejected():
    payload = b'{"event":"payment.succeeded"}'

    timestamp = 1_000_000

    signature = generate_signature(
        payload,
        SECRET,
        timestamp,
    )

    assert not verify_signature(
        payload,
        signature,
        "wrong-secret",
        timestamp,
        now=timestamp,
    )


def test_expired_webhook_is_rejected():
    payload = b'{"event":"payment.succeeded"}'

    timestamp = 1_000_000

    signature = generate_signature(
        payload,
        SECRET,
        timestamp,
    )

    assert not verify_signature(
        payload,
        signature,
        SECRET,
        timestamp,
        tolerance_seconds=300,
        now=1_000_301,
    )


def test_tampered_payload_is_rejected():
    payload = b'{"event":"payment.succeeded"}'
    tampered = b'{"event":"payment.failed"}'

    timestamp = 1_000_000

    signature = generate_signature(
        payload,
        SECRET,
        timestamp,
    )

    assert not verify_signature(
        tampered,
        signature,
        SECRET,
        timestamp,
        now=timestamp,
    )