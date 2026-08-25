import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_transaction import LedgerTransactionType

from app.services.payment_provider import process_payment
from app.services.payment_state_machine import transition_payment

from app.services.transaction_service import (
    create_ledger_transaction,
    get_wallet_account,
    fingerprint,
)


def process_payment_event(
    db: Session,
    payment_id: uuid.UUID,
) -> Payment:

    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
    )

    if payment is None:
        raise ValueError("Payment not found.")

    # ---------------------------------------------------------
    # Idempotent processing
    # ---------------------------------------------------------

    if payment.status in {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
        PaymentStatus.REFUNDED,
    }:
        return payment

    if payment.status == PaymentStatus.PENDING:
        transition_payment(
            db,
            payment.id,
            PaymentStatus.PROCESSING,
        )

    elif payment.status != PaymentStatus.PROCESSING:
        raise ValueError(
            f"Payment cannot be processed from "
            f"{payment.status.value}."
        )

    # ---------------------------------------------------------
    # Process external provider
    # ---------------------------------------------------------

    result = process_payment(
        payment.id,
        payment.amount,
        payment.currency,
    )

    if not result.success:

        transition_payment(
            db,
            payment.id,
            PaymentStatus.FAILED,
            failure_code=result.failure_code,
            failure_message=result.failure_message,
        )

        db.flush()

        return payment

    # ---------------------------------------------------------
    # Provider succeeded
    # ---------------------------------------------------------

    payment.provider_payment_id = (
        result.provider_payment_id
    )

    transition_payment(
        db,
        payment.id,
        PaymentStatus.SUCCEEDED,
    )

    # ---------------------------------------------------------
    # Financial ledger
    #
    # External payment funds the user's wallet:
    #
    # SYSTEM     DEBIT
    # USER       CREDIT
    # ---------------------------------------------------------

    system_account = db.scalar(
        select(LedgerAccount)
        .where(
            LedgerAccount.account_type
            == LedgerAccountType.SYSTEM,
            LedgerAccount.currency
            == payment.currency,
            LedgerAccount.wallet_id.is_(None),
        )
        .with_for_update()
    )

    if system_account is None:
        raise ValueError(
            "System ledger account not configured."
        )

    wallet_account = get_wallet_account(
        db,
        payment.wallet_id,
    )

    ledger_fingerprint = fingerprint(
        transaction_type=LedgerTransactionType.PAYMENT,
        amount=payment.amount,
        currency=payment.currency,
        target_wallet_id=payment.wallet_id,
        description=f"Payment {payment.id}",
    )

    create_ledger_transaction(
        db,
        LedgerTransactionType.PAYMENT,
        system_account,
        wallet_account,
        payment.amount,
        f"payment:{payment.id}:ledger",
        ledger_fingerprint,
        f"Payment {payment.id}",
    )

    db.flush()

    return payment