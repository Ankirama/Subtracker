"""
Mailbox API endpoints for managing email account connections.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.mailbox import Mailbox
from app.models.sync_history import SyncHistory
from app.models.email_sync_error import EmailSyncError
from app.schemas.mailbox import (
    MailboxCreate,
    MailboxUpdate,
    MailboxResponse,
    MailboxTestConnection,
    MailboxTestResult,
    MailboxSyncRequest,
    MailboxSyncStatus,
)
from app.schemas.sync_history import (
    SyncHistoryResponse,
    SyncHistoryList,
    SyncStatistics,
    SyncProgressResponse,
)
from app.security.dependencies import get_current_user
from app.security.encryption import encrypt_credentials
from app.email_providers import JMAPProvider, GmailProvider
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_email_provider(provider_type: str, credentials: dict):
    """
    Factory function to get the appropriate email provider instance.
    """
    if provider_type == "jmap":
        return JMAPProvider(credentials)
    elif provider_type == "gmail":
        return GmailProvider(credentials)
    elif provider_type == "outlook":
        # TODO: Implement OutlookProvider in Phase 2
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Outlook provider not yet implemented. Coming in Phase 2.",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider type: {provider_type}",
        )


@router.post("/test", response_model=MailboxTestResult)
async def test_mailbox_connection(
    test_data: MailboxTestConnection, current_user: User = Depends(get_current_user)
):
    """
    Test mailbox connection without saving credentials.

    This allows users to verify their credentials work before creating a mailbox.
    """
    try:
        provider = get_email_provider(test_data.provider_type, test_data.credentials)

        # Test the connection
        result = await provider.test_connection()

        await provider.close()

        return MailboxTestResult(**result)

    except Exception as e:
        logger.error(f"Connection test failed for user {current_user.id}: {str(e)}")
        return MailboxTestResult(
            success=False,
            message=f"Connection test failed: {str(e)}",
            provider_info=None,
        )


@router.post("/", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
async def create_mailbox(
    mailbox_data: MailboxCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new mailbox connection.

    The credentials are encrypted before storage.
    """
    # Check if mailbox with this email already exists for user
    existing = (
        db.query(Mailbox)
        .filter(
            Mailbox.user_id == current_user.id,
            Mailbox.email_address == mailbox_data.email_address,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mailbox with email {mailbox_data.email_address} already exists",
        )

    # Note: Connection test is skipped here because:
    # 1. Frontend requires successful /mailboxes/test call before allowing create
    # 2. Redundant auth calls can trigger rate limiting (e.g., Fastmail)
    # 3. Credentials are verified on first sync anyway
    # If validation is needed, use the /mailboxes/test endpoint first

    # Encrypt credentials
    encrypted_creds = encrypt_credentials(mailbox_data.credentials)

    # Create mailbox
    new_mailbox = Mailbox(
        user_id=current_user.id,
        provider_type=mailbox_data.provider_type,
        email_address=mailbox_data.email_address,
        encrypted_credentials=encrypted_creds,
        display_name=mailbox_data.display_name or mailbox_data.email_address,
        sync_frequency=mailbox_data.sync_frequency,
        batch_size=mailbox_data.batch_size,
        import_date_filter=mailbox_data.import_date_filter,
        is_active=True,
        last_sync_status=None,
    )

    db.add(new_mailbox)
    db.commit()
    db.refresh(new_mailbox)

    logger.info(f"Mailbox created: {new_mailbox.id} for user {current_user.id}")

    return MailboxResponse.model_validate(new_mailbox)


@router.get("/", response_model=List[MailboxResponse])
async def list_mailboxes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_only: bool = True,
):
    """
    List all mailboxes for the current user.

    Args:
        active_only: If True, only return active mailboxes (default: True)
    """
    query = db.query(Mailbox).filter(Mailbox.user_id == current_user.id)

    if active_only:
        query = query.filter(Mailbox.is_active)

    mailboxes = query.order_by(Mailbox.created_at.desc()).all()

    # Batch-load pending sync-error counts for the badge.
    mailbox_ids = [m.id for m in mailboxes]
    counts: dict = {}
    if mailbox_ids:
        rows = (
            db.query(EmailSyncError.mailbox_id, func.count(EmailSyncError.id))
            .filter(
                EmailSyncError.mailbox_id.in_(mailbox_ids),
                EmailSyncError.status == "pending",
            )
            .group_by(EmailSyncError.mailbox_id)
            .all()
        )
        counts = {mb_id: cnt for mb_id, cnt in rows}

    responses = []
    for m in mailboxes:
        resp = MailboxResponse.model_validate(m)
        resp.pending_sync_errors_count = counts.get(m.id, 0)
        responses.append(resp)
    return responses


