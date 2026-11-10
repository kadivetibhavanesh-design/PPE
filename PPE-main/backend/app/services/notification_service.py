import copy
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from app.services.websocket_manager import get_websocket_manager
except ImportError:
    from services.websocket_manager import get_websocket_manager

logger = logging.getLogger("ppe_monitoring.notification_service")

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"
NOTIFICATIONS_FILE = STORAGE_DIR / "notifications.json"


@dataclass
class NotificationRecord:
    id: str
    event_type: str
    category: str  # "ppe" | "alarm" | "email" | "monitoring"
    title: str
    description: str
    severity: str  # "critical" | "high" | "medium" | "low" | "info"
    timestamp: float
    read: bool = False
    worker_id: Optional[int] = None
    incident_id: Optional[str] = None
    destination: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["datetime"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        return data


class NotificationService:
    """
    Manages persistent notification records for the SafeVision AI real-time notification center.
    Persists data locally in JSON format, coordinates real-time WebSocket broadcasts,
    and provides thread-safe query, mark-read, and clear operations.
    """

    def __init__(self, storage_file: Optional[Path] = None):
        self.storage_file = storage_file or NOTIFICATIONS_FILE
        self._lock = threading.Lock()
        self._notifications: List[NotificationRecord] = []
        self._notification_ids: set = set()
        # Cooldown deduplication map: deduplication_key -> last_timestamp
        self._dedup_cache: Dict[str, float] = {}

        self._ensure_storage_dir()
        self._load_notifications()

    def _ensure_storage_dir(self) -> None:
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create notification storage directory: {e}")

    def _save_notifications(self) -> None:
        """Atomic write of notifications to JSON file."""
        try:
            payload = [n.to_dict() for n in self._notifications]
            tmp = self.storage_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.storage_file)
        except Exception as e:
            logger.error(f"Failed to persist notifications: {e}")

    def _load_notifications(self) -> None:
        """Loads persisted notifications from disk."""
        if not self.storage_file.exists():
            return
        try:
            data = json.loads(self.storage_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                with self._lock:
                    self._notifications = []
                    self._notification_ids.clear()
                    for item in data:
                        if isinstance(item, dict) and "id" in item:
                            rec = NotificationRecord(
                                id=str(item["id"]),
                                event_type=str(item.get("event_type", "general")),
                                category=str(item.get("category", "monitoring")),
                                title=str(item.get("title", "")),
                                description=str(item.get("description", "")),
                                severity=str(item.get("severity", "info")),
                                timestamp=float(item.get("timestamp", time.time())),
                                read=bool(item.get("read", False)),
                                worker_id=item.get("worker_id"),
                                incident_id=item.get("incident_id"),
                                destination=item.get("destination"),
                                metadata=item.get("metadata", {}),
                            )
                            self._notifications.append(rec)
                            self._notification_ids.add(rec.id)
                    logger.info(f"Loaded {len(self._notifications)} notifications from storage.")
        except Exception as e:
            logger.warning(f"Error loading notification storage file: {e}")

    def create_notification(
        self,
        event_type: str,
        category: str,
        title: str,
        description: str,
        severity: str = "info",
        worker_id: Optional[int] = None,
        incident_id: Optional[str] = None,
        destination: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        dedup_window_sec: float = 3.0,
        custom_id: Optional[str] = None,
    ) -> Optional[NotificationRecord]:
        """
        Creates, stores, and broadcasts a new real-time notification.
        Deduplicates repeated events within dedup_window_sec.
        """
        now = time.time()
        dedup_key = f"{event_type}:{incident_id}:{worker_id}:{title}"

        with self._lock:
            # Check deduplication window to avoid repeated frame noise
            last_time = self._dedup_cache.get(dedup_key)
            if last_time is not None and (now - last_time) < dedup_window_sec:
                return None
            self._dedup_cache[dedup_key] = now

            # Clean old dedup cache entries (older than 60s)
            if len(self._dedup_cache) > 200:
                self._dedup_cache = {
                    k: v for k, v in self._dedup_cache.items() if (now - v) < 60.0
                }

            notif_id = custom_id or f"NOTIF-{int(now * 1000)}-{len(self._notifications) + 1:03d}"
            # Ensure unique ID
            if notif_id in self._notification_ids:
                notif_id = f"{notif_id}-{int(now * 1000000) % 10000}"

            rec = NotificationRecord(
                id=notif_id,
                event_type=event_type,
                category=category,
                title=title,
                description=description,
                severity=severity,
                timestamp=now,
                read=False,
                worker_id=worker_id,
                incident_id=incident_id,
                destination=destination,
                metadata=metadata or {},
            )

            # Prepend newest first
            self._notifications.insert(0, rec)
            self._notification_ids.add(rec.id)

            # Bounded capacity safeguard: keep at most 500 recent notifications
            if len(self._notifications) > 500:
                removed = self._notifications.pop()
                self._notification_ids.discard(removed.id)

            self._save_notifications()

        # Real-time WebSocket broadcast outside lock
        try:
            ws_mgr = get_websocket_manager()
            if ws_mgr is not None:
                ws_mgr.broadcast_sync({
                    "type": "notification",
                    "timestamp": now,
                    "data": rec.to_dict(),
                })
        except Exception as ws_err:
            logger.debug(f"Could not broadcast notification to WebSocket: {ws_err}")

        logger.info(f"Created notification [{rec.id}] {title} ({severity})")
        return rec

    def get_notifications(
        self,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
        category: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns paginated notifications and aggregate unread count."""
        with self._lock:
            items = self._notifications

            if unread_only:
                items = [n for n in items if not n.read]

            if category:
                cat_lower = str(category).lower().strip()
                items = [n for n in items if n.category.lower() == cat_lower]

            if severity:
                sev_lower = str(severity).lower().strip()
                items = [n for n in items if n.severity.lower() == sev_lower]

            total = len(items)
            unread_total = sum(1 for n in self._notifications if not n.read)
            paginated = items[offset : offset + limit]

            return {
                "total": total,
                "unread_count": unread_total,
                "notifications": [n.to_dict() for n in paginated],
            }

    def get_unread_count(self) -> int:
        """Returns the total number of unread notifications."""
        with self._lock:
            return sum(1 for n in self._notifications if not n.read)

    def mark_as_read(self, notification_id: str) -> bool:
        """Marks an individual notification as read."""
        with self._lock:
            for rec in self._notifications:
                if rec.id == notification_id:
                    if not rec.read:
                        rec.read = True
                        self._save_notifications()
                    return True
        return False

    def mark_all_as_read(self) -> int:
        """Marks all notifications as read."""
        marked = 0
        with self._lock:
            for rec in self._notifications:
                if not rec.read:
                    rec.read = True
                    marked += 1
            if marked > 0:
                self._save_notifications()
        return marked

    def clear_all(self) -> int:
        """Clears all stored notification history."""
        with self._lock:
            count = len(self._notifications)
            self._notifications.clear()
            self._notification_ids.clear()
            self._save_notifications()
        logger.info(f"Cleared {count} notifications.")
        return count

    def delete_notification(self, notification_id: str) -> bool:
        """Deletes a specific notification by ID."""
        with self._lock:
            initial_count = len(self._notifications)
            self._notifications = [n for n in self._notifications if n.id != notification_id]
            if len(self._notifications) < initial_count:
                self._notification_ids.discard(notification_id)
                self._save_notifications()
                return True
        return False


# Singleton instance
_notification_service_instance: Optional[NotificationService] = None
_instance_lock = threading.Lock()


def get_notification_service() -> NotificationService:
    global _notification_service_instance
    if _notification_service_instance is None:
        with _instance_lock:
            if _notification_service_instance is None:
                _notification_service_instance = NotificationService()
    return _notification_service_instance

