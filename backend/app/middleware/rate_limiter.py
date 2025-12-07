"""
Rate limiting middleware using fastapi-limiter with Redis backend.
"""

import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)


async def init_rate_limiter():
    """
    Initialize the rate limiter with Redis backend.

    This should be called during application startup.
    """
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
        await FastAPILimiter.init(redis_client)
        logger.info("Rate limiter initialized successfully with Redis backend")
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        raise


async def close_rate_limiter():
    """
    Close the rate limiter connection.

    This should be called during application shutdown.
    """
    try:
        await FastAPILimiter.close()
        logger.info("Rate limiter closed successfully")
    except Exception as e:
        logger.error(f"Failed to close rate limiter: {e}")


def rate_limit_exceeded_handler(
    request: Request, response: Response, pexpire: int
) -> JSONResponse:
    """
    Custom handler for rate limit exceeded responses.

    Args:
        request: The FastAPI request
        response: The FastAPI response
        pexpire: Time until limit resets (milliseconds)

    Returns:
        JSONResponse with 429 status code
    """
    retry_after_seconds = int(pexpire / 1000)
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please try again later.",
            "retry_after": retry_after_seconds,
        },
        headers={"Retry-After": str(retry_after_seconds)},
    )


# Pre-configured rate limiters for common use cases
class RateLimits:
    """Common rate limit configurations"""

    # Waitlist: 5 requests per 15 minutes (900 seconds)
    WAITLIST = RateLimiter(times=5, seconds=900)

    # Authentication: 5 login attempts per 5 minutes
    AUTH = RateLimiter(times=5, seconds=300)

    # API: 100 requests per hour
    API = RateLimiter(times=100, seconds=3600)

    # Strict: 3 requests per hour (for sensitive operations)
    STRICT = RateLimiter(times=3, seconds=3600)
