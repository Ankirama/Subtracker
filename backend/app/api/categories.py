"""
API endpoints for managing subscription categories.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import logging

from app.database import get_db
from app.models.user import User
from app.models.category import Category, DEFAULT_CATEGORIES
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoriesListResponse
)
from app.security import get_current_user

router = APIRouter(tags=["categories"])
logger = logging.getLogger(__name__)


@router.get("", response_model=CategoriesListResponse)
async def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all available categories (default + custom).

    Returns default categories plus any custom categories created by the user.
    """
    # Get custom categories for this user
    custom_categories = db.query(Category).filter(
        Category.user_id == current_user.id
    ).all()

    # Build response with default categories
    categories = []

    # Add default categories
    for cat_name, cat_info in DEFAULT_CATEGORIES.items():
        categories.append(CategoryResponse(
            id=None,
            name=cat_name,
            display_name=cat_info['display_name'],
            color=cat_info['color'],
            is_default=True,
            user_id=None,
            created_at=None,
            updated_at=None
        ))

    # Add custom categories
    for cat in custom_categories:
        categories.append(CategoryResponse(
            id=cat.id,
            name=cat.name,
            display_name=cat.display_name,
            color=cat.color,
            is_default=False,
            user_id=cat.user_id,
            created_at=cat.created_at,
            updated_at=cat.updated_at
        ))

    return CategoriesListResponse(
        categories=categories,
        total=len(categories)
    )


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new custom category.

    Category name must be unique for the user and cannot conflict with default categories.
    """
    # Normalize category name (lowercase, replace spaces with underscores)
    cat_name = category_data.name.lower().strip().replace(' ', '_')

    # Check if it conflicts with default categories
    if cat_name in DEFAULT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{cat_name}' is a default category and cannot be created as custom"
        )

    # Check if category already exists for this user
    existing = db.query(Category).filter(
        Category.user_id == current_user.id,
        Category.name == cat_name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{cat_name}' already exists"
        )

    # Create new category
    new_category = Category(
        user_id=current_user.id,
        name=cat_name,
        display_name=category_data.display_name.strip(),
        color=category_data.color,
        is_default=False
    )

    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    logger.info(f"Created custom category '{cat_name}' for user {current_user.id}")

    return CategoryResponse(
        id=new_category.id,
        name=new_category.name,
        display_name=new_category.display_name,
        color=new_category.color,
        is_default=False,
        user_id=new_category.user_id,
        created_at=new_category.created_at,
        updated_at=new_category.updated_at
    )


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a custom category.

    Only custom categories can be deleted (not default ones).
    """
    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user.id
    ).first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    if category.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default categories cannot be deleted"
        )

    db.delete(category)
    db.commit()

    logger.info(f"Deleted custom category '{category.name}' for user {current_user.id}")

    return None
