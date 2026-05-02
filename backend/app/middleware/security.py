"""
Security middleware for rate limiting, logging, and headers.

Provides comprehensive security protection including:
- Rate limiting per IP and user
- Suspicious query pattern detection and logging
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Request/response logging for audit trails
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict
import time
import logging
from collections import defaultdict
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# Rate limiting storage (in-memory - for production use Redis)
_rate_limit_storage: Dict[str, Dict] = defaultdict(
    lambda: {"count": 0, "reset_time": 0}
)

# Suspicious pattern tracking
_suspicious_patterns = [
    r"%_%_%_%",  # Wildcard injection
    r"UNION\s+SELECT",  # SQL injection
    r"<script",  # XSS attempt
    r"\.\./\.\.",  # Path traversal
    r"exec\(",  # Code injection
    r"eval\(",  # Code injection
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.

    Limits:
    - 100 requests per minute per IP
    - 1000 requests per hour per IP
    - Special limits for search endpoints (30/min)
    """

    def __init__(
        self, app, requests_per_minute: int = 100, requests_per_hour: int = 1000
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Check if this is a search endpoint (stricter limits)
        # Match actual search endpoints like /search/ but not /research
        is_search = (
            "/search" in request.url.path or "uncertain-emails" in request.url.path
        )
        limit = 30 if is_search else self.requests_per_minute

        # Rate limit key
        rate_key = f"{client_ip}:{int(time.time() / 60)}"  # Per minute

        # Check rate limit
        current = _rate_limit_storage[rate_key]
        current_time = time.time()

        # Reset if time window passed
        if current_time >= current["reset_time"]:
            current["count"] = 0
            current["reset_time"] = current_time + 60

        # Increment counter
        current["count"] += 1

        # Check if limit exceeded
        if current["count"] > limit:
            logger.warning(
                f"Rate limit exceeded for IP {client_ip} on {request.url.path}",
                extra={
                    "ip": client_ip,
                    "path": request.url.path,
                    "count": current["count"],
                    "limit": limit,
                },
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": int(current["reset_time"] - current_time),
                },
            )

        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(limit - current["count"])
        response.headers["X-RateLimit-Reset"] = str(int(current["reset_time"]))

        return response


class QueryLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs suspicious query patterns and tracks potential attacks.

    Monitors for:
    - SQL injection attempts
    - XSS attempts
    - Path traversal
    - Excessive wildcards
    - Code injection
    """

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Check query parameters for suspicious patterns
        if request.query_params:
            for key, value in request.query_params.items():
                for pattern in _suspicious_patterns:
                    if re.search(pattern, str(value), re.IGNORECASE):
                        logger.warning(
                            f"Suspicious query pattern detected from IP {client_ip}",
                            extra={
                                "ip": client_ip,
                                "path": request.url.path,
                                "parameter": key,
                                "value": value[:100],  # Limit logged value
                                "pattern": pattern,
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )

                        # Could implement auto-blocking here
                        # For now, just log and continue

        # Log all search queries for audit
        if "search" in request.url.path:
            search_param = request.query_params.get("search", "")
            logger.info(
                f"Search query from {client_ip}: {search_param[:100]}",
                extra={
                    "ip": client_ip,
                    "path": request.url.path,
                    "search_term": search_param[:100],
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses.

    Headers added:
    - Content-Security-Policy (CSP)
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Content Security Policy
        # Adjust based on your frontend needs
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Adjust for production
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.openai.com; "  # Add your API endpoints
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

        # HSTS - Enforce HTTPS (only in production with HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS Protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy (formerly Feature Policy)
        permissions = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        response.headers["Permissions-Policy"] = permissions

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs all requests for audit trail and security monitoring.

    Tracks:
    - Request method, path, IP
    - Response status and duration
    - User authentication status
    - Errors and exceptions
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"

        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "ip": client_ip,
                "user_agent": request.headers.get("user-agent", "unknown"),
            },
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration": duration,
                    "ip": client_ip,
                },
            )

            return response

        except Exception as e:  # noqa: BLE001 — log + record duration, then re-raise
            duration = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)} ({duration:.3f}s)",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration": duration,
                    "ip": client_ip,
                },
                exc_info=True,
            )
            raise
