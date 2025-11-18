"""
Budget API endpoints for managing spending limits and alerts.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.budget import Budget
from app.schemas.budget import (
    BudgetCreate,
    BudgetUpdate,
    BudgetResponse,
    BudgetStatusResponse,
    BudgetAlertResponse
)
from app.services.budget_service import BudgetService
from app.security.dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget_data: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new budget.

    Budgets can be category-specific or overall (category=None).
    """
    # Check for duplicate budget name for this user
    existing = db.query(Budget).filter(
        Budget.user_id == current_user.id,
        Budget.name == budget_data.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Budget with name '{budget_data.name}' already exists"
        )

    # Create budget
    budget = Budget(
        user_id=current_user.id,
        name=budget_data.name,
        category=budget_data.category,
        period=budget_data.period,
        limit_amount=budget_data.limit_amount,
        currency=budget_data.currency,
        alert_threshold=budget_data.alert_threshold,
        alert_enabled='true' if budget_data.alert_enabled else 'false'
    )

    db.add(budget)
    db.commit()
    db.refresh(budget)

    logger.info(f"Created budget {budget.id} for user {current_user.id}")

    return budget


@router.get("/", response_model=List[BudgetResponse])
async def list_budgets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all budgets for the current user.
    """
    budgets = db.query(Budget).filter(
        Budget.user_id == current_user.id
    ).order_by(Budget.created_at.desc()).all()

    return budgets


@router.get("/status", response_model=List[BudgetStatusResponse])
async def get_budgets_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get status for all budgets including current spending and alerts.
    """
    statuses = BudgetService.get_all_budgets_status(db, str(current_user.id))
    return statuses


@router.get("/alerts", response_model=List[BudgetAlertResponse])
async def get_budget_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all active budget alerts (warning or exceeded).
    """
    alerts = BudgetService.check_budget_alerts(db, str(current_user.id))
    return alerts


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific budget by ID.
    """
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    return budget


@router.get("/{budget_id}/status", response_model=BudgetStatusResponse)
async def get_budget_status(
    budget_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed status for a specific budget including spending and alerts.
    """
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    status = BudgetService.get_budget_status(db, budget)
    return status


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: UUID,
    budget_data: BudgetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing budget.
    """
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    # Check for duplicate name if name is being changed
    if budget_data.name and budget_data.name != budget.name:
        existing = db.query(Budget).filter(
            Budget.user_id == current_user.id,
            Budget.name == budget_data.name,
            Budget.id != budget_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Budget with name '{budget_data.name}' already exists"
            )

    # Update fields
    update_data = budget_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == 'alert_enabled':
            setattr(budget, field, 'true' if value else 'false')
        else:
            setattr(budget, field, value)

    db.commit()
    db.refresh(budget)

    logger.info(f"Updated budget {budget.id}")

    return budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a budget.
    """
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.user_id == current_user.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    db.delete(budget)
    db.commit()

    logger.info(f"Deleted budget {budget_id}")

    return None
