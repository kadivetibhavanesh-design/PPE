
import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_monitoring_controller, get_monitoring_service
from app.api.schemas import (
    ComplianceSummaryResponse,
    MonitoringStartRequest,
    MonitoringStartResponse,
    MonitoringStatusResponse,
    MonitoringStopResponse,
    MonitoringWorkersResponse,
)
from app.services.monitoring_controller import MonitoringController
from app.services.ppe_monitoring_service import PPEMonitoringService


logger = logging.getLogger("ppe_monitoring.api.monitoring")

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.post(
    "/start",
    response_model=MonitoringStartResponse,
    summary="Start Live Webcam Monitoring",
    description="Initiates real-time video capture and YOLO PPE compliance detection in a background worker thread.",
)
async def start_monitoring(
    request: Optional[MonitoringStartRequest] = None,
    controller: MonitoringController = Depends(get_monitoring_controller),
):
    """Starts the real-time webcam inference and monitoring background process."""

    try:
        camera_idx = request.camera_index if request else 0

        result = controller.start_monitoring(camera_index=camera_idx)

        if not result["success"] and result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"],
            )

        return result

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Unexpected error starting monitoring: {e}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start monitoring: {str(e)}",
        )


@router.post(
    "/stop",
    response_model=MonitoringStopResponse,
    summary="Stop Live Webcam Monitoring",
    description="Halts the real-time video capture loop and releases the webcam hardware handle.",
)
async def stop_monitoring(
    controller: MonitoringController = Depends(get_monitoring_controller),
):
    """Stops the real-time monitoring thread and releases the webcam."""

    try:
        result = controller.stop_monitoring()
        return result

    except Exception as e:
        logger.error(
            f"Unexpected error stopping monitoring: {e}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop monitoring: {str(e)}",
        )


@router.get(
    "/video_feed",
    summary="Live Annotated Camera MJPEG Feed",
    description="Streams real-time annotated webcam video frames.",
)
async def video_feed(
    request: Request,
    controller: MonitoringController = Depends(get_monitoring_controller),
):
    """
    Automatically starts monitoring if inactive,
    then streams the latest annotated webcam frames.
    """

    # Automatically start monitoring if it is not running.
    if not controller.is_running:

        logger.info(
            "Monitoring is inactive. Attempting to start webcam monitoring."
        )

        try:
            result = controller.start_monitoring(camera_index=0)

            if not result.get("success", False):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=result.get(
                        "message",
                        "Unable to start webcam monitoring.",
                    ),
                )

            # Wait up to 5 seconds for the monitoring thread to start.
            for _ in range(50):

                if controller.is_running:
                    break

                await asyncio.sleep(0.1)

            if not controller.is_running:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Monitoring did not start. "
                        "Check the camera and backend logs."
                    ),
                )

        except HTTPException:
            raise

        except Exception as e:
            logger.error(
                f"Failed to start monitoring: {e}",
                exc_info=True,
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize monitoring: {str(e)}",
            )

    async def frame_generator():

        last_frame_id = -1

        try:

            while controller.is_running:

                if await request.is_disconnected():
                    break

                frame_id, jpeg_bytes = controller.get_latest_frame_info()

                if (
                    jpeg_bytes is not None
                    and frame_id != last_frame_id
                ):

                    last_frame_id = frame_id

                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + jpeg_bytes
                        + b"\r\n"
                    )

                # Poll for new frames.
                await asyncio.sleep(0.015)

        except (asyncio.CancelledError, GeneratorExit):
            logger.info("Video feed client disconnected.")

        except Exception as e:
            logger.error(
                f"Video feed streaming error: {e}",
                exc_info=True,
            )

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get(
    "/status",
    response_model=MonitoringStatusResponse,
    summary="Current Monitoring Status",
    description="Returns high-level statistics and worker loop health metrics for the current session.",
)
async def get_monitoring_status(
    monitoring_service: PPEMonitoringService = Depends(
        get_monitoring_service
    ),
    controller: MonitoringController = Depends(
        get_monitoring_controller
    ),
):
    """Retrieves monitoring statistics and operational state."""

    try:

        latest = monitoring_service.get_latest_monitoring_data()

        ctrl_status = controller.get_status()
        worker_lifecycle = latest.get("worker_lifecycle", {})
        is_running = bool(ctrl_status.get("is_running", False))

        return {
            "status": ctrl_status.get("status", "idle"),
            "is_running": is_running,
            "camera_index": ctrl_status.get("camera_index", 0),
            "frames_processed": ctrl_status.get("frames_processed", 0),
            "current_fps": ctrl_status.get("current_fps", 0.0),
            "uptime_seconds": ctrl_status.get("uptime_seconds", 0.0),
            "last_error": ctrl_status.get("last_error"),
            "last_exit_reason": ctrl_status.get("last_exit_reason"),
            "timestamp": latest.get("timestamp", time.time()),
            "active_workers_count": int(
                worker_lifecycle.get("active_count", 0)
                if is_running
                else 0
            ),
            "compliant_workers_count": int(
                latest.get("total_compliant", 0)
            ),
            "non_compliant_workers_count": int(
                latest.get("total_non_compliant", 0)
            ),
            "needs_review_workers_count": int(
                latest.get("total_needs_review", 0)
            ),
            "active_timers_count": int(
                latest.get("active_timer_count", 0)
            ),
            "active_alarms_count": int(
                latest.get("active_alarms_count", 0)
            ),
            "total_events_count": int(
                latest.get(
                    "violation_event_summary", {}
                ).get("total_events_count", 0)
            ),
            "active_events_count": int(
                latest.get(
                    "violation_event_summary", {}
                ).get("active_events_count", 0)
            ),
            "worker_lifecycle": worker_lifecycle,
            "active_model_id": ctrl_status.get(
                "active_model_id",
                latest.get("active_model_id"),
            ),
            "active_model_name": ctrl_status.get(
                "active_model_name",
                latest.get("active_model_name"),
            ),
        }

    except Exception as e:

        logger.error(
            f"Error retrieving monitoring status: {e}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve monitoring status: {str(e)}",
        )


