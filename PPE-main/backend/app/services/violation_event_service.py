import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("ppe_monitoring.violation_event_service")

# Event statuses
STATUS_OPEN = "open"
STATUS_ONGOING = "ongoing"
STATUS_RESOLVED = "resolved"
STATUS_CLOSED = "closed"
STATUS_INTERRUPTED = "interrupted"

# Severity levels
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_UNCLASSIFIED = "unclassified"

SEVERITY_PRIORITY: Dict[str, int] = {
    SEVERITY_CRITICAL: 4,
    SEVERITY_HIGH: 3,
    SEVERITY_MEDIUM: 2,
    SEVERITY_UNCLASSIFIED: 1,
}

DEFAULT_SEVERITY_MAPPING: Dict[str, str] = {
    "hardhat": SEVERITY_CRITICAL,
    "safety_vest": SEVERITY_HIGH,
    "safety_shoes": SEVERITY_HIGH,
    "gloves": SEVERITY_MEDIUM,
    "goggles": SEVERITY_MEDIUM,
    "mask": SEVERITY_MEDIUM,
}


@dataclass
class ViolationEventRecord:
    """
    In-memory representation of a confirmed PPE violation lifecycle event.
    Represents a consolidated worker incident containing one or more missing PPE categories.
    """
    event_id: str
    worker_track_id: int
    ppe_category: str
    severity: str
    status: str
    start_timestamp: float
    confirmation_timestamp: float
    last_updated_timestamp: float
    alarm_status: str = "none"
    resolution_timestamp: Optional[float] = None
    closure_timestamp: Optional[float] = None
    ppe_categories: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.ppe_categories and self.ppe_category:
            self.ppe_categories = [c.strip() for c in self.ppe_category.split(",") if c.strip()]
        elif self.ppe_categories and not self.ppe_category:
            self.ppe_category = ", ".join(self.ppe_categories)

    @property
    def violation_duration(self) -> float:
        """Total duration from start_timestamp to last_updated_timestamp in seconds."""
        end_time = self.resolution_timestamp or self.closure_timestamp or self.last_updated_timestamp
        return max(0.0, round(end_time - self.start_timestamp, 3))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes event record to a JSON-serializable dictionary."""
        return {
            "event_id": self.event_id,
            "worker_track_id": self.worker_track_id,
            "ppe_categories": list(self.ppe_categories),
            "ppe_category": self.ppe_category,
            "severity": self.severity,
            "status": self.status,
            "start_timestamp": round(self.start_timestamp, 3),
            "confirmation_timestamp": round(self.confirmation_timestamp, 3),
            "last_updated_timestamp": round(self.last_updated_timestamp, 3),
            "violation_duration": self.violation_duration,
            "alarm_status": self.alarm_status,
            "resolution_timestamp": round(self.resolution_timestamp, 3) if self.resolution_timestamp else None,
            "closure_timestamp": round(self.closure_timestamp, 3) if self.closure_timestamp else None,
        }


class ViolationEventService:
    """
    Manages the lifecycle of confirmed PPE violation events in RAM.
    Consolidates all PPE violations per tracked worker into a single incident (EVT-XXXX).
    Tracks creation, continuous updates, resolution, and closure for industrial safety audits.
    """

    def __init__(
        self,
        severity_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initializes the ViolationEventService.

        Args:
            severity_mapping: Optional custom category-to-severity mapping.
        """
        self.severity_mapping: Dict[str, str] = (
            dict(severity_mapping) if severity_mapping is not None else dict(DEFAULT_SEVERITY_MAPPING)
        )

        # In-memory storage: event_id -> ViolationEventRecord
        self._events: Dict[str, ViolationEventRecord] = {}
        # Active episode map: worker_track_id -> event_id (one active incident per worker)
        self._active_episode_map: Dict[int, str] = {}
        # Session event counter for unique IDs
        self._event_counter: int = 0

        # Event callbacks and transition tracking
        self._on_created_callbacks: List[Callable[[ViolationEventRecord], None]] = []
        self._on_updated_callbacks: List[Callable[[ViolationEventRecord], None]] = []
        self._on_resolved_callbacks: List[Callable[[ViolationEventRecord], None]] = []
        self._on_closed_callbacks: List[Callable[[ViolationEventRecord], None]] = []
        self._on_interrupted_callbacks: List[Callable[[ViolationEventRecord], None]] = []
        self._last_created_events: List[ViolationEventRecord] = []
        self._last_resolved_events: List[ViolationEventRecord] = []

    def register_listener(
        self,
        on_created: Optional[Callable[[ViolationEventRecord], None]] = None,
        on_resolved: Optional[Callable[[ViolationEventRecord], None]] = None,
        on_closed: Optional[Callable[[ViolationEventRecord], None]] = None,
        on_updated: Optional[Callable[[ViolationEventRecord], None]] = None,
        on_interrupted: Optional[Callable[[ViolationEventRecord], None]] = None,
    ) -> None:
        """Registers callback functions triggered on event lifecycle transitions."""
        if on_created:
            self._on_created_callbacks.append(on_created)
        if on_updated:
            self._on_updated_callbacks.append(on_updated)
        if on_resolved:
            self._on_resolved_callbacks.append(on_resolved)
        if on_closed:
            self._on_closed_callbacks.append(on_closed)
        if on_interrupted:
            self._on_interrupted_callbacks.append(on_interrupted)

    def get_last_created_events(self) -> List[ViolationEventRecord]:
        """Returns the violation event records created during the most recent update."""
        return list(self._last_created_events)

    def get_last_resolved_events(self) -> List[ViolationEventRecord]:
        """Returns the violation event records resolved during the most recent update."""
        return list(self._last_resolved_events)

    def classify_severity(self, ppe_category: str) -> str:
        """Classifies severity level for a given PPE category."""
        return self.severity_mapping.get(str(ppe_category).lower(), SEVERITY_UNCLASSIFIED)

    def classify_highest_severity(self, ppe_categories: List[str]) -> str:
        """Determines the highest severity level among multiple PPE categories."""
        if not ppe_categories:
            return SEVERITY_UNCLASSIFIED
        return max(
            (self.classify_severity(cat) for cat in ppe_categories),
            key=lambda s: SEVERITY_PRIORITY.get(s, 0),
        )

    def _generate_event_id(self) -> str:
        """Generates a sequential session-scoped event identifier."""
        self._event_counter += 1
        return f"EVT-{self._event_counter:04d}"

    def update(
        self,
        alarm_eligible_violations: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
        alarm_summary: Optional[Dict[str, Any]] = None,
        current_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Updates violation events based on current frame's alarm-eligible violations.
        Consolidates all PPE violations belonging to the same tracked worker into one incident.

        Lifecycle Rules:
            1. If a worker has alarm-eligible violations and no active event exists,
               create ONE new consolidated event with status='open'.
            2. If the violation continues across subsequent frames, update status='ongoing'
               and update last_updated_timestamp without changing event_id.
            3. If an additional violation is detected for the same worker while active,
               update the existing incident's violation list. Do not create a separate event.
            4. If an active worker has no confirmed violations in the current frame,
               transition their incident to status='resolved'.
            5. If a resolved violation occurs again later, a new event with a new event_id is created.

        Args:
            alarm_eligible_violations: List of alarm-eligible violation dicts or payload dict.
            alarm_summary: Optional summary payload from AlarmService containing active alarm states.
            current_time: Optional float timestamp for deterministic testing.

        Returns:
            dict: Summary containing all active events and aggregate metrics.
        """
        now = float(current_time if current_time is not None else time.time())

        # Extract items from various supported input formats
        eligible_items: List[Dict[str, Any]] = []
        if isinstance(alarm_eligible_violations, dict):
            if "alarm_eligible_violations" in alarm_eligible_violations:
                eligible_items = alarm_eligible_violations["alarm_eligible_violations"]
            elif "alarm_eligible_timers" in alarm_eligible_violations:
                eligible_items = alarm_eligible_violations["alarm_eligible_timers"]
        elif isinstance(alarm_eligible_violations, list):
            eligible_items = alarm_eligible_violations

        # Extract alarm status map: worker_track_id -> alarm_status
        alarm_status_map: Dict[int, str] = {}
        if isinstance(alarm_summary, dict):
            alarms_list = alarm_summary.get("active_alarms", [])
            for al in alarms_list:
                if isinstance(al, dict):
                    w_id = al.get("worker_track_id")
                    if w_id is not None:
                        try:
                            alarm_status_map[int(w_id)] = str(al.get("status", "active"))
                        except (ValueError, TypeError):
                            pass

        # Group eligible violations by worker_track_id
        eligible_by_worker: Dict[int, List[Dict[str, Any]]] = {}
        for item in eligible_items:
            if not isinstance(item, dict):
                continue

            track_id = item.get("worker_track_id")
            cat = item.get("ppe_category")
            if track_id is None or cat is None:
                continue

            try:
                track_id = int(track_id)
                cat = str(cat).strip()
            except (ValueError, TypeError):
                continue

            if not item.get("alarm_eligible", True):
                continue

            eligible_by_worker.setdefault(track_id, []).append(item)

        current_active_workers: Set[int] = set()
        new_events: List[ViolationEventRecord] = []
        resolved_events: List[ViolationEventRecord] = []

        for track_id, items in eligible_by_worker.items():
            current_active_workers.add(track_id)
            cats: List[str] = sorted(list({str(it.get("ppe_category", "")).strip() for it in items if it.get("ppe_category")}))
            if not cats:
                continue

            ppe_category_str = ", ".join(cats)
            severity = self.classify_highest_severity(cats)
            earliest_start = min(float(it.get("start_timestamp", now)) for it in items)
            rel_alarm_status = alarm_status_map.get(track_id, "active")

            if track_id in self._active_episode_map:
                # Existing active event episode continues for this worker
                event_id = self._active_episode_map[track_id]
                record = self._events[event_id]

                if record.status == STATUS_OPEN:
                    record.status = STATUS_ONGOING

                categories_changed = set(record.ppe_categories) != set(cats)
                record.ppe_categories = cats
                record.ppe_category = ppe_category_str
                record.severity = severity
                record.last_updated_timestamp = now
                record.alarm_status = rel_alarm_status

                if categories_changed:
                    logger.info(
                        f"Updated active violation event {event_id} for Worker #{track_id}: "
                        f"categories={cats}, severity={severity}"
                    )
                    for cb in self._on_updated_callbacks:
                        try:
                            cb(record)
                        except Exception as cb_err:
                            logger.error(f"Error in on_updated callback: {cb_err}")
            else:
                # New confirmed consolidated violation event episode begins
                event_id = self._generate_event_id()

                record = ViolationEventRecord(
                    event_id=event_id,
                    worker_track_id=track_id,
                    ppe_categories=cats,
                    ppe_category=ppe_category_str,
                    severity=severity,
                    status=STATUS_OPEN,
                    start_timestamp=earliest_start,
                    confirmation_timestamp=now,
                    last_updated_timestamp=now,
                    alarm_status=rel_alarm_status,
                )
                self._events[event_id] = record
                self._active_episode_map[track_id] = event_id
                new_events.append(record)

                # Bounded memory safeguard: prune oldest resolved/closed records if exceeding 1000
                if len(self._events) > 1000:
                    for old_id, old_rec in list(self._events.items()):
                        if old_rec.status in (STATUS_RESOLVED, STATUS_CLOSED) and old_id not in self._active_episode_map.values():
                            del self._events[old_id]
                            if len(self._events) <= 800:
                                break

                for cb in self._on_created_callbacks:
                    try:
                        cb(record)
                    except Exception as cb_err:
                        logger.error(f"Error in on_created callback: {cb_err}")
                logger.info(
                    f"Created consolidated violation event {event_id} for Worker #{track_id} -> {cats} [{severity}]"
                )

        # Automatically resolve events whose violations are no longer confirmed in this frame
        workers_to_resolve = [w for w in self._active_episode_map.keys() if w not in current_active_workers]
        for track_id in workers_to_resolve:
            event_id = self._active_episode_map.pop(track_id)
            record = self._events.get(event_id)
            if record and record.status in (STATUS_OPEN, STATUS_ONGOING):
                record.status = STATUS_RESOLVED
                record.resolution_timestamp = now
                record.last_updated_timestamp = now
                resolved_events.append(record)
                for cb in self._on_resolved_callbacks:
                    try:
                        cb(record)
                    except Exception as cb_err:
                        logger.error(f"Error in on_resolved callback: {cb_err}")
                logger.info(
                    f"Resolved violation event {event_id} for Worker #{record.worker_track_id} -> {record.ppe_categories}"
                )

        self._last_created_events = new_events
        self._last_resolved_events = resolved_events

        return self.get_summary(current_time=now)

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Returns a specific event dictionary by event ID."""
        record = self._events.get(str(event_id))
        return record.to_dict() if record else None

    def get_all_events(self) -> List[Dict[str, Any]]:
        """Returns all events recorded in the current session."""
        return [e.to_dict() for e in self._events.values()]

    def get_active_events(self) -> List[Dict[str, Any]]:
        """Returns all currently open or ongoing events."""
        return [e.to_dict() for e in self._events.values() if e.status in (STATUS_OPEN, STATUS_ONGOING)]

    def get_events_for_worker(self, worker_track_id: int) -> List[Dict[str, Any]]:
        """Returns all events associated with a specific worker track ID."""
        w_id = int(worker_track_id)
        return [e.to_dict() for e in self._events.values() if e.worker_track_id == w_id]

    def get_events_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Returns all events matching a specific lifecycle status."""
        target_status = str(status).lower()
        return [e.to_dict() for e in self._events.values() if e.status == target_status]

    def resolve_event(self, event_id: str, current_time: Optional[float] = None) -> bool:
        """
        Manually resolves an active event.

        Returns:
            bool: True if event was found and resolved, False otherwise.
        """
        now = float(current_time if current_time is not None else time.time())
        record = self._events.get(str(event_id))
        if record and record.status in (STATUS_OPEN, STATUS_ONGOING):
            record.status = STATUS_RESOLVED
            record.resolution_timestamp = now
            record.last_updated_timestamp = now
            # Clean up active episode mapping
            if self._active_episode_map.get(record.worker_track_id) == event_id:
                del self._active_episode_map[record.worker_track_id]
            for cb in self._on_resolved_callbacks:
                try:
                    cb(record)
                except Exception as cb_err:
                    logger.error(f"Error in on_resolved callback: {cb_err}")
            logger.info(f"Manually resolved event {event_id}")
            return True
        return False

    def close_event(self, event_id: str, current_time: Optional[float] = None) -> bool:
        """
        Explicitly closes an event (audit closure).

        Returns:
            bool: True if event was found and closed, False otherwise.
        """
        now = float(current_time if current_time is not None else time.time())
        record = self._events.get(str(event_id))
        if record:
            record.status = STATUS_CLOSED
            record.closure_timestamp = now
            record.last_updated_timestamp = now
            # Clean up active episode mapping if it was still active
            if self._active_episode_map.get(record.worker_track_id) == event_id:
                del self._active_episode_map[record.worker_track_id]
            for cb in self._on_closed_callbacks:
                try:
                    cb(record)
                except Exception as cb_err:
                    logger.error(f"Error in on_closed callback: {cb_err}")
            logger.info(f"Explicitly closed event {event_id}")
            return True
        return False

    def interrupt_active_events(
        self,
        reason: str = "monitoring_stopped",
        current_time: Optional[float] = None,
    ) -> List[ViolationEventRecord]:
        """
        Interrupts all currently active violation episodes when camera monitoring stops.
        Ensures incidents are NOT marked as resolved or workers as compliant.
        Cancels active episode mappings so a subsequent monitoring session requires fresh 5s confirmation.
        """
        now = float(current_time if current_time is not None else time.time())
        interrupted: List[ViolationEventRecord] = []
        for track_id, event_id in list(self._active_episode_map.items()):
            record = self._events.get(event_id)
            if record and record.status in (STATUS_OPEN, STATUS_ONGOING):
                record.status = STATUS_INTERRUPTED
                record.last_updated_timestamp = now
                interrupted.append(record)
                for cb in self._on_interrupted_callbacks:
                    try:
                        cb(record)
                    except Exception as cb_err:
                        logger.error(f"Error in on_interrupted callback: {cb_err}")
                logger.info(
                    f"Interrupted active incident {event_id} for Worker #{track_id} (reason: {reason})"
                )
        self._active_episode_map.clear()
        return interrupted

    def reset_all(self) -> None:
        """Clears all in-memory events and resets session counter."""
        self._events.clear()
        self._active_episode_map.clear()
        self._last_created_events.clear()
        self._last_resolved_events.clear()
        self._event_counter = 0
        logger.info("Cleared all violation events and reset session.")

    def get_summary(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Returns structured summary metrics grouped by status, severity, and PPE category.
        """
        now = float(current_time if current_time is not None else time.time())
        all_events = list(self._events.values())
        active_events = [e for e in all_events if e.status in (STATUS_OPEN, STATUS_ONGOING)]

        by_status: Dict[str, int] = {
            STATUS_OPEN: 0,
            STATUS_ONGOING: 0,
            STATUS_RESOLVED: 0,
            STATUS_CLOSED: 0,
        }
        by_severity: Dict[str, int] = {
            SEVERITY_CRITICAL: 0,
            SEVERITY_HIGH: 0,
            SEVERITY_MEDIUM: 0,
            SEVERITY_UNCLASSIFIED: 0,
        }
        by_category: Dict[str, int] = {}

        for e in all_events:
            by_status[e.status] = by_status.get(e.status, 0) + 1
            by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
            cats = e.ppe_categories if e.ppe_categories else [e.ppe_category]
            for cat in cats:
                if cat:
                    by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "timestamp": now,
            "total_events_count": len(all_events),
            "active_events_count": len(active_events),
            "by_status": by_status,
            "by_severity": by_severity,
            "by_category": by_category,
            "active_events": [e.to_dict() for e in active_events],
            "recent_events": [e.to_dict() for e in all_events[-10:]],
            "new_events": [e.to_dict() for e in self._last_created_events],
            "resolved_events": [e.to_dict() for e in self._last_resolved_events],
        }


