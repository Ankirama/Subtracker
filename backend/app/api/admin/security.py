"""
Admin API endpoints for security events management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc
from typing import Optional
import uuid
from datetime import datetime, timedelta

from app.database import get_db
from app.models.admin import SecurityEvent
from app.models.ip_whitelist import IPWhitelist
from app.models.user import User
from app.schemas.admin import (
    SecurityEventResponse,
    SecurityEventListResponse,
    SecurityEventUpdate,
    IPWhitelistCreate,
    IPWhitelistUpdate,
    IPWhitelistResponse,
    IPWhitelistListResponse,
)
from app.security.dependencies import get_current_admin_user

router = APIRouter(prefix="/admin/security", tags=["admin-security"])


@router.get("", response_model=SecurityEventListResponse, dependencies=[Depends(get_current_admin_user)])
async def list_security_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_resolved: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """
    List security events with pagination and filtering.

    - **page**: Page number (starts at 1)
    - **page_size**: Items per page (1-100)
    - **event_type**: Filter by event type
    - **severity**: Filter by severity level (low, medium, high, critical)
    - **is_resolved**: Filter by resolution status
    """
    query = db.query(SecurityEvent)

    # Apply filters
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)

    if severity:
        query = query.filter(SecurityEvent.severity == severity)

    if is_resolved is not None:
        query = query.filter(SecurityEvent.is_resolved == is_resolved)

    # Get total count
    total = query.count()

    # Apply pagination and ordering (most recent first)
    offset = (page - 1) * page_size
    events = query.order_by(desc(SecurityEvent.created_at)).offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size

    return {
        "items": [
            SecurityEventResponse(
                id=event.id,
                event_type=event.event_type,
                user_id=event.user_id,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                details=event.details,
                severity=event.severity,
                is_resolved=event.is_resolved,
                resolved_at=event.resolved_at,
                created_at=event.created_at,
            )
            for event in events
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/stats", dependencies=[Depends(get_current_admin_user)])
async def get_security_stats(db: Session = Depends(get_db)):
    """
    Get security event statistics.
    """
    total_events = db.query(func.count(SecurityEvent.id)).scalar()
    unresolved_events = db.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.is_resolved == False
    ).scalar()

    # Events in last 24 hours
    last_24h = datetime.utcnow() - timedelta(hours=24)
    events_24h = db.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.created_at >= last_24h
    ).scalar()

    # Critical unresolved events
    critical_unresolved = db.query(func.count(SecurityEvent.id)).filter(
        SecurityEvent.severity == 'critical',
        SecurityEvent.is_resolved == False
    ).scalar()

    # Events by severity (unresolved only)
    severity_counts = {}
    for severity in ['low', 'medium', 'high', 'critical']:
        count = db.query(func.count(SecurityEvent.id)).filter(
            SecurityEvent.severity == severity,
            SecurityEvent.is_resolved == False
        ).scalar()
        severity_counts[severity] = count

    return {
        "total_events": total_events,
        "unresolved_events": unresolved_events,
        "events_24h": events_24h,
        "critical_unresolved": critical_unresolved,
        "by_severity": severity_counts
    }


@router.get("/event-types", dependencies=[Depends(get_current_admin_user)])
async def get_event_types(db: Session = Depends(get_db)):
    """
    Get list of available event types.
    """
    # Get distinct event types from database
    event_types = db.query(SecurityEvent.event_type).distinct().all()

    return {
        "event_types": [et[0] for et in event_types if et[0]]
    }


# IP Whitelist Endpoints (must come before /{event_id} to avoid route conflicts)
@router.get("/ip-whitelist", response_model=IPWhitelistListResponse, dependencies=[Depends(get_current_admin_user)])
async def list_ip_whitelist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all whitelisted IP addresses with pagination.

    - **page**: Page number (starts at 1)
    - **page_size**: Items per page (1-100)
    """
    query = db.query(IPWhitelist)

    # Get total count
    total = query.count()

    # Apply pagination and ordering (most recently added first)
    offset = (page - 1) * page_size
    entries = query.order_by(desc(IPWhitelist.added_at)).offset(offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size

    return {
        "items": [
            IPWhitelistResponse(
                ip_address=entry.ip_address,
                description=entry.description,
                added_by_user_id=entry.added_by_user_id,
                added_at=entry.added_at,
                last_seen=entry.last_seen,
                access_count=entry.access_count,
            )
            for entry in entries
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/ip-whitelist/{ip_address}", response_model=IPWhitelistResponse, dependencies=[Depends(get_current_admin_user)])
async def get_whitelist_entry(
    ip_address: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific whitelisted IP.
    """
    entry = db.query(IPWhitelist).filter(IPWhitelist.ip_address == ip_address).first()

    if not entry:
        raise HTTPException(status_code=404, detail="IP address not found in whitelist")

    return IPWhitelistResponse(
        ip_address=entry.ip_address,
        description=entry.description,
        added_by_user_id=entry.added_by_user_id,
        added_at=entry.added_at,
        last_seen=entry.last_seen,
        access_count=entry.access_count,
    )


@router.post("/ip-whitelist", response_model=IPWhitelistResponse, status_code=201)
async def add_to_whitelist(
    whitelist_data: IPWhitelistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Add an IP address to the whitelist.

    - **ip_address**: The IP address to whitelist (IPv4 or IPv6)
    - **description**: Optional description (e.g., "Admin office IP", "VPN gateway")
    """
    # Check if IP already exists in whitelist
    existing = db.query(IPWhitelist).filter(IPWhitelist.ip_address == whitelist_data.ip_address).first()
    if existing:
        raise HTTPException(status_code=400, detail="IP address already in whitelist")

    # Create new whitelist entry
    new_entry = IPWhitelist(
        ip_address=whitelist_data.ip_address,
        description=whitelist_data.description,
        added_by_user_id=str(current_user.id),
        access_count=0
    )

    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return IPWhitelistResponse(
        ip_address=new_entry.ip_address,
        description=new_entry.description,
        added_by_user_id=new_entry.added_by_user_id,
        added_at=new_entry.added_at,
        last_seen=new_entry.last_seen,
        access_count=new_entry.access_count,
    )


@router.patch("/ip-whitelist/{ip_address}", response_model=IPWhitelistResponse)
async def update_whitelist_entry(
    ip_address: str,
    update_data: IPWhitelistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Update a whitelist entry (typically to update description).

    - **description**: Updated description for the whitelisted IP
    """
    entry = db.query(IPWhitelist).filter(IPWhitelist.ip_address == ip_address).first()

    if not entry:
        raise HTTPException(status_code=404, detail="IP address not found in whitelist")

    # Update description if provided
    if update_data.description is not None:
        entry.description = update_data.description

    db.commit()
    db.refresh(entry)

    return IPWhitelistResponse(
        ip_address=entry.ip_address,
        description=entry.description,
        added_by_user_id=entry.added_by_user_id,
        added_at=entry.added_at,
        last_seen=entry.last_seen,
        access_count=entry.access_count,
    )


@router.delete("/ip-whitelist/{ip_address}")
async def remove_from_whitelist(
    ip_address: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Remove an IP address from the whitelist.

    Use with caution - the IP will be subject to normal brute force protection after removal.
    """
    entry = db.query(IPWhitelist).filter(IPWhitelist.ip_address == ip_address).first()

    if not entry:
        raise HTTPException(status_code=404, detail="IP address not found in whitelist")

    db.delete(entry)
    db.commit()

    return {"success": True, "message": f"IP address {ip_address} removed from whitelist"}


# Security Event Detail Endpoints (parameterized routes come after specific routes)
@router.get("/{event_id}", response_model=SecurityEventResponse, dependencies=[Depends(get_current_admin_user)])
async def get_security_event(
    event_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific security event.
    """
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event ID format")

    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_uuid).first()

    if not event:
        raise HTTPException(status_code=404, detail="Security event not found")

    return SecurityEventResponse(
        id=event.id,
        event_type=event.event_type,
        user_id=event.user_id,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        details=event.details,
        severity=event.severity,
        is_resolved=event.is_resolved,
        resolved_at=event.resolved_at,
        created_at=event.created_at,
    )


@router.patch("/{event_id}", response_model=SecurityEventResponse, dependencies=[Depends(get_current_admin_user)])
async def update_security_event(
    event_id: str,
    update_data: SecurityEventUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a security event (typically to mark as resolved).

    - **is_resolved**: Mark event as resolved/unresolved
    """
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event ID format")

    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_uuid).first()

    if not event:
        raise HTTPException(status_code=404, detail="Security event not found")

    # Update fields if provided
    if update_data.is_resolved is not None:
        event.is_resolved = update_data.is_resolved
        if update_data.is_resolved:
            event.resolved_at = datetime.utcnow()
        else:
            event.resolved_at = None

    if update_data.resolved_at is not None:
        event.resolved_at = update_data.resolved_at

    db.commit()
    db.refresh(event)

    return SecurityEventResponse(
        id=event.id,
        event_type=event.event_type,
        user_id=event.user_id,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        details=event.details,
        severity=event.severity,
        is_resolved=event.is_resolved,
        resolved_at=event.resolved_at,
        created_at=event.created_at,
    )


@router.delete("/{event_id}", dependencies=[Depends(get_current_admin_user)])
async def delete_security_event(
    event_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a security event (permanent deletion).

    Use with caution - this permanently removes the security event from the database.
    """
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event ID format")

    event = db.query(SecurityEvent).filter(SecurityEvent.id == event_uuid).first()

    if not event:
        raise HTTPException(status_code=404, detail="Security event not found")

    db.delete(event)
    db.commit()

    return {"success": True, "message": "Security event deleted successfully"}
