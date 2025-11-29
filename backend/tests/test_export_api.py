"""
Tests for Export API endpoints and ExportService.

Tests cover:
- CSV export (basic, filters, content validation)
- PDF export (basic, filters, HTML validation)
- Analytics export (basic, filters, calculations)
- ExportService utility methods
- Date filtering and query parameters
- Empty data handling
"""

from datetime import datetime, timezone, timedelta, date

from app.services.export_service import ExportService


class TestCSVExport:
    """Test GET /api/export/csv - export subscriptions to CSV."""

    def test_csv_export_success(self, client, auth_headers, test_subscription):
        """Successfully export subscriptions to CSV."""
        response = client.get("/api/export/csv", headers=auth_headers)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        # Check filename in content-disposition header
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert "subscriptions_" in content_disposition
        assert ".csv" in content_disposition

    def test_csv_export_no_subscriptions(self, client, auth_headers):
        """Export CSV when user has no subscriptions (empty result)."""
        response = client.get("/api/export/csv", headers=auth_headers)

        assert response.status_code == 200
        content = response.text

        # Should have headers but no data rows (beyond summary)
        assert "Subscription Export Report" in content
        assert "Provider" in content
        assert "Total Subscriptions:,0" in content

    def test_csv_export_with_date_filter(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export CSV with start_date and end_date filters."""
        from app.models.subscription import Subscription

        # Create subscriptions at different dates
        now = datetime.now(timezone.utc)
        old_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="OldService",
            amount=10.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now - timedelta(days=90),
            last_confirmed_at=now,
        )
        recent_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="NewService",
            amount=15.00,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.95,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now - timedelta(days=10),
            last_confirmed_at=now,
        )
        db_session.add_all([old_sub, recent_sub])
        db_session.commit()

        # Filter to only recent subscriptions
        start_date = (now - timedelta(days=30)).date()

        response = client.get(
            "/api/export/csv",
            headers=auth_headers,
            params={"start_date": start_date.isoformat()},
        )

        assert response.status_code == 200
        content = response.text

        # Should include NewService but not OldService
        assert "NewService" in content
        assert "OldService" not in content
        assert f'Start Date:,{start_date.strftime("%Y-%m-%d")}' in content

    def test_csv_export_active_only(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export CSV with active_only filter."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)
        active_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="ActiveService",
            amount=20.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        inactive_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="InactiveService",
            amount=10.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=False,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        db_session.add_all([active_sub, inactive_sub])
        db_session.commit()

        response = client.get(
            "/api/export/csv", headers=auth_headers, params={"active_only": True}
        )

        assert response.status_code == 200
        content = response.text

        # Should include only active subscription
        assert "ActiveService" in content
        assert "InactiveService" not in content

    def test_csv_export_category_filter(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export CSV filtered by category."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)
        streaming_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="StreamingService",
            amount=15.00,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        software_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="SoftwareService",
            amount=20.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        db_session.add_all([streaming_sub, software_sub])
        db_session.commit()

        response = client.get(
            "/api/export/csv", headers=auth_headers, params={"category": "streaming"}
        )

        assert response.status_code == 200
        content = response.text

        # Should include only streaming category
        assert "StreamingService" in content
        assert "SoftwareService" not in content

    def test_csv_content_validation(self, client, auth_headers, test_subscription):
        """Validate CSV content structure and data."""
        response = client.get("/api/export/csv", headers=auth_headers)

        assert response.status_code == 200
        content = response.text
        lines = content.split("\n")

        # Check header section
        assert "Subscription Export Report" in lines[0]
        assert "Generated:" in lines[1]

        # Check column headers
        header_line = None
        for i, line in enumerate(lines):
            if "Provider" in line and "Amount" in line:
                header_line = i
                break

        assert header_line is not None
        assert "Billing Cycle" in lines[header_line]
        assert "Monthly Equivalent" in lines[header_line]
        assert "Category" in lines[header_line]

        # Check summary section exists
        assert any("Summary" in line for line in lines)
        assert any("Total Subscriptions:" in line for line in lines)
        assert any("Total Monthly Cost:" in line for line in lines)


class TestPDFExport:
    """Test GET /api/export/pdf - export subscriptions to PDF HTML."""

    def test_pdf_export_success(self, client, auth_headers, test_subscription):
        """Successfully export subscriptions to PDF HTML."""
        response = client.get("/api/export/pdf", headers=auth_headers)

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_pdf_export_no_subscriptions(self, client, auth_headers):
        """Export PDF when user has no subscriptions."""
        response = client.get("/api/export/pdf", headers=auth_headers)

        assert response.status_code == 200
        content = response.text

        # Should have report structure but show 0 subscriptions
        assert "Subscription Report" in content
        assert "<html>" in content
        assert "</html>" in content

    def test_pdf_export_with_date_filter(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export PDF with date range filter."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)
        recent_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="RecentService",
            amount=15.00,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.95,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now - timedelta(days=5),
            last_confirmed_at=now,
        )
        db_session.add(recent_sub)
        db_session.commit()

        start_date = (now - timedelta(days=10)).date()
        end_date = now.date()

        response = client.get(
            "/api/export/pdf",
            headers=auth_headers,
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )

        assert response.status_code == 200
        content = response.text

        # Should include date range in metadata
        assert "RecentService" in content
        assert "Period:" in content

    def test_pdf_export_active_only(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export PDF with active_only filter."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)
        active_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="ActivePDFService",
            amount=25.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        db_session.add(active_sub)
        db_session.commit()

        response = client.get(
            "/api/export/pdf", headers=auth_headers, params={"active_only": True}
        )

        assert response.status_code == 200
        content = response.text
        assert "ActivePDFService" in content

    def test_pdf_html_structure(self, client, auth_headers, test_subscription):
        """Validate PDF HTML structure and styling."""
        response = client.get("/api/export/pdf", headers=auth_headers)

        assert response.status_code == 200
        content = response.text

        # Check HTML structure
        assert "<!DOCTYPE html>" in content
        assert "<html>" in content
        assert "</html>" in content
        assert "<head>" in content
        assert "<style>" in content

        # Check report sections
        assert 'class="header"' in content
        assert 'class="summary"' in content
        assert "Subscription Report" in content

        # Check table structure
        assert "<table>" in content
        assert "<thead>" in content
        assert "<tbody>" in content
        assert "<th>Provider</th>" in content
        assert "<th>Amount</th>" in content
        assert "<th>Status</th>" in content


class TestAnalyticsExport:
    """Test GET /api/export/analytics - export analytics data."""

    def test_analytics_export_success(self, client, auth_headers, test_subscription):
        """Successfully export analytics data."""
        response = client.get("/api/export/analytics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "total_subscriptions" in data
        assert "active_subscriptions" in data
        assert "total_monthly_cost" in data
        assert "total_yearly_cost" in data
        assert "by_category" in data
        assert "by_billing_cycle" in data
        assert "date_range" in data

    def test_analytics_export_no_mailboxes(self, client, db_session):
        """Export analytics when user has no mailboxes."""
        from app.models.user import User
        from app.security.password import hash_password
        from app.security.jwt import create_access_token

        # Create user without mailboxes
        password_hash, salt = hash_password("testpass")
        user = User(
            email="nomailbox@example.com",
            password_hash=password_hash,
            salt=salt,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        token = create_access_token(str(user.id))
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/export/analytics", headers=headers)

        assert response.status_code == 200
        data = response.json()

        # Should return empty analytics
        assert data["total_subscriptions"] == 0
        assert data["active_subscriptions"] == 0
        assert data["total_monthly_cost"] == 0.0
        assert data["by_category"] == {}
        assert data["by_billing_cycle"] == {}

    def test_analytics_export_with_date_filter(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export analytics with date range filter."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)
        old_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="OldAnalytics",
            amount=30.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now - timedelta(days=100),
            last_confirmed_at=now,
        )
        recent_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="RecentAnalytics",
            amount=20.00,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.95,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now - timedelta(days=5),
            last_confirmed_at=now,
        )
        db_session.add_all([old_sub, recent_sub])
        db_session.commit()

        # Filter to only recent subscriptions
        start_date = (now - timedelta(days=10)).date()

        response = client.get(
            "/api/export/analytics",
            headers=auth_headers,
            params={"start_date": start_date.isoformat()},
        )

        assert response.status_code == 200
        data = response.json()

        # Should only count recent subscription
        assert data["total_subscriptions"] == 1
        assert data["date_range"]["start"] == start_date.isoformat()

    def test_analytics_by_category_breakdown(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export analytics with category breakdown."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)

        # Create subscriptions in different categories
        streaming1 = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Netflix",
            amount=15.00,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        streaming2 = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Spotify",
            amount=10.00,
            currency="EUR",
            billing_cycle="monthly",
            category="streaming",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        software = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="GitHub",
            amount=7.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        db_session.add_all([streaming1, streaming2, software])
        db_session.commit()

        response = client.get("/api/export/analytics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check category breakdown
        assert "streaming" in data["by_category"]
        assert "software" in data["by_category"]

        streaming_data = data["by_category"]["streaming"]
        assert streaming_data["count"] == 2
        assert streaming_data["monthly_cost"] == 25.0  # 15 + 10
        assert streaming_data["yearly_cost"] == 300.0  # 25 * 12

        software_data = data["by_category"]["software"]
        assert software_data["count"] == 1
        assert software_data["monthly_cost"] == 7.0

    def test_analytics_by_billing_cycle_breakdown(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Export analytics with billing cycle breakdown."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)

        monthly_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="MonthlyService",
            amount=10.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        yearly_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="YearlyService",
            amount=120.00,
            currency="EUR",
            billing_cycle="yearly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        db_session.add_all([monthly_sub, yearly_sub])
        db_session.commit()

        response = client.get("/api/export/analytics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check billing cycle breakdown
        assert "monthly" in data["by_billing_cycle"]
        assert "yearly" in data["by_billing_cycle"]

        monthly_data = data["by_billing_cycle"]["monthly"]
        assert monthly_data["count"] == 1
        assert monthly_data["total_amount"] == 10.0

        yearly_data = data["by_billing_cycle"]["yearly"]
        assert yearly_data["count"] == 1
        assert yearly_data["total_amount"] == 120.0

    def test_analytics_cost_calculations(
        self, client, auth_headers, db_session, test_mailbox
    ):
        """Validate analytics cost calculations."""
        from app.models.subscription import Subscription

        now = datetime.now(timezone.utc)

        # Monthly subscription
        monthly_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Monthly",
            amount=20.00,
            currency="EUR",
            billing_cycle="monthly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        # Yearly subscription (should be normalized to monthly)
        yearly_sub = Subscription(
            user_id=test_mailbox.user_id,
            mailbox_id=test_mailbox.id,
            provider="Yearly",
            amount=120.00,
            currency="EUR",
            billing_cycle="yearly",
            category="software",
            extraction_method="ai",
            confidence_score=0.90,
            is_active=True,
            is_confirmed=True,
            first_detected_at=now,
            last_confirmed_at=now,
        )
        db_session.add_all([monthly_sub, yearly_sub])
        db_session.commit()

        response = client.get("/api/export/analytics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Monthly: 20 + (120/12) = 20 + 10 = 30
        assert data["total_monthly_cost"] == 30.0
        # Yearly: 30 * 12 = 360
        assert data["total_yearly_cost"] == 360.0


class TestExportService:
    """Test ExportService utility methods."""

    def test_normalize_billing_to_monthly(self):
        """Test billing cycle normalization to monthly equivalent."""
        # Weekly: 10 * 4.33 = 43.30
        assert ExportService._normalize_billing_to_monthly(10.0, "weekly") == 43.3

        # Monthly: 10 * 1 = 10
        assert ExportService._normalize_billing_to_monthly(10.0, "monthly") == 10.0

        # Quarterly: 30 * (1/3) = 10
        assert ExportService._normalize_billing_to_monthly(30.0, "quarterly") == 10.0

        # Biannual: 60 * (1/6) = 10
        assert ExportService._normalize_billing_to_monthly(60.0, "biannual") == 10.0

        # Yearly: 120 * (1/12) = 10
        assert ExportService._normalize_billing_to_monthly(120.0, "yearly") == 10.0

        # Annual (alias for yearly): 120 * (1/12) = 10
        assert ExportService._normalize_billing_to_monthly(120.0, "annual") == 10.0

        # Unknown cycle defaults to 1.0 multiplier
        assert ExportService._normalize_billing_to_monthly(15.0, "unknown") == 15.0

        # Zero amount
        assert ExportService._normalize_billing_to_monthly(0.0, "monthly") == 0.0

        # None amount
        assert ExportService._normalize_billing_to_monthly(None, "monthly") == 0.0

    def test_generate_csv_empty(self):
        """Generate CSV with empty subscription list."""
        csv_content = ExportService.generate_csv([])

        assert "Subscription Export Report" in csv_content
        assert "Total Subscriptions:,0" in csv_content
        assert "Provider" in csv_content

    def test_generate_csv_with_dates(self):
        """Generate CSV with date range metadata."""
        start = date(2025, 1, 1)
        end = date(2025, 1, 31)

        csv_content = ExportService.generate_csv([], start, end)

        assert "Start Date:,2025-01-01" in csv_content
        assert "End Date:,2025-01-31" in csv_content

    def test_generate_pdf_html_empty(self):
        """Generate PDF HTML with empty subscription list."""
        html_content = ExportService.generate_pdf_html([])

        assert "<!DOCTYPE html>" in html_content
        assert "Subscription Report" in html_content
        assert "<table>" in html_content

        # Should show 0 subscriptions
        assert html_content.count('<div class="stat-value">0</div>') >= 2

    def test_generate_pdf_html_with_dates(self):
        """Generate PDF HTML with date range metadata."""
        start = date(2025, 1, 1)
        end = date(2025, 1, 31)

        html_content = ExportService.generate_pdf_html([], start, end)

        # Should include period information
        assert "Period:" in html_content
        assert "January" in html_content
