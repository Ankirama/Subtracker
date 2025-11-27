"""
Budget service for calculating spending, tracking budgets, and generating alerts.
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional
from decimal import Decimal

from app.models.budget import Budget
from app.models.subscription import Subscription
from app.models.mailbox import Mailbox


class BudgetService:
    """Service for budget calculations and tracking."""

    @staticmethod
    def _get_period_dates(period: str) -> tuple[datetime, datetime]:
        """
        Get start and end dates for the current budget period.

        Args:
            period: 'monthly', 'quarterly', or 'yearly'

        Returns:
            Tuple of (start_date, end_date) for the current period
        """
        today = datetime.now()

        if period == "monthly":
            start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start + relativedelta(months=1) - relativedelta(days=1)
        elif period == "quarterly":
            # Get current quarter
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            start = today.replace(
                month=quarter_start_month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end = start + relativedelta(months=3) - relativedelta(days=1)
        elif period == "yearly":
            start = today.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            end = today.replace(month=12, day=31, hour=23, minute=59, second=59)
        else:
            # Default to monthly
            start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start + relativedelta(months=1) - relativedelta(days=1)

        return start, end

    @staticmethod
    def _normalize_billing_to_monthly(amount: float, billing_cycle: str) -> float:
        """Convert any billing cycle to monthly equivalent."""
        if not amount:
            return 0.0

        cycle_multipliers = {
            "weekly": 4.33,
            "monthly": 1.0,
            "quarterly": 1 / 3,
            "biannual": 1 / 6,
            "yearly": 1 / 12,
            "annual": 1 / 12,
        }

        multiplier = cycle_multipliers.get(billing_cycle.lower(), 1.0)
        return round(amount * multiplier, 2)

    @staticmethod
    def _normalize_to_period(
        amount: float, billing_cycle: str, target_period: str
    ) -> float:
        """
        Convert billing amount to target period (monthly, quarterly, yearly).

        Args:
            amount: Subscription amount
            billing_cycle: Source billing cycle
            target_period: Target period to normalize to

        Returns:
            Normalized amount for target period
        """
        # First convert to monthly
        monthly = BudgetService._normalize_billing_to_monthly(amount, billing_cycle)

        # Then convert from monthly to target period
        if target_period == "monthly":
            return monthly
        elif target_period == "quarterly":
            return monthly * 3
        elif target_period == "yearly":
            return monthly * 12

        return monthly

    @staticmethod
    def calculate_spending(
        db: Session,
        user_id: str,
        category: Optional[str] = None,
        period: str = "monthly",
    ) -> float:
        """
        Calculate current spending for a budget period.

        Args:
            db: Database session
            user_id: User UUID
            category: Optional category filter (None for overall)
            period: Budget period ('monthly', 'quarterly', 'yearly')

        Returns:
            Total spending normalized to the period
        """
        # Get user's mailbox IDs
        mailbox_ids = db.query(Mailbox.id).filter(Mailbox.user_id == user_id).all()
        mailbox_ids = [m[0] for m in mailbox_ids]

        if not mailbox_ids:
            return 0.0

        # Build query for active subscriptions
        query = db.query(Subscription).filter(
            and_(
                Subscription.mailbox_id.in_(mailbox_ids), Subscription.is_active == True
            )
        )

        # Apply category filter if specified
        if category:
            query = query.filter(Subscription.category == category)

        subscriptions = query.all()

        # Calculate total spending normalized to period
        total = 0.0
        for sub in subscriptions:
            if sub.amount:
                normalized = BudgetService._normalize_to_period(
                    float(sub.amount), sub.billing_cycle, period
                )
                total += normalized

        return round(total, 2)

    @staticmethod
    def get_budget_status(db: Session, budget: Budget) -> Dict:
        """
        Get comprehensive status for a budget including spending, percentage, alerts.

        Args:
            db: Database session
            budget: Budget model instance

        Returns:
            Dictionary with budget status information
        """
        # Calculate current spending
        current_spending = BudgetService.calculate_spending(
            db, str(budget.user_id), budget.category, budget.period
        )

        limit = float(budget.limit_amount)
        percentage_used = (current_spending / limit * 100) if limit > 0 else 0
        remaining = limit - current_spending

        # Determine status
        if percentage_used >= 100:
            status = "exceeded"
        elif percentage_used >= budget.alert_threshold:
            status = "warning"
        else:
            status = "good"

        # Get period dates
        start_date, end_date = BudgetService._get_period_dates(budget.period)

        return {
            "budget_id": str(budget.id),
            "name": budget.name,
            "category": budget.category,
            "period": budget.period,
            "limit_amount": limit,
            "current_spending": current_spending,
            "remaining": remaining,
            "percentage_used": round(percentage_used, 2),
            "status": status,
            "alert_threshold": budget.alert_threshold,
            "alert_enabled": budget.alert_enabled == "true",
            "period_start": start_date.date().isoformat(),
            "period_end": end_date.date().isoformat(),
            "currency": budget.currency,
        }

    @staticmethod
    def get_all_budgets_status(db: Session, user_id: str) -> List[Dict]:
        """
        Get status for all user budgets.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            List of budget status dictionaries
        """
        budgets = db.query(Budget).filter(Budget.user_id == user_id).all()

        return [BudgetService.get_budget_status(db, budget) for budget in budgets]

    @staticmethod
    def check_budget_alerts(db: Session, user_id: str) -> List[Dict]:
        """
        Check all budgets for alert conditions.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            List of budgets that need alerts (warning or exceeded)
        """
        budgets = (
            db.query(Budget)
            .filter(and_(Budget.user_id == user_id, Budget.alert_enabled == "true"))
            .all()
        )

        alerts = []
        for budget in budgets:
            status = BudgetService.get_budget_status(db, budget)

            if status["status"] in ["warning", "exceeded"]:
                alerts.append(
                    {
                        "budget": status,
                        "alert_type": status["status"],
                        "message": f"Budget '{budget.name}' is at {status['percentage_used']}% ({status['current_spending']}/{status['limit_amount']} {budget.currency})",
                    }
                )

        return alerts
