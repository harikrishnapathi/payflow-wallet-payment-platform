import uuid

from pydantic import BaseModel, ConfigDict


class RecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    wallet_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    currency: str


class RecipientSearchResponse(BaseModel):
    items: list[RecipientResponse]