"""
Tests for IP Whitelist functionality.

Tests cover:
- Adding IP to whitelist
- Listing whitelisted IPs
- Retrieving specific whitelisted IP
- Updating whitelist entry
- Deleting from whitelist
- Brute force protection bypass for whitelisted IPs
"""

import pytest
from datetime import datetime

from app.models.ip_whitelist import IPWhitelist
from app.security.email_verification import VerificationRateLimiter


class TestIPWhitelistAPI:
    """Test IP Whitelist admin API endpoints."""

    def test_list_whitelist_empty(self, client, admin_headers):
        """List whitelist when empty."""
        response = client.get("/api/admin/security/ip-whitelist", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    def test_add_ip_to_whitelist(self, client, admin_headers):
        """Add an IP address to the whitelist."""
        whitelist_data = {
            "ip_address": "192.168.1.1",
            "description": "Test admin office IP",
        }

        response = client.post(
            "/api/admin/security/ip-whitelist",
            json=whitelist_data,
            headers=admin_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["ip_address"] == "192.168.1.1"
        assert data["description"] == "Test admin office IP"
        assert data["access_count"] == 0
        assert "added_at" in data

    def test_add_duplicate_ip_fails(self, client, admin_headers, db_session):
        """Cannot add the same IP twice."""
        # Add first IP
        whitelist_data = {"ip_address": "192.168.1.2", "description": "First entry"}
        response1 = client.post(
            "/api/admin/security/ip-whitelist",
            json=whitelist_data,
            headers=admin_headers,
        )
        assert response1.status_code == 201

        # Try to add same IP again
        whitelist_data["description"] = "Duplicate entry"
        response2 = client.post(
            "/api/admin/security/ip-whitelist",
            json=whitelist_data,
            headers=admin_headers,
        )

        assert response2.status_code == 400
        assert "already in whitelist" in response2.json()["detail"].lower()

    def test_list_whitelist_with_entries(self, client, admin_headers):
        """List whitelist with multiple entries."""
        # Add several IPs
        for i in range(5):
            client.post(
                "/api/admin/security/ip-whitelist",
                json={
                    "ip_address": f"192.168.1.{i+10}",
                    "description": f"Test IP {i+1}",
                },
                headers=admin_headers,
            )

        # List all
        response = client.get("/api/admin/security/ip-whitelist", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    def test_get_whitelist_entry(self, client, admin_headers):
        """Get specific whitelisted IP."""
        # Add IP
        client.post(
            "/api/admin/security/ip-whitelist",
            json={"ip_address": "10.0.0.1", "description": "VPN gateway"},
            headers=admin_headers,
        )

        # Get specific IP
        response = client.get(
            "/api/admin/security/ip-whitelist/10.0.0.1", headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ip_address"] == "10.0.0.1"
        assert data["description"] == "VPN gateway"

    def test_get_nonexistent_ip_fails(self, client, admin_headers):
        """Getting non-existent IP returns 404."""
        response = client.get(
            "/api/admin/security/ip-whitelist/1.2.3.4", headers=admin_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_whitelist_description(self, client, admin_headers):
        """Update description of whitelisted IP."""
        # Add IP
        client.post(
            "/api/admin/security/ip-whitelist",
            json={"ip_address": "172.16.0.1", "description": "Original description"},
            headers=admin_headers,
        )

        # Update description
        response = client.patch(
            "/api/admin/security/ip-whitelist/172.16.0.1",
            json={"description": "Updated description"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    def test_delete_from_whitelist(self, client, admin_headers):
        """Remove IP from whitelist."""
        # Add IP
        client.post(
            "/api/admin/security/ip-whitelist",
            json={"ip_address": "203.0.113.1", "description": "To be deleted"},
            headers=admin_headers,
        )

        # Delete it
        response = client.delete(
            "/api/admin/security/ip-whitelist/203.0.113.1", headers=admin_headers
        )

        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

        # Verify it's gone
        get_response = client.get(
            "/api/admin/security/ip-whitelist/203.0.113.1", headers=admin_headers
        )
        assert get_response.status_code == 404

    def test_pagination(self, client, admin_headers):
        """Test pagination of whitelist entries."""
        # Add 25 IPs
        for i in range(25):
            client.post(
                "/api/admin/security/ip-whitelist",
                json={
                    "ip_address": f"192.168.2.{i+1}",
                    "description": f"Test IP {i+1}",
                },
                headers=admin_headers,
            )

        # Get first page (20 items)
        response1 = client.get(
            "/api/admin/security/ip-whitelist?page=1&page_size=20",
            headers=admin_headers,
        )
        data1 = response1.json()
        assert len(data1["items"]) == 20
        assert data1["total"] == 25
        assert data1["total_pages"] == 2

        # Get second page (5 items)
        response2 = client.get(
            "/api/admin/security/ip-whitelist?page=2&page_size=20",
            headers=admin_headers,
        )
        data2 = response2.json()
        assert len(data2["items"]) == 5


class TestIPWhitelistBruteForceProtection:
    """Test that whitelisted IPs bypass brute force protection."""

    def test_whitelisted_ip_not_blocked(self, db_session, admin_user):
        """Whitelisted IP should not be blocked."""
        # Add IP to whitelist
        whitelist_entry = IPWhitelist(
            ip_address="192.168.100.1",
            description="Test admin IP",
            added_by_user_id=str(admin_user.id),
            access_count=0,
        )
        db_session.add(whitelist_entry)
        db_session.commit()

        # Check if IP is blocked (should not be)
        is_blocked, reason = VerificationRateLimiter.is_ip_blocked(
            db_session, "192.168.100.1"
        )

        assert is_blocked is False
        assert reason is None

    def test_whitelisted_ip_updates_stats(self, db_session, admin_user):
        """Accessing with whitelisted IP should update last_seen and access_count."""
        # Add IP to whitelist
        whitelist_entry = IPWhitelist(
            ip_address="192.168.100.2",
            description="Test stats tracking",
            added_by_user_id=str(admin_user.id),
            access_count=0,
        )
        db_session.add(whitelist_entry)
        db_session.commit()

        initial_count = whitelist_entry.access_count

        # Check if IP is blocked (will update stats)
        VerificationRateLimiter.is_ip_blocked(db_session, "192.168.100.2")

        # Refresh to get updated data
        db_session.refresh(whitelist_entry)

        assert whitelist_entry.access_count == initial_count + 1
        assert whitelist_entry.last_seen is not None

    def test_whitelisted_ip_not_tracked(self, db_session, admin_user):
        """Whitelisted IP should not be tracked for brute force."""
        # Add IP to whitelist
        whitelist_entry = IPWhitelist(
            ip_address="192.168.100.3",
            description="Test no tracking",
            added_by_user_id=str(admin_user.id),
            access_count=0,
        )
        db_session.add(whitelist_entry)
        db_session.commit()

        # Try to track verification attempts (should return None for whitelisted IP)
        error_msg = VerificationRateLimiter.track_verification_attempt(
            db_session, "192.168.100.3"
        )

        assert error_msg is None  # No error, IP is whitelisted

    def test_non_whitelisted_ip_can_be_blocked(self, db_session):
        """Non-whitelisted IP can still be blocked normally."""
        # Don't add to whitelist, just check if it can be tracked
        error_msg = VerificationRateLimiter.track_verification_attempt(
            db_session, "192.168.100.99"
        )

        # Should not be blocked on first attempt
        assert error_msg is None

        # But IP should be trackable (would be blocked after threshold)
        is_blocked, reason = VerificationRateLimiter.is_ip_blocked(
            db_session, "192.168.100.99"
        )
        assert is_blocked is False  # Not blocked yet, but is being tracked


class TestIPWhitelistPermissions:
    """Test that only admins can manage IP whitelist."""

    def test_non_admin_cannot_list(self, client, auth_headers):
        """Non-admin users cannot list whitelist."""
        response = client.get("/api/admin/security/ip-whitelist", headers=auth_headers)

        assert response.status_code == 403

    def test_non_admin_cannot_add(self, client, auth_headers):
        """Non-admin users cannot add to whitelist."""
        response = client.post(
            "/api/admin/security/ip-whitelist",
            json={"ip_address": "1.2.3.4", "description": "Test"},
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_non_admin_cannot_update(self, client, auth_headers):
        """Non-admin users cannot update whitelist."""
        response = client.patch(
            "/api/admin/security/ip-whitelist/1.2.3.4",
            json={"description": "Updated"},
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_non_admin_cannot_delete(self, client, auth_headers):
        """Non-admin users cannot delete from whitelist."""
        response = client.delete(
            "/api/admin/security/ip-whitelist/1.2.3.4", headers=auth_headers
        )

        assert response.status_code == 403

    def test_unauthenticated_cannot_access(self, client):
        """Unauthenticated users cannot access whitelist."""
        response = client.get("/api/admin/security/ip-whitelist")

        assert response.status_code == 403
