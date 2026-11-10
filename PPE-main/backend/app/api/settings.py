import logging
import platform
import sys
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

try:
    from app.services.settings_service import get_settings_service, SettingsService
    from app.services.monitoring_controller import get_monitoring_controller, MonitoringController
    from app.services.alarm_service import AlarmService
    from app.services.ppe_monitoring_service import get_monitoring_service
except ImportError:
    from backend.app.services.settings_service import get_settings_service, SettingsService
    from backend.app.services.monitoring_controller import get_monitoring_controller, MonitoringController
    from backend.app.services.alarm_service import AlarmService
    from backend.app.services.ppe_monitoring_service import get_monitoring_service

logger = logging.getLogger("ppe_monitoring.api.settings")

router = APIRouter(prefix="/settings", tags=["System Settings"])


# -----------------------------------------------------------------------------
# Pydantic Request Models
# -----------------------------------------------------------------------------

class ModelProfileActivateRequest(BaseModel):
    profile_id: str = Field(..., description="Target model profile identifier ('constructelligence' or 'vyra')")


class CameraSettingsUpdateRequest(BaseModel):
    device_index: int = Field(0, ge=0)
    resolution: str = Field("1280x720")
    width: int = Field(1280, ge=320, le=3840)
    height: int = Field(720, ge=240, le=2160)
    fps: int = Field(30, ge=5, le=60)
    backend: str = Field("DirectShow")


class PPESettingsUpdateRequest(BaseModel):
    global_confidence: float = Field(0.20, ge=0.05, le=0.95)
    min_ioa: float = Field(0.15, ge=0.01, le=0.90)
    violation_duration: float = Field(5.0, ge=1.0, le=60.0)
    violation_cooldown: float = Field(10.0, ge=1.0, le=120.0)
    enabled_categories: List[str] = Field(default_factory=list)
    category_confidence: Dict[str, float] = Field(default_factory=dict)


class AlertSettingsUpdateRequest(BaseModel):
    sound_enabled: bool = True
    visual_enabled: bool = True
    duration_ms: int = Field(400, ge=50, le=5000)
    frequency_hz: int = Field(1000, ge=200, le=4000)
    cooldown_seconds: float = Field(10.0, ge=1.0, le=120.0)
    triggers: Dict[str, bool] = Field(default_factory=dict)


class StorageSettingsUpdateRequest(BaseModel):
    retention_days: int = Field(30, ge=0, le=3650)
    image_capture_enabled: bool = True


class PreferencesSettingsUpdateRequest(BaseModel):
    theme: str = Field("light")
    default_page: str = Field("dashboard")
    refresh_interval_ms: int = Field(2000, ge=500, le=60000)
    notification_mode: str = Field("banner")
    datetime_format: str = Field("24h")
    ui_density: str = Field("normal")


class EmailSettingsUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    recipient_email: Optional[str] = None
    sender_email: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    use_tls: Optional[bool] = None
    use_ssl: Optional[bool] = None
    reminder_interval_minutes: Optional[int] = Field(None, ge=1, le=1440)


class TestEmailRequest(BaseModel):
    recipient_email: Optional[str] = None


class FullSettingsUpdateRequest(BaseModel):
    model: Optional[Dict[str, Any]] = None
    camera: Optional[CameraSettingsUpdateRequest] = None
    ppe: Optional[PPESettingsUpdateRequest] = None
    alerts: Optional[AlertSettingsUpdateRequest] = None
    storage: Optional[StorageSettingsUpdateRequest] = None
    preferences: Optional[PreferencesSettingsUpdateRequest] = None
    email: Optional[EmailSettingsUpdateRequest] = None


class TestAlarmRequest(BaseModel):
    duration_ms: Optional[int] = Field(None, ge=50, le=2000)
    frequency_hz: Optional[int] = Field(None, ge=200, le=4000)


class StorageCleanupRequest(BaseModel):
    retention_days: Optional[int] = Field(None, ge=0, le=3650)


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("", summary="Get Complete System Configuration")
async def get_all_settings(svc: SettingsService = Depends(get_settings_service)):
    """Returns all current persisted settings across all 8 modules."""
    return svc.get_settings()


@router.put("", summary="Update and Persist System Configuration")
async def update_all_settings(
    payload: Dict[str, Any],
    svc: SettingsService = Depends(get_settings_service),
):
    """Updates, validates, persists, and immediately applies settings to live engines."""
    try:
        updated = svc.save_settings(payload)
        return {"success": True, "message": "Settings updated successfully.", "settings": updated}
    except Exception as e:
        logger.error(f"Error saving settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update settings: {str(e)}",
        )


@router.post("/reset", summary="Reset System Configuration to Defaults")
async def reset_settings(svc: SettingsService = Depends(get_settings_service)):
    """Resets all configuration values to system defaults and applies them immediately."""
    try:
        defaults = svc.reset_to_defaults()
        return {"success": True, "message": "Configuration reset to factory defaults.", "settings": defaults}
    except Exception as e:
        logger.error(f"Error resetting settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset settings: {str(e)}",
        )


