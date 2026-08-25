import uuid

from pydantic import BaseModel, Field


class RefundCreateRequest(BaseModel):
    payment_id: uuid.UUID
    amount: int = Field(gt=0)


class RefundResponse(BaseModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    amount: int
    currency: str
    status: str
    idempotency_key: str

    model_config = {
        "from_attributes": True,
    }