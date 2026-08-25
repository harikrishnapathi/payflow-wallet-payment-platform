import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger_account import (
    LedgerAccount,
    LedgerAccountType,
)
from app.models.ledger_transaction import LedgerTransactionType
from app.models.payment import Payment, PaymentStatus
from app.models.refund import Refund, RefundStatus
from app.services.payment_provider import process_refund
from app.services.payment_state_machine import transition_payment
from app.services.transaction_service import (
    create_ledger_transaction,
    fingerprint,
    get_wallet_account,
)


def process_refund_event(
    db: Session,
    refund_id: uuid.UUID,
) -> Refund:

    # ---------------------------------------------------------
    # 1. Lock refund
    # ---------------------------------------------------------

    refund = db.scalar(
        select(Refund)
        .where(Refund.id == refund_id)
        .with_for_update()
    )

    if refund is None:
        raise ValueError("Refund not found.")

    # ---------------------------------------------------------
    # 2. Idempotency
    # ---------------------------------------------------------

    if refund.status == RefundStatus.SUCCEEDED:
        return refund

    if refund.status == RefundStatus.FAILED:
        return refund

    if refund.status == RefundStatus.CREATED:
        refund.status = RefundStatus.PROCESSING
        db.flush()

    elif refund.status != RefundStatus.PROCESSING:
        raise ValueError(
            f"Refund cannot be processed from "
            f"{refund.status.value}."
        )

    # ---------------------------------------------------------
    # 3. Lock payment
    # ---------------------------------------------------------

    payment = db.scalar(
        select(Payment)
        .where(Payment.id == refund.payment_id)
        .with_for_update()
    )

    if payment is None:
        raise ValueError("Payment not found.")

    # ---------------------------------------------------------
    # 4. Process provider refund
    # ---------------------------------------------------------

    result = process_refund(
        refund.id,
        payment.id,
        refund.amount,
        refund.currency,
    )

    if not result.success:
        refund.status = RefundStatus.FAILED
        refund.failure_code = result.failure_code
        refund.failure_message = result.failure_message

        db.flush()

        return refund

    # ---------------------------------------------------------
    # 5. Store provider refund ID
    # ---------------------------------------------------------

    refund.provider_refund_id = result.provider_refund_id

    # ---------------------------------------------------------
    # 6. Find system account
    # ---------------------------------------------------------

    system_account = db.scalar(
        select(LedgerAccount)
        .where(
            LedgerAccount.account_type
            == LedgerAccountType.SYSTEM,
            LedgerAccount.currency
            == refund.currency,
            LedgerAccount.wallet_id.is_(None),
        )
        .with_for_update()
    )

    if system_account is None:
        raise ValueError(
            "System ledger account not configured."
        )

    # ---------------------------------------------------------
    # 7. Find user's wallet ledger account
    # ---------------------------------------------------------

    wallet_account = get_wallet_account(
        db,
        payment.wallet_id,
    )

    # ---------------------------------------------------------
    # 8. Create refund ledger transaction
    #
    # Original payment:
    #
    # SYSTEM       DEBIT
    # USER WALLET  CREDIT
    #
    # Refund:
    #
    # USER WALLET  DEBIT
    # SYSTEM       CREDIT
    # ---------------------------------------------------------

    ledger_fingerprint = fingerprint(
        transaction_type=LedgerTransactionType.REFUND,
        amount=refund.amount,
        currency=refund.currency,
        source_wallet_id=payment.wallet_id,
        target_wallet_id=None,
        description=f"Refund {refund.id}",
    )

    create_ledger_transaction(
        db,
        LedgerTransactionType.REFUND,
        wallet_account,
        system_account,
        refund.amount,
        f"refund:{refund.id}:ledger",
        ledger_fingerprint,
        f"Refund {refund.id}",
    )

    # ---------------------------------------------------------
    # 9. Mark refund succeeded
    # ---------------------------------------------------------

    refund.status = RefundStatus.SUCCEEDED

    # ---------------------------------------------------------
    # 10. Payment:
    #
    # REFUNDABLE → REFUNDED
    # ---------------------------------------------------------

    if payment.status == PaymentStatus.REFUNDABLE:
        transition_payment(
            db,
            payment.id,
            PaymentStatus.REFUNDED,
        )

    elif payment.status != PaymentStatus.REFUNDED:
        raise ValueError(
            "Payment is not in a refundable state."
        )

    db.flush()

    return refund