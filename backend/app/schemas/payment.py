import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCreateRequest(BaseModel):
    wallet_id: uuid.UUID
    amount: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)


class PaymentResponse(BaseModel):
    model_config = {
        "from_attributes": True
    }

    id: uuid.UUID
    user_id: uuid.UUID
    wallet_id: uuid.UUID
    amount: int
    currency: str
    status: str
    provider: str
    provider_payment_id: str | None
    idempotency_key: str
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime