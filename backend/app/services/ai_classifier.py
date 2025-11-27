"""
AI-powered email classification service.
Uses OpenAI GPT to determine if an email is subscription-related.
"""

from openai import AsyncOpenAI, RateLimitError, APIError
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.config import settings
from app.email_providers.base import EmailMessage
from app.utils.config_helper import get_config_value
from app.utils.email_cleaner import get_optimized_email_body
import logging
import json
import asyncio

logger = logging.getLogger(__name__)


def get_openai_client(db: Optional[Session] = None) -> AsyncOpenAI:
    """
    Get OpenAI client with API key from admin settings or environment.

    Args:
        db: Optional database session to check admin settings

    Returns:
        Configured AsyncOpenAI client
    """
    api_key = get_config_value("openai.api_key", settings.OPENAI_API_KEY, db)
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


async def classify_email(
    email: EmailMessage, db: Optional[Session] = None
) -> Dict[str, Any]:
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

        # Prepare email content with smart cleaning and truncation
        body = get_optimized_email_body(
            body_text=email.body_text,
            body_html=email.body_html,
            mode="classification",  # Uses 1000 char limit with key info extraction
        )

        prompt = CLASSIFICATION_PROMPT.format(
            subject=email.subject,
            sender=email.sender,
            sender_name=email.sender_name or "Unknown",
            date=email.date.isoformat(),
            body=body,
        )

        logger.info(f"Classifying email: {email.subject}")

        # Call OpenAI API
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Using mini for cost efficiency
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise email classification assistant. Always respond with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=300,
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
                "category": "not_subscription",
            }

    except Exception as e:
        logger.error(f"Error classifying email: {str(e)}")
        # Return conservative default on error
        return {
            "is_subscription": False,
            "confidence": 0.0,
            "reasoning": f"Classification error: {str(e)}",
            "category": "not_subscription",
        }


async def classify_email_with_retry(
    email: EmailMessage,
    db: Optional[Session] = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> Dict[str, Any]:
    """
    Classify email with exponential backoff retry on failures.

    Args:
        email: EmailMessage to classify
        db: Database session
        max_retries: Maximum retry attempts (default 3)
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        Classification result or conservative default on permanent failure
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            # Attempt classification
            result = await classify_email(email, db)
            return result

        except RateLimitError as e:
            # 429 Rate Limit - need to back off
            last_exception = e
            if attempt < max_retries - 1:
                # Exponential backoff: 2s, 4s, 8s
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Rate limit hit for email '{email.subject}'. "
                    f"Retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Rate limit exceeded after {max_retries} retries for '{email.subject}'"
                )

        except APIError as e:
            # Other API errors (500, 503, etc.)
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"API error for email '{email.subject}': {e}. "
                    f"Retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"API error after {max_retries} retries for '{email.subject}': {e}"
                )

        except Exception as e:
            # Unexpected errors - log and return default
            logger.error(f"Unexpected error classifying '{email.subject}': {e}")
            last_exception = e
            break

    # If all retries failed, return conservative default
    return {
        "is_subscription": False,
        "confidence": 0.0,
        "reasoning": f"Classification failed after {max_retries} retries: {str(last_exception)}",
        "category": "not_subscription",
    }


async def classify_emails_batch(
    emails: List[EmailMessage],
    db: Optional[Session] = None,
    initial_batch_size: int = 10,
    min_batch_size: int = 2,
) -> List[Dict[str, Any]]:
    """
    Classify emails with adaptive batch sizing based on rate limit detection.

    Processes emails in parallel batches with automatic rate limit handling
    and adaptive batch size adjustment.

    Args:
        emails: List of EmailMessage objects to classify
        db: Database session
        initial_batch_size: Starting batch size for parallel processing
        min_batch_size: Minimum batch size when rate limited

    Returns:
        List of classification results matching input email order
    """
    all_results = []
    current_batch_size = initial_batch_size
    consecutive_rate_limits = 0

    i = 0
    while i < len(emails):
        # Get current batch
        batch = emails[i : i + current_batch_size]

        logger.info(
            f"Classifying batch: {len(batch)} emails "
            f"(position {i}/{len(emails)}, batch_size={current_batch_size})"
        )

        # Process batch in parallel with retry logic
        tasks = [classify_email_with_retry(email, db) for email in batch]

        try:
            # Execute all tasks concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for rate limit errors in results
            rate_limit_count = sum(
                1
                for r in batch_results
                if isinstance(r, Exception)
                or (isinstance(r, dict) and "Rate limit" in r.get("reasoning", ""))
            )

            # Process results
            for email, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to classify '{email.subject}': {result}")
                    all_results.append(
                        {
                            "is_subscription": False,
                            "confidence": 0.0,
                            "reasoning": f"Error: {str(result)}",
                            "category": "not_subscription",
                        }
                    )
                else:
                    all_results.append(result)

            # Adaptive batch size adjustment
            if rate_limit_count > 0:
                consecutive_rate_limits += 1

                # Reduce batch size if hitting rate limits frequently
                if consecutive_rate_limits >= 2 and current_batch_size > min_batch_size:
                    current_batch_size = max(min_batch_size, current_batch_size // 2)
                    logger.warning(
                        f"Rate limits detected. Reducing batch size to {current_batch_size}"
                    )

                # Longer sleep after rate limits
                await asyncio.sleep(5.0)
            else:
                # No rate limits - can try increasing batch size
                consecutive_rate_limits = 0

                if current_batch_size < initial_batch_size:
                    current_batch_size = min(initial_batch_size, current_batch_size + 2)
                    logger.info(f"Increasing batch size to {current_batch_size}")

                # Normal sleep between batches
                await asyncio.sleep(1.0)

            # Move to next batch
            i += len(batch)

        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            # On catastrophic batch failure, process emails one-by-one
            logger.warning("Falling back to sequential processing for this batch")
            for email in batch:
                result = await classify_email_with_retry(email, db)
                all_results.append(result)
                await asyncio.sleep(2.0)

            i += len(batch)

    logger.info(f"Classified {len(all_results)} emails in total")
    return all_results