# Section 1: AI Model Configuration
@router.get("/models", summary="Get Sanitized AI Model Profiles")
async def get_model_profiles(svc: SettingsService = Depends(get_settings_service)):
    """
    Returns sanitized detection model profiles.
    Never exposes raw repository IDs, filenames, or internal weight paths.
    """
    return svc.get_sanitized_models()


@router.post("/models/activate", summary="Activate AI Detection Model Profile")
async def activate_model_profile(
    payload: ModelProfileActivateRequest,
    svc: SettingsService = Depends(get_settings_service),
):
    """
    Safely switches the active AI detection model.
    Guards strictly against switching while camera monitoring is running.
    """
    res = svc.activate_model_profile(payload.profile_id)
    if not res.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("message", "Failed to activate model profile."),
        )
    return res


# Section 2: Camera Configuration
@router.get("/camera", summary="Get Camera Configuration")
async def get_camera_settings(svc: SettingsService = Depends(get_settings_service)):
    """Returns camera resolution, device index, and backend configuration."""
    cfg = svc.get_settings()
    return cfg.get("camera", {})


@router.put("/camera", summary="Update Camera Configuration")
async def update_camera_settings(
    payload: CameraSettingsUpdateRequest,
    svc: SettingsService = Depends(get_settings_service),
):
    """Updates camera configuration."""
    updated = svc.save_settings({"camera": payload.model_dump()})
    return {"success": True, "camera": updated.get("camera", {})}


@router.get("/camera/test", summary="Test Camera Device Availability Safely")
async def test_camera(
    device_index: int = Query(0, ge=0),
    backend: str = Query("DirectShow"),
    svc: SettingsService = Depends(get_settings_service),
):
    """
    Safely tests camera device availability by briefly reading 1 test frame
    and immediately closing the device handle. NEVER starts monitoring.
    """
    return svc.test_camera_device(camera_index=device_index, backend=backend)


@router.get("/camera/devices", summary="Scan Connected Camera Devices")
async def scan_camera_devices(svc: SettingsService = Depends(get_settings_service)):
    """Scans and lists connected video capture devices."""
    return {"devices": svc.scan_camera_devices(max_devices=4)}


# Section 3: PPE Detection Configuration
@router.get("/ppe", summary="Get PPE Detection Configuration")
async def get_ppe_settings(svc: SettingsService = Depends(get_settings_service)):
    """Returns confidence thresholds, IoA, and violation timer durations."""
    cfg = svc.get_settings()
    return cfg.get("ppe", {})


@router.put("/ppe", summary="Update PPE Detection Configuration")
async def update_ppe_settings(
    payload: PPESettingsUpdateRequest,
    svc: SettingsService = Depends(get_settings_service),
):
    """Updates and applies PPE detection parameters to live compliance and tracking services."""
    updated = svc.save_settings({"ppe": payload.model_dump()})
    return {"success": True, "ppe": updated.get("ppe", {})}


# Section 4: Alert & Notification Settings
@router.get("/alerts", summary="Get Alert & Notification Settings")
async def get_alert_settings(svc: SettingsService = Depends(get_settings_service)):
    """Returns alarm sounds, visual warnings, cooldowns, and trigger toggles."""
    cfg = svc.get_settings()
    return cfg.get("alerts", {})


@router.put("/alerts", summary="Update Alert & Notification Settings")
async def update_alert_settings(
    payload: AlertSettingsUpdateRequest,
    svc: SettingsService = Depends(get_settings_service),
):
    """Updates and applies alert configurations."""
    updated = svc.save_settings({"alerts": payload.model_dump()})
    return {"success": True, "alerts": updated.get("alerts", {})}


@router.post("/alerts/test", summary="Play Test Alarm Tone")
async def test_alarm_tone(
    payload: Optional[TestAlarmRequest] = None,
    monitoring_svc=Depends(get_monitoring_service),
):
    """Plays a short synthesized audio tone to verify speaker output."""
    alarm_svc: AlarmService = monitoring_svc.alarm_service
    dur = payload.duration_ms if payload else None
    freq = payload.frequency_hz if payload else None
    success = alarm_svc.play_test_alarm(duration_ms=dur, frequency_hz=freq)
    return {"success": success, "message": "Test alarm tone triggered."}


@router.post("/alerts/stop-all", summary="Stop All Active Alarms")
async def stop_all_alarms(monitoring_svc=Depends(get_monitoring_service)):
    """Silences and stops all currently active alarms."""
    alarm_svc: AlarmService = monitoring_svc.alarm_service
    count = alarm_svc.stop_all_alarms()
    return {"success": True, "stopped_count": count, "message": f"Silenced {count} active alarms."}


# Section 5: System Health & Performance
@router.get("/system/metrics", summary="Get Real-Time Hardware & Inference Metrics")
async def get_system_metrics(svc: SettingsService = Depends(get_settings_service)):
    """
    Returns real-time CPU, RAM, GPU (if available, N/A otherwise),
    AI inference latency, FPS, and disk storage metrics.
    """
    return svc.get_system_metrics()


