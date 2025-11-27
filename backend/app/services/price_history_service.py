"""
Price history service for tracking and analyzing subscription price changes.
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from decimal import Decimal
from datetime import datetime

from app.models.price_history import PriceHistory
from app.models.subscription import Subscription


class PriceHistoryService:
    """Service for managing subscription price history."""

    @staticmethod
    def record_price_change(
        db: Session,
        subscription_id: str,
        new_amount: float,
        old_amount: Optional[float] = None,
        detected_from: str = "manual",
        notes: Optional[str] = None,
    ) -> PriceHistory:
        """
        Record a price change for a subscription.

        Args:
            db: Database session
            subscription_id: Subscription UUID
            new_amount: New price amount
            old_amount: Previous price amount (None for initial record)
            detected_from: Source of detection ('email', 'manual', 'api')
            notes: Optional notes about the change

        Returns:
            Created PriceHistory record
        """
        # Get subscription for currency
        subscription = (
            db.query(Subscription).filter(Subscription.id == subscription_id).first()
        )
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        # Determine change type and percentage
        if old_amount is None:
            change_type = "initial"
            change_percentage = None
        else:
            if new_amount > old_amount:
                change_type = "increase"
                change_percentage = ((new_amount - old_amount) / old_amount) * 100
            elif new_amount < old_amount:
                change_type = "decrease"
                change_percentage = ((old_amount - new_amount) / old_amount) * 100
            else:
                # No change, don't record
                return None

        # Create price history record
        price_history = PriceHistory(
            subscription_id=subscription_id,
            old_amount=old_amount,
            new_amount=new_amount,
            currency=subscription.currency,
            change_type=change_type,
            change_percentage=(
                round(change_percentage, 2) if change_percentage else None
            ),
            detected_from=detected_from,
            notes=notes,
        )

        db.add(price_history)
        db.commit()
        db.refresh(price_history)

        return price_history

    @staticmethod
    def check_and_record_price_change(
        db: Session,
        subscription: Subscription,
        new_amount: float,
        detected_from: str = "email",
    ) -> Optional[PriceHistory]:
        """
        Check if price has changed and record it if so.

        Args:
            db: Database session
            subscription: Subscription model instance
            new_amount: Detected price amount
            detected_from: Source of detection

        Returns:
            PriceHistory record if change was recorded, None otherwise
        """
        current_amount = float(subscription.amount) if subscription.amount else None

        # If no current amount, this is the initial price
        if current_amount is None:
            price_history = PriceHistoryService.record_price_change(
                db=db,
                subscription_id=str(subscription.id),
                new_amount=new_amount,
                old_amount=None,
                detected_from=detected_from,
                notes="Initial price recorded",
            )

            # Update subscription amount
            subscription.amount = new_amount
            db.commit()

            return price_history

        # Check if price has changed (with small tolerance for floating point)
        if abs(new_amount - current_amount) > 0.01:
            price_history = PriceHistoryService.record_price_change(
                db=db,
                subscription_id=str(subscription.id),
                new_amount=new_amount,
                old_amount=current_amount,
                detected_from=detected_from,
                notes=f"Price changed from {current_amount} to {new_amount}",
            )

            # Update subscription amount
            subscription.amount = new_amount
            db.commit()

            return price_history

        return None

    @staticmethod
    def get_subscription_price_history(
        db: Session, subscription_id: str, limit: Optional[int] = None
    ) -> List[PriceHistory]:
        """
        Get price history for a subscription.

        Args:
            db: Database session
            subscription_id: Subscription UUID
            limit: Optional limit on number of records

        Returns:
            List of PriceHistory records ordered by detected_at descending
        """
        query = (
            db.query(PriceHistory)
            .filter(PriceHistory.subscription_id == subscription_id)
            .order_by(PriceHistory.detected_at.desc())
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    @staticmethod
    def get_price_increases(db: Session, subscription_id: str) -> List[PriceHistory]:
        """
        Get all price increases for a subscription.

        Args:
            db: Database session
            subscription_id: Subscription UUID

        Returns:
            List of price increase records
        """
        return (
            db.query(PriceHistory)
            .filter(
                PriceHistory.subscription_id == subscription_id,
                PriceHistory.change_type == "increase",
            )
            .order_by(PriceHistory.detected_at.desc())
            .all()
        )

    @staticmethod
    def get_price_statistics(db: Session, subscription_id: str) -> Dict:
        """
        Get price change statistics for a subscription.

        Args:
            db: Database session
            subscription_id: Subscription UUID

        Returns:
            Dictionary with price statistics
        """
        history = PriceHistoryService.get_subscription_price_history(
            db, subscription_id
        )

        if not history:
            return {
                "total_changes": 0,
                "increases": 0,
                "decreases": 0,
                "total_increase_amount": 0.0,
                "total_decrease_amount": 0.0,
                "average_change_percentage": 0.0,
                "latest_price": None,
                "original_price": None,
            }

        increases = [h for h in history if h.change_type == "increase"]
        decreases = [h for h in history if h.change_type == "decrease"]

        total_increase = sum(
            float(h.new_amount - h.old_amount) for h in increases if h.old_amount
        )
        total_decrease = sum(
            float(h.old_amount - h.new_amount) for h in decreases if h.old_amount
        )

        changes_with_percentage = [h for h in history if h.change_percentage]
        avg_change = (
            sum(float(h.change_percentage) for h in changes_with_percentage)
            / len(changes_with_percentage)
            if changes_with_percentage
            else 0.0
        )

        return {
            "total_changes": len(history) - 1,  # Exclude initial record
            "increases": len(increases),
            "decreases": len(decreases),
            "total_increase_amount": round(total_increase, 2),
            "total_decrease_amount": round(total_decrease, 2),
            "average_change_percentage": round(avg_change, 2),
            "latest_price": float(history[0].new_amount),
            "original_price": (
                float(history[-1].new_amount)
                if len(history) > 1
                else float(history[0].new_amount)
            ),
        }
