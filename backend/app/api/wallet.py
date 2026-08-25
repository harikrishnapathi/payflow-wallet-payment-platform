from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.wallet import WalletResponse


router = APIRouter(
    prefix="/wallet",
    tags=["Wallet"],
)


@router.get(
    "/me",
    response_model=WalletResponse,
)
def get_my_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = db.scalar(
        select(Wallet).where(
            Wallet.user_id == current_user.id
        )
    )

    if wallet is None:
        # Existing users created before automatic
        # wallet creation may not have a wallet.
        from app.services.wallet_service import (
            create_user_wallet,
        )

        wallet = create_user_wallet(
            db=db,
            user=current_user,
        )

        db.commit()
        db.refresh(wallet)

    return wallet