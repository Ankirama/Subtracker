"""
Celery tasks for email synchronization and subscription detection.
"""
from celery import Task
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from uuid import UUID
import logging
import asyncio

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.mailbox import Mailbox
from app.models.subscription import Subscription
from app.models.email_message import EmailMessage, subscription_emails
from app.email_providers import JMAPProvider
from app.security.encryption import decrypt_credentials
from app.config import settings

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    Base task with database session management.
    """
    _db: Session = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Close database session after task completion."""
        if self._db is not None:
            self._db.close()
            self._db = None


async def _sync_mailbox_async(
    db: Session,
    mailbox: Mailbox,
    force_full_sync: bool,
    date_filter: str
) -> Dict[str, Any]:
    """
    Async implementation of email sync logic.
    """
    try:
        # Decrypt credentials
        credentials = decrypt_credentials(mailbox.encrypted_credentials)
        
        # Get email provider
        if mailbox.provider_type == 'jmap':
            provider = JMAPProvider(credentials)
        else:
            raise ValueError(f"Unsupported provider type: {mailbox.provider_type}")
        
        # Authenticate
        auth_success = await provider.authenticate()
        if not auth_success:
            return {"success": False, "error": "Authentication failed"}
        
        # Determine date filter - prioritize explicit date_filter parameter
        since_date = None
        if date_filter:
            # Use explicit date filter if provided (from UI or API call)
            filter_str = date_filter
            since_date = parse_date_filter(filter_str)
            logger.info(f"Using custom date filter: {filter_str} (since {since_date})")
        elif not force_full_sync and mailbox.last_sync_at:
            # Use last sync time for incremental updates
            since_date = mailbox.last_sync_at
            logger.info(f"Using last sync time: {since_date}")
        elif mailbox.import_date_filter:
            # Fall back to mailbox's default import filter
            filter_str = mailbox.import_date_filter
            since_date = parse_date_filter(filter_str)
            logger.info(f"Using mailbox default filter: {filter_str} (since {since_date})")
        else:
            # No filter - fetch all emails
            since_date = None
            logger.info("No date filter - fetching all emails")

        # Import AI services here to avoid circular imports
        from app.services.ai_classifier import classify_email
        from app.services.subscription_extractor import extract_subscription_data

        # Pagination loop - fetch and process emails in batches
        position = 0
        has_more = True
        total_emails_processed = 0
        subscriptions_found = 0
        subscriptions_updated = 0
        batch_num = 0

        logger.info(f"Starting paginated email fetch since {since_date}")

        while has_more:
            batch_num += 1

            # Fetch batch of emails
            logger.info(f"Fetching batch {batch_num} (position {position}, batch_size {mailbox.batch_size})")
            emails, has_more = await provider.fetch_messages(
                folder=None,
                since_date=since_date,
                limit=mailbox.batch_size,
                position=position
            )

            batch_size = len(emails)
            logger.info(f"SYNC DEBUG - Fetched {batch_size} emails in batch {batch_num}, has_more={has_more}, current position={position}")

            if batch_size == 0:
                logger.info("SYNC DEBUG - No more emails to fetch (batch_size=0), breaking loop")
                break

            logger.info(f"SYNC DEBUG - Loop state BEFORE processing: has_more={has_more}, position={position}, batch_num={batch_num}")

            # Process emails in this batch
            for idx, email in enumerate(emails):
                try:
                    # Get Message-ID from headers for uniqueness check
                    message_id = email.headers.get('Message-ID', email.id)

                    # Check if email already exists in database
                    existing_email = db.query(EmailMessage).filter(
                        EmailMessage.message_id == message_id
                    ).first()

                    if not existing_email:
                        # Stage 1: Classify email (OpenAI API call)
                        classification = await classify_email(email)

                        # Rate limiting: Add delay after OpenAI API call
                        if idx < len(emails) - 1:  # Don't delay after the last email
                            delay = settings.OPENAI_REQUEST_DELAY_SECONDS
                            logger.debug(f"Rate limiting: waiting {delay}s before next email...")
                            await asyncio.sleep(delay)

                        # Save email to database
                        email_record = EmailMessage(
                            mailbox_id=mailbox.id,
                            message_id=message_id,
                            thread_id=email.headers.get('Thread-ID'),
                            subject=email.subject,
                            sender=email.sender,
                            sender_name=email.sender_name,
                            recipient=email.recipients[0] if email.recipients else mailbox.email_address,
                            date=email.date,
                            body_text=email.body_text,
                            body_html=email.body_html,
                            labels=[email.folder] if email.folder else None,
                            attachments=None,  # TODO: Store attachment metadata if needed
                            is_subscription=classification.get('is_subscription', False),
                            classification_confidence=classification.get('confidence', 0.0),
                            classification_reasoning=classification
                        )
                        db.add(email_record)
                        db.flush()  # Get the ID without committing
                        logger.info(f"Saved email to database: {email.subject}")
                    else:
                        email_record = existing_email
                        logger.info(f"Email already exists in database: {email.subject}")

                    # Process subscription if email is classified as subscription-related
                    if email_record.is_subscription:
                        logger.info(f"Subscription email detected: {email.subject}")

                        # Stage 2: Extract subscription data (OpenAI API call)
                        subscription_data = await extract_subscription_data(email)

                        # Rate limiting: Add delay after OpenAI API call
                        if idx < len(emails) - 1:  # Don't delay after the last email
                            delay = settings.OPENAI_REQUEST_DELAY_SECONDS
                            logger.debug(f"Rate limiting: waiting {delay}s before next email...")
                            await asyncio.sleep(delay)

                        if subscription_data:
                            # Check if subscription already exists using composite key
                            # Strategy: Match on stable fields (provider, amount, billing_cycle, email_sender)
                            # Only use custom_label for genuinely different subscriptions (Twitch channels, specific tiers)

                            # Start with base query: mailbox + provider
                            query = db.query(Subscription).filter(
                                Subscription.mailbox_id == mailbox.id,
                                Subscription.provider == subscription_data['provider']
                            )

                            # Add stable matching fields to prevent AI-description-based duplicates
                            if subscription_data.get('amount') is not None:
                                query = query.filter(Subscription.amount == subscription_data['amount'])

                            if subscription_data.get('billing_cycle'):
                                query = query.filter(Subscription.billing_cycle == subscription_data['billing_cycle'])

                            if subscription_data.get('email_sender'):
                                query = query.filter(Subscription.email_sender == subscription_data['email_sender'])

                            # Only use custom_label for meaningful distinctions (Twitch channels, specific plans)
                            # Ignore generic descriptions like "renewal", "payment", "subscription notification"
                            custom_label = subscription_data.get('custom_label')
                            if custom_label:
                                # Check if custom_label is meaningful (contains tier/channel info)
                                meaningful_keywords = ['tier', 'channel', 'plan', 'premium', 'basic', 'pro', 'plus', 'family', 'individual', 'student']
                                is_meaningful = any(keyword in custom_label.lower() for keyword in meaningful_keywords)

                                if is_meaningful:
                                    # Use custom_label for matching (different tiers/channels)
                                    query = query.filter(Subscription.custom_label == custom_label)

                            existing_sub = query.first()

                            subscription_record = None
                            if existing_sub:
                                # Update existing subscription
                                for key, value in subscription_data.items():
                                    setattr(existing_sub, key, value)
                                existing_sub.updated_at = datetime.now(timezone.utc)
                                subscription_record = existing_sub
                                subscriptions_updated += 1
                                logger.info(f"Updated subscription: {subscription_data['provider']} - {custom_label or 'No label'}")
                            else:
                                # Create new subscription
                                new_subscription = Subscription(
                                    user_id=mailbox.user_id,
                                    mailbox_id=mailbox.id,
                                    **subscription_data
                                )
                                db.add(new_subscription)
                                db.flush()  # Get the ID
                                subscription_record = new_subscription
                                subscriptions_found += 1
                                logger.info(f"Created new subscription: {subscription_data['provider']} - {custom_label or 'No label'}")

                            # Create subscription-email relationship if not exists
                            if subscription_record and email_record:
                                # Check if relationship already exists
                                relationship_exists = db.execute(
                                    subscription_emails.select().where(
                                        subscription_emails.c.subscription_id == subscription_record.id,
                                        subscription_emails.c.email_id == email_record.id
                                    )
                                ).first()

                                if not relationship_exists:
                                    # Convert datetime objects to ISO strings for JSONB storage
                                    extraction_data_json = {}
                                    for key, value in subscription_data.items():
                                        if isinstance(value, datetime):
                                            extraction_data_json[key] = value.isoformat()
                                        else:
                                            extraction_data_json[key] = value

                                    db.execute(
                                        subscription_emails.insert().values(
                                            subscription_id=subscription_record.id,
                                            email_id=email_record.id,
                                            extraction_role='detection' if not existing_sub else 'update',
                                            extraction_data=extraction_data_json
                                        )
                                    )
                                    logger.info(f"Linked email to subscription")

                            db.commit()

                except Exception as e:
                    logger.error(f"Error processing email {email.id}: {str(e)}")
                    db.rollback()
                    continue

            # Update counters after processing batch
            total_emails_processed += batch_size
            position += batch_size

            logger.info(f"SYNC DEBUG - Updated position to {position}, total_emails_processed={total_emails_processed}")

            # Update sync progress in database
            mailbox.last_sync_emails_processed = total_emails_processed
            mailbox.last_sync_subscriptions_found = subscriptions_found
            db.commit()

            logger.info(f"Completed batch {batch_num}: {total_emails_processed} total emails processed, {subscriptions_found} subscriptions found")
            logger.info(f"SYNC DEBUG - Loop state at END of iteration: has_more={has_more}, position={position}, will_continue={has_more}")

            # Continue to next batch if has_more is True

        # Close provider connection
        await provider.close()

        return {
            "success": True,
            "total_emails_processed": total_emails_processed,
            "subscriptions_found": subscriptions_found,
            "subscriptions_updated": subscriptions_updated
        }
        
    except Exception as e:
        logger.error(f"Error in async sync: {str(e)}")
        raise


