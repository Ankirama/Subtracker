"""
Export API endpoints for generating subscription reports.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Optional
import io

from app.database import get_db
from app.models.user import User
from app.models.subscription import Subscription
from app.models.mailbox import Mailbox
from app.security import get_current_user
from app.services.export_service import ExportService

router = APIRouter()


@router.get("/csv")
async def export_subscriptions_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="Start date for filtering (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for filtering (YYYY-MM-DD)"),
    active_only: bool = Query(False, description="Export only active subscriptions"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """
    Export subscriptions to CSV format.

    Query parameters:
    - start_date: Optional start date for filtering by first_detected_at
    - end_date: Optional end date for filtering by first_detected_at
    - active_only: Only export active subscriptions
    - category: Filter by specific category
    """
    try:
        # Get user's mailbox IDs
        mailbox_ids = db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        mailbox_ids = [m[0] for m in mailbox_ids]

        if not mailbox_ids:
            # User has no mailboxes, return empty CSV
            csv_content = ExportService.generate_csv([], start_date, end_date)
            return StreamingResponse(
                io.StringIO(csv_content),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=subscriptions_{datetime.now().strftime('%Y%m%d')}.csv"}
            )

        # Build query
        query = db.query(Subscription).filter(Subscription.mailbox_id.in_(mailbox_ids))

        # Apply filters
        if start_date:
            query = query.filter(Subscription.first_detected_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Subscription.first_detected_at <= datetime.combine(end_date, datetime.max.time()))
        if active_only:
            query = query.filter(Subscription.is_active == True)
        if category:
            query = query.filter(Subscription.category == category)

        subscriptions = query.order_by(Subscription.provider).all()

        # Generate CSV
        csv_content = ExportService.generate_csv(subscriptions, start_date, end_date)

        # Return as downloadable file
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=subscriptions_{datetime.now().strftime('%Y%m%d')}.csv"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export subscriptions: {str(e)}"
        )


@router.get("/pdf", response_class=HTMLResponse)
async def export_subscriptions_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="Start date for filtering (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for filtering (YYYY-MM-DD)"),
    active_only: bool = Query(False, description="Export only active subscriptions"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """
    Export subscriptions to PDF format (returns HTML that can be printed/converted to PDF).

    Query parameters:
    - start_date: Optional start date for filtering by first_detected_at
    - end_date: Optional end date for filtering by first_detected_at
    - active_only: Only export active subscriptions
    - category: Filter by specific category

    Note: This returns HTML optimized for PDF printing. Use browser's Print to PDF feature
    or client-side PDF generation library.
    """
    try:
        # Get user's mailbox IDs
        mailbox_ids = db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        mailbox_ids = [m[0] for m in mailbox_ids]

        if not mailbox_ids:
            # User has no mailboxes, return empty report
            html_content = ExportService.generate_pdf_html([], start_date, end_date)
            return HTMLResponse(content=html_content)

        # Build query
        query = db.query(Subscription).filter(Subscription.mailbox_id.in_(mailbox_ids))

        # Apply filters
        if start_date:
            query = query.filter(Subscription.first_detected_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Subscription.first_detected_at <= datetime.combine(end_date, datetime.max.time()))
        if active_only:
            query = query.filter(Subscription.is_active == True)
        if category:
            query = query.filter(Subscription.category == category)

        subscriptions = query.order_by(Subscription.provider).all()

        # Generate HTML for PDF
        html_content = ExportService.generate_pdf_html(subscriptions, start_date, end_date)

        return HTMLResponse(content=html_content)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export subscriptions: {str(e)}"
        )


@router.get("/analytics")
async def export_analytics_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="Start date for analytics range"),
    end_date: Optional[date] = Query(None, description="End date for analytics range")
):
    """
    Export analytics data in JSON format for custom reporting.

    Returns detailed breakdown by category, billing cycle, and time period.
    """
    try:
        # Get user's mailbox IDs
        mailbox_ids = db.query(Mailbox.id).filter(Mailbox.user_id == current_user.id).all()
        mailbox_ids = [m[0] for m in mailbox_ids]

        if not mailbox_ids:
            return {
                "total_subscriptions": 0,
                "active_subscriptions": 0,
                "total_monthly_cost": 0.0,
                "total_yearly_cost": 0.0,
                "by_category": {},
                "by_billing_cycle": {},
                "date_range": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }

        # Build query
        query = db.query(Subscription).filter(Subscription.mailbox_id.in_(mailbox_ids))

        # Apply date filters
        if start_date:
            query = query.filter(Subscription.first_detected_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(Subscription.first_detected_at <= datetime.combine(end_date, datetime.max.time()))

        all_subscriptions = query.all()
        active_subscriptions = [s for s in all_subscriptions if s.is_active]

        # Calculate totals
        total_monthly = 0.0
        by_category = {}
        by_billing_cycle = {}

        for sub in active_subscriptions:
            monthly_cost = ExportService._normalize_billing_to_monthly(
                float(sub.amount) if sub.amount else 0.0,
                sub.billing_cycle
            )
            total_monthly += monthly_cost

            # By category
            cat = sub.category or 'other'
            if cat not in by_category:
                by_category[cat] = {'count': 0, 'monthly_cost': 0.0, 'yearly_cost': 0.0}
            by_category[cat]['count'] += 1
            by_category[cat]['monthly_cost'] += monthly_cost
            by_category[cat]['yearly_cost'] = by_category[cat]['monthly_cost'] * 12

            # By billing cycle
            cycle = sub.billing_cycle
            if cycle not in by_billing_cycle:
                by_billing_cycle[cycle] = {'count': 0, 'total_amount': 0.0}
            by_billing_cycle[cycle]['count'] += 1
            by_billing_cycle[cycle]['total_amount'] += float(sub.amount) if sub.amount else 0.0

        return {
            "total_subscriptions": len(all_subscriptions),
            "active_subscriptions": len(active_subscriptions),
            "total_monthly_cost": round(total_monthly, 2),
            "total_yearly_cost": round(total_monthly * 12, 2),
            "by_category": by_category,
            "by_billing_cycle": by_billing_cycle,
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export analytics: {str(e)}"
        )
