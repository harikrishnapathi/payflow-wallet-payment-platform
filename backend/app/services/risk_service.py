import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.ledger_transaction import (
    LedgerTransaction,
    LedgerTransactionType,
)

# Amounts are stored in paise.
MAX_TRANSFER_AMOUNT = int(
    os.getenv("PAYFLOW_MAX_TRANSFER_AMOUNT", "10000000")
)  # ₹1,00,000

DAILY_TRANSFER_LIMIT = int(
    os.getenv("PAYFLOW_DAILY_TRANSFER_LIMIT", "50000000")
)  # ₹5,00,000

HOURLY_TRANSFER_COUNT_LIMIT = int(
    os.getenv("PAYFLOW_HOURLY_TRANSFER_COUNT_LIMIT", "20")
)


class TransferRiskViolation(ValueError):
    """Raised when a transfer violates a configured risk/limit rule."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def check_transfer_limits_for_account(
    db: Session,
    ledger_account_id: uuid.UUID,
    amount: int,
) -> None:
    """Apply transfer amount and velocity limits for a user ledger account."""

    if amount > MAX_TRANSFER_AMOUNT:
        raise TransferRiskViolation(
            "MAX_TRANSFER_AMOUNT_EXCEEDED",
            "Transfer amount exceeds the per-transaction limit of ₹1,00,000.",
        )

    now = datetime.now(timezone.utc)
    day_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    hour_start = now - timedelta(hours=1)

    daily_amount = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .join(
            LedgerTransaction,
            LedgerTransaction.id
            == LedgerEntry.ledger_transaction_id,
        )
        .where(
            LedgerEntry.ledger_account_id == ledger_account_id,
            LedgerEntry.entry_type == LedgerEntryType.DEBIT,
            LedgerTransaction.transaction_type
            == LedgerTransactionType.TRANSFER,
            LedgerTransaction.created_at >= day_start,
        )
    ) or 0

    if daily_amount + amount > DAILY_TRANSFER_LIMIT:
        remaining = max(DAILY_TRANSFER_LIMIT - daily_amount, 0)
        raise TransferRiskViolation(
            "DAILY_TRANSFER_LIMIT_EXCEEDED",
            "Daily transfer limit exceeded. "
            f"Remaining limit today: ₹{remaining / 100:,.2f}.",
        )

    hourly_count = db.scalar(
        select(func.count(LedgerTransaction.id))
        .join(
            LedgerEntry,
            LedgerEntry.ledger_transaction_id
            == LedgerTransaction.id,
        )
        .where(
            LedgerEntry.ledger_account_id == ledger_account_id,
            LedgerEntry.entry_type == LedgerEntryType.DEBIT,
            LedgerTransaction.transaction_type
            == LedgerTransactionType.TRANSFER,
            LedgerTransaction.created_at >= hour_start,
        )
    ) or 0

    if hourly_count >= HOURLY_TRANSFER_COUNT_LIMIT:
        raise TransferRiskViolation(
            "TRANSFER_VELOCITY_LIMIT_EXCEEDED",
            "Too many transfers in the last hour. Please try again later.",
        )