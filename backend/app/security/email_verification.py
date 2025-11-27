"""
Email verification utilities for managing email verification tokens and rate limiting.
"""

import secrets
import redis
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.ip_block import IPBlock
from app.models.ip_whitelist import IPWhitelist
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Redis client for rate limiting and temporary blocks
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None


class EmailVerificationManager:
    """Manage email verification tokens and validation."""

    TOKEN_LENGTH = 64  # Length of verification token in characters
    TOKEN_EXPIRY_HOURS = 24  # Token expires in 24 hours

    @staticmethod
    def generate_verification_token() -> str:
        """Generate a cryptographically secure verification token."""
        return secrets.token_urlsafe(EmailVerificationManager.TOKEN_LENGTH)

    @staticmethod
    def is_token_expired(sent_at: datetime) -> bool:
        """Check if verification token has expired."""
        expiry_time = sent_at + timedelta(
            hours=EmailVerificationManager.TOKEN_EXPIRY_HOURS
        )
        return datetime.utcnow() > expiry_time

    @staticmethod
    def verify_token(
        db: Session, token: str
    ) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Verify email verification token.

        Returns:
            Tuple of (success: bool, user: Optional[User], error_message: Optional[str])
        """
        # Find user with this token
        user = db.query(User).filter(User.email_verification_token == token).first()

        if not user:
            return False, None, "Invalid or expired verification token"

        if user.email_verified:
            return False, None, "Email already verified"

        # Check if token has expired
        if not user.email_verification_sent_at:
            return False, None, "Verification token is invalid"

        if EmailVerificationManager.is_token_expired(user.email_verification_sent_at):
            return (
                False,
                None,
                "Verification token has expired. Please request a new one.",
            )

        return True, user, None

    @staticmethod
    def mark_as_verified(db: Session, user: User) -> None:
        """Mark user's email as verified."""
        user.email_verified = True
        user.email_verified_at = datetime.utcnow()
        user.email_verification_token = None  # Clear token after use
        user.email_verification_sent_at = None
        db.commit()
        logger.info(f"Email verified for user: {user.email}")


