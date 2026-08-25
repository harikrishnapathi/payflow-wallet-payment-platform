import json
import time
import uuid

from app.services.provider_simulator_service import (
    create_payment_failed_webhook,
    create_payment_webhook,
)
from app.services.webhook_processing_service import (
    process_provider_webhook,
)
from app.models.ledger_transaction import LedgerTransaction
from app.models.payment import (
    Payment,
    PaymentProvider,
    PaymentStatus,
)
from app.models.user import User
from app.services.transaction_service import fingerprint
from app.services.wallet_service import create_user_wallet

from app.models.ledger_account import (
    LedgerAccount,
    LedgerAccountType,
)

def create_test_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"lifecycle-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Lifecycle",
        last_name="Test",
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

def create_test_payment(
    db,
    user,
    wallet,
    amount=5000,
):
    payment = Payment(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=amount,
        currency="INR",
        status=PaymentStatus.PENDING,
        provider=PaymentProvider.SIMULATOR,
        idempotency_key=(
            f"lifecycle-{uuid.uuid4()}"
        ),
        request_fingerprint=fingerprint(
            transaction_type="PAYMENT",
            amount=amount,
            currency="INR",
            source_wallet_id=wallet.id,
        ),
    )

    db.add(payment)
    db.flush()

    return payment


def test_successful_payment_webhook_updates_payment(
    db,
    
):
    user = create_test_user(db)
    create_system_account(db)
    wallet = create_user_wallet(db, user)

    payment = create_test_payment(
        db,
        user,
        wallet,
        amount=5000,
    )

    webhook = create_payment_webhook(
        payment_id=payment.id,
        secret="change-me",
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

    db.refresh(payment)
    db.refresh(wallet)

    assert payment.status == PaymentStatus.SUCCEEDED

    assert payment.provider_payment_id == (
        f"sim_{payment.id.hex}"
    )

    assert wallet.available_balance == 0


def test_successful_payment_creates_one_ledger(
    db,
    
):
    user = create_test_user(db)
    create_system_account(db)
    wallet = create_user_wallet(db, user)

    payment = create_test_payment(
        db,
        user,
        wallet,
        amount=7500,
    )

    webhook = create_payment_webhook(
        payment_id=payment.id,
        secret="change-me",
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

    ledger_key = (
        f"payment:{payment.id}:ledger"
    )

    transactions = (
        db.query(LedgerTransaction)
        .filter(
            LedgerTransaction.idempotency_key
            == ledger_key
        )
        .all()
    )

    assert len(transactions) == 1
    assert len(transactions[0].entries) == 2


def test_duplicate_success_webhook_does_not_double_credit(
    db,
    
):
    user = create_test_user(db)
    create_system_account(db)
    wallet = create_user_wallet(db, user)

    payment = create_test_payment(
        db,
        user,
        wallet,
        amount=5000,
    )

    webhook = create_payment_webhook(
        payment_id=payment.id,
        secret="change-me",
        provider_event_id=(
            f"evt-{uuid.uuid4()}"
        ),
    )

    first = process_provider_webhook(
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

    second = process_provider_webhook(
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

    assert first.id == second.id

    db.refresh(wallet)

    assert wallet.available_balance == 0

    ledger_key = (
        f"payment:{payment.id}:ledger"
    )

    transactions = (
        db.query(LedgerTransaction)
        .filter(
            LedgerTransaction.idempotency_key
            == ledger_key
        )
        .all()
    )

    assert len(transactions) == 1


def test_failed_payment_webhook_marks_payment_failed(
    db,
    
):
    user = create_test_user(db)
    create_system_account(db)
    wallet = create_user_wallet(db, user)

    payment = create_test_payment(
        db,
        user,
        wallet,
        amount=5000,
    )

    webhook = create_payment_failed_webhook(
        payment_id=payment.id,
        secret="change-me",
        failure_code="CARD_DECLINED",
        failure_message="Card was declined.",
    )

    event = process_provider_webhook(
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

    db.refresh(payment)
    db.refresh(wallet)

    assert event.status.value == "PROCESSED"

    assert payment.status == PaymentStatus.FAILED

    assert payment.failure_code == (
        "CARD_DECLINED"
    )

    assert payment.failure_message == (
        "Card was declined."
    )

    assert wallet.available_balance == 0


def test_failed_payment_creates_no_ledger(
    db,
    
):
    user = create_test_user(db)
    create_system_account(db)
    wallet = create_user_wallet(db, user)

    payment = create_test_payment(
        db,
        user,
        wallet,
        amount=5000,
    )

    webhook = create_payment_failed_webhook(
        payment_id=payment.id,
        secret="change-me",
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

    ledger_key = (
        f"payment:{payment.id}:ledger"
    )

    transactions = (
        db.query(LedgerTransaction)
        .filter(
            LedgerTransaction.idempotency_key
            == ledger_key
        )
        .all()
    )

    assert transactions == []

def test_completed_payment_cannot_be_failed(
    db,
):
    user = create_test_user(db)
    create_system_account(db)

    wallet = create_user_wallet(
        db,
        user,
    )

    payment = create_test_payment(
        db,
        user,
        wallet,
        amount=5000,
    )

    success_webhook = create_payment_webhook(
        payment_id=payment.id,
        secret="change-me",
    )

    process_provider_webhook(
        db,
        provider=success_webhook["provider"],
        provider_event_id=success_webhook[
            "provider_event_id"
        ],
        event_type=success_webhook["payload"][
            "event_type"
        ],
        payload=success_webhook["payload"],
    )

    db.flush()

    assert payment.status == PaymentStatus.SUCCEEDED

    failed_webhook = create_payment_failed_webhook(
        payment_id=payment.id,
        secret="change-me",
    )

    failed_event = None

    try:
        failed_event = process_provider_webhook(
            db,
            provider=failed_webhook["provider"],
            provider_event_id=failed_webhook[
                "provider_event_id"
            ],
            event_type=failed_webhook["payload"][
                "event_type"
            ],
            payload=failed_webhook["payload"],
        )
    except Exception:
        pass

    db.expire_all()

    payment_after = db.get(
        Payment,
        payment.id,
    )

    assert payment_after is not None
    assert (
        payment_after.status
        == PaymentStatus.SUCCEEDED
    )