@router.get("/{mailbox_id}", response_model=MailboxResponse)
async def get_mailbox(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific mailbox by ID.
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    pending_count = (
        db.query(func.count(EmailSyncError.id))
        .filter(
            EmailSyncError.mailbox_id == mailbox.id,
            EmailSyncError.status == "pending",
        )
        .scalar()
        or 0
    )
    response = MailboxResponse.model_validate(mailbox)
    response.pending_sync_errors_count = pending_count
    return response


@router.put("/{mailbox_id}", response_model=MailboxResponse)
async def update_mailbox(
    mailbox_id: UUID,
    update_data: MailboxUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update mailbox settings.

    Can update display name, sync settings, and credentials.
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)

    # Handle credentials update separately (needs encryption)
    if "credentials" in update_dict:
        new_creds = update_dict.pop("credentials")

        # Test new credentials before updating
        try:
            provider = get_email_provider(mailbox.provider_type, new_creds)
            test_result = await provider.test_connection()
            await provider.close()

            if not test_result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"New credentials test failed: {test_result['message']}",
                )

            # Encrypt and update
            mailbox.encrypted_credentials = encrypt_credentials(new_creds)

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credentials update failed: {str(e)}",
            )

    # Update other fields
    for field, value in update_dict.items():
        setattr(mailbox, field, value)

    db.commit()
    db.refresh(mailbox)

    logger.info(f"Mailbox updated: {mailbox_id}")

    return MailboxResponse.model_validate(mailbox)


