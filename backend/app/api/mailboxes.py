"""
Mailbox API endpoints for managing email account connections.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.mailbox import Mailbox
from app.schemas.mailbox import (
    MailboxCreate,
    MailboxUpdate,
    MailboxResponse,
    MailboxTestConnection,
    MailboxTestResult,
    MailboxSyncRequest,
    MailboxSyncStatus
)
from app.security.dependencies import get_current_user
from app.security.encryption import encrypt_credentials, decrypt_credentials
from app.email_providers import JMAPProvider
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_email_provider(provider_type: str, credentials: dict):
    """
    Factory function to get the appropriate email provider instance.
    """
    if provider_type == 'jmap':
        return JMAPProvider(credentials)
    elif provider_type == 'gmail':
        # TODO: Implement GmailProvider in Phase 2
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Gmail provider not yet implemented. Coming in Phase 2."
        )
    elif provider_type == 'outlook':
        # TODO: Implement OutlookProvider in Phase 2
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Outlook provider not yet implemented. Coming in Phase 2."
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider type: {provider_type}"
        )


@router.post("/test", response_model=MailboxTestResult)
async def test_mailbox_connection(
    test_data: MailboxTestConnection,
    current_user: User = Depends(get_current_user)
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
            provider_info=None
        )


@router.post("/", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
async def create_mailbox(
    mailbox_data: MailboxCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new mailbox connection.

    The credentials are encrypted before storage.
    """
    # Check if mailbox with this email already exists for user
    existing = db.query(Mailbox).filter(
        Mailbox.user_id == current_user.id,
        Mailbox.email_address == mailbox_data.email_address
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mailbox with email {mailbox_data.email_address} already exists"
        )

    # Test connection before saving
    try:
        provider = get_email_provider(mailbox_data.provider_type, mailbox_data.credentials)
        test_result = await provider.test_connection()
        await provider.close()

        if not test_result['success']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection test failed: {test_result['message']}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection test failed: {str(e)}"
        )

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
        last_sync_status=None
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
    active_only: bool = True
):
    """
    List all mailboxes for the current user.

    Args:
        active_only: If True, only return active mailboxes (default: True)
    """
    query = db.query(Mailbox).filter(Mailbox.user_id == current_user.id)

    if active_only:
        query = query.filter(Mailbox.is_active == True)

    mailboxes = query.order_by(Mailbox.created_at.desc()).all()

    return [MailboxResponse.model_validate(m) for m in mailboxes]


@router.get("/{mailbox_id}", response_model=MailboxResponse)
async def get_mailbox(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific mailbox by ID.
    """
    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == current_user.id
    ).first()

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found"
        )

    return MailboxResponse.model_validate(mailbox)


@router.put("/{mailbox_id}", response_model=MailboxResponse)
async def update_mailbox(
    mailbox_id: UUID,
    update_data: MailboxUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update mailbox settings.

    Can update display name, sync settings, and credentials.
    """
    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == current_user.id
    ).first()

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found"
        )

    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)

    # Handle credentials update separately (needs encryption)
    if 'credentials' in update_dict:
        new_creds = update_dict.pop('credentials')

        # Test new credentials before updating
        try:
            provider = get_email_provider(mailbox.provider_type, new_creds)
            test_result = await provider.test_connection()
            await provider.close()

            if not test_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"New credentials test failed: {test_result['message']}"
                )

            # Encrypt and update
            mailbox.encrypted_credentials = encrypt_credentials(new_creds)

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credentials update failed: {str(e)}"
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
    current_user: User = Depends(get_current_user)
):
    """
    Delete a mailbox connection.

    This will also delete all associated subscriptions (CASCADE).
    """
    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == current_user.id
    ).first()

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found"
        )

    db.delete(mailbox)
    db.commit()

    logger.info(f"Mailbox deleted: {mailbox_id}")

    return None


@router.get("/{mailbox_id}/sync-status", response_model=MailboxSyncStatus)
async def get_mailbox_sync_status(
    mailbox_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current sync status for a mailbox.

    Returns the latest sync information including status, metrics, and any errors.
    """
    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == current_user.id
    ).first()

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found"
        )

    return MailboxSyncStatus(
        mailbox_id=mailbox_id,
        status=mailbox.last_sync_status or 'never_synced',
        last_sync_at=mailbox.last_sync_at,
        total_emails_processed=mailbox.last_sync_emails_processed,
        subscriptions_found=mailbox.last_sync_subscriptions_found,
        error_message=mailbox.last_sync_error_message
    )


@router.post("/{mailbox_id}/sync", response_model=MailboxSyncStatus)
async def trigger_mailbox_sync(
    mailbox_id: UUID,
    sync_request: MailboxSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger email synchronization for a mailbox.

    This will queue a Celery task to fetch and process emails.
    For now, returns a placeholder response. Will be implemented with Celery in next phase.
    """
    mailbox = db.query(Mailbox).filter(
        Mailbox.id == mailbox_id,
        Mailbox.user_id == current_user.id
    ).first()

    if not mailbox:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mailbox not found"
        )

    if not mailbox.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot sync inactive mailbox"
        )

    # Set status to 'queued' immediately
    mailbox.last_sync_status = 'queued'
    mailbox.last_sync_error_message = None
    db.commit()

    # Queue Celery task for email import
    from app.tasks.email_sync import sync_mailbox_emails

    try:
        task = sync_mailbox_emails.delay(
            mailbox_id=str(mailbox_id),
            force_full_sync=sync_request.force_full_sync,
            date_filter=sync_request.date_filter_override or mailbox.import_date_filter
        )

        logger.info(f"Sync task queued for mailbox {mailbox_id}, task_id: {task.id}")

        return MailboxSyncStatus(
            mailbox_id=mailbox_id,
            status='queued',
            last_sync_at=mailbox.last_sync_at,
            total_emails_processed=mailbox.last_sync_emails_processed,
            subscriptions_found=mailbox.last_sync_subscriptions_found,
            error_message=None
        )

    except Exception as e:
        logger.error(f"Failed to queue sync task for mailbox {mailbox_id}: {str(e)}")
        mailbox.last_sync_status = 'failed'
        mailbox.last_sync_error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue sync task: {str(e)}"
        )
