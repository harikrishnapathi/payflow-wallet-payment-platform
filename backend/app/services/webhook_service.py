import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.models.webhook_event import WebhookEvent
from app.services.payment_state_machine import transition_payment


def generate_signature(
    payload: dict,
    secret: str,
) -> str:
    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    return hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    payload: dict,
    signature: str,
    secret: str,
) -> bool:
    expected = generate_signature(
        payload,
        secret,
    )

    return hmac.compare_digest(
        expected,
        signature,
    )


def process_webhook(
    db: Session,
    *,
    provider: str,
    event_id: str,
    event_type: str,
    payment_id: uuid.UUID,
    payload: dict,
    signature: str,
    secret: str,
) -> WebhookEvent:

    # 1. Verify provider signature before touching payment state.
    if not verify_signature(
        payload,
        signature,
        secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    # 2. Lock the existing webhook event if this event
    #    has already been received.
    existing_event = db.scalar(
        select(WebhookEvent)
        .where(
            WebhookEvent.provider == provider,
            WebhookEvent.event_id == event_id,
        )
        .with_for_update()
    )

    if existing_event:
        return existing_event

    # 3. Lock the payment so concurrent webhooks cannot
    #    mutate it simultaneously.
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
    )

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found.",
        )

    # 4. Store the webhook event.
    webhook_event = WebhookEvent(
        provider=provider,
        event_id=event_id,
        event_type=event_type,
        payment_id=payment_id,
        payload=payload,
        signature=signature,
    )

    db.add(webhook_event)
    db.flush()

    # 5. Apply the provider event.
    if event_type == "PAYMENT_SUCCEEDED":

        if payment.status not in {
            PaymentStatus.SUCCEEDED,
            PaymentStatus.REFUNDED,
        }:
            transition_payment(
                db,
                payment.id,
                PaymentStatus.SUCCEEDED,
            )

    elif event_type == "PAYMENT_FAILED":

        if payment.status not in {
            PaymentStatus.FAILED,
            PaymentStatus.SUCCEEDED,
            PaymentStatus.REFUNDED,
        }:
            transition_payment(
                db,
                payment.id,
                PaymentStatus.FAILED,
                failure_code=payload.get(
                    "failure_code"
                ),
                failure_message=payload.get(
                    "failure_message"
                ),
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported webhook event: {event_type}",
        )

    webhook_event.processed_at = datetime.now(
        timezone.utc
    )

    db.flush()

    return webhook_event