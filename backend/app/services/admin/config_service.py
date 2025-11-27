"""
ConfigService for managing admin settings with encryption support
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List, Any
from uuid import UUID
import uuid
from datetime import datetime

from app.models.admin import AdminSetting, AdminAuditLog
from app.schemas.admin import AdminSettingCreate, AdminSettingUpdate
from app.utils.encryption import encryption_service


class ConfigService:
    """Service for managing admin configuration settings"""

    def __init__(self, db: Session):
        self.db = db

    def get_setting(self, key: str, decrypt: bool = True) -> Optional[AdminSetting]:
        """
        Get a setting by key

        Args:
            key: The setting key
            decrypt: Whether to decrypt secret values (default: True)

        Returns:
            The AdminSetting if found, None otherwise
        """
        setting = self.db.query(AdminSetting).filter(AdminSetting.key == key).first()

        if setting and decrypt and setting.is_secret:
            # Decrypt the value for secret settings
            try:
                decrypted_value = encryption_service.decrypt(str(setting.value))
                # Create a copy to avoid modifying the DB object
                setting.value = decrypted_value
            except Exception as e:
                # Log decryption error but don't fail
                print(f"Failed to decrypt setting {key}: {e}")

        return setting

    def get_setting_value(
        self, key: str, default: Any = None, decrypt: bool = True
    ) -> Any:
        """
        Get just the value of a setting

        Args:
            key: The setting key
            default: Default value if setting not found
            decrypt: Whether to decrypt secret values

        Returns:
            The setting value or default
        """
        setting = self.get_setting(key, decrypt=decrypt)
        return setting.value if setting else default

    def list_settings(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        decrypt: bool = False,  # Default to False for list operations for security
    ) -> tuple[List[AdminSetting], int]:
        """
        List settings with optional filtering

        Args:
            category: Filter by category
            search: Search in key or description
            page: Page number (1-indexed)
            page_size: Items per page
            decrypt: Whether to decrypt secret values

        Returns:
            Tuple of (settings list, total count)
        """
        query = self.db.query(AdminSetting)

        # Apply filters
        if category:
            query = query.filter(AdminSetting.category == category)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    AdminSetting.key.ilike(search_term),
                    AdminSetting.description.ilike(search_term),
                )
            )

        # Get total count
        total = query.count()

        # Apply pagination
        settings = (
            query.order_by(AdminSetting.category, AdminSetting.key)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        # Decrypt secret values if requested
        if decrypt:
            for setting in settings:
                if setting.is_secret:
                    try:
                        setting.value = encryption_service.decrypt(str(setting.value))
                    except Exception:
                        pass  # Leave encrypted if decryption fails

        return settings, total

    def create_setting(
        self, setting_data: AdminSettingCreate, admin_user_id: UUID
    ) -> AdminSetting:
        """
        Create a new admin setting

        Args:
            setting_data: Setting data
            admin_user_id: ID of the admin creating the setting

        Returns:
            The created AdminSetting
        """
        # Encrypt value if it's a secret
        value = setting_data.value
        if setting_data.is_secret:
            value = encryption_service.encrypt(str(value))

        # Create setting
        setting = AdminSetting(
            id=uuid.uuid4(),
            key=setting_data.key,
            value=value,
            value_type=setting_data.value_type,
            is_secret=setting_data.is_secret,
            description=setting_data.description,
            category=setting_data.category,
            updated_by=admin_user_id,
        )

        self.db.add(setting)
        self.db.commit()
        self.db.refresh(setting)

        # Create audit log
        self._create_audit_log(
            user_id=admin_user_id,
            action="create_setting",
            resource_type="admin_setting",
            resource_id=str(setting.id),
            details={
                "key": setting.key,
                "category": setting.category,
                "is_secret": setting.is_secret,
            },
        )

        return setting

    def update_setting(
        self, key: str, setting_data: AdminSettingUpdate, admin_user_id: UUID
    ) -> Optional[AdminSetting]:
        """
        Update an existing setting

        Args:
            key: The setting key
            setting_data: Updated setting data
            admin_user_id: ID of the admin updating the setting

        Returns:
            The updated AdminSetting if found, None otherwise
        """
        setting = self.db.query(AdminSetting).filter(AdminSetting.key == key).first()

        if not setting:
            return None

        # Track what changed for audit log
        changes = {}

        # Update fields
        if setting_data.value is not None:
            # Encrypt if secret
            if setting.is_secret or (
                setting_data.is_secret is not None and setting_data.is_secret
            ):
                setting.value = encryption_service.encrypt(str(setting_data.value))
            else:
                setting.value = setting_data.value
            changes["value"] = "updated"

        if setting_data.value_type is not None:
            setting.value_type = setting_data.value_type
            changes["value_type"] = setting_data.value_type

        if setting_data.is_secret is not None:
            # If changing from non-secret to secret, encrypt the value
            if not setting.is_secret and setting_data.is_secret:
                setting.value = encryption_service.encrypt(str(setting.value))
            # If changing from secret to non-secret, decrypt the value
            elif setting.is_secret and not setting_data.is_secret:
                try:
                    setting.value = encryption_service.decrypt(str(setting.value))
                except Exception:
                    pass  # Leave as is if decryption fails
            setting.is_secret = setting_data.is_secret
            changes["is_secret"] = setting_data.is_secret

        if setting_data.description is not None:
            setting.description = setting_data.description
            changes["description"] = "updated"

        if setting_data.category is not None:
            setting.category = setting_data.category
            changes["category"] = setting_data.category

        setting.updated_by = admin_user_id
        setting.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(setting)

        # Create audit log
        self._create_audit_log(
            user_id=admin_user_id,
            action="update_setting",
            resource_type="admin_setting",
            resource_id=str(setting.id),
            details={"key": setting.key, "changes": changes},
        )

        return setting

    def delete_setting(self, key: str, admin_user_id: UUID) -> bool:
        """
        Delete a setting

        Args:
            key: The setting key
            admin_user_id: ID of the admin deleting the setting

        Returns:
            True if deleted, False if not found
        """
        setting = self.db.query(AdminSetting).filter(AdminSetting.key == key).first()

        if not setting:
            return False

        # Create audit log before deletion
        self._create_audit_log(
            user_id=admin_user_id,
            action="delete_setting",
            resource_type="admin_setting",
            resource_id=str(setting.id),
            details={"key": setting.key, "category": setting.category},
        )

        self.db.delete(setting)
        self.db.commit()

        return True

    def _create_audit_log(
        self,
        user_id: UUID,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "info",
    ) -> None:
        """
        Create an audit log entry

        Args:
            user_id: ID of the user performing the action
            action: Action performed
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            details: Additional details
            severity: Severity level
        """
        audit_log = AdminAuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            severity=severity,
        )

        self.db.add(audit_log)
        self.db.commit()
