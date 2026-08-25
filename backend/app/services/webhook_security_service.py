import hashlib
import hmac
import time


DEFAULT_TOLERANCE_SECONDS = 300


def generate_signature(
    payload: bytes,
    secret: str,
    timestamp: int,
) -> str:
    """
    Generate an HMAC-SHA256 webhook signature.

    Format:
        sha256=<hex digest>
    """

    signed_payload = (
        f"{timestamp}.".encode("utf-8")
        + payload
    )

    digest = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def verify_signature(
    payload: bytes,
    signature: str,
    secret: str,
    timestamp: int,
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> bool:
    """
    Verify webhook authenticity and prevent replay attacks.
    """

    if not signature:
        return False

    current_time = (
        int(time.time())
        if now is None
        else now
    )

    if abs(current_time - timestamp) > tolerance_seconds:
        return False

    expected = generate_signature(
        payload,
        secret,
        timestamp,
    )

    return hmac.compare_digest(
        expected,
        signature,
    )