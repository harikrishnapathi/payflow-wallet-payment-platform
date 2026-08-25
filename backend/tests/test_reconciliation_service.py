import uuid

from app.models.ledger_account import (
    LedgerAccount,
    LedgerAccountType,
)
from app.models.ledger_entry import (
    LedgerEntry,
    LedgerEntryType,
)
from app.models.ledger_transaction import (
    LedgerTransaction,
    LedgerTransactionType,
)
from app.models.user import User
from app.models.wallet import Wallet
from app.services.reconciliation_service import (
    calculate_ledger_balance,
    reconcile_all_wallets,
    reconcile_wallet,
)


def create_wallet_with_account(db):
    user = User(
        id=uuid.uuid4(),
        email=f"reconcile-{uuid.uuid4()}@example.com",
        password_hash="test-password",
        first_name="Reconcile",
        last_name="Test",
    )

    db.add(user)
    db.flush()

    wallet = Wallet(
        id=uuid.uuid4(),
        user_id=user.id,
        currency="INR",
        available_balance=0,
    )

    db.add(wallet)
    db.flush()

    account = LedgerAccount(
        id=uuid.uuid4(),
        wallet_id=wallet.id,
        account_type=LedgerAccountType.USER_WALLET,
        currency="INR",
    )

    db.add(account)
    db.flush()

    return wallet, account


def create_ledger_transaction(
    db,
    account,
    amount,
    entry_type,
):
    transaction = LedgerTransaction(
        id=uuid.uuid4(),
        transaction_type=LedgerTransactionType.DEPOSIT,
        currency="INR",
        idempotency_key=f"reconcile-{uuid.uuid4()}",
    )

    db.add(transaction)
    db.flush()

    entry = LedgerEntry(
        id=uuid.uuid4(),
        ledger_transaction_id=transaction.id,
        ledger_account_id=account.id,
        entry_type=entry_type,
        amount=amount,
    )

    db.add(entry)
    db.flush()

    return transaction


def test_calculate_ledger_balance(db):
    wallet, account = create_wallet_with_account(db)

    create_ledger_transaction(
        db,
        account,
        10000,
        LedgerEntryType.CREDIT,
    )

    create_ledger_transaction(
        db,
        account,
        2500,
        LedgerEntryType.DEBIT,
    )

    balance = calculate_ledger_balance(
        db,
        account.id,
    )

    assert balance == 7500


def test_reconcile_wallet_balanced(db):
    wallet, account = create_wallet_with_account(db)

    create_ledger_transaction(
        db,
        account,
        10000,
        LedgerEntryType.CREDIT,
    )

    wallet.available_balance = 10000
    db.flush()

    result = reconcile_wallet(
        db,
        wallet.id,
    )

    assert result.wallet_balance == 10000
    assert result.ledger_balance == 10000
    assert result.difference == 0
    assert result.is_balanced is True


def test_reconcile_wallet_detects_mismatch(db):
    wallet, account = create_wallet_with_account(db)

    create_ledger_transaction(
        db,
        account,
        10000,
        LedgerEntryType.CREDIT,
    )

    wallet.available_balance = 8000
    db.flush()

    result = reconcile_wallet(
        db,
        wallet.id,
    )

    assert result.wallet_balance == 8000
    assert result.ledger_balance == 10000
    assert result.difference == -2000
    assert result.is_balanced is False


def test_reconcile_all_wallets(db):
    wallet1, account1 = create_wallet_with_account(db)
    wallet2, account2 = create_wallet_with_account(db)

    create_ledger_transaction(
        db,
        account1,
        5000,
        LedgerEntryType.CREDIT,
    )

    create_ledger_transaction(
        db,
        account2,
        8000,
        LedgerEntryType.CREDIT,
    )

    wallet1.available_balance = 5000
    wallet2.available_balance = 8000

    db.flush()

    results = reconcile_all_wallets(db)

    wallet_ids = {
        result.wallet_id
        for result in results
    }

    assert wallet1.id in wallet_ids
    assert wallet2.id in wallet_ids

    assert all(
        result.is_balanced
        for result in results
    )
    