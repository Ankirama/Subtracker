"""
Admin API endpoints for system logs viewing.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
import os
import re
from pathlib import Path

from app.database import get_db
from app.schemas.admin import LogEntryResponse, LogListResponse
from app.security.dependencies import get_current_admin_user

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])


def parse_log_line(line: str) -> Optional[dict]:
    """
    Parse a log line into structured data.

    Expected format:
    2025-01-18 10:30:45,123 - app.module - LEVEL - Message
    """
    # Pattern for standard Python logging format
    pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+-\s+([\w.]+)\s+-\s+(\w+)\s+-\s+(.+)$'

    match = re.match(pattern, line)
    if match:
        timestamp_str, module, level, message = match.groups()
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            return {
                "timestamp": timestamp.isoformat(),
                "module": module,
                "level": level,
                "message": message.strip()
            }
        except ValueError:
            pass

    # Fallback: treat entire line as message
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "module": "unknown",
        "level": "INFO",
        "message": line.strip()
    }


def read_logs(
    log_file: str = "app.log",
    max_lines: int = 1000,
    level_filter: Optional[str] = None,
    search: Optional[str] = None
) -> List[dict]:
    """
    Read and parse log files.
    """
    logs = []
    log_path = Path("/app/logs") / log_file if os.path.exists("/app/logs") else Path("logs") / log_file

    if not log_path.exists():
        return []

    try:
        with open(log_path, 'r') as f:
            # Read last N lines
            lines = f.readlines()[-max_lines:]

            for line in reversed(lines):  # Most recent first
                if line.strip():
                    parsed = parse_log_line(line)
                    if parsed:
                        # Apply filters
                        if level_filter and parsed["level"] != level_filter.upper():
                            continue
                        if search and search.lower() not in parsed["message"].lower():
                            continue

                        logs.append(parsed)
    except Exception as e:
        # If we can't read the file, return error log
        logs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "module": "admin.logs",
            "level": "ERROR",
            "message": f"Failed to read log file: {str(e)}"
        })

    return logs


@router.get("", response_model=LogListResponse, dependencies=[Depends(get_current_admin_user)])
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    level: Optional[str] = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"),
    search: Optional[str] = Query(None, description="Search in log messages"),
    source: str = Query("app", description="Log source (app, celery, nginx)"),
    db: Session = Depends(get_db)
):
    """
    Retrieve system logs with filtering and pagination.

    - **page**: Page number (starts at 1)
    - **page_size**: Items per page (1-500)
    - **level**: Filter by log level
    - **search**: Search term in log messages
    - **source**: Log source (app, celery, nginx)
    """
    # Map source to log file
    log_files = {
        "app": "app.log",
        "celery": "celery.log",
        "nginx": "nginx/access.log"
    }

    log_file = log_files.get(source, "app.log")

    # Read logs with filters
    all_logs = read_logs(
        log_file=log_file,
        max_lines=page_size * 10,  # Read more than needed for filtering
        level_filter=level,
        search=search
    )

    # Apply pagination
    total = len(all_logs)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_logs = all_logs[start_idx:end_idx]

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return {
        "logs": [
            {
                "id": f"{log['timestamp']}_{idx}",  # Synthetic ID for frontend
                "timestamp": log["timestamp"],
                "level": log["level"],
                "module": log["module"],
                "message": log["message"],
                "source": source
            }
            for idx, log in enumerate(paginated_logs)
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/sources", dependencies=[Depends(get_current_admin_user)])
async def get_log_sources():
    """
    Get available log sources.
    """
    return {
        "sources": [
            {"name": "app", "label": "Application", "available": True},
            {"name": "celery", "label": "Background Tasks", "available": True},
            {"name": "nginx", "label": "Web Server", "available": False}
        ]
    }


@router.get("/stats", dependencies=[Depends(get_current_admin_user)])
async def get_log_stats():
    """
    Get log statistics (errors, warnings in last 24 hours).
    """
    logs = read_logs(max_lines=10000)

    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    errors_24h = 0
    warnings_24h = 0

    for log in logs:
        try:
            log_time = datetime.fromisoformat(log["timestamp"].replace('Z', '+00:00'))
            if log_time >= last_24h:
                if log["level"] == "ERROR" or log["level"] == "CRITICAL":
                    errors_24h += 1
                elif log["level"] == "WARNING":
                    warnings_24h += 1
        except:
            continue

    return {
        "errors_24h": errors_24h,
        "warnings_24h": warnings_24h,
        "total_logs": len(logs)
    }
