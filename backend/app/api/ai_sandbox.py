"""
AI Sandbox API endpoints for testing and reviewing email classification/extraction.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.email_message import EmailMessage
from app.models.subscription import Subscription
from app.models.mailbox import Mailbox
from app.schemas.ai_sandbox import (
    EmailTestRequest,
    ClassificationTestResponse,
    ExtractionTestResponse,
    UncertainEmailsResponse,
    UncertainEmail,
    EmailDetailResponse,
    ManualSubscriptionCreate,
    BulkMarkNotSubscriptionRequest,
    BulkMarkNotSubscriptionResponse,
)
from app.security.dependencies import get_current_user
from app.services.ai_classifier import classify_email
from app.services.subscription_extractor import extract_subscription_data
from app.email_providers.base import EmailMessage as EmailMessageModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/test-classification", response_model=ClassificationTestResponse)
async def test_email_classification(
    request: EmailTestRequest, current_user: User = Depends(get_current_user)
):
    """
    Test email classification without saving to database.
    Useful for debugging and improving classification prompts.
    """
    try:
        # Create a temporary EmailMessage object for classification
        temp_email = EmailMessageModel(
            id=request.sender,  # Use sender as temp ID
            subject=request.subject,
            sender=request.sender,
            sender_name=request.sender_name,
            recipients=[],
            date=request.date or datetime.now(timezone.utc),
            body_text=request.body_text,
            body_html=request.body_html,
            headers={},
            folder=None,
        )

        # Run classification
        result = await classify_email(temp_email)

        return ClassificationTestResponse(
            is_subscription=result.get("is_subscription", False),
            confidence=result.get("confidence", 0.0),
            reasoning=result.get("reasoning", "No reasoning provided"),
            category=result.get("category", "not_subscription"),
        )

    except Exception as e:
        logger.error(f"Classification test failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification test failed: {str(e)}",
        )


@router.post("/test-extraction", response_model=ExtractionTestResponse)
async def test_email_extraction(
    request: EmailTestRequest, current_user: User = Depends(get_current_user)
):
    """
    Test subscription data extraction without saving to database.
    Useful for debugging and improving extraction prompts.
    """
    try:
        # Create a temporary EmailMessage object for extraction
        temp_email = EmailMessageModel(
            id=request.sender,
            subject=request.subject,
            sender=request.sender,
            sender_name=request.sender_name,
            recipients=[],
            date=request.date or datetime.now(timezone.utc),
            body_text=request.body_text,
            body_html=request.body_html,
            headers={},
            folder=None,
        )

        # Run extraction
        result = await extract_subscription_data(temp_email)

        if not result:
            return ExtractionTestResponse(
                provider=None,
                amount=None,
                currency=None,
                billing_cycle=None,
                renewal_date=None,
                custom_label=None,
                category="other",
                confidence_score=0.0,
                extraction_method="gpt-4o-mini",
                raw_response=None,
            )

        return ExtractionTestResponse(
            provider=result.get("provider"),
            amount=result.get("amount"),
            currency=result.get("currency"),
            billing_cycle=result.get("billing_cycle"),
            renewal_date=(
                result.get("renewal_date").isoformat()
                if result.get("renewal_date")
                else None
            ),
            custom_label=result.get("custom_label"),
            category=result.get("category", "other"),
            confidence_score=result.get("confidence_score", 0.0),
            extraction_method=result.get("extraction_method", "gpt-4o-mini"),
            raw_response=result,
        )

    except Exception as e:
        logger.error(f"Extraction test failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction test failed: {str(e)}",
        )


@router.get("/uncertain-emails", response_model=UncertainEmailsResponse)
async def get_uncertain_emails(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=100),
):
    """
    Get emails that need manual review:
    - Classified as subscription but low confidence (< 0.8)
    - Classified as subscription but no subscription created
    - Subscriptions with missing data (amount = null)

    Args:
        limit: Number of results to return (1-100, default 50)
        search: Optional search term to filter by sender, sender_name, or subject (max 100 chars, case-insensitive)

    Security:
        - Input validation: search limited to 100 chars, limit capped at 100
        - SQL injection protection: parameterized queries with escaped wildcards
        - Authorization: filtered by current_user's mailboxes only
    """
    try:
        # Get user's mailbox IDs
        mailbox_ids = (
            db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        )
        mailbox_ids = [m[0] for m in mailbox_ids]

        if not mailbox_ids:
            return UncertainEmailsResponse(
                emails=[], total=0, uncertain_classified=0, extraction_failed=0
            )

        # Build base query for uncertain emails
        filter_conditions = [
            EmailMessage.mailbox_id.in_(mailbox_ids),
            EmailMessage.is_subscription,
            or_(
                EmailMessage.classification_confidence < 0.8,  # Low confidence
                EmailMessage.id.notin_(  # No subscription created
                    db.query(EmailMessage.id)
                    .join(EmailMessage.subscriptions)
                    .filter(EmailMessage.mailbox_id.in_(mailbox_ids))
                ),
            ),
        ]

        # Add search filter if provided with proper sanitization
        if search:
            # Strip whitespace and validate
            search = search.strip()
            if search:
                # Escape SQL wildcards to prevent wildcard injection attacks
                # This prevents queries like "%_%_%_%_" from causing performance issues
                search_escaped = (
                    search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                )
                search_term = f"%{search_escaped}%"

                filter_conditions.append(
                    or_(
                        EmailMessage.sender.ilike(search_term, escape="\\"),
                        EmailMessage.sender_name.ilike(search_term, escape="\\"),
                        EmailMessage.subject.ilike(search_term, escape="\\"),
                    )
                )

        base_filter = and_(*filter_conditions)

        # Get total count of all uncertain emails
        total_count = db.query(func.count(EmailMessage.id)).filter(base_filter).scalar()

        # Get limited results for display
        query = (
            db.query(EmailMessage)
            .filter(base_filter)
            .order_by(EmailMessage.date.desc())
            .limit(limit)
        )
        emails = query.all()

        # Count different types of uncertain emails from returned results
        uncertain_classified = sum(
            1 for e in emails if e.classification_confidence < 0.8
        )
        extraction_failed = sum(1 for e in emails if not e.subscriptions)

        # Convert to response schema
        uncertain_emails = []
        for email in emails:
            # Get first 200 chars for preview
            body = email.body_text or email.body_html or ""
            preview = body[:200] + "..." if len(body) > 200 else body

            uncertain_emails.append(
                UncertainEmail(
                    id=str(email.id),
                    subject=email.subject,
                    sender=email.sender,
                    sender_name=email.sender_name,
                    date=email.date,
                    classification_confidence=email.classification_confidence or 0.0,
                    is_subscription=email.is_subscription,
                    has_linked_subscription=len(email.subscriptions) > 0,
                    preview=preview,
                )
            )

        return UncertainEmailsResponse(
            emails=uncertain_emails,
            total=total_count,
            uncertain_classified=uncertain_classified,
            extraction_failed=extraction_failed,
        )

    except Exception as e:
        logger.error(f"Failed to get uncertain emails: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get uncertain emails: {str(e)}",
        )


@router.get("/email/{email_id}", response_model=EmailDetailResponse)
async def get_email_detail(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information about a specific email for review."""
    try:
        # Get user's mailbox IDs for security
        mailbox_ids = (
            db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        )
        mailbox_ids = [m[0] for m in mailbox_ids]

        # Get email
        email = (
            db.query(EmailMessage)
            .filter(
                and_(
                    EmailMessage.id == email_id,
                    EmailMessage.mailbox_id.in_(mailbox_ids),
                )
            )
            .first()
        )

        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
            )

        # Check if email has linked subscription
        linked_subscription_id = None
        if email.subscriptions:
            linked_subscription_id = str(email.subscriptions[0].id)

        return EmailDetailResponse(
            id=str(email.id),
            subject=email.subject,
            sender=email.sender,
            sender_name=email.sender_name,
            recipient=email.recipient,
            date=email.date,
            body_text=email.body_text,
            body_html=email.body_html,
            is_subscription=email.is_subscription,
            classification_confidence=email.classification_confidence or 0.0,
            classification_reasoning=email.classification_reasoning,
            has_linked_subscription=len(email.subscriptions) > 0,
            linked_subscription_id=linked_subscription_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get email detail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get email detail: {str(e)}",
        )


