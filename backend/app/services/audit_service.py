import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """
    Create an immutable audit record.

    Audit records are written inside the caller's
    database transaction. The caller decides when
    the transaction is committed.
    """

    audit = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=metadata,
    )

    db.add(audit)

    db.flush()

    return audit


def audit_transaction(
    db: Session,
    *,
    user_id: uuid.UUID,
    action: str,
    transaction_id: uuid.UUID,
    metadata: dict | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:

    return create_audit_log(
        db,
        action=action,
        user_id=user_id,
        resource_type="TRANSACTION",
        resource_id=transaction_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
    )


def audit_payment(
    db: Session,
    *,
    user_id: uuid.UUID,
    action: str,
    payment_id: uuid.UUID,
    metadata: dict | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:

    return create_audit_log(
        db,
        action=action,
        user_id=user_id,
        resource_type="PAYMENT",
        resource_id=payment_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
    )


def audit_refund(
    db: Session,
    *,
    user_id: uuid.UUID,
    action: str,
    refund_id: uuid.UUID,
    metadata: dict | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:

    return create_audit_log(
        db,
        action=action,
        user_id=user_id,
        resource_type="REFUND",
        resource_id=refund_id,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
    )