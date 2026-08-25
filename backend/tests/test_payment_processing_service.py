import uuid

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_entry import LedgerEntryType
from app.models.ledger_transaction import LedgerTransaction
from app.models.ledger_transaction import LedgerTransactionType
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.user import User
from app.services.payment_processing_service import process_payment_event
from app.services.wallet_service import create_user_wallet
from app.services.transaction_service import fingerprint


def create_test_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"payment-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Payment",
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


def create_payment(db, user, wallet, amount=5000):
    payment = Payment(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=amount,
        currency="INR",
        status=PaymentStatus.PENDING,
        provider=PaymentProvider.SIMULATOR,
        idempotency_key=f"payment-test-{uuid.uuid4()}",
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


def test_payment_processing_succeeds_and_creates_ledger(db):
    user = create_test_user(db)
    wallet = create_user_wallet(db, user)
    create_system_account(db)

    payment = create_payment(
        db,
        user,
        wallet,
        amount=5000,
    )

    processed = process_payment_event(
        db,
        payment.id,
    )

    db.flush()

    assert processed.status == PaymentStatus.SUCCEEDED

    assert processed.provider_payment_id == (
        f"sim_{payment.id.hex}"
    )

    assert wallet.available_balance == 0

    ledger_key = f"payment:{payment.id}:ledger"

    transaction = db.query(LedgerTransaction).filter(
        LedgerTransaction.idempotency_key == ledger_key
    ).one()

    assert transaction.transaction_type == (
        LedgerTransactionType.PAYMENT
    )

    assert transaction.currency == "INR"
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


def test_payment_processing_is_idempotent(db):
    user = create_test_user(db)
    wallet = create_user_wallet(db, user)
    create_system_account(db)

    payment = create_payment(
        db,
        user,
        wallet,
        amount=5000,
    )

    first = process_payment_event(
        db,
        payment.id,
    )

    second = process_payment_event(
        db,
        payment.id,
    )

    db.flush()

    assert first.id == second.id
    assert second.status == PaymentStatus.SUCCEEDED

    ledger_key = f"payment:{payment.id}:ledger"

    transactions = db.query(LedgerTransaction).filter(
        LedgerTransaction.idempotency_key == ledger_key
    ).all()

    assert len(transactions) == 1
    assert len(transactions[0].entries) == 2