@router.post("/create-subscription")
async def create_subscription_from_email(
    request: ManualSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually create a subscription from an email after review.
    Useful for emails with missing data or uncertain classification.
    """
    try:
        # Get user's mailbox IDs for security
        mailbox_ids = (
            db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        )
        mailbox_ids = [m[0] for m in mailbox_ids]

        # Get email
        email = (
            db.query(EmailMessage)
            .filter(
                and_(
                    EmailMessage.id == UUID(request.email_id),
                    EmailMessage.mailbox_id.in_(mailbox_ids),
                )
            )
            .first()
        )

        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
            )

        # Check if subscription already exists
        existing_sub = db.query(Subscription).filter(
            and_(
                Subscription.mailbox_id == email.mailbox_id,
                Subscription.provider == request.provider,
            )
        )

        # Add custom_label to uniqueness check if present
        if request.custom_label:
            existing_sub = existing_sub.filter(
                Subscription.custom_label == request.custom_label
            )
        else:
            existing_sub = existing_sub.filter(Subscription.custom_label.is_(None))

        existing_sub = existing_sub.first()

        if existing_sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription already exists",
            )

        # Create new subscription
        new_subscription = Subscription(
            user_id=current_user.id,
            mailbox_id=email.mailbox_id,
            provider=request.provider,
            amount=request.amount,
            currency=request.currency,
            billing_cycle=request.billing_cycle,
            renewal_date=request.renewal_date,
            custom_label=request.custom_label,
            category=request.category,
            notes=request.notes,
            email_sender=email.sender,
            confidence_score=1.0,  # Manual creation = high confidence
            extraction_method="manual",
        )
        db.add(new_subscription)
        db.flush()  # Get subscription ID without committing yet

        # Link email to subscription
        new_subscription.source_emails.append(email)

        # Update email classification to mark it as a subscription
        email.is_subscription = True
        email.classification_confidence = 1.0  # Manual confirmation = high confidence

        # Add user feedback to reasoning
        if email.classification_reasoning:
            email.classification_reasoning["user_feedback"] = (
                "confirmed_as_subscription"
            )
            email.classification_reasoning["feedback_date"] = datetime.now(
                timezone.utc
            ).isoformat()

        db.commit()
        db.refresh(new_subscription)

        logger.info(
            f"Manually created subscription: {request.provider} from email {request.email_id}"
        )

        return {
            "success": True,
            "subscription_id": str(new_subscription.id),
            "message": "Subscription created successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subscription: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subscription: {str(e)}",
        )


@router.post("/mark-not-subscription/{email_id}")
async def mark_email_not_subscription(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark an email as NOT a subscription (user feedback).
    This helps clean up the uncertain emails list and provides feedback for AI improvement.
    """
    try:
        # Get user's mailbox IDs for security
        mailbox_ids = (
            db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        )
        mailbox_ids = [m[0] for m in mailbox_ids]

        # Get email
        email = (
            db.query(EmailMessage)
            .filter(
                and_(
                    EmailMessage.id == email_id,
                    EmailMessage.mailbox_id.in_(mailbox_ids),
                )
            )
            .first()
        )

        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Email not found"
            )

        # Update classification
        email.is_subscription = False
        email.classification_confidence = 0.0

        # Add user feedback to reasoning
        if email.classification_reasoning:
            email.classification_reasoning["user_feedback"] = (
                "marked_as_not_subscription"
            )
            email.classification_reasoning["feedback_date"] = datetime.now(
                timezone.utc
            ).isoformat()

        db.commit()

        logger.info(
            f"Email {email_id} marked as not a subscription by user {current_user.id}"
        )

        return {"success": True, "message": "Email marked as not a subscription"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark email as not subscription: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark email: {str(e)}",
        )


