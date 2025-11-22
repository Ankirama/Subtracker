"""
API endpoints for cancellation feedback and metrics.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, case, desc, String
from typing import List
from uuid import UUID
import logging
import json

from app.database import get_db
from app.models.user import User
from app.models.cancellation_feedback import CancellationFeedback, FeedbackType
from app.models.provider_cancellation import ProviderCancellationInfo
from app.schemas.feedback import (
    FeedbackSubmission,
    FeedbackResponse,
    QuickFeedback,
    DashboardMetrics,
    ValidationMetrics,
    ProviderMetrics
)
from app.security import get_current_user

router = APIRouter(prefix="/feedback", tags=["feedback"])
logger = logging.getLogger(__name__)


@router.post("/submit", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    feedback: FeedbackSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback on cancellation instructions.

    Users can rate helpfulness, accuracy, and report success/failure.
    """
    try:
        # Get the provider cancellation info
        provider_info = db.execute(
            select(ProviderCancellationInfo).where(
                ProviderCancellationInfo.id == feedback.provider_cancellation_id
            )
        ).scalar_one_or_none()

        if not provider_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider cancellation info not found"
            )

        # Extract AI metadata from stored response
        ai_response = json.loads(provider_info.ai_research_response) if provider_info.ai_research_response else {}

        # Create feedback record
        feedback_record = CancellationFeedback(
            user_id=current_user.id,
            provider_cancellation_id=feedback.provider_cancellation_id,
            provider_name=provider_info.provider_name,
            feedback_type=FeedbackType(feedback.feedback_type),
            successfully_cancelled=feedback.successfully_cancelled,
            time_taken_minutes=feedback.time_taken_minutes,
            helpfulness_rating=feedback.helpfulness_rating,
            accuracy_rating=feedback.accuracy_rating,
            comment=feedback.comment,
            issues_encountered=feedback.issues_encountered,
            ai_confidence_at_feedback=provider_info.ai_confidence_score,
            validation_quality_at_feedback=ai_response.get("validation_quality_score"),
            prompt_version_at_feedback=ai_response.get("prompt_version", "v1_baseline"),
            device_type=feedback.device_type
        )

        db.add(feedback_record)
        db.commit()
        db.refresh(feedback_record)

        logger.info(
            f"User {current_user.id} submitted feedback for {provider_info.provider_name}: "
            f"{feedback.feedback_type} (success={feedback.successfully_cancelled})"
        )

        return FeedbackResponse.model_validate(feedback_record)

    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback"
        )


