"""
AI-powered subscription optimization service.

Analyzes user subscriptions and generates personalized recommendations for:
- Duplicate detection
- Savings opportunities
- Alternative suggestions
- Unused subscription detection
- Family plan opportunities
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import openai
import json
import logging

from app.models.subscription import Subscription
from app.models.user import User
from app.config import settings

logger = logging.getLogger(__name__)

# Configure OpenAI
openai.api_key = settings.OPENAI_API_KEY


class AIOptimizer:
    """AI-powered subscription optimization and recommendation engine."""

    @staticmethod
    def analyze_subscriptions(
        db: Session, user: User, subscriptions: List[Subscription]
    ) -> Dict[str, Any]:
        """
        Perform comprehensive AI analysis of user subscriptions.

        Args:
            db: Database session
            user: User to analyze
            subscriptions: List of active subscriptions

        Returns:
            Dict with analysis results and recommendations
        """
        if not subscriptions:
            return {
                "total_recommendations": 0,
                "potential_savings": 0.0,
                "recommendations": [],
                "insights": ["No active subscriptions to analyze"],
            }

        # Prepare subscription data for AI
        subscription_data = AIOptimizer._prepare_subscription_data(subscriptions)

        # Run AI analysis
        recommendations = []
        total_savings = 0.0

        # 1. Duplicate detection
        duplicate_recs = AIOptimizer._detect_duplicates(
            subscriptions, subscription_data
        )
        recommendations.extend(duplicate_recs)
        total_savings += sum(r.get("potential_savings", 0) for r in duplicate_recs)

        # 2. Unused subscriptions
        unused_recs = AIOptimizer._detect_unused(subscriptions)
        recommendations.extend(unused_recs)
        total_savings += sum(r.get("potential_savings", 0) for r in unused_recs)

        # 3. Family plan opportunities
        family_recs = AIOptimizer._detect_family_plan_opportunities(subscriptions)
        recommendations.extend(family_recs)
        total_savings += sum(r.get("potential_savings", 0) for r in family_recs)

        # 4. Annual billing savings
        annual_recs = AIOptimizer._suggest_annual_billing(subscriptions)
        recommendations.extend(annual_recs)
        total_savings += sum(r.get("potential_savings", 0) for r in annual_recs)

        # 5. Alternative providers (using AI)
        alternative_recs = AIOptimizer._suggest_alternatives(subscription_data)
        recommendations.extend(alternative_recs)
        total_savings += sum(r.get("potential_savings", 0) for r in alternative_recs)

        # Generate insights
        insights = AIOptimizer._generate_insights(subscriptions, recommendations)

        return {
            "total_recommendations": len(recommendations),
            "potential_savings": round(total_savings, 2),
            "recommendations": recommendations,
            "insights": insights,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _prepare_subscription_data(
        subscriptions: List[Subscription],
    ) -> List[Dict[str, Any]]:
        """Prepare subscription data for AI analysis."""
        return [
            {
                "id": str(sub.id),
                "provider": sub.provider,
                "category": sub.category or "other",
                "amount": float(sub.amount) if sub.amount else 0,
                "billing_cycle": sub.billing_cycle,
                "monthly_cost": AIOptimizer._get_monthly_cost(sub),
                "last_confirmed": (
                    sub.last_confirmed_at.isoformat() if sub.last_confirmed_at else None
                ),
                "first_detected": (
                    sub.first_detected_at.isoformat() if sub.first_detected_at else None
                ),
            }
            for sub in subscriptions
        ]

    @staticmethod
    def _get_monthly_cost(subscription: Subscription) -> float:
        """Convert subscription cost to monthly equivalent."""
        if not subscription.amount:
            return 0.0

        amount = float(subscription.amount)
        cycle = subscription.billing_cycle

        if cycle == "monthly":
            return amount
        elif cycle == "yearly":
            return amount / 12
        elif cycle == "weekly":
            return amount * 4.33
        elif cycle == "quarterly":
            return amount / 3
        elif cycle == "biannual":
            return amount / 6
        else:
            return 0.0

    @staticmethod
    def _detect_duplicates(
        subscriptions: List[Subscription], subscription_data: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Detect duplicate or overlapping subscriptions."""
        recommendations = []

        # Group by category
        by_category = defaultdict(list)
        for sub_data, sub in zip(subscription_data, subscriptions):
            category = sub_data["category"]
            by_category[category].append((sub_data, sub))

        # Check for duplicates within categories
        for category, subs in by_category.items():
            if len(subs) < 2:
                continue

            # Storage duplicates
            if category in ["storage", "cloud_storage"]:
                if len(subs) >= 2:
                    total_cost = sum(s[0]["monthly_cost"] for s in subs)
                    providers = [s[0]["provider"] for s in subs]
                    recommendations.append(
                        {
                            "type": "duplicate_consolidation",
                            "category": category,
                            "title": f"Consolidate {len(subs)} Storage Services",
                            "description": f"You have {len(subs)} storage subscriptions: {', '.join(providers)}. Consider consolidating to one service.",
                            "potential_savings": total_cost
                            * 0.5,  # Estimate 50% savings
                            "action": "consolidate",
                            "affected_subscriptions": [s[0]["id"] for s in subs],
                            "priority": "high",
                        }
                    )

            # Streaming duplicates
            elif category in ["streaming", "entertainment"]:
                if len(subs) >= 3:
                    providers = [s[0]["provider"] for s in subs]
                    total_cost = sum(s[0]["monthly_cost"] for s in subs)
                    recommendations.append(
                        {
                            "type": "duplicate_review",
                            "category": category,
                            "title": f"{len(subs)} Streaming Services",
                            "description": f"You have {len(subs)} streaming services: {', '.join(providers)}. Review if you need all of them.",
                            "potential_savings": total_cost
                            * 0.3,  # Estimate 30% savings by dropping least used
                            "action": "review",
                            "affected_subscriptions": [s[0]["id"] for s in subs],
                            "priority": "medium",
                        }
                    )

        return recommendations

    @staticmethod
    def _detect_unused(subscriptions: List[Subscription]) -> List[Dict[str, Any]]:
        """Detect potentially unused subscriptions based on last confirmation."""
        recommendations = []
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

        for sub in subscriptions:
            if sub.last_confirmed_at and sub.last_confirmed_at < ninety_days_ago:
                days_inactive = (
                    datetime.now(timezone.utc) - sub.last_confirmed_at
                ).days
                monthly_cost = AIOptimizer._get_monthly_cost(sub)

                recommendations.append(
                    {
                        "type": "unused_subscription",
                        "category": "optimization",
                        "title": f"Potentially Unused: {sub.provider}",
                        "description": f"No activity detected in {days_inactive} days. You might not be using this subscription.",
                        "potential_savings": monthly_cost,
                        "action": "review_or_cancel",
                        "affected_subscriptions": [str(sub.id)],
                        "priority": "high" if monthly_cost > 10 else "medium",
                    }
                )

        return recommendations

    @staticmethod
    def _detect_family_plan_opportunities(
        subscriptions: List[Subscription],
    ) -> List[Dict[str, Any]]:
        """Detect opportunities to upgrade to family plans."""
        recommendations = []

        # Known services with family plan options
        family_plan_services = {
            "Spotify": {"individual": 10.99, "family": 16.99, "members": 6},
            "Apple Music": {"individual": 10.99, "family": 16.99, "members": 6},
            "YouTube Premium": {"individual": 11.99, "family": 22.99, "members": 6},
            "Netflix": {"standard": 15.49, "premium": 19.99, "screens": 4},
            "Disney+": {"individual": 7.99, "family": 13.99, "members": 4},
        }

        for sub in subscriptions:
            provider_name = sub.provider
            for service, pricing in family_plan_services.items():
                if service.lower() in provider_name.lower():
                    monthly_cost = AIOptimizer._get_monthly_cost(sub)
                    # If close to individual price, suggest family plan
                    if (
                        "individual" in pricing
                        and abs(monthly_cost - pricing["individual"]) < 2
                    ):
                        family_price = pricing.get("family", 0)
                        members = pricing.get("members", 2)
                        per_person = family_price / members

                        if per_person < monthly_cost:
                            recommendations.append(
                                {
                                    "type": "family_plan_upgrade",
                                    "category": "savings_opportunity",
                                    "title": f"Consider {service} Family Plan",
                                    "description": f"Family plan at €{family_price}/mo for {members} people (€{per_person:.2f} per person) vs your current €{monthly_cost:.2f}",
                                    "potential_savings": 0,  # No savings unless they share
                                    "action": "consider_upgrade",
                                    "affected_subscriptions": [str(sub.id)],
                                    "priority": "low",
                                }
                            )

        return recommendations

    @staticmethod
    def _suggest_annual_billing(
        subscriptions: List[Subscription],
    ) -> List[Dict[str, Any]]:
        """Suggest switching to annual billing for savings."""
        recommendations = []

        for sub in subscriptions:
            if sub.billing_cycle == "monthly":
                monthly_cost = AIOptimizer._get_monthly_cost(sub)
                # Typical annual discount is 15-20%
                annual_savings = monthly_cost * 12 * 0.17  # 17% average discount
                monthly_savings = annual_savings / 12

                if monthly_cost > 5:  # Only suggest for subscriptions > €5/mo
                    recommendations.append(
                        {
                            "type": "annual_billing_savings",
                            "category": "savings_opportunity",
                            "title": f"Switch {sub.provider} to Annual Billing",
                            "description": f"Save approximately €{annual_savings:.2f}/year by switching to annual billing (typical 15-20% discount)",
                            "potential_savings": monthly_savings,
                            "action": "switch_to_annual",
                            "affected_subscriptions": [str(sub.id)],
                            "priority": "medium" if annual_savings > 50 else "low",
                        }
                    )

        return recommendations

    @staticmethod
    def _suggest_alternatives(
        subscription_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use AI to suggest alternative providers with better pricing."""
        recommendations = []

        # Only analyze most expensive subscriptions
        sorted_subs = sorted(
            subscription_data, key=lambda x: x["monthly_cost"], reverse=True
        )[:5]

        for sub_data in sorted_subs:
            if sub_data["monthly_cost"] < 10:  # Skip cheap subscriptions
                continue

            try:
                # Use AI to find alternatives
                prompt = f"""
Analyze this subscription and suggest cheaper alternatives if available:

Service: {sub_data['provider']}
Category: {sub_data['category']}
Current cost: €{sub_data['monthly_cost']:.2f}/month

If there are well-known, reputable alternatives that offer similar features at a lower price,
suggest ONE best alternative. Focus on established providers only.

Respond in JSON format:
{{
    "has_alternative": true/false,
    "alternative_name": "name or null",
    "alternative_price": price or null,
    "savings_percentage": percentage or null,
    "reason": "brief explanation or null"
}}
"""

                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a subscription cost optimization expert. Be conservative - only suggest alternatives that are genuinely better value.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=200,
                )

                result_text = response.choices[0].message.content.strip()
                # Extract JSON from response
                if "{" in result_text and "}" in result_text:
                    json_start = result_text.index("{")
                    json_end = result_text.rindex("}") + 1
                    result = json.loads(result_text[json_start:json_end])

                    if result.get("has_alternative") and result.get("alternative_name"):
                        current_cost = sub_data["monthly_cost"]
                        alt_price = result.get("alternative_price", 0)
                        savings = current_cost - alt_price

                        if savings > 2:  # Only recommend if saves at least €2/mo
                            recommendations.append(
                                {
                                    "type": "alternative_provider",
                                    "category": "cost_reduction",
                                    "title": f"Consider {result['alternative_name']} Instead of {sub_data['provider']}",
                                    "description": f"{result.get('reason', 'Similar features at lower cost')}. Current: €{current_cost:.2f}/mo → Alternative: €{alt_price:.2f}/mo (Save €{savings:.2f}/month)",
                                    "current_provider": sub_data["provider"],
                                    "current_cost": current_cost,
                                    "alternative_provider": result["alternative_name"],
                                    "alternative_cost": alt_price,
                                    "potential_savings": savings,
                                    "action": "research_alternative",
                                    "affected_subscriptions": [sub_data["id"]],
                                    "priority": "high" if savings > 10 else "medium",
                                }
                            )

            except Exception as e:
                logger.warning(
                    f"Failed to get AI alternative for {sub_data['provider']}: {str(e)}"
                )
                continue

        return recommendations

    @staticmethod
    def _generate_insights(
        subscriptions: List[Subscription], recommendations: List[Dict]
    ) -> List[str]:
        """Generate AI-powered insights about subscription portfolio."""
        insights = []

        total_subs = len(subscriptions)
        total_monthly = sum(AIOptimizer._get_monthly_cost(s) for s in subscriptions)
        total_savings = sum(r.get("potential_savings", 0) for r in recommendations)

        # Overall insights
        if total_savings > 0:
            insights.append(
                f"💰 We found opportunities to save €{total_savings:.2f}/month (€{total_savings * 12:.2f}/year)"
            )

        if len(recommendations) > 0:
            insights.append(
                f"🎯 {len(recommendations)} optimization opportunities identified"
            )

        # Category-specific insights
        high_priority_count = len(
            [r for r in recommendations if r.get("priority") == "high"]
        )
        if high_priority_count > 0:
            insights.append(
                f"⚠️ {high_priority_count} high-priority recommendations require your attention"
            )

        # Spending insights
        if total_monthly > 100:
            insights.append(
                f"📊 Your total subscription spending is €{total_monthly:.2f}/month (€{total_monthly * 12:.2f}/year)"
            )

        # Action insights
        duplicate_count = len(
            [
                r
                for r in recommendations
                if r["type"] in ["duplicate_consolidation", "duplicate_review"]
            ]
        )
        if duplicate_count > 0:
            insights.append(
                f"🔄 {duplicate_count} potential duplicate or overlapping services detected"
            )

        unused_count = len(
            [r for r in recommendations if r["type"] == "unused_subscription"]
        )
        if unused_count > 0:
            insights.append(
                f"⏸️ {unused_count} subscriptions appear to be unused recently"
            )

        return insights
