import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("ppe_monitoring.violation_timer_service")

# Violation status constants
STATUS_ACTIVE_VIOLATION = "active_violation"
STATUS_ALARM_ELIGIBLE = "alarm_eligible"

# Target compliance status that counts as confirmed violation
TARGET_VIOLATION_STATUS = "missing"
TARGET_VIOLATION_STATUSES = {"missing", "violation_detected", "violation"}


@dataclass
class ViolationTimerRecord:
    """
    In-memory record tracking continuous confirmed violation duration for a specific
    (worker_track_id, ppe_category) pair.
    """
    worker_track_id: int
    ppe_category: str
    start_timestamp: float
    last_confirmed_timestamp: float
    threshold_seconds: float = 5.0

    @property
    def elapsed_seconds(self) -> float:
        """Calculates total continuous elapsed duration in seconds."""
        return max(0.0, round(self.last_confirmed_timestamp - self.start_timestamp, 3))

    @property
    def remaining_seconds(self) -> float:
        """Calculates remaining seconds before reaching confirmation threshold."""
        return max(0.0, round(self.threshold_seconds - self.elapsed_seconds, 3))

    @property
    def alarm_eligible(self) -> bool:
        """True if the violation has persisted continuously for >= threshold_seconds."""
        return self.elapsed_seconds >= self.threshold_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Serializes timer record to a JSON-serializable dictionary."""
        return {
            "worker_track_id": self.worker_track_id,
            "ppe_category": self.ppe_category,
            "violation_status": STATUS_ALARM_ELIGIBLE if self.alarm_eligible else STATUS_ACTIVE_VIOLATION,
            "start_timestamp": round(self.start_timestamp, 3),
            "last_confirmed_timestamp": round(self.last_confirmed_timestamp, 3),
            "elapsed_seconds": self.elapsed_seconds,
            "threshold_seconds": round(self.threshold_seconds, 3),
            "remaining_seconds": self.remaining_seconds,
            "alarm_eligible": self.alarm_eligible,
        }


class ViolationTimerService:
    """
    Manages continuous PPE violation confirmation timers in RAM.
    Ensures that violations must be continuously confirmed for a configurable
    threshold (default: 5.0s) before becoming alarm-eligible, preventing false
    alarms caused by momentary detection dropouts or transient occlusions.
    """

    def __init__(self, default_threshold_seconds: float = 5.0) -> None:
        """
        Initializes the ViolationTimerService.

        Args:
            default_threshold_seconds: Continuous duration threshold in seconds
                                       before marking violation alarm-eligible (default: 5.0s).
        """
        self.default_threshold_seconds: float = float(default_threshold_seconds)
        # In-memory timers mapped by (worker_track_id, ppe_category)
        self._timers: Dict[Tuple[int, str], ViolationTimerRecord] = {}

    def update(
        self,
        monitoring_payload: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        current_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Updates violation timers based on the latest compliance evaluations.

        Args:
            monitoring_payload: Monitoring result payload from PPEMonitoringService or
                                a list of worker evaluation dictionaries.
            current_time: Optional explicit timestamp (float) for deterministic testing.

        Returns:
            dict: Summary containing active timers and alarm-eligible timers.
        """
        now = float(current_time if current_time is not None else time.time())

        # Extract worker evaluations from various accepted input formats
        workers_list: List[Dict[str, Any]] = []

        if isinstance(monitoring_payload, dict):
            if "workers" in monitoring_payload:
                workers_list = monitoring_payload["workers"]
            elif "worker_evaluations" in monitoring_payload:
                # Format: {"worker_evaluations": {track_id: eval_dict}}
                evals = monitoring_payload["worker_evaluations"]
                if isinstance(evals, dict):
                    workers_list = list(evals.values())
                elif isinstance(evals, list):
                    workers_list = evals
            elif "categories" in monitoring_payload:
                # Single worker evaluation dict
                workers_list = [monitoring_payload]
        elif isinstance(monitoring_payload, list):
            workers_list = monitoring_payload

        # Keep track of (worker_id, ppe_category) confirmed in this frame
        confirmed_in_frame: Set[Tuple[int, str]] = set()
        active_worker_ids_in_frame: Set[int] = set()

        # 1. Process active workers in the current frame
        for worker in workers_list:
            if not isinstance(worker, dict):
                continue

            track_id = worker.get("worker_track_id")
            if track_id is None:
                continue

            track_id = int(track_id)
            active_worker_ids_in_frame.add(track_id)

            categories = worker.get("categories", {})
            if not isinstance(categories, dict):
                continue

            for cat_key, cat_data in categories.items():
                if not isinstance(cat_data, dict):
                    continue

                status = cat_data.get("status")
                timer_key = (track_id, cat_key)

                if status in TARGET_VIOLATION_STATUSES:
                    confirmed_in_frame.add(timer_key)
                    if timer_key in self._timers:
                        # Continue existing timer
                        record = self._timers[timer_key]
                        record.last_confirmed_timestamp = now
                    else:
                        # Start new continuous violation timer
                        self._timers[timer_key] = ViolationTimerRecord(
                            worker_track_id=track_id,
                            ppe_category=cat_key,
                            start_timestamp=now,
                            last_confirmed_timestamp=now,
                            threshold_seconds=self.default_threshold_seconds,
                        )
                        logger.debug(f"Started violation timer for Worker #{track_id} -> {cat_key} at {now:.2f}")

        # 2. Reset any timers that were NOT continuously confirmed in this frame
        # (This handles: status became compliant, not_detected, uncertain, category disappeared,
        # or worker became absent/missing/left per Rules 6, 7, 8, 11)
        timers_to_remove = [k for k in self._timers.keys() if k not in confirmed_in_frame]
        for timer_key in timers_to_remove:
            w_id, cat_key = timer_key
            logger.debug(f"Resetting unconfirmed timer for Worker #{w_id} -> {cat_key}")
            del self._timers[timer_key]

        return self.get_summary(current_time=now)

    def get_timer(self, worker_track_id: int, ppe_category: str) -> Optional[Dict[str, Any]]:
        """Returns the specific timer dictionary for a worker and PPE category, if active."""
        record = self._timers.get((int(worker_track_id), str(ppe_category)))
        return record.to_dict() if record else None

    def get_active_timers(self) -> List[Dict[str, Any]]:
        """Returns all currently active violation timers."""
        return [t.to_dict() for t in self._timers.values()]

    def get_alarm_eligible_timers(self) -> List[Dict[str, Any]]:
        """Returns all timers that have met or exceeded the continuous threshold."""
        return [t.to_dict() for t in self._timers.values() if t.alarm_eligible]

    def reset_timer(self, worker_track_id: int, ppe_category: str) -> bool:
        """
        Resets a specific violation timer.

        Returns:
            bool: True if the timer existed and was reset, False otherwise.
        """
        key = (int(worker_track_id), str(ppe_category))
        if key in self._timers:
            del self._timers[key]
            logger.info(f"Explicitly reset violation timer for Worker #{worker_track_id} -> {ppe_category}")
            return True
        return False

    def reset_worker_timers(self, worker_track_id: int) -> int:
        """
        Resets all active timers for a given worker.

        Returns:
            int: Number of timers reset.
        """
        w_id = int(worker_track_id)
        keys_to_remove = [k for k in self._timers.keys() if k[0] == w_id]
        for k in keys_to_remove:
            del self._timers[k]
        logger.info(f"Reset {len(keys_to_remove)} timers for Worker #{worker_track_id}")
        return len(keys_to_remove)

    def reset_all(self) -> None:
        """Clears all in-memory violation timers across the entire session."""
        count = len(self._timers)
        self._timers.clear()
        logger.info(f"Cleared all {count} in-memory violation timers.")

    def get_summary(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Returns a structured summary of active and alarm-eligible timers.
        """
        now = float(current_time if current_time is not None else time.time())
        active = self.get_active_timers()
        eligible = self.get_alarm_eligible_timers()

        return {
            "timestamp": now,
            "active_timers_count": len(active),
            "alarm_eligible_count": len(eligible),
            "active_timers": active,
            "alarm_eligible_timers": eligible,
        }
