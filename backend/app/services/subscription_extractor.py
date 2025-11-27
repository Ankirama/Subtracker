"""
AI-powered subscription data extraction service.
Uses OpenAI GPT to extract structured subscription information from emails.
"""

from openai import AsyncOpenAI, RateLimitError, APIError
from typing import Dict, Any, Optional, List
from datetime import datetime
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


EXTRACTION_PROMPT = """You are an AI assistant that extracts subscription information from emails.

CRITICAL RULE: Only extract if the email contains EXPLICIT subscription evidence. Being from a subscription service is NOT enough.

REQUIRED EVIDENCE (must have at least ONE):
1. Explicit subscription cost/price mentioned (e.g., "$9.99/month", "€15.99 monthly")
2. Recurring payment confirmation with service name
3. Subscription renewal/expiration date mentioned
4. Explicit words: "subscription", "recurring", "renew", "auto-renewal"
5. Billing cycle explicitly stated (monthly, yearly, etc.)

VALID subscription emails (extract data):
✅ "Your Netflix subscription: $15.99 monthly"
✅ "Amazon Prime membership renewal: $139/year"
✅ "Your Spotify Premium subscription renews on..."
✅ PayPal receipt FOR a recurring subscription service

INVALID emails (return confidence_score: 0.0):
❌ New device access notifications
❌ Password reset/security alerts
❌ Service usage notifications (even from subscription services)
❌ One-time purchases/gifts (even if to a subscription service)
❌ General service emails without subscription context
❌ "Typically associated with" reasoning - need EXPLICIT evidence

EXAMPLES OF FALSE POSITIVES TO AVOID:
❌ "Your Crunchyroll account accessed from new device" - NO subscription evidence
❌ "AWS Lambda end of support notification" - NO payment/billing information
❌ "Gift $25 to PayPal" - One-time gift, NOT recurring subscription
❌ "Delivery from service X" - Transaction, NOT subscription

Email Details:
Subject: {subject}
From: {sender} ({sender_name})
Date: {date}

Full Body:
{body}

Headers (if relevant):
{headers}

DECISION PROCESS:
1. Does email contain price AND billing cycle? → Extract
2. Does email mention subscription renewal/payment? → Extract
3. Does email only mention service name without subscription context? → confidence_score: 0.0
4. Is this a one-time transaction/gift/notification? → confidence_score: 0.0

TRIAL DETECTION (CRITICAL):
- Check for trial indicators: "trial", "free trial", "trial period", "complimentary", "try free", "trial ends", "trial expires"
- Extract trial end date if mentioned: "trial ends on [date]", "trial period: X days", "complimentary access until [date]"
- If trial detected AND only first email: this is likely a trial signup (not a paid subscription yet)

PRICE UPDATE DETECTION (CRITICAL):
- Check for price change indicators: "price increase", "price change", "price adjustment", "new price", "new rate", "pricing update", "rate change", "subscription price", "price will increase", "increasing to", "changing from", "new pricing", "price is changing"
- Extract BOTH amounts if price update detected: old price AND new price
- Look for phrases like: "$X increasing to $Y", "changing from $X to $Y", "new rate of $Y (currently $X)"
- If price update detected: set is_price_update: true, extract old_amount and new_amount
- If NOT a price update: set is_price_update: false, old_amount: null, new_amount: null

CUSTOM LABEL / IDENTIFIER EXTRACTION (CRITICAL):
This field identifies WHICH specific subscription within a service (e.g., which Twitch streamer):
- **Twitch**: Extract streamer/channel name from subject or body (e.g., "xQc", "Pokimane", "Asmongold")
  - Look for: "to [streamer]", "subscription to [streamer]", "[streamer]'s channel", streamer name in subject
  - Example: "Subscription to xQc - Tier 3" → custom_label: "xQc"
- **Patreon**: Extract creator name (e.g., "John Doe", "Artist Name")
  - Look for: "supporting [creator]", "[creator]'s Patreon", creator name mentioned
- **YouTube Memberships**: Extract channel name
- **OnlyFans**: Extract creator name
- **Other services**: Any identifying info that makes this subscription unique
  - For services where multiple subscriptions are common (gaming platforms, content creators)
  - Leave null if no distinguishing information exists or service typically has only one subscription per user

Extract the following information and respond ONLY with a JSON object:
{{
    "provider": "Service name ONLY if subscription evidence found, else null",
    "amount": decimal number ONLY if explicitly stated (CRITICAL: Use TOTAL amount including taxes, NOT subtotal), else null,
    "currency": "USD|EUR|GBP etc ONLY if amount found, else null",
    "billing_cycle": "monthly|yearly|weekly ONLY if explicitly stated, else null",
    "renewal_date": "YYYY-MM-DD ONLY if explicitly mentioned, else null",
    "description": "Brief description or null",
    "custom_label": "For Twitch/Patreon/YouTube: streamer/creator/channel name. For others: identifying info that distinguishes this from other subscriptions of same provider, else null",
    "category": "streaming|software|storage|productivity|entertainment|fitness|gaming|news|education|communication|finance|shopping|music|other",
    "payment_method_last4": "last 4 digits ONLY if shown, else null",
    "confidence_score": 0.0-1.0 (MUST be 0.0 without EXPLICIT subscription evidence),
    "extraction_method": "gpt-4o-mini",
    "trial_detected": true if trial keywords found, else false,
    "trial_end_date": "YYYY-MM-DD ONLY if trial end date explicitly mentioned, else null",
    "trial_keywords_found": ["list", "of", "trial", "keywords", "found"] or [],
    "is_price_update": true if price change detected, else false,
    "old_amount": decimal number for current/old price ONLY if price update detected, else null,
    "new_amount": decimal number for new price ONLY if price update detected, else null,
    "raw_email_data": {{
        "subject": "original subject",
        "sender": "sender email",
        "date": "original date"
    }}
}}

AMOUNT EXTRACTION RULES:
- If email shows both SUBTOTAL and TOTAL (with taxes/VAT): extract the TOTAL amount
- Keywords indicating total: "Total payé", "Total paid", "Amount charged", "Total", "Grand total"
- Keywords indicating subtotal: "Subtotal", "Sous-total", "Before tax", "Excluding VAT"
- Always prefer the final amount that was actually charged to the payment method

Rules:
- Return confidence_score: 0.0 if NO explicit subscription evidence
- "Typically associated with subscription" is NOT evidence - need actual proof
- Gifts, one-time transactions, service notifications = confidence_score: 0.0
- Be EXTREMELY conservative - when in doubt, return 0.0"""


