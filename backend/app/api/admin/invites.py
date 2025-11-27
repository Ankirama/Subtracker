"""
Admin API endpoints for managing invite tokens.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.models.invite_token import InviteToken
from app.security.dependencies import get_current_user
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Schemas
class CreateInviteRequest(BaseModel):
    email: Optional[EmailStr] = None  # Optional pre-filled email
    note: Optional[str] = None  # Admin note
    expires_in_days: int = 7


class InviteResponse(BaseModel):
    id: UUID
    token: str
    invite_url: str
    invited_email: Optional[str]
    note: Optional[str]
    is_used: bool
    used_at: Optional[datetime]
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class InviteListResponse(BaseModel):
    invites: List[InviteResponse]
    total: int


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to ensure user is admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


@router.post(
    "/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED
)
async def create_invite(
    invite_data: CreateInviteRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new invite token (admin only).

    Returns an invite URL that can be shared with the user to register.
    """
    # Create invite token
    invite = InviteToken.create_invite(
        created_by_id=admin_user.id,
        invited_email=invite_data.email,
        note=invite_data.note,
        expires_in_days=invite_data.expires_in_days,
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    logger.info(
        f"Admin {admin_user.email} created invite token for {invite_data.email or 'anyone'}"
    )

    # Build invite URL
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    invite_url = f"{frontend_url}/register?invite={invite.token}"

    return InviteResponse(
        id=invite.id,
        token=invite.token,
        invite_url=invite_url,
        invited_email=invite.invited_email,
        note=invite.note,
        is_used=invite.is_used,
        used_at=invite.used_at,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
    )


@router.get("/invites", response_model=InviteListResponse)
async def list_invites(
    include_used: bool = False,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all invite tokens (admin only).
    """
    query = db.query(InviteToken)

    if not include_used:
        query = query.filter(not InviteToken.is_used)

    invites = query.order_by(InviteToken.created_at.desc()).all()

    frontend_url = settings.FRONTEND_URL.rstrip("/")

    invite_responses = [
        InviteResponse(
            id=invite.id,
            token=invite.token,
            invite_url=f"{frontend_url}/register?invite={invite.token}",
            invited_email=invite.invited_email,
            note=invite.note,
            is_used=invite.is_used,
            used_at=invite.used_at,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        )
        for invite in invites
    ]

    return InviteListResponse(invites=invite_responses, total=len(invite_responses))


@router.delete("/invites/{invite_id}")
async def revoke_invite(
    invite_id: UUID,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Revoke/delete an invite token (admin only).
    """
    invite = db.query(InviteToken).filter(InviteToken.id == invite_id).first()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )

    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke an already used invite",
        )

    db.delete(invite)
    db.commit()

    logger.info(f"Admin {admin_user.email} revoked invite token {invite_id}")

    return {"message": "Invite revoked successfully"}


@router.get("/invites/{token}/validate")
async def validate_invite(token: str, db: Session = Depends(get_db)):
    """
    Validate an invite token (public endpoint for registration form).
    """
    invite = db.query(InviteToken).filter(InviteToken.token == token).first()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite token"
        )

    if invite.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite has already been used",
        )

    if datetime.utcnow() >= invite.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This invite has expired"
        )

    return {
        "valid": True,
        "invited_email": invite.invited_email,
        "expires_at": invite.expires_at,
    }
