import uuid

from pydantic import BaseModel


class PaymentWebhookRequest(BaseModel):
    event_id: str
    event_type: str
    payment_id: uuid.UUID
    payload: dict


class WebhookResponse(BaseModel):
    event_id: str
    status: str