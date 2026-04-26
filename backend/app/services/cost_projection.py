"""
Pure-function helpers for converting subscription amounts to different
billing-period equivalents (monthly, yearly, weekly).

Conversion factors used throughout the codebase:
  - monthly  → as-is (identity)
  - yearly   → /12 (monthly), ×12 (yearly), /52 (weekly)
  - weekly   → ×4.33 (monthly), ×52 (yearly), as-is (weekly)
  - quarterly  → /3 (monthly)
  - biannual   → /6 (monthly)
  Unknown / None → 0.0

These helpers replace triplicate inline arithmetic in api/subscriptions.py
(stats and analytics endpoints) and can be used anywhere cost projection
is needed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Union

# Sentinel for unrecognised billing cycles.
_ZERO = 0.0

AmountLike = Union[float, Decimal, int, None]


def _to_float(amount: AmountLike) -> float:
    """Coerce Decimal / int / float to float; return 0.0 for None."""
    if amount is None:
        return _ZERO
    return float(amount)


def project_monthly_cost(
    amount: AmountLike,
    billing_cycle: str | None,
) -> float:
    """
    Return the equivalent monthly cost for *amount* billed on *billing_cycle*.

    Returns 0.0 when either argument is None/falsy or the cycle is unknown.

    Conversion table
    ----------------
    monthly   → amount
    yearly    → amount / 12
    weekly    → amount × 4.33  (average weeks per month)
    quarterly → amount / 3
    biannual  → amount / 6
    """
    if not amount or not billing_cycle:
        return _ZERO

    a = _to_float(amount)
    cycle = billing_cycle.lower()

    if cycle == "monthly":
        return a
    if cycle == "yearly":
        return a / 12
    if cycle == "weekly":
        return a * 4.33
    if cycle == "quarterly":
        return a / 3
    if cycle == "biannual":
        return a / 6
    return _ZERO


def project_yearly_cost(
    amount: AmountLike,
    billing_cycle: str | None,
) -> float:
    """
    Return the equivalent yearly cost for *amount* billed on *billing_cycle*.

    Returns 0.0 when either argument is None/falsy or the cycle is unknown.

    Conversion table
    ----------------
    monthly   → amount × 12
    yearly    → amount
    weekly    → amount × 52
    quarterly → amount × 4
    biannual  → amount × 2
    """
    if not amount or not billing_cycle:
        return _ZERO

    a = _to_float(amount)
    cycle = billing_cycle.lower()

    if cycle == "monthly":
        return a * 12
    if cycle == "yearly":
        return a
    if cycle == "weekly":
        return a * 52
    if cycle == "quarterly":
        return a * 4
    if cycle == "biannual":
        return a * 2
    return _ZERO


def project_weekly_cost(
    amount: AmountLike,
    billing_cycle: str | None,
) -> float:
    """
    Return the equivalent weekly cost for *amount* billed on *billing_cycle*.

    Returns 0.0 when either argument is None/falsy or the cycle is unknown.

    Conversion table
    ----------------
    monthly   → amount / 4.33
    yearly    → amount / 52
    weekly    → amount
    quarterly → amount / 13
    biannual  → amount / 26
    """
    if not amount or not billing_cycle:
        return _ZERO

    a = _to_float(amount)
    cycle = billing_cycle.lower()

    if cycle == "monthly":
        return a / 4.33
    if cycle == "yearly":
        return a / 52
    if cycle == "weekly":
        return a
    if cycle == "quarterly":
        return a / 13
    if cycle == "biannual":
        return a / 26
    return _ZERO
