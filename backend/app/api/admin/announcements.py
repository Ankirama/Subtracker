"""
Admin system announcements API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.models.user import User
from app.security.dependencies import get_current_admin_user
from app.schemas.admin import SystemAnnouncementCreate, SystemAnnouncementResponse
from app.tasks.system_announcements import broadcast_system_announcement
from app.models.admin import AdminAuditLog

router = APIRouter()


@router.post(
    "/announcements/broadcast",
    response_model=SystemAnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_system_announcement(
    announcement_data: SystemAnnouncementCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Create and broadcast a system announcement to users.

    This endpoint triggers a Celery task to send the announcement to all users
    or specific target users based on their notification preferences.

    Args:
        announcement_data: Announcement content and targeting
        current_user: Current admin user
        db: Database session

    Returns:
        Announcement broadcast result

    Raises:
        HTTPException: If validation fails
    """
    # Validate targeting
    if not announcement_data.target_all_users and not announcement_data.target_user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must either target all users or provide specific user IDs",
        )

    # Generate unique announcement ID
    announcement_id = uuid.uuid4()

    # Log admin action
    audit_log = AdminAuditLog(
        user_id=current_user.id,
        action="broadcast_system_announcement",
        resource_type="announcement",
        resource_id=str(announcement_id),
        details={
            "title": announcement_data.title,
            "priority": announcement_data.priority,
            "target_all_users": announcement_data.target_all_users,
            "target_user_count": (
                len(announcement_data.target_user_ids)
                if announcement_data.target_user_ids
                else "all"
            ),
        },
        severity="info",
    )
    db.add(audit_log)
    db.commit()

    # Trigger broadcast task
    task = broadcast_system_announcement.delay(
        announcement_id=str(announcement_id),
        title=announcement_data.title,
        message=announcement_data.message,
        priority=announcement_data.priority,
        target_all_users=announcement_data.target_all_users,
        target_user_ids=(
            [str(uid) for uid in announcement_data.target_user_ids]
            if announcement_data.target_user_ids
            else None
        ),
    )

    return SystemAnnouncementResponse(
        success=True,
        announcement_id=announcement_id,
        notifications_created=0,  # Will be updated when task completes
        emails_sent=0,  # Will be updated when task completes
        message=f"System announcement '{announcement_data.title}' is being broadcast. Task ID: {task.id}",
    )
