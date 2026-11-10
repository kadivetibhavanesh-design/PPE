import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("ppe_monitoring.evidence_service")

# Default evidence directory: backend/storage/evidence/
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORAGE_DIR = BACKEND_DIR / "storage" / "evidence"


class EvidenceService:
    """
    Manages local storage and retrieval of incident evidence for PPE violations.

    Responsibilities:
        - Captures and stores annotated JPEG frames for confirmed violation events.
        - Persists event metadata in structured JSON format locally.
        - Enforces strict filename validation and prevents path traversal attacks.
        - Prevents duplicate image captures for continuous or repeated frame updates.
        - Updates event lifecycle states (e.g., resolution, closure) locally.
        - Preserves and reloads historical metadata across application restarts.
    """

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initializes the EvidenceService with a target local storage directory.

        Args:
            storage_dir: Optional custom storage path. Defaults to backend/storage/evidence/.
        """
        self.storage_dir: Path = (
            Path(storage_dir).resolve() if storage_dir is not None else DEFAULT_STORAGE_DIR.resolve()
        )
        self._ensure_storage_dir()
        self.metadata_file: Path = self.storage_dir / "evidence_metadata.json"

        self._lock = threading.Lock()
        self._records: Dict[str, Dict[str, Any]] = {}
        self._saved_events: Set[str] = set()
        self.image_capture_enabled: bool = True

        # Load any existing persisted evidence metadata
        self._load_existing_metadata()

    def _ensure_storage_dir(self) -> None:
        """Ensures the evidence storage directory exists, creating parents if needed."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create evidence storage directory at {self.storage_dir}: {e}")
            raise

    def _load_existing_metadata(self) -> None:
        """
        Loads persisted metadata from disk on startup to preserve state across restarts.
        Reads both the consolidated evidence_metadata.json and individual event JSON files.
        """
        with self._lock:
            # 1. Load from consolidated evidence_metadata.json if present
            if self.metadata_file.exists():
                try:
                    raw_data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
                    if isinstance(raw_data, list):
                        for item in raw_data:
                            if isinstance(item, dict) and "event_id" in item:
                                eid = str(item["event_id"])
                                self._records[eid] = item
                                if item.get("image_filename") or item.get("evidence_image_filename"):
                                    self._saved_events.add(eid)
                    elif isinstance(raw_data, dict):
                        for eid, item in raw_data.items():
                            if isinstance(item, dict):
                                self._records[str(eid)] = item
                                if item.get("image_filename") or item.get("evidence_image_filename"):
                                    self._saved_events.add(str(eid))
                    logger.info(
                        f"Loaded {len(self._records)} evidence records from {self.metadata_file.name}."
                    )
                except Exception as e:
                    logger.warning(f"Error loading {self.metadata_file}: {e}")

            # 2. Check for individual event JSON files to catch any unindexed records
            if self.storage_dir.exists():
                try:
                    for json_path in self.storage_dir.glob("*.json"):
                        if json_path.name == "evidence_metadata.json":
                            continue
                        try:
                            record = json.loads(json_path.read_text(encoding="utf-8"))
                            if isinstance(record, dict) and "event_id" in record:
                                eid = str(record["event_id"])
                                if eid not in self._records:
                                    self._records[eid] = record
                                    if record.get("image_filename") or record.get("evidence_image_filename"):
                                        self._saved_events.add(eid)
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Error scanning individual evidence JSON files: {e}")

    def _write_master_metadata(self) -> None:
        """Writes all in-memory records to evidence_metadata.json atomically."""
        self._ensure_storage_dir()
        temp_file = self.storage_dir / f"evidence_metadata_{int(time.time() * 1000)}.tmp"
        try:
            records_list = list(self._records.values())
            temp_file.write_text(json.dumps(records_list, indent=2), encoding="utf-8")
            temp_file.replace(self.metadata_file)
        except Exception as e:
            logger.error(f"Failed to write master evidence metadata: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def validate_filename(self, filename: str) -> Path:
        """
        Validates a filename strictly to prevent directory traversal and injection attacks.

        Args:
            filename: Target file name (e.g. 'EVT-0001.jpg').

        Returns:
            Path: Safe resolved Path within self.storage_dir.

        Raises:
            ValueError: If path traversal or illegal characters are detected.
        """
        if not filename or not isinstance(filename, str):
            raise ValueError("Filename must be a non-empty string.")

        # Reject path separators, null bytes, and traversal tokens
        if "/" in filename or "\\" in filename or "\0" in filename or ".." in filename:
            raise ValueError(f"Directory traversal or invalid path separator detected in filename: '{filename}'")

        # Strict character set enforcement: alphanumeric, underscore, hyphen, dot
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
            raise ValueError(f"Filename contains illegal characters: '{filename}'")

        resolved_target = (self.storage_dir / filename).resolve()
        resolved_base = self.storage_dir.resolve()

        # Strict containment check
        try:
            resolved_target.relative_to(resolved_base)
        except ValueError:
            raise ValueError(f"Path traversal detected: '{filename}' resolves outside evidence directory.")

        return resolved_target

    def capture_evidence(
        self,
        event: Union[Dict[str, Any], Any],
        frame_bytes: Optional[bytes] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Captures and stores the annotated camera frame and event metadata for a new confirmed violation.

        Requirements enforced:
            - Captures evidence only when a confirmed violation event is created.
            - Links unique image filename to event ID (e.g., 'EVT-0001.jpg').
            - Avoids saving duplicate images for repeated updates to the same event.
            - Handles missing frame gracefully without throwing exceptions.
            - Creates missing storage directories automatically.

        Args:
            event: Violation event dictionary or record object.
            frame_bytes: Optional raw JPEG encoded bytes of the annotated frame.

        Returns:
            dict: The saved metadata record, or existing record if duplicate.
        """
        # Extract event attributes safely whether passed as dict or dataclass
        if isinstance(event, dict):
            event_id = str(event.get("event_id", ""))
            worker_track_id = event.get("worker_track_id", 0)
            ppe_category = str(event.get("ppe_category", "unknown"))
            severity = str(event.get("severity", "unclassified"))
            start_ts = event.get("start_timestamp", event.get("first_detected_timestamp", time.time()))
            status = str(event.get("status", event.get("event_status", "open")))
            resolution_ts = event.get("resolution_timestamp")
        else:
            event_id = str(getattr(event, "event_id", ""))
            worker_track_id = getattr(event, "worker_track_id", 0)
            ppe_category = str(getattr(event, "ppe_category", "unknown"))
            severity = str(getattr(event, "severity", "unclassified"))
            start_ts = getattr(event, "start_timestamp", getattr(event, "first_detected_timestamp", time.time()))
            status = str(getattr(event, "status", getattr(event, "event_status", "open")))
            resolution_ts = getattr(event, "resolution_timestamp", None)

        if not event_id:
            logger.warning("capture_evidence called with missing or empty event_id.")
            return None

        with self._lock:
            # 1. Prevent duplicate evidence image capture for the same event
            if event_id in self._saved_events:
                existing_record = self._records.get(event_id)
                if existing_record and existing_record.get("image_filename"):
                    logger.debug(f"Evidence for event '{event_id}' already captured; skipping duplicate.")
                    return dict(existing_record)

            # 2. Ensure storage directory is present (handles missing directory creation)
            self._ensure_storage_dir()

            # 3. Handle image saving with unique filename linked to event_id
            clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", event_id)
            image_filename: Optional[str] = None

            if not self.image_capture_enabled:
                frame_bytes = None

            if frame_bytes is not None and len(frame_bytes) > 0:
                image_filename = f"{clean_id}.jpg"
                image_path = self.storage_dir / image_filename
                try:
                    image_path.write_bytes(frame_bytes)
                    self._saved_events.add(event_id)
                    logger.info(f"Saved incident evidence frame: {image_filename} ({len(frame_bytes)} bytes)")
                except Exception as e:
                    logger.error(f"Failed to write evidence image {image_path}: {e}")
                    image_filename = None
            else:
                # Requirement 7: Missing frame handling
                logger.warning(
                    f"No frame bytes provided for violation event '{event_id}'; saving metadata record without image."
                )

            # 4. Construct complete event metadata JSON structure
            now_ts = round(time.time(), 3)
            start_timestamp_float = round(float(start_ts), 3) if start_ts is not None else now_ts
            resolution_timestamp_float = (
                round(float(resolution_ts), 3) if resolution_ts is not None else None
            )

            metadata: Dict[str, Any] = {
                "event_id": event_id,
                "worker_track_id": int(worker_track_id),
                "ppe_category": ppe_category,
                "severity": severity,
                "first_detected_timestamp": start_timestamp_float,
                "start_timestamp": start_timestamp_float,
                "evidence_image_filename": image_filename,
                "image_filename": image_filename,
                "event_status": status,
                "status": status,
                "resolution_timestamp": resolution_timestamp_float,
                "last_updated_timestamp": now_ts,
            }

            # 5. Persist individual event JSON file
            try:
                event_json_path = self.storage_dir / f"{clean_id}.json"
                event_json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to write event metadata file {clean_id}.json: {e}")

            # 6. Update in-memory registry and master metadata file
            self._records[event_id] = metadata
            self._write_master_metadata()

            return dict(metadata)

    def update_event_status(
        self,
        event_id: str,
        status: str,
        resolution_timestamp: Optional[float] = None,
        closure_timestamp: Optional[float] = None,
    ) -> bool:
        """
        Updates metadata when an event is resolved or closed.

        Args:
            event_id: Identifier of the violation event.
            status: New event status ('resolved' or 'closed').
            resolution_timestamp: Optional resolution epoch timestamp.
            closure_timestamp: Optional closure epoch timestamp.

        Returns:
            bool: True if event was found and updated, False otherwise.
        """
        with self._lock:
            eid = str(event_id)
            if eid not in self._records:
                return False

            now_ts = round(time.time(), 3)
            rec = self._records[eid]
            rec["event_status"] = str(status)
            rec["status"] = str(status)

            if resolution_timestamp is not None:
                rec["resolution_timestamp"] = round(float(resolution_timestamp), 3)
            elif status == "resolved" and rec.get("resolution_timestamp") is None:
                rec["resolution_timestamp"] = now_ts

            if closure_timestamp is not None:
                rec["closure_timestamp"] = round(float(closure_timestamp), 3)

            rec["last_updated_timestamp"] = now_ts

            # Persist updated individual file and master metadata
            self._ensure_storage_dir()
            clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", eid)
            try:
                (self.storage_dir / f"{clean_id}.json").write_text(
                    json.dumps(rec, indent=2), encoding="utf-8"
                )
            except Exception as e:
                logger.error(f"Failed to update {clean_id}.json: {e}")

            self._write_master_metadata()
            logger.info(f"Updated evidence metadata for event {eid} -> status='{status}'")
            return True

    def get_evidence(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Returns metadata dictionary for a specific event ID, or None if not found."""
        with self._lock:
            rec = self._records.get(str(event_id))
            return dict(rec) if rec else None

    def get_all_evidence(self) -> List[Dict[str, Any]]:
        """Returns a list of all recorded incident evidence metadata."""
        with self._lock:
            return [dict(r) for r in self._records.values()]

    def get_image_path(self, identifier: str) -> Optional[Path]:
        """
        Retrieves the validated on-disk image Path for a given event ID or image filename.

        Args:
            identifier: Either an event_id (e.g., 'EVT-0001') or a filename (e.g., 'EVT-0001.jpg').

        Returns:
            Optional[Path]: Validated Path if file exists on disk, None otherwise.

        Raises:
            ValueError: If path traversal or illegal characters are detected.
        """
        with self._lock:
            filename: Optional[str] = None
            if identifier in self._records:
                filename = (
                    self._records[identifier].get("image_filename")
                    or self._records[identifier].get("evidence_image_filename")
                )
                if not filename:
                    return None
            else:
                filename = identifier

        path = self.validate_filename(filename)
        if path.exists() and path.is_file():
            return path
        return None

    def attach_to_violation_event_service(self, event_service: Any) -> None:
        """
        Registers event lifecycle listeners with a ViolationEventService instance
        to automatically update evidence metadata on event resolution and closure.
        """
        if hasattr(event_service, "register_listener"):
            def _on_resolved(record):
                try:
                    self.update_event_status(
                        event_id=record.event_id,
                        status=record.status,
                        resolution_timestamp=record.resolution_timestamp,
                    )
                except Exception as err:
                    logger.error(f"Error handling evidence on_resolved for {record.event_id}: {err}")

            def _on_closed(record):
                try:
                    self.update_event_status(
                        event_id=record.event_id,
                        status=record.status,
                        closure_timestamp=record.closure_timestamp,
                    )
                except Exception as err:
                    logger.error(f"Error handling evidence on_closed for {record.event_id}: {err}")

            event_service.register_listener(
                on_resolved=_on_resolved,
                on_closed=_on_closed,
            )
            logger.info("EvidenceService successfully attached to ViolationEventService lifecycle.")

    def get_storage_stats(self) -> Dict[str, Any]:
        """Returns storage metrics for the evidence directory."""
        with self._lock:
            total_files = 0
            total_bytes = 0
            image_count = 0
            json_count = 0

            try:
                for p in self.storage_dir.iterdir():
                    if p.is_file():
                        total_files += 1
                        sz = p.stat().st_size
                        total_bytes += sz
                        suffix = p.suffix.lower()
                        if suffix in [".jpg", ".jpeg", ".png"]:
                            image_count += 1
                        elif suffix == ".json":
                            json_count += 1
            except Exception as e:
                logger.warning(f"Error scanning storage dir for stats: {e}")

            import shutil
            try:
                du = shutil.disk_usage(self.storage_dir)
                disk_total_gb = round(du.total / (1024 ** 3), 2)
                disk_used_gb = round(du.used / (1024 ** 3), 2)
                disk_free_gb = round(du.free / (1024 ** 3), 2)
            except Exception:
                disk_total_gb = 0.0
                disk_used_gb = 0.0
                disk_free_gb = 0.0

            return {
                "storage_directory": str(self.storage_dir),
                "total_files": total_files,
                "image_files": image_count,
                "metadata_files": json_count,
                "incident_records_count": len(self._records),
                "total_size_bytes": total_bytes,
                "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                "disk_total_gb": disk_total_gb,
                "disk_used_gb": disk_used_gb,
                "disk_free_gb": disk_free_gb,
                "image_capture_enabled": self.image_capture_enabled,
            }

    def cleanup_expired_evidence(self, retention_days: int) -> Dict[str, Any]:
        """
        Safely removes evidence records and image files older than retention_days.
        If retention_days <= 0, no files are removed.
        """
        if retention_days <= 0:
            return {"removed_count": 0, "freed_bytes": 0, "freed_mb": 0.0, "message": "Retention is set to infinite / 0 days."}

        cutoff_ts = time.time() - (retention_days * 86400)
        removed_count = 0
        freed_bytes = 0

        with self._lock:
            expired_ids = []
            for eid, rec in list(self._records.items()):
                start_ts = rec.get("start_timestamp") or rec.get("first_detected_timestamp")
                if start_ts and float(start_ts) < cutoff_ts:
                    expired_ids.append(eid)
                    img_file = rec.get("image_filename") or rec.get("evidence_image_filename")
                    if img_file:
                        try:
                            fpath = self.storage_dir / str(img_file)
                            if fpath.exists() and fpath.is_file():
                                freed_bytes += fpath.stat().st_size
                                fpath.unlink()
                                removed_count += 1
                        except Exception as e:
                            logger.error(f"Failed to remove expired evidence image {img_file}: {e}")

                    meta_file = self.storage_dir / f"{eid}.json"
                    if meta_file.exists() and meta_file.is_file():
                        try:
                            freed_bytes += meta_file.stat().st_size
                            meta_file.unlink()
                        except Exception:
                            pass

                    self._records.pop(eid, None)
                    self._saved_events.discard(eid)

            if expired_ids:
                try:
                    self._save_metadata()
                except Exception as e:
                    logger.error(f"Failed to persist metadata after cleanup: {e}")

        logger.info(
            f"Evidence cleanup complete: purged {len(expired_ids)} incidents, {removed_count} files, "
            f"freed {freed_bytes / (1024 * 1024):.2f} MB"
        )
        return {
            "removed_count": removed_count,
            "expired_incidents": len(expired_ids),
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "retention_days": retention_days,
        }


# Module singleton instance
_evidence_service_instance: Optional[EvidenceService] = None


def get_evidence_service(storage_dir: Optional[Union[str, Path]] = None) -> EvidenceService:
    """Returns the shared EvidenceService singleton."""
    global _evidence_service_instance
    if _evidence_service_instance is None:
        _evidence_service_instance = EvidenceService(storage_dir=storage_dir)
    return _evidence_service_instance