@celery_app.task(base=DatabaseTask, bind=True, name="app.tasks.email_sync.sync_mailbox_emails")
def sync_mailbox_emails(
    self,
    mailbox_id: str,
    force_full_sync: bool = False,
    date_filter: str = None
) -> Dict[str, Any]:
    """
    Sync emails from a mailbox and detect subscriptions.

    Args:
        mailbox_id: UUID of the mailbox to sync
        force_full_sync: If True, ignore last_sync_at and sync all emails
        date_filter: Override mailbox date filter (e.g., '30days', '6months')

    Returns:
        Dict with sync results
    """
    db = self.db
    logger.info(f"Starting email sync for mailbox {mailbox_id}")

    # Fetch mailbox
    mailbox = db.query(Mailbox).filter(Mailbox.id == UUID(mailbox_id)).first()
    if not mailbox:
        logger.error(f"Mailbox {mailbox_id} not found")
        return {"success": False, "error": "Mailbox not found"}

    if not mailbox.is_active:
        logger.error(f"Mailbox {mailbox_id} is not active")
        return {"success": False, "error": "Mailbox is not active"}

    # Set status to in_progress and clear previous error
    mailbox.last_sync_status = 'in_progress'
    mailbox.last_sync_error_message = None
    db.commit()

    try:
        # Run async sync logic
        result = asyncio.run(_sync_mailbox_async(db, mailbox, force_full_sync, date_filter))

        # Update mailbox sync status with metrics
        mailbox.last_sync_at = datetime.now(timezone.utc)
        mailbox.last_sync_status = 'success' if result['success'] else 'failed'

        if result['success']:
            # Update metrics on success
            mailbox.last_sync_emails_processed = result.get('total_emails_processed', 0)
            mailbox.last_sync_subscriptions_found = result.get('subscriptions_found', 0) + result.get('subscriptions_updated', 0)
            mailbox.last_sync_error_message = None

            # Update subscription active/inactive status based on last confirmation dates
            status_update = update_subscription_statuses(db, mailbox.id)
            logger.info(f"Subscription status update: {status_update['activated']} activated, {status_update['deactivated']} deactivated")
        else:
            # Store error message on failure
            mailbox.last_sync_error_message = result.get('error', 'Unknown error')

        db.commit()

        result.update({
            "mailbox_id": mailbox_id,
            "sync_timestamp": datetime.now(timezone.utc).isoformat()
        })

        logger.info(f"Email sync completed for mailbox {mailbox_id}: {result}")
        return result

    except Exception as e:
        logger.error(f"Email sync failed for mailbox {mailbox_id}: {str(e)}")
        mailbox.last_sync_status = 'failed'
        mailbox.last_sync_at = datetime.now(timezone.utc)
        mailbox.last_sync_error_message = str(e)
        db.commit()
        return {"success": False, "error": str(e)}


