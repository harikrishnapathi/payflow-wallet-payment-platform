from fastapi import HTTPException, Request, status

from app.services.rate_limit_service import (
    RateLimitExceeded,
    check_rate_limit,
)


TRANSACTION_RATE_LIMIT = 20
TRANSACTION_RATE_WINDOW = 60

PAYMENT_RATE_LIMIT = 10
PAYMENT_RATE_WINDOW = 60

REFUND_RATE_LIMIT = 10
REFUND_RATE_WINDOW = 60


def _client_ip(request: Request) -> str:
    return (
        request.client.host
        if request.client
        else "unknown"
    )


def _rate_limit(
    request: Request,
    *,
    prefix: str,
    limit: int,
    window_seconds: int,
    message: str,
) -> None:
    key = f"{prefix}:ip:{_client_ip(request)}"

    try:
        check_rate_limit(
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )

    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
            headers={
                "Retry-After": str(exc.retry_after),
            },
        )


def payment_rate_limit(request: Request) -> None:
    _rate_limit(
        request,
        prefix="payment",
        limit=PAYMENT_RATE_LIMIT,
        window_seconds=PAYMENT_RATE_WINDOW,
        message=(
            "Too many payment requests. "
            "Please try again later."
        ),
    )


def transaction_rate_limit(request: Request) -> None:
    _rate_limit(
        request,
        prefix="transaction",
        limit=TRANSACTION_RATE_LIMIT,
        window_seconds=TRANSACTION_RATE_WINDOW,
        message=(
            "Too many transaction requests. "
            "Please try again later."
        ),
    )


def refund_rate_limit(request: Request) -> None:
    _rate_limit(
        request,
        prefix="refund",
        limit=REFUND_RATE_LIMIT,
        window_seconds=REFUND_RATE_WINDOW,
        message=(
            "Too many refund requests. "
            "Please try again later."
        ),
    )