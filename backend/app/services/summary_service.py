"""
Service for generating subscription summaries (weekly/monthly).

Aggregates subscription data and spending patterns for email digests.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from collections import defaultdict

from app.models.subscription import Subscription
from app.models.mailbox import Mailbox
from app.models.user import User
from app.services.ai_optimizer import AIOptimizer


class SummaryService:
    """Generate weekly and monthly subscription summaries."""

    @staticmethod
    def generate_weekly_summary(db: Session, user: User) -> Dict[str, Any]:
        """
        Generate weekly summary for user.

        Returns:
            Dictionary with summary data for email template
        """
        # Calculate date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        return SummaryService._generate_summary(
            db=db,
            user=user,
            start_date=start_date,
            end_date=end_date,
            period_type="weekly"
        )

    @staticmethod
    def generate_monthly_summary(db: Session, user: User) -> Dict[str, Any]:
        """
        Generate monthly summary for user.

        Returns:
            Dictionary with summary data for email template
        """
        # Calculate date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        return SummaryService._generate_summary(
            db=db,
            user=user,
            start_date=start_date,
            end_date=end_date,
            period_type="monthly"
        )

    @staticmethod
    def _generate_summary(
        db: Session,
        user: User,
        start_date: datetime,
        end_date: datetime,
        period_type: str
    ) -> Dict[str, Any]:
        """
        Internal method to generate summary for any time period.
        """
        # Get all user's mailboxes
        mailbox_ids = db.query(Mailbox.id).filter(
            Mailbox.user_id == user.id
        ).all()
        mailbox_ids = [m[0] for m in mailbox_ids]

        if not mailbox_ids:
            return SummaryService._empty_summary(period_type, start_date, end_date)

        # Get all subscriptions (active and inactive)
        all_subscriptions = db.query(Subscription).filter(
            Subscription.mailbox_id.in_(mailbox_ids)
        ).all()

        # Current active subscriptions
        active_subscriptions = [s for s in all_subscriptions if s.is_active]

        # New subscriptions in period
        new_subscriptions = [
            s for s in all_subscriptions
            if s.first_detected_at and s.first_detected_at >= start_date
        ]

        # Cancelled subscriptions in period
        cancelled_subscriptions = [
            s for s in all_subscriptions
            if not s.is_active and s.last_confirmed_at and s.last_confirmed_at >= start_date
        ]

        # Calculate spending
        total_monthly_cost = sum(
            SummaryService._get_monthly_cost(s) for s in active_subscriptions
        )
        total_yearly_cost = total_monthly_cost * 12

        # Category breakdown
        category_breakdown = defaultdict(lambda: {'count': 0, 'cost': 0.0})
        for sub in active_subscriptions:
            category = sub.category or 'other'
            category_breakdown[category]['count'] += 1
            category_breakdown[category]['cost'] += SummaryService._get_monthly_cost(sub)

        # Sort categories by cost
        top_categories = sorted(
            [
                {'category': cat, 'count': data['count'], 'cost': data['cost']}
                for cat, data in category_breakdown.items()
            ],
            key=lambda x: x['cost'],
            reverse=True
        )[:5]  # Top 5 categories

        # Most expensive subscriptions
        top_subscriptions = sorted(
            [
                {
                    'provider': s.provider,
                    'amount': float(s.amount) if s.amount else 0,
                    'billing_cycle': s.billing_cycle,
                    'monthly_cost': SummaryService._get_monthly_cost(s)
                }
                for s in active_subscriptions
            ],
            key=lambda x: x['monthly_cost'],
            reverse=True
        )[:5]  # Top 5 most expensive

        # Calculate savings from cancellations
        savings_from_cancellations = sum(
            SummaryService._get_monthly_cost(s) for s in cancelled_subscriptions
        )

        # Cost of new subscriptions
        cost_of_new = sum(
            SummaryService._get_monthly_cost(s) for s in new_subscriptions
        )

        # Upcoming renewals (next 30 days)
        upcoming_renewals = [
            {
                'provider': s.provider,
                'renewal_date': s.renewal_date.isoformat() if s.renewal_date else None,
                'amount': float(s.amount) if s.amount else 0,
            }
            for s in active_subscriptions
            if s.renewal_date and s.renewal_date <= (end_date + timedelta(days=30)).date()
        ]
        upcoming_renewals = sorted(upcoming_renewals, key=lambda x: x['renewal_date'] or '')[:10]

        # AI Optimization Analysis
        try:
            ai_analysis = AIOptimizer.analyze_subscriptions(db, user, active_subscriptions)
        except Exception as e:
            # If AI analysis fails, continue without it
            ai_analysis = {
                'total_recommendations': 0,
                'potential_savings': 0.0,
                'recommendations': [],
                'insights': []
            }

        return {
            'period_type': period_type,
            'start_date': start_date.strftime('%B %d, %Y'),
            'end_date': end_date.strftime('%B %d, %Y'),
            'user_name': user.display_name or user.email.split('@')[0],

            # Overview
            'total_subscriptions': len(active_subscriptions),
            'total_monthly_cost': round(total_monthly_cost, 2),
            'total_yearly_cost': round(total_yearly_cost, 2),

            # Changes
            'new_subscriptions_count': len(new_subscriptions),
            'new_subscriptions': [
                {
                    'provider': s.provider,
                    'amount': float(s.amount) if s.amount else 0,
                    'billing_cycle': s.billing_cycle
                }
                for s in new_subscriptions
            ],
            'cancelled_subscriptions_count': len(cancelled_subscriptions),
            'cancelled_subscriptions': [
                {
                    'provider': s.provider,
                    'amount': float(s.amount) if s.amount else 0,
                    'billing_cycle': s.billing_cycle
                }
                for s in cancelled_subscriptions
            ],

            # Spending analysis
            'top_categories': top_categories,
            'top_subscriptions': top_subscriptions,
            'savings_from_cancellations': round(savings_from_cancellations, 2),
            'cost_of_new': round(cost_of_new, 2),
            'net_change': round(cost_of_new - savings_from_cancellations, 2),

            # Upcoming
            'upcoming_renewals': upcoming_renewals,

            # Insights
            'insights': SummaryService._generate_insights(
                active_subscriptions=active_subscriptions,
                new_subscriptions=new_subscriptions,
                cancelled_subscriptions=cancelled_subscriptions,
                total_monthly_cost=total_monthly_cost,
                category_breakdown=category_breakdown
            ),

            # AI Optimization
            'ai_recommendations': ai_analysis.get('recommendations', []),
            'ai_insights': ai_analysis.get('insights', []),
            'potential_savings': ai_analysis.get('potential_savings', 0.0),
            'total_ai_recommendations': ai_analysis.get('total_recommendations', 0)
        }

    @staticmethod
    def _get_monthly_cost(subscription: Subscription) -> float:
        """Convert subscription cost to monthly equivalent."""
        if not subscription.amount:
            return 0.0

        amount = float(subscription.amount)
        cycle = subscription.billing_cycle

        if cycle == 'monthly':
            return amount
        elif cycle == 'yearly':
            return amount / 12
        elif cycle == 'weekly':
            return amount * 4.33  # Average weeks per month
        elif cycle == 'quarterly':
            return amount / 3
        elif cycle == 'biannual':
            return amount / 6
        else:
            return 0.0

    @staticmethod
    def _generate_insights(
        active_subscriptions: List[Subscription],
        new_subscriptions: List[Subscription],
        cancelled_subscriptions: List[Subscription],
        total_monthly_cost: float,
        category_breakdown: Dict
    ) -> List[str]:
        """Generate smart insights based on subscription data."""
        insights = []

        # Growth insight
        if len(new_subscriptions) > len(cancelled_subscriptions):
            net_new = len(new_subscriptions) - len(cancelled_subscriptions)
            insights.append(
                f"📈 You added {net_new} net new subscription{'s' if net_new != 1 else ''} this period"
            )
        elif len(cancelled_subscriptions) > len(new_subscriptions):
            net_cancelled = len(cancelled_subscriptions) - len(new_subscriptions)
            insights.append(
                f"📉 You cancelled {net_cancelled} more subscription{'s' if net_cancelled != 1 else ''} than you added"
            )

        # Spending insight
        if total_monthly_cost > 100:
            insights.append(
                f"💰 You're spending €{total_monthly_cost:.2f}/month on subscriptions"
            )

        # Top category insight
        if category_breakdown:
            top_cat = max(category_breakdown.items(), key=lambda x: x[1]['cost'])
            category_name = top_cat[0].replace('_', ' ').title()
            insights.append(
                f"🎯 {category_name} is your top spending category at €{top_cat[1]['cost']:.2f}/month"
            )

        # Annual equivalent
        if total_monthly_cost > 0:
            insights.append(
                f"📅 That's €{(total_monthly_cost * 12):.2f} annually"
            )

        # Savings opportunity
        if len(active_subscriptions) >= 5:
            insights.append(
                f"💡 Review your {len(active_subscriptions)} active subscriptions - consolidation opportunities may exist"
            )

        return insights

    @staticmethod
    def _empty_summary(period_type: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Return empty summary when user has no subscriptions."""
        return {
            'period_type': period_type,
            'start_date': start_date.strftime('%B %d, %Y'),
            'end_date': end_date.strftime('%B %d, %Y'),
            'total_subscriptions': 0,
            'total_monthly_cost': 0,
            'total_yearly_cost': 0,
            'new_subscriptions_count': 0,
            'new_subscriptions': [],
            'cancelled_subscriptions_count': 0,
            'cancelled_subscriptions': [],
            'top_categories': [],
            'top_subscriptions': [],
            'savings_from_cancellations': 0,
            'cost_of_new': 0,
            'net_change': 0,
            'upcoming_renewals': [],
            'insights': ['👋 Add some subscriptions to start tracking your spending!']
        }