def update_subscription_statuses(db: Session, mailbox_id: UUID) -> Dict[str, int]:
    """
    Update subscription active status based on last email confirmation.

    Logic:
    - If last email was received within expected billing cycle + grace period, mark as active
    - Otherwise, mark as inactive

    Grace periods by billing cycle:
    - weekly: 2 weeks (14 days)
    - monthly: 2 months (60 days)
    - quarterly: 4 months (120 days)
    - biannual: 7 months (210 days)
    - yearly/annual: 13 months (395 days)

    Returns:
        Dict with counts of activated and deactivated subscriptions
    """
    # Define grace periods for each billing cycle (in days)
    GRACE_PERIODS = {
        'weekly': 14,
        'monthly': 60,
        'quarterly': 120,
        'biannual': 210,
        'yearly': 395,
        'annual': 395,
    }

    now = datetime.now(timezone.utc)
    activated_count = 0
    deactivated_count = 0

    # Get all subscriptions for this mailbox
    subscriptions = db.query(Subscription).filter(
        Subscription.mailbox_id == mailbox_id
    ).all()

    for sub in subscriptions:
        if not sub.billing_cycle:
            # Skip subscriptions without billing cycle defined
            continue

        # Get grace period for this billing cycle (default to 60 days if unknown)
        billing_cycle_lower = sub.billing_cycle.lower()
        grace_days = GRACE_PERIODS.get(billing_cycle_lower, 60)

        # Calculate cutoff date
        cutoff_date = now - timedelta(days=grace_days)

        # Check if subscription should be active
        should_be_active = sub.last_confirmed_at >= cutoff_date

        # Update status if it changed
        if should_be_active and not sub.is_active:
            sub.is_active = True
            activated_count += 1
            logger.info(f"Activated subscription: {sub.provider} (last confirmed: {sub.last_confirmed_at})")
        elif not should_be_active and sub.is_active:
            sub.is_active = False
            deactivated_count += 1
            logger.info(f"Deactivated subscription: {sub.provider} (last confirmed: {sub.last_confirmed_at}, cutoff: {cutoff_date})")

    if activated_count > 0 or deactivated_count > 0:
        db.commit()
        logger.info(f"Subscription status update: {activated_count} activated, {deactivated_count} deactivated")

    return {
        "activated": activated_count,
        "deactivated": deactivated_count
    }


def parse_date_filter(filter_str: str) -> datetime:
    """
    Parse date filter string into datetime.

    Supported formats:
    - '30days', '60days', '90days', '365days'
    - '1month', '3months', '6months', '12months'
    - '1year', '2years'
    """
    filter_str = filter_str.lower().strip()
    now = datetime.now(timezone.utc)

    if 'day' in filter_str:
        days = int(filter_str.replace('days', '').replace('day', ''))
        return now - timedelta(days=days)
    elif 'month' in filter_str:
        months = int(filter_str.replace('months', '').replace('month', ''))
        return now - timedelta(days=months * 30)
    elif 'year' in filter_str:
        years = int(filter_str.replace('years', '').replace('year', ''))
        return now - timedelta(days=years * 365)
    else:
        # Use configurable default sync period
        return now - timedelta(days=settings.DEFAULT_SYNC_PERIOD_DAYS)
