"""
Configuration helper that prioritizes admin settings over environment variables.

This allows runtime configuration changes through the admin panel without
requiring application restarts.
"""
from typing import Optional, Any
from functools import lru_cache
import logging

from app.config import settings
from app.models.admin import AdminSetting
from app.utils.encryption import encryption_service

logger = logging.getLogger(__name__)


class ConfigHelper:
    """Helper to get configuration values from admin settings or environment."""

    def __init__(self, db_session=None):
        """
        Initialize config helper.

        Args:
            db_session: SQLAlchemy session for database queries (optional)
        """
        self.db = db_session

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with priority: admin settings > env vars > default.

        Args:
            key: Configuration key (e.g., 'sendgrid.api_key', 'openai.api_key')
            default: Default value if not found

        Returns:
            Configuration value
        """
        # Try admin settings first (if db session available)
        if self.db:
            try:
                admin_setting = self.db.query(AdminSetting).filter(
                    AdminSetting.key == key
                ).first()

                if admin_setting:
                    value = admin_setting.value

                    # Decrypt if secret
                    if admin_setting.is_secret and isinstance(value, str):
                        try:
                            value = encryption_service.decrypt(value)
                        except Exception as e:
                            logger.error(f"Failed to decrypt setting {key}: {e}")
                            # Fall through to env var

                    logger.info(f"Using admin setting for {key}")
                    return value
            except Exception as e:
                logger.warning(f"Error fetching admin setting {key}: {e}")
                # Fall through to env var

        # Fall back to environment variables
        env_mapping = {
            'sendgrid.api_key': settings.SENDGRID_API_KEY,
            'sendgrid.from_email': settings.SENDGRID_FROM_EMAIL,
            'sendgrid.from_name': settings.SENDGRID_FROM_NAME,
            'openai.api_key': settings.OPENAI_API_KEY,
            'openai.assistant_id': settings.OPENAI_ASSISTANT_ID,
        }

        env_value = env_mapping.get(key)
        if env_value is not None:
            logger.debug(f"Using environment variable for {key}")
            return env_value

        logger.debug(f"Using default value for {key}")
        return default


def get_config_value(key: str, default: Any = None, db_session=None) -> Any:
    """
    Convenience function to get a config value.

    Args:
        key: Configuration key
        default: Default value if not found
        db_session: Optional database session

    Returns:
        Configuration value
    """
    helper = ConfigHelper(db_session)
    return helper.get_config(key, default)
