"""
Internationalization utilities for backend.
"""

from typing import Optional
from app.models.user import User


SUPPORTED_LANGUAGES = ["en", "fr"]
DEFAULT_LANGUAGE = "en"


def get_user_language(user: Optional[User], accept_language: Optional[str] = None) -> str:
    """
    Get the appropriate language for a user.

    Priority order:
    1. User's preferred_language from database (if authenticated)
    2. Accept-Language header from request
    3. Default language (English)

    Args:
        user: Optional authenticated user
        accept_language: Optional Accept-Language header value

    Returns:
        Language code ('en' or 'fr')
    """
    # Check user preference first
    if user and user.preferred_language:
        if user.preferred_language in SUPPORTED_LANGUAGES:
            return user.preferred_language

    # Check Accept-Language header
    if accept_language:
        # Parse Accept-Language header (e.g., "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7")
        languages = accept_language.lower().split(",")
        for lang_spec in languages:
            # Extract just the language code (ignore region and quality)
            lang = lang_spec.split(";")[0].split("-")[0].strip()
            if lang in SUPPORTED_LANGUAGES:
                return lang

    # Fall back to default
    return DEFAULT_LANGUAGE


def detect_browser_language(accept_language: Optional[str]) -> Optional[str]:
    """
    Detect browser language from Accept-Language header.

    Args:
        accept_language: Accept-Language header value

    Returns:
        Detected language code or None if not supported
    """
    if not accept_language:
        return None

    languages = accept_language.lower().split(",")
    for lang_spec in languages:
        lang = lang_spec.split(";")[0].split("-")[0].strip()
        if lang in SUPPORTED_LANGUAGES:
            return lang

    return None


# Translation dictionaries for backend strings
# These are simple key-value translations for backend use (emails, notifications, etc.)
# Frontend uses react-i18next with JSON files

TRANSLATIONS = {
    "en": {
        "email.welcome_subject": "Welcome to Subscription Tracker!",
        "email.verification_subject": "Verify your email address",
        "email.password_reset_subject": "Reset your password",
        "notification.renewal_reminder": "Your {provider} subscription renews in {days} days",
        "notification.price_change": "Price change detected for {provider}",
    },
    "fr": {
        "email.welcome_subject": "Bienvenue sur Suivi d'Abonnements !",
        "email.verification_subject": "Vérifiez votre adresse email",
        "email.password_reset_subject": "Réinitialisez votre mot de passe",
        "notification.renewal_reminder": "Votre abonnement {provider} se renouvelle dans {days} jours",
        "notification.price_change": "Changement de prix détecté pour {provider}",
    },
}


def translate(key: str, language: str = DEFAULT_LANGUAGE, **kwargs) -> str:
    """
    Get translated string for a key.

    Args:
        key: Translation key (e.g., "email.welcome_subject")
        language: Language code
        **kwargs: Format arguments for string interpolation

    Returns:
        Translated string with format arguments applied
    """
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE

    translations = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE])
    template = translations.get(key, key)  # Fall back to key if not found

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError):
            return template

    return template
