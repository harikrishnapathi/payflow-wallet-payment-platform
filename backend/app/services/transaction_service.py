import hashlib
import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry, LedgerEntryType
from app.models.ledger_transaction import (
    LedgerTransaction,
    LedgerTransactionType,
)
from app.models.wallet import Wallet


def fingerprint(
    *,
    transaction_type,
    amount,
    currency,
    source_wallet_id=None,
    target_wallet_id=None,
    description=None,
):
    payload = {
        "type": (
            transaction_type.value
            if hasattr(transaction_type, "value")
            else str(transaction_type)
        ),
        "amount": amount,
        "currency": currency,
        "source": (
            str(source_wallet_id)
            if source_wallet_id
            else None
        ),
        "target": (
            str(target_wallet_id)
            if target_wallet_id
            else None
        ),
        "description": description,
    }

    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def get_wallet_for_update(
    db: Session,
    wallet_id: uuid.UUID,
):
    wallet = db.scalar(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update()
    )

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    return wallet


def get_wallet_account(
    db: Session,
    wallet_id: uuid.UUID,
):
    account = db.scalar(
        select(LedgerAccount).where(
            LedgerAccount.wallet_id == wallet_id
        )
    )

    if not account:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Wallet ledger account not found.",
        )

    return account


def create_ledger_transaction(
    db: Session,
    transaction_type,
    debit_account,
    credit_account,
    amount,
    idempotency_key,
    request_fingerprint,
    description=None,
):
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be greater than zero.",
        )

    existing = db.scalar(
        select(LedgerTransaction)
        .where(
            LedgerTransaction.idempotency_key
            == idempotency_key
        )
        .with_for_update()
    )

    if existing:
        if (
            existing.request_fingerprint
            != request_fingerprint
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Idempotency key was already used "
                    "for a different request."
                ),
            )

        return existing

    if debit_account.id == credit_account.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Debit and credit accounts "
                "must be different."
            ),
        )

    transaction = LedgerTransaction(
        transaction_type=transaction_type,
        currency=debit_account.currency,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        description=description,
    )

    db.add(transaction)
    db.flush()

    debit_entry = LedgerEntry(
        ledger_transaction_id=transaction.id,
        ledger_account_id=debit_account.id,
        entry_type=LedgerEntryType.DEBIT,
        amount=amount,
    )

    credit_entry = LedgerEntry(
        ledger_transaction_id=transaction.id,
        ledger_account_id=credit_account.id,
        entry_type=LedgerEntryType.CREDIT,
        amount=amount,
    )

    db.add_all([
        debit_entry,
        credit_entry,
    ])

    db.flush()

    return transaction