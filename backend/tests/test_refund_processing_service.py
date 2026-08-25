import uuid

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_entry import LedgerEntryType
from app.models.ledger_transaction import LedgerTransaction
from app.models.ledger_transaction import LedgerTransactionType
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.refund import Refund, RefundStatus
from app.models.user import User
from app.services.payment_processing_service import process_payment_event
from app.services.refund_processing_service import process_refund_event
from app.services.refund_service import create_refund
from app.services.wallet_service import create_user_wallet
from app.services.transaction_service import fingerprint


def create_test_user(db, prefix="refund"):
    user = User(
        id=uuid.uuid4(),
        email=f"{prefix}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Refund",
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


def create_successful_payment(db):
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
        idempotency_key=f"refund-payment-{uuid.uuid4()}",
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


def test_refund_processing_creates_compensating_ledger(db):
    payment, user, wallet = create_successful_payment(db)

    payment.status = PaymentStatus.REFUNDABLE
    db.flush()

    refund = Refund(
        payment_id=payment.id,
        user_id=user.id,
        amount=5000,
        currency="INR",
        status=RefundStatus.CREATED,
        idempotency_key=f"refund-processing-{uuid.uuid4()}",
        request_fingerprint="refund-test-fingerprint",
    )

    db.add(refund)
    db.flush()

    processed = process_refund_event(
        db,
        refund.id,
    )

    db.flush()

    assert processed.status == RefundStatus.SUCCEEDED
    assert processed.provider_refund_id == (
        f"sim_refund_{refund.id.hex}"
    )

    assert payment.status == PaymentStatus.REFUNDED

    ledger_key = f"refund:{refund.id}:ledger"

    transaction = db.query(LedgerTransaction).filter(
        LedgerTransaction.idempotency_key == ledger_key
    ).one()

    assert transaction.transaction_type == (
        LedgerTransactionType.REFUND
    )

    assert len(transaction.entries) == 2

    debit = next(
        entry
        for entry in transaction.entries
        if entry.entry_type == LedgerEntryType.DEBIT
    )

    credit = next(
        entry
        for entry in transaction.entries
        if entry.entry_type == LedgerEntryType.CREDIT
    )

    assert debit.amount == 5000
    assert credit.amount == 5000


def test_refund_processing_is_idempotent(db):
    payment, user, wallet = create_successful_payment(db)

    payment.status = PaymentStatus.REFUNDABLE
    db.flush()

    refund = Refund(
        payment_id=payment.id,
        user_id=user.id,
        amount=5000,
        currency="INR",
        status=RefundStatus.CREATED,
        idempotency_key=f"refund-idempotency-{uuid.uuid4()}",
        request_fingerprint="refund-idempotency-fingerprint",
    )

    db.add(refund)
    db.flush()

    first = process_refund_event(
        db,
        refund.id,
    )

    second = process_refund_event(
        db,
        refund.id,
    )

    db.flush()

    assert first.id == second.id
    assert second.status == RefundStatus.SUCCEEDED

    ledger_key = f"refund:{refund.id}:ledger"

    transactions = db.query(LedgerTransaction).filter(
        LedgerTransaction.idempotency_key == ledger_key
    ).all()

    assert len(transactions) == 1
    assert len(transactions[0].entries) == 2