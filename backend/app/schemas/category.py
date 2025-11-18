"""
Pydantic schemas for category endpoints.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class CategoryCreate(BaseModel):
    """Schema for creating a custom category."""
    name: str = Field(..., min_length=1, max_length=100, description="Category name (lowercase, no spaces)")
    display_name: str = Field(..., min_length=1, max_length=100, description="Display name")
    color: str = Field(default='gray', max_length=50, description="Chakra UI color scheme")


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    """Schema for category response."""
    id: Optional[UUID] = None  # None for default categories
    name: str
    display_name: str
    color: str
    is_default: bool
    user_id: Optional[UUID] = None  # None for default categories
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CategoriesListResponse(BaseModel):
    """Schema for categories list response."""
    categories: list[CategoryResponse]
    total: int
