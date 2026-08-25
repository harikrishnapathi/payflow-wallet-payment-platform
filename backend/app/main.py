from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.payments import router as payments_router
from app.api.refunds import router as refunds_router
from app.api.recipients import router as recipients_router
from app.api.transactions import router as transaction_router
from app.api.wallet import router as wallet_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.api.reconciliation import router as reconciliation_router
from app.api.integrity import router as integrity_router


app = FastAPI(
    title="PayFlow API",
    description="Production-oriented digital wallet and payment platform.",
    version="1.2.0",
)


origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    health_router,
)


app.include_router(
    auth_router,
    prefix="/api/v1",
)


app.include_router(
    wallet_router,
    prefix="/api/v1",
)


app.include_router(
    transaction_router,
    prefix="/api/v1",
)


app.include_router(
    recipients_router,
    prefix="/api/v1",
)


app.include_router(
    admin_router,
    prefix="/api/v1",
)


app.include_router(
    payments_router,
    prefix="/api/v1",
)


app.include_router(
    webhooks_router,
    prefix="/api/v1",
)


app.include_router(
    refunds_router,
    prefix="/api/v1",
)

app.include_router(
    reconciliation_router,
    prefix="/api/v1",
)

app.include_router(
    integrity_router,
    prefix="/api/v1",
)