async def extract_subscription_data(
    email: EmailMessage, db: Optional[Session] = None
) -> Optional[Dict[str, Any]]:
    """
    Extract structured subscription information from an email.

    Args:
        email: EmailMessage object classified as subscription-related
        db: Optional database session to check admin settings

    Returns:
        Dict with subscription data or None if extraction fails
    """
    try:
        # Get OpenAI client with admin settings support
        client = get_openai_client(db)

        # Prepare email content with smart cleaning and truncation
        body = get_optimized_email_body(
            body_text=email.body_text,
            body_html=email.body_html,
            mode="extraction",  # Uses 2500 char limit with key info extraction
        )

        # Format relevant headers
        relevant_headers = {
            k: v
            for k, v in email.headers.items()
            if k.lower() in ["list-unsubscribe", "x-service-name", "x-subscription-id"]
        }

        prompt = EXTRACTION_PROMPT.format(
            subject=email.subject,
            sender=email.sender,
            sender_name=email.sender_name or "Unknown",
            date=email.date.isoformat(),
            body=body[:3000],  # Limit to 3000 chars for context
            headers=(
                json.dumps(relevant_headers, indent=2) if relevant_headers else "None"
            ),
        )

        logger.info(f"Extracting subscription data from: {email.subject}")

        # Call OpenAI API
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise data extraction assistant. Always respond with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,  # Very low temperature for consistent extraction
            max_tokens=800,
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

            extracted = json.loads(result_text)

            # Validate and clean extracted data
            cleaned = clean_extracted_data(extracted)

            # Only return if we have minimum required fields
            if cleaned.get("provider") and cleaned.get("confidence_score", 0) > 0.5:
                logger.info(f"Extracted subscription: {cleaned['provider']}")
                return cleaned
            else:
                logger.warning(
                    f"Extraction confidence too low or missing provider: {cleaned}"
                )
                return None

        except json.JSONDecodeError:
            logger.error(f"Failed to parse extraction response as JSON: {result_text}")
            return None

    except Exception as e:
        logger.error(f"Error extracting subscription data: {str(e)}")
        return None


