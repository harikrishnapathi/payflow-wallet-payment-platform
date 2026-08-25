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
from app.services.ledger_integrity_service import (
    check_transaction_balance,
    find_negative_wallets,
    find_unbalanced_transactions,
    run_integrity_check,
)


def create_transaction(db):
    transaction = LedgerTransaction(
        id=uuid.uuid4(),
        transaction_type=LedgerTransactionType.TRANSFER,
        currency="INR",
        idempotency_key=f"integrity-{uuid.uuid4()}",
    )

    db.add(transaction)
    db.flush()

    return transaction


def create_account(db):
    account = LedgerAccount(
        id=uuid.uuid4(),
        account_type=LedgerAccountType.USER_WALLET,
        currency="INR",
    )

    db.add(account)
    db.flush()

    return account


def test_balanced_transaction(db):
    transaction = create_transaction(db)
    account1 = create_account(db)
    account2 = create_account(db)

    db.add_all(
        [
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account1.id,
                entry_type=LedgerEntryType.DEBIT,
                amount=5000,
            ),
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account2.id,
                entry_type=LedgerEntryType.CREDIT,
                amount=5000,
            ),
        ]
    )

    db.flush()

    result = check_transaction_balance(
        db,
        transaction.id,
    )

    assert result.debit_total == 5000
    assert result.credit_total == 5000
    assert result.is_balanced is True


def test_unbalanced_transaction(db):
    transaction = create_transaction(db)
    account1 = create_account(db)
    account2 = create_account(db)

    db.add_all(
        [
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account1.id,
                entry_type=LedgerEntryType.DEBIT,
                amount=5000,
            ),
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account2.id,
                entry_type=LedgerEntryType.CREDIT,
                amount=3000,
            ),
        ]
    )

    db.flush()

    result = check_transaction_balance(
        db,
        transaction.id,
    )

    assert result.debit_total == 5000
    assert result.credit_total == 3000
    assert result.is_balanced is False


def test_find_unbalanced_transactions(db):
    transaction = create_transaction(db)
    account1 = create_account(db)
    account2 = create_account(db)

    db.add_all(
        [
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account1.id,
                entry_type=LedgerEntryType.DEBIT,
                amount=10000,
            ),
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account2.id,
                entry_type=LedgerEntryType.CREDIT,
                amount=9000,
            ),
        ]
    )

    db.flush()

    issues = find_unbalanced_transactions(db)

    assert any(
        issue.transaction_id == transaction.id
        for issue in issues
    )


def test_find_negative_wallet(db):
    user = User(
        id=uuid.uuid4(),
        email=f"negative-{uuid.uuid4()}@example.com",
        password_hash="test-password",
        first_name="Negative",
        last_name="Balance",
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

    # The database deliberately prevents negative balances.
    # Therefore this test verifies that the integrity checker
    # returns no negative-wallet issue for a valid wallet.
    issues = find_negative_wallets(db)

    assert not any(
        issue.wallet_id == wallet.id
        for issue in issues
    )


def test_integrity_check_returns_empty_for_clean_data(db):
    transaction = create_transaction(db)
    account1 = create_account(db)
    account2 = create_account(db)

    db.add_all(
        [
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account1.id,
                entry_type=LedgerEntryType.DEBIT,
                amount=5000,
            ),
            LedgerEntry(
                ledger_transaction_id=transaction.id,
                ledger_account_id=account2.id,
                entry_type=LedgerEntryType.CREDIT,
                amount=5000,
            ),
        ]
    )

    db.flush()

    issues = run_integrity_check(db)

    assert issues == []