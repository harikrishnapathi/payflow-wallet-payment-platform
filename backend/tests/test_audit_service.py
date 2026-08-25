import uuid

from app.models.audit_log import AuditLog
from app.services.audit_service import (
    audit_payment,
    audit_refund,
    audit_transaction,
    create_audit_log,
)


def test_create_audit_log(db):
    user_id = uuid.uuid4()
    resource_id = uuid.uuid4()

    audit = create_audit_log(
        db,
        action="TRANSFER_CREATED",
        user_id=user_id,
        resource_type="TRANSACTION",
        resource_id=resource_id,
        request_id="req-test-001",
        ip_address="127.0.0.1",
        user_agent="pytest",
        metadata={
            "amount": 5000,
            "currency": "INR",
        },
    )

    db.flush()

    assert audit.id is not None
    assert audit.user_id == user_id
    assert audit.action == "TRANSFER_CREATED"
    assert audit.resource_type == "TRANSACTION"
    assert audit.resource_id == resource_id
    assert audit.request_id == "req-test-001"
    assert audit.ip_address == "127.0.0.1"
    assert audit.metadata_json["amount"] == 5000


def test_audit_transaction(db):
    user_id = uuid.uuid4()
    transaction_id = uuid.uuid4()

    audit = audit_transaction(
        db,
        user_id=user_id,
        action="TRANSFER_SUCCEEDED",
        transaction_id=transaction_id,
        metadata={
            "amount": 2000,
        },
    )

    db.flush()

    assert audit.resource_type == "TRANSACTION"
    assert audit.resource_id == transaction_id
    assert audit.action == "TRANSFER_SUCCEEDED"


def test_audit_payment(db):
    user_id = uuid.uuid4()
    payment_id = uuid.uuid4()

    audit = audit_payment(
        db,
        user_id=user_id,
        action="PAYMENT_CREATED",
        payment_id=payment_id,
    )

    db.flush()

    assert audit.resource_type == "PAYMENT"
    assert audit.resource_id == payment_id


def test_audit_refund(db):
    user_id = uuid.uuid4()
    refund_id = uuid.uuid4()

    audit = audit_refund(
        db,
        user_id=user_id,
        action="REFUND_CREATED",
        refund_id=refund_id,
    )

    db.flush()

    assert audit.resource_type == "REFUND"
    assert audit.resource_id == refund_id


def test_audit_log_is_persisted(db):
    audit = AuditLog(
        action="LOGIN",
        metadata_json={
            "method": "password",
        },
    )

    db.add(audit)
    db.flush()

    stored = db.get(
        AuditLog,
        audit.id,
    )

    assert stored is not None
    assert stored.action == "LOGIN"