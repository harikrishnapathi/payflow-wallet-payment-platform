import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.ledger_transaction import LedgerTransaction
from app.models.wallet import Wallet


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    message: str
    transaction_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None


@dataclass(frozen=True)
class TransactionIntegrityResult:
    transaction_id: uuid.UUID
    debit_total: int
    credit_total: int
    is_balanced: bool


def check_transaction_balance(
    db: Session,
    transaction_id: uuid.UUID,
) -> TransactionIntegrityResult:
    transaction = db.scalar(
        select(LedgerTransaction)
        .where(
            LedgerTransaction.id == transaction_id
        )
    )

    if transaction is None:
        raise ValueError(
            "Ledger transaction not found."
        )

    debit_total = db.scalar(
        select(
            func.coalesce(
                func.sum(LedgerEntry.amount),
                0,
            )
        )
        .where(
            LedgerEntry.ledger_transaction_id
            == transaction_id,
            LedgerEntry.entry_type
            == LedgerEntryType.DEBIT,
        )
    ) or 0

    credit_total = db.scalar(
        select(
            func.coalesce(
                func.sum(LedgerEntry.amount),
                0,
            )
        )
        .where(
            LedgerEntry.ledger_transaction_id
            == transaction_id,
            LedgerEntry.entry_type
            == LedgerEntryType.CREDIT,
        )
    ) or 0

    debit_total = int(debit_total)
    credit_total = int(credit_total)

    return TransactionIntegrityResult(
        transaction_id=transaction_id,
        debit_total=debit_total,
        credit_total=credit_total,
        is_balanced=debit_total == credit_total,
    )


def find_unbalanced_transactions(
    db: Session,
) -> list[IntegrityIssue]:
    rows = db.execute(
        select(
            LedgerTransaction.id,
            func.coalesce(
                func.sum(
                    LedgerEntry.amount
                ).filter(
                    LedgerEntry.entry_type
                    == LedgerEntryType.DEBIT
                ),
                0,
            ).label("debit_total"),
            func.coalesce(
                func.sum(
                    LedgerEntry.amount
                ).filter(
                    LedgerEntry.entry_type
                    == LedgerEntryType.CREDIT
                ),
                0,
            ).label("credit_total"),
        )
        .join(
            LedgerEntry,
            LedgerEntry.ledger_transaction_id
            == LedgerTransaction.id,
        )
        .group_by(
            LedgerTransaction.id
        )
        .having(
            func.coalesce(
                func.sum(
                    LedgerEntry.amount
                ).filter(
                    LedgerEntry.entry_type
                    == LedgerEntryType.DEBIT
                ),
                0,
            )
            != func.coalesce(
                func.sum(
                    LedgerEntry.amount
                ).filter(
                    LedgerEntry.entry_type
                    == LedgerEntryType.CREDIT
                ),
                0,
            )
        )
    ).all()

    return [
        IntegrityIssue(
            code="UNBALANCED_LEDGER_TRANSACTION",
            message=(
                f"Transaction {transaction_id} is unbalanced: "
                f"debits={int(debit_total)}, "
                f"credits={int(credit_total)}."
            ),
            transaction_id=transaction_id,
        )
        for transaction_id, debit_total, credit_total in rows
    ]


def find_invalid_ledger_entries(
    db: Session,
) -> list[IntegrityIssue]:
    issues: list[IntegrityIssue] = []

    entries = db.scalars(
        select(LedgerEntry)
    ).all()

    for entry in entries:
        if entry.amount <= 0:
            issues.append(
                IntegrityIssue(
                    code="INVALID_LEDGER_AMOUNT",
                    message=(
                        f"Ledger entry {entry.id} "
                        "has a non-positive amount."
                    ),
                )
            )

    return issues


def find_wallet_currency_mismatches(
    db: Session,
) -> list[IntegrityIssue]:
    rows = db.execute(
        select(
            Wallet.id,
            Wallet.currency,
            LedgerAccount.currency,
        )
        .join(
            LedgerAccount,
            LedgerAccount.wallet_id
            == Wallet.id,
        )
        .where(
            Wallet.currency
            != LedgerAccount.currency
        )
    ).all()

    return [
        IntegrityIssue(
            code="WALLET_CURRENCY_MISMATCH",
            message=(
                f"Wallet {wallet_id} currency "
                f"{wallet_currency} does not match "
                f"ledger account currency "
                f"{account_currency}."
            ),
            wallet_id=wallet_id,
        )
        for (
            wallet_id,
            wallet_currency,
            account_currency,
        ) in rows
    ]


def find_negative_wallets(
    db: Session,
) -> list[IntegrityIssue]:
    wallets = db.scalars(
        select(Wallet)
        .where(
            Wallet.available_balance < 0
        )
    ).all()

    return [
        IntegrityIssue(
            code="NEGATIVE_WALLET_BALANCE",
            message=(
                f"Wallet {wallet.id} has "
                f"negative available balance: "
                f"{wallet.available_balance}."
            ),
            wallet_id=wallet.id,
        )
        for wallet in wallets
    ]


def run_integrity_check(
    db: Session,
) -> list[IntegrityIssue]:
    """
    Run all ledger integrity checks.

    This function is read-only.
    It NEVER modifies balances or ledger records.
    """

    issues: list[IntegrityIssue] = []

    issues.extend(
        find_unbalanced_transactions(db)
    )

    issues.extend(
        find_invalid_ledger_entries(db)
    )

    issues.extend(
        find_wallet_currency_mismatches(db)
    )

    issues.extend(
        find_negative_wallets(db)
    )

    return issues