import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DepositRequest(BaseModel):
    amount: int = Field(
        gt=0,
        le=10_000_000_000,
    )
    description: str | None = Field(
        default=None,
        max_length=500,
    )


class WithdrawalRequest(DepositRequest):
    pass


class TransferRequest(BaseModel):
    recipient_wallet_id: uuid.UUID
    amount: int = Field(
        gt=0,
        le=10_000_000_000,
    )
    description: str | None = Field(
        default=None,
        max_length=500,
    )


class TransactionResponse(BaseModel):
    """
    Transaction representation returned to the frontend.

    Amount is stored in integer paise.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_type: str

    reference_id: uuid.UUID | None = None

    currency: str

    description: str | None = None

    idempotency_key: str | None = None

    created_at: datetime

    # Financial information
    amount: int

    # DEBIT / CREDIT from the perspective
    # of the authenticated user's wallet.
    entry_type: str

    # Positive / negative representation.
    direction: str

    # Human-readable counterparty information.
    #
    # For deposits/withdrawals these are None
    # because the counterparty is the platform/system.
    counterparty_name: str | None = None
    counterparty_email: str | None = None
    counterparty_wallet_id: uuid.UUID | None = None

    # Useful for frontend display.
    is_incoming: bool


class TransactionDetail(TransactionResponse):
    entries: list["LedgerEntryResponse"]


class LedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ledger_account_id: uuid.UUID
    entry_type: str
    amount: int