import json
import time
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.webhook_security_service import (
    generate_signature,
)

from app.core.config import settings

WEBHOOK_SECRET = settings.webhook_secret
client = TestClient(app)


def make_webhook(
    *,
    event_type="unknown.event",
    event_id=None,
    payload_extra=None,
    timestamp=None,
):
    if event_id is None:
        event_id = f"evt-{uuid.uuid4()}"

    payload = {
        "event_type": event_type,
    }

    if payload_extra:
        payload.update(payload_extra)

    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode()

    if timestamp is None:
        timestamp = int(time.time())

    signature = generate_signature(
        body,
        WEBHOOK_SECRET,
        timestamp,
    )

    headers = {
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Provider": "SIMULATOR",
        "X-Provider-Event-Id": event_id,
    }

    return body, headers, event_id


def test_valid_webhook_is_accepted():
    body, headers, event_id = make_webhook()

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["accepted"] is True
    assert data["provider_event_id"] == event_id
    assert data["status"] == "IGNORED"


def test_missing_signature_returns_401():
    body, headers, _ = make_webhook()

    headers.pop("X-Webhook-Signature")

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401


def test_invalid_signature_returns_401():
    body, headers, _ = make_webhook()

    headers["X-Webhook-Signature"] = (
        "sha256=invalid"
    )

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401


def test_missing_timestamp_returns_401():
    body, headers, _ = make_webhook()

    headers.pop("X-Webhook-Timestamp")

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401


def test_expired_timestamp_returns_401():
    old_timestamp = int(time.time()) - 1000

    body, headers, _ = make_webhook(
        timestamp=old_timestamp,
    )

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 401


def test_missing_provider_event_id_returns_400():
    body, headers, _ = make_webhook()

    headers.pop("X-Provider-Event-Id")

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 400


def test_invalid_json_returns_400():
    body = b"not-valid-json"

    timestamp = int(time.time())

    signature = generate_signature(
        body,
        WEBHOOK_SECRET,
        timestamp,
    )

    headers = {
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Provider": "SIMULATOR",
        "X-Provider-Event-Id": f"evt-{uuid.uuid4()}",
    }

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 400


def test_missing_event_type_returns_400():
    event_id = f"evt-{uuid.uuid4()}"

    payload = {}

    body = json.dumps(
        payload,
        separators=(",", ":"),
    ).encode()

    timestamp = int(time.time())

    signature = generate_signature(
        body,
        WEBHOOK_SECRET,
        timestamp,
    )

    headers = {
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Provider": "SIMULATOR",
        "X-Provider-Event-Id": event_id,
    }

    response = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert response.status_code == 400


def test_duplicate_webhook_is_idempotent():
    body, headers, event_id = make_webhook(
        event_type="duplicate.test",
    )

    first = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    second = client.post(
        "/api/v1/webhooks/provider",
        content=body,
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_data = first.json()
    second_data = second.json()

    assert (
        first_data["event_id"]
        == second_data["event_id"]
    )

    assert (
        first_data["provider_event_id"]
        == event_id
    )

    assert (
        second_data["provider_event_id"]
        == event_id
    )