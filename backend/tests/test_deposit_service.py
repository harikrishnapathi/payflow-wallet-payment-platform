import uuid

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_entry import LedgerEntryType
from app.models.ledger_transaction import LedgerTransactionType
from app.models.user import User
from app.services.deposit_service import deposit
from app.services.wallet_service import create_user_wallet


def create_test_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"deposit-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Deposit",
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


def test_deposit_updates_wallet_and_creates_double_entry(db):
    user = create_test_user(db)

    wallet = create_user_wallet(
        db,
        user,
    )

    create_system_account(db)

    tx = deposit(
        db,
        wallet_id=wallet.id,
        amount=5000,
        idempotency_key="deposit-test-001",
        description="Test deposit",
    )

    db.flush()

    assert tx.transaction_type == LedgerTransactionType.DEPOSIT
    assert tx.currency == "INR"
    assert tx.idempotency_key == "deposit-test-001"

    assert wallet.available_balance == 5000
    assert wallet.pending_balance == 0

    assert len(tx.entries) == 2

    debit = next(
        entry
        for entry in tx.entries
        if entry.entry_type == LedgerEntryType.DEBIT
    )

    credit = next(
        entry
        for entry in tx.entries
        if entry.entry_type == LedgerEntryType.CREDIT
    )

    assert debit.amount == 5000
    assert credit.amount == 5000


def test_deposit_idempotency_does_not_create_duplicate_transaction(db):
    user = create_test_user(db)

    wallet = create_user_wallet(
        db,
        user,
    )

    create_system_account(db)

    first = deposit(
        db,
        wallet_id=wallet.id,
        amount=5000,
        idempotency_key="deposit-idempotency-001",
        description="Test deposit",
    )

    second = deposit(
        db,
        wallet_id=wallet.id,
        amount=5000,
        idempotency_key="deposit-idempotency-001",
        description="Test deposit",
    )

    assert first.id == second.id
    assert wallet.available_balance == 5000