@router.get(
    "/workers",
    response_model=MonitoringWorkersResponse,
    summary="Active Worker Summaries",
    description="Returns detailed records of all active workers detected and tracked in the latest frame.",
)
async def get_active_workers(
    monitoring_service: PPEMonitoringService = Depends(
        get_monitoring_service
    ),
):
    """Retrieves all active workers."""

    try:

        latest = monitoring_service.get_latest_monitoring_data()

        workers = latest.get("workers", [])

        return {
            "timestamp": latest.get("timestamp", time.time()),
            "total_workers": len(workers),
            "workers": workers,
        }

    except Exception as e:

        logger.error(
            f"Error retrieving worker summaries: {e}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve worker summaries: {str(e)}",
        )


@router.get(
    "/compliance",
    response_model=ComplianceSummaryResponse,
    summary="Worker PPE Compliance Summaries",
    description="Returns individual per-worker PPE compliance evaluations and category breakdowns.",
)
async def get_compliance_summary(
    monitoring_service: PPEMonitoringService = Depends(
        get_monitoring_service
    ),
):
    """Retrieves worker PPE compliance summaries."""

    try:

        latest = monitoring_service.get_latest_monitoring_data()

        workers = latest.get("workers", [])

        return {
            "timestamp": latest.get("timestamp", time.time()),
            "total_workers": int(
                latest.get("total_workers", len(workers))
            ),
            "compliant_workers": int(
                latest.get("total_compliant", 0)
            ),
            "non_compliant_workers": int(
                latest.get("total_non_compliant", 0)
            ),
            "needs_review_workers": int(
                latest.get("total_needs_review", 0)
            ),
            "workers": workers,
        }

    except Exception as e:

        logger.error(
            f"Error retrieving compliance summary: {e}",
            exc_info=True,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve compliance summary: {str(e)}",
        )
