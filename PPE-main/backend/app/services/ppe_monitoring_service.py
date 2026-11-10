
import collections
import json
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("ppe_monitoring.pipeline_service")

try:
    from app.services.detection_service import process_detections
    from app.services.model_service import get_model
    from app.services.model_registry import get_active_model_id, get_model_profile
    from app.services.ppe_association_service import PPEAssociationService
    from app.services.ppe_compliance_service import PPEComplianceService
    from app.services.worker_tracking_service import WorkerTrackingService
    from app.services.violation_timer_service import ViolationTimerService
    from app.services.alarm_service import AlarmService
    from app.services.violation_event_service import ViolationEventService
    from app.services.websocket_manager import ConnectionManager, get_websocket_manager

except ImportError:
    from services.detection_service import process_detections
    from services.model_service import get_model
    from services.model_registry import get_active_model_id, get_model_profile
    from services.ppe_association_service import PPEAssociationService
    from services.ppe_compliance_service import PPEComplianceService
    from services.worker_tracking_service import WorkerTrackingService
    from services.violation_timer_service import ViolationTimerService
    from services.alarm_service import AlarmService
    from services.violation_event_service import ViolationEventService
    from services.websocket_manager import ConnectionManager, get_websocket_manager


class PPEMonitoringService:
    """
    Real-time PPE monitoring pipeline.

    Uses persistent Ultralytics ByteTrack IDs to associate worker detections
    across frames while preserving the original detection results for PPE checks.
    """

    def __init__(
        self,
        model=None,
        worker_tracking_service: Optional[WorkerTrackingService] = None,
        association_service: Optional[PPEAssociationService] = None,
        compliance_service: Optional[PPEComplianceService] = None,
        violation_timer_service: Optional[ViolationTimerService] = None,
        alarm_service: Optional[AlarmService] = None,
        violation_event_service: Optional[ViolationEventService] = None,
        websocket_manager: Optional[ConnectionManager] = None,
        conf_threshold: float = 0.20,
        imgsz: int = 640,
        device: str = "cpu",
    ) -> None:

        self._model = model
        self.conf_threshold = float(conf_threshold)
        self.imgsz = int(imgsz)
        self.device = str(device)

        # Initialize services
        self.worker_tracking_service = (
            worker_tracking_service
            or WorkerTrackingService(timeout_seconds=5.0)
        )

        self.association_service = (
            association_service or PPEAssociationService()
        )

        self.compliance_service = (
            compliance_service
            or PPEComplianceService(min_confidence=self.conf_threshold)
        )

        self.violation_timer_service = (
            violation_timer_service
            or ViolationTimerService(default_threshold_seconds=5.0)
        )

        self.alarm_service = alarm_service or AlarmService()

        self.violation_event_service = (
            violation_event_service or ViolationEventService()
        )

        self.websocket_manager = (
            websocket_manager or get_websocket_manager()
        )

        # Latest monitoring result
        self._last_result: Optional[Dict[str, Any]] = None

        # Performance metrics
        self._inference_latencies = collections.deque(maxlen=30)
        self._frame_times = collections.deque(maxlen=30)

        self._latest_inference_latency_ms = 0.0
        self._avg_inference_latency_ms = 0.0
        self._max_inference_latency_ms = 0.0
        self._avg_frame_time_ms = 0.0

        self._total_detections_count = 0
        self._last_frame_timestamp: Optional[float] = None

    @property
    def model(self):
        """Lazy-load YOLO model."""
        if self._model is None:
            self._model = get_model()
        return self._model

    def refresh_model(self) -> None:
        """Refresh active YOLO model."""
        self._model = get_model()

        if hasattr(self.compliance_service, "refresh_config"):
            self.compliance_service.refresh_config()

        logger.info(
            f"PPEMonitoringService refreshed with model: {self._model}"
        )

    def process_frame(
        self,
        frame: Optional[np.ndarray],
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:

        ts = float(
            timestamp if timestamp is not None else time.time()
        )

        # Step 1: Validate frame
        if (
            frame is None
            or not isinstance(frame, np.ndarray)
            or frame.size == 0
        ):
            return self._empty_response(
                timestamp=ts,
                error="Invalid, empty, or unreadable video frame received.",
            )

        frame_h, frame_w = frame.shape[:2]

        # Step 2: Run persistent tracking on each frame. Ultralytics maps tracker
        # output back to Results.boxes, which process_detections reads below.
        t_infer_start = time.perf_counter()

        try:
            results = self.model.track(
                source=frame,
                persist=True,
                tracker="bytetrack.yaml",
                device=self.device,
                conf=self.conf_threshold,
                imgsz=self.imgsz,
                verbose=False,
            )

            infer_ms = (
                time.perf_counter() - t_infer_start
            ) * 1000.0

            self._latest_inference_latency_ms = round(infer_ms, 2)
            self._inference_latencies.append(infer_ms)

            if self._inference_latencies:
                self._avg_inference_latency_ms = round(
                    sum(self._inference_latencies)
                    / len(self._inference_latencies),
                    2,
                )

                self._max_inference_latency_ms = round(
                    max(self._inference_latencies),
                    2,
                )

            now_perf = time.perf_counter()

            if self._last_frame_timestamp is not None:
                dt_ms = (
                    now_perf - self._last_frame_timestamp
                ) * 1000.0

                self._frame_times.append(dt_ms)

                if self._frame_times:
                    self._avg_frame_time_ms = round(
                        sum(self._frame_times)
                        / len(self._frame_times),
                        2,
                    )

            self._last_frame_timestamp = now_perf

        except Exception as e:
            logger.error(
                f"YOLO detection error: {e}",
                exc_info=True,
            )

            return self._empty_response(
                timestamp=ts,
                frame_width=frame_w,
                frame_height=frame_h,
                error=f"YOLO detection execution error: {str(e)}",
            )

        # Step 3: Process detection results
        model_names = getattr(self.model, "names", {})

        structured = process_detections(
            results,
            model_names,
        )

        self._total_detections_count += structured.get(
            "total_detections", 0
        )

        # Structured logging
        person_detections = structured.get("workers", [])
        tracked_workers = structured.get("tracked_workers", [])

        ppe_list = (
            structured.get("compliant_ppe", [])
            or structured.get("ppe", [])
        )

        violation_list = structured.get("violations", [])

        if person_detections or ppe_list or violation_list:

            logger.info(
                f"[YOLO DETECTIONS] Total: "
                f"{structured.get('total_detections', 0)} | "
                f"Person detections: {len(person_detections)}, "
                f"Tracked workers: {len(tracked_workers)}, "
                f"PPE: {len(ppe_list)}, "
                f"Violations: {len(violation_list)}"
            )

            for worker_det in person_detections:
                logger.info(
                    f"Person detection: "
                    f"ByteTrack ID: {worker_det.get('track_id')}, "
                    f"Confidence: "
                    f"{worker_det.get('confidence', 0.0):.2f}, "
                    f"BBox: {worker_det.get('bbox')}"
                )

            for worker_det in tracked_workers:
                logger.info(
                    "Tracked worker: ID %s, confidence %.2f, bbox %s",
                    worker_det["track_id"],
                    worker_det.get("confidence", 0.0),
                    worker_det.get("bbox"),
                )

            for p in ppe_list:
                logger.info(
                    f"PPE: {p.get('class_name')}, "
                    f"Confidence: {p.get('confidence', 0.0):.2f}, "
                    f"BBox: {p.get('bbox')}"
                )

            for v in violation_list:
                logger.info(
                    f"Violation: {v.get('class_name')}, "
                    f"Confidence: "
                    f"{v.get('confidence', 0.0):.2f}, "
                    f"BBox: {v.get('bbox')}"
                )

        # Step 4-8: Downstream pipeline
        return self.process_structured_data(
            structured_detections=structured,
            frame_width=frame_w,
            frame_height=frame_h,
            timestamp=ts,
        )

    def process_structured_data(
        self,
        structured_detections: Dict[str, Any],
        frame_width: int = 1280,
        frame_height: int = 720,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:

        ts = float(
            timestamp if timestamp is not None else time.time()
        )

        # Step 4: Worker lifecycle
        lifecycle_stats = self.worker_tracking_service.update(
            worker_detections=structured_detections,
            current_time=ts,
        )

        # Step 5 and 6: PPE association
        assoc_result = self.association_service.associate(
            structured_detections=structured_detections
        )

        associations = assoc_result.get("associations", [])
        unassigned_ppe = assoc_result.get("unassigned_ppe", [])

        active_workers = structured_detections.get(
            "tracked_workers",
            structured_detections.get("workers", []),
        )

        active_track_ids = [
            int(w["track_id"])
            for w in active_workers
            if w.get("track_id") is not None
        ]

        # Step 7: PPE compliance
        compliance_result = self.compliance_service.evaluate_all(
            associations_payload=associations,
            worker_track_ids=active_track_ids,
        )

        worker_evals = compliance_result.get(
            "worker_evaluations", {}
        )

        # Step 8A: Assemble worker records
        worker_assoc_map: Dict[int, List[Dict[str, Any]]] = {}

        for a in associations:
            wid = a.get("worker_track_id")

            if wid is not None:
                worker_assoc_map.setdefault(wid, []).append(a)

        workers_payload: List[Dict[str, Any]] = []

        for w in active_workers:

            track_id = w.get("track_id")

            if track_id is None:
                continue

            track_id = int(track_id)

            bbox = [
                float(v)
                for v in w.get("bbox", [])
            ]
            tracked_record = self.worker_tracking_service.get_worker(track_id)
            if tracked_record is None:
                logger.error("Tracked worker #%s has no lifecycle record.", track_id)
                continue

            w_eval = worker_evals.get(track_id, {})
            w_assocs = worker_assoc_map.get(track_id, [])

            overall_st = w_eval.get(
                "overall_status", "needs_review"
            )

            ppe_st = w_eval.get("ppe_status", {})
            missing_items = w_eval.get("missing_ppe", [])
            missing_lbls = w_eval.get("missing_ppe_labels", [])

            worker_item = {
                "worker_id": track_id,
                "worker_track_id": track_id,
                "worker_bounding_box": bbox,
                "confidence": tracked_record.confidence,
                "first_seen": tracked_record.first_seen,
                "last_seen": tracked_record.last_seen,
                "total_frames_detected": tracked_record.total_frames_detected,
                "lifecycle_status": "active",
                "overall_status": overall_st,
                "compliance_status": overall_st,
                "overall_reason": w_eval.get(
                    "overall_reason", "No evaluation data"
                ),
                "compliant_category_count": int(
                    w_eval.get("compliant_count", 0)
                ),
                "violation_count": int(
                    w_eval.get("violation_count", 0)
                ),
                "not_detected_count": int(
                    w_eval.get("not_detected_count", 0)
                ),
                "uncertain_count": int(
                    w_eval.get("uncertain_count", 0)
                ),
                "categories": w_eval.get("categories", {}),
                "ppe_status": ppe_st,
                "missing_ppe": missing_items,
                "missing_ppe_labels": missing_lbls,
                "associated_ppe": w_assocs,
            }

            workers_payload.append(worker_item)

            logger.info(
                f"[WORKER COMPLIANCE] Worker #{track_id} -> "
                f"Status: {overall_st.upper()} | "
                f"Missing PPE: "
                f"{missing_lbls if missing_lbls else 'None'}"
            )

        # Step 8B: Violation timers
        timer_summary = self.violation_timer_service.update(
            monitoring_payload={"workers": workers_payload},
            current_time=ts,
        )

        # Step 8C: Alarm service
        alarm_summary = self.alarm_service.update(
            alarm_eligible_violations=timer_summary.get(
                "alarm_eligible_timers", []
            ),
            current_time=ts,
        )

        # Step 8D: Violation events
        event_summary = self.violation_event_service.update(
            alarm_eligible_violations=timer_summary.get(
                "alarm_eligible_timers", []
            ),
            alarm_summary=alarm_summary,
            current_time=ts,
        )

        # Step 9: Consolidated result
        result = {
            "timestamp": ts,
            "frame_width": int(frame_width),
            "frame_height": int(frame_height),
            "detection_count": int(
                structured_detections.get("total_detections", 0)
            ),
            "worker_lifecycle": lifecycle_stats,
            "total_workers": int(
                compliance_result.get(
                    "total_workers",
                    len(workers_payload),
                )
            ),
            "total_compliant": int(
                compliance_result.get("compliant_workers", 0)
            ),
            "total_non_compliant": int(
                compliance_result.get("non_compliant_workers", 0)
            ),
            "total_needs_review": int(
                compliance_result.get("needs_review_workers", 0)
            ),
            "workers": workers_payload,
            "unassigned_ppe": unassigned_ppe,
            "associations": associations,
            "violation_timers": timer_summary.get(
                "active_timers", []
            ),
            "alarm_eligible_violations": timer_summary.get(
                "alarm_eligible_timers", []
            ),
            "active_timer_count": int(
                timer_summary.get("active_timers_count", 0)
            ),
            "alarm_eligible_count": int(
                timer_summary.get("alarm_eligible_count", 0)
            ),
            "alarms": alarm_summary.get("active_alarms", []),
            "triggered_alarms": alarm_summary.get(
                "triggered_alarms", []
            ),
            "active_alarms_count": int(
                alarm_summary.get("active_alarms_count", 0)
            ),
            "violation_events": (
                self.violation_event_service.get_all_events()
            ),
            "active_violation_events": (
                self.violation_event_service.get_active_events()
            ),
            "violation_event_summary": event_summary,
            "active_model_id": get_active_model_id(),
            "active_model_name": get_model_profile().display_name,
            "error": None,
        }

        self._last_result = result

        # Step 10: WebSocket broadcast
        if (
            self.websocket_manager is not None
            and self.websocket_manager.has_connections()
        ):
            self.websocket_manager.broadcast_monitoring_update(
                result
            )

        return result

    def _empty_response(
        self,
        timestamp: float,
        frame_width: int = 0,
        frame_height: int = 0,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:

        return {
            "timestamp": float(timestamp),
            "frame_width": int(frame_width),
            "frame_height": int(frame_height),
            "detection_count": 0,
            "worker_lifecycle": (
                self.worker_tracking_service.get_session_statistics()
            ),
            "total_workers": 0,
            "total_compliant": 0,
            "total_non_compliant": 0,
            "total_needs_review": 0,
            "workers": [],
            "unassigned_ppe": [],
            "associations": [],
            "violation_timers": (
                self.violation_timer_service.get_active_timers()
            ),
            "alarm_eligible_violations": (
                self.violation_timer_service.get_alarm_eligible_timers()
            ),
            "active_timer_count": len(
                self.violation_timer_service.get_active_timers()
            ),
            "alarm_eligible_count": len(
                self.violation_timer_service.get_alarm_eligible_timers()
            ),
            "alarms": self.alarm_service.get_active_alarms(),
            "triggered_alarms": [],
            "active_alarms_count": len(
                self.alarm_service.get_active_alarms()
            ),
            "violation_events": (
                self.violation_event_service.get_all_events()
            ),
            "active_violation_events": (
                self.violation_event_service.get_active_events()
            ),
            "violation_event_summary": (
                self.violation_event_service.get_summary(
                    current_time=timestamp
                )
            ),
            "error": error,
        }

    def get_latest_monitoring_data(self) -> Dict[str, Any]:
        """Return latest monitoring data or baseline response."""

        if self._last_result is not None:
            return self._last_result

        return self._empty_response(timestamp=time.time())

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Return performance metrics."""

        fps = (
            round(1000.0 / self._avg_frame_time_ms, 1)
            if self._avg_frame_time_ms > 0
            else 0.0
        )

        return {
            "latest_inference_latency_ms": (
                self._latest_inference_latency_ms
            ),
            "avg_inference_latency_ms": (
                self._avg_inference_latency_ms
            ),
            "max_inference_latency_ms": (
                self._max_inference_latency_ms
            ),
            "avg_frame_time_ms": self._avg_frame_time_ms,
            "fps": fps,
            "total_detections": self._total_detections_count,
            "confidence_threshold": self.conf_threshold,
            "imgsz": self.imgsz,
            "device": self.device,
        }

    def set_confidence_threshold(
        self,
        threshold: float,
    ) -> None:

        self.conf_threshold = max(
            0.01,
            min(0.99, float(threshold)),
        )

        if hasattr(self.compliance_service, "min_confidence"):
            self.compliance_service.min_confidence = (
                self.conf_threshold
            )

        logger.info(
            f"PPEMonitoringService confidence threshold updated "
            f"to {self.conf_threshold:.2f}"
        )


# Module-level singleton
_monitoring_service_instance: Optional[PPEMonitoringService] = None


def get_monitoring_service() -> PPEMonitoringService:
    """Return shared PPEMonitoringService singleton."""

    global _monitoring_service_instance

    if _monitoring_service_instance is None:
        _monitoring_service_instance = PPEMonitoringService()

    return _monitoring_service_instance
