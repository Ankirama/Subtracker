"""
Admin configuration API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import math

from app.database import get_db
from app.models.user import User
from app.security.dependencies import get_current_admin_user
from app.schemas.admin import (
    AdminSettingCreate,
    AdminSettingUpdate,
    AdminSettingResponse,
    AdminSettingListResponse,
    ConfigStatusResponse,
)
from app.services.admin.config_service import ConfigService

router = APIRouter()


@router.get("/config", response_model=AdminSettingListResponse)
async def list_settings(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in key or description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    List all admin settings with optional filtering and pagination

    Args:
        category: Optional category filter
        search: Optional search term
        page: Page number (1-indexed)
        page_size: Items per page
        current_user: Current admin user
        db: Database session

    Returns:
        Paginated list of admin settings
    """
    config_service = ConfigService(db)

    # Get settings (not decrypted for list view)
    settings, total = config_service.list_settings(
        category=category,
        search=search,
        page=page,
        page_size=page_size,
        decrypt=False,  # Don't decrypt for list view
    )

    total_pages = math.ceil(total / page_size)

    return AdminSettingListResponse(
        items=[AdminSettingResponse.model_validate(s) for s in settings],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/config/{key}", response_model=AdminSettingResponse)
async def get_setting(
    key: str,
    decrypt: bool = Query(True, description="Decrypt secret values"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific admin setting by key

    Args:
        key: Setting key
        decrypt: Whether to decrypt secret values
        current_user: Current admin user
        db: Database session

    Returns:
        Admin setting details
    """
    config_service = ConfigService(db)
    setting = config_service.get_setting(key, decrypt=decrypt)

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Setting '{key}' not found"
        )

    return AdminSettingResponse.model_validate(setting)


@router.post(
    "/config", response_model=AdminSettingResponse, status_code=status.HTTP_201_CREATED
)
async def create_setting(
    setting_data: AdminSettingCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Create a new admin setting

    Args:
        setting_data: Setting data
        current_user: Current admin user
        db: Database session

    Returns:
        Created admin setting

    Raises:
        HTTPException: If setting key already exists
    """
    config_service = ConfigService(db)

    # Check if key already exists
    existing = config_service.get_setting(setting_data.key, decrypt=False)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setting '{setting_data.key}' already exists",
        )

    # Create setting
    setting = config_service.create_setting(
        setting_data=setting_data, admin_user_id=current_user.id
    )

    return AdminSettingResponse.model_validate(setting)


@router.put("/config/{key}", response_model=AdminSettingResponse)
async def update_setting(
    key: str,
    setting_data: AdminSettingUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing admin setting

    Args:
        key: Setting key
        setting_data: Updated setting data
        current_user: Current admin user
        db: Database session

    Returns:
        Updated admin setting

    Raises:
        HTTPException: If setting not found
    """
    config_service = ConfigService(db)

    setting = config_service.update_setting(
        key=key, setting_data=setting_data, admin_user_id=current_user.id
    )

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Setting '{key}' not found"
        )

    return AdminSettingResponse.model_validate(setting)


@router.delete("/config/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    key: str,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Delete an admin setting

    Args:
        key: Setting key
        current_user: Current admin user
        db: Database session

    Raises:
        HTTPException: If setting not found
    """
    config_service = ConfigService(db)

    deleted = config_service.delete_setting(key=key, admin_user_id=current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Setting '{key}' not found"
        )

    return None


@router.get("/config/status", response_model=ConfigStatusResponse)
async def get_config_status(
    current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)
):
    """
    Get configuration status showing missing, incomplete, and valid settings.

    This endpoint checks which settings from config_helper are properly configured
    in the database and identifies any issues that need attention.

    Args:
        current_user: Current admin user
        db: Database session

    Returns:
        Configuration status with lists of missing, incomplete, and valid settings
    """
    from app.models.admin import AdminSetting

    # Define expected settings (matches config_helper mappings)
    EXPECTED_SETTINGS = {
        "resend.api_key": {
            "category": "email",
            "value_type": "string",
            "is_secret": True,
            "required": True,
        },
        "resend.from_email": {
            "category": "email",
            "value_type": "string",
            "is_secret": False,
            "required": True,
        },
        "resend.from_name": {
            "category": "email",
            "value_type": "string",
            "is_secret": False,
            "required": True,
        },
        "openai.api_key": {
            "category": "ai",
            "value_type": "string",
            "is_secret": True,
            "required": True,
        },
        "openai.assistant_id": {
            "category": "ai",
            "value_type": "string",
            "is_secret": False,
            "required": False,
        },
        "openai.request_delay_seconds": {
            "category": "ai",
            "value_type": "number",
            "is_secret": False,
            "required": True,
        },
        "openai.max_requests_per_minute": {
            "category": "ai",
            "value_type": "number",
            "is_secret": False,
            "required": True,
        },
        "email.default_batch_size": {
            "category": "processing",
            "value_type": "number",
            "is_secret": False,
            "required": True,
        },
        "email.confidence_auto_accept": {
            "category": "processing",
            "value_type": "number",
            "is_secret": False,
            "required": True,
        },
        "email.confidence_review_min": {
            "category": "processing",
            "value_type": "number",
            "is_secret": False,
            "required": True,
        },
        "email.default_sync_period_days": {
            "category": "processing",
            "value_type": "number",
            "is_secret": False,
            "required": True,
        },
        "frontend.url": {
            "category": "application",
            "value_type": "string",
            "is_secret": False,
            "required": True,
        },
    }

    # Get all existing admin settings
    existing_settings = {s.key: s for s in db.query(AdminSetting).all()}

    missing = []
    incomplete = []
    valid = []
    extra = []

    # Check expected settings
    for key, expected in EXPECTED_SETTINGS.items():
        if key not in existing_settings:
            missing.append(
                {
                    "key": key,
                    "category": expected["category"],
                    "required": expected["required"],
                    "description": f"Setting {key} is missing from database",
                }
            )
        else:
            setting = existing_settings[key]
            issues = []

            # Check if value is missing for required settings
            if expected["required"] and not setting.value:
                issues.append("missing_value")

            # Check type mismatch
            if setting.value_type != expected["value_type"]:
                issues.append("type_mismatch")

            if issues:
                incomplete.append(
                    {"key": key, "category": expected["category"], "issues": issues}
                )
            else:
                valid.append({"key": key, "category": expected["category"]})

    # Check for extra settings
    for key in existing_settings:
        if key not in EXPECTED_SETTINGS:
            extra.append(
                {
                    "key": key,
                    "category": existing_settings[key].category,
                    "value_type": existing_settings[key].value_type,
                }
            )

    # Generate recommendations
    recommendations = []
    if missing:
        recommendations.append(
            "Run seed script to create missing settings: python -m scripts.seed_admin_settings"
        )
    if incomplete:
        recommendations.append(
            "Update incomplete settings via Admin Panel or re-run seed with --overwrite"
        )

    is_healthy = len(missing) == 0 and len(incomplete) == 0

    return ConfigStatusResponse(
        total_expected=len(EXPECTED_SETTINGS),
        total_found=len(existing_settings),
        valid_count=len(valid),
        incomplete_count=len(incomplete),
        missing_count=len(missing),
        extra_count=len(extra),
        missing=missing,
        incomplete=incomplete,
        valid=valid,
        extra=extra,
        is_healthy=is_healthy,
        recommendations=recommendations,
    )
