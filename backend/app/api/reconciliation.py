import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.reconciliation_service import (
    reconcile_all_wallets,
    reconcile_wallet,
)

router = APIRouter(
    prefix="/admin/reconciliation",
    tags=["Reconciliation"],
)


class ReconciliationResponse(BaseModel):
    wallet_id: uuid.UUID
    wallet_balance: int
    ledger_balance: int
    difference: int
    is_balanced: bool


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.value != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required.",
        )

    return user


@router.get(
    "/wallet/{wallet_id}",
    response_model=ReconciliationResponse,
)
def reconcile_single_wallet(
    wallet_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = reconcile_wallet(
            db,
            wallet_id,
        )

        return ReconciliationResponse(
            wallet_id=result.wallet_id,
            wallet_balance=result.wallet_balance,
            ledger_balance=result.ledger_balance,
            difference=result.difference,
            is_balanced=result.is_balanced,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )


@router.get(
    "/all",
    response_model=list[ReconciliationResponse],
)
def reconcile_all(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    results = reconcile_all_wallets(db)

    return [
        ReconciliationResponse(
            wallet_id=result.wallet_id,
            wallet_balance=result.wallet_balance,
            ledger_balance=result.ledger_balance,
            difference=result.difference,
            is_balanced=result.is_balanced,
        )
        for result in results
    ]