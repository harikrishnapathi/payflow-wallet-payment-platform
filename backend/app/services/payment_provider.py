import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderResult:
    success: bool
    provider_payment_id: str | None = None
    provider_refund_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


def process_payment(
    payment_id: uuid.UUID,
    amount: int,
    currency: str,
) -> ProviderResult:
    """
    Deterministic payment provider simulator.

    Every valid payment succeeds.
    """

    if amount <= 0:
        return ProviderResult(
            success=False,
            failure_code="INVALID_AMOUNT",
            failure_message=(
                "Payment amount must be greater than zero."
            ),
        )

    provider_payment_id = f"sim_{payment_id.hex}"

    return ProviderResult(
        success=True,
        provider_payment_id=provider_payment_id,
    )


def process_refund(
    refund_id: uuid.UUID,
    payment_id: uuid.UUID,
    amount: int,
    currency: str,
) -> ProviderResult:
    """
    Deterministic refund provider simulator.

    Every valid refund succeeds.
    """

    if amount <= 0:
        return ProviderResult(
            success=False,
            failure_code="INVALID_AMOUNT",
            failure_message=(
                "Refund amount must be greater than zero."
            ),
        )

    provider_refund_id = f"sim_refund_{refund_id.hex}"

    return ProviderResult(
        success=True,
        provider_refund_id=provider_refund_id,
    )