@router.delete("/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mailbox(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a mailbox connection.

    This will also delete all associated subscriptions (CASCADE).
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    db.delete(mailbox)
    db.commit()

    logger.info(f"Mailbox deleted: {mailbox_id}")

    return None


@router.get("/{mailbox_id}/sync-status", response_model=MailboxSyncStatus)
async def get_mailbox_sync_status(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current sync status for a mailbox.

    Returns the latest sync information including status, metrics, and any errors.
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    return MailboxSyncStatus(
        mailbox_id=mailbox_id,
        status=mailbox.last_sync_status or "never_synced",
        last_sync_at=mailbox.last_sync_at,
        total_emails_processed=mailbox.last_sync_emails_processed,
        subscriptions_found=mailbox.last_sync_subscriptions_found,
        error_message=mailbox.last_sync_error_message,
    )


@router.post("/{mailbox_id}/sync", response_model=MailboxSyncStatus)
async def trigger_mailbox_sync(
    mailbox_id: UUID,
    sync_request: MailboxSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger email synchronization for a mailbox.

    This will queue a Celery task to fetch and process emails.
    For now, returns a placeholder response. Will be implemented with Celery in next phase.
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    if not mailbox.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot sync inactive mailbox",
        )

    # Set status to 'queued' immediately
    mailbox.last_sync_status = "queued"
    mailbox.last_sync_error_message = None
    db.commit()

    # Queue Celery task for email import
    from app.tasks.email_sync import sync_mailbox_emails

    try:
        task = sync_mailbox_emails.delay(
            mailbox_id=str(mailbox_id),
            force_full_sync=sync_request.force_full_sync,
            date_filter=sync_request.date_filter_override or mailbox.import_date_filter,
        )

        logger.info(f"Sync task queued for mailbox {mailbox_id}, task_id: {task.id}")

        return MailboxSyncStatus(
            mailbox_id=mailbox_id,
            status="queued",
            last_sync_at=mailbox.last_sync_at,
            total_emails_processed=mailbox.last_sync_emails_processed,
            subscriptions_found=mailbox.last_sync_subscriptions_found,
            error_message=None,
        )

    except Exception as e:
        logger.error(f"Failed to queue sync task for mailbox {mailbox_id}: {str(e)}")
        mailbox.last_sync_status = "failed"
        mailbox.last_sync_error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue sync task: {str(e)}",
        )


@router.post("/{mailbox_id}/sync/cancel", response_model=MailboxSyncStatus)
async def cancel_mailbox_sync(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Request cancellation of a running sync for a mailbox.

    The sync will stop gracefully after completing the current batch.
    Progress is saved so the sync can be resumed later.
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    # Check if there's a sync in progress
    if mailbox.last_sync_status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel sync: mailbox is not currently syncing (status: {mailbox.last_sync_status})",
        )

    # Set the cancellation flag
    mailbox.sync_cancellation_requested = True
    db.commit()

    logger.info(f"Sync cancellation requested for mailbox {mailbox_id}")

    return MailboxSyncStatus(
        mailbox_id=mailbox_id,
        status="cancelling",
        last_sync_at=mailbox.last_sync_at,
        total_emails_processed=mailbox.last_sync_emails_processed,
        subscriptions_found=mailbox.last_sync_subscriptions_found,
        error_message=None,
    )


@router.post("/{mailbox_id}/sync/resume", response_model=MailboxSyncStatus)
async def resume_mailbox_sync(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Resume a cancelled or interrupted sync for a mailbox.

    The sync will automatically resume from where it left off if the cancellation
    was recent (< 1 hour). Otherwise, it will start from the beginning.
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    if not mailbox.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resume sync: mailbox is not active",
        )

    # Check if there's already a sync in progress
    if mailbox.last_sync_status == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot resume sync: a sync is already in progress",
        )

    # Clear cancellation flag if it was set
    if mailbox.sync_cancellation_requested:
        mailbox.sync_cancellation_requested = False
        db.commit()

    # Queue Celery task - it will automatically resume from last position if possible
    from app.tasks.email_sync import sync_mailbox_emails

    try:
        # Set status to 'queued'
        mailbox.last_sync_status = "queued"
        mailbox.last_sync_error_message = None
        db.commit()

        task = sync_mailbox_emails.delay(
            mailbox_id=str(mailbox_id),
            force_full_sync=False,  # Let the task decide whether to resume or restart
            date_filter=mailbox.import_date_filter,
        )

        logger.info(
            f"Sync resume task queued for mailbox {mailbox_id}, task_id: {task.id}"
        )

        return MailboxSyncStatus(
            mailbox_id=mailbox_id,
            status="queued",
            last_sync_at=mailbox.last_sync_at,
            total_emails_processed=mailbox.last_sync_emails_processed,
            subscriptions_found=mailbox.last_sync_subscriptions_found,
            error_message=None,
        )

    except Exception as e:
        logger.error(f"Failed to queue resume task for mailbox {mailbox_id}: {str(e)}")
        mailbox.last_sync_status = "failed"
        mailbox.last_sync_error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue resume task: {str(e)}",
        )