def clean_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and validate extracted subscription data.
    """
    cleaned = {}

    # Required string fields
    cleaned["provider"] = str(data.get("provider", "")).strip() or None
    cleaned["custom_label"] = (
        str(data.get("description", "")).strip() or None
    )  # Map description to custom_label

    # Currency - validate it's a proper 3-letter ISO code or NULL
    currency = str(data.get("currency", "")).upper().strip()
    if currency in ("NONE", "NULL", "") or len(currency) != 3:
        cleaned["currency"] = None
    else:
        cleaned["currency"] = currency[:3]  # Ensure max 3 chars

    cleaned["billing_cycle"] = str(data.get("billing_cycle", "")).lower() or None

    # Category - validate against allowed list, default to 'other' for unknown
    ALLOWED_CATEGORIES = [
        "streaming",
        "software",
        "storage",
        "productivity",
        "entertainment",
        "fitness",
        "gaming",
        "news",
        "education",
        "communication",
        "finance",
        "shopping",
        "music",
        "other",
    ]
    category = str(data.get("category", "other")).lower().strip()
    cleaned["category"] = category if category in ALLOWED_CATEGORIES else "other"

    cleaned["extraction_method"] = str(data.get("extraction_method", "gpt-4o-mini"))

    # Payment processor metadata (JSONB)
    payment_method_last4 = str(data.get("payment_method_last4", "")).strip() or None
    if payment_method_last4:
        cleaned["payment_processor"] = {
            "last4": payment_method_last4,
            "extracted_at": datetime.now().isoformat(),
        }

    # Amount (Decimal)
    amount = data.get("amount")
    if amount is not None:
        try:
            cleaned["amount"] = float(
                amount
            )  # SQLAlchemy Numeric will handle conversion
        except (ValueError, TypeError):
            cleaned["amount"] = None
    else:
        cleaned["amount"] = None

    # Confidence score
    confidence = data.get("confidence_score", 0.0)
    try:
        cleaned["confidence_score"] = float(confidence)
        cleaned["confidence_score"] = max(0.0, min(1.0, cleaned["confidence_score"]))
    except (ValueError, TypeError):
        cleaned["confidence_score"] = 0.5

    # Renewal date
    renewal_date = data.get("renewal_date")
    if renewal_date and renewal_date != "null":
        try:
            cleaned["renewal_date"] = datetime.fromisoformat(
                str(renewal_date).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            cleaned["renewal_date"] = None
    else:
        cleaned["renewal_date"] = None

    # Email sender (for tracking)
    email_sender = data.get("raw_email_data", {}).get("sender")
    if email_sender:
        cleaned["email_sender"] = email_sender

    # Trial detection
    trial_detected = data.get("trial_detected", False)
    if trial_detected:
        # Store trial metadata in extraction_metadata
        trial_keywords = data.get("trial_keywords_found", [])
        cleaned["extraction_metadata"] = {
            "trial_detected": True,
            "trial_keywords": trial_keywords,
            "detected_at": datetime.now().isoformat(),
        }

        # Extract trial end date
        trial_end_date = data.get("trial_end_date")
        if trial_end_date and trial_end_date != "null":
            try:
                cleaned["trial_end_date"] = datetime.fromisoformat(
                    str(trial_end_date).replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                cleaned["trial_end_date"] = None
        else:
            cleaned["trial_end_date"] = None
    else:
        cleaned["extraction_metadata"] = None
        cleaned["trial_end_date"] = None

    # Price update detection
    is_price_update = data.get("is_price_update", False)
    cleaned["is_price_update"] = bool(is_price_update)

    if is_price_update:
        # Extract old amount
        old_amount = data.get("old_amount")
        if old_amount is not None:
            try:
                cleaned["old_amount"] = float(old_amount)
            except (ValueError, TypeError):
                cleaned["old_amount"] = None
        else:
            cleaned["old_amount"] = None

        # Extract new amount
        new_amount = data.get("new_amount")
        if new_amount is not None:
            try:
                cleaned["new_amount"] = float(new_amount)
            except (ValueError, TypeError):
                cleaned["new_amount"] = None
        else:
            cleaned["new_amount"] = None
    else:
        cleaned["old_amount"] = None
        cleaned["new_amount"] = None

    return cleaned


async def extract_subscription_data_with_retry(
    email: EmailMessage,
    db: Optional[Session] = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """
    Extract subscription data with exponential backoff retry on failures.

    Args:
        email: EmailMessage to extract from
        db: Database session
        max_retries: Maximum retry attempts (default 3)
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        Extracted data or None on permanent failure
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            # Attempt extraction
            result = await extract_subscription_data(email, db)
            return result

        except RateLimitError as e:
            # 429 Rate Limit - need to back off
            last_exception = e
            if attempt < max_retries - 1:
                # Exponential backoff: 2s, 4s, 8s
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Rate limit hit extracting '{email.subject}'. "
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
                    f"API error extracting '{email.subject}': {e}. "
                    f"Retrying in {delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"API error after {max_retries} retries for '{email.subject}': {e}"
                )

        except Exception as e:
            # Unexpected errors - log and return None
            logger.error(f"Unexpected error extracting '{email.subject}': {e}")
            last_exception = e
            break

    # If all retries failed, return None
    logger.error(
        f"Extraction failed for '{email.subject}' after {max_retries} retries: {str(last_exception)}"
    )
    return None


