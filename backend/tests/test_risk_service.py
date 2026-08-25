import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.ledger_transaction import (
    LedgerTransaction,
    LedgerTransactionType,
)
from app.services.risk_service import (
    check_transfer_limits_for_account,
)


def test_transfer_limit_rejects_large_amount(db):
    account = LedgerAccount(
        id=uuid.uuid4(),
        account_type=LedgerAccountType.USER_WALLET,
        currency="INR",
    )
    db.add(account)
    db.flush()

    with pytest.raises(Exception, match="per-transaction limit"):
        check_transfer_limits_for_account(
            db,
            account.id,
            10_000_001,
        )


def test_transfer_limit_rejects_daily_limit(db):
    account = LedgerAccount(
        id=uuid.uuid4(),
        account_type=LedgerAccountType.USER_WALLET,
        currency="INR",
    )
    db.add(account)
    db.flush()

    tx = LedgerTransaction(
        transaction_type=LedgerTransactionType.TRANSFER,
        currency="INR",
        idempotency_key=f"risk-{uuid.uuid4()}",
    )
    db.add(tx)
    db.flush()

    db.add(
        LedgerEntry(
            ledger_transaction_id=tx.id,
            ledger_account_id=account.id,
            entry_type=LedgerEntryType.DEBIT,
            amount=49_999_900,
        )
    )
    db.flush()

    with pytest.raises(Exception, match="Daily transfer limit exceeded"):
        check_transfer_limits_for_account(
            db,
            account.id,
            20_000,
        )


def test_transfer_limit_allows_normal_transfer(db):
    account = LedgerAccount(
        id=uuid.uuid4(),
        account_type=LedgerAccountType.USER_WALLET,
        currency="INR",
    )
    db.add(account)
    db.flush()

    check_transfer_limits_for_account(
        db,
        account.id,
        20_000,
    )