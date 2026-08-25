import uuid

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User, UserRole


def create_admin(db):
    admin = User(
        id=uuid.uuid4(),
        email=f"admin-integrity-{uuid.uuid4()}@example.com",
        password_hash="test-password",
        first_name="Integrity",
        last_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )

    db.add(admin)
    db.flush()

    return admin


def create_user(db):
    user = User(
        id=uuid.uuid4(),
        email=f"user-integrity-{uuid.uuid4()}@example.com",
        password_hash="test-password",
        first_name="Integrity",
        last_name="User",
        role=UserRole.USER,
        is_active=True,
    )

    db.add(user)
    db.flush()

    return user


def test_admin_can_access_integrity_endpoint(db):
    admin = create_admin(db)

    app.dependency_overrides[
        get_current_user
    ] = lambda: admin

    try:
        client = TestClient(app)

        response = client.get(
            "/api/v1/admin/integrity"
        )

        assert response.status_code == 200

        data = response.json()

        assert "healthy" in data
        assert "total_issues" in data
        assert "issues" in data

    finally:
        app.dependency_overrides.clear()


def test_normal_user_cannot_access_integrity_endpoint(db):
    user = create_user(db)

    app.dependency_overrides[
        get_current_user
    ] = lambda: user

    try:
        client = TestClient(app)

        response = client.get(
            "/api/v1/admin/integrity"
        )

        assert response.status_code == 403

        assert response.json()["detail"] == (
            "Admin access required."
        )

    finally:
        app.dependency_overrides.clear()


def test_integrity_response_shape(db):
    admin = create_admin(db)

    app.dependency_overrides[
        get_current_user
    ] = lambda: admin

    try:
        client = TestClient(app)

        response = client.get(
            "/api/v1/admin/integrity"
        )

        assert response.status_code == 200

        data = response.json()

        assert isinstance(
            data["healthy"],
            bool,
        )

        assert isinstance(
            data["total_issues"],
            int,
        )

        assert isinstance(
            data["issues"],
            list,
        )

        for issue in data["issues"]:
            assert "code" in issue
            assert "message" in issue

    finally:
        app.dependency_overrides.clear()