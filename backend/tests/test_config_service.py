"""Comprehensive tests for admin ConfigService"""

import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.services.admin.config_service import ConfigService
from app.models.admin import AdminSetting, AdminAuditLog
from app.models.user import User
from app.schemas.admin import AdminSettingCreate, AdminSettingUpdate


@pytest.fixture
def config_service(db_session: Session) -> ConfigService:
    """Create ConfigService instance"""
    return ConfigService(db_session)


@pytest.fixture
def test_admin_user(test_user: User, db_session: Session) -> User:
    """Create a test admin user from test_user"""
    # Make the test user an admin
    test_user.is_admin = True
    db_session.commit()
    db_session.refresh(test_user)
    return test_user


@pytest.fixture
def test_setting(db_session: Session, test_admin_user: User) -> AdminSetting:
    """Create a test admin setting"""
    setting = AdminSetting(
        id=uuid4(),
        key="test.setting",
        value="test_value",
        value_type="string",
        is_secret=False,
        description="Test setting",
        category="test",
        updated_by=test_admin_user.id,
    )
    db_session.add(setting)
    db_session.commit()
    db_session.refresh(setting)
    return setting


@pytest.fixture
def test_secret_setting(db_session: Session, test_admin_user: User) -> AdminSetting:
    """Create a test secret setting with encrypted value"""
    setting = AdminSetting(
        id=uuid4(),
        key="test.secret",
        value="encrypted_value_placeholder",  # Would be encrypted by encryption service
        value_type="string",
        is_secret=True,
        description="Test secret setting",
        category="api_keys",
        updated_by=test_admin_user.id,
    )
    db_session.add(setting)
    db_session.commit()
    db_session.refresh(setting)
    return setting


class TestGetSetting:
    """Tests for get_setting method"""

    def test_gets_existing_setting(
        self, config_service: ConfigService, test_setting: AdminSetting
    ):
        """Should retrieve an existing setting"""
        result = config_service.get_setting("test.setting")

        assert result is not None
        assert result.key == "test.setting"
        assert result.value == "test_value"
        assert result.is_secret is False

    def test_returns_none_for_nonexistent_setting(self, config_service: ConfigService):
        """Should return None if setting doesn't exist"""
        result = config_service.get_setting("nonexistent.key")

        assert result is None

    @patch("app.services.admin.config_service.encryption_service.decrypt")
    def test_decrypts_secret_setting_when_requested(
        self,
        mock_decrypt: MagicMock,
        config_service: ConfigService,
        test_secret_setting: AdminSetting,
    ):
        """Should decrypt secret settings when decrypt=True"""
        mock_decrypt.return_value = "decrypted_value"

        result = config_service.get_setting("test.secret", decrypt=True)

        assert result is not None
        assert result.value == "decrypted_value"
        mock_decrypt.assert_called_once_with("encrypted_value_placeholder")

    def test_does_not_decrypt_when_decrypt_false(
        self, config_service: ConfigService, test_secret_setting: AdminSetting
    ):
        """Should not decrypt when decrypt=False"""
        result = config_service.get_setting("test.secret", decrypt=False)

        assert result is not None
        assert result.value == "encrypted_value_placeholder"

    @patch("app.services.admin.config_service.encryption_service.decrypt")
    def test_handles_decryption_error_gracefully(
        self,
        mock_decrypt: MagicMock,
        config_service: ConfigService,
        test_secret_setting: AdminSetting,
    ):
        """Should handle decryption errors without crashing"""
        mock_decrypt.side_effect = Exception("Decryption failed")

        result = config_service.get_setting("test.secret", decrypt=True)

        # Should still return the setting, just not decrypted
        assert result is not None
        assert result.key == "test.secret"


class TestGetSettingValue:
    """Tests for get_setting_value method"""

    def test_returns_value_for_existing_setting(
        self, config_service: ConfigService, test_setting: AdminSetting
    ):
        """Should return just the value"""
        result = config_service.get_setting_value("test.setting")

        assert result == "test_value"

    def test_returns_default_for_nonexistent_setting(
        self, config_service: ConfigService
    ):
        """Should return default value if setting doesn't exist"""
        result = config_service.get_setting_value(
            "nonexistent.key", default="default_value"
        )

        assert result == "default_value"

    def test_returns_none_by_default(self, config_service: ConfigService):
        """Should return None by default if not found"""
        result = config_service.get_setting_value("nonexistent.key")

        assert result is None


