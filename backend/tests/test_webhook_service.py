import uuid

import pytest

from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.user import User
from app.models.wallet import Wallet
from app.services.transaction_service import fingerprint
from app.services.webhook_service import (
    generate_signature,
    process_webhook,
)
from app.services.wallet_service import create_user_wallet


SECRET = "test-webhook-secret"


def create_test_payment(db, status=PaymentStatus.PENDING):
    user = User(
        id=uuid.uuid4(),
        email=f"webhook-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Webhook",
        last_name="Test",
    )

    db.add(user)
    db.flush()

    wallet = create_user_wallet(
        db,
        user,
    )

    payment = Payment(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=5000,
        currency="INR",
        status=status,
        provider=PaymentProvider.SIMULATOR,
        idempotency_key=f"webhook-payment-{uuid.uuid4()}",
        request_fingerprint=fingerprint(
            transaction_type="PAYMENT",
            amount=5000,
            currency="INR",
            source_wallet_id=wallet.id,
        ),
    )

    db.add(payment)
    db.flush()

    return payment


def test_generate_and_verify_webhook_signature():
    payload = {
        "payment_id": "payment-123",
        "amount": 5000,
        "status": "succeeded",
    }

    signature = generate_signature(
        payload,
        SECRET,
    )

    assert signature
    assert len(signature) == 64

    from app.services.webhook_service import verify_signature

    assert verify_signature(
        payload,
        signature,
        SECRET,
    )

    assert not verify_signature(
        payload,
        signature,
        "wrong-secret",
    )


def test_payment_succeeded_webhook_updates_payment(db):
    payment = create_test_payment(
    db,
    PaymentStatus.PROCESSING,
)

    payload = {
        "payment_id": str(payment.id),
        "amount": 5000,
        "status": "succeeded",
    }

    signature = generate_signature(
        payload,
        SECRET,
    )

    event = process_webhook(
        db,
        provider="SIMULATOR",
        event_id="webhook-success-001",
        event_type="PAYMENT_SUCCEEDED",
        payment_id=payment.id,
        payload=payload,
        signature=signature,
        secret=SECRET,
    )

    db.flush()

    assert event.event_id == "webhook-success-001"
    assert event.processed_at is not None
    assert payment.status == PaymentStatus.SUCCEEDED


def test_payment_failed_webhook_updates_payment(db):
    payment = create_test_payment(
    db,
    PaymentStatus.PROCESSING,
)
    payload = {
        "payment_id": str(payment.id),
        "failure_code": "CARD_DECLINED",
        "failure_message": "Card was declined.",
    }

    signature = generate_signature(
        payload,
        SECRET,
    )

    event = process_webhook(
        db,
        provider="SIMULATOR",
        event_id="webhook-failed-001",
        event_type="PAYMENT_FAILED",
        payment_id=payment.id,
        payload=payload,
        signature=signature,
        secret=SECRET,
    )

    db.flush()

    assert event.processed_at is not None
    assert payment.status == PaymentStatus.FAILED
    assert payment.failure_code == "CARD_DECLINED"
    assert payment.failure_message == "Card was declined."


def test_invalid_webhook_signature_is_rejected(db):
    payment = create_test_payment(db)

    payload = {
        "payment_id": str(payment.id),
        "amount": 5000,
    }

    with pytest.raises(
        Exception,
        match="Invalid webhook signature",
    ):
        process_webhook(
            db,
            provider="SIMULATOR",
            event_id="webhook-invalid-signature-001",
            event_type="PAYMENT_SUCCEEDED",
            payment_id=payment.id,
            payload=payload,
            signature="invalid-signature",
            secret=SECRET,
        )

    assert payment.status == PaymentStatus.PENDING


def test_duplicate_webhook_event_is_idempotent(db):
    payment = create_test_payment(
    db,
    PaymentStatus.PROCESSING,
)

    payload = {
        "payment_id": str(payment.id),
        "amount": 5000,
    }

    signature = generate_signature(
        payload,
        SECRET,
    )

    first = process_webhook(
        db,
        provider="SIMULATOR",
        event_id="webhook-duplicate-001",
        event_type="PAYMENT_SUCCEEDED",
        payment_id=payment.id,
        payload=payload,
        signature=signature,
        secret=SECRET,
    )

    second = process_webhook(
        db,
        provider="SIMULATOR",
        event_id="webhook-duplicate-001",
        event_type="PAYMENT_SUCCEEDED",
        payment_id=payment.id,
        payload=payload,
        signature=signature,
        secret=SECRET,
    )

    assert first.id == second.id
    assert payment.status == PaymentStatus.SUCCEEDED


def test_unsupported_webhook_event_is_rejected(db):
    payment = create_test_payment(db)

    payload = {
        "payment_id": str(payment.id),
    }

    signature = generate_signature(
        payload,
        SECRET,
    )

    with pytest.raises(
        Exception,
        match="Unsupported webhook event",
    ):
        process_webhook(
            db,
            provider="SIMULATOR",
            event_id="webhook-unsupported-001",
            event_type="UNKNOWN_EVENT",
            payment_id=payment.id,
            payload=payload,
            signature=signature,
            secret=SECRET,
        )