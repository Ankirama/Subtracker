"""
Renewal Date Calculator Service

Calculates accurate renewal dates and active status for subscriptions using:
1. Pattern extraction from email content (provider-specific)
2. Billing cycle calculation based on last email date
3. Inactivity detection (no emails for >2 billing cycles)
4. Reactivation detection (new emails after gaps)
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class RenewalCalculator:
    """Calculate renewal dates and active status for subscriptions"""

    # Provider-specific renewal date patterns
    RENEWAL_PATTERNS = {
        'apple': [
            # Pattern: "Renews 25 November 2025"
            (r'Renews?\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
             lambda m: datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y")),
            # Pattern: "Renews on 11/25/2025"
            (r'Renews?\s+on\s+(\d{1,2}/\d{1,2}/\d{4})',
             lambda m: datetime.strptime(m.group(1), "%m/%d/%Y")),
        ],
        'hacktthebox': [
            # Pattern: HTML with "Next Invoice" followed by date like "Sep 20, 2025"
            (r'Next\s+Invoice.*?([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})',
             lambda m: datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y")),
        ],
        'twitch': [
            # Pattern: "22 oct. – 22 nov. 2025" (French date format, end date is renewal)
            (r'\d{1,2}\s+\w+\.\s*[–-]\s*(\d{1,2})\s+(janv\.|févr\.|mars|avr\.|mai|juin|juil\.|août|sept\.|oct\.|nov\.|déc\.)\s+(\d{4})',
             lambda m: _parse_french_date(m.group(1), m.group(2), m.group(3))),
        ],
        'stripe': [
            # Pattern: Common in Stripe invoices - "Your next invoice will be on December 5, 2025"
            (r'next\s+invoice.*?on\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})',
             lambda m: datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y")),
        ],
        'generic': [
            # Generic patterns that work for many providers
            # Pattern: "Next payment: December 5, 2025"
            (r'next\s+payment.*?([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})',
             lambda m: datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y")),
            # Pattern: "Billing date: 2025-12-05"
            (r'billing\s+date.*?(\d{4})-(\d{2})-(\d{2})',
             lambda m: datetime.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "%Y-%m-%d")),
            # Pattern: "Renewal date: 12/05/2025"
            (r'renewal\s+date.*?(\d{1,2}/\d{1,2}/\d{4})',
             lambda m: datetime.strptime(m.group(1), "%m/%d/%Y")),
        ]
    }

    # Billing cycle to relativedelta mapping
    BILLING_CYCLE_DELTA = {
        'monthly': relativedelta(months=1),
        'yearly': relativedelta(years=1),
        'weekly': relativedelta(weeks=1),
        'quarterly': relativedelta(months=3),
    }

    def __init__(self, db: Session):
        self.db = db

    def calculate_renewal_info(
        self,
        provider: str,
        billing_cycle: Optional[str],
        email_dates: List[datetime],
        email_contents: List[str],
        extraction_metadata: Optional[Dict] = None
    ) -> Tuple[Optional[datetime], bool, Optional[str], bool]:
        """
        Calculate renewal date, active status, trial status, and confirmation for a subscription.

        Args:
            provider: Subscription provider name
            billing_cycle: Billing cycle (monthly, yearly, etc.)
            email_dates: List of email dates (sorted newest first)
            email_contents: List of email contents (body_text or body_html)
            extraction_metadata: Optional metadata from AI extraction (includes trial detection)

        Returns:
            Tuple of (renewal_date, is_active, trial_status, is_confirmed)
        """
        if not email_dates:
            return None, False, None, False

        # Trial Detection Logic
        email_count = len(email_dates)
        trial_detected = extraction_metadata and extraction_metadata.get('trial_detected', False)

        # Determine trial status and confirmation
        # is_confirmed = True if 2+ emails OR no trial detected
        is_confirmed = email_count >= 2 or not trial_detected

        # Set trial_status based on detection and email count
        trial_status = None
        if trial_detected:
            if email_count == 1:
                # Only 1 email with trial detected = trial signup only
                trial_status = 'trial'
            elif email_count >= 2:
                # 2+ emails with trial = converted to paid
                trial_status = 'converted'
        else:
            # No trial detected = regular subscription
            trial_status = 'none'

        # Strategy 1: Try to extract renewal date from email content
        extracted_date = self._extract_renewal_date(provider, email_contents)
        if extracted_date:
            # Check if this date is in the future
            now = datetime.now(timezone.utc)
            if extracted_date.replace(tzinfo=timezone.utc) > now:
                # Check if trial that hasn't converted yet
                is_active_status = True
                if trial_status == 'trial' and email_count == 1:
                    # Only 1 email with trial = mark as inactive (likely cancelled before payment)
                    is_active_status = False
                return extracted_date.replace(tzinfo=timezone.utc), is_active_status, trial_status, is_confirmed
            logger.info(f"Extracted renewal date {extracted_date} is in the past for {provider}")

        # Strategy 2: Calculate based on billing cycle and last email date
        if billing_cycle and billing_cycle.lower() in self.BILLING_CYCLE_DELTA:
            last_email_date = email_dates[0]  # Assuming sorted newest first
            calculated_date, is_active = self._calculate_from_billing_cycle(
                last_email_date,
                billing_cycle.lower(),
                len(email_dates)
            )
            # Override is_active if trial that hasn't converted
            if trial_status == 'trial' and email_count == 1:
                is_active = False
            return calculated_date, is_active, trial_status, is_confirmed

        # Strategy 3: Default - assume inactive if no recent emails
        last_email_date = email_dates[0]
        is_active = self._is_recently_active(last_email_date)

        # Override is_active if trial that hasn't converted
        if trial_status == 'trial' and email_count == 1:
            is_active = False

        # If inactive, set renewal to when it should have renewed (but didn't)
        if not is_active and billing_cycle and billing_cycle.lower() in self.BILLING_CYCLE_DELTA:
            delta = self.BILLING_CYCLE_DELTA[billing_cycle.lower()]
            renewal_date = last_email_date + delta
            return renewal_date.replace(tzinfo=timezone.utc), False, trial_status, is_confirmed

        return None, is_active, trial_status, is_confirmed

    def _extract_renewal_date(self, provider: str, email_contents: List[str]) -> Optional[datetime]:
        """
        Extract renewal date from email content using provider-specific patterns.

        Tries provider-specific patterns first, then falls back to generic patterns.
        """
        # Normalize provider name for pattern matching
        provider_lower = provider.lower()

        # Determine which patterns to try
        patterns_to_try = []

        # Add provider-specific patterns
        for pattern_key in self.RENEWAL_PATTERNS.keys():
            if pattern_key in provider_lower:
                patterns_to_try.extend(self.RENEWAL_PATTERNS[pattern_key])

        # Always add generic patterns as fallback
        patterns_to_try.extend(self.RENEWAL_PATTERNS['generic'])

        # Try each email content (most recent first)
        for content in email_contents:
            if not content:
                continue

            # Try each pattern
            for pattern, parser in patterns_to_try:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    try:
                        renewal_date = parser(match)
                        logger.info(f"Extracted renewal date {renewal_date} from {provider} email using pattern")
                        return renewal_date
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Failed to parse renewal date from match: {e}")
                        continue

        return None

    def _calculate_from_billing_cycle(
        self,
        last_email_date: datetime,
        billing_cycle: str,
        email_count: int
    ) -> Tuple[Optional[datetime], bool]:
        """
        Calculate renewal date based on billing cycle and last email date.

        Also determines if subscription is active based on time since last email.
        """
        delta = self.BILLING_CYCLE_DELTA[billing_cycle]
        now = datetime.now(timezone.utc)

        # Ensure last_email_date has timezone info
        if last_email_date.tzinfo is None:
            last_email_date = last_email_date.replace(tzinfo=timezone.utc)

        # Calculate expected next renewal
        next_renewal = last_email_date + delta

        # Determine if subscription is still active
        # Consider inactive if:
        # 1. More than 2 billing cycles have passed since last email
        # 2. The calculated renewal date is more than 1 billing cycle in the past

        cycles_since_last_email = (now - last_email_date) / self._delta_to_timedelta(delta)

        if cycles_since_last_email > 2:
            # Subscription is inactive - no emails for more than 2 billing cycles
            logger.info(f"Subscription inactive: {cycles_since_last_email:.1f} billing cycles since last email")
            return next_renewal, False

        # Check if the calculated renewal date has passed
        if next_renewal < now:
            # Renewal date in past - calculate next future renewal
            cycles_to_add = int((now - next_renewal) / self._delta_to_timedelta(delta)) + 1
            future_renewal = next_renewal
            for _ in range(cycles_to_add):
                future_renewal = future_renewal + delta

            # If we're adding many cycles, subscription might be inactive
            if cycles_to_add > 1:
                logger.warning(f"Calculated renewal {cycles_to_add} cycles ahead - subscription may be inactive")
                return future_renewal, False

            return future_renewal, True

        return next_renewal, True

    def _delta_to_timedelta(self, delta: relativedelta) -> timedelta:
        """Convert relativedelta to approximate timedelta for comparison"""
        if delta.years:
            return timedelta(days=365 * delta.years)
        if delta.months:
            return timedelta(days=30 * delta.months)
        if delta.weeks:
            return timedelta(weeks=delta.weeks)
        if delta.days:
            return timedelta(days=delta.days)
        return timedelta(days=30)  # Default to monthly

    def _is_recently_active(self, last_email_date: datetime) -> bool:
        """
        Check if subscription is recently active based on last email date.

        Consider active if last email was within 60 days (approximately 2 monthly cycles).
        """
        now = datetime.now(timezone.utc)
        if last_email_date.tzinfo is None:
            last_email_date = last_email_date.replace(tzinfo=timezone.utc)

        days_since_last_email = (now - last_email_date).days
        return days_since_last_email <= 60

    def detect_reactivation(
        self,
        email_dates: List[datetime],
        billing_cycle: Optional[str]
    ) -> bool:
        """
        Detect if a subscription was reactivated after a gap.

        Returns True if there's a significant gap between emails indicating
        a cancellation and reactivation.
        """
        if len(email_dates) < 2 or not billing_cycle:
            return False

        billing_cycle_lower = billing_cycle.lower()
        if billing_cycle_lower not in self.BILLING_CYCLE_DELTA:
            return False

        delta = self.BILLING_CYCLE_DELTA[billing_cycle_lower]
        expected_gap = self._delta_to_timedelta(delta)

        # Check gaps between consecutive emails
        sorted_dates = sorted(email_dates, reverse=True)  # Newest first

        for i in range(len(sorted_dates) - 1):
            actual_gap = sorted_dates[i] - sorted_dates[i + 1]

            # If gap is more than 2x the billing cycle, consider it a reactivation
            if actual_gap > expected_gap * 2:
                logger.info(f"Reactivation detected: {actual_gap.days} day gap between emails")
                return True

        return False


def _parse_french_date(day: str, month: str, year: str) -> datetime:
    """Parse French date format (e.g., '22 nov. 2025')"""
    french_months = {
        'janv.': 1, 'févr.': 2, 'mars': 3, 'avr.': 4,
        'mai': 5, 'juin': 6, 'juil.': 7, 'août': 8,
        'sept.': 9, 'oct.': 10, 'nov.': 11, 'déc.': 12
    }

    month_num = french_months.get(month.lower())
    if not month_num:
        raise ValueError(f"Unknown French month: {month}")

    return datetime(int(year), month_num, int(day))


def get_subscription_emails(db: Session, subscription_id: str) -> List[Dict]:
    """
    Get all emails for a subscription with dates and content.

    Returns list of dicts with 'date', 'body_text', 'body_html' sorted by date (newest first).
    """
    from app.models.subscription import Subscription
    from app.models.email_message import EmailMessage, subscription_emails

    results = db.query(
        EmailMessage.date,
        EmailMessage.body_text,
        EmailMessage.body_html
    ).join(
        subscription_emails,
        EmailMessage.id == subscription_emails.c.email_id
    ).filter(
        subscription_emails.c.subscription_id == subscription_id
    ).order_by(
        EmailMessage.date.desc()
    ).all()

    return [
        {
            'date': row.date,
            'body_text': row.body_text,
            'body_html': row.body_html
        }
        for row in results
    ]
