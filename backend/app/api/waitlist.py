"""
Waitlist API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.waitlist import Waitlist
from app.models.user import User
from app.schemas.waitlist import (
    WaitlistCreate,
    WaitlistApprove,
    WaitlistReject,
    WaitlistListResponse,
    WaitlistMessageResponse,
)
from app.security.dependencies import get_current_admin_user
from app.middleware.rate_limiter import RateLimits
import secrets
import string
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()


def generate_access_code() -> str:
    """Generate a secure random access code."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


@router.post(
    "/waitlist",
    response_model=WaitlistMessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimits.WAITLIST)],
)
async def join_waitlist(waitlist_data: WaitlistCreate, db: Session = Depends(get_db)):
    """
    Join the waitlist.

    Public endpoint for users to join the waitlist.
    Rate limited to 5 requests per 15 minutes per IP.

    Args:
        waitlist_data: User's email
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If email already exists in waitlist or rate limit exceeded
    """
    # Check if email already exists
    existing = db.query(Waitlist).filter(Waitlist.email == waitlist_data.email).first()

    if existing:
        if existing.status == "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email has already been approved. Please check your inbox for the access code.",
            )
        elif existing.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You're already on the waitlist. We'll notify you when your access is approved.",
            )
        else:  # rejected
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email was previously rejected from the waitlist.",
            )

    # Create new waitlist entry
    new_entry = Waitlist(email=waitlist_data.email, status="pending")

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    logger.info(f"New waitlist entry created: {waitlist_data.email}")

    return WaitlistMessageResponse(
        message="Successfully joined the waitlist! We'll notify you when your access is approved.",
        email=waitlist_data.email,
    )


@router.get("/admin/waitlist", response_model=WaitlistListResponse)
async def list_waitlist(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, regex="^(pending|approved|rejected)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    List all waitlist entries (Admin only).

    Args:
        page: Page number
        page_size: Number of items per page
        status_filter: Filter by status (pending, approved, rejected)
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        Paginated list of waitlist entries
    """
    query = db.query(Waitlist)

    # Apply status filter if provided
    if status_filter:
        query = query.filter(Waitlist.status == status_filter)

    # Get total count
    total = query.count()

    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size

    # Get paginated results
    entries = (
        query.order_by(Waitlist.created_at.desc()).offset(offset).limit(page_size).all()
    )

    return WaitlistListResponse(
        items=entries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/admin/waitlist/{waitlist_id}/approve", response_model=WaitlistMessageResponse
)
async def approve_waitlist(
    waitlist_id: str,
    approve_data: WaitlistApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Approve a waitlist entry and generate access code (Admin only).

    Args:
        waitlist_id: Waitlist entry ID
        approve_data: Approval settings
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        Success message with access code

    Raises:
        HTTPException: If entry not found or already processed
    """
    entry = db.query(Waitlist).filter(Waitlist.id == waitlist_id).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    if entry.status == "approved":
        return WaitlistMessageResponse(
            message="This entry was already approved.",
            email=entry.email,
            access_code=entry.access_code,
        )

    # Generate access code
    access_code = generate_access_code()

    # Update entry
    entry.status = "approved"
    entry.access_code = access_code
    entry.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(entry)

    logger.info(f"Waitlist entry approved: {entry.email} by {current_user.email}")

    # TODO: Send email with access code if send_email is True
    # if approve_data.send_email:
    #     send_access_code_email(entry.email, access_code)

    return WaitlistMessageResponse(
        message="Successfully approved! Access code generated."
        + (" Email sent to user." if approve_data.send_email else ""),
        email=entry.email,
        access_code=access_code,
    )


@router.post(
    "/admin/waitlist/{waitlist_id}/reject", response_model=WaitlistMessageResponse
)
async def reject_waitlist(
    waitlist_id: str,
    reject_data: WaitlistReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Reject a waitlist entry (Admin only).

    Args:
        waitlist_id: Waitlist entry ID
        reject_data: Rejection details
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        Success message

    Raises:
        HTTPException: If entry not found
    """
    entry = db.query(Waitlist).filter(Waitlist.id == waitlist_id).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    if entry.status == "rejected":
        return WaitlistMessageResponse(
            message="This entry was already rejected.", email=entry.email
        )

    # Update entry
    entry.status = "rejected"
    entry.rejected_at = datetime.utcnow()

    db.commit()
    db.refresh(entry)

    logger.info(
        f"Waitlist entry rejected: {entry.email} by {current_user.email}. Reason: {reject_data.reason}"
    )

    return WaitlistMessageResponse(message="Successfully rejected.", email=entry.email)


@router.delete("/admin/waitlist/{waitlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_waitlist(
    waitlist_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a waitlist entry (Admin only).

    Args:
        waitlist_id: Waitlist entry ID
        db: Database session
        current_user: Current authenticated admin user

    Raises:
        HTTPException: If entry not found
    """
    entry = db.query(Waitlist).filter(Waitlist.id == waitlist_id).first()

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Waitlist entry not found"
        )

    db.delete(entry)
    db.commit()

    logger.info(f"Waitlist entry deleted: {entry.email} by {current_user.email}")