class TestListSettings:
    """Tests for list_settings method"""

    def test_lists_all_settings(
        self, config_service: ConfigService, test_setting: AdminSetting
    ):
        """Should list all settings without filters"""
        settings, total = config_service.list_settings()

        assert total >= 1
        assert any(s.key == "test.setting" for s in settings)

    def test_filters_by_category(
        self,
        config_service: ConfigService,
        db_session: Session,
        test_admin_user: User,
        test_setting: AdminSetting,
    ):
        """Should filter settings by category"""
        # Create setting in different category
        other_setting = AdminSetting(
            id=uuid4(),
            key="other.setting",
            value="value",
            value_type="string",
            category="api_keys",
            updated_by=test_admin_user.id,
        )
        db_session.add(other_setting)
        db_session.commit()

        settings, total = config_service.list_settings(category="test")

        assert all(s.category == "test" for s in settings)
        assert any(s.key == "test.setting" for s in settings)

    def test_searches_by_key(
        self, config_service: ConfigService, test_setting: AdminSetting
    ):
        """Should search settings by key"""
        settings, total = config_service.list_settings(search="test.setting")

        assert any(s.key == "test.setting" for s in settings)

    def test_searches_by_description(
        self, config_service: ConfigService, test_setting: AdminSetting
    ):
        """Should search settings by description"""
        settings, total = config_service.list_settings(search="Test setting")

        assert any(s.key == "test.setting" for s in settings)

    def test_pagination(
        self, config_service: ConfigService, db_session: Session, test_admin_user: User
    ):
        """Should paginate results correctly"""
        # Create multiple settings
        for i in range(5):
            setting = AdminSetting(
                id=uuid4(),
                key=f"pagination.test.{i}",
                value=f"value_{i}",
                value_type="string",
                updated_by=test_admin_user.id,
            )
            db_session.add(setting)
        db_session.commit()

        # Get first page
        settings_page1, total = config_service.list_settings(page=1, page_size=3)
        # Get second page
        settings_page2, _ = config_service.list_settings(page=2, page_size=3)

        assert len(settings_page1) <= 3
        assert len(settings_page2) <= 3
        assert total >= 5

    @patch("app.services.admin.config_service.encryption_service.decrypt")
    def test_decrypts_secrets_when_requested(
        self,
        mock_decrypt: MagicMock,
        config_service: ConfigService,
        test_secret_setting: AdminSetting,
    ):
        """Should decrypt secret settings when decrypt=True"""
        mock_decrypt.return_value = "decrypted_value"

        settings, total = config_service.list_settings(decrypt=True)

        secret_settings = [s for s in settings if s.is_secret]
        if secret_settings:
            assert any(
                s.value == "decrypted_value"
                for s in secret_settings
                if s.key == "test.secret"
            )


class TestCreateSetting:
    """Tests for create_setting method"""

    @patch("app.services.admin.config_service.encryption_service.encrypt")
    def test_creates_regular_setting(
        self,
        mock_encrypt: MagicMock,
        config_service: ConfigService,
        db_session: Session,
        test_admin_user: User,
    ):
        """Should create a regular (non-secret) setting"""
        setting_data = AdminSettingCreate(
            key="new.setting",
            value="new_value",
            value_type="string",
            is_secret=False,
            description="New setting",
            category="system",
        )

        result = config_service.create_setting(setting_data, test_admin_user.id)

        assert result.key == "new.setting"
        assert result.value == "new_value"
        assert result.is_secret is False
        mock_encrypt.assert_not_called()

        # Verify audit log was created
        audit_log = (
            db_session.query(AdminAuditLog)
            .filter(
                AdminAuditLog.action == "create_setting",
                AdminAuditLog.resource_id == str(result.id),
            )
            .first()
        )
        assert audit_log is not None

    @patch("app.services.admin.config_service.encryption_service.encrypt")
    def test_creates_secret_setting_with_encryption(
        self,
        mock_encrypt: MagicMock,
        config_service: ConfigService,
        db_session: Session,
        test_admin_user: User,
    ):
        """Should encrypt value when creating secret setting"""
        mock_encrypt.return_value = "encrypted_value"

        setting_data = AdminSettingCreate(
            key="secret.key",
            value="secret_value",
            value_type="string",
            is_secret=True,
            description="Secret setting",
            category="api_keys",
        )

        result = config_service.create_setting(setting_data, test_admin_user.id)

        assert result.key == "secret.key"
        assert result.value == "encrypted_value"
        assert result.is_secret is True
        mock_encrypt.assert_called_once_with("secret_value")


