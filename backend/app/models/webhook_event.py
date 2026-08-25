import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    event_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
       
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey(
        "payments.id",
        ondelete="RESTRICT",
    ),
    nullable=False,
    index=True,
)

    payload: Mapped[dict] = mapped_column(
        # PostgreSQL JSONB
        __import__(
            "sqlalchemy.dialects.postgresql",
            fromlist=["JSONB"],
        ).JSONB,
        nullable=False,
    )

    signature: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
__table_args__ = (
    Index(
        "uq_webhook_provider_event",
        "provider",
        "event_id",
        unique=True,
    ),
)