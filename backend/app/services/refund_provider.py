import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class RefundProviderResult:
    success: bool
    provider_refund_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


def process_refund(
    refund_id: uuid.UUID,
    amount: int,
    currency: str,
) -> RefundProviderResult:

    if amount <= 0:
        return RefundProviderResult(
            success=False,
            failure_code="INVALID_AMOUNT",
            failure_message=(
                "Refund amount must be greater than zero."
            ),
        )

    return RefundProviderResult(
        success=True,
        provider_refund_id=f"sim_refund_{refund_id.hex}",
    )