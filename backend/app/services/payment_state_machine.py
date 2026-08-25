from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus


ALLOWED_TRANSITIONS: dict[
    PaymentStatus,
    set[PaymentStatus],
] = {
    PaymentStatus.CREATED: {
        PaymentStatus.PENDING,
    },

    PaymentStatus.PENDING: {
        PaymentStatus.PROCESSING,
        PaymentStatus.FAILED,
    },

    PaymentStatus.PROCESSING: {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
    },

    PaymentStatus.SUCCEEDED: {
        PaymentStatus.REFUNDABLE,
    },

    PaymentStatus.REFUNDABLE: {
        PaymentStatus.REFUNDED,
    },

    PaymentStatus.FAILED: set(),

    PaymentStatus.REFUNDED: set(),
}


class InvalidPaymentTransition(Exception):
    pass


def get_payment_for_update(
    db: Session,
    payment_id: uuid.UUID,
) -> Payment:
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == payment_id)
        .with_for_update()
    )

    if payment is None:
        raise ValueError(
            "Payment not found."
        )

    return payment


def transition_payment(
    db: Session,
    payment_id: uuid.UUID,
    new_status: PaymentStatus,
    *,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> Payment:

    payment = get_payment_for_update(
        db,
        payment_id,
    )

    current_status = payment.status

    allowed_states = ALLOWED_TRANSITIONS.get(
        current_status,
        set(),
    )

    if new_status not in allowed_states:
        raise InvalidPaymentTransition(
            f"Invalid payment transition: "
            f"{current_status.value} -> "
            f"{new_status.value}"
        )

    payment.status = new_status

    if new_status == PaymentStatus.FAILED:
        payment.failure_code = failure_code
        payment.failure_message = failure_message

    if new_status != PaymentStatus.FAILED:
        payment.failure_code = None
        payment.failure_message = None

    db.flush()

    return payment