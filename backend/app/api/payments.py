from fastapi import APIRouter, Depends, Header, HTTPException, status
from app.api.rate_limit import payment_rate_limit
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentResponse,
)
from app.services.payment_service import create_payment


router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


@router.post(
    "",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_endpoint(
    request: PaymentCreateRequest,
     _: None = Depends(payment_rate_limit),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required.",
        )

    payment = create_payment(
        db,
        user_id=current_user.id,
        wallet_id=request.wallet_id,
        amount=request.amount,
        currency=request.currency,
        idempotency_key=idempotency_key.strip(),
    )

    db.commit()
    db.refresh(payment)

    return payment