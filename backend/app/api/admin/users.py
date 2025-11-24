"""
Admin API endpoints for user management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
import uuid
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.schemas.admin import (
    UserListResponse,
    UserDetailResponse,
    UserUpdateRequest,
    UserStatsResponse
)
from app.security.dependencies import get_current_admin_user

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=UserListResponse, dependencies=[Depends(get_current_admin_user)])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_admin: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """
    List all users with pagination and filtering.

    - **page**: Page number (starts at 1)
    - **page_size**: Items per page (1-100)
    - **search**: Search by email
    - **is_active**: Filter by active status
    - **is_admin**: Filter by admin status
    """
    query = db.query(User)

    # Apply filters
    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))

    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if is_admin is not None:
        query = query.filter(User.is_admin == is_admin)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size

    return {
        "users": [
            {
                "id": str(user.id),
                "email": user.email,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "email_verified": user.email_verified,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat(),
            }
            for user in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/stats", response_model=UserStatsResponse, dependencies=[Depends(get_current_admin_user)])
async def get_user_stats(db: Session = Depends(get_db)):
    """
    Get user statistics.
    """
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
    admin_users = db.query(func.count(User.id)).filter(User.is_admin == True).scalar()

    # Users created in last 30 days
    from datetime import timedelta
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_users_30d = db.query(func.count(User.id)).filter(User.created_at >= thirty_days_ago).scalar()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": total_users - active_users,
        "admin_users": admin_users,
        "new_users_30d": new_users_30d
    }


@router.get("/{user_id}", response_model=UserDetailResponse, dependencies=[Depends(get_current_admin_user)])
async def get_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific user.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user statistics
    from app.models.subscription import Subscription
    from app.models.mailbox import Mailbox

    subscription_count = db.query(func.count(Subscription.id)).filter(
        Subscription.user_id == user_uuid
    ).scalar()

    mailbox_count = db.query(func.count(Mailbox.id)).filter(
        Mailbox.user_id == user_uuid
    ).scalar()

    return {
        "id": str(user.id),
        "email": user.email,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "email_verified": user.email_verified,
        "settings": user.settings,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
        "subscription_count": subscription_count,
        "mailbox_count": mailbox_count
    }


@router.put("/{user_id}", response_model=UserDetailResponse, dependencies=[Depends(get_current_admin_user)])
async def update_user(
    user_id: str,
    update_data: UserUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update user information.

    - **is_active**: Activate or deactivate the user
    - **is_admin**: Grant or revoke admin privileges
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields if provided
    if update_data.is_active is not None:
        user.is_active = update_data.is_active

    if update_data.is_admin is not None:
        user.is_admin = update_data.is_admin

    db.commit()
    db.refresh(user)

    # Get updated statistics
    from app.models.subscription import Subscription
    from app.models.mailbox import Mailbox

    subscription_count = db.query(func.count(Subscription.id)).filter(
        Subscription.user_id == user_uuid
    ).scalar()

    mailbox_count = db.query(func.count(Mailbox.id)).filter(
        Mailbox.user_id == user_uuid
    ).scalar()

    return {
        "id": str(user.id),
        "email": user.email,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "email_verified": user.email_verified,
        "settings": user.settings,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
        "subscription_count": subscription_count,
        "mailbox_count": mailbox_count
    }


@router.delete("/{user_id}", dependencies=[Depends(get_current_admin_user)])
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a user (soft delete by deactivating).

    This will deactivate the user rather than permanently deleting them.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Soft delete by deactivating
    user.is_active = False
    db.commit()

    return {"success": True, "message": "User deactivated successfully"}


@router.post("/{user_id}/verify", dependencies=[Depends(get_current_admin_user)])
async def verify_user_email(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Manually verify a user's email address.

    This is useful when users can't click the verification link.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.email_verified:
        raise HTTPException(status_code=400, detail="User email is already verified")

    # Verify the user's email
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()
    user.email_verification_token = None
    db.commit()

    return {"success": True, "message": "User email verified successfully"}
