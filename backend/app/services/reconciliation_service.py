import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.wallet import Wallet


@dataclass(frozen=True)
class ReconciliationResult:
    wallet_id: uuid.UUID
    wallet_balance: int
    ledger_balance: int
    difference: int
    is_balanced: bool


def calculate_ledger_balance(
    db: Session,
    ledger_account_id: uuid.UUID,
) -> int:
    """Calculate the balance represented by ledger entries."""

    credits = db.scalar(
        select(
            func.coalesce(
                func.sum(LedgerEntry.amount),
                0,
            )
        ).where(
            LedgerEntry.ledger_account_id == ledger_account_id,
            LedgerEntry.entry_type == LedgerEntryType.CREDIT,
        )
    ) or 0

    debits = db.scalar(
        select(
            func.coalesce(
                func.sum(LedgerEntry.amount),
                0,
            )
        ).where(
            LedgerEntry.ledger_account_id == ledger_account_id,
            LedgerEntry.entry_type == LedgerEntryType.DEBIT,
        )
    ) or 0

    return credits - debits


def reconcile_wallet(
    db: Session,
    wallet_id: uuid.UUID,
) -> ReconciliationResult:
    """Compare wallet balance against its ledger balance."""

    wallet = db.scalar(
        select(Wallet)
        .where(Wallet.id == wallet_id)
    )

    if wallet is None:
        raise ValueError("Wallet not found.")

    account = db.scalar(
        select(LedgerAccount)
        .where(
            LedgerAccount.wallet_id == wallet_id
        )
    )

    if account is None:
        raise ValueError(
            "Wallet ledger account not found."
        )

    ledger_balance = calculate_ledger_balance(
        db,
        account.id,
    )

    difference = (
        wallet.available_balance
        - ledger_balance
    )

    return ReconciliationResult(
        wallet_id=wallet.id,
        wallet_balance=wallet.available_balance,
        ledger_balance=ledger_balance,
        difference=difference,
        is_balanced=difference == 0,
    )


def reconcile_all_wallets(
    db: Session,
) -> list[ReconciliationResult]:
    """Reconcile every wallet in the system."""

    wallet_ids = db.scalars(
        select(Wallet.id)
        .order_by(Wallet.created_at)
    ).all()

    return [
        reconcile_wallet(db, wallet_id)
        for wallet_id in wallet_ids
    ]