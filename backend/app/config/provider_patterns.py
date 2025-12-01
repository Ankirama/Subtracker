"""
Provider-specific extraction patterns for service reference detection.

This module defines regex patterns and extraction rules for different providers
to reliably identify service-specific identifiers (like OVH service codes, AWS account IDs, etc.)
that help differentiate multiple subscriptions from the same provider.
"""

from typing import Dict, List, TypedDict
import re


class PatternRule(TypedDict):
    """Type definition for a pattern extraction rule."""

    name: str  # Identifier for this pattern (e.g., "service_code", "domain")
    pattern: str  # Regex pattern to match
    description: str  # Human-readable description
    priority: int  # Higher priority patterns are checked first (default: 100)
    context_hint: str  # Optional hint for AI about what this pattern represents


# Provider-specific patterns
# Each provider can have multiple patterns to extract different types of identifiers
PROVIDER_PATTERNS: Dict[str, List[PatternRule]] = {
    "OVH": [
        {
            "name": "service_code",
            "pattern": r"\b(FR\d{8})\b",
            "description": "OVH service reference code (FR + 8 digits)",
            "priority": 200,
            "context_hint": "OVH service identifier like FR73880615"
        },
        {
            "name": "domain",
            "pattern": r"\b([a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,})\b",
            "description": "Domain name",
            "priority": 100,
            "context_hint": "Domain name being managed or renewed"
        },
    ],

    "AWS": [
        {
            "name": "account_id",
            "pattern": r"\b(\d{12})\b",
            "description": "AWS 12-digit account ID",
            "priority": 200,
            "context_hint": "AWS account identifier"
        },
        {
            "name": "service_name",
            "pattern": r"\b(EC2|S3|RDS|Lambda|DynamoDB|CloudFront|Route53|ECS|EKS)\b",
            "description": "AWS service name",
            "priority": 150,
            "context_hint": "Specific AWS service being used"
        },
    ],

    "Google Cloud": [
        {
            "name": "project_id",
            "pattern": r"\b([a-z][a-z0-9\-]{4,28}[a-z0-9])\b",
            "description": "Google Cloud project ID",
            "priority": 200,
            "context_hint": "GCP project identifier"
        },
    ],

    "Azure": [
        {
            "name": "subscription_id",
            "pattern": r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\b",
            "description": "Azure subscription UUID",
            "priority": 200,
            "context_hint": "Azure subscription GUID"
        },
    ],

    "Namecheap": [
        {
            "name": "domain",
            "pattern": r"\b([a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,})\b",
            "description": "Domain name",
            "priority": 150,
            "context_hint": "Domain being registered or renewed"
        },
    ],

    "GoDaddy": [
        {
            "name": "domain",
            "pattern": r"\b([a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,})\b",
            "description": "Domain name",
            "priority": 150,
            "context_hint": "Domain being managed"
        },
    ],

    "Cloudflare": [
        {
            "name": "zone_id",
            "pattern": r"\b([a-f0-9]{32})\b",
            "description": "Cloudflare zone ID",
            "priority": 200,
            "context_hint": "Cloudflare zone identifier"
        },
        {
            "name": "domain",
            "pattern": r"\b([a-z0-9][a-z0-9\-]{0,61}[a-z0-9]?\.[a-z]{2,})\b",
            "description": "Domain name",
            "priority": 150,
            "context_hint": "Domain being protected"
        },
    ],

    "Twitch": [
        {
            "name": "channel_name",
            "pattern": r"(?:twitch\.tv/|@)([a-zA-Z0-9_]{3,25})\b",
            "description": "Twitch channel name",
            "priority": 200,
            "context_hint": "Twitch channel or streamer name"
        },
    ],

    "Discord": [
        {
            "name": "server_id",
            "pattern": r"\b(\d{17,19})\b",
            "description": "Discord server ID",
            "priority": 150,
            "context_hint": "Discord server/guild identifier"
        },
    ],
}


