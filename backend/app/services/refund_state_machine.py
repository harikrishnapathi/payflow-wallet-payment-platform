from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refund import Refund, RefundStatus


ALLOWED_TRANSITIONS = {
    RefundStatus.CREATED: {
        RefundStatus.PROCESSING,
        RefundStatus.FAILED,
    },
    RefundStatus.PROCESSING: {
        RefundStatus.SUCCEEDED,
        RefundStatus.FAILED,
    },
    RefundStatus.SUCCEEDED: set(),
    RefundStatus.FAILED: set(),
}


class InvalidRefundTransition(Exception):
    pass


def transition_refund(
    db: Session,
    refund_id: uuid.UUID,
    new_status: RefundStatus,
) -> Refund:

    refund = db.scalar(
        select(Refund)
        .where(Refund.id == refund_id)
        .with_for_update()
    )

    if refund is None:
        raise ValueError("Refund not found.")

    allowed = ALLOWED_TRANSITIONS.get(
        refund.status,
        set(),
    )

    if new_status not in allowed:
        raise InvalidRefundTransition(
            f"Invalid refund transition: "
            f"{refund.status.value} -> "
            f"{new_status.value}"
        )

    refund.status = new_status

    db.flush()

    return refund