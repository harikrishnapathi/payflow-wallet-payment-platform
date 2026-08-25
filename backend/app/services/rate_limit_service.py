import time

import redis

from app.core.config import settings


redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


class RateLimitExceeded(Exception):
    def __init__(
        self,
        retry_after: int,
    ):
        self.retry_after = retry_after
        super().__init__(
            "Rate limit exceeded."
        )


def check_rate_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """
    Redis-backed fixed-window rate limiter.

    Raises RateLimitExceeded when the limit
    has been reached.
    """

    current_window = int(
        time.time() // window_seconds
    )

    redis_key = (
        f"payflow:rate_limit:"
        f"{key}:{current_window}"
    )

    count = redis_client.incr(
        redis_key
    )

    if count == 1:
        redis_client.expire(
            redis_key,
            window_seconds,
        )

    if count > limit:
        remaining = (
            window_seconds
            - int(time.time() % window_seconds)
        )

        raise RateLimitExceeded(
            max(1, remaining)
        )