import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_monitoring_controller
from app.services.monitoring_controller import MonitoringController
from app.services.model_registry import (
    get_active_model_id,
    get_model_profile,
    list_available_models,
)
from app.services.model_service import get_model_info

logger = logging.getLogger("ppe_monitoring.api.models")

router = APIRouter(prefix="/models", tags=["AI Models"])


class ModelSelectRequest(BaseModel):
    model_id: str = Field(..., description="Target YOLO model identifier ('constructelligence' or 'vyra')")


class ModelItemResponse(BaseModel):
    model_id: str
    display_name: str
    repo_id: str
    filename: str
    description: str
    is_active: bool
    is_default: bool
    num_classes: int
    classes: Dict[int, str]
    positive_mask_support: bool
    positive_glove_support: bool
    supported_ppe: List[str]


class ModelListResponse(BaseModel):
    total_models: int
    active_model_id: str
    models: List[ModelItemResponse]


class ModelSelectResponse(BaseModel):
    success: bool
    message: str
    active_model_id: str
    active_model: Dict[str, Any]


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List Registered AI Detection Models",
    description="Returns all registered YOLO PPE detection models, their architectures, supported PPE classes, and active status.",
)
async def get_models():
    """Lists all available models in the registry."""
    try:
        models = list_available_models()
        active_id = get_active_model_id()
        return {
            "total_models": len(models),
            "active_model_id": active_id,
            "models": models,
        }
    except Exception as e:
        logger.error(f"Failed to list models: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve models: {str(e)}",
        )


@router.get(
    "/active",
    summary="Get Currently Active AI Detection Model",
    description="Returns the active YOLO model configuration, loaded weights metadata, and class names.",
)
async def get_active_model():
    """Returns inspection metadata for the currently active detection model."""
    try:
        info = get_model_info()
        return info
    except Exception as e:
        logger.error(f"Failed to retrieve active model info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve active model: {str(e)}",
        )


@router.post(
    "/select",
    response_model=ModelSelectResponse,
    summary="Select and Activate AI Detection Model",
    description="Switches the active YOLO PPE detection model. Prohibited while camera monitoring is running.",
)
async def select_model(
    payload: ModelSelectRequest,
    controller: MonitoringController = Depends(get_monitoring_controller),
):
    """
    Selects and loads a detection model.
    Guarantees model cannot be switched while monitoring is active (returns 409 Conflict).
    """
    try:
        # Check if monitoring is currently running
        if controller.is_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot switch detection model while camera monitoring is active. Please stop camera monitoring first.",
            )

        # Switch model in controller and model_service
        info = controller.switch_model(payload.model_id)
        active_id = info.get("model_id", payload.model_id)

        return {
            "success": True,
            "message": f"Successfully activated model '{info.get('display_name', active_id)}'.",
            "active_model_id": active_id,
            "active_model": info,
        }
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except RuntimeError as re:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(re),
        )
    except Exception as e:
        logger.error(f"Failed to switch model to '{payload.model_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to switch model: {str(e)}",
        )

