"""Admin endpoints for demo data management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.security import get_current_admin_user
from app.seed_demo_data import (
    create_demo_user,
    create_demo_mailbox,
    create_subscriptions,
    create_budgets,
    disable_notifications,
    DEMO_EMAIL,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/demo/generate-data")
async def generate_demo_data(
    reset: bool = False,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Generate demo data for testing and screenshots.

    Args:
        reset: If True, delete existing demo user data before creating new data
        current_user: The authenticated admin user
        db: Database session

    Returns:
        Summary of created demo data
    """
    try:
        # Get or create demo user
        demo_user = db.query(User).filter(User.email == DEMO_EMAIL).first()

        if demo_user and reset:
            # Delete existing demo user and all their data (CASCADE will handle related data)
            logger.info(f"Resetting demo data for user: {DEMO_EMAIL}")
            db.delete(demo_user)
            db.commit()
            demo_user = None

        # Create demo user
        demo_user = create_demo_user(db)

        # Create demo mailbox
        demo_mailbox = create_demo_mailbox(db, demo_user.id)

        # Create subscriptions
        create_subscriptions(db, demo_user.id, demo_mailbox.id)

        # Create budgets
        create_budgets(db, demo_user.id)

        # Disable all notifications for safety
        disable_notifications(db, demo_user.id)

        # Get counts
        from app.models import Subscription, Budget

        subscription_count = (
            db.query(Subscription).filter(Subscription.user_id == demo_user.id).count()
        )
        budget_count = db.query(Budget).filter(Budget.user_id == demo_user.id).count()

        return {
            "success": True,
            "message": "Demo data generated successfully",
            "demo_user": {
                "email": DEMO_EMAIL,
                "password": "demo123",
            },
            "data_created": {
                "subscriptions": subscription_count,
                "budgets": budget_count,
            },
            "reset": reset,
        }

    except Exception as e:
        logger.error(f"Error generating demo data: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate demo data: {str(e)}",
        )


@router.delete("/demo/delete-data")
async def delete_demo_data(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Delete all demo user data.

    Args:
        current_user: The authenticated admin user
        db: Database session

    Returns:
        Success message
    """
    try:
        demo_user = db.query(User).filter(User.email == DEMO_EMAIL).first()

        if not demo_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Demo user not found",
            )

        logger.info(f"Deleting demo user: {DEMO_EMAIL}")
        db.delete(demo_user)
        db.commit()

        return {
            "success": True,
            "message": "Demo user and all related data deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting demo data: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete demo data: {str(e)}",
        )


@router.get("/demo/status")
async def get_demo_status(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Check if demo user exists and get data counts.

    Args:
        current_user: The authenticated admin user
        db: Database session

    Returns:
        Demo user status and data counts
    """
    from app.models import Subscription, Budget

    demo_user = db.query(User).filter(User.email == DEMO_EMAIL).first()

    if not demo_user:
        return {
            "exists": False,
            "email": DEMO_EMAIL,
            "data_counts": {
                "subscriptions": 0,
                "budgets": 0,
            },
        }

    subscription_count = (
        db.query(Subscription).filter(Subscription.user_id == demo_user.id).count()
    )
    budget_count = db.query(Budget).filter(Budget.user_id == demo_user.id).count()

    return {
        "exists": True,
        "email": DEMO_EMAIL,
        "user_id": str(demo_user.id),
        "created_at": (
            demo_user.created_at.isoformat() if demo_user.created_at else None
        ),
        "data_counts": {
            "subscriptions": subscription_count,
            "budgets": budget_count,
        },
    }