async def extract_subscriptions_batch(
    emails: List[EmailMessage],
    db: Optional[Session] = None,
    initial_batch_size: int = 10,
    min_batch_size: int = 2,
) -> List[Optional[Dict[str, Any]]]:
    """
    Extract subscription data from multiple emails with adaptive batch sizing.

    Processes emails in parallel batches with automatic rate limit handling
    and adaptive batch size adjustment.

    Args:
        emails: List of EmailMessage objects to extract from
        db: Database session
        initial_batch_size: Starting batch size for parallel processing
        min_batch_size: Minimum batch size when rate limited

    Returns:
        List of extraction results (or None) matching input email order
    """
    all_results = []
    current_batch_size = initial_batch_size
    consecutive_rate_limits = 0

    i = 0
    while i < len(emails):
        # Get current batch
        batch = emails[i : i + current_batch_size]

        logger.info(
            f"Extracting batch: {len(batch)} emails "
            f"(position {i}/{len(emails)}, batch_size={current_batch_size})"
        )

        # Process batch in parallel with retry logic
        tasks = [extract_subscription_data_with_retry(email, db) for email in batch]

        try:
            # Execute all tasks concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for rate limit errors in results
            rate_limit_count = sum(
                1 for r in batch_results if isinstance(r, Exception) or r is None
            )

            # Process results
            for email, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to extract '{email.subject}': {result}")
                    all_results.append(None)
                else:
                    all_results.append(result)

            # Adaptive batch size adjustment
            if rate_limit_count > 0:
                consecutive_rate_limits += 1

                # Reduce batch size if hitting rate limits frequently
                if consecutive_rate_limits >= 2 and current_batch_size > min_batch_size:
                    current_batch_size = max(min_batch_size, current_batch_size // 2)
                    logger.warning(
                        f"Rate limits detected. Reducing extraction batch size to {current_batch_size}"
                    )

                # Longer sleep after rate limits
                await asyncio.sleep(5.0)
            else:
                # No rate limits - can try increasing batch size
                consecutive_rate_limits = 0

                if current_batch_size < initial_batch_size:
                    current_batch_size = min(initial_batch_size, current_batch_size + 2)
                    logger.info(
                        f"Increasing extraction batch size to {current_batch_size}"
                    )

                # Normal sleep between batches
                await asyncio.sleep(1.0)

            # Move to next batch
            i += len(batch)

        except Exception as e:
            logger.error(f"Batch extraction error: {e}")
            # On catastrophic batch failure, process emails one-by-one
            logger.warning("Falling back to sequential extraction for this batch")
            for email in batch:
                result = await extract_subscription_data_with_retry(email, db)
                all_results.append(result)
                await asyncio.sleep(2.0)

            i += len(batch)

    successful_extractions = sum(1 for r in all_results if r is not None)
    logger.info(
        f"Extracted {successful_extractions}/{len(all_results)} emails successfully"
    )
    return all_results
