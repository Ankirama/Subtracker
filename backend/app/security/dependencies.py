"""
FastAPI dependencies for authentication.
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.security.jwt import get_user_id_from_token
from app.security.events import SecurityEventLogger

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        Current authenticated User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Extract user_id from token
        user_id = get_user_id_from_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure user is active.

    Args:
        current_user: Current authenticated user

    Returns:
        Active user

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


async def get_current_admin_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to ensure user is an active admin.
    Logs security events for admin access attempts.

    Args:
        request: HTTP request for IP and user agent
        current_user: Current authenticated user
        db: Database session

    Returns:
        Active admin user

    Raises:
        HTTPException: If user is not an admin or not active
    """
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if not current_user.is_active:
        # Log failed admin access for inactive user
        SecurityEventLogger.log_admin_access_denied(
            db=db,
            user_id=str(current_user.id),
            email=current_user.email,
            resource=str(request.url.path),
            ip_address=ip_address,
            user_agent=user_agent,
            reason="account_inactive"
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    if not current_user.is_admin:
        # Log unauthorized admin access attempt
        SecurityEventLogger.log_admin_access_denied(
            db=db,
            user_id=str(current_user.id),
            email=current_user.email,
            resource=str(request.url.path),
            ip_address=ip_address,
            user_agent=user_agent,
            reason="insufficient_privileges"
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    # Log successful admin access
    SecurityEventLogger.log_admin_access(
        db=db,
        user_id=str(current_user.id),
        email=current_user.email,
        resource=str(request.url.path),
        ip_address=ip_address,
        user_agent=user_agent
    )

    return current_user
