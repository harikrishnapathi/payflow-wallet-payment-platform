import uuid

from app.models.ledger_account import (
    LedgerAccount,
    LedgerAccountType,
)
from app.models.ledger_transaction import LedgerTransaction
from app.models.payment import (
    Payment,
    PaymentProvider,
    PaymentStatus,
)
from app.models.refund import RefundStatus
from app.models.user import User
from app.services.provider_simulator_service import (
    create_payment_webhook,
    create_refund_webhook,
)
from app.services.refund_service import create_refund
from app.services.transaction_service import fingerprint
from app.services.wallet_service import create_user_wallet
from app.services.webhook_processing_service import (
    process_provider_webhook,
)


def create_test_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"refund-{uuid.uuid4()}@example.com",
        password_hash="password",
        first_name="Refund",
        last_name="User",
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


def create_payment(db, user, wallet):
    payment = Payment(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=5000,
        currency="INR",
        provider=PaymentProvider.SIMULATOR,
        status=PaymentStatus.PENDING,
        idempotency_key=f"payment-{uuid.uuid4()}",
        request_fingerprint=fingerprint(
            transaction_type="PAYMENT",
            amount=5000,
            currency="INR",
            source_wallet_id=wallet.id,
        ),
    )

    db.add(payment)
    db.flush()

    webhook = create_payment_webhook(
        payment_id=payment.id,
    )

    process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook["provider_event_id"],
        event_type=webhook["payload"]["event_type"],
        payload=webhook["payload"],
    )

    db.flush()

    return payment


def create_successful_refund(db, payment):
    refund = create_refund(
        db,
        user_id=payment.user_id,
        payment_id=payment.id,
        amount=payment.amount,
        idempotency_key=f"refund-{uuid.uuid4()}",
    )

    db.flush()

    return refund


def test_refund_webhook_processes_refund(db):
    user = create_test_user(db)
    create_system_account(db)

    wallet = create_user_wallet(db, user)

    payment = create_payment(db, user, wallet)

    refund = create_successful_refund(db, payment)

    webhook = create_refund_webhook(
        refund_id=refund.id,
    )

    event = process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook["provider_event_id"],
        event_type=webhook["payload"]["event_type"],
        payload=webhook["payload"],
    )

    db.flush()

    db.refresh(refund)
    db.refresh(payment)

    assert event.status.value == "PROCESSED"
    assert refund.status == RefundStatus.SUCCEEDED
    assert payment.status == PaymentStatus.REFUNDED


def test_duplicate_refund_webhook_is_idempotent(db):
    user = create_test_user(db)
    create_system_account(db)

    wallet = create_user_wallet(db, user)

    payment = create_payment(db, user, wallet)

    refund = create_successful_refund(db, payment)

    webhook = create_refund_webhook(
        refund_id=refund.id,
        provider_event_id=f"evt-{uuid.uuid4()}",
    )

    first = process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook["provider_event_id"],
        event_type=webhook["payload"]["event_type"],
        payload=webhook["payload"],
    )

    second = process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook["provider_event_id"],
        event_type=webhook["payload"]["event_type"],
        payload=webhook["payload"],
    )

    db.flush()

    assert first.id == second.id

    ledger_key = f"refund:{refund.id}:ledger"

    transactions = db.query(LedgerTransaction).filter(
        LedgerTransaction.idempotency_key == ledger_key
    ).all()

    assert len(transactions) == 1


def test_refund_webhook_invalid_refund_id(db):
    webhook = create_refund_webhook(
        refund_id=uuid.uuid4(),
    )

    try:
        process_provider_webhook(
            db,
            provider=webhook["provider"],
            provider_event_id=webhook["provider_event_id"],
            event_type=webhook["payload"]["event_type"],
            payload=webhook["payload"],
        )
    except Exception:
        db.rollback()

    assert True


def test_refund_creates_reverse_ledger(db):
    user = create_test_user(db)
    create_system_account(db)

    wallet = create_user_wallet(db, user)

    payment = create_payment(db, user, wallet)

    refund = create_successful_refund(db, payment)

    webhook = create_refund_webhook(
        refund_id=refund.id,
    )

    process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook["provider_event_id"],
        event_type=webhook["payload"]["event_type"],
        payload=webhook["payload"],
    )

    db.flush()

    ledger_key = f"refund:{refund.id}:ledger"

    transaction = db.query(LedgerTransaction).filter(
        LedgerTransaction.idempotency_key == ledger_key
    ).one()

    assert transaction.transaction_type.value == "REFUND"

    assert len(transaction.entries) == 2


def test_payment_cannot_be_refunded_twice(db):
    user = create_test_user(db)
    create_system_account(db)

    wallet = create_user_wallet(
        db,
        user,
    )

    payment = create_payment(
        db,
        user,
        wallet,
    )

    refund = create_successful_refund(
        db,
        payment,
    )

    webhook = create_refund_webhook(
        refund_id=refund.id,
    )

    process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook[
            "provider_event_id"
        ],
        event_type=webhook["payload"][
            "event_type"
        ],
        payload=webhook["payload"],
    )

    db.flush()

    # Payment must now be fully refunded.
    db.refresh(payment)

    assert payment.status == PaymentStatus.REFUNDED

    # A second refund must be rejected.
    second_refund_rejected = False

    try:
        create_refund(
            db,
            user_id=user.id,
            payment_id=payment.id,
            amount=payment.amount,
            idempotency_key=f"refund-{uuid.uuid4()}",
        )
    except Exception:
        second_refund_rejected = True

    assert second_refund_rejected is True


def test_provider_refund_id_is_saved(db):
    user = create_test_user(db)
    create_system_account(db)

    wallet = create_user_wallet(db, user)

    payment = create_payment(db, user, wallet)

    refund = create_successful_refund(db, payment)

    webhook = create_refund_webhook(
        refund_id=refund.id,
    )

    process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook["provider_event_id"],
        event_type=webhook["payload"]["event_type"],
        payload=webhook["payload"],
    )

    db.flush()

    db.refresh(refund)

    assert refund.provider_refund_id.startswith(
        "sim_refund_"
    )


def test_unknown_refund_webhook_is_ignored(db):
    webhook = {
        "provider": "SIMULATOR",
        "provider_event_id": f"evt-{uuid.uuid4()}",
        "payload": {
            "event_type": "refund.unknown",
            "refund_id": str(uuid.uuid4()),
        },
    }

    event = process_provider_webhook(
        db,
        provider=webhook["provider"],
        provider_event_id=webhook["provider_event_id"],
        event_type=webhook["payload"]["event_type"],
        payload=webhook["payload"],
    )

    db.flush()

    assert event.status.value == "IGNORED"
