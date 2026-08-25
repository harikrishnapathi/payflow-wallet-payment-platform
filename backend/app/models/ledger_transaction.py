import enum
import uuid

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    String,
    UniqueConstraint,
    func,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.session import Base


class LedgerTransactionType(
    str,
    enum.Enum,
):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    FEE = "FEE"
    ADJUSTMENT = "ADJUSTMENT"


class LedgerTransaction(Base):

    __tablename__ = "ledger_transactions"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_ledger_transaction_idempotency_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    transaction_type: Mapped[
        LedgerTransactionType
    ] = mapped_column(
        Enum(
            LedgerTransactionType,
            name="ledger_transaction_type",
        ),
        nullable=False,
    )

    reference_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    description: Mapped[
        str | None
    ] = mapped_column(
        String(500),
        nullable=True,
    )

    idempotency_key: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    request_fingerprint: Mapped[
        str | None
    ] = mapped_column(
        String(64),
        nullable=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    entries: Mapped[
        list["LedgerEntry"]
    ] = relationship(
        "LedgerEntry",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def amount(self) -> int:
        """
        Transaction amount is stored on the
        double-entry ledger entries.

        Every financial transaction created
        by PayFlow has exactly two entries:
        one debit and one credit.

        Both entries contain the same amount.
        """

        if not self.entries:
            return 0

        return self.entries[0].amount

    @property
    def entry_type(self) -> str | None:
        """
        Returns the first ledger entry type.

        Used by the API/frontend for displaying
        debit/credit direction.
        """

        if not self.entries:
            return None

        return self.entries[0].entry_type.value