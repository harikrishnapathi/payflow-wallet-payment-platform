import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.outbox_event import (
    OutboxEvent,
    OutboxEventStatus,
)
from app.services.payment_processing_service import (
    process_payment_event,
)
from app.services.refund_processing_service import (
    process_refund_event,
)

BATCH_SIZE = 10
MAX_ATTEMPTS = 5
BASE_RETRY_SECONDS = 5


def claim_events(db: Session) -> list[OutboxEvent]:
    now = datetime.now(timezone.utc) 
    events = db.scalars(
        select(OutboxEvent)
        .where(
            OutboxEvent.status.in_(
                [
                    OutboxEventStatus.PENDING,
                    OutboxEventStatus.FAILED,
                ]
            ),
            OutboxEvent.available_at <= now,
            OutboxEvent.attempts < MAX_ATTEMPTS,
        )
        .order_by(OutboxEvent.created_at)
        .limit(BATCH_SIZE)
        .with_for_update(
            skip_locked=True,
        )
    ).all()

    for event in events:
        event.status = OutboxEventStatus.PROCESSING
        event.attempts += 1

    db.flush()

    return events


def publish_event(
    db: Session,
    event: OutboxEvent,
) -> None:

    if event.event_type == "PAYMENT_CREATED":
        process_payment_event(
            db,
            event.aggregate_id,
        )
        return

    if event.event_type == "REFUND_CREATED":
        process_refund_event(
            db,
            event.aggregate_id,
        )
        return

    raise ValueError(
        f"Unsupported event type: {event.event_type}"
    )

def process_event(
    db: Session,
    event: OutboxEvent,
) -> None:
    try:
        publish_event(
            db,
            event,
        )

        event.status = OutboxEventStatus.PUBLISHED
        event.processed_at = datetime.now(
            timezone.utc
        )
        event.last_error = None

    except Exception as exc:
        event.status = OutboxEventStatus.FAILED
        event.last_error = str(exc)

        delay = BASE_RETRY_SECONDS * (
            2 ** max(event.attempts - 1, 0)
        )

        event.available_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=delay)
        )


def run_once() -> int:
    db: Session = SessionLocal()

    try:
        events = claim_events(db)

        if not events:
            db.commit()
            return 0

        for event in events:
            process_event(
                db,
                event,
            )

        db.commit()

        return len(events)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def run_worker() -> None:
    print(
        "Outbox worker started..."
    )

    while True:
        try:
            processed = run_once()

            if processed == 0:
                time.sleep(2)

        except KeyboardInterrupt:
            print(
                "Outbox worker stopped."
            )
            break

        except Exception as exc:
            print(
                f"[OUTBOX ERROR] {exc}"
            )
            time.sleep(5)


if __name__ == "__main__":
    run_worker()