@router.post("/quick", status_code=status.HTTP_201_CREATED)
async def quick_feedback(
    feedback: QuickFeedback,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Quick thumbs up/down feedback (simplified version)"""
    submission = FeedbackSubmission(
        provider_cancellation_id=feedback.provider_cancellation_id,
        feedback_type="helpful" if feedback.was_helpful else "not_helpful",
        comment=feedback.comment
    )

    return await submit_feedback(submission, current_user, db)


@router.get("/my-feedback", response_model=List[FeedbackResponse])
async def get_my_feedback(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20
):
    """Get current user's feedback history"""
    stmt = (
        select(CancellationFeedback)
        .where(CancellationFeedback.user_id == current_user.id)
        .order_by(desc(CancellationFeedback.created_at))
        .limit(limit)
    )

    feedback_records = db.execute(stmt).scalars().all()
    return [FeedbackResponse.model_validate(f) for f in feedback_records]


@router.get("/metrics/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard metrics.

    Admin-only endpoint for monitoring AI prompt performance.
    """
    # TODO: Add admin role check when implemented
    # For now, any authenticated user can access

    try:
        # Get provider metrics
        provider_metrics = await _get_provider_metrics(db)

        # Calculate overall metrics
        total_feedback = db.execute(
            select(func.count(CancellationFeedback.id))
        ).scalar() or 0

        # Calculate success rates by confidence level
        high_confidence_threshold = 0.7

        # High confidence success rate
        high_conf_total = db.execute(
            select(func.count(CancellationFeedback.id))
            .where(
                and_(
                    CancellationFeedback.ai_confidence_at_feedback >= high_confidence_threshold,
                    CancellationFeedback.successfully_cancelled.isnot(None)
                )
            )
        ).scalar() or 0

        high_conf_success = db.execute(
            select(func.count(CancellationFeedback.id))
            .where(
                and_(
                    CancellationFeedback.ai_confidence_at_feedback >= high_confidence_threshold,
                    CancellationFeedback.successfully_cancelled == True
                )
            )
        ).scalar() or 0

        high_confidence_success_rate = (
            float(high_conf_success) / float(high_conf_total) if high_conf_total > 0 else None
        )

        # Low confidence success rate
        low_conf_total = db.execute(
            select(func.count(CancellationFeedback.id))
            .where(
                and_(
                    CancellationFeedback.ai_confidence_at_feedback < high_confidence_threshold,
                    CancellationFeedback.successfully_cancelled.isnot(None)
                )
            )
        ).scalar() or 0

        low_conf_success = db.execute(
            select(func.count(CancellationFeedback.id))
            .where(
                and_(
                    CancellationFeedback.ai_confidence_at_feedback < high_confidence_threshold,
                    CancellationFeedback.successfully_cancelled == True
                )
            )
        ).scalar() or 0

        low_confidence_success_rate = (
            float(low_conf_success) / float(low_conf_total) if low_conf_total > 0 else None
        )

        # Get providers needing update (low success rate or poor ratings)
        providers_needing_update = [
            pm.provider_name for pm in provider_metrics
            if (pm.success_rate is not None and pm.success_rate < 0.7) or
               (pm.avg_helpfulness is not None and pm.avg_helpfulness < 3.0) or
               (pm.avg_accuracy is not None and pm.avg_accuracy < 3.0)
        ]

        overall_metrics = ValidationMetrics(
            total_feedback=total_feedback,
            high_confidence_success_rate=high_confidence_success_rate,
            low_confidence_success_rate=low_confidence_success_rate,
            providers_needing_update=providers_needing_update
        )

        return DashboardMetrics(
            overall_metrics=overall_metrics,
            provider_metrics=provider_metrics
        )

    except Exception as e:
        logger.error(f"Failed to get dashboard metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


async def _get_validation_metrics(db: Session) -> ValidationMetrics:
    """Calculate validation metrics from stored research results"""

    # Get all provider cancellation info with AI research
    providers = db.execute(
        select(ProviderCancellationInfo)
        .where(ProviderCancellationInfo.ai_research_response.isnot(None))
    ).scalars().all()

    if not providers:
        return ValidationMetrics(
            total_researched=0,
            avg_quality_score=0.0,
            avg_confidence_score=0.0,
            quality_distribution={},
            confidence_distribution={},
            warning_frequency={},
            prompt_version_stats={},
            top_providers_by_quality=[],
            providers_needing_update=[]
        )

    # Extract metrics from stored responses
    quality_scores = []
    confidence_scores = []
    warning_counts = {"high": 0, "medium": 0, "low": 0}
    prompt_versions = {}
    provider_stats = []

    for provider in providers:
        try:
            response_data = json.loads(provider.ai_research_response)

            quality = response_data.get("validation_quality_score")
            confidence = provider.ai_confidence_score or response_data.get("confidence", 0)
            version = response_data.get("prompt_version", "v1_baseline")

            if quality is not None:
                quality_scores.append(quality)
            if confidence is not None:
                confidence_scores.append(confidence)

            # Count warnings
            warnings = response_data.get("validation_warnings", {})
            if isinstance(warnings, dict):
                warning_counts["high"] += warnings.get("high", 0)
                warning_counts["medium"] += warnings.get("medium", 0)
                warning_counts["low"] += warnings.get("low", 0)

            # Track prompt version stats
            if version not in prompt_versions:
                prompt_versions[version] = {
                    "count": 0,
                    "avg_quality": 0,
                    "avg_confidence": 0,
                    "quality_scores": [],
                    "confidence_scores": []
                }

            prompt_versions[version]["count"] += 1
            if quality is not None:
                prompt_versions[version]["quality_scores"].append(quality)
            if confidence is not None:
                prompt_versions[version]["confidence_scores"].append(confidence)

            # Track provider stats
            provider_stats.append({
                "name": provider.provider_name,
                "quality": quality or 0,
                "confidence": confidence or 0
            })

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse research response for {provider.provider_name}: {e}")
            continue

    # Calculate averages for prompt versions
    for version, stats in prompt_versions.items():
        if stats["quality_scores"]:
            stats["avg_quality"] = sum(stats["quality_scores"]) / len(stats["quality_scores"])
        if stats["confidence_scores"]:
            stats["avg_confidence"] = sum(stats["confidence_scores"]) / len(stats["confidence_scores"])

        # Remove score arrays from response (too large)
        del stats["quality_scores"]
        del stats["confidence_scores"]

    # Create distributions
    quality_dist = _create_distribution(quality_scores)
    confidence_dist = _create_distribution(confidence_scores)

    # Sort providers
    top_providers = sorted(provider_stats, key=lambda x: x["quality"], reverse=True)[:10]
    needs_update = [p for p in provider_stats if p["quality"] < 0.6 or p["confidence"] < 0.5][:10]

    return ValidationMetrics(
        total_researched=len(providers),
        avg_quality_score=round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else 0.0,
        avg_confidence_score=round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else 0.0,
        quality_distribution=quality_dist,
        confidence_distribution=confidence_dist,
        warning_frequency=warning_counts,
        prompt_version_stats=prompt_versions,
        top_providers_by_quality=top_providers,
        providers_needing_update=needs_update
    )


async def _get_provider_metrics(db: Session) -> List[ProviderMetrics]:
    """Calculate per-provider metrics from feedback"""

    # Get feedback grouped by provider
    feedback_by_provider = db.execute(
        select(
            CancellationFeedback.provider_name,
            func.count(CancellationFeedback.id).label("total_feedback"),
            func.sum(
                case(
                    (CancellationFeedback.feedback_type.cast(String).in_(['helpful', 'worked']), 1),
                    else_=0
                )
            ).label("positive_count"),
            func.sum(
                case(
                    (CancellationFeedback.successfully_cancelled == True, 1),
                    else_=0
                )
            ).label("success_count"),
            func.count(
                case(
                    (CancellationFeedback.successfully_cancelled.isnot(None), 1),
                    else_=None
                )
            ).label("success_total"),
            func.avg(CancellationFeedback.helpfulness_rating).label("avg_helpfulness"),
            func.avg(CancellationFeedback.accuracy_rating).label("avg_accuracy"),
            func.avg(CancellationFeedback.time_taken_minutes).label("avg_time"),
            func.avg(CancellationFeedback.ai_confidence_at_feedback).label("avg_confidence"),
            func.avg(CancellationFeedback.validation_quality_at_feedback).label("avg_quality")
        )
        .group_by(CancellationFeedback.provider_name)
        .order_by(desc("total_feedback"))
    ).all()

    metrics = []
    for row in feedback_by_provider:
        success_rate = None
        if row.success_total and row.success_total > 0:
            success_rate = round(float(row.success_count) / float(row.success_total), 3)

        metrics.append(ProviderMetrics(
            provider_name=row.provider_name,
            total_feedback=row.total_feedback,
            helpful_count=row.positive_count or 0,
            not_helpful_count=(row.total_feedback - (row.positive_count or 0)),
            success_rate=success_rate,
            avg_helpfulness=round(float(row.avg_helpfulness), 2) if row.avg_helpfulness else None,
            avg_accuracy=round(float(row.avg_accuracy), 2) if row.avg_accuracy else None,
            avg_time_minutes=round(float(row.avg_time), 1) if row.avg_time else None,
            common_issues=[]  # TODO: Extract from feedback comments
        ))

    return metrics


def _create_distribution(scores: List[float]) -> dict:
    """Create distribution buckets for scores"""
    if not scores:
        return {}

    buckets = {
        "0.0-0.2": 0,
        "0.2-0.4": 0,
        "0.4-0.6": 0,
        "0.6-0.8": 0,
        "0.8-1.0": 0,
    }

    for score in scores:
        if score < 0.2:
            buckets["0.0-0.2"] += 1
        elif score < 0.4:
            buckets["0.2-0.4"] += 1
        elif score < 0.6:
            buckets["0.4-0.6"] += 1
        elif score < 0.8:
            buckets["0.6-0.8"] += 1
        else:
            buckets["0.8-1.0"] += 1

    return buckets
