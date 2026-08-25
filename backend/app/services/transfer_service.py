import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.ledger_transaction import (
    LedgerTransaction,
    LedgerTransactionType,
)
from app.models.wallet import Wallet
from app.services.risk_service import (
    check_transfer_limits_for_account,
)
from app.services.transaction_service import (
    create_ledger_transaction,
    get_wallet_account,
    get_wallet_for_update,
    fingerprint,
)


def transfer(
    db: Session,
    sender_wallet_id: uuid.UUID,
    recipient_wallet_id: uuid.UUID,
    amount: int,
    idempotency_key: str,
    description: str | None = None,
):
    if amount <= 0:
        raise ValueError(
            "Transfer amount must be greater than zero."
        )

    if sender_wallet_id == recipient_wallet_id:
        raise ValueError(
            "Cannot transfer to the same wallet."
        )

    # Lock wallets in deterministic order to reduce deadlock risk.
    wallet_ids = sorted(
        [sender_wallet_id, recipient_wallet_id],
        key=str,
    )

    wallets = {
        wallet_id: get_wallet_for_update(db, wallet_id)
        for wallet_id in wallet_ids
    }

    sender = wallets[sender_wallet_id]
    recipient = wallets[recipient_wallet_id]

    if sender.status.value != "ACTIVE":
        raise ValueError(
            "Sender wallet is not active."
        )

    if recipient.status.value != "ACTIVE":
        raise ValueError(
            "Recipient wallet is not active."
        )

    if sender.currency != recipient.currency:
        raise ValueError(
            "Wallet currencies must match."
        )

    request_fingerprint = fingerprint(
        transaction_type=LedgerTransactionType.TRANSFER,
        amount=amount,
        currency=sender.currency,
        source_wallet_id=sender_wallet_id,
        target_wallet_id=recipient_wallet_id,
        description=description,
    )

    # Idempotency MUST be checked before risk limits so retries
    # return the original transaction without consuming limits.
    existing = db.scalar(
        select(LedgerTransaction)
        .where(
            LedgerTransaction.idempotency_key == idempotency_key
        )
        .with_for_update()
    )

    if existing:
        if existing.request_fingerprint != request_fingerprint:
            raise ValueError(
                "Idempotency key was already used "
                "for a different request."
            )
        return existing

    sender_account = get_wallet_account(
        db,
        sender_wallet_id,
    )
    recipient_account = get_wallet_account(
        db,
        recipient_wallet_id,
    )

    # SDE-2 risk controls:
    # - max amount per transfer
    # - daily amount limit
    # - hourly transfer velocity
    check_transfer_limits_for_account(
        db,
        sender_account.id,
        amount,
    )

    # Atomic balance debit protects against concurrent overspending.
    result = db.execute(
        update(Wallet)
        .where(
            Wallet.id == sender_wallet_id,
            Wallet.available_balance >= amount,
        )
        .values(
            available_balance=Wallet.available_balance - amount
        )
        .returning(Wallet.id)
    )

    if result.scalar_one_or_none() is None:
        raise ValueError(
            "Insufficient wallet balance."
        )

    # Credit recipient in the same database transaction.
    db.execute(
        update(Wallet)
        .where(Wallet.id == recipient_wallet_id)
        .values(
            available_balance=Wallet.available_balance + amount
        )
    )

    transaction = create_ledger_transaction(
        db=db,
        transaction_type=LedgerTransactionType.TRANSFER,
        debit_account=sender_account,
        credit_account=recipient_account,
        amount=amount,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        description=description,
    )

    db.flush()

    return transaction