@router.post(
    "/bulk-mark-not-subscription", response_model=BulkMarkNotSubscriptionResponse
)
async def bulk_mark_not_subscription(
    request: BulkMarkNotSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark multiple emails as NOT subscriptions in bulk (user feedback).
    This helps efficiently clean up the uncertain emails list.
    """
    try:
        # Get user's mailbox IDs for security
        mailbox_ids = (
            db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        )
        mailbox_ids = [m[0] for m in mailbox_ids]

        processed = 0
        failed = 0
        errors = []

        # Process each email
        for email_id_str in request.email_ids:
            try:
                email_id = UUID(email_id_str)

                # Get email
                email = (
                    db.query(EmailMessage)
                    .filter(
                        and_(
                            EmailMessage.id == email_id,
                            EmailMessage.mailbox_id.in_(mailbox_ids),
                        )
                    )
                    .first()
                )

                if not email:
                    failed += 1
                    errors.append(f"Email {email_id_str} not found")
                    continue

                # Update classification
                email.is_subscription = False
                email.classification_confidence = 0.0

                # Add user feedback to reasoning
                if email.classification_reasoning:
                    email.classification_reasoning["user_feedback"] = (
                        "bulk_marked_as_not_subscription"
                    )
                    email.classification_reasoning["feedback_date"] = datetime.now(
                        timezone.utc
                    ).isoformat()

                processed += 1

            except ValueError:
                failed += 1
                errors.append(f"Invalid email ID: {email_id_str}")
            except Exception as e:
                failed += 1
                errors.append(f"Failed to process {email_id_str}: {str(e)}")

        # Commit all changes
        db.commit()

        logger.info(
            f"Bulk marked {processed} emails as not subscriptions by user {current_user.id}"
        )

        return BulkMarkNotSubscriptionResponse(
            success=True, processed=processed, failed=failed, errors=errors
        )

    except Exception as e:
        logger.error(f"Bulk mark not subscription failed: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk operation failed: {str(e)}",
        )
