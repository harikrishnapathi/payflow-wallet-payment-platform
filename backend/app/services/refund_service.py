import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.models.refund import Refund, RefundStatus
from app.services.outbox_service import create_outbox_event
from app.services.payment_state_machine import transition_payment
from app.services.transaction_service import fingerprint


def create_refund(
    db: Session,
    *,
    user_id: uuid.UUID,
    payment_id: uuid.UUID,
    amount: int,
    idempotency_key: str,
) -> Refund:

    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund amount must be greater than zero.",
        )

    # ---------------------------------------------------------
    # 1. Check idempotency first
    # ---------------------------------------------------------

    request_fingerprint = fingerprint(
        transaction_type="REFUND",
        amount=amount,
        currency="INR",
        source_wallet_id=None,
        description=f"REFUND:{payment_id}",
    )

    existing = db.scalar(
        select(Refund)
        .where(
            Refund.idempotency_key == idempotency_key,
        )
        .with_for_update()
    )

    if existing:
        if existing.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key belongs to another user.",
            )

        if existing.request_fingerprint != request_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Idempotency key was already used "
                    "for a different refund request."
                ),
            )

        return existing

    # ---------------------------------------------------------
    # 2. Lock payment
    # ---------------------------------------------------------

    payment = db.scalar(
        select(Payment)
        .where(
            Payment.id == payment_id,
            Payment.user_id == user_id,
        )
        .with_for_update()
    )

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    if payment.status not in {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.REFUNDABLE,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only successful payments can be refunded."
            ),
        )

    # ---------------------------------------------------------
    # 3. Only allow full refund for now
    # ---------------------------------------------------------

    if amount != payment.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Partial refunds are not supported yet. "
                "Refund the full payment amount."
            ),
        )

    # ---------------------------------------------------------
    # 4. Prevent multiple successful refunds
    # ---------------------------------------------------------

    refunded_amount = db.scalar(
        select(
            func.coalesce(
                func.sum(Refund.amount),
                0,
            )
        )
        .where(
            Refund.payment_id == payment.id,
            Refund.status.in_(
                [
                    RefundStatus.CREATED,
                    RefundStatus.PROCESSING,
                    RefundStatus.SUCCEEDED,
                ]
            ),
        )
    ) or 0

    if refunded_amount + amount > payment.amount:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment has already been fully or partially refunded.",
        )

    # ---------------------------------------------------------
    # 5. Move payment to REFUNDABLE
    # ---------------------------------------------------------

    if payment.status == PaymentStatus.SUCCEEDED:
        transition_payment(
            db,
            payment.id,
            PaymentStatus.REFUNDABLE,
        )

    # ---------------------------------------------------------
    # 6. Create refund
    # ---------------------------------------------------------

    refund = Refund(
        payment_id=payment.id,
        user_id=user_id,
        amount=amount,
        currency=payment.currency,
        status=RefundStatus.CREATED,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )

    db.add(refund)
    db.flush()

    # ---------------------------------------------------------
    # 7. Create transactional outbox event
    # ---------------------------------------------------------

    create_outbox_event(
        db,
        event_type="REFUND_CREATED",
        aggregate_type="REFUND",
        aggregate_id=refund.id,
        payload={
            "refund_id": str(refund.id),
            "payment_id": str(payment.id),
            "user_id": str(user_id),
            "amount": refund.amount,
            "currency": refund.currency,
            "status": refund.status.value,
            "idempotency_key": refund.idempotency_key,
        },
    )

    db.flush()

    return refund