# Section 6: Storage and Evidence Management
@router.get("/storage", summary="Get Storage and Evidence Statistics")
async def get_storage_stats(svc: SettingsService = Depends(get_settings_service)):
    """Returns evidence directory size, total files, and retention policy."""
    cfg = svc.get_settings()
    stats = svc.get_system_metrics().get("storage", {})
    return {
        "settings": cfg.get("storage", {}),
        "statistics": stats,
    }


@router.put("/storage", summary="Update Storage Retention Policy")
async def update_storage_settings(
    payload: StorageSettingsUpdateRequest,
    svc: SettingsService = Depends(get_settings_service),
):
    """Updates storage retention policy and image capture toggle."""
    updated = svc.save_settings({"storage": payload.model_dump()})
    return {"success": True, "storage": updated.get("storage", {})}


@router.post("/storage/cleanup", summary="Purge Expired Incident Evidence")
async def cleanup_storage(
    payload: Optional[StorageCleanupRequest] = None,
    svc: SettingsService = Depends(get_settings_service),
):
    """Deletes evidence records and image files older than the retention threshold."""
    retention = payload.retention_days if (payload and payload.retention_days is not None) else None
    if retention is None:
        cfg = svc.get_settings()
        retention = int(cfg.get("storage", {}).get("retention_days", 30))

    from app.services.evidence_service import get_evidence_service
    evidence_svc = get_evidence_service()
    res = evidence_svc.cleanup_expired_evidence(retention_days=retention)
    return {"success": True, **res}


# Section 7: Application Preferences
@router.get("/preferences", summary="Get Application Preferences")
async def get_preferences(svc: SettingsService = Depends(get_settings_service)):
    """Returns UI theme, refresh intervals, density, and formatting preferences."""
    cfg = svc.get_settings()
    return cfg.get("preferences", {})


@router.put("/preferences", summary="Update Application Preferences")
async def update_preferences(
    payload: PreferencesSettingsUpdateRequest,
    svc: SettingsService = Depends(get_settings_service),
):
    """Updates application UI preferences."""
    updated = svc.save_settings({"preferences": payload.model_dump()})
    return {"success": True, "preferences": updated.get("preferences", {})}


# Section: Automatic Email Alert & Notification Settings
@router.get("/email", summary="Get Email Notification Settings")
async def get_email_settings(svc: SettingsService = Depends(get_settings_service)):
    """Returns email alert and ongoing reminder settings with masked credentials."""
    return svc.get_email_settings(mask_password=True)


@router.put("/email", summary="Update Email Notification Settings")
async def update_email_settings(
    payload: EmailSettingsUpdateRequest,
    svc: SettingsService = Depends(get_settings_service),
):
    """Updates email settings and applies configuration immediately."""
    try:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        res = svc.update_email_settings(updates)
        return {
            "success": True,
            "message": "Email notification settings updated.",
            "settings": res,
            "email": res,
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating email settings: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update email settings: {str(e)}")


@router.post("/email/test", summary="Send Test Verification Email")
async def send_test_email(
    payload: Optional[TestEmailRequest] = None,
    svc: SettingsService = Depends(get_settings_service),
):
    """Sends a verified test email to check SMTP delivery independently of camera monitoring."""
    target_recip = payload.recipient_email if payload else None
    success, message = svc.send_test_email(recipient=target_recip)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"success": True, "message": message}


# Section 8: System Information
@router.get("/system/info", summary="Get Complete System Architecture & Service Statuses")
async def get_system_info():
    """Returns static and runtime application and engine environment metadata."""
    import psutil
    import torch

    boot_time = psutil.boot_time()
    uptime_seconds = round(time.time() - boot_time, 1)

    return {
        "application_name": "SafeVision AI",
        "tagline": "AI-Powered Real-Time PPE Detection & Industrial Safety Monitoring System",
        "version": "1.0.0",
        "environment": "Local Industrial Edge",
        "api_base_url": "http://127.0.0.1:8000/api",
        "python_version": platform.python_version(),
        "pytorch_version": torch.__version__,
        "os_platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "cpu_cores": {
            "physical": psutil.cpu_count(logical=False),
            "logical": psutil.cpu_count(logical=True),
        },
        "system_uptime_seconds": uptime_seconds,
        "services": [
            {"name": "AI Model Engine", "status": "operational", "description": "YOLO Real-time Multi-Class Inference"},
            {"name": "Tracking Engine", "status": "operational", "description": "ByteTrack Kalman Filter Lifecycle Tracker"},
            {"name": "Compliance Engine", "status": "operational", "description": "Spatial IoA & Multi-Class Rule Evaluator"},
            {"name": "Violation Timer Engine", "status": "operational", "description": "Continuous Duration & Threshold Monitor"},
            {"name": "Alarm Engine", "status": "operational", "description": "Direct Audio Synthesizer & Cooldown Registry"},
            {"name": "Storage & Evidence Engine", "status": "operational", "description": "Annotated Frame & Metadata Store"},
            {"name": "WebSocket Engine", "status": "operational", "description": "Low-Latency Live Frame & Event Broadcast"},
        ],
    }
