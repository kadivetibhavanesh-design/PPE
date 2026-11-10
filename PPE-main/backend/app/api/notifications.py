
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

try:
    from app.services.email_service import get_email_service, EmailService
    from app.services.notification_service import get_notification_service, NotificationService
except ImportError:
    from backend.app.services.email_service import get_email_service, EmailService
    from backend.app.services.notification_service import get_notification_service, NotificationService

logger = logging.getLogger("ppe_monitoring.api.notifications")

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# =============================================================================
# REAL-TIME NOTIFICATION CENTER ENDPOINTS
# =============================================================================

@router.get(
    "",
    summary="Get Paginated Notifications",
    description="Returns persisted system notifications with unread counts and optional filtering.",
)
async def get_notifications(
    limit: int = Query(50, ge=1, le=200, description="Number of notifications to retrieve"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    category: Optional[str] = Query(None, description="Filter by category ('ppe', 'alarm', 'email', 'monitoring')"),
    severity: Optional[str] = Query(None, description="Filter by severity ('critical', 'high', 'medium', 'low', 'info')"),
):
    """Returns paginated notification list and aggregate unread count."""
    svc = get_notification_service()
    return svc.get_notifications(
        limit=limit,
        offset=offset,
        unread_only=unread_only,
        category=category,
        severity=severity,
    )


@router.get(
    "/unread_count",
    summary="Get Unread Notification Count",
    description="Returns the total number of unread notifications for badge rendering.",
)
async def get_unread_notification_count():
    """Returns total unread notifications count."""
    svc = get_notification_service()
    return {"unread_count": svc.get_unread_count()}


@router.patch(
    "/{notification_id}/read",
    summary="Mark Notification as Read",
    description="Updates the read status of an individual notification.",
)
async def mark_notification_as_read(notification_id: str):
    """Marks a single notification as read."""
    svc = get_notification_service()
    success = svc.mark_as_read(notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    return {"success": True, "notification_id": notification_id, "read": True}


@router.post(
    "/mark_all_read",
    summary="Mark All Notifications as Read",
    description="Sets read status to True for all notifications in the notification center.",
)
async def mark_all_notifications_as_read():
    """Marks all notifications as read."""
    svc = get_notification_service()
    count = svc.mark_all_as_read()
    return {"success": True, "marked_count": count}


@router.delete(
    "",
    summary="Clear All Notifications",
    description="Clears all stored notifications history.",
)
async def clear_all_notifications():
    """Clears all notifications."""
    svc = get_notification_service()
    count = svc.clear_all()
    return {"success": True, "cleared_count": count}


@router.delete(
    "/{notification_id}",
    summary="Delete Notification",
    description="Permanently deletes an individual notification by ID.",
)
async def delete_notification(notification_id: str):
    """Deletes an individual notification."""
    svc = get_notification_service()
    success = svc.delete_notification(notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )
    return {"success": True, "notification_id": notification_id}


# =============================================================================
# EMAIL NOTIFICATION ENDPOINTS
# =============================================================================

@router.get(
    "/email/status",
    summary="Get Automatic Email Alert & Notification Status",
    description="Returns current email notification engine status, delivery statistics, and active ongoing reminder schedules.",
)
async def get_email_notification_status():
    """Returns real-time status of the email notification service."""
    svc = get_email_service()
    return svc.get_status()


@router.get(
    "/email/history",
    summary="Get Email Notification Delivery History",
    description="Returns chronologically ordered history of all sent first alerts, 5-minute reminders, test messages, and failure logs.",
)
async def get_email_notification_history(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of historical records to retrieve"),
):
    """Returns persisted delivery history records."""
    svc = get_email_service()
    records = svc.get_history(limit=limit)
    return {
        "total_records": len(records),
        "history": records,
    }


@router.get(
    "/email/incident/{incident_id}",
    summary="Get Email History & Reminder Schedule for Specific Incident",
    description="Returns delivery records and current reminder schedule status for an individual violation event ID.",
)
async def get_incident_email_notifications(incident_id: str):
    """Returns history and schedule state for an individual incident."""
    svc = get_email_service()
    records = svc.get_incident_history(incident_id)
    status_data = svc.get_status()
    active_schedule = next(
        (s for s in status_data.get("active_incident_schedules", []) if s.get("incident_id") == incident_id),
        None,
    )
    return {
        "incident_id": incident_id,
        "total_notifications": len(records),
        "active_schedule": active_schedule,
        "history": records,
    }
