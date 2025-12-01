"""Configuration package for provider patterns and other config files."""

from app.config.provider_patterns import (
    extract_service_references,
    get_provider_patterns,
    format_custom_label,
    PROVIDER_PATTERNS,
    GENERIC_PATTERNS,
)

__all__ = [
    "extract_service_references",
    "get_provider_patterns",
    "format_custom_label",
    "PROVIDER_PATTERNS",
    "GENERIC_PATTERNS",
]
