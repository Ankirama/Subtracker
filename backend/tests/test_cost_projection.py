"""
Unit tests for app.services.cost_projection.

Covers all three projection functions across every supported billing cycle,
plus edge-cases (None amount, None cycle, unknown cycle, Decimal input).
"""

from decimal import Decimal

from app.services.cost_projection import (
    project_monthly_cost,
    project_weekly_cost,
    project_yearly_cost,
)


# ---------------------------------------------------------------------------
# project_monthly_cost
# ---------------------------------------------------------------------------


class TestProjectMonthlyCost:
    def test_monthly_is_identity(self):
        assert project_monthly_cost(10.0, "monthly") == 10.0

    def test_yearly_divides_by_12(self):
        result = project_monthly_cost(120.0, "yearly")
        assert abs(result - 10.0) < 1e-9

    def test_weekly_multiplies_by_4_33(self):
        result = project_monthly_cost(10.0, "weekly")
        assert abs(result - 43.3) < 1e-9

    def test_quarterly_divides_by_3(self):
        result = project_monthly_cost(30.0, "quarterly")
        assert abs(result - 10.0) < 1e-9

    def test_biannual_divides_by_6(self):
        result = project_monthly_cost(60.0, "biannual")
        assert abs(result - 10.0) < 1e-9

    def test_unknown_cycle_returns_zero(self):
        assert project_monthly_cost(10.0, "biennial") == 0.0

    def test_none_amount_returns_zero(self):
        assert project_monthly_cost(None, "monthly") == 0.0

    def test_none_cycle_returns_zero(self):
        assert project_monthly_cost(10.0, None) == 0.0

    def test_both_none_returns_zero(self):
        assert project_monthly_cost(None, None) == 0.0

    def test_decimal_input_accepted(self):
        result = project_monthly_cost(Decimal("120.00"), "yearly")
        assert abs(result - 10.0) < 1e-9

    def test_zero_amount_returns_zero(self):
        # 0 is falsy; treated as "no amount"
        assert project_monthly_cost(0, "monthly") == 0.0

    def test_cycle_case_insensitive(self):
        assert project_monthly_cost(10.0, "MONTHLY") == 10.0
        assert abs(project_monthly_cost(120.0, "YEARLY") - 10.0) < 1e-9


# ---------------------------------------------------------------------------
# project_yearly_cost
# ---------------------------------------------------------------------------


class TestProjectYearlyCost:
    def test_monthly_multiplies_by_12(self):
        result = project_yearly_cost(10.0, "monthly")
        assert abs(result - 120.0) < 1e-9

    def test_yearly_is_identity(self):
        assert project_yearly_cost(99.0, "yearly") == 99.0

    def test_weekly_multiplies_by_52(self):
        result = project_yearly_cost(2.0, "weekly")
        assert abs(result - 104.0) < 1e-9

    def test_quarterly_multiplies_by_4(self):
        result = project_yearly_cost(25.0, "quarterly")
        assert abs(result - 100.0) < 1e-9

    def test_biannual_multiplies_by_2(self):
        result = project_yearly_cost(50.0, "biannual")
        assert abs(result - 100.0) < 1e-9

    def test_unknown_cycle_returns_zero(self):
        assert project_yearly_cost(10.0, "biennial") == 0.0

    def test_none_amount_returns_zero(self):
        assert project_yearly_cost(None, "monthly") == 0.0

    def test_none_cycle_returns_zero(self):
        assert project_yearly_cost(10.0, None) == 0.0

    def test_decimal_input_accepted(self):
        result = project_yearly_cost(Decimal("10.00"), "monthly")
        assert abs(result - 120.0) < 1e-9


# ---------------------------------------------------------------------------
# project_weekly_cost
# ---------------------------------------------------------------------------


class TestProjectWeeklyCost:
    def test_weekly_is_identity(self):
        assert project_weekly_cost(5.0, "weekly") == 5.0

    def test_monthly_divides_by_4_33(self):
        result = project_weekly_cost(43.3, "monthly")
        assert abs(result - 10.0) < 0.001

    def test_yearly_divides_by_52(self):
        result = project_weekly_cost(52.0, "yearly")
        assert abs(result - 1.0) < 1e-9

    def test_quarterly_divides_by_13(self):
        result = project_weekly_cost(130.0, "quarterly")
        assert abs(result - 10.0) < 1e-9

    def test_biannual_divides_by_26(self):
        result = project_weekly_cost(260.0, "biannual")
        assert abs(result - 10.0) < 1e-9

    def test_unknown_cycle_returns_zero(self):
        assert project_weekly_cost(10.0, "biennial") == 0.0

    def test_none_amount_returns_zero(self):
        assert project_weekly_cost(None, "weekly") == 0.0

    def test_none_cycle_returns_zero(self):
        assert project_weekly_cost(10.0, None) == 0.0

    def test_decimal_input_accepted(self):
        result = project_weekly_cost(Decimal("52.00"), "yearly")
        assert abs(result - 1.0) < 1e-9
