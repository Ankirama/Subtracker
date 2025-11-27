"""
Pydantic schemas for Price History API requests and responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class PriceHistoryResponse(BaseModel):
    """Schema for price history response."""

    id: UUID
    subscription_id: UUID
    old_amount: Optional[float]
    new_amount: float
    currency: str
    change_type: str  # 'increase', 'decrease', 'initial'
    change_percentage: Optional[float]
    detected_from: Optional[str]
    notes: Optional[str]
    detected_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "subscription_id": "123e4567-e89b-12d3-a456-426614174001",
                "old_amount": 9.99,
                "new_amount": 12.99,
                "currency": "EUR",
                "change_type": "increase",
                "change_percentage": 30.03,
                "detected_from": "email",
                "notes": "Price changed from 9.99 to 12.99",
                "detected_at": "2025-01-15T10:00:00Z",
            }
        },
    )


class PriceStatisticsResponse(BaseModel):
    """Schema for price statistics response."""

    total_changes: int
    increases: int
    decreases: int
    total_increase_amount: float
    total_decrease_amount: float
    average_change_percentage: float
    latest_price: Optional[float]
    original_price: Optional[float]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_changes": 3,
                "increases": 2,
                "decreases": 1,
                "total_increase_amount": 6.00,
                "total_decrease_amount": 2.00,
                "average_change_percentage": 25.5,
                "latest_price": 14.99,
                "original_price": 9.99,
            }
        }
    )
