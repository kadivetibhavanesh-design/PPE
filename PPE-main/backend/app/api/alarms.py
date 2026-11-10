import logging
import time
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_alarm_service
from app.api.schemas import (
    AlarmStopAllResponse,
    AlarmStopRequest,
    AlarmStopResponse,
    AlarmsListResponse,
)
from app.services.alarm_service import AlarmService

logger = logging.getLogger("ppe_monitoring.api.alarms")

router = APIRouter(prefix="/alarms", tags=["Alarms"])


@router.get(
    "",
    response_model=AlarmsListResponse,
    summary="Retrieve Active Alarms",
    description="Returns all currently active, cooling down, or triggered violation alarms in the session.",
)
async def get_active_alarms(
    alarm_service: AlarmService = Depends(get_alarm_service),
):
    """Retrieves all active alarm records."""
    try:
        active = alarm_service.get_active_alarms()
        return {
            "timestamp": time.time(),
            "active_alarms_count": len(active),
            "active_alarms": active,
        }
    except Exception as e:
        logger.error(f"Error querying active alarms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query active alarms: {str(e)}")


@router.post(
    "/stop",
    response_model=AlarmStopResponse,
    summary="Stop Specific Alarm",
    description="Stops/mutes sound alerts for a specific (worker_track_id, ppe_category) continuous violation episode.",
)
async def stop_alarm(
    request: AlarmStopRequest,
    alarm_service: AlarmService = Depends(get_alarm_service),
):
    """Stops audio alerts for a specified worker and PPE category."""
    try:
        stopped = alarm_service.stop_alarm(
            worker_track_id=request.worker_track_id,
            ppe_category=request.ppe_category,
        )

        if stopped:
            return {
                "success": True,
                "message": f"Alarm successfully stopped for Worker #{request.worker_track_id} ({request.ppe_category}).",
                "worker_track_id": request.worker_track_id,
                "ppe_category": request.ppe_category,
                "stopped": True,
            }
        else:
            return {
                "success": False,
                "message": f"No active alarm found to stop for Worker #{request.worker_track_id} ({request.ppe_category}).",
                "worker_track_id": request.worker_track_id,
                "ppe_category": request.ppe_category,
                "stopped": False,
            }
    except Exception as e:
        logger.error(f"Error stopping alarm: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop alarm: {str(e)}")


@router.post(
    "/stop-all",
    response_model=AlarmStopAllResponse,
    summary="Stop All Active Alarms",
    description="Stops and silences all currently active violation alarms across all workers.",
)
async def stop_all_alarms(
    alarm_service: AlarmService = Depends(get_alarm_service),
):
    """Silences all active alarms."""
    try:
        stopped_count = alarm_service.stop_all_alarms()
        return {
            "success": True,
            "message": f"Successfully stopped {stopped_count} active alarm(s).",
            "stopped_count": stopped_count,
        }
    except Exception as e:
        logger.error(f"Error stopping all alarms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop all alarms: {str(e)}")

