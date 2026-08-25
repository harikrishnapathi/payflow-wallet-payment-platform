from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.recipient import (
    RecipientResponse,
    RecipientSearchResponse,
)
from app.services.recipient_service import search_recipients


router = APIRouter(
    prefix="/recipients",
    tags=["Recipients"],
)


@router.get(
    "/search",
    response_model=RecipientSearchResponse,
)
def search_recipient_endpoint(
    q: str = Query(
        ...,
        min_length=3,
        max_length=100,
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = search_recipients(
        db,
        current_user_id=current_user.id,
        query=q,
    )

    return RecipientSearchResponse(
        items=[
            RecipientResponse(
                user_id=user.id,
                wallet_id=wallet.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                currency=wallet.currency,
            )
            for user, wallet in results
        ]
    )