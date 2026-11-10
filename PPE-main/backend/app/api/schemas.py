from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# System Schemas
# ============================================================================

class SystemHealthResponse(BaseModel):
    status: str = Field("healthy", description="Application health status")
    application: str = Field(..., description="Project name")
    python_version: str = Field(..., description="Python runtime version")
    pytorch_version: str = Field(..., description="PyTorch version")
    device: str = Field(..., description="Target execution device")


class SystemInfoResponse(BaseModel):
    status: str = Field("online", description="System operational state")
    application: str = Field(..., description="Project name")
    version: str = Field(..., description="Application version")
    python_version: str = Field(..., description="Python runtime version")
    pytorch_version: str = Field(..., description="PyTorch version")
    device: str = Field(..., description="Target execution device")
    os: str = Field(..., description="Host OS platform")
    model: Dict[str, Any] = Field(..., description="Loaded YOLO model inspection metadata")


# ============================================================================
# Monitoring Schemas
# ============================================================================

class WorkerSummaryItem(BaseModel):
    worker_id: Optional[int] = None
    worker_track_id: int
    worker_bounding_box: List[float] = Field(default_factory=list)
    confidence: Optional[float] = None
    first_seen: Optional[float] = None
    last_seen: Optional[float] = None
    total_frames_detected: Optional[int] = None
    lifecycle_status: str
    overall_status: str
    compliance_status: Optional[str] = None
    overall_reason: str
    compliant_category_count: int
    violation_count: int
    not_detected_count: int
    uncertain_count: int
    categories: Dict[str, Any] = Field(default_factory=dict)
    ppe_status: Dict[str, str] = Field(default_factory=dict)
    missing_ppe: List[str] = Field(default_factory=list)
    missing_ppe_labels: List[str] = Field(default_factory=list)
    associated_ppe: List[Dict[str, Any]] = Field(default_factory=list)


class MonitoringStartRequest(BaseModel):
    camera_index: int = Field(0, ge=0, description="Webcam device hardware index (default: 0)")


class MonitoringStartResponse(BaseModel):
    success: bool
    message: str
    status: str
    camera_index: int
    frames_processed: int = 0


class MonitoringStopResponse(BaseModel):
    success: bool
    message: str
    status: str
    frames_processed: int = 0


class MonitoringStatusResponse(BaseModel):
    status: str = Field(..., description="Pipeline execution state ('active', 'idle', 'error')")
    is_running: bool = Field(False, description="Whether background capture thread is running")
    camera_index: int = Field(0, description="Active camera index")
    frames_processed: int = Field(0, description="Total frames processed in current run")
    current_fps: float = Field(0.0, description="Current rolling processing FPS")
    uptime_seconds: float = Field(0.0, description="Elapsed uptime of active monitoring run")
    last_error: Optional[str] = Field(None, description="Most recent error message if any")
    last_exit_reason: Optional[str] = Field(None, description="Reason the monitoring worker last exited")
    timestamp: float = Field(..., description="Epoch timestamp of current status")
    active_workers_count: int = Field(..., description="Current count of active workers")
    compliant_workers_count: int = Field(..., description="Compliant workers count")
    non_compliant_workers_count: int = Field(..., description="Non-compliant workers count")
    needs_review_workers_count: int = Field(..., description="Workers requiring review")
    active_timers_count: int = Field(..., description="Active continuous violation timers")
    active_alarms_count: int = Field(..., description="Active violation alarms")
    total_events_count: int = Field(..., description="Total violation events in session")
    active_events_count: int = Field(..., description="Active violation events")
    active_model_id: Optional[str] = Field(None, description="Active YOLO model ID")
    active_model_name: Optional[str] = Field(None, description="Active YOLO model display name")
    worker_lifecycle: Dict[str, Any] = Field(default_factory=dict)


class MonitoringWorkersResponse(BaseModel):
    timestamp: float
    total_workers: int
    workers: List[WorkerSummaryItem]


class ComplianceSummaryResponse(BaseModel):
    timestamp: float
    total_workers: int
    compliant_workers: int
    non_compliant_workers: int
    needs_review_workers: int
    workers: List[Dict[str, Any]]


# ============================================================================
# Violation Schemas
# ============================================================================

class ViolationEventItem(BaseModel):
    event_id: str
    worker_track_id: int
    ppe_category: str
    ppe_categories: List[str] = Field(default_factory=list)
    severity: str
    status: str
    start_timestamp: float
    confirmation_timestamp: float
    last_updated_timestamp: float
    violation_duration: float
    alarm_status: str
    resolution_timestamp: Optional[float] = None
    closure_timestamp: Optional[float] = None


class ViolationEventsListResponse(BaseModel):
    total_count: int
    events: List[ViolationEventItem]


class ViolationSummaryResponse(BaseModel):
    timestamp: float
    total_events_count: int
    active_events_count: int
    by_status: Dict[str, int]
    by_severity: Dict[str, int]
    by_category: Dict[str, int]


# ============================================================================
# Alarm Schemas
# ============================================================================

class AlarmItemResponse(BaseModel):
    worker_track_id: int
    ppe_category: str
    status: str
    trigger_count: int
    first_triggered_timestamp: float
    last_triggered_timestamp: float
    cooldown_seconds: float


class AlarmsListResponse(BaseModel):
    timestamp: float
    active_alarms_count: int
    active_alarms: List[AlarmItemResponse]


class AlarmStopRequest(BaseModel):
    worker_track_id: int = Field(..., description="Unique track ID of the worker")
    ppe_category: str = Field(..., min_length=1, description="PPE violation category (e.g., 'hardhat', 'safety_vest')")


class AlarmStopResponse(BaseModel):
    success: bool
    message: str
    worker_track_id: Optional[int] = None
    ppe_category: Optional[str] = None
    stopped: bool = False


class AlarmStopAllResponse(BaseModel):
    success: bool
    message: str
    stopped_count: int


# ============================================================================
# Evidence Schemas
# ============================================================================

class EvidenceItem(BaseModel):
    event_id: str
    worker_track_id: int
    ppe_category: str
    severity: str
    first_detected_timestamp: float
    start_timestamp: Optional[float] = None
    evidence_image_filename: Optional[str] = None
    image_filename: Optional[str] = None
    event_status: str
    status: str
    resolution_timestamp: Optional[float] = None
    last_updated_timestamp: float


class EvidenceListResponse(BaseModel):
    total_count: int
    evidence: List[EvidenceItem]
