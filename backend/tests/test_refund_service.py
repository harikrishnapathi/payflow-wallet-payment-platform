import uuid

import pytest

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.refund import Refund, RefundStatus
from app.models.user import User
from app.services.payment_processing_service import process_payment_event
from app.services.refund_service import create_refund
from app.services.wallet_service import create_user_wallet
from app.services.transaction_service import fingerprint


def create_test_user(db, prefix="refund-service"):
    user = User(
        id=uuid.uuid4(),
        email=f"{prefix}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Refund",
        last_name="Service",
    )

    db.add(user)
    db.flush()

    return user


def create_system_account(db):
    account = LedgerAccount(
        account_type=LedgerAccountType.SYSTEM,
        currency="INR",
        wallet_id=None,
    )

    db.add(account)
    db.flush()

    return account


def create_payment(db):
    user = create_test_user(db)
    wallet = create_user_wallet(db, user)
    create_system_account(db)

    payment = Payment(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=5000,
        currency="INR",
        status=PaymentStatus.PENDING,
        provider=PaymentProvider.SIMULATOR,
        idempotency_key=f"refund-service-payment-{uuid.uuid4()}",
        request_fingerprint=fingerprint(
            transaction_type="PAYMENT",
            amount=5000,
            currency="INR",
            source_wallet_id=wallet.id,
        ),
    )

    db.add(payment)
    db.flush()

    process_payment_event(
        db,
        payment.id,
    )

    return payment, user, wallet


def test_create_refund_moves_payment_to_refundable(db):
    payment, user, wallet = create_payment(db)

    refund = create_refund(
        db,
        user_id=user.id,
        payment_id=payment.id,
        amount=5000,
        idempotency_key="refund-service-001",
    )

    assert refund.status == RefundStatus.CREATED
    assert refund.amount == 5000
    assert refund.currency == "INR"
    assert payment.status == PaymentStatus.REFUNDABLE


def test_create_refund_rejects_partial_refund(db):
    payment, user, wallet = create_payment(db)

    with pytest.raises(
        Exception,
        match="Partial refunds are not supported",
    ):
        create_refund(
            db,
            user_id=user.id,
            payment_id=payment.id,
            amount=1000,
            idempotency_key="refund-partial-001",
        )


def test_create_refund_idempotency_returns_same_refund(db):
    payment, user, wallet = create_payment(db)

    first = create_refund(
        db,
        user_id=user.id,
        payment_id=payment.id,
        amount=5000,
        idempotency_key="refund-idempotency-service-001",
    )

    second = create_refund(
        db,
        user_id=user.id,
        payment_id=payment.id,
        amount=5000,
        idempotency_key="refund-idempotency-service-001",
    )

    assert first.id == second.id
    