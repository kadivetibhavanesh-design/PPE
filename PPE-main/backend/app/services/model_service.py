import gc
import logging
import os
import threading
import time
from typing import Any, Dict, Optional
from huggingface_hub import hf_hub_download
from huggingface_hub.utils import HfHubHTTPError
from ultralytics import YOLO

try:
    from app.services.model_registry import (
        MODEL_CONSTRUCTELLIGENCE,
        MODEL_VYRA,
        get_active_model_id,
        set_active_model_id,
        get_model_profile,
        list_available_models,
        ModelProfile,
    )
except ImportError:
    from services.model_registry import (
        MODEL_CONSTRUCTELLIGENCE,
        MODEL_VYRA,
        get_active_model_id,
        set_active_model_id,
        get_model_profile,
        list_available_models,
        ModelProfile,
    )

logger = logging.getLogger("ppe_monitoring.model_service")

# Global singleton storage for currently active loaded model
_model_instance: Optional[YOLO] = None
_model_weights_path: Optional[str] = None
_loaded_model_id: Optional[str] = None
_model_init_time_seconds: float = 0.0
_model_lock = threading.Lock()


def get_model_init_time() -> float:
    """Returns the initialization duration in seconds for the active model."""
    global _model_init_time_seconds
    return round(_model_init_time_seconds, 3)


def download_model_weights(
    repo_id: Optional[str] = None,
    filename: Optional[str] = None,
    model_id: Optional[str] = None,
) -> str:
    """
    Downloads model weights from Hugging Face Hub using automatic local caching.
    Supports either explicit repo_id/filename or resolving via model_id.

    Args:
        repo_id: Hugging Face repository identifier (optional).
        filename: Weights filename inside the repository (optional).
        model_id: Optional registered model identifier (e.g., 'constructelligence', 'vyra').

    Returns:
        str: Absolute path to the cached weights file.

    Raises:
        RuntimeError: If download fails due to network or authentication issues.
    """
    if model_id is not None or (repo_id is None and filename is None):
        profile = get_model_profile(model_id)
        target_repo = profile.repo_id
        target_filename = profile.filename
    else:
        target_repo = str(repo_id)
        target_filename = str(filename)

    logger.info(f"Downloading/verifying weights from Hugging Face: {target_repo}/{target_filename}...")
    try:
        weights_path = hf_hub_download(
            repo_id=target_repo,
            filename=target_filename,
        )
        logger.info(f"Weights successfully cached at: {weights_path}")
        return weights_path
    except HfHubHTTPError as e:
        logger.error(f"Hugging Face Hub HTTP error downloading {target_repo}/{target_filename}: {e}")
        raise RuntimeError(
            f"Failed to download weights from Hugging Face ({target_repo}/{target_filename}). "
            f"HTTP status: {getattr(e.response, 'status_code', 'unknown')}. Error: {e}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error retrieving model weights: {e}")
        raise RuntimeError(
            f"Failed to download model weights from {target_repo}/{target_filename}: {str(e)}"
        ) from e


def load_model(
    model_id: Optional[str] = None,
    force_reload: bool = False,
    device: str = "cpu",
) -> YOLO:
    """
    Loads and caches the selected YOLO model singleton on the specified device (CPU).
    Ensures ONLY the active model is loaded in memory, releasing any previously loaded model.

    Args:
        model_id: Model to load ('constructelligence' or 'vyra'). If None, loads active model.
        force_reload: If True, forces reloading even if already loaded.
        device: Target execution device, defaults to 'cpu'.

    Returns:
        YOLO: Instantiated and ready-to-use YOLO model.

    Raises:
        RuntimeError: If the model fails to download or initialize.
    """
    global _model_instance, _model_weights_path, _loaded_model_id

    target_id = model_id or get_active_model_id()

    with _model_lock:
        if (
            _model_instance is not None
            and _loaded_model_id == target_id
            and not force_reload
        ):
            logger.debug(f"Returning cached YOLO model instance for '{target_id}'.")
            return _model_instance

        # Release previous model from RAM before loading the new one to save memory
        if _model_instance is not None:
            logger.info(f"Unloading previous model '{_loaded_model_id}' to free RAM...")
            _model_instance = None
            gc.collect()

        try:
            profile = get_model_profile(target_id)
            logger.info(f"Loading model '{profile.model_id}' ({profile.display_name})...")
            t_start = time.perf_counter()

            # Download or locate weights
            weights_path = download_model_weights(
                repo_id=profile.repo_id,
                filename=profile.filename,
            )

            # Instantiate YOLO model
            model = YOLO(weights_path)
            model.to(device)
            global _model_init_time_seconds
            _model_init_time_seconds = time.perf_counter() - t_start
            logger.info(f"Model '{profile.model_id}' successfully initialized on {device.upper()} in {_model_init_time_seconds:.3f}s.")

            _model_weights_path = weights_path
            _model_instance = model
            _loaded_model_id = target_id
            set_active_model_id(target_id)

            return _model_instance
        except Exception as e:
            logger.error(f"Failed to load YOLO model '{target_id}': {e}", exc_info=True)
            _model_instance = None
            _loaded_model_id = None
            raise RuntimeError(f"YOLO model '{target_id}' initialization failed: {str(e)}") from e


def get_model(model_id: Optional[str] = None) -> YOLO:
    """
    Returns the loaded YOLO model singleton, loading it if not already loaded.
    """
    target_id = model_id or get_active_model_id()
    if _model_instance is None or _loaded_model_id != target_id:
        return load_model(target_id)
    return _model_instance


def switch_model(model_id: str, force_reload: bool = False, device: str = "cpu") -> Dict[str, Any]:
    """
    Switches the active model and loads its weights into memory.

    Args:
        model_id: The identifier of the model to activate ('constructelligence' or 'vyra').
        force_reload: Whether to force reload weights from disk.
        device: Device to place model on ('cpu').

    Returns:
        dict: Inspection metadata of the newly active model.
    """
    profile = set_active_model_id(model_id)
    load_model(model_id=profile.model_id, force_reload=force_reload, device=device)
    return get_model_info()


def get_model_info(model: Optional[YOLO] = None) -> Dict[str, Any]:
    """
    Extracts inspection metadata from the loaded YOLO model and registry profile.

    Args:
        model: Optional YOLO model instance. If omitted, inspects active model.

    Returns:
        dict: Inspection metadata containing repo, filename, path, classes, active status, etc.
    """
    active_id = get_active_model_id()
    profile = get_model_profile(active_id)

    if model is None:
        try:
            model = get_model(active_id)
        except Exception as e:
            logger.warning(f"Could not load model instance for inspection: {e}")
            model = None

    names = model.names if (model is not None and hasattr(model, "names")) else profile.classes
    arch = getattr(model.model, "__class__", type(model)).__name__ if (model is not None and hasattr(model, "model")) else "YOLO"

    return {
        "model_id": profile.model_id,
        "display_name": profile.display_name,
        "repository": profile.repo_id,
        "filename": profile.filename,
        "weights_path": _model_weights_path or "Unknown",
        "architecture": arch,
        "num_classes": len(names),
        "classes": names,
        "device": "CPU",
        "description": profile.description,
        "positive_mask_support": profile.positive_mask_support,
        "positive_glove_support": profile.positive_glove_support,
        "supported_ppe": profile.supported_ppe,
    }
