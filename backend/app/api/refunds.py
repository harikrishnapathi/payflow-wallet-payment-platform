from fastapi import (
    APIRouter,
    Depends,
    Header,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.refund import (
    RefundCreateRequest,
    RefundResponse,
)
from app.api.dependencies import get_current_user
from app.services.refund_service import create_refund
from app.api.rate_limit import refund_rate_limit


router = APIRouter(
    prefix="/refunds",
    tags=["Refunds"],
)


@router.post(
    "",
    response_model=RefundResponse,
    status_code=201,
)
def create_refund_endpoint(
    request: RefundCreateRequest,
     _: None = Depends(refund_rate_limit),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    refund = create_refund(
        db,
        user_id=current_user.id,
        payment_id=request.payment_id,
        amount=request.amount,
        idempotency_key=idempotency_key,
    )

    db.commit()
    db.refresh(refund)

    return refund
