import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.models.user import User
from app.services.wallet_service import create_user_wallet


client = TestClient(app)


def create_api_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"ratelimit-{uuid.uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="Rate",
        last_name="Limit",
    )

    db.add(user)
    db.flush()

    wallet = create_user_wallet(db, user)
    db.flush()

    return user, wallet


def auth_headers(user):
    token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
    )

    return {
        "Authorization": f"Bearer {token}",
    }


def test_payment_rate_limit_returns_429(db, monkeypatch):
    user, wallet = create_api_user(db)

    app.dependency_overrides[get_db] = lambda: db

    try:
        # Keep this test independent of the real Redis counter.
        from app.api import rate_limit

        calls = {"count": 0}

        def fake_check_rate_limit(
            *,
            key,
            limit,
            window_seconds,
        ):
            calls["count"] += 1

            if calls["count"] > 2:
                from app.services.rate_limit_service import (
                    RateLimitExceeded,
                )

                raise RateLimitExceeded(
                    retry_after=30
                )

        monkeypatch.setattr(
            rate_limit,
            "check_rate_limit",
            fake_check_rate_limit,
        )

        for i in range(2):
            response = client.post(
                "/api/v1/payments",
                json={
                    "wallet_id": str(wallet.id),
                    "amount": 100,
                    "currency": "INR",
                },
                headers={
                    **auth_headers(user),
                    "Idempotency-Key": (
                        f"rate-limit-{uuid.uuid4()}"
                    ),
                },
            )

            assert response.status_code == 201

        response = client.post(
            "/api/v1/payments",
            json={
                "wallet_id": str(wallet.id),
                "amount": 100,
                "currency": "INR",
            },
            headers={
                **auth_headers(user),
                "Idempotency-Key": (
                    f"rate-limit-{uuid.uuid4()}"
                ),
            },
        )

        assert response.status_code == 429
        assert (
            response.headers["Retry-After"]
            == "30"
        )

    finally:
        app.dependency_overrides.clear()