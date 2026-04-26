"""
Unit tests for app.services.price_history_recorder.

Uses a real SQLite in-memory database (via the shared conftest fixtures) so
that ``db.add()`` behaviour is tested realistically without needing commits.
"""

from decimal import Decimal
from unittest.mock import MagicMock

from app.services.price_history_recorder import (
    record_initial_price,
    record_price_change,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sub(provider: str = "Netflix", currency: str = "EUR"):
    """Return a lightweight mock Subscription with the minimum attributes."""
    sub = MagicMock()
    sub.id = "test-sub-id"
    sub.provider = provider
    sub.currency = currency
    return sub


# ---------------------------------------------------------------------------
# record_price_change
# ---------------------------------------------------------------------------


class TestRecordPriceChange:
    def test_increase_sets_correct_change_type(self, db_session):
        sub = _make_sub()
        record = record_price_change(
            db_session, sub, old_amount=10.0, new_amount=15.0, notes="test"
        )
        assert record is not None
        assert record.change_type == "increase"

    def test_decrease_sets_correct_change_type(self, db_session):
        sub = _make_sub()
        record = record_price_change(
            db_session, sub, old_amount=20.0, new_amount=15.0, notes="test"
        )
        assert record is not None
        assert record.change_type == "decrease"

    def test_change_percentage_increase_is_correct(self, db_session):
        sub = _make_sub()
        # 10 → 12: +20 %
        record = record_price_change(
            db_session, sub, old_amount=10.0, new_amount=12.0, notes="test"
        )
        assert record is not None
        assert abs(float(record.change_percentage) - 20.0) < 0.01

    def test_change_percentage_decrease_is_correct(self, db_session):
        sub = _make_sub()
        # 20 → 15: -25 %
        record = record_price_change(
            db_session, sub, old_amount=20.0, new_amount=15.0, notes="test"
        )
        assert record is not None
        assert abs(float(record.change_percentage) - (-25.0)) < 0.01

    def test_decimal_amounts_accepted(self, db_session):
        sub = _make_sub()
        record = record_price_change(
            db_session,
            sub,
            old_amount=Decimal("9.99"),
            new_amount=Decimal("12.99"),
            notes="test",
        )
        assert record is not None
        assert record.change_type == "increase"

    def test_none_old_amount_returns_none(self, db_session):
        sub = _make_sub()
        result = record_price_change(
            db_session, sub, old_amount=None, new_amount=15.0, notes="test"
        )
        assert result is None

    def test_none_new_amount_returns_none(self, db_session):
        sub = _make_sub()
        result = record_price_change(
            db_session, sub, old_amount=10.0, new_amount=None, notes="test"
        )
        assert result is None

    def test_both_none_returns_none(self, db_session):
        sub = _make_sub()
        result = record_price_change(
            db_session, sub, old_amount=None, new_amount=None, notes="test"
        )
        assert result is None

    def test_currency_carried_from_subscription(self, db_session):
        sub = _make_sub(currency="USD")
        record = record_price_change(
            db_session, sub, old_amount=10.0, new_amount=12.0, notes="test"
        )
        assert record is not None
        assert record.currency == "USD"

    def test_detected_from_default_is_email(self, db_session):
        sub = _make_sub()
        record = record_price_change(
            db_session, sub, old_amount=10.0, new_amount=12.0, notes="test"
        )
        assert record is not None
        assert record.detected_from == "email"

    def test_detected_from_custom_value(self, db_session):
        sub = _make_sub()
        record = record_price_change(
            db_session,
            sub,
            old_amount=10.0,
            new_amount=12.0,
            detected_from="manual",
            notes="test",
        )
        assert record is not None
        assert record.detected_from == "manual"

    def test_record_added_to_session(self, db_session):
        sub = _make_sub()
        db_mock = MagicMock()
        record_price_change(db_mock, sub, old_amount=10.0, new_amount=12.0, notes="t")
        db_mock.add.assert_called_once()


# ---------------------------------------------------------------------------
# record_initial_price
# ---------------------------------------------------------------------------


class TestRecordInitialPrice:
    def test_change_type_is_initial(self, db_session):
        sub = _make_sub()
        record = record_initial_price(db_session, sub, amount=9.99, notes="initial")
        assert record is not None
        assert record.change_type == "initial"

    def test_old_amount_is_none(self, db_session):
        sub = _make_sub()
        record = record_initial_price(db_session, sub, amount=9.99, notes="initial")
        assert record is not None
        assert record.old_amount is None

    def test_change_percentage_is_none(self, db_session):
        sub = _make_sub()
        record = record_initial_price(db_session, sub, amount=9.99, notes="initial")
        assert record is not None
        assert record.change_percentage is None

    def test_new_amount_matches_input(self, db_session):
        sub = _make_sub()
        record = record_initial_price(db_session, sub, amount=12.99, notes="initial")
        assert record is not None
        assert float(record.new_amount) == 12.99

    def test_none_amount_returns_none(self, db_session):
        sub = _make_sub()
        result = record_initial_price(db_session, sub, amount=None, notes="initial")
        assert result is None

    def test_currency_passed_through(self, db_session):
        sub = _make_sub()
        record = record_initial_price(
            db_session, sub, amount=5.0, currency="GBP", notes="initial"
        )
        assert record is not None
        assert record.currency == "GBP"

    def test_detected_from_default_is_email(self, db_session):
        sub = _make_sub()
        record = record_initial_price(db_session, sub, amount=5.0, notes="initial")
        assert record is not None
        assert record.detected_from == "email"

    def test_decimal_amount_accepted(self, db_session):
        sub = _make_sub()
        record = record_initial_price(
            db_session, sub, amount=Decimal("19.99"), notes="initial"
        )
        assert record is not None
        assert record.change_type == "initial"

    def test_record_added_to_session(self, db_session):
        sub = _make_sub()
        db_mock = MagicMock()
        record_initial_price(db_mock, sub, amount=9.99, notes="t")
        db_mock.add.assert_called_once()
