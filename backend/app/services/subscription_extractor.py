"""
AI-powered subscription data extraction service.
Uses OpenAI GPT to extract structured subscription information from emails.
"""
from openai import AsyncOpenAI
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
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

Extract the following information and respond ONLY with a JSON object:
{{
    "provider": "Service name ONLY if subscription evidence found, else null",
    "amount": decimal number ONLY if explicitly stated (CRITICAL: Use TOTAL amount including taxes, NOT subtotal), else null,
    "currency": "USD|EUR|GBP etc ONLY if amount found, else null",
    "billing_cycle": "monthly|yearly|weekly ONLY if explicitly stated, else null",
    "renewal_date": "YYYY-MM-DD ONLY if explicitly mentioned, else null",
    "description": "Brief description or null",
    "category": "streaming|software|storage|productivity|entertainment|fitness|gaming|news|education|communication|finance|shopping|music|other",
    "payment_method_last4": "last 4 digits ONLY if shown, else null",
    "confidence_score": 0.0-1.0 (MUST be 0.0 without EXPLICIT subscription evidence),
    "extraction_method": "gpt-4o-mini",
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
    email: EmailMessage,
    db: Optional[Session] = None
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

        # Prepare email content
        body = email.body_text or email.body_html or ""

        # Format relevant headers
        relevant_headers = {
            k: v for k, v in email.headers.items()
            if k.lower() in ['list-unsubscribe', 'x-service-name', 'x-subscription-id']
        }

        prompt = EXTRACTION_PROMPT.format(
            subject=email.subject,
            sender=email.sender,
            sender_name=email.sender_name or "Unknown",
            date=email.date.isoformat(),
            body=body[:3000],  # Limit to 3000 chars for context
            headers=json.dumps(relevant_headers, indent=2) if relevant_headers else "None"
        )

        logger.info(f"Extracting subscription data from: {email.subject}")

        # Call OpenAI API
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise data extraction assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Very low temperature for consistent extraction
            max_tokens=800
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
            if cleaned.get('provider') and cleaned.get('confidence_score', 0) > 0.5:
                logger.info(f"Extracted subscription: {cleaned['provider']}")
                return cleaned
            else:
                logger.warning(f"Extraction confidence too low or missing provider: {cleaned}")
                return None
                
        except json.JSONDecodeError as e:
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
    cleaned['provider'] = str(data.get('provider', '')).strip() or None
    cleaned['custom_label'] = str(data.get('description', '')).strip() or None  # Map description to custom_label

    # Currency - validate it's a proper 3-letter ISO code or NULL
    currency = str(data.get('currency', '')).upper().strip()
    if currency in ('NONE', 'NULL', '') or len(currency) != 3:
        cleaned['currency'] = None
    else:
        cleaned['currency'] = currency[:3]  # Ensure max 3 chars

    cleaned['billing_cycle'] = str(data.get('billing_cycle', '')).lower() or None

    # Category - validate against allowed list, default to 'other' for unknown
    ALLOWED_CATEGORIES = [
        'streaming', 'software', 'storage', 'productivity', 'entertainment',
        'fitness', 'gaming', 'news', 'education', 'communication', 'finance', 'shopping', 'music', 'other'
    ]
    category = str(data.get('category', 'other')).lower().strip()
    cleaned['category'] = category if category in ALLOWED_CATEGORIES else 'other'

    cleaned['extraction_method'] = str(data.get('extraction_method', 'gpt-4o-mini'))

    # Payment processor metadata (JSONB)
    payment_method_last4 = str(data.get('payment_method_last4', '')).strip() or None
    if payment_method_last4:
        cleaned['payment_processor'] = {
            'last4': payment_method_last4,
            'extracted_at': datetime.now().isoformat()
        }
    
    # Amount (Decimal)
    amount = data.get('amount')
    if amount is not None:
        try:
            cleaned['amount'] = float(amount)  # SQLAlchemy Numeric will handle conversion
        except (ValueError, TypeError):
            cleaned['amount'] = None
    else:
        cleaned['amount'] = None
    
    # Confidence score
    confidence = data.get('confidence_score', 0.0)
    try:
        cleaned['confidence_score'] = float(confidence)
        cleaned['confidence_score'] = max(0.0, min(1.0, cleaned['confidence_score']))
    except (ValueError, TypeError):
        cleaned['confidence_score'] = 0.5
    
    # Renewal date
    renewal_date = data.get('renewal_date')
    if renewal_date and renewal_date != 'null':
        try:
            cleaned['renewal_date'] = datetime.fromisoformat(str(renewal_date).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            cleaned['renewal_date'] = None
    else:
        cleaned['renewal_date'] = None

    # Email sender (for tracking)
    email_sender = data.get('raw_email_data', {}).get('sender')
    if email_sender:
        cleaned['email_sender'] = email_sender

    return cleaned
