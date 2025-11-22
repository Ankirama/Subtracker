"""
Tests for Mailbox API endpoints.

Tests cover:
- Test mailbox connection
- Create mailbox (success, duplicate, connection failure)
- List mailboxes (all, active only)
- Get mailbox by ID (success, not found, wrong user)
- Update mailbox (settings, credentials)
- Delete mailbox
- Get sync status
- Trigger sync (success, inactive mailbox, failure)
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
import uuid


class TestMailboxConnectionTest:
    """Test POST /api/mailboxes/test - test mailbox connection."""

    @patch('app.api.mailboxes.get_email_provider')
    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_get_provider, client, auth_headers):
        """Successfully test mailbox connection."""
        # Mock the email provider
        mock_provider = AsyncMock()
        mock_provider.test_connection.return_value = {
            'success': True,
            'message': 'Connection successful',
            'provider_info': {'server': 'mail.example.com'}
        }
        mock_provider.close = AsyncMock()
        mock_get_provider.return_value = mock_provider

        test_data = {
            "provider_type": "jmap",
            "credentials": {
                "username": "test@example.com",
                "password": "testpass"
            }
        }

        response = client.post("/api/mailboxes/test", headers=auth_headers, json=test_data)

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'Connection successful' in data['message']

    @patch('app.api.mailboxes.get_email_provider')
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, mock_get_provider, client, auth_headers):
        """Test connection failure is handled gracefully."""
        # Mock provider that fails
        mock_provider = AsyncMock()
        mock_provider.test_connection.return_value = {
            'success': False,
            'message': 'Authentication failed',
            'provider_info': None
        }
        mock_provider.close = AsyncMock()
        mock_get_provider.return_value = mock_provider

        test_data = {
            "provider_type": "jmap",
            "credentials": {
                "username": "test@example.com",
                "password": "wrongpass"
            }
        }

        response = client.post("/api/mailboxes/test", headers=auth_headers, json=test_data)

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'failed' in data['message'].lower()

    def test_test_connection_no_auth(self, client):
        """Cannot test connection without authentication."""
        test_data = {
            "provider_type": "jmap",
            "credentials": {"username": "test", "password": "pass"}
        }

        response = client.post("/api/mailboxes/test", json=test_data)

        assert response.status_code == 403


class TestMailboxCreate:
    """Test POST /api/mailboxes - create mailbox."""

    @patch('app.api.mailboxes.get_email_provider')
    def test_create_mailbox_success(self, mock_get_provider, client, auth_headers):
        """Successfully create a new mailbox."""
        # Mock successful connection test
        mock_provider = AsyncMock()
        mock_provider.test_connection.return_value = {
            'success': True,
            'message': 'Connected'
        }
        mock_provider.close = AsyncMock()
        mock_get_provider.return_value = mock_provider

        mailbox_data = {
            "provider_type": "jmap",
            "email_address": "newmailbox@example.com",
            "credentials": {
                "server_url": "https://jmap.example.com",
                "username": "newmailbox@example.com",
                "password": "securepass123"
            },
            "display_name": "My Work Email",
            "sync_frequency": "daily",
            "batch_size": 100,
            "import_date_filter": "30days"
        }

        response = client.post("/api/mailboxes/", headers=auth_headers, json=mailbox_data)

        assert response.status_code == 201
        data = response.json()
        assert data['email_address'] == "newmailbox@example.com"
        assert data['display_name'] == "My Work Email"
        assert data['provider_type'] == "jmap"
        assert data['is_active'] is True
        assert 'id' in data
        # Credentials should not be in response
        assert 'credentials' not in data
        assert 'encrypted_credentials' not in data

    @patch('app.api.mailboxes.get_email_provider')
    def test_create_mailbox_duplicate_email(self, mock_get_provider, client, auth_headers, test_mailbox):
        """Cannot create mailbox with duplicate email address."""
        mock_provider = AsyncMock()
        mock_provider.test_connection.return_value = {'success': True, 'message': 'OK'}
        mock_provider.close = AsyncMock()
        mock_get_provider.return_value = mock_provider

        mailbox_data = {
            "provider_type": "jmap",
            "email_address": test_mailbox.email_address,  # Existing email
            "credentials": {
                "server_url": "https://jmap.example.com",
                "username": "test",
                "password": "pass"
            }
        }

        response = client.post("/api/mailboxes/", headers=auth_headers, json=mailbox_data)

        assert response.status_code == 400
        assert "already exists" in response.json()['detail'].lower()

    @patch('app.api.mailboxes.get_email_provider')
    def test_create_mailbox_connection_test_fails(self, mock_get_provider, client, auth_headers):
        """Cannot create mailbox if connection test fails."""
        # Mock failed connection test
        mock_provider = AsyncMock()
        mock_provider.test_connection.return_value = {
            'success': False,
            'message': 'Invalid credentials'
        }
        mock_provider.close = AsyncMock()
        mock_get_provider.return_value = mock_provider

        mailbox_data = {
            "provider_type": "jmap",
            "email_address": "newmailbox@example.com",
            "credentials": {
                "server_url": "https://jmap.example.com",
                "username": "test",
                "password": "wrongpass"
            }
        }

        response = client.post("/api/mailboxes/", headers=auth_headers, json=mailbox_data)

        assert response.status_code == 400
        assert "failed" in response.json()['detail'].lower()

    def test_create_mailbox_no_auth(self, client):
        """Cannot create mailbox without authentication."""
        mailbox_data = {
            "provider_type": "jmap",
            "email_address": "test@example.com",
            "credentials": {"username": "test", "password": "pass"}
        }

        response = client.post("/api/mailboxes/", json=mailbox_data)

        assert response.status_code == 403

    def test_create_mailbox_unsupported_provider(self, client, auth_headers):
        """Cannot create mailbox with unsupported provider."""
        mailbox_data = {
            "provider_type": "invalid_provider",
            "email_address": "test@example.com",
            "credentials": {"username": "test", "password": "pass"}
        }

        response = client.post("/api/mailboxes/", headers=auth_headers, json=mailbox_data)

        # Should fail during provider creation
        assert response.status_code in [400, 422]


class TestMailboxList:
    """Test GET /api/mailboxes - list mailboxes."""

    def test_list_mailboxes_success(self, client, auth_headers, test_mailbox):
        """List mailboxes for current user."""
        response = client.get("/api/mailboxes/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(m['id'] == str(test_mailbox.id) for m in data)

    def test_list_mailboxes_active_only(self, client, auth_headers, db_session, test_mailbox):
        """List only active mailboxes by default."""
        # Create inactive mailbox
        from app.models.mailbox import Mailbox
        from app.security.encryption import encrypt_credentials

        inactive_mailbox = Mailbox(
            user_id=test_mailbox.user_id,
            email_address="inactive@example.com",
            provider_type="jmap",
            encrypted_credentials=encrypt_credentials({"user": "test"}),
            is_active=False
        )
        db_session.add(inactive_mailbox)
        db_session.commit()

        # Default request (active_only=True)
        response = client.get("/api/mailboxes/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        emails = [m['email_address'] for m in data]

        # Should only see active mailbox
        assert test_mailbox.email_address in emails
        assert "inactive@example.com" not in emails

    def test_list_mailboxes_include_inactive(self, client, auth_headers, db_session, test_mailbox):
        """Can optionally include inactive mailboxes."""
        # Create inactive mailbox
        from app.models.mailbox import Mailbox
        from app.security.encryption import encrypt_credentials

        inactive_mailbox = Mailbox(
            user_id=test_mailbox.user_id,
            email_address="inactive@example.com",
            provider_type="jmap",
            encrypted_credentials=encrypt_credentials({"user": "test"}),
            is_active=False
        )
        db_session.add(inactive_mailbox)
        db_session.commit()

        # Request with active_only=False
        response = client.get("/api/mailboxes/?active_only=false", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        emails = [m['email_address'] for m in data]

        # Should see both mailboxes
        assert test_mailbox.email_address in emails
        assert "inactive@example.com" in emails

    def test_list_mailboxes_no_auth(self, client):
        """Cannot list mailboxes without authentication."""
        response = client.get("/api/mailboxes/")

        assert response.status_code == 403

    def test_list_mailboxes_empty(self, client, auth_headers, db_session):
        """Returns empty list when user has no mailboxes."""
        # Login as a different user with no mailboxes
        from app.models.user import User
        from app.security.password import hash_password

        password_hash, salt = hash_password("testpass")
        new_user = User(
            email="nomail@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=True
        )
        db_session.add(new_user)
        db_session.commit()

        # Login as new user
        login_response = client.post(
            "/api/auth/login",
            json={"email": "nomail@example.com", "password": "testpass"}
        )
        new_auth_headers = {
            "Authorization": f"Bearer {login_response.json()['access_token']}"
        }

        response = client.get("/api/mailboxes/", headers=new_auth_headers)

        assert response.status_code == 200
        assert response.json() == []


class TestMailboxGetById:
    """Test GET /api/mailboxes/{id} - get mailbox by ID."""

    def test_get_mailbox_success(self, client, auth_headers, test_mailbox):
        """Get mailbox by ID successfully."""
        response = client.get(
            f"/api/mailboxes/{test_mailbox.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == str(test_mailbox.id)
        assert data['email_address'] == test_mailbox.email_address

    def test_get_mailbox_not_found(self, client, auth_headers):
        """Get non-existent mailbox returns 404."""
        fake_id = uuid.uuid4()

        response = client.get(
            f"/api/mailboxes/{fake_id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_mailbox_wrong_user(self, client, db_session, test_mailbox):
        """Cannot get another user's mailbox."""
        # Create another user
        from app.models.user import User
        from app.security.password import hash_password

        password_hash, salt = hash_password("otherpass")
        other_user = User(
            email="other@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
            email_verified=True
        )
        db_session.add(other_user)
        db_session.commit()

        # Login as other user
        login_response = client.post(
            "/api/auth/login",
            json={"email": "other@example.com", "password": "otherpass"}
        )
        other_auth_headers = {
            "Authorization": f"Bearer {login_response.json()['access_token']}"
        }

        # Try to get test_mailbox (belongs to different user)
        response = client.get(
            f"/api/mailboxes/{test_mailbox.id}",
            headers=other_auth_headers
        )

        assert response.status_code == 404  # Not found (for security)

    def test_get_mailbox_no_auth(self, client, test_mailbox):
        """Cannot get mailbox without authentication."""
        response = client.get(f"/api/mailboxes/{test_mailbox.id}")

        assert response.status_code == 403