# Generic patterns that apply to all providers (lower priority)
GENERIC_PATTERNS: List[PatternRule] = [
    {
        "name": "invoice_number",
        "pattern": r"\b(?:invoice|bill|receipt)[#\s:-]*([A-Z0-9\-]{6,})\b",
        "description": "Invoice/receipt number",
        "priority": 50,
        "context_hint": "Invoice or receipt identifier"
    },
    {
        "name": "order_number",
        "pattern": r"\b(?:order|transaction)[#\s:-]*([A-Z0-9\-]{6,})\b",
        "description": "Order/transaction number",
        "priority": 50,
        "context_hint": "Order or transaction identifier"
    },
]


def extract_service_references(
    text: str,
    provider: str,
) -> Dict[str, str]:
    """
    Extract service-specific references from email text using provider patterns.

    Args:
        text: Email body or subject to analyze
        provider: Provider name (e.g., "OVH", "AWS")

    Returns:
        Dictionary mapping pattern names to extracted values
        Example: {"service_code": "FR73880615", "domain": "example.com"}
    """
    references = {}

    # Normalize provider name for case-insensitive matching
    provider_normalized = provider.strip() if provider else ""

    # Get provider-specific patterns
    patterns = []
    for provider_key, provider_patterns in PROVIDER_PATTERNS.items():
        if provider_key.lower() in provider_normalized.lower():
            patterns.extend(provider_patterns)
            break

    # Add generic patterns with lower priority
    patterns.extend(GENERIC_PATTERNS)

    # Sort by priority (highest first)
    patterns.sort(key=lambda p: p.get("priority", 100), reverse=True)

    # Extract matches for each pattern
    for pattern_rule in patterns:
        pattern = pattern_rule["pattern"]
        name = pattern_rule["name"]

        # Skip if we already found a value for this pattern name
        if name in references:
            continue

        # Try to find matches
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Use first capture group if available, otherwise use full match
            value = match.group(1) if match.groups() else match.group(0)
            value = value.strip()

            if value and len(value) > 2:  # Minimum length filter
                references[name] = value
                break  # Take first match for this pattern

    return references


def get_provider_patterns(provider: str) -> List[PatternRule]:
    """
    Get all extraction patterns for a specific provider.

    Args:
        provider: Provider name

    Returns:
        List of pattern rules for the provider
    """
    provider_normalized = provider.strip().lower() if provider else ""

    for provider_key, patterns in PROVIDER_PATTERNS.items():
        if provider_key.lower() in provider_normalized:
            return patterns

    return []


def format_custom_label(
    provider: str,
    references: Dict[str, str],
    service_type: str = None
) -> str:
    """
    Generate a smart custom label from extracted references.

    Args:
        provider: Provider name
        references: Extracted service references
        service_type: Optional AI-detected service type

    Returns:
        Formatted custom label string
        Example: "VPS - FR73880615" or "Domain: example.com"
    """
    if not references:
        return ""

    # Provider-specific formatting logic
    provider_lower = provider.lower() if provider else ""

    if "ovh" in provider_lower:
        # OVH: Prefer "Service Type - Code" or "Domain: name"
        if "service_code" in references:
            service_prefix = service_type.upper() if service_type else "Service"
            return f"{service_prefix} - {references['service_code']}"
        elif "domain" in references:
            return f"Domain: {references['domain']}"

    elif "aws" in provider_lower:
        # AWS: Prefer "Service - Account" format
        parts = []
        if "service_name" in references:
            parts.append(references["service_name"])
        if "account_id" in references:
            parts.append(f"Account {references['account_id'][:8]}...")
        if parts:
            return " - ".join(parts)

    elif any(x in provider_lower for x in ["namecheap", "godaddy", "cloudflare"]):
        # Domain providers: "Domain: example.com"
        if "domain" in references:
            return f"Domain: {references['domain']}"

    elif "twitch" in provider_lower:
        # Twitch: "Channel: username"
        if "channel_name" in references:
            return f"Channel: {references['channel_name']}"

    # Generic fallback: Use first available reference
    for key, value in references.items():
        if key != "invoice_number" and key != "order_number":  # Prefer non-generic
            return f"{key.replace('_', ' ').title()}: {value}"

    # Absolute fallback
    first_key = next(iter(references))
    return f"{first_key.replace('_', ' ').title()}: {references[first_key]}"
