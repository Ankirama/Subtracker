"""
Service reference extraction service.

Combines regex pattern matching with AI context understanding to extract
service-specific identifiers from subscription emails.
"""

from typing import Dict, Optional, Any
import logging
from openai import OpenAI

from app.config import settings
from app.provider_config.provider_patterns import (
    extract_service_references,
    format_custom_label,
)

logger = logging.getLogger(__name__)


class ReferenceExtractor:
    """Hybrid service reference extractor using regex + AI."""

    def __init__(self):
        """Initialize the reference extractor."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def extract(
        self,
        email_subject: str,
        email_body: str,
        provider: str,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract service references using hybrid regex + AI approach.

        Args:
            email_subject: Email subject line
            email_body: Email body text
            provider: Provider name (e.g., "OVH", "AWS")
            category: Optional service category from AI classification

        Returns:
            Dictionary containing:
            - references: Dict of extracted service references
            - custom_label: Auto-generated label for the service
            - service_type: AI-detected service type
            - extraction_metadata: Full metadata for storage
        """
        try:
            # Step 1: Extract references using regex patterns
            full_text = f"{email_subject}\n\n{email_body}"
            regex_references = extract_service_references(full_text, provider)

            if not regex_references:
                logger.info(
                    f"No service references found via regex for provider: {provider}"
                )
                return {
                    "references": {},
                    "custom_label": "",
                    "service_type": None,
                    "extraction_metadata": {},
                }

            # Step 2: Use AI to understand service type context
            service_type = self._detect_service_type(
                email_subject, email_body, provider, regex_references, category
            )

            # Step 3: Generate custom label
            custom_label = format_custom_label(provider, regex_references, service_type)

            # Step 4: Build comprehensive metadata
            extraction_metadata = {
                "service_references": regex_references,
                "service_type": service_type,
                "provider": provider,
                "extraction_method": "hybrid_regex_ai",
                "patterns_matched": list(regex_references.keys()),
            }

            return {
                "references": regex_references,
                "custom_label": custom_label,
                "service_type": service_type,
                "extraction_metadata": extraction_metadata,
            }

        except Exception as e:
            logger.error(f"Error extracting service references: {e}", exc_info=True)
            return {
                "references": {},
                "custom_label": "",
                "service_type": None,
                "extraction_metadata": {"error": str(e)},
            }

    def _detect_service_type(
        self,
        subject: str,
        body: str,
        provider: str,
        references: Dict[str, str],
        category: Optional[str] = None,
    ) -> Optional[str]:
        """
        Use AI to detect the specific service type from email context.

        Args:
            subject: Email subject
            body: Email body
            provider: Provider name
            references: Already extracted service references
            category: Optional pre-classified category

        Returns:
            Detected service type (e.g., "VPS", "Domain", "Cloud Storage")
        """
        try:
            # Build context from extracted references
            references_context = "\n".join(
                [f"- {key}: {value}" for key, value in references.items()]
            )

            prompt = f"""Analyze this {provider} subscription email and identify the SPECIFIC SERVICE TYPE.

Email Subject: {subject}

Email Body (first 500 chars): {body[:500]}

Extracted Service References:
{references_context}

Category (if known): {category or 'Unknown'}

Based on the email content and service references, what SPECIFIC type of service is this?
For {provider}, common types include:
- VPS (Virtual Private Server)
- Dedicated Server
- Domain Registration
- Domain Renewal
- Web Hosting
- Cloud Storage
- DNS Service
- Email Hosting
- SSL Certificate

Respond with ONLY the service type (2-4 words maximum). Examples:
- "VPS"
- "Domain Renewal"
- "Cloud Storage"
- "Web Hosting"

Service Type:"""

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=20,
            )

            service_type = response.choices[0].message.content.strip()
            logger.info(
                f"AI detected service type: {service_type} for provider: {provider}"
            )
            return service_type

        except Exception as e:
            logger.error(f"Error detecting service type with AI: {e}", exc_info=True)
            return None

    def can_match_subscription(
        self, references: Dict[str, str], existing_metadata: Dict[str, Any]
    ) -> bool:
        """
        Check if extracted references match an existing subscription.

        Args:
            references: Newly extracted service references
            existing_metadata: extraction_metadata from existing subscription

        Returns:
            True if references match, False otherwise
        """
        if not references or not existing_metadata:
            return False

        existing_refs = existing_metadata.get("service_references", {})
        if not existing_refs:
            return False

        # Check if any reference matches
        for key, value in references.items():
            if key in existing_refs and existing_refs[key] == value:
                logger.info(f"Found matching service reference: {key}={value}")
                return True

        return False

    def find_matching_subscription(
        self,
        references: Dict[str, str],
        provider: str,
        user_subscriptions: list,
    ) -> Optional[Any]:
        """
        Find an existing subscription matching the service references.

        Args:
            references: Extracted service references
            provider: Provider name
            user_subscriptions: List of user's subscriptions for this provider

        Returns:
            Matching subscription object or None
        """
        if not references:
            return None

        for subscription in user_subscriptions:
            # Check if subscription is from same provider
            if subscription.provider.lower() != provider.lower():
                continue

            # Check extraction metadata for matching references
            metadata = subscription.extraction_metadata or {}
            if self.can_match_subscription(references, metadata):
                logger.info(
                    f"Found matching subscription: {subscription.id} for references: {references}"
                )
                return subscription

        logger.info(
            f"No matching subscription found for provider: {provider}, references: {references}"
        )
        return None


# Singleton instance
_extractor_instance = None


def get_reference_extractor() -> ReferenceExtractor:
    """Get or create the reference extractor singleton."""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ReferenceExtractor()
    return _extractor_instance
