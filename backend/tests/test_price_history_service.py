"""Comprehensive tests for price_history_service"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.price_history_service import PriceHistoryService
from app.models.price_history import PriceHistory
from app.models.subscription import Subscription
from app.models.user import User


@pytest.fixture
def test_subscription_with_amount(db_session: Session, test_user: User) -> Subscription:
    """Create a test subscription with an amount"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="Test Service",
        amount=9.99,
        currency="USD",
        billing_cycle="monthly",
        is_active=True
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def test_subscription_no_amount(db_session: Session, test_user: User) -> Subscription:
    """Create a test subscription without an amount"""
    sub = Subscription(
        id=uuid4(),
        user_id=test_user.id,
        provider="New Service",
        amount=None,
        currency="USD",
        billing_cycle="monthly",
        is_active=True
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


class TestRecordPriceChange:
    """Tests for record_price_change method"""

    def test_records_initial_price(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should record initial price with no old amount"""
        result = PriceHistoryService.record_price_change(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id),
            new_amount=9.99,
            old_amount=None,
            detected_from="manual"
        )

        assert result is not None
        assert result.subscription_id == test_subscription_with_amount.id
        assert result.old_amount is None
        assert float(result.new_amount) == 9.99
        assert result.currency == "USD"
        assert result.change_type == "initial"
        assert result.change_percentage is None
        assert result.detected_from == "manual"

    def test_records_price_increase(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should record price increase with correct percentage"""
        result = PriceHistoryService.record_price_change(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id),
            new_amount=12.99,
            old_amount=9.99,
            detected_from="email"
        )

        assert result is not None
        assert float(result.old_amount) == 9.99
        assert float(result.new_amount) == 12.99
        assert result.change_type == "increase"
        # ((12.99 - 9.99) / 9.99) * 100 = 30.03%
        assert float(result.change_percentage) == pytest.approx(30.03, rel=0.01)

    def test_records_price_decrease(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should record price decrease with correct percentage"""
        result = PriceHistoryService.record_price_change(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id),
            new_amount=7.99,
            old_amount=9.99,
            detected_from="api"
        )

        assert result is not None
        assert float(result.old_amount) == 9.99
        assert float(result.new_amount) == 7.99
        assert result.change_type == "decrease"
        # ((9.99 - 7.99) / 9.99) * 100 = 20.02%
        assert float(result.change_percentage) == pytest.approx(20.02, rel=0.01)

    def test_returns_none_for_no_change(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should return None if price hasn't changed"""
        result = PriceHistoryService.record_price_change(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id),
            new_amount=9.99,
            old_amount=9.99,
            detected_from="manual"
        )

        assert result is None

    def test_raises_error_for_nonexistent_subscription(self, db_session: Session):
        """Should raise ValueError for nonexistent subscription"""
        fake_id = str(uuid4())

        with pytest.raises(ValueError, match=f"Subscription {fake_id} not found"):
            PriceHistoryService.record_price_change(
                db=db_session,
                subscription_id=fake_id,
                new_amount=9.99
            )

    def test_includes_notes(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should include notes when provided"""
        result = PriceHistoryService.record_price_change(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id),
            new_amount=14.99,
            old_amount=9.99,
            detected_from="manual",
            notes="Annual price hike"
        )

        assert result.notes == "Annual price hike"


class TestCheckAndRecordPriceChange:
    """Tests for check_and_record_price_change method"""

    def test_records_initial_price_when_subscription_has_none(
        self,
        db_session: Session,
        test_subscription_no_amount: Subscription
    ):
        """Should record initial price and update subscription"""
        result = PriceHistoryService.check_and_record_price_change(
            db=db_session,
            subscription=test_subscription_no_amount,
            new_amount=15.99,
            detected_from="email"
        )

        assert result is not None
        assert result.change_type == "initial"
        assert float(result.new_amount) == 15.99
        assert result.notes == "Initial price recorded"

        # Verify subscription was updated
        db_session.refresh(test_subscription_no_amount)
        assert float(test_subscription_no_amount.amount) == 15.99

    def test_detects_and_records_price_change(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should detect price change and record it"""
        result = PriceHistoryService.check_and_record_price_change(
            db=db_session,
            subscription=test_subscription_with_amount,
            new_amount=12.99,
            detected_from="email"
        )

        assert result is not None
        assert result.change_type == "increase"
        assert float(result.old_amount) == 9.99
        assert float(result.new_amount) == 12.99
        assert "Price changed from 9.99 to 12.99" in result.notes

        # Verify subscription was updated
        db_session.refresh(test_subscription_with_amount)
        assert float(test_subscription_with_amount.amount) == 12.99

    def test_ignores_tiny_price_differences(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should ignore differences within floating point tolerance"""
        result = PriceHistoryService.check_and_record_price_change(
            db=db_session,
            subscription=test_subscription_with_amount,
            new_amount=9.991,  # Within 0.01 tolerance
            detected_from="email"
        )

        assert result is None

        # Subscription should not be updated
        db_session.refresh(test_subscription_with_amount)
        assert float(test_subscription_with_amount.amount) == 9.99

    def test_detects_price_decrease(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should detect and record price decrease"""
        result = PriceHistoryService.check_and_record_price_change(
            db=db_session,
            subscription=test_subscription_with_amount,
            new_amount=7.99,
            detected_from="api"
        )

        assert result is not None
        assert result.change_type == "decrease"
        assert float(result.old_amount) == 9.99
        assert float(result.new_amount) == 7.99


class TestGetSubscriptionPriceHistory:
    """Tests for get_subscription_price_history method"""

    def test_returns_all_history_records(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should return all price history records"""
        # Create multiple price history records
        for i, amount in enumerate([9.99, 12.99, 14.99]):
            history = PriceHistory(
                subscription_id=test_subscription_with_amount.id,
                old_amount=amount - 1 if i > 0 else None,
                new_amount=amount,
                currency="USD",
                change_type="increase" if i > 0 else "initial",
                detected_from="test",
                detected_at=datetime.utcnow() + timedelta(hours=i)
            )
            db_session.add(history)
        db_session.commit()

        result = PriceHistoryService.get_subscription_price_history(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id)
        )

        assert len(result) == 3
        # Should be ordered by detected_at descending (newest first)
        assert float(result[0].new_amount) == 14.99
        assert float(result[1].new_amount) == 12.99
        assert float(result[2].new_amount) == 9.99

    def test_limits_results_when_specified(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should limit results when limit is specified"""
        # Create 5 records
        for i in range(5):
            history = PriceHistory(
                subscription_id=test_subscription_with_amount.id,
                new_amount=10.00 + i,
                currency="USD",
                change_type="initial" if i == 0 else "increase",
                detected_from="test",
                detected_at=datetime.utcnow() + timedelta(hours=i)
            )
            db_session.add(history)
        db_session.commit()

        result = PriceHistoryService.get_subscription_price_history(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id),
            limit=3
        )

        assert len(result) == 3

    def test_returns_empty_list_for_no_history(self, db_session: Session):
        """Should return empty list if no history exists"""
        fake_id = str(uuid4())

        result = PriceHistoryService.get_subscription_price_history(
            db=db_session,
            subscription_id=fake_id
        )

        assert result == []


class TestGetPriceIncreases:
    """Tests for get_price_increases method"""

    def test_returns_only_increases(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should return only price increase records"""
        # Create mixed history
        changes = [
            ("initial", 9.99),
            ("increase", 12.99),
            ("decrease", 10.99),
            ("increase", 14.99)
        ]

        for i, (change_type, amount) in enumerate(changes):
            history = PriceHistory(
                subscription_id=test_subscription_with_amount.id,
                new_amount=amount,
                currency="USD",
                change_type=change_type,
                detected_from="test",
                detected_at=datetime.utcnow() + timedelta(hours=i)
            )
            db_session.add(history)
        db_session.commit()

        result = PriceHistoryService.get_price_increases(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id)
        )

        assert len(result) == 2
        assert all(h.change_type == "increase" for h in result)
        # Ordered by detected_at descending
        assert float(result[0].new_amount) == 14.99
        assert float(result[1].new_amount) == 12.99

    def test_returns_empty_list_for_no_increases(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should return empty list if no increases"""
        # Create only decrease
        history = PriceHistory(
            subscription_id=test_subscription_with_amount.id,
            new_amount=7.99,
            currency="USD",
            change_type="decrease",
            detected_from="test"
        )
        db_session.add(history)
        db_session.commit()

        result = PriceHistoryService.get_price_increases(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id)
        )

        assert result == []


class TestGetPriceStatistics:
    """Tests for get_price_statistics method"""

    def test_returns_statistics_for_complete_history(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should calculate comprehensive statistics"""
        # Create history: initial 9.99 → increase to 12.99 → decrease to 11.99 → increase to 14.99
        changes = [
            (None, 9.99, "initial", None),
            (9.99, 12.99, "increase", 30.03),
            (12.99, 11.99, "decrease", 7.70),
            (11.99, 14.99, "increase", 25.02)
        ]

        for i, (old, new, change_type, pct) in enumerate(changes):
            history = PriceHistory(
                subscription_id=test_subscription_with_amount.id,
                old_amount=old,
                new_amount=new,
                currency="USD",
                change_type=change_type,
                change_percentage=pct,
                detected_from="test",
                detected_at=datetime.utcnow() + timedelta(hours=i)  # Add timestamp for proper ordering
            )
            db_session.add(history)
        db_session.commit()

        result = PriceHistoryService.get_price_statistics(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id)
        )

        assert result["total_changes"] == 3  # Excludes initial
        assert result["increases"] == 2
        assert result["decreases"] == 1
        assert result["total_increase_amount"] == pytest.approx(6.0, rel=0.01)  # (12.99-9.99) + (14.99-11.99)
        assert result["total_decrease_amount"] == pytest.approx(1.0, rel=0.01)  # (12.99-11.99)
        # Average percentage: (30.03 + 7.70 + 25.02) / 3 = 20.92%
        assert result["average_change_percentage"] == pytest.approx(20.92, rel=0.1)
        assert result["latest_price"] == 14.99
        assert result["original_price"] == 9.99

    def test_returns_zero_statistics_for_no_history(self, db_session: Session):
        """Should return zero statistics if no history"""
        fake_id = str(uuid4())

        result = PriceHistoryService.get_price_statistics(
            db=db_session,
            subscription_id=fake_id
        )

        assert result["total_changes"] == 0
        assert result["increases"] == 0
        assert result["decreases"] == 0
        assert result["total_increase_amount"] == 0.0
        assert result["total_decrease_amount"] == 0.0
        assert result["average_change_percentage"] == 0.0
        assert result["latest_price"] is None
        assert result["original_price"] is None

    def test_handles_only_increases(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should calculate statistics for only increases"""
        changes = [
            (None, 9.99, "initial", None),
            (9.99, 12.99, "increase", 30.03),
            (12.99, 15.99, "increase", 23.09)
        ]

        for old, new, change_type, pct in changes:
            history = PriceHistory(
                subscription_id=test_subscription_with_amount.id,
                old_amount=old,
                new_amount=new,
                currency="USD",
                change_type=change_type,
                change_percentage=pct,
                detected_from="test"
            )
            db_session.add(history)
        db_session.commit()

        result = PriceHistoryService.get_price_statistics(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id)
        )

        assert result["increases"] == 2
        assert result["decreases"] == 0
        assert result["total_increase_amount"] == pytest.approx(6.0, rel=0.01)
        assert result["total_decrease_amount"] == 0.0

    def test_handles_only_initial_record(
        self,
        db_session: Session,
        test_subscription_with_amount: Subscription
    ):
        """Should handle case with only initial record"""
        history = PriceHistory(
            subscription_id=test_subscription_with_amount.id,
            old_amount=None,
            new_amount=9.99,
            currency="USD",
            change_type="initial",
            change_percentage=None,
            detected_from="test"
        )
        db_session.add(history)
        db_session.commit()

        result = PriceHistoryService.get_price_statistics(
            db=db_session,
            subscription_id=str(test_subscription_with_amount.id)
        )

        assert result["total_changes"] == 0
        assert result["latest_price"] == 9.99
        assert result["original_price"] == 9.99
