"""
AI-powered email classification service.
Uses OpenAI GPT to determine if an email is subscription-related.
"""
from openai import AsyncOpenAI
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.email_providers.base import EmailMessage
from app.utils.config_helper import get_config_value
import logging
import json

logger = logging.getLogger(__name__)


def get_openai_client(db: Optional[Session] = None) -> AsyncOpenAI:
    """
    Get OpenAI client with API key from admin settings or environment.

    Args:
        db: Optional database session to check admin settings

    Returns:
        Configured AsyncOpenAI client
    """
    api_key = get_config_value('openai.api_key', settings.OPENAI_API_KEY, db)
    return AsyncOpenAI(api_key=api_key)


CLASSIFICATION_PROMPT = """You are an AI assistant that classifies emails to detect BILLING, PAYMENT, or ACCOUNT MANAGEMENT emails for SUBSCRIPTION SERVICES.

A SUBSCRIPTION is a service with RECURRING payments for ongoing access.

✅ SUBSCRIPTION-RELATED EMAILS (is_subscription: true):

1. **Billing & Payment Emails**:
   - Payment confirmations for subscription services (e.g., "Netflix charged $15.99")
   - Billing statements/invoices for recurring services
   - Payment method updates for subscriptions
   - Failed payment notifications for subscriptions

2. **Renewal & Trial Emails**:
   - Renewal reminders (e.g., "Your Spotify subscription renews in 3 days")
   - Trial ending notices (e.g., "Your Disney+ free trial ends tomorrow")
   - Auto-renewal confirmations
   - Subscription expiration notices

3. **Subscription Management**:
   - Subscription upgrade/downgrade confirmations
   - Plan change confirmations (e.g., "You switched to Premium")
   - Subscription cancellation confirmations
   - Reactivation emails

4. **Welcome/Onboarding for Paid Subscriptions**:
   - "Welcome to Premium" emails with billing info
   - First payment confirmation for new subscriptions

🚫 NOT SUBSCRIPTION-RELATED (is_subscription: false):

1. **Security & Account Access** (HIGH PRIORITY):
   - Login notifications (e.g., "New sign-in from Chrome")
   - Password reset/change confirmations
   - Security alerts (e.g., "Unusual activity detected")
   - Two-factor authentication codes
   - Email verification requests

2. **Service Notifications** (HIGH PRIORITY):
   - Technical alerts (e.g., "AWS Lambda end of support")
   - Usage warnings (e.g., "API quota limit reached")
   - Service status/downtime notifications
   - Feature announcements
   - Product updates

3. **One-Time Transactions**:
   - Single purchase receipts (e.g., "You bought a book on Amazon")
   - Shipping/delivery notifications
   - Order confirmations for physical goods

4. **Marketing & Engagement**:
   - Promotional emails without billing info
   - Newsletter content (articles, blog posts)
   - "New content available" without billing context
   - General marketing emails

5. **Support & Admin**:
   - Support ticket responses
   - Account creation (without payment)
   - Settings change confirmations (non-billing)

⚠️ CRITICAL DISTINCTIONS:

**Amazon Emails**:
- ❌ "Someone signed in to your Amazon account" → NOT subscription (login alert)
- ✅ "Your Amazon Prime membership renews on..." → IS subscription (renewal)
- ❌ "Your order has shipped" → NOT subscription (one-time purchase)

**AWS/Cloud Emails**:
- ❌ "AWS Lambda end of support notification" → NOT subscription (service alert)
- ❌ "CloudWatch alarm triggered" → NOT subscription (usage alert)
- ✅ "Your AWS invoice is ready" → IS subscription (billing)

**Streaming Services**:
- ❌ "New login from Windows PC" → NOT subscription (security alert)
- ❌ "New episodes available on Crunchyroll" → NOT subscription (content notification)
- ✅ "Your Crunchyroll subscription renews on 12/15" → IS subscription (renewal)

**PayPal/Payment Emails**:
- ❌ "You sent $50 to John Doe" → NOT subscription (one-time transfer)
- ✅ "Automatic payment to Netflix for $15.99" → IS subscription (recurring payment)

**Newsletter/Content Emails**:
- ❌ "Here's your daily tech news" → NOT subscription (content delivery)
- ❌ "10 tips for productivity" → NOT subscription (marketing)
- ✅ "Your Medium membership payment of $5/month" → IS subscription (billing)

CLASSIFICATION RULES:
1. If email is about LOGIN, SECURITY, or TECHNICAL ALERTS → confidence must be LOW (< 0.3)
2. If email mentions BILLING, PAYMENT, RENEWAL, TRIAL → check if it's for a subscription service
3. If uncertain whether service is subscription-based → confidence should be < 0.6
4. Only use confidence > 0.8 for clear billing/payment/renewal emails

Email Details:
Subject: {subject}
From: {sender} ({sender_name})
Date: {date}

Body (first 1000 chars):
{body}

Respond ONLY with a JSON object in this exact format:
{{
    "is_subscription": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation of why this is/isn't subscription-related",
    "category": "streaming|saas|gaming|newsletter|membership|payment_confirmation|renewal|trial|cancellation|upgrade|not_subscription"
}}"""


async def classify_email(email: EmailMessage, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Classify an email to determine if it's subscription-related.

    Args:
        email: EmailMessage object to classify
        db: Optional database session to check admin settings

    Returns:
        Dict with classification results:
        {
            "is_subscription": bool,
            "confidence": float (0-1),
            "reasoning": str,
            "category": str
        }
    """
    try:
        # Get OpenAI client with admin settings support
        client = get_openai_client(db)

        # Prepare email content
        body = email.body_text or email.body_html or ""
        body = body[:1000]  # Limit to first 1000 chars

        prompt = CLASSIFICATION_PROMPT.format(
            subject=email.subject,
            sender=email.sender,
            sender_name=email.sender_name or "Unknown",
            date=email.date.isoformat(),
            body=body
        )

        logger.info(f"Classifying email: {email.subject}")

        # Call OpenAI API
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Using mini for cost efficiency
            messages=[
                {"role": "system", "content": "You are a precise email classification assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=300
        )
        
        # Parse response
        result_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            
            logger.info(f"Classification result: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {result_text}")
            # Return conservative default
            return {
                "is_subscription": False,
                "confidence": 0.0,
                "reasoning": "Failed to parse classification response",
                "category": "not_subscription"
            }
            
    except Exception as e:
        logger.error(f"Error classifying email: {str(e)}")
        # Return conservative default on error
        return {
            "is_subscription": False,
            "confidence": 0.0,
            "reasoning": f"Classification error: {str(e)}",
            "category": "not_subscription"
        }