class VerificationRateLimiter:
    """Rate limiting and brute force protection for email verification."""

    # Rate limiting: 12 emails per hour (every 5 minutes)
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
    RATE_LIMIT_MAX = 12  # Maximum requests per window

    # Multi-tier brute force protection
    TIER_1_ATTEMPTS = 5
    TIER_1_WINDOW = 180  # 3 minutes
    TIER_1_BLOCK_DURATION = 3600  # 1 hour

    TIER_2_ATTEMPTS = 10
    TIER_2_WINDOW = 1800  # 30 minutes
    TIER_2_BLOCK_DURATION = 86400  # 24 hours

    TIER_3_ATTEMPTS = 20
    TIER_3_WINDOW = 3600  # 1 hour
    # Tier 3 = permanent block in database

    @staticmethod
    def get_rate_limit_key(email: str) -> str:
        """Get Redis key for rate limiting."""
        return f"email_verify_rate:{email}"

    @staticmethod
    def get_brute_force_key(ip: str, tier: int) -> str:
        """Get Redis key for brute force tracking."""
        return f"email_verify_bf_t{tier}:{ip}"

    @staticmethod
    def get_block_key(ip: str, tier: int) -> str:
        """Get Redis key for temporary block."""
        return f"email_verify_block_t{tier}:{ip}"

    @staticmethod
    def check_rate_limit(email: str) -> Tuple[bool, Optional[str]]:
        """
        Check if email has exceeded rate limit.

        Returns:
            Tuple of (allowed: bool, error_message: Optional[str])
        """
        if not redis_client:
            # If Redis is unavailable, allow the request but log warning
            logger.warning("Redis unavailable, skipping rate limit check")
            return True, None

        key = VerificationRateLimiter.get_rate_limit_key(email)

        try:
            # Get current count
            count = redis_client.get(key)
            if count is None:
                # First request in window
                redis_client.setex(key, VerificationRateLimiter.RATE_LIMIT_WINDOW, 1)
                return True, None

            count = int(count)
            if count >= VerificationRateLimiter.RATE_LIMIT_MAX:
                ttl = redis_client.ttl(key)
                minutes = ttl // 60
                return (
                    False,
                    f"Rate limit exceeded. Please try again in {minutes} minutes.",
                )

            # Increment counter
            redis_client.incr(key)
            return True, None

        except Exception as e:
            logger.error(f"Redis error in rate limit check: {e}")
            return True, None  # Fail open on Redis errors

    @staticmethod
    def is_ip_blocked(db: Session, ip: str) -> Tuple[bool, Optional[str]]:
        """
        Check if IP is blocked (temporary or permanent).

        Returns:
            Tuple of (blocked: bool, reason: Optional[str])
        """
        # Check if IP is whitelisted - whitelisted IPs bypass all blocking
        whitelist_entry = (
            db.query(IPWhitelist).filter(IPWhitelist.ip_address == ip).first()
        )
        if whitelist_entry:
            # Update last_seen and access_count for tracking
            whitelist_entry.last_seen = datetime.utcnow()
            whitelist_entry.access_count += 1
            db.commit()
            logger.info(
                f"Whitelisted IP {ip} accessed (count: {whitelist_entry.access_count})"
            )
            return False, None

        # Check permanent block in database
        permanent_block = db.query(IPBlock).filter(IPBlock.ip_address == ip).first()
        if permanent_block:
            return True, f"IP permanently blocked due to: {permanent_block.reason}"

        if not redis_client:
            return False, None

        # Check temporary blocks (Tier 1 and Tier 2)
        try:
            for tier in [1, 2]:
                block_key = VerificationRateLimiter.get_block_key(ip, tier)
                if redis_client.exists(block_key):
                    ttl = redis_client.ttl(block_key)
                    hours = ttl // 3600
                    minutes = (ttl % 3600) // 60
                    time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                    return True, f"IP temporarily blocked. Try again in {time_str}."

            return False, None

        except Exception as e:
            logger.error(f"Redis error in block check: {e}")
            return False, None

    @staticmethod
    def track_verification_attempt(db: Session, ip: str) -> Optional[str]:
        """
        Track verification attempt and apply tiered blocking if thresholds exceeded.

        Returns:
            Error message if IP should be blocked, None otherwise
        """
        # Skip tracking for whitelisted IPs
        whitelist_entry = (
            db.query(IPWhitelist).filter(IPWhitelist.ip_address == ip).first()
        )
        if whitelist_entry:
            logger.info(f"Skipping brute force tracking for whitelisted IP: {ip}")
            return None

        if not redis_client:
            return None

        try:
            # Check Tier 1: 5 attempts in 3 minutes → 1 hour block
            tier1_key = VerificationRateLimiter.get_brute_force_key(ip, 1)
            tier1_count = redis_client.get(tier1_key)
            if tier1_count is None:
                redis_client.setex(tier1_key, VerificationRateLimiter.TIER_1_WINDOW, 1)
            else:
                tier1_count = int(tier1_count)
                if tier1_count >= VerificationRateLimiter.TIER_1_ATTEMPTS:
                    # Apply Tier 1 block
                    block_key = VerificationRateLimiter.get_block_key(ip, 1)
                    redis_client.setex(
                        block_key, VerificationRateLimiter.TIER_1_BLOCK_DURATION, "1"
                    )
                    logger.warning(
                        f"IP {ip} blocked (Tier 1): {tier1_count} attempts in 3 minutes"
                    )
                    return "Too many verification attempts. IP blocked for 1 hour."
                redis_client.incr(tier1_key)

            # Check Tier 2: 10 attempts in 30 minutes → 24 hour block
            tier2_key = VerificationRateLimiter.get_brute_force_key(ip, 2)
            tier2_count = redis_client.get(tier2_key)
            if tier2_count is None:
                redis_client.setex(tier2_key, VerificationRateLimiter.TIER_2_WINDOW, 1)
            else:
                tier2_count = int(tier2_count)
                if tier2_count >= VerificationRateLimiter.TIER_2_ATTEMPTS:
                    # Apply Tier 2 block
                    block_key = VerificationRateLimiter.get_block_key(ip, 2)
                    redis_client.setex(
                        block_key, VerificationRateLimiter.TIER_2_BLOCK_DURATION, "1"
                    )
                    logger.warning(
                        f"IP {ip} blocked (Tier 2): {tier2_count} attempts in 30 minutes"
                    )
                    return "Too many verification attempts. IP blocked for 24 hours."
                redis_client.incr(tier2_key)

            # Check Tier 3: 20 attempts in 1 hour → permanent block
            tier3_key = VerificationRateLimiter.get_brute_force_key(ip, 3)
            tier3_count = redis_client.get(tier3_key)
            if tier3_count is None:
                redis_client.setex(tier3_key, VerificationRateLimiter.TIER_3_WINDOW, 1)
            else:
                tier3_count = int(tier3_count)
                if tier3_count >= VerificationRateLimiter.TIER_3_ATTEMPTS:
                    # Apply permanent block in database
                    existing_block = (
                        db.query(IPBlock).filter(IPBlock.ip_address == ip).first()
                    )
                    if not existing_block:
                        permanent_block = IPBlock(
                            ip_address=ip,
                            reason="email_verification_brute_force",
                            attempt_count=tier3_count,
                        )
                        db.add(permanent_block)
                        db.commit()
                        logger.error(
                            f"IP {ip} permanently blocked: {tier3_count} attempts in 1 hour"
                        )
                    return "Too many verification attempts. IP permanently blocked."
                redis_client.incr(tier3_key)

            return None

        except Exception as e:
            logger.error(f"Redis error in attempt tracking: {e}")
            return None
