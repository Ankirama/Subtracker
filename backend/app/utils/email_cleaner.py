"""
Smart email content extraction and cleaning for efficient AI processing.

Reduces token usage by:
1. Converting HTML to clean text
2. Removing signatures, footers, and boilerplate
3. Extracting key subscription indicators
4. Smart truncation preserving important content
"""

import re
from typing import Optional
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


def html_to_text(html: str) -> str:
    """
    Convert HTML email to clean text, preserving important structure.

    Args:
        html: HTML content

    Returns:
        Clean text content
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text
    except Exception as e:
        logger.warning(f"Failed to parse HTML: {e}")
        # Fallback: simple tag removal
        return re.sub(r"<[^>]+>", "", html)


def remove_email_boilerplate(text: str) -> str:
    """
    Remove common email boilerplate, signatures, and footers.

    Args:
        text: Email text content

    Returns:
        Cleaned text without boilerplate
    """
    # Common signature indicators
    signature_patterns = [
        r"\n--+\s*\n.*",  # Standard -- signature delimiter
        r"\nSent from my .*",  # Mobile signatures
        r"\nGet Outlook for .*",
        r"\n(?:Best regards|Regards|Sincerely|Thanks|Thank you)[\s,].*",  # Sign-offs
        r"\nThis email was sent to.*",  # Footer notices
        r"\nTo unsubscribe.*",  # Unsubscribe links
        r"\nYou (?:are )?receiving this (?:email|message).*",  # Receiving notices
        r"\n©\s*\d{4}.*",  # Copyright notices
        r"\nPrivacy Policy.*",  # Privacy links
        r"\nTerms (?:of Service|and Conditions).*",  # Terms links
        r"\nIf you (?:no longer|don\'t) want.*",  # Opt-out text
        r"\nUpdate your (?:email )?preferences.*",  # Preference links
        r"\nView (?:this email )?in (?:your )?browser.*",  # Web view links
    ]

    cleaned = text
    for pattern in signature_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

    # Remove excessive newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def extract_key_indicators(text: str) -> str:
    """
    Extract and highlight key subscription indicators from email content.

    This helps preserve important information during truncation.

    Args:
        text: Email text content

    Returns:
        Text with key indicators extracted to the beginning
    """
    indicators = []

    # Extract monetary amounts with currency
    money_pattern = r"(?:USD|EUR|GBP|CAD|AUD|\$|€|£|¥)\s*\d+(?:[.,]\d{2})?(?:\s*(?:/|per)\s*(?:month|year|mo|yr))?"
    amounts = re.findall(money_pattern, text, re.IGNORECASE)
    if amounts:
        indicators.append(
            "AMOUNTS: " + ", ".join(set(amounts[:5]))
        )  # Top 5 unique amounts

    # Extract dates
    date_pattern = r"\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})\b"
    dates = re.findall(date_pattern, text, re.IGNORECASE)
    if dates:
        indicators.append("DATES: " + ", ".join(set(dates[:3])))  # Top 3 unique dates

    # Extract subscription-related keywords
    subscription_keywords = [
        "subscription",
        "renew",
        "renewal",
        "trial",
        "membership",
        "billing",
        "invoice",
        "payment",
        "charged",
        "auto-renew",
        "plan",
        "premium",
        "upgrade",
        "cancel",
        "expire",
    ]
    found_keywords = [kw for kw in subscription_keywords if kw in text.lower()]
    if found_keywords:
        indicators.append("KEYWORDS: " + ", ".join(found_keywords[:5]))

    # Extract service/company names from subject-like patterns
    # Look for capitalized phrases at the start of lines
    service_pattern = r"^([A-Z][A-Za-z0-9\s&-]{2,30})(?:\s*[-:]\s*|\n)"
    services = re.findall(service_pattern, text, re.MULTILINE)
    if services:
        indicators.append(
            "SERVICES: " + ", ".join(set(s.strip() for s in services[:3]))
        )

    if indicators:
        indicator_block = (
            "[KEY INFO]\n" + "\n".join(indicators) + "\n\n[EMAIL CONTENT]\n"
        )
        return indicator_block + text

    return text


def clean_email_content(
    body_text: Optional[str],
    body_html: Optional[str],
    max_length: int = 2000,
    preserve_key_info: bool = True,
) -> str:
    """
    Clean and prepare email content for AI processing.

    Performs intelligent content extraction and truncation to minimize
    token usage while preserving important subscription information.

    Args:
        body_text: Plain text email body
        body_html: HTML email body
        max_length: Maximum character length for output
        preserve_key_info: Whether to extract and preserve key indicators

    Returns:
        Cleaned and optimized email content
    """
    # Start with text, fall back to HTML
    if body_text:
        content = body_text
    elif body_html:
        content = html_to_text(body_html)
    else:
        return ""

    # Remove boilerplate
    content = remove_email_boilerplate(content)

    # Extract key indicators if enabled
    if preserve_key_info:
        content = extract_key_indicators(content)

    # Smart truncation
    if len(content) > max_length:
        # Try to truncate at sentence boundary
        truncated = content[:max_length]
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")

        # Use sentence or paragraph boundary if close to end
        cutoff = max(last_period, last_newline)
        if cutoff > max_length * 0.8:  # If boundary is in last 20%
            content = truncated[: cutoff + 1]
        else:
            content = truncated + "..."

    return content.strip()


def get_optimized_email_body(
    body_text: Optional[str], body_html: Optional[str], mode: str = "classification"
) -> str:
    """
    Get optimized email body for specific AI processing mode.

    Different modes require different levels of detail:
    - classification: Minimal content needed (1000 chars)
    - extraction: More detail needed (2500 chars)

    Args:
        body_text: Plain text email body
        body_html: HTML email body
        mode: Processing mode ("classification" or "extraction")

    Returns:
        Optimized email content
    """
    if mode == "classification":
        # For classification, we need less detail
        return clean_email_content(
            body_text=body_text,
            body_html=body_html,
            max_length=1000,
            preserve_key_info=True,  # Key info helps with accurate classification
        )
    elif mode == "extraction":
        # For extraction, we need more detail
        return clean_email_content(
            body_text=body_text,
            body_html=body_html,
            max_length=2500,
            preserve_key_info=True,  # Essential for accurate data extraction
        )
    else:
        # Default to extraction mode
        return clean_email_content(
            body_text=body_text,
            body_html=body_html,
            max_length=2000,
            preserve_key_info=True,
        )
