"""
Google OAuth2 endpoints for Gmail mailbox integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import secrets
import logging
import httpx
import redis
import json

from app.database import get_db
from app.models.user import User
from app.models.mailbox import Mailbox
from app.security.dependencies import get_current_user
from app.security.encryption import encrypt_credentials
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# OAuth2 Configuration
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "email", "profile"]

# OAuth state TTL in seconds (10 minutes)
OAUTH_STATE_TTL = 600

# Redis client for OAuth state storage (shared across workers)
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Redis client initialized for OAuth state storage")
except Exception as e:
    logger.error(f"Failed to connect to Redis for OAuth: {e}")
    redis_client = None


@router.get("/google/authorize")
async def google_authorize(
    current_user: User = Depends(get_current_user)
):
    """
    Initiate Google OAuth2 flow.

    Generates authorization URL and returns it to the frontend.
    The frontend should redirect the user to this URL.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state -> user_id mapping in Redis (expires after 10 minutes)
    if redis_client:
        try:
            state_data = {
                "user_id": str(current_user.id),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            redis_key = f"oauth:state:{state}"
            redis_client.setex(redis_key, OAUTH_STATE_TTL, json.dumps(state_data))
            logger.info(f"Stored OAuth state in Redis for user {current_user.id}")
        except Exception as e:
            logger.error(f"Failed to store OAuth state in Redis: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OAuth state storage failed. Please try again."
            )
    else:
        logger.error("Redis client not available for OAuth state storage")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth service temporarily unavailable"
        )

    # Build authorization URL
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Force consent screen to get refresh token
        "state": state
    }

    auth_url = f"{GOOGLE_AUTH_URL}?" + "&".join(f"{k}={v}" for k, v in params.items())

    return {
        "authorization_url": auth_url,
        "state": state
    }


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State token for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from Google"),
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth2 callback.

    Exchanges authorization code for tokens, fetches user info,
    and creates a Gmail mailbox.
    """
    # Handle errors from Google
    if error:
        logger.error(f"Google OAuth error: {error}")
        # Redirect to frontend with error
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/mailboxes/add?error={error}"
        )

    # Validate state by retrieving from Redis
    if not redis_client:
        logger.error("Redis client not available for OAuth state validation")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/mailboxes/add?error=oauth_unavailable"
        )

    try:
        redis_key = f"oauth:state:{state}"
        state_json = redis_client.get(redis_key)

        if not state_json:
            logger.error(f"Invalid or expired OAuth state: {state}")
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/mailboxes/add?error=invalid_state"
            )

        # Delete the state from Redis (one-time use)
        redis_client.delete(redis_key)

        # Parse state data
        state_data = json.loads(state_json)
        user_id = state_data["user_id"]
        logger.info(f"OAuth state validated for user {user_id}")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OAuth state data: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/mailboxes/add?error=invalid_state"
        )
    except Exception as e:
        logger.error(f"Failed to validate OAuth state: {e}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/mailboxes/add?error=invalid_state"
        )

    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
            )

            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/mailboxes/add?error=token_exchange_failed"
                )

            tokens = token_response.json()

            # Get user email from Google
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )

            if userinfo_response.status_code != 200:
                logger.error(f"Failed to get user info: {userinfo_response.text}")
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/mailboxes/add?error=userinfo_failed"
                )

            userinfo = userinfo_response.json()
            email = userinfo.get("email")

            if not email:
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/mailboxes/add?error=no_email"
                )

        # Check if mailbox already exists
        existing = db.query(Mailbox).filter(
            Mailbox.user_id == user_id,
            Mailbox.email_address == email
        ).first()

        if existing:
            # Update existing mailbox credentials
            credentials = {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token", existing.encrypted_credentials.get("refresh_token") if existing.encrypted_credentials else None),
                "token_expiry": None,  # Will be set on first use
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "email_address": email
            }

            existing.encrypted_credentials = encrypt_credentials(credentials)
            existing.provider_type = "gmail"
            existing.is_active = True
            db.commit()

            logger.info(f"Updated Gmail mailbox for user {user_id}: {email}")

            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/mailboxes?success=gmail_updated"
            )

        # Create new mailbox
        credentials = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "token_expiry": None,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "email_address": email
        }

        new_mailbox = Mailbox(
            user_id=user_id,
            provider_type="gmail",
            email_address=email,
            encrypted_credentials=encrypt_credentials(credentials),
            display_name=f"Gmail - {email}",
            sync_frequency="daily",
            batch_size=100,
            import_date_filter=30,
            is_active=True,
            last_sync_status=None
        )

        db.add(new_mailbox)
        db.commit()

        logger.info(f"Created Gmail mailbox for user {user_id}: {email}")

        # Redirect to frontend with success
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/mailboxes?success=gmail_connected"
        )

    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/mailboxes/add?error=callback_failed"
        )


@router.post("/google/refresh")
async def refresh_google_token(
    mailbox_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually refresh Google OAuth tokens for a mailbox.

    This is typically handled automatically, but can be called
    if tokens need to be refreshed manually.
    """
    from app.security.encryption import decrypt_credentials

    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == current_user.id,
        Mailbox.provider_type == "gmail"
    ).first()

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gmail mailbox not found"
        )

    # Decrypt credentials
    credentials = decrypt_credentials(mailbox.encrypted_credentials)

    if not credentials.get("refresh_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available. Please reconnect the mailbox."
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": credentials["refresh_token"],
                    "grant_type": "refresh_token"
                }
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Token refresh failed: {response.text}"
                )

            new_tokens = response.json()

            # Update credentials
            credentials["access_token"] = new_tokens["access_token"]
            if "refresh_token" in new_tokens:
                credentials["refresh_token"] = new_tokens["refresh_token"]

            mailbox.encrypted_credentials = encrypt_credentials(credentials)
            db.commit()

            return {"message": "Token refreshed successfully"}

    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.delete("/google/disconnect/{mailbox_id}")
async def disconnect_google(
    mailbox_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Disconnect a Gmail mailbox and revoke OAuth access.
    """
    from app.security.encryption import decrypt_credentials

    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == current_user.id,
        Mailbox.provider_type == "gmail"
    ).first()

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gmail mailbox not found"
        )

    # Decrypt credentials to get access token for revocation
    credentials = decrypt_credentials(mailbox.encrypted_credentials)

    # Revoke the token with Google
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": credentials.get("access_token")}
            )
    except Exception as e:
        logger.warning(f"Token revocation failed (continuing with deletion): {e}")

    # Delete the mailbox
    db.delete(mailbox)
    db.commit()

    logger.info(f"Disconnected Gmail mailbox {mailbox_id} for user {current_user.id}")

    return {"message": "Gmail disconnected successfully"}
