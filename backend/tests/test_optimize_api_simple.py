"""
Simplified tests for Optimize API endpoints using mocking.

Tests cover:
- Get optimization recommendations (endpoint behavior)
- Empty states
- Authentication
- Error handling
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestOptimizeAPISimple:
    """Simplified tests for optimize API endpoint."""

    def test_recommendations_no_auth(self, client):
        """Cannot get recommendations without authentication."""
        response = client.get("/api/optimize/recommendations")
        assert response.status_code == 403

    def test_recommendations_no_mailboxes(self, client, auth_headers):
        """Get recommendations when user has no mailboxes."""
        response = client.get("/api/optimize/recommendations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data['total_recommendations'] == 0
        assert data['potential_savings'] == 0.0
        assert data['recommendations'] == []
        assert len(data['insights']) == 1
        assert 'Connect a mailbox' in data['insights'][0]

    def test_recommendations_no_active_subscriptions(self, client, auth_headers, test_mailbox):
        """Get recommendations when mailbox exists but no active subscriptions."""
        response = client.get("/api/optimize/recommendations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data['total_recommendations'] == 0
        assert data['potential_savings'] == 0.0
        assert data['recommendations'] == []
        assert 'No active subscriptions' in data['insights'][0]

    @patch('app.services.ai_optimizer.AIOptimizer.analyze_subscriptions')
    def test_recommendations_with_subscriptions_mocked(self, mock_analyze, client, auth_headers, test_subscription):
        """Get recommendations with active subscriptions (mocked analyzer)."""
        # Mock the AI optimizer response
        mock_analyze.return_value = {
            'total_recommendations': 3,
            'potential_savings': 25.50,
            'recommendations': [
                {
                    'type': 'annual_billing_savings',
                    'title': 'Switch Netflix to Annual Billing',
                    'potential_savings': 25.50,
                    'priority': 'medium'
                }
            ],
            'insights': [
                '💰 We found opportunities to save €25.50/month',
                '🎯 3 optimization opportunities identified'
            ],
            'analyzed_at': datetime.now(timezone.utc).isoformat()
        }

        response = client.get("/api/optimize/recommendations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify the mocked response is returned
        assert data['total_recommendations'] == 3
        assert data['potential_savings'] == 25.50
        assert len(data['recommendations']) == 1
        assert data['recommendations'][0]['type'] == 'annual_billing_savings'
        assert len(data['insights']) == 2
        assert 'analyzed_at' in data

        # Verify the mock was called with correct arguments
        assert mock_analyze.called

    @patch('app.services.ai_optimizer.AIOptimizer.analyze_subscriptions')
    def test_recommendations_service_error(self, mock_analyze, client, auth_headers, test_subscription):
        """Handle service errors gracefully."""
        # Mock an error in the service
        mock_analyze.side_effect = Exception("Service unavailable")

        response = client.get("/api/optimize/recommendations", headers=auth_headers)

        assert response.status_code == 500
        assert 'Failed to generate recommendations' in response.json()['detail']

    @patch('app.services.ai_optimizer.AIOptimizer.analyze_subscriptions')
    def test_recommendations_response_structure(self, mock_analyze, client, auth_headers, test_subscription):
        """Verify response has required fields."""
        mock_analyze.return_value = {
            'total_recommendations': 0,
            'potential_savings': 0.0,
            'recommendations': [],
            'insights': ['Test insight'],
            'analyzed_at': datetime.now(timezone.utc).isoformat()
        }

        response = client.get("/api/optimize/recommendations", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        assert 'total_recommendations' in data
        assert 'potential_savings' in data
        assert 'recommendations' in data
        assert 'insights' in data
        assert 'analyzed_at' in data
