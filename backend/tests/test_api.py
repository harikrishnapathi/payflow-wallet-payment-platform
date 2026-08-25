import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.models.user import User
from app.services.wallet_service import create_user_wallet


client = TestClient(app)


def create_api_user(db, prefix="api"):
    user = User(
        id=uuid.uuid4(),
        email=f"{prefix}-{uuid.uuid4()}@example.com",
        password_hash=hash_password("TestPassword123!"),
        first_name="API",
        last_name="Test",
    )

    db.add(user)
    db.flush()

    wallet = create_user_wallet(
        db,
        user,
    )

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


def test_payment_api_requires_authentication():
    response = client.post(
        "/api/v1/payments",
        json={
            "wallet_id": str(uuid.uuid4()),
            "amount": 5000,
            "currency": "INR",
        },
        headers={
            "Idempotency-Key": "api-auth-test-001",
        },
    )

    assert response.status_code == 401


def test_payment_api_rejects_invalid_token():
    response = client.post(
        "/api/v1/payments",
        json={
            "wallet_id": str(uuid.uuid4()),
            "amount": 5000,
            "currency": "INR",
        },
        headers={
            "Authorization": "Bearer invalid-token",
            "Idempotency-Key": "api-invalid-token-001",
        },
    )

    assert response.status_code == 401


def test_payment_api_creates_payment(db):
    user, wallet = create_api_user(db)

    app.dependency_overrides[get_db] = lambda: db

    try:
        idempotency_key = f"api-payment-{uuid.uuid4()}"

        response = client.post(
            "/api/v1/payments",
            json={
                "wallet_id": str(wallet.id),
                "amount": 5000,
                "currency": "INR",
            },
            headers={
                **auth_headers(user),
                "Idempotency-Key": idempotency_key,
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["wallet_id"] == str(wallet.id)
        assert data["user_id"] == str(user.id)
        assert data["amount"] == 5000
        assert data["currency"] == "INR"
        assert data["status"] == "PENDING"
        assert data["idempotency_key"] == idempotency_key

    finally:
        app.dependency_overrides.clear()


def test_payment_api_rejects_missing_idempotency_header(db):
    user, wallet = create_api_user(db)

    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.post(
            "/api/v1/payments",
            json={
                "wallet_id": str(wallet.id),
                "amount": 5000,
                "currency": "INR",
            },
            headers=auth_headers(user),
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()


def test_payment_api_rejects_invalid_amount(db):
    user, wallet = create_api_user(db)

    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.post(
            "/api/v1/payments",
            json={
                "wallet_id": str(wallet.id),
                "amount": 0,
                "currency": "INR",
            },
            headers={
                **auth_headers(user),
                "Idempotency-Key": "api-invalid-payment-001",
            },
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()


def test_refund_api_requires_authentication():
    response = client.post(
        "/api/v1/refunds",
        json={
            "payment_id": str(uuid.uuid4()),
            "amount": 5000,
        },
        headers={
            "Idempotency-Key": "api-refund-auth-001",
        },
    )

    assert response.status_code == 401


def test_deposit_api_requires_authentication():
    response = client.post(
        "/api/v1/transactions/deposit",
        json={
            "amount": 5000,
        },
        headers={
            "Idempotency-Key": "api-deposit-auth-001",
        },
    )

    assert response.status_code == 401


def test_withdrawal_api_requires_authentication():
    response = client.post(
        "/api/v1/transactions/withdraw",
        json={
            "amount": 5000,
        },
        headers={
            "Idempotency-Key": "api-withdraw-auth-001",
        },
    )

    assert response.status_code == 401


def test_transfer_api_requires_authentication():
    response = client.post(
        "/api/v1/transactions/transfer",
        json={
            "recipient_wallet_id": str(uuid.uuid4()),
            "amount": 5000,
        },
        headers={
            "Idempotency-Key": "api-transfer-auth-001",
        },
    )

    assert response.status_code == 401


def test_transaction_list_requires_authentication():
    response = client.get(
        "/api/v1/transactions",
    )

    assert response.status_code == 401


def test_transaction_detail_requires_authentication():
    response = client.get(
        f"/api/v1/transactions/{uuid.uuid4()}",
    )

    assert response.status_code == 401