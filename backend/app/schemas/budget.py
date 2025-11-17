"""
Pydantic schemas for Budget API requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from uuid import UUID


class BudgetCreate(BaseModel):
    """Schema for creating a new budget."""
    name: str = Field(..., min_length=1, max_length=255, description="Budget name")
    category: Optional[str] = Field(None, max_length=100, description="Category (None for overall budget)")
    period: str = Field('monthly', description="Budget period: monthly, quarterly, yearly")
    limit_amount: float = Field(..., gt=0, description="Budget limit amount")
    currency: str = Field('EUR', min_length=3, max_length=3, description="Currency code")
    alert_threshold: int = Field(80, ge=0, le=100, description="Alert threshold percentage (0-100)")
    alert_enabled: bool = Field(True, description="Enable budget alerts")

    @validator('period')
    def validate_period(cls, v):
        allowed = ['monthly', 'quarterly', 'yearly']
        if v not in allowed:
            raise ValueError(f'period must be one of: {", ".join(allowed)}')
        return v

    @validator('currency')
    def validate_currency(cls, v):
        return v.upper()

    class Config:
        schema_extra = {
            "example": {
                "name": "Entertainment Budget",
                "category": "entertainment",
                "period": "monthly",
                "limit_amount": 50.00,
                "currency": "EUR",
                "alert_threshold": 80,
                "alert_enabled": True
            }
        }


class BudgetUpdate(BaseModel):
    """Schema for updating an existing budget."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    period: Optional[str] = None
    limit_amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    alert_threshold: Optional[int] = Field(None, ge=0, le=100)
    alert_enabled: Optional[bool] = None

    @validator('period')
    def validate_period(cls, v):
        if v is not None:
            allowed = ['monthly', 'quarterly', 'yearly']
            if v not in allowed:
                raise ValueError(f'period must be one of: {", ".join(allowed)}')
        return v

    @validator('currency')
    def validate_currency(cls, v):
        if v is not None:
            return v.upper()
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Budget Name",
                "limit_amount": 75.00,
                "alert_threshold": 85
            }
        }


class BudgetResponse(BaseModel):
    """Schema for budget response."""
    id: UUID
    user_id: UUID
    name: str
    category: Optional[str]
    period: str
    limit_amount: float
    currency: str
    alert_threshold: int
    alert_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "name": "Entertainment Budget",
                "category": "entertainment",
                "period": "monthly",
                "limit_amount": 50.00,
                "currency": "EUR",
                "alert_threshold": 80,
                "alert_enabled": True,
                "created_at": "2025-01-15T10:00:00Z",
                "updated_at": "2025-01-15T10:00:00Z"
            }
        }


class BudgetStatusResponse(BaseModel):
    """Schema for budget status with spending information."""
    budget_id: str
    name: str
    category: Optional[str]
    period: str
    limit_amount: float
    current_spending: float
    remaining: float
    percentage_used: float
    status: str  # 'good', 'warning', 'exceeded'
    alert_threshold: int
    alert_enabled: bool
    period_start: str  # ISO date
    period_end: str  # ISO date
    currency: str

    class Config:
        schema_extra = {
            "example": {
                "budget_id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Entertainment Budget",
                "category": "entertainment",
                "period": "monthly",
                "limit_amount": 50.00,
                "current_spending": 42.50,
                "remaining": 7.50,
                "percentage_used": 85.0,
                "status": "warning",
                "alert_threshold": 80,
                "alert_enabled": True,
                "period_start": "2025-01-01",
                "period_end": "2025-01-31",
                "currency": "EUR"
            }
        }


class BudgetAlertResponse(BaseModel):
    """Schema for budget alerts."""
    budget: BudgetStatusResponse
    alert_type: str  # 'warning' or 'exceeded'
    message: str

    class Config:
        schema_extra = {
            "example": {
                "budget": {
                    "budget_id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Entertainment Budget",
                    "category": "entertainment",
                    "limit_amount": 50.00,
                    "current_spending": 55.00,
                    "percentage_used": 110.0,
                    "status": "exceeded"
                },
                "alert_type": "exceeded",
                "message": "Budget 'Entertainment Budget' is at 110.0% (55.00/50.00 EUR)"
            }
        }
