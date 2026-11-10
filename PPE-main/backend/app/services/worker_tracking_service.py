import logging
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("ppe_monitoring.worker_tracking_service")

# Standard Worker Lifecycle Statuses
STATUS_ACTIVE = "active"
STATUS_MISSING = "missing"
STATUS_LEFT = "left"


@dataclass
class WorkerRecord:
    """
    In-memory record tracking an individual worker lifecycle during a monitoring session.
    Uses ByteTrack integer ID as session-bound temporary identity.
    """
    track_id: int
    first_seen: float
    last_seen: float
    confidence: float = 0.0
    total_frames_detected: int = 1
    current_status: str = STATUS_ACTIVE
    last_known_bounding_box: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes worker record to a dictionary."""
        return {
            "track_id": self.track_id,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "confidence": self.confidence,
            "total_frames_detected": self.total_frames_detected,
            "current_status": self.current_status,
            "last_known_bounding_box": list(self.last_known_bounding_box),
        }


class WorkerTrackingService:
    """
    Manages in-memory worker lifecycle throughout a monitoring session.
    Tracks worker presence, detects new arrivals, flags temporary absence,
    and marks departure after a configurable timeout threshold.
    """

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        """
        Initializes the WorkerTrackingService.

        Args:
            timeout_seconds: Duration in seconds of continuous absence before
                             marking an absent worker as 'left'. Default: 5.0 seconds.
        """
        self.timeout_seconds: float = float(timeout_seconds)
        self._workers: Dict[int, WorkerRecord] = {}

    def update(
        self,
        worker_detections: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
        current_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Updates worker lifecycle states based on current frame detections.

        Args:
            worker_detections: Structured detections from detection_service
                               (either dict with 'workers' list, or list of worker items).
            current_time: Optional explicit timestamp (float). Uses time.time() if None.
                          Allows deterministic unit testing without real-time delays.

        Returns:
            dict: Updated session statistics summary.
        """
        now = float(current_time if current_time is not None else time.time())
        detected_ids_in_frame: Set[int] = set()

        # Parse worker detections
        workers_list: List[Dict[str, Any]] = []
        if isinstance(worker_detections, dict):
            workers_list = worker_detections.get(
                "tracked_workers",
                worker_detections.get("workers", []),
            )
        elif isinstance(worker_detections, list):
            workers_list = worker_detections

        # 1. Process all workers detected in the current frame
        for item in workers_list:
            if not isinstance(item, dict):
                continue

            raw_track_id = item.get("track_id")
            if raw_track_id is None or isinstance(raw_track_id, bool):
                continue

            try:
                track_id = int(raw_track_id)
                confidence = float(item["confidence"])
                bbox = [float(value) for value in item["bbox"]]
            except (KeyError, TypeError, ValueError, OverflowError):
                logger.warning("Skipping tracked worker with invalid ID, confidence, or bounding box.")
                continue

            if (
                track_id < 0
                or len(bbox) != 4
                or not all(math.isfinite(value) for value in bbox)
                or bbox[2] <= bbox[0]
                or bbox[3] <= bbox[1]
                or not math.isfinite(confidence)
                or not 0.0 <= confidence <= 1.0
            ):
                logger.warning("Skipping tracked worker with invalid ID, confidence, or bounding box.")
                continue

            detected_ids_in_frame.add(track_id)

            if track_id not in self._workers:
                # New worker observed for the first time
                self._workers[track_id] = WorkerRecord(
                    track_id=track_id,
                    first_seen=now,
                    last_seen=now,
                    confidence=confidence,
                    total_frames_detected=1,
                    current_status=STATUS_ACTIVE,
                    last_known_bounding_box=bbox,
                )
                logger.debug(f"New worker #{track_id} registered at {now:.2f}")
            else:
                # Existing worker detected again
                record = self._workers[track_id]
                record.last_seen = now
                record.confidence = confidence
                record.total_frames_detected += 1
                record.last_known_bounding_box = bbox
                record.current_status = STATUS_ACTIVE

        # 2. Update lifecycle for absent workers
        for track_id, record in self._workers.items():
            if track_id not in detected_ids_in_frame:
                time_absent = now - record.last_seen
                if time_absent >= self.timeout_seconds:
                    record.current_status = STATUS_LEFT
                else:
                    record.current_status = STATUS_MISSING

        return self.get_session_statistics()

    def get_worker(self, track_id: int) -> Optional[WorkerRecord]:
        """Retrieves a single worker record by track ID."""
        return self._workers.get(track_id)

    def get_all_workers(self) -> Dict[int, WorkerRecord]:
        """Returns all worker records registered in the current session."""
        return dict(self._workers)

    def get_total_workers_observed(self) -> int:
        """Returns the total number of unique worker IDs observed so far."""
        return len(self._workers)

    def get_active_workers(self) -> List[WorkerRecord]:
        """Returns all workers currently marked as active."""
        return [w for w in self._workers.values() if w.current_status == STATUS_ACTIVE]

    def get_missing_workers(self) -> List[WorkerRecord]:
        """Returns all workers currently marked as temporarily missing."""
        return [w for w in self._workers.values() if w.current_status == STATUS_MISSING]

    def get_left_workers(self) -> List[WorkerRecord]:
        """Returns all workers who have exceeded the departure timeout threshold."""
        return [w for w in self._workers.values() if w.current_status == STATUS_LEFT]

    def get_session_statistics(self) -> Dict[str, Any]:
        """
        Returns an aggregated summary of active, missing, and departed workers.
        """
        active = self.get_active_workers()
        missing = self.get_missing_workers()
        left = self.get_left_workers()

        return {
            "total_workers_observed": len(self._workers),
            "active_count": len(active),
            "missing_count": len(missing),
            "left_count": len(left),
            "active_ids": sorted([w.track_id for w in active]),
            "missing_ids": sorted([w.track_id for w in missing]),
            "left_ids": sorted([w.track_id for w in left]),
        }

    def reset(self) -> None:
        """Clears all in-memory worker tracking records."""
        self._workers.clear()
        logger.info("WorkerTrackingService in-memory records reset.")
