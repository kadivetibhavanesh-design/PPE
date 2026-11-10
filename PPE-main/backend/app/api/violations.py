import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_violation_event_service
from app.api.schemas import ViolationEventsListResponse, ViolationSummaryResponse
from app.services.violation_event_service import ViolationEventService

logger = logging.getLogger("ppe_monitoring.api.violations")

router = APIRouter(prefix="/violations", tags=["Violations"])


@router.get(
    "",
    response_model=ViolationEventsListResponse,
    summary="Retrieve Violation Events",
    description="Returns recorded violation events in the current session with optional filtering by status, severity, worker, or category.",
)
async def get_violations(
    status: Optional[str] = Query(None, description="Filter by event status: 'open', 'ongoing', 'resolved', 'closed'"),
    severity: Optional[str] = Query(None, description="Filter by severity level: 'critical', 'high', 'medium', 'unclassified'"),
    worker_track_id: Optional[int] = Query(None, description="Filter by worker track ID"),
    ppe_category: Optional[str] = Query(None, description="Filter by PPE violation category (e.g., 'hardhat', 'safety_vest')"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of events to return"),
    event_service: ViolationEventService = Depends(get_violation_event_service),
):
    """Retrieves all or filtered PPE violation events."""
    try:
        events = event_service.get_all_events()

        # Apply optional query filters
        if status:
            events = [e for e in events if e.get("status") == status.lower()]
        if severity:
            events = [e for e in events if e.get("severity") == severity.lower()]
        if worker_track_id is not None:
            events = [e for e in events if e.get("worker_track_id") == worker_track_id]
        if ppe_category:
            target_cat = ppe_category.lower()
            events = [
                e for e in events
                if e.get("ppe_category") == target_cat
                or target_cat in [str(c).lower() for c in e.get("ppe_categories", [])]
                or target_cat in [c.strip().lower() for c in str(e.get("ppe_category", "")).split(",")]
            ]

        # Apply limit
        events = events[:limit]

        return {
            "total_count": len(events),
            "events": events,
        }
    except Exception as e:
        logger.error(f"Error querying violation events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query violation events: {str(e)}")


@router.get(
    "/active",
    response_model=ViolationEventsListResponse,
    summary="Retrieve Active Violation Events",
    description="Returns all currently open and ongoing violation events requiring safety attention.",
)
async def get_active_violations(
    event_service: ViolationEventService = Depends(get_violation_event_service),
):
    """Retrieves all active (open or ongoing) violation events."""
    try:
        active_events = event_service.get_active_events()
        return {
            "total_count": len(active_events),
            "events": active_events,
        }
    except Exception as e:
        logger.error(f"Error querying active violation events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query active violation events: {str(e)}")


@router.get(
    "/summary",
    response_model=ViolationSummaryResponse,
    summary="Violation Event Summary Metrics",
    description="Returns aggregate counts of violation events grouped by status, severity, and PPE category.",
)
async def get_violation_summary(
    event_service: ViolationEventService = Depends(get_violation_event_service),
):
    """Retrieves aggregated metrics across statuses, severities, and PPE categories."""
    try:
        summary = event_service.get_summary()
        return summary
    except Exception as e:
        logger.error(f"Error retrieving violation summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve violation summary: {str(e)}")


@router.post(
    "/{event_id}/resolve",
    summary="Resolve Violation Event",
    description="Manually marks an active violation event as resolved.",
)
async def resolve_violation_event(
    event_id: str,
    event_service: ViolationEventService = Depends(get_violation_event_service),
):
    """Manually marks an open or ongoing violation event as resolved."""
    try:
        success = event_service.resolve_event(event_id)
        if not success:
            event = event_service.get_event(event_id)
            if not event:
                raise HTTPException(status_code=404, detail=f"Violation event '{event_id}' not found")
            return {
                "success": True,
                "message": f"Event '{event_id}' is already in state '{event.get('status')}'",
                "event": event,
            }
        return {
            "success": True,
            "message": f"Event '{event_id}' successfully marked as resolved",
            "event": event_service.get_event(event_id),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving violation event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to resolve violation event: {str(e)}")

