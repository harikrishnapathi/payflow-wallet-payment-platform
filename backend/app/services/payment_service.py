import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.wallet import Wallet
from app.services.transaction_service import fingerprint
from app.services.payment_state_machine import transition_payment
from app.services.outbox_service import create_outbox_event


def create_payment(
    db: Session,
    *,
    user_id: uuid.UUID,
    wallet_id: uuid.UUID,
    amount: int,
    currency: str,
    idempotency_key: str,
) -> Payment:

    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment amount must be greater than zero.",
        )

    currency = currency.upper()

    if len(currency) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Currency must be a 3-letter ISO code.",
        )

    wallet = db.scalar(
        select(Wallet)
        .where(
            Wallet.id == wallet_id,
            Wallet.user_id == user_id,
        )
        .with_for_update()
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    if wallet.status.value != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet is not active.",
        )

    if wallet.currency != currency:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment currency does not match wallet currency.",
        )

    request_fingerprint = fingerprint(
        transaction_type="PAYMENT",
        amount=amount,
        currency=currency,
        source_wallet_id=wallet_id,
        description=None,
    )

    existing = db.scalar(
        select(Payment)
        .where(
            Payment.idempotency_key == idempotency_key
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
                    "for a different payment request."
                ),
            )

        return existing

    payment = Payment(
        user_id=user_id,
        wallet_id=wallet_id,
        amount=amount,
        currency=currency,
        status=PaymentStatus.CREATED,
        provider=PaymentProvider.SIMULATOR,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )

    db.add(payment)
    db.flush()

    transition_payment(
        db,
        payment.id,
        PaymentStatus.PENDING,
    )

    create_outbox_event(
        db,
        event_type="PAYMENT_CREATED",
        aggregate_type="PAYMENT",
        aggregate_id=payment.id,
        payload={
            "payment_id": str(payment.id),
            "user_id": str(payment.user_id),
            "wallet_id": str(payment.wallet_id),
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status.value,
            "provider": payment.provider.value,
            "idempotency_key": payment.idempotency_key,
        },
    )

    db.flush()

    return payment