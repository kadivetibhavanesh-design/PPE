import logging
import platform
import torch
from fastapi import APIRouter, HTTPException

from config import settings
from app.api.schemas import SystemHealthResponse, SystemInfoResponse
from app.services.model_service import get_model_info

logger = logging.getLogger("ppe_monitoring.api.system")

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=SystemHealthResponse,
    summary="System Health Probe",
    description="Returns the operational health status of the application, runtime, and PyTorch device configuration.",
)
async def health_check():
    """Health check endpoint returning application status, Python/PyTorch versions, and device."""
    try:
        pytorch_version = torch.__version__
        device = settings.DEVICE
        if torch.cuda.is_available():
            device = "GPU (Warning: CPU configured)"

        return {
            "status": "healthy",
            "application": settings.PROJECT_NAME,
            "python_version": platform.python_version(),
            "pytorch_version": pytorch_version,
            "device": device,
        }
    except Exception as e:
        logger.error(f"Health check probe failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Health check probe failed")


@router.get(
    "/system/info",
    response_model=SystemInfoResponse,
    summary="System & Model Information",
    description="Returns detailed runtime environment metrics, operating system info, and YOLOv8 model metadata.",
)
async def system_info():
    """Returns detailed system, platform, and YOLO model metadata."""
    try:
        pytorch_version = torch.__version__
        device = settings.DEVICE
        if torch.cuda.is_available():
            device = "GPU (Warning: CPU configured)"

        try:
            model_info = get_model_info()
        except Exception as e:
            logger.warning(f"Model metadata extraction issue: {e}")
            model_info = {
                "error": f"Model unavailable: {str(e)}",
                "classes": {},
                "num_classes": 0,
            }

        return {
            "status": "online",
            "application": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "python_version": platform.python_version(),
            "pytorch_version": pytorch_version,
            "device": device,
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "model": model_info,
        }
    except Exception as e:
        logger.error(f"Failed to gather system information: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve system info: {str(e)}")

