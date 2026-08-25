import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.models.provider_event import (
    ProviderEvent,
    ProviderEventStatus,
)
from app.services.payment_processing_service import (
    process_payment_event,
)
from app.services.payment_state_machine import (
    transition_payment,
)
from app.services.provider_event_service import (
    mark_provider_event_failed,
    mark_provider_event_processed,
    receive_provider_event,
)
from app.services.refund_processing_service import (
    process_refund_event,
)


class WebhookProcessingError(Exception):
    pass


def process_provider_webhook(
    db: Session,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload: dict,
) -> ProviderEvent:
    """
    Receive and process a provider webhook exactly once.

    Provider event ID provides idempotency.
    """

    event = receive_provider_event(
        db,
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        payload=payload,
    )

    if event.status == ProviderEventStatus.PROCESSED:
        return event

    if event.status == ProviderEventStatus.IGNORED:
        return event

    if event.status == ProviderEventStatus.FAILED:
        event.attempts += 1

    try:
        # ---------------------------------------------------------
        # PAYMENT WEBHOOKS
        # ---------------------------------------------------------

        payment_id = payload.get("payment_id")

        if event_type in {
            "payment.succeeded",
            "payment.failed",
        }:
            if not payment_id:
                raise WebhookProcessingError(
                    "payment_id is required."
                )

            try:
                payment_uuid = uuid.UUID(
                    str(payment_id)
                )
            except ValueError as exc:
                raise WebhookProcessingError(
                    "Invalid payment_id."
                ) from exc

            payment = db.scalar(
                select(Payment)
                .where(Payment.id == payment_uuid)
                .with_for_update()
            )

            if payment is None:
                raise WebhookProcessingError(
                    "Payment not found."
                )

            # -----------------------------------------------------
            # PAYMENT SUCCEEDED
            # -----------------------------------------------------

            if event_type == "payment.succeeded":
                process_payment_event(
                    db,
                    payment_uuid,
                )

            # -----------------------------------------------------
            # PAYMENT FAILED
            # -----------------------------------------------------

            elif event_type == "payment.failed":
                failure_code = payload.get(
                    "failure_code",
                    "PAYMENT_FAILED",
                )

                failure_message = payload.get(
                    "failure_message",
                    "Payment failed.",
                )

                if payment.status in {
                    PaymentStatus.SUCCEEDED,
                    PaymentStatus.REFUNDED,
                }:
                    raise WebhookProcessingError(
                        "A completed payment cannot "
                        "be marked as failed."
                    )

                if payment.status == PaymentStatus.PENDING:
                    transition_payment(
                        db,
                        payment.id,
                        PaymentStatus.PROCESSING,
                    )

                if payment.status == PaymentStatus.PROCESSING:
                    transition_payment(
                        db,
                        payment.id,
                        PaymentStatus.FAILED,
                        failure_code=failure_code,
                        failure_message=failure_message,
                    )

                elif payment.status != PaymentStatus.FAILED:
                    raise WebhookProcessingError(
                        "Payment cannot be marked "
                        f"failed from "
                        f"{payment.status.value}."
                    )

                db.flush()

        # ---------------------------------------------------------
        # REFUND WEBHOOK
        # ---------------------------------------------------------

        elif event_type == "refund.succeeded":
            refund_id = payload.get("refund_id")

            if not refund_id:
                raise WebhookProcessingError(
                    "refund_id is required."
                )

            try:
                refund_uuid = uuid.UUID(
                    str(refund_id)
                )
            except ValueError as exc:
                raise WebhookProcessingError(
                    "Invalid refund_id."
                ) from exc

            process_refund_event(
                db,
                refund_uuid,
            )

        # ---------------------------------------------------------
        # UNKNOWN EVENT
        # ---------------------------------------------------------

        else:
            event.status = (
                ProviderEventStatus.IGNORED
            )

            event.processed_at = datetime.now(
                timezone.utc
            )

            db.flush()

            return event

        # ---------------------------------------------------------
        # MARK EVENT PROCESSED
        # ---------------------------------------------------------

        return mark_provider_event_processed(
            db,
            event,
        )

    # -------------------------------------------------------------
    # EXPECTED WEBHOOK PROCESSING FAILURE
    # -------------------------------------------------------------

    except WebhookProcessingError:
        mark_provider_event_failed(
            db,
            event,
            "Webhook processing failed.",
        )
        raise

    # -------------------------------------------------------------
    # UNEXPECTED FAILURE
    # -------------------------------------------------------------

    except Exception as exc:
        mark_provider_event_failed(
            db,
            event,
            str(exc),
        )

        raise WebhookProcessingError(
            str(exc)
        ) from exc