class TestUpdateSetting:
    """Tests for update_setting method"""

    def test_updates_setting_value(
        self,
        config_service: ConfigService,
        test_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should update setting value"""
        update_data = AdminSettingUpdate(value="updated_value")

        result = config_service.update_setting(
            "test.setting", update_data, test_admin_user.id
        )

        assert result is not None
        assert result.value == "updated_value"

    def test_returns_none_for_nonexistent_setting(
        self, config_service: ConfigService, test_admin_user: User
    ):
        """Should return None if setting doesn't exist"""
        update_data = AdminSettingUpdate(value="new_value")

        result = config_service.update_setting(
            "nonexistent.key", update_data, test_admin_user.id
        )

        assert result is None

    @patch("app.services.admin.config_service.encryption_service.encrypt")
    def test_encrypts_value_when_changing_to_secret(
        self,
        mock_encrypt: MagicMock,
        config_service: ConfigService,
        test_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should encrypt value when changing is_secret from False to True"""
        mock_encrypt.return_value = "encrypted_value"

        update_data = AdminSettingUpdate(is_secret=True)

        result = config_service.update_setting(
            "test.setting", update_data, test_admin_user.id
        )

        assert result.is_secret is True
        assert result.value == "encrypted_value"
        mock_encrypt.assert_called_once()

    @patch("app.services.admin.config_service.encryption_service.decrypt")
    def test_decrypts_value_when_changing_to_non_secret(
        self,
        mock_decrypt: MagicMock,
        config_service: ConfigService,
        test_secret_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should decrypt value when changing is_secret from True to False"""
        mock_decrypt.return_value = "decrypted_value"

        update_data = AdminSettingUpdate(is_secret=False)

        result = config_service.update_setting(
            "test.secret", update_data, test_admin_user.id
        )

        assert result.is_secret is False
        # Note: If decryption fails, it keeps the old value
        mock_decrypt.assert_called_once()

    @patch("app.services.admin.config_service.encryption_service.encrypt")
    def test_updates_secret_setting_value(
        self,
        mock_encrypt: MagicMock,
        config_service: ConfigService,
        test_secret_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should encrypt new value when updating secret setting"""
        mock_encrypt.return_value = "new_encrypted_value"

        update_data = AdminSettingUpdate(value="new_secret_value")

        result = config_service.update_setting(
            "test.secret", update_data, test_admin_user.id
        )

        assert result.value == "new_encrypted_value"
        mock_encrypt.assert_called_once_with("new_secret_value")

    def test_updates_multiple_fields(
        self,
        config_service: ConfigService,
        test_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should update multiple fields at once"""
        update_data = AdminSettingUpdate(
            value="updated",
            description="Updated description",
            category="updated_category",
        )

        result = config_service.update_setting(
            "test.setting", update_data, test_admin_user.id
        )

        assert result.value == "updated"
        assert result.description == "Updated description"
        assert result.category == "updated_category"

    def test_creates_audit_log(
        self,
        config_service: ConfigService,
        db_session: Session,
        test_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should create audit log entry when updating"""
        update_data = AdminSettingUpdate(value="updated")

        result = config_service.update_setting(
            "test.setting", update_data, test_admin_user.id
        )

        audit_log = (
            db_session.query(AdminAuditLog)
            .filter(
                AdminAuditLog.action == "update_setting",
                AdminAuditLog.resource_id == str(result.id),
            )
            .first()
        )

        assert audit_log is not None
        assert audit_log.details["key"] == "test.setting"
        assert "changes" in audit_log.details


class TestDeleteSetting:
    """Tests for delete_setting method"""

    def test_deletes_existing_setting(
        self,
        config_service: ConfigService,
        db_session: Session,
        test_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should delete an existing setting"""
        result = config_service.delete_setting("test.setting", test_admin_user.id)

        assert result is True

        # Verify setting is deleted
        deleted = (
            db_session.query(AdminSetting)
            .filter(AdminSetting.key == "test.setting")
            .first()
        )
        assert deleted is None

    def test_returns_false_for_nonexistent_setting(
        self, config_service: ConfigService, test_admin_user: User
    ):
        """Should return False if setting doesn't exist"""
        result = config_service.delete_setting("nonexistent.key", test_admin_user.id)

        assert result is False

    def test_creates_audit_log_before_deletion(
        self,
        config_service: ConfigService,
        db_session: Session,
        test_setting: AdminSetting,
        test_admin_user: User,
    ):
        """Should create audit log entry before deleting"""
        setting_id = str(test_setting.id)

        config_service.delete_setting("test.setting", test_admin_user.id)

        # Audit log should exist even though setting is deleted
        audit_log = (
            db_session.query(AdminAuditLog)
            .filter(
                AdminAuditLog.action == "delete_setting",
                AdminAuditLog.resource_id == setting_id,
            )
            .first()
        )

        assert audit_log is not None
        assert audit_log.details["key"] == "test.setting"


class TestAuditLog:
    """Tests for audit log functionality"""

    def test_audit_log_captures_create_action(
        self, config_service: ConfigService, db_session: Session, test_admin_user: User
    ):
        """Should create audit log for setting creation"""
        setting_data = AdminSettingCreate(
            key="audit.test", value="value", value_type="string", category="system"
        )

        config_service.create_setting(setting_data, test_admin_user.id)

        audit_log = (
            db_session.query(AdminAuditLog)
            .filter(AdminAuditLog.action == "create_setting")
            .order_by(AdminAuditLog.created_at.desc())
            .first()
        )

        assert audit_log is not None
        assert audit_log.user_id == test_admin_user.id
        assert audit_log.resource_type == "admin_setting"
        assert audit_log.details["key"] == "audit.test"
        assert audit_log.severity == "info"
