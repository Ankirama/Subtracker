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
from app.models.price_history import PriceHistory
from app.models.sync_history import SyncHistory
from app.email_providers import JMAPProvider
from app.security.encryption import decrypt_credentials
from app.config import settings
from app.utils.config_helper import get_config_value
from app.services.renewal_calculator import RenewalCalculator, get_subscription_emails
from app.services.ai_classifier import classify_emails_batch
from app.services.subscription_extractor import extract_subscriptions_batch
from app.services.email_filter import should_process_email

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
    date_filter: str,
    resume_position: int = 0,
    resume_batch_num: int = 0,
    sync_start_time: datetime = None,
    history_entry: 'SyncHistory' = None
) -> Dict[str, Any]:
    """
    Async implementation of email sync logic with resume capability.

    Args:
        db: Database session
        mailbox: Mailbox to sync
        force_full_sync: Whether to ignore last sync and fetch all
        date_filter: Optional date filter override
        resume_position: Position to resume from (for interrupted syncs)
        resume_batch_num: Batch number to resume from (for interrupted syncs)
        sync_start_time: Start time of the sync (for progress tracking)
        history_entry: Sync history entry to update on cancellation
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
            since_date = parse_date_filter(filter_str, db)
            logger.info(f"Using custom date filter: {filter_str} (since {since_date})")
        elif not force_full_sync and mailbox.last_sync_at:
            # Use last sync time for incremental updates
            since_date = mailbox.last_sync_at
            logger.info(f"Using last sync time: {since_date}")
        elif mailbox.import_date_filter:
            # Fall back to mailbox's default import filter
            filter_str = mailbox.import_date_filter
            since_date = parse_date_filter(filter_str, db)
            logger.info(f"Using mailbox default filter: {filter_str} (since {since_date})")
        else:
            # No filter - fetch all emails
            since_date = None
            logger.info("No date filter - fetching all emails")

        # Import AI services here to avoid circular imports
        from app.services.ai_classifier import classify_emails_batch
        from app.services.subscription_extractor import extract_subscriptions_batch

        # Pagination loop - fetch and process emails in batches
        # Resume from last position if resuming an interrupted sync
        position = resume_position
        has_more = True
        total_emails_processed = mailbox.last_sync_emails_processed or 0  # Resume from last count
        subscriptions_found = 0
        subscriptions_updated = 0
        batch_num = resume_batch_num

        if resume_position > 0:
            logger.info(f"Resuming paginated email fetch from position {position}, batch {batch_num}")
        else:
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

            # Issue #9 fix: Safety check for empty batch (catches edge cases from pagination heuristics)
            if batch_size == 0:
                logger.info("SYNC DEBUG - No more emails to fetch (batch_size=0), breaking loop (Issue #9 safety net)")
                break

            logger.info(f"SYNC DEBUG - Loop state BEFORE processing: has_more={has_more}, position={position}, batch_num={batch_num}")

            # STAGE 1: Parallel Classification
            # Filter out emails that already exist
            new_emails = []
            new_emails_to_classify = []
            existing_email_records = []

            for email in emails:
                message_id = email.headers.get('Message-ID', email.id)
                existing_email = db.query(EmailMessage).filter(
                    EmailMessage.message_id == message_id
                ).first()

                if not existing_email:
                    new_emails.append(email)
                    # Only add to classification if not a system email
                    if should_process_email(email, db):
                        new_emails_to_classify.append(email)
                    else:
                        logger.info(f"Skipping system email: {email.subject}")
                else:
                    existing_email_records.append((email, existing_email))

            logger.info(f"Batch {batch_num}: {len(new_emails)} new emails, {len(existing_email_records)} existing emails")

            # Classify all new emails in parallel
            classifications = []
            if new_emails_to_classify:
                logger.info(f"Classifying {len(new_emails_to_classify)} emails in parallel...")
                classifications = await classify_emails_batch(new_emails_to_classify, db)

            # Save new emails to database with classification results
            email_records = []
            for email, classification in zip(new_emails, classifications):
                message_id = email.headers.get('Message-ID', email.id)
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
                    attachments=None,
                    is_subscription=classification.get('is_subscription', False),
                    classification_confidence=classification.get('confidence', 0.0),
                    classification_reasoning=classification
                )
                db.add(email_record)
                db.flush()
                email_records.append((email, email_record))
                logger.info(f"Saved email to database: {email.subject} (subscription: {email_record.is_subscription})")

            # STAGE 2: Parallel Extraction for subscription emails
            subscription_emails_to_extract = []
            subscription_email_records = []
            skipped_count = 0

            # Add newly classified subscription emails (always need extraction)
            new_subscription_count = 0
            for email, email_record in email_records:
                if email_record.is_subscription:
                    subscription_emails_to_extract.append(email)
                    subscription_email_records.append((email, email_record))
                    new_subscription_count += 1

            # For existing subscription emails, only extract if not already linked to a subscription
            # This avoids redundant API calls for emails that have already been processed
            existing_subscription_count = 0
            for email, email_record in existing_email_records:
                if email_record.is_subscription:
                    existing_subscription_count += 1

                    # Check if this email is already linked to a subscription (extraction already done)
                    existing_link = db.execute(
                        subscription_emails.select().where(
                            subscription_emails.c.email_id == email_record.id
                        )
                    ).first()

                    if not existing_link:
                        # No existing link - needs extraction
                        subscription_emails_to_extract.append(email)
                        subscription_email_records.append((email, email_record))
                        logger.info(f"Existing email needs extraction: {email.subject}")
                    else:
                        skipped_count += 1
                        logger.debug(f"Skipping extraction for already-linked email: {email.subject}")

            logger.info(
                f"Subscription emails: {new_subscription_count} new, {existing_subscription_count} existing "
                f"({len(subscription_emails_to_extract)} need extraction, {skipped_count} cached)"
            )

            # Extract subscription data in parallel
            subscription_data_list = []
            if subscription_emails_to_extract:
                logger.info(f"Extracting {len(subscription_emails_to_extract)} subscription emails in parallel...")
                subscription_data_list = await extract_subscriptions_batch(subscription_emails_to_extract, db)

            # STAGE 3: Process subscription data and save to database
            for (email, email_record), subscription_data in zip(subscription_email_records, subscription_data_list):
                try:
                    if subscription_data:
                        logger.info(f"Processing subscription data for: {email.subject}")

                        # PRIORITY: Handle price updates detected by AI
                        is_price_update = subscription_data.get('is_price_update', False)

                        if is_price_update:
                            logger.info(f"Price update detected by AI for: {email.subject}")
                            old_amount = subscription_data.get('old_amount')
                            new_amount = subscription_data.get('new_amount')

                            # Search for existing subscription more aggressively for price updates
                            existing_sub = db.query(Subscription).filter(
                                Subscription.mailbox_id == mailbox.id,
                                Subscription.provider == subscription_data['provider']
                            ).first()

                            if existing_sub:
                                logger.info(f"Found existing subscription for price update: {existing_sub.provider}")

                                # Update subscription with new price
                                existing_sub.amount = new_amount
                                existing_sub.updated_at = datetime.now(timezone.utc)

                                # Create price history record
                                if old_amount is not None and new_amount is not None:
                                    change_percentage = ((float(new_amount) - float(old_amount)) / float(old_amount)) * 100
                                    change_type = 'increase' if float(new_amount) > float(old_amount) else 'decrease'

                                    price_history_record = PriceHistory(
                                        subscription_id=existing_sub.id,
                                        old_amount=old_amount,
                                        new_amount=new_amount,
                                        currency=subscription_data.get('currency') or existing_sub.currency,
                                        change_type=change_type,
                                        change_percentage=round(change_percentage, 2),
                                        detected_from='email',
                                        notes=f"Price update detected by AI from email: {email.subject}"
                                    )
                                    db.add(price_history_record)
                                    logger.info(f"AI-detected price {change_type} for {existing_sub.provider}: {old_amount} -> {new_amount} ({change_type} of {abs(change_percentage):.1f}%)")

                                # Link email to existing subscription
                                relationship_exists = db.execute(
                                    subscription_emails.select().where(
                                        subscription_emails.c.subscription_id == existing_sub.id,
                                        subscription_emails.c.email_id == email_record.id
                                    )
                                ).first()

                                if not relationship_exists:
                                    extraction_data_json = {}
                                    for key, value in subscription_data.items():
                                        if isinstance(value, datetime):
                                            extraction_data_json[key] = value.isoformat()
                                        else:
                                            extraction_data_json[key] = value

                                    db.execute(
                                        subscription_emails.insert().values(
                                            subscription_id=existing_sub.id,
                                            email_id=email_record.id,
                                            extraction_role='price_update',
                                            extraction_data=extraction_data_json
                                        )
                                    )
                                    logger.info(f"Linked price update email to subscription")

                                subscriptions_updated += 1
                                db.commit()
                                continue  # Skip normal processing, price update handled
                            else:
                                logger.warning(f"Price update detected but no existing subscription found for {subscription_data['provider']}, creating new subscription")
                                # Fall through to normal creation logic

                        # NORMAL PROCESSING: Check if subscription already exists using composite key
                        # Strategy: Match on stable fields (provider, billing_cycle, email_sender)
                        # Note: Amount is NOT used for matching since prices can change over time
                        # Only use custom_label for genuinely different subscriptions (Twitch channels, specific tiers)

                        # Start with base query: mailbox + provider
                        query = db.query(Subscription).filter(
                            Subscription.mailbox_id == mailbox.id,
                            Subscription.provider == subscription_data['provider']
                        )

                        # Add stable matching fields to prevent AI-description-based duplicates
                        # Note: We removed amount matching to handle price changes gracefully

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
                            # Check if price has changed before updating
                            old_amount = existing_sub.amount
                            new_amount = subscription_data.get('amount')
                            price_changed = (
                                old_amount is not None and
                                new_amount is not None and
                                float(old_amount) != float(new_amount)
                            )

                            # Update existing subscription
                            for key, value in subscription_data.items():
                                setattr(existing_sub, key, value)
                            existing_sub.updated_at = datetime.now(timezone.utc)
                            subscription_record = existing_sub
                            subscriptions_updated += 1

                            # Create price history record if price changed
                            if price_changed:
                                change_percentage = ((float(new_amount) - float(old_amount)) / float(old_amount)) * 100
                                change_type = 'increase' if float(new_amount) > float(old_amount) else 'decrease'

                                price_history_record = PriceHistory(
                                    subscription_id=existing_sub.id,
                                    old_amount=old_amount,
                                    new_amount=new_amount,
                                    currency=subscription_data.get('currency', 'EUR'),
                                    change_type=change_type,
                                    change_percentage=round(change_percentage, 2),
                                    detected_from='email',
                                    notes=f"Price change detected from email: {email.subject}"
                                )
                                db.add(price_history_record)
                                logger.info(f"Price change detected for {subscription_data['provider']}: €{old_amount} -> €{new_amount} ({change_type} of {abs(change_percentage):.1f}%)")
                            else:
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

                            # Create initial price history record
                            if subscription_data.get('amount') is not None:
                                initial_price_history = PriceHistory(
                                    subscription_id=new_subscription.id,
                                    old_amount=None,  # No previous price for initial record
                                    new_amount=subscription_data['amount'],
                                    currency=subscription_data.get('currency', 'EUR'),
                                    change_type='initial',
                                    change_percentage=None,  # No percentage for initial record
                                    detected_from='email',
                                    notes=f"Initial price detected from email: {email.subject}"
                                )
                                db.add(initial_price_history)
                                logger.info(f"Created initial price history for {subscription_data['provider']}: €{subscription_data['amount']}")

                        # Calculate accurate renewal date and active status
                        if subscription_record:
                            try:
                                # Flush to ensure we can query for subscription emails
                                db.flush()

                                # Get all emails for this subscription
                                subscription_emails_data = get_subscription_emails(db, subscription_record.id)

                                if subscription_emails_data:
                                    # Extract dates and contents
                                    email_dates = [e['date'] for e in subscription_emails_data]
                                    email_contents = [
                                        e['body_html'] or e['body_text'] or ''
                                        for e in subscription_emails_data
                                    ]

                                    # Initialize renewal calculator
                                    renewal_calc = RenewalCalculator(db)

                                    # Calculate renewal date, active status, trial status, and confirmation
                                    renewal_date, is_active, trial_status, is_confirmed = renewal_calc.calculate_renewal_info(
                                        provider=subscription_record.provider,
                                        billing_cycle=subscription_record.billing_cycle,
                                        email_dates=email_dates,
                                        email_contents=email_contents,
                                        extraction_metadata=subscription_record.extraction_metadata
                                    )

                                    # Update subscription with calculated values
                                    if renewal_date:
                                        subscription_record.renewal_date = renewal_date
                                        logger.info(f"Calculated renewal date for {subscription_record.provider}: {renewal_date.strftime('%Y-%m-%d')}")

                                    subscription_record.is_active = is_active
                                    subscription_record.trial_status = trial_status
                                    subscription_record.is_confirmed = is_confirmed
                                    logger.info(f"Set status for {subscription_record.provider}: active={is_active}, trial={trial_status}, confirmed={is_confirmed}")

                                    # Detect if this is a reactivation
                                    is_reactivation = renewal_calc.detect_reactivation(
                                        email_dates=email_dates,
                                        billing_cycle=subscription_record.billing_cycle
                                    )

                                    if is_reactivation:
                                        logger.info(f"Reactivation detected for {subscription_record.provider}")

                            except Exception as e:
                                logger.error(f"Error calculating renewal date for {subscription_record.provider}: {str(e)}")
                                # Continue with subscription creation even if renewal calculation fails

                        # Check for cancellation category and create suggestion
                        if subscription_record and email_record:
                            try:
                                classification = email_record.classification_reasoning or {}
                                category = classification.get('category', '')

                                if category == 'cancellation':
                                    # Only create suggestion if no existing suggestion is pending
                                    if not subscription_record.suggested_cancellation_status:
                                        subscription_record.suggested_cancellation_status = 'cancelled'
                                        subscription_record.cancellation_suggestion_reason = classification.get('reasoning', 'AI detected a cancellation email')
                                        subscription_record.cancellation_suggestion_created_at = datetime.now(timezone.utc)
                                        logger.info(f"Created cancellation suggestion for {subscription_record.provider}: {classification.get('reasoning', 'No reason')}")
                                    else:
                                        logger.info(f"Cancellation suggestion already exists for {subscription_record.provider}, skipping")
                            except Exception as e:
                                logger.error(f"Error creating cancellation suggestion for {subscription_record.provider}: {str(e)}")
                                # Continue even if suggestion creation fails

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

            # Update sync progress in database (Issue #7: Sync resume capability)
            # Persist position and batch_num so sync can resume if interrupted
            mailbox.last_sync_emails_processed = total_emails_processed
            mailbox.last_sync_subscriptions_found = subscriptions_found
            mailbox.last_sync_position = position
            mailbox.last_sync_batch_num = batch_num

            # Update real-time progress tracking (Issue #10)
            # Estimate total batches based on has_more flag
            # If has_more=True, we estimate at least 2 more batches, otherwise this is the last
            estimated_remaining_batches = 2 if has_more else 0
            total_batches_estimate = batch_num + estimated_remaining_batches

            # Calculate progress percentage
            progress_percentage = (batch_num / total_batches_estimate * 100) if total_batches_estimate > 0 else 100.0

            # Calculate estimated completion time based on average batch duration
            elapsed_time = datetime.now(timezone.utc) - sync_start_time
            avg_time_per_batch = elapsed_time.total_seconds() / batch_num if batch_num > 0 else 0
            estimated_remaining_seconds = avg_time_per_batch * estimated_remaining_batches
            estimated_completion_time = datetime.now(timezone.utc) + timedelta(seconds=estimated_remaining_seconds) if has_more else None

            # Update progress fields
            mailbox.current_batch_number = batch_num
            mailbox.total_batches_estimate = total_batches_estimate
            mailbox.progress_percentage = min(progress_percentage, 99.0)  # Cap at 99% until actually done
            mailbox.estimated_completion_time = estimated_completion_time

            db.commit()

            # Check for user-initiated cancellation after each batch
            db.refresh(mailbox)
            if mailbox.sync_cancellation_requested:
                logger.info(f"Sync cancellation requested by user at batch {batch_num}. Stopping gracefully.")
                mailbox.last_sync_status = 'cancelled'
                mailbox.sync_cancelled_at = datetime.now(timezone.utc)
                mailbox.sync_cancellation_requested = False  # Reset flag

                # Update history entry for cancellation (Issue #11)
                history_entry.status = 'cancelled'
                history_entry.completed_at = datetime.now(timezone.utc)
                history_entry.duration_seconds = int((history_entry.completed_at - history_entry.started_at).total_seconds())
                history_entry.total_emails_processed = total_emails_processed
                history_entry.subscriptions_found = subscriptions_found
                history_entry.subscriptions_updated = subscriptions_updated
                history_entry.batches_processed = batch_num
                history_entry.final_position = position
                history_entry.final_batch_number = batch_num
                history_entry.final_progress_percentage = mailbox.progress_percentage

                db.commit()

                # Break out of the loop gracefully - progress is already saved
                return {
                    "success": True,
                    "cancelled": True,
                    "total_emails_processed": total_emails_processed,
                    "subscriptions_found": subscriptions_found,
                    "subscriptions_updated": subscriptions_updated,
                    "message": f"Sync cancelled by user at batch {batch_num}"
                }

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


@celery_app.task(
    base=DatabaseTask,
    bind=True,
    name="app.tasks.email_sync.sync_mailbox_emails",
    autoretry_for=(Exception,),  # Retry on any exception
    retry_kwargs={'max_retries': 3, 'countdown': 60},  # 3 retries with 60s initial delay
    retry_backoff=True,  # Exponential backoff (60s, 120s, 240s)
    retry_backoff_max=300,  # Max 5 minutes between retries
    retry_jitter=True  # Add randomness to avoid thundering herd
)
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

    # Check for sync resume capability (Issue #7)
    # If there's a recent in_progress or cancelled sync (< 1 hour old), resume from last position
    resume_position = 0
    resume_batch_num = 0
    is_resuming = False

    if mailbox.last_sync_status in ('in_progress', 'cancelled') and mailbox.last_sync_started_at:
        time_since_start = datetime.now(timezone.utc) - mailbox.last_sync_started_at.replace(tzinfo=timezone.utc)

        if time_since_start.total_seconds() < 3600:  # Less than 1 hour old
            # Resume from last position
            resume_position = mailbox.last_sync_position or 0
            resume_batch_num = mailbox.last_sync_batch_num or 0
            is_resuming = True
            resume_reason = "cancelled by user" if mailbox.last_sync_status == 'cancelled' else "interrupted"
            logger.info(
                f"Resuming sync from position {resume_position}, batch {resume_batch_num} "
                f"(was {resume_reason}, started {time_since_start.total_seconds():.0f}s ago)"
            )
        else:
            # Stale sync - restart from beginning
            logger.warning(
                f"Found stale {mailbox.last_sync_status} sync (started {time_since_start.total_seconds()/3600:.1f}h ago), "
                f"restarting from beginning"
            )

    # Set status to in_progress and update sync start time
    # For resuming syncs, use the original start time; for fresh syncs, use current time
    if is_resuming and mailbox.last_sync_started_at:
        sync_start_time = mailbox.last_sync_started_at.replace(tzinfo=timezone.utc)
        logger.info(f"Using original sync start time: {sync_start_time}")
    else:
        sync_start_time = datetime.now(timezone.utc)
        mailbox.last_sync_status = 'in_progress'
        mailbox.last_sync_started_at = sync_start_time
        mailbox.last_sync_position = 0
        mailbox.last_sync_batch_num = 0
    mailbox.last_sync_error_message = None
    db.commit()

    # Create sync history entry (Issue #11)
    history_entry = SyncHistory(
        mailbox_id=mailbox.id,
        started_at=sync_start_time,
        status='in_progress',
        sync_type='full' if force_full_sync else 'incremental',
        date_filter_used=date_filter or mailbox.import_date_filter,
        batch_size_used=mailbox.batch_size,
        was_resumed=is_resuming,
        resumed_from_position=resume_position if is_resuming else None,
        resumed_from_batch=resume_batch_num if is_resuming else None
    )
    db.add(history_entry)
    db.commit()
    logger.info(f"Created sync history entry: {history_entry.id}")

    try:
        # Run async sync logic with resume position and sync start time
        result = asyncio.run(_sync_mailbox_async(
            db, mailbox, force_full_sync, date_filter,
            resume_position=resume_position,
            resume_batch_num=resume_batch_num,
            sync_start_time=sync_start_time,
            history_entry=history_entry
        ))

        # Update mailbox sync status with metrics
        completion_time = datetime.now(timezone.utc)
        mailbox.last_sync_at = completion_time
        mailbox.last_sync_status = 'success' if result['success'] else 'failed'

        if result['success']:
            # Update metrics on success
            mailbox.last_sync_emails_processed = result.get('total_emails_processed', 0)
            mailbox.last_sync_subscriptions_found = result.get('subscriptions_found', 0) + result.get('subscriptions_updated', 0)
            mailbox.last_sync_error_message = None

            # Clear sync resume fields on successful completion (Issue #7)
            mailbox.last_sync_position = 0
            mailbox.last_sync_batch_num = 0
            mailbox.last_sync_started_at = None

            # Clear progress tracking fields on completion (Issue #10)
            mailbox.current_batch_number = None
            mailbox.total_batches_estimate = None
            mailbox.progress_percentage = 100.0  # Set to 100% on completion
            mailbox.estimated_completion_time = None

            # Update history entry for successful completion (Issue #11)
            history_entry.status = 'completed'
            history_entry.completed_at = completion_time
            history_entry.duration_seconds = int((completion_time - history_entry.started_at.replace(tzinfo=timezone.utc)).total_seconds())
            history_entry.total_emails_processed = result.get('total_emails_processed', 0)
            history_entry.subscriptions_found = result.get('subscriptions_found', 0)
            history_entry.subscriptions_updated = result.get('subscriptions_updated', 0)
            history_entry.batches_processed = mailbox.last_sync_batch_num or 0
            history_entry.final_position = mailbox.last_sync_position or 0
            history_entry.final_batch_number = mailbox.last_sync_batch_num or 0
            history_entry.final_progress_percentage = 100.0

            # Update subscription active/inactive status based on last confirmation dates
            status_update = update_subscription_statuses(db, mailbox.id)
            logger.info(f"Subscription status update: {status_update['activated']} activated, {status_update['deactivated']} deactivated")
        else:
            # Store error message on failure
            error_msg = result.get('error', 'Unknown error')
            mailbox.last_sync_error_message = error_msg

            # Update history entry for failure (Issue #11)
            history_entry.status = 'failed'
            history_entry.completed_at = completion_time
            history_entry.duration_seconds = int((completion_time - history_entry.started_at.replace(tzinfo=timezone.utc)).total_seconds())
            history_entry.total_emails_processed = result.get('total_emails_processed', 0)
            history_entry.subscriptions_found = result.get('subscriptions_found', 0)
            history_entry.subscriptions_updated = result.get('subscriptions_updated', 0)
            history_entry.error_message = error_msg
            history_entry.error_type = result.get('error_type', 'sync_error')

        db.commit()

        result.update({
            "mailbox_id": mailbox_id,
            "sync_timestamp": datetime.now(timezone.utc).isoformat()
        })

        logger.info(f"Email sync completed for mailbox {mailbox_id}: {result}")
        return result

    except Exception as e:
        logger.error(f"Email sync failed for mailbox {mailbox_id}: {str(e)}")
        exception_time = datetime.now(timezone.utc)
        mailbox.last_sync_status = 'failed'
        mailbox.last_sync_at = exception_time
        mailbox.last_sync_error_message = str(e)

        # Update history entry for exception (Issue #11)
        history_entry.status = 'failed'
        history_entry.completed_at = exception_time
        history_entry.duration_seconds = int((exception_time - history_entry.started_at.replace(tzinfo=timezone.utc)).total_seconds())
        history_entry.error_message = str(e)
        history_entry.error_type = type(e).__name__
        history_entry.total_emails_processed = mailbox.last_sync_emails_processed or 0
        history_entry.subscriptions_found = mailbox.last_sync_subscriptions_found or 0
        history_entry.batches_processed = mailbox.last_sync_batch_num or 0

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

        if sub.manual_status_override:
            # Skip subscriptions with manual status override - user has manually set the status
            continue

        # Get grace period for this billing cycle (default to 60 days if unknown)
        billing_cycle_lower = sub.billing_cycle.lower()
        grace_days = GRACE_PERIODS.get(billing_cycle_lower, 60)

        # Calculate cutoff date
        cutoff_date = now - timedelta(days=grace_days)

        # Normalize timezone before comparison (SQLite returns timezone-naive datetimes)
        last_confirmed = sub.last_confirmed_at
        if last_confirmed.tzinfo is None:
            last_confirmed = last_confirmed.replace(tzinfo=timezone.utc)

        # Check if subscription should be active
        should_be_active = last_confirmed >= cutoff_date

        # Update status if it changed
        if should_be_active and not sub.is_active:
            sub.is_active = True
            activated_count += 1
            logger.info(f"Activated subscription: {sub.provider} (last confirmed: {last_confirmed})")
        elif not should_be_active and sub.is_active:
            sub.is_active = False
            deactivated_count += 1
            logger.info(f"Deactivated subscription: {sub.provider} (last confirmed: {last_confirmed}, cutoff: {cutoff_date})")

    if activated_count > 0 or deactivated_count > 0:
        db.commit()
        logger.info(f"Subscription status update: {activated_count} activated, {deactivated_count} deactivated")

    return {
        "activated": activated_count,
        "deactivated": deactivated_count
    }


def parse_date_filter(filter_str: str, db: Session = None) -> datetime:
    """
    Parse date filter string into datetime.

    Supported formats:
    - '30days', '60days', '90days', '365days'
    - '1month', '3months', '6months', '12months'
    - '1year', '2years'

    Args:
        filter_str: Date filter string
        db: Optional database session for admin config lookup
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
        # Use configurable default sync period (admin panel or env)
        default_days = get_config_value('email.default_sync_period_days', settings.DEFAULT_SYNC_PERIOD_DAYS, db)
        return now - timedelta(days=default_days)
