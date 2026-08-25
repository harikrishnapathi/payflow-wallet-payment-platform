import uuid

import pytest

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_entry import LedgerEntryType
from app.models.ledger_transaction import LedgerTransactionType
from app.models.user import User
from app.services.deposit_service import deposit
from app.services.wallet_service import create_user_wallet
from app.services.withdrawal_service import withdraw


def create_test_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"withdraw-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Withdraw",
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


def test_withdrawal_updates_wallet_and_creates_double_entry(db):
    user = create_test_user(db)
    wallet = create_user_wallet(db, user)
    create_system_account(db)

    deposit(
        db,
        wallet_id=wallet.id,
        amount=10000,
        idempotency_key="withdraw-funding-001",
        description="Withdrawal test funding",
    )

    tx = withdraw(
        db,
        wallet_id=wallet.id,
        amount=4000,
        idempotency_key="withdraw-test-001",
        description="Test withdrawal",
    )

    db.flush()

    assert tx.transaction_type == LedgerTransactionType.WITHDRAWAL
    assert tx.currency == "INR"
    assert tx.idempotency_key == "withdraw-test-001"

    assert wallet.available_balance == 6000
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

    assert debit.amount == 4000
    assert credit.amount == 4000


def test_withdrawal_rejects_insufficient_balance(db):
    user = create_test_user(db)
    wallet = create_user_wallet(db, user)
    create_system_account(db)

    with pytest.raises(
        ValueError,
        match="Insufficient wallet balance",
    ):
        withdraw(
            db,
            wallet_id=wallet.id,
            amount=5000,
            idempotency_key="withdraw-insufficient-001",
            description="Insufficient balance test",
        )

    assert wallet.available_balance == 0


def test_withdrawal_idempotency_does_not_debit_twice(db):
    user = create_test_user(db)
    wallet = create_user_wallet(db, user)
    create_system_account(db)

    deposit(
        db,
        wallet_id=wallet.id,
        amount=10000,
        idempotency_key="withdraw-idempotency-funding-001",
        description="Withdrawal idempotency funding",
    )

    first = withdraw(
        db,
        wallet_id=wallet.id,
        amount=4000,
        idempotency_key="withdraw-idempotency-001",
        description="Test withdrawal",
    )

    second = withdraw(
        db,
        wallet_id=wallet.id,
        amount=4000,
        idempotency_key="withdraw-idempotency-001",
        description="Test withdrawal",
    )

    assert first.id == second.id
    assert wallet.available_balance == 6000