import uuid
from datetime import datetime, timedelta, timezone

from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.outbox_event import (
    OutboxEvent,
    OutboxEventStatus,
)
from app.models.payment import (
    Payment,
    PaymentProvider,
    PaymentStatus,
)
from app.models.user import User

from app.services.outbox_service import create_outbox_event
from app.services.wallet_service import create_user_wallet
from app.workers.outbox_worker import (
    claim_events,
    process_event,
)


def create_test_user(db, prefix="outbox"):
    user = User(
        id=uuid.uuid4(),
        email=f"{prefix}-{uuid.uuid4()}@example.com",
        password_hash="test-password-hash",
        first_name="Outbox",
        last_name="Test",
    )

    db.add(user)
    db.flush()

    return user


def create_system_account(db):
    account = LedgerAccount(
        account_type=LedgerAccountType.SYSTEM,
        currency="INR",
        wallet_id=None,
    )

    db.add(account)
    db.flush()

    return account


def create_pending_payment(db):
    user = create_test_user(db)

    wallet = create_user_wallet(
        db,
        user,
    )

    create_system_account(db)

    payment = Payment(
        user_id=user.id,
        wallet_id=wallet.id,
        amount=5000,
        currency="INR",
        status=PaymentStatus.PENDING,
        provider=PaymentProvider.SIMULATOR,
        idempotency_key=f"outbox-payment-{uuid.uuid4()}",
        request_fingerprint="test-fingerprint",
    )

    db.add(payment)
    db.flush()

    return payment


def test_create_outbox_event_starts_pending(db):
    aggregate_id = uuid.uuid4()

    event = create_outbox_event(
        db,
        event_type="TEST_EVENT",
        aggregate_type="TEST",
        aggregate_id=aggregate_id,
        payload={"hello": "world"},
    )

    assert event.status == OutboxEventStatus.PENDING
    assert event.attempts == 0
    assert event.aggregate_id == aggregate_id
    assert event.payload == {"hello": "world"}


def test_outbox_claim_changes_event_to_processing(db):
    event = OutboxEvent(
        event_type="TEST_EVENT",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        payload={"test": True},
        status=OutboxEventStatus.PENDING,
        attempts=0,
        available_at=datetime(
            2000,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        created_at=datetime(
            2000,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    db.add(event)
    db.flush()

    events = claim_events(db)

    claimed = next(
        (
            item
            for item in events
            if item.id == event.id
        ),
        None,
    )

    assert claimed is not None
    assert claimed.status == OutboxEventStatus.PROCESSING
    assert claimed.attempts == 1

def test_payment_outbox_event_is_published(db):
    payment = create_pending_payment(db)

    event = create_outbox_event(
        db,
        event_type="PAYMENT_CREATED",
        aggregate_type="PAYMENT",
        aggregate_id=payment.id,
        payload={
            "payment_id": str(payment.id),
        },
    )

    process_event(
        db,
        event,
    )

    db.flush()

    assert event.status == OutboxEventStatus.PUBLISHED
    assert event.processed_at is not None
    assert event.last_error is None

    assert payment.status == PaymentStatus.SUCCEEDED


def test_unknown_outbox_event_is_marked_failed(db):
    event = OutboxEvent(
        event_type="UNKNOWN_EVENT",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        payload={},
        status=OutboxEventStatus.PROCESSING,
        attempts=1,
        available_at=datetime.now(timezone.utc),
    )

    db.add(event)
    db.flush()

    process_event(
        db,
        event,
    )

    assert event.status == OutboxEventStatus.FAILED
    assert event.last_error is not None
    assert event.attempts == 1

    def test_failed_outbox_event_gets_retry_delay(db):
     event = OutboxEvent(
        event_type="UNKNOWN_EVENT",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        payload={},
        status=OutboxEventStatus.PROCESSING,
        attempts=1,
        available_at=datetime.now(timezone.utc),
    )

    db.add(event)
    db.flush()

    before = datetime.now(timezone.utc)

    process_event(
        db,
        event,
    )

    after = datetime.now(timezone.utc)

    assert event.status == OutboxEventStatus.FAILED
    assert event.last_error is not None
    assert event.available_at >= before + __import__(
        "datetime"
    ).timedelta(seconds=5)
    assert event.available_at <= after + __import__(
        "datetime"
    ).timedelta(seconds=5)


def test_outbox_retry_backoff_increases_with_attempts(db):
    event = OutboxEvent(
        event_type="UNKNOWN_EVENT",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        payload={},
        status=OutboxEventStatus.PROCESSING,
        attempts=3,
        available_at=datetime.now(timezone.utc),
    )

    db.add(event)
    db.flush()

    before = datetime.now(timezone.utc)

    process_event(
        db,
        event,
    )

    assert event.status == OutboxEventStatus.FAILED

    # attempts=3 → 5 * 2^(3-1) = 20 seconds
    expected = before + __import__(
        "datetime"
    ).timedelta(seconds=20)

    assert event.available_at >= expected


def test_outbox_max_attempts_constant_is_five():
    from app.workers.outbox_worker import MAX_ATTEMPTS

    assert MAX_ATTEMPTS == 5