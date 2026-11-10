from fastapi import Depends

try:
    from app.services.ppe_monitoring_service import (
        PPEMonitoringService,
        get_monitoring_service as _get_monitoring_service_singleton,
    )
    from app.services.alarm_service import AlarmService
    from app.services.violation_event_service import ViolationEventService
    from app.services.worker_tracking_service import WorkerTrackingService
    from app.services.model_service import get_model, get_model_info
    from app.services.websocket_manager import ConnectionManager, get_websocket_manager
    from app.services.monitoring_controller import MonitoringController, get_monitoring_controller
    from app.services.evidence_service import EvidenceService, get_evidence_service as _get_evidence_service_singleton
    from app.services.report_service import ReportService, get_report_service as _get_report_service_singleton
except ImportError:
    from services.ppe_monitoring_service import (
        PPEMonitoringService,
        get_monitoring_service as _get_monitoring_service_singleton,
    )
    from services.alarm_service import AlarmService
    from services.violation_event_service import ViolationEventService
    from services.worker_tracking_service import WorkerTrackingService
    from services.model_service import get_model, get_model_info
    from services.websocket_manager import ConnectionManager, get_websocket_manager
    from services.monitoring_controller import MonitoringController, get_monitoring_controller
    from services.evidence_service import EvidenceService, get_evidence_service as _get_evidence_service_singleton
    from services.report_service import ReportService, get_report_service as _get_report_service_singleton


def get_monitoring_service() -> PPEMonitoringService:
    """Dependency provider for the shared PPEMonitoringService singleton."""
    return _get_monitoring_service_singleton()


def get_alarm_service(
    monitoring_service: PPEMonitoringService = Depends(get_monitoring_service),
) -> AlarmService:
    """Dependency provider for AlarmService from monitoring service."""
    return monitoring_service.alarm_service


def get_violation_event_service(
    monitoring_service: PPEMonitoringService = Depends(get_monitoring_service),
) -> ViolationEventService:
    """Dependency provider for ViolationEventService from monitoring service."""
    return monitoring_service.violation_event_service


def get_evidence_service() -> EvidenceService:
    """Dependency provider for EvidenceService singleton."""
    return _get_evidence_service_singleton()


def get_report_service() -> ReportService:
    """Dependency provider for ReportService singleton."""
    return _get_report_service_singleton()