@router.get("/{mailbox_id}/sync-progress", response_model=SyncProgressResponse)
async def get_sync_progress(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get real-time sync progress for a mailbox (Issue #10).

    Returns current progress information including batch number, percentage,
    and estimated completion time.
    """
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    # Calculate elapsed time if sync is in progress
    elapsed_seconds = None
    if mailbox.last_sync_status == "in_progress" and mailbox.last_sync_started_at:
        elapsed_time = datetime.now(
            timezone.utc
        ) - mailbox.last_sync_started_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = int(elapsed_time.total_seconds())

    return SyncProgressResponse(
        mailbox_id=mailbox_id,
        status=mailbox.last_sync_status or "never_synced",
        current_batch_number=mailbox.current_batch_number,
        total_batches_estimate=mailbox.total_batches_estimate,
        progress_percentage=mailbox.progress_percentage,
        estimated_completion_time=mailbox.estimated_completion_time,
        emails_processed=mailbox.last_sync_emails_processed,
        subscriptions_found=mailbox.last_sync_subscriptions_found,
        started_at=mailbox.last_sync_started_at,
        elapsed_seconds=elapsed_seconds,
    )


@router.get("/{mailbox_id}/sync-history", response_model=SyncHistoryList)
async def get_sync_history(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="Filter by status"),
):
    """
    Get paginated sync history for a mailbox (Issue #11).

    Returns historical records of all sync operations with metrics and status.
    """
    # Verify mailbox ownership
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    # Build query
    query = db.query(SyncHistory).filter(SyncHistory.mailbox_id == mailbox_id)

    # Apply status filter if provided
    if status:
        query = query.filter(SyncHistory.status == status)

    # Get total count
    total = query.count()

    # Get paginated results
    history_items = (
        query.order_by(SyncHistory.started_at.desc()).offset(offset).limit(limit).all()
    )

    return SyncHistoryList(
        items=[SyncHistoryResponse.model_validate(item) for item in history_items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{mailbox_id}/sync-history/{history_id}", response_model=SyncHistoryResponse
)
async def get_sync_history_detail(
    mailbox_id: UUID,
    history_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific sync history entry (Issue #11).
    """
    # Verify mailbox ownership
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    # Get history entry
    history_entry = (
        db.query(SyncHistory)
        .filter(SyncHistory.id == history_id, SyncHistory.mailbox_id == mailbox_id)
        .first()
    )

    if not history_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sync history entry not found"
        )

    return SyncHistoryResponse.model_validate(history_entry)


@router.get("/{mailbox_id}/sync-statistics", response_model=SyncStatistics)
async def get_sync_statistics(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get sync statistics summary for a mailbox (Issue #11).

    Returns aggregated statistics including total syncs, success rate,
    and processing metrics.
    """
    # Verify mailbox ownership
    mailbox = (
        db.query(Mailbox)
        .filter(Mailbox.id == mailbox_id, Mailbox.user_id == current_user.id)
        .first()
    )

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found"
        )

    # Calculate statistics
    total_syncs = (
        db.query(SyncHistory).filter(SyncHistory.mailbox_id == mailbox_id).count()
    )

    successful_syncs = (
        db.query(SyncHistory)
        .filter(SyncHistory.mailbox_id == mailbox_id, SyncHistory.status == "completed")
        .count()
    )

    failed_syncs = (
        db.query(SyncHistory)
        .filter(SyncHistory.mailbox_id == mailbox_id, SyncHistory.status == "failed")
        .count()
    )

    cancelled_syncs = (
        db.query(SyncHistory)
        .filter(SyncHistory.mailbox_id == mailbox_id, SyncHistory.status == "cancelled")
        .count()
    )

    # Sum of emails processed
    total_emails_result = (
        db.query(func.sum(SyncHistory.total_emails_processed))
        .filter(SyncHistory.mailbox_id == mailbox_id)
        .scalar()
    )
    total_emails_processed = int(total_emails_result) if total_emails_result else 0

    # Sum of subscriptions found
    total_subs_result = (
        db.query(func.sum(SyncHistory.subscriptions_found))
        .filter(SyncHistory.mailbox_id == mailbox_id)
        .scalar()
    )
    total_subscriptions_found = int(total_subs_result) if total_subs_result else 0

    # Average duration
    avg_duration_result = (
        db.query(func.avg(SyncHistory.duration_seconds))
        .filter(SyncHistory.mailbox_id == mailbox_id, SyncHistory.status == "completed")
        .scalar()
    )
    average_duration_seconds = (
        float(avg_duration_result) if avg_duration_result else None
    )

    # Last successful and failed sync times
    last_successful = (
        db.query(SyncHistory)
        .filter(SyncHistory.mailbox_id == mailbox_id, SyncHistory.status == "completed")
        .order_by(SyncHistory.completed_at.desc())
        .first()
    )

    last_failed = (
        db.query(SyncHistory)
        .filter(SyncHistory.mailbox_id == mailbox_id, SyncHistory.status == "failed")
        .order_by(SyncHistory.completed_at.desc())
        .first()
    )

    return SyncStatistics(
        total_syncs=total_syncs,
        successful_syncs=successful_syncs,
        failed_syncs=failed_syncs,
        cancelled_syncs=cancelled_syncs,
        total_emails_processed=total_emails_processed,
        total_subscriptions_found=total_subscriptions_found,
        average_duration_seconds=average_duration_seconds,
        last_successful_sync=last_successful.completed_at if last_successful else None,
        last_failed_sync=last_failed.completed_at if last_failed else None,
    )