class TestMailboxUpdate:
    """Test PUT /api/mailboxes/{id} - update mailbox."""

    def test_update_mailbox_settings(self, client, auth_headers, test_mailbox):
        """Update mailbox settings successfully."""
        update_data = {
            "display_name": "Updated Name",
            "sync_frequency": "daily",
            "batch_size": 200
        }

        response = client.put(
            f"/api/mailboxes/{test_mailbox.id}",
            headers=auth_headers,
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data['display_name'] == "Updated Name"
        assert data['sync_frequency'] == "daily"
        assert data['batch_size'] == 200

    @patch('app.api.mailboxes.get_email_provider')
    def test_update_mailbox_credentials(self, mock_get_provider, client, auth_headers, test_mailbox):
        """Update mailbox credentials with connection test."""
        # Mock successful connection test
        mock_provider = AsyncMock()
        mock_provider.test_connection.return_value = {
            'success': True,
            'message': 'Connected'
        }
        mock_provider.close = AsyncMock()
        mock_get_provider.return_value = mock_provider

        update_data = {
            "credentials": {
                "username": "updated@example.com",
                "password": "newpassword123"
            }
        }

        response = client.put(
            f"/api/mailboxes/{test_mailbox.id}",
            headers=auth_headers,
            json=update_data
        )

        assert response.status_code == 200

    @patch('app.api.mailboxes.get_email_provider')
    def test_update_mailbox_invalid_credentials(self, mock_get_provider, client, auth_headers, test_mailbox):
        """Cannot update with invalid credentials."""
        # Mock failed connection test
        mock_provider = AsyncMock()
        mock_provider.test_connection.return_value = {
            'success': False,
            'message': 'Authentication failed'
        }
        mock_provider.close = AsyncMock()
        mock_get_provider.return_value = mock_provider

        update_data = {
            "credentials": {
                "username": "test@example.com",
                "password": "wrongpass"
            }
        }

        response = client.put(
            f"/api/mailboxes/{test_mailbox.id}",
            headers=auth_headers,
            json=update_data
        )

        assert response.status_code == 400
        assert "failed" in response.json()['detail'].lower()

    def test_update_mailbox_not_found(self, client, auth_headers):
        """Update non-existent mailbox returns 404."""
        fake_id = uuid.uuid4()

        response = client.put(
            f"/api/mailboxes/{fake_id}",
            headers=auth_headers,
            json={"display_name": "New Name"}
        )

        assert response.status_code == 404

    def test_update_mailbox_no_auth(self, client, test_mailbox):
        """Cannot update mailbox without authentication."""
        response = client.put(
            f"/api/mailboxes/{test_mailbox.id}",
            json={"display_name": "New Name"}
        )

        assert response.status_code == 403


class TestMailboxDelete:
    """Test DELETE /api/mailboxes/{id} - delete mailbox."""

    def test_delete_mailbox_success(self, client, auth_headers, test_mailbox):
        """Successfully delete a mailbox."""
        mailbox_id = test_mailbox.id

        response = client.delete(
            f"/api/mailboxes/{mailbox_id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(
            f"/api/mailboxes/{mailbox_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404

    def test_delete_mailbox_not_found(self, client, auth_headers):
        """Delete non-existent mailbox returns 404."""
        fake_id = uuid.uuid4()

        response = client.delete(
            f"/api/mailboxes/{fake_id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_delete_mailbox_no_auth(self, client, test_mailbox):
        """Cannot delete mailbox without authentication."""
        response = client.delete(f"/api/mailboxes/{test_mailbox.id}")

        assert response.status_code == 403


class TestMailboxSyncStatus:
    """Test GET /api/mailboxes/{id}/sync-status - get sync status."""

    def test_get_sync_status_success(self, client, auth_headers, test_mailbox, db_session):
        """Get mailbox sync status successfully."""
        # Set some sync status data
        test_mailbox.last_sync_status = 'success'
        test_mailbox.last_sync_at = datetime.now(timezone.utc)
        test_mailbox.last_sync_emails_processed = 50
        test_mailbox.last_sync_subscriptions_found = 3
        db_session.commit()

        response = client.get(
            f"/api/mailboxes/{test_mailbox.id}/sync-status",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['total_emails_processed'] == 50
        assert data['subscriptions_found'] == 3
        assert 'last_sync_at' in data

    def test_get_sync_status_never_synced(self, client, auth_headers, test_mailbox):
        """Get sync status for mailbox that was never synced."""
        response = client.get(
            f"/api/mailboxes/{test_mailbox.id}/sync-status",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'never_synced'

    def test_get_sync_status_not_found(self, client, auth_headers):
        """Get sync status for non-existent mailbox returns 404."""
        fake_id = uuid.uuid4()

        response = client.get(
            f"/api/mailboxes/{fake_id}/sync-status",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_sync_status_no_auth(self, client, test_mailbox):
        """Cannot get sync status without authentication."""
        response = client.get(f"/api/mailboxes/{test_mailbox.id}/sync-status")

        assert response.status_code == 403


class TestMailboxTriggerSync:
    """Test POST /api/mailboxes/{id}/sync - trigger sync."""

    @patch('app.tasks.email_sync.sync_mailbox_emails')
    def test_trigger_sync_success(self, mock_sync_task, client, auth_headers, test_mailbox):
        """Successfully trigger mailbox sync."""
        # Mock Celery task
        mock_task = MagicMock()
        mock_task.id = "test-task-id-123"
        mock_sync_task.delay.return_value = mock_task

        sync_request = {
            "force_full_sync": False,
            "date_filter_override": None
        }

        response = client.post(
            f"/api/mailboxes/{test_mailbox.id}/sync",
            headers=auth_headers,
            json=sync_request
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'queued'
        assert data['mailbox_id'] == str(test_mailbox.id)

        # Verify task was called
        mock_sync_task.delay.assert_called_once()

    @patch('app.tasks.email_sync.sync_mailbox_emails')
    def test_trigger_sync_with_date_filter(self, mock_sync_task, client, auth_headers, test_mailbox):
        """Trigger sync with custom date filter."""
        mock_task = MagicMock()
        mock_task.id = "test-task-id-456"
        mock_sync_task.delay.return_value = mock_task

        sync_request = {
            "force_full_sync": False,
            "date_filter_override": "7days"
        }

        response = client.post(
            f"/api/mailboxes/{test_mailbox.id}/sync",
            headers=auth_headers,
            json=sync_request
        )

        assert response.status_code == 200

    def test_trigger_sync_inactive_mailbox(self, client, auth_headers, test_mailbox, db_session):
        """Cannot trigger sync for inactive mailbox."""
        # Deactivate mailbox
        test_mailbox.is_active = False
        db_session.commit()

        sync_request = {"force_full_sync": False}

        response = client.post(
            f"/api/mailboxes/{test_mailbox.id}/sync",
            headers=auth_headers,
            json=sync_request
        )

        assert response.status_code == 400
        assert "inactive" in response.json()['detail'].lower()

    def test_trigger_sync_not_found(self, client, auth_headers):
        """Trigger sync for non-existent mailbox returns 404."""
        fake_id = uuid.uuid4()

        response = client.post(
            f"/api/mailboxes/{fake_id}/sync",
            headers=auth_headers,
            json={"force_full_sync": False}
        )

        assert response.status_code == 404

    def test_trigger_sync_no_auth(self, client, test_mailbox):
        """Cannot trigger sync without authentication."""
        response = client.post(
            f"/api/mailboxes/{test_mailbox.id}/sync",
            json={"force_full_sync": False}
        )

        assert response.status_code == 403

    @patch('app.tasks.email_sync.sync_mailbox_emails')
    def test_trigger_sync_task_failure(self, mock_sync_task, client, auth_headers, test_mailbox):
        """Handle sync task queue failure gracefully."""
        # Mock task failure
        mock_sync_task.delay.side_effect = Exception("Celery connection failed")

        sync_request = {"force_full_sync": False}

        response = client.post(
            f"/api/mailboxes/{test_mailbox.id}/sync",
            headers=auth_headers,
            json=sync_request
        )

        assert response.status_code == 500
        assert "failed to queue" in response.json()['detail'].lower()
