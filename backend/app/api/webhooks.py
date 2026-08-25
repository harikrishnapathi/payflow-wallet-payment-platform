import json

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.orm import Session
from app.core.config import settings

from app.db.session import get_db
from app.services.webhook_processing_service import (
    WebhookProcessingError,
    process_provider_webhook,
)
from app.services.webhook_security_service import (
    verify_signature,
)

router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)



@router.post("/provider")
async def provider_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_signature: str | None = Header(
        default=None,
        alias="X-Webhook-Signature",
    ),
    x_webhook_timestamp: int | None = Header(
        default=None,
        alias="X-Webhook-Timestamp",
    ),
    x_provider: str = Header(
        default="SIMULATOR",
        alias="X-Provider",
    ),
    x_provider_event_id: str | None = Header(
        default=None,
        alias="X-Provider-Event-Id",
    ),
):
    body = await request.body()

    if not x_webhook_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook signature.",
        )

    if x_webhook_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook timestamp.",
        )

    if not x_provider_event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing provider event ID.",
        )

    if not verify_signature(
        body,
        x_webhook_signature,
        settings.webhook_secret,
        x_webhook_timestamp,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be an object.",
        )

    event_type = payload.get("event_type")

    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event_type.",
        )

    try:
        event = process_provider_webhook(
            db,
            provider=x_provider,
            provider_event_id=x_provider_event_id,
            event_type=event_type,
            payload=payload,
        )

        db.commit()

        return {
            "accepted": True,
            "event_id": str(event.id),
            "provider_event_id": event.provider_event_id,
            "status": event.status.value,
        }

    except WebhookProcessingError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    except Exception:
        db.rollback()
        raise