import copy
import email
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
import json
import logging
import os
from pathlib import Path
import re
import smtplib
import socket
import ssl
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
for env_candidate in [ROOT_DIR / ".env", BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"]:
    if env_candidate.exists():
        load_dotenv(env_candidate, override=False)

logger = logging.getLogger("ppe_monitoring.email_service")

try:
    from app.services.notification_service import get_notification_service
except ImportError:
    try:
        from services.notification_service import get_notification_service
    except ImportError:
        get_notification_service = None

STORAGE_DIR = BACKEND_DIR / "storage"
STATE_FILE = STORAGE_DIR / "email_state.json"
HISTORY_FILE = STORAGE_DIR / "email_history.json"
EVIDENCE_DIR = STORAGE_DIR / "evidence"

DEFAULT_RECIPIENT = "bhavaneshkadiveti@gmail.com"
DEFAULT_REMINDER_INTERVAL_MINUTES = 5

CORRECTIVE_ACTIONS: Dict[str, str] = {
    "hardhat": "Require worker to immediately don an approved hardhat/safety helmet before remaining in active zone.",
    "safety_vest": "Instruct worker to equip high-visibility safety vest immediately for site visibility compliance.",
    "mask": "Provide respiratory face mask and verify proper facial seal compliance.",
    "gloves": "Provide certified protective work gloves suited for current material handling tasks.",
    "goggles": "Direct worker to wear ANSI Z87.1 safety goggles/eye protection before operating or approaching hazards.",
    "safety_shoes": "Ensure worker is wearing steel-toe protective footwear meeting safety standards.",
}


def is_valid_email(email_str: str) -> bool:
    """Validates an email address format strictly."""
    if not email_str or not isinstance(email_str, str):
        return False
    email_str = email_str.strip()
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email_str))


class EmailService:
    """
    Production-ready Automatic Email Alert & Reminder Service for SafeVision AI.

    Responsibilities:
      - Sends instantaneous First Alert emails upon confirmed 5-second PPE violation.
      - Schedules independent recurring reminder emails (default: every 5 minutes) for each active incident.
      - Immediately cancels future reminders when an incident transitions to RESOLVED or CLOSED.
      - Re-checks incident status immediately before dispatching each reminder.
      - Asynchronously dispatches emails via background worker threads to protect YOLO inference and capture loops.
      - Attaches local evidence JPEG frames if present without attaching video streams.
      - Persists state and complete notification delivery history locally across backend restarts.
      - Supports mock SMTP transport and custom clock for deterministic automated testing.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        state_file: Optional[Union[str, Path]] = None,
        history_file: Optional[Union[str, Path]] = None,
        evidence_dir: Optional[Union[str, Path]] = None,
        time_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self.state_file = Path(state_file).resolve() if state_file else STATE_FILE.resolve()
        self.history_file = Path(history_file).resolve() if history_file else HISTORY_FILE.resolve()
        self.evidence_dir = Path(evidence_dir).resolve() if evidence_dir else EVIDENCE_DIR.resolve()
        self.time_provider = time_provider or time.time

        self._lock = threading.RLock()
        self._scheduler_stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None

        # Configuration dictionary
        env_enabled = os.getenv("EMAIL_ENABLED")
        self._config: Dict[str, Any] = {
            "enabled": env_enabled.lower() in ("true", "1", "t") if env_enabled is not None else False,
            "recipient_email": os.getenv("EMAIL_RECIPIENT", DEFAULT_RECIPIENT),
            "sender_email": os.getenv("SMTP_SENDER_EMAIL", ""),
            "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "smtp_username": os.getenv("SMTP_USERNAME", ""),
            "smtp_password": os.getenv("SMTP_PASSWORD", ""),
            "use_tls": os.getenv("SMTP_USE_TLS", "True").lower() in ("true", "1", "t"),
            "use_ssl": os.getenv("SMTP_USE_SSL", "False").lower() in ("true", "1", "t"),
            "reminder_interval_minutes": int(os.getenv("EMAIL_REMINDER_INTERVAL_MINUTES", str(DEFAULT_REMINDER_INTERVAL_MINUTES))),
        }
        if config:
            self._config.update(config)

        # Harmonize Gmail sender and username if one is populated from env
        host = self._config.get("smtp_host", "").lower()
        if "gmail.com" in host or "googlemail.com" in host:
            u_name = str(self._config.get("smtp_username", "")).strip()
            s_email = str(self._config.get("sender_email", "")).strip()
            if u_name and not s_email:
                self._config["sender_email"] = u_name
            elif s_email and not u_name:
                self._config["smtp_username"] = s_email

        # In-memory tracking of active incident schedules: {incident_id: schedule_dict}
        self._active_schedules: Dict[str, Dict[str, Any]] = {}

        # Thread-safe camera monitoring state tracking
        self._camera_monitoring_active: bool = False
        self._monitoring_session_id: int = 0
        self._monitoring_active_checker: Optional[Callable[[], bool]] = None

        # Delivery statistics
        self._total_sent: int = 0
        self._total_failed: int = 0
        self._last_sent_timestamp: Optional[float] = None
        self._last_delivery_error: Optional[str] = None

        # Delivery history in-memory cache: list of records
        self._history: List[Dict[str, Any]] = []

        # Optional test mock transport: callable(msg, recipient, has_attachment) -> Tuple[bool, str]
        self._mock_transport: Optional[Callable[[MIMEMultipart, str, bool], Tuple[bool, str]]] = None

        # External reference to ViolationEventService for pre-send status rechecking
        self._violation_event_service: Optional[Any] = None

        self._ensure_storage_dir()
        self._load_state()
        self._load_history()
        self.start_scheduler()

    def _now(self) -> float:
        return float(self.time_provider())

    def _ensure_storage_dir(self) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create email storage directory: {e}")

    # -------------------------------------------------------------------------
    # Configuration Management
    # -------------------------------------------------------------------------

    def get_config(self, mask_password: bool = True) -> Dict[str, Any]:
        """Returns the current email settings. Never returns plaintext password when masked."""
        with self._lock:
            cfg = copy.deepcopy(self._config)
            pwd = cfg.get("smtp_password", "")
            cfg["has_password"] = bool(pwd)
            if mask_password:
                cfg["smtp_password"] = "******" if pwd else ""
            return cfg

    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates and validates email settings."""
        with self._lock:
            recipient = updates.get("recipient_email")
            if recipient is not None:
                recipient = str(recipient).strip()
                if not is_valid_email(recipient):
                    raise ValueError(f"Invalid recipient email address format: '{recipient}'")
                self._config["recipient_email"] = recipient

            if "enabled" in updates:
                self._config["enabled"] = bool(updates["enabled"])

            if "sender_email" in updates:
                self._config["sender_email"] = str(updates["sender_email"]).strip()

            if "smtp_host" in updates:
                self._config["smtp_host"] = str(updates["smtp_host"]).strip()

            if "smtp_port" in updates:
                self._config["smtp_port"] = int(updates["smtp_port"])

            if "smtp_username" in updates:
                self._config["smtp_username"] = str(updates["smtp_username"]).strip()

            # Only update password if a non-masked string is provided
            if "smtp_password" in updates:
                pwd = str(updates["smtp_password"]).strip()
                if pwd and pwd != "******":
                    self._config["smtp_password"] = pwd

            if "use_tls" in updates:
                self._config["use_tls"] = bool(updates["use_tls"])

            if "use_ssl" in updates:
                self._config["use_ssl"] = bool(updates["use_ssl"])

            if "reminder_interval_minutes" in updates:
                interval = int(updates["reminder_interval_minutes"])
                if interval < 1 or interval > 1440:
                    raise ValueError("Reminder interval must be between 1 and 1440 minutes.")
                self._config["reminder_interval_minutes"] = interval

            # Dynamic validation and harmonization for Gmail SMTP
            host = self._config.get("smtp_host", "").lower()
            username = self._config.get("smtp_username", "").strip()
            sender = self._config.get("sender_email", "").strip()
            is_gmail = "gmail.com" in host or "googlemail.com" in host

            if is_gmail:
                if username and not sender:
                    self._config["sender_email"] = username
                    sender = username
                elif sender and not username:
                    self._config["smtp_username"] = sender
                    username = sender
                elif username and sender and username.lower() != sender.lower():
                    raise ValueError(
                        f"For Gmail SMTP, the sender address ('{sender}') must match the authenticated SMTP username ('{username}')."
                    )

            logger.info(
                f"EmailService config updated: enabled={self._config['enabled']}, "
                f"host={self._config['smtp_host']}:{self._config['smtp_port']}, "
                f"sender={self.get_configured_sender()}, recipient={self._config['recipient_email']}"
            )
            return self.get_config(mask_password=True)

    def get_configured_sender(self) -> str:
        """
        Dynamically returns the configured sender email address from saved configuration.
        For Gmail SMTP, ensures the sender matches the authenticated SMTP username.
        Never falls back to hardcoded domain addresses like alerts@safevision.ai.
        """
        with self._lock:
            sender = str(self._config.get("sender_email") or "").strip()
            username = str(self._config.get("smtp_username") or "").strip()
            host = str(self._config.get("smtp_host") or "").lower()
            is_gmail = "gmail.com" in host or "googlemail.com" in host

            if is_gmail and username:
                return username
            return sender or username

    def is_configured(self) -> bool:
        """Returns True if minimum SMTP settings are populated."""
        with self._lock:
            sender = self.get_configured_sender()
            return bool(
                self._config.get("smtp_host")
                and self._config.get("recipient_email")
                and is_valid_email(self._config.get("recipient_email", ""))
                and bool(sender)
                and is_valid_email(sender)
            )

    def set_monitoring_active_checker(self, checker: Callable[[], bool]) -> None:
        """Registers a callback from MonitoringController returning True when camera is active."""
        with self._lock:
            self._monitoring_active_checker = checker

    def is_camera_monitoring_active(self) -> bool:
        """
        Thread-safe check verifying whether camera monitoring is actively running.
        Returns False if camera is off, monitoring idle, initializing, or failed.
        """
        with self._lock:
            if self._monitoring_active_checker is not None:
                try:
                    if not self._monitoring_active_checker():
                        return False
                except Exception as e:
                    logger.debug(f"Error checking monitoring controller state: {e}")
                    return False
            return bool(self._camera_monitoring_active)

    def set_camera_monitoring_active(self, active: bool, reason: str = "") -> None:
        """
        Signals transition in camera monitoring operational state.
        When active=True: enables automatic email notifications for fresh camera frames.
        When active=False: immediately stops automatic emails, cancels pending reminder schedules,
        and invalidates in-flight background worker threads via session counter.
        """
        with self._lock:
            if active:
                self._camera_monitoring_active = True
                self._monitoring_session_id += 1
                self._active_schedules.clear()
                self._save_state()
                logger.info(
                    f"EmailService: Camera monitoring is now ACTIVE (Session #{self._monitoring_session_id}). "
                    f"Automatic email alert engine enabled."
                )
            else:
                self._camera_monitoring_active = False
                self._monitoring_session_id += 1  # Invalidate in-flight background worker threads
                for sch in self._active_schedules.values():
                    sch["status"] = "interrupted"
                    sch["resolved"] = True
                    sch["next_reminder_timestamp"] = None
                    sch["interruption_reason"] = reason
                self._active_schedules.clear()
                self._save_state()
                logger.info(
                    f"EmailService: Camera monitoring STOPPED ({reason}). "
                    f"All automatic email reminder schedules cancelled and queued emails suppressed."
                )

    # -------------------------------------------------------------------------
    # State & History Persistence Across Restarts
    # -------------------------------------------------------------------------

    def _save_state(self) -> None:
        """Persists active incident schedules locally to handle restart recovery."""
        try:
            payload = {
                "active_schedules": self._active_schedules,
                "total_sent": self._total_sent,
                "total_failed": self._total_failed,
                "last_sent_timestamp": self._last_sent_timestamp,
                "last_delivery_error": self._last_delivery_error,
            }
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.state_file)
        except Exception as e:
            logger.error(f"Failed to persist email notification state: {e}")

    def _load_state(self) -> None:
        """Loads persisted state on startup. Never restores active reminder schedules while camera is idle."""
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # Stale schedules from previous run must NOT be restored as active while camera is off
                self._active_schedules = {}
                self._total_sent = int(data.get("total_sent", 0))
                self._total_failed = int(data.get("total_failed", 0))
                self._last_sent_timestamp = data.get("last_sent_timestamp")
                self._last_delivery_error = data.get("last_delivery_error")
                logger.info(
                    f"EmailService restored state: {self._total_sent} previously sent emails. "
                    f"Active reminder schedules reset (camera is off/idle)."
                )
        except Exception as e:
            logger.warning(f"Error loading email state file: {e}")

    def _save_history(self) -> None:
        """Persists notification history entries locally."""
        try:
            tmp = self.history_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._history, indent=2), encoding="utf-8")
            tmp.replace(self.history_file)
        except Exception as e:
            logger.error(f"Failed to persist email history: {e}")

    def _load_history(self) -> None:
        """Loads historical notification delivery records."""
        if not self.history_file.exists():
            return
        try:
            data = json.loads(self.history_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._history = data
        except Exception as e:
            logger.warning(f"Error loading email history file: {e}")

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns notification delivery history (most recent first)."""
        with self._lock:
            # Return reversed list for newest first
            return list(reversed(self._history[-limit:]))

    def get_incident_history(self, incident_id: str) -> List[Dict[str, Any]]:
        """Returns history records for a specific incident."""
        with self._lock:
            return [h for h in self._history if h.get("incident_id") == str(incident_id)]

    def get_status(self) -> Dict[str, Any]:
        """Returns current operational status, counters, and active schedules."""
        with self._lock:
            active_list = []
            for iid, sch in self._active_schedules.items():
                if sch.get("status") in ("open", "ongoing") and not sch.get("resolved"):
                    cats = sch.get("ppe_categories")
                    if not cats:
                        raw_c = sch.get("ppe_category", "")
                        cats = [c.strip() for c in str(raw_c).split(",") if c.strip()] if "," in str(raw_c) else [str(raw_c)]
                    active_list.append({
                        "incident_id": iid,
                        "worker_track_id": sch.get("worker_track_id"),
                        "ppe_categories": cats,
                        "ppe_category": sch.get("ppe_category", ", ".join(cats)),
                        "severity": sch.get("severity"),
                        "status": sch.get("status"),
                        "first_alert_sent": sch.get("first_alert_sent"),
                        "reminder_count": sch.get("reminder_count", 0),
                        "next_reminder_timestamp": sch.get("next_reminder_timestamp"),
                    })

            return {
                "enabled": bool(self._config.get("enabled")),
                "smtp_configured": self.is_configured(),
                "recipient_email": self._config.get("recipient_email", DEFAULT_RECIPIENT),
                "reminder_interval_minutes": self._config.get("reminder_interval_minutes", 5),
                "total_emails_sent": self._total_sent,
                "failed_email_count": self._total_failed,
                "last_sent_timestamp": self._last_sent_timestamp,
                "last_delivery_error": self._last_delivery_error,
                "active_incident_schedules_count": len(active_list),
                "active_incident_schedules": active_list,
            }

    # -------------------------------------------------------------------------
    # Lifecycle Integration with ViolationEventService
    # -------------------------------------------------------------------------

    def attach_to_violation_event_service(self, event_service: Any) -> None:
        """
        Subscribes to ViolationEventService lifecycle callbacks:
          - on_created: confirmed 5-second violation -> send consolidated First Alert immediately.
          - on_updated: additional/changed violations detected -> update violation list without immediate duplicate email.
          - on_resolved: violation fixed -> cancel all future reminders immediately.
          - on_closed: incident closed -> cancel reminders immediately.
        """
        self._violation_event_service = event_service
        if hasattr(event_service, "register_listener"):
            event_service.register_listener(
                on_created=self.on_incident_confirmed,
                on_updated=self.on_incident_updated,
                on_resolved=self.on_incident_resolved,
                on_closed=self.on_incident_closed,
            )
            logger.info("EmailService attached successfully to ViolationEventService lifecycle.")

    def on_incident_confirmed(self, event: Any) -> None:
        """
        Invoked when a continuous violation exceeds the 5-second threshold
        and becomes a confirmed violation event.
        Immediately dispatches exactly ONE consolidated First Alert email containing all detected PPE violations.
        Suppresses transmission if camera monitoring is inactive.
        """
        if not self.is_camera_monitoring_active():
            logger.debug("Received incident confirmation while camera monitoring is inactive; suppressing automatic First Alert.")
            return

        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        incident_id = str(event_dict.get("event_id", ""))
        if not incident_id:
            return

        with self._lock:
            # Deduplicate: if schedule already exists and first alert was sent, do not resend
            existing = self._active_schedules.get(incident_id)
            if existing and existing.get("first_alert_sent"):
                logger.debug(f"First alert for incident {incident_id} already dispatched; skipping duplicate.")
                return

            # Check history: if First Alert was already sent for this incident, avoid duplicate dispatch
            if any(h.get("incident_id") == incident_id and h.get("email_type") == "First Alert" for h in self._history):
                logger.debug(f"First alert for incident {incident_id} already recorded in delivery history; skipping duplicate.")
                return

            now = self._now()
            interval_sec = self._config.get("reminder_interval_minutes", 5) * 60.0

            cats = event_dict.get("ppe_categories")
            if not cats:
                raw_c = event_dict.get("ppe_category", "unknown")
                cats = [c.strip() for c in str(raw_c).split(",") if c.strip()] if "," in str(raw_c) else [str(raw_c)]

            # Register schedule
            self._active_schedules[incident_id] = {
                "incident_id": incident_id,
                "worker_track_id": event_dict.get("worker_track_id", 0),
                "ppe_categories": cats,
                "ppe_category": str(event_dict.get("ppe_category") or ", ".join(cats)),
                "severity": str(event_dict.get("severity", "critical")),
                "status": str(event_dict.get("status", "open")),
                "start_timestamp": float(event_dict.get("start_timestamp", now)),
                "confirmation_timestamp": float(event_dict.get("confirmation_timestamp", now)),
                "first_alert_sent": True,
                "first_alert_timestamp": now,
                "reminder_count": 0,
                "last_reminder_timestamp": None,
                "next_reminder_timestamp": now + interval_sec,
                "resolved": False,
            }
            self._save_state()
            curr_session = self._monitoring_session_id

        logger.info(f"Triggering consolidated First Alert email for confirmed incident {incident_id} ({cats})...")
        self._dispatch_email_async(
            email_type="First Alert",
            incident_data=dict(self._active_schedules[incident_id]),
            reminder_number=0,
            session_id=curr_session,
        )

    def on_incident_updated(self, event: Any) -> None:
        """
        Invoked when additional or changed PPE violations are detected on an active incident.
        Updates the existing schedule's violation list and severity without sending an immediate email.
        """
        if not self.is_camera_monitoring_active():
            return
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        incident_id = str(event_dict.get("event_id", ""))
        if not incident_id:
            return

        with self._lock:
            sch = self._active_schedules.get(incident_id)
            if sch and not sch.get("resolved") and sch.get("status") not in ("resolved", "closed"):
                cats = event_dict.get("ppe_categories")
                if not cats:
                    raw_c = event_dict.get("ppe_category", "")
                    cats = [c.strip() for c in str(raw_c).split(",") if c.strip()] if "," in str(raw_c) else [str(raw_c)]
                sch["ppe_categories"] = cats
                sch["ppe_category"] = str(event_dict.get("ppe_category") or ", ".join(cats))
                sch["severity"] = str(event_dict.get("severity", sch.get("severity", "critical")))
                sch["status"] = str(event_dict.get("status", "ongoing"))
                self._save_state()
                logger.info(
                    f"EmailService: Incident {incident_id} updated with categories {cats}. "
                    f"Will be included in next reminder without immediate duplicate email."
                )

    def on_incident_resolved(self, event: Any) -> None:
        """
        Invoked when a worker corrects their PPE and the violation ends.
        Cancels all future reminders immediately.
        """
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        incident_id = str(event_dict.get("event_id", ""))
        if not incident_id:
            return

        with self._lock:
            sch = self._active_schedules.get(incident_id)
            if sch:
                sch["status"] = "resolved"
                sch["resolved"] = True
                sch["next_reminder_timestamp"] = None
                self._save_state()
                logger.info(f"Incident {incident_id} resolved: cancelled all future email reminders.")

    def on_incident_closed(self, event: Any) -> None:
        """Invoked when an incident is audited or closed."""
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        incident_id = str(event_dict.get("event_id", ""))
        if not incident_id:
            return

        with self._lock:
            sch = self._active_schedules.get(incident_id)
            if sch:
                sch["status"] = "closed"
                sch["resolved"] = True
                sch["next_reminder_timestamp"] = None
                self._save_state()
                logger.info(f"Incident {incident_id} closed: cancelled all future email reminders.")

    # -------------------------------------------------------------------------
    # Background Scheduler for Reminders
    # -------------------------------------------------------------------------

    def start_scheduler(self) -> None:
        """Starts the detached background scheduler thread."""
        with self._lock:
            if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
                return
            self._scheduler_stop_event.clear()
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="SafeVision-EmailScheduler",
                daemon=True,
            )
            self._scheduler_thread.start()
            logger.info("Email notification reminder scheduler thread started.")

    def stop_scheduler(self, timeout: float = 3.0) -> None:
        """Stops the scheduler thread cleanly."""
        self._scheduler_stop_event.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=timeout)
        self._scheduler_thread = None

    def _scheduler_loop(self) -> None:
        """Periodic background check for due reminders."""
        while not self._scheduler_stop_event.is_set():
            try:
                self.check_due_reminders()
            except Exception as e:
                logger.error(f"Error in email reminder scheduler loop: {e}", exc_info=True)
            self._scheduler_stop_event.wait(3.0)

    def check_due_reminders(self) -> List[str]:
        """
        Evaluates all active incidents and dispatches reminders for those due.
        Rechecks incident status from ViolationEventService immediately before sending.
        Suppresses reminders if camera monitoring is currently inactive.
        Returns list of incident IDs for which reminders were dispatched.
        """
        if not self.is_camera_monitoring_active():
            return []

        now = self._now()
        due_dispatches: List[Tuple[str, Dict[str, Any], int]] = []

        with self._lock:
            if not self._config.get("enabled"):
                return []

            curr_session = self._monitoring_session_id
            interval_sec = self._config.get("reminder_interval_minutes", 5) * 60.0

            for iid, sch in list(self._active_schedules.items()):
                # Only active, unresolved incidents receive reminders
                if sch.get("resolved") or sch.get("status") in ("resolved", "closed"):
                    continue

                next_ts = sch.get("next_reminder_timestamp")
                if next_ts is not None and now >= next_ts:
                    # Pre-send check: verify status with ViolationEventService if attached
                    if self._violation_event_service:
                        try:
                            live_rec = self._violation_event_service.get_event(iid)
                            if live_rec:
                                live_status = live_rec.get("status") if isinstance(live_rec, dict) else getattr(live_rec, "status", None)
                                if live_status in ("resolved", "closed"):
                                    sch["status"] = live_status
                                    sch["resolved"] = True
                                    sch["next_reminder_timestamp"] = None
                                    continue

                                # Update schedule with current categories and severity
                                live_cats = live_rec.get("ppe_categories")
                                if live_cats:
                                    sch["ppe_categories"] = live_cats
                                live_cat = live_rec.get("ppe_category")
                                if live_cat:
                                    sch["ppe_category"] = live_cat
                                live_sev = live_rec.get("severity")
                                if live_sev:
                                    sch["severity"] = live_sev
                                sch["status"] = live_status
                        except Exception as e:
                            logger.warning(f"Could not re-verify event status for {iid}: {e}")

                    # Advance schedule
                    rem_num = int(sch.get("reminder_count", 0)) + 1
                    sch["reminder_count"] = rem_num
                    sch["last_reminder_timestamp"] = now
                    sch["next_reminder_timestamp"] = now + interval_sec

                    # Clone data for sending
                    incident_data = dict(sch)
                    due_dispatches.append((iid, incident_data, rem_num))

            if due_dispatches:
                self._save_state()

        dispatched_ids = []
        for iid, inc_data, rem_num in due_dispatches:
            logger.info(f"Dispatching Reminder #{rem_num} for active incident {iid}...")
            self._dispatch_email_async(
                email_type="Reminder Alert",
                incident_data=inc_data,
                reminder_number=rem_num,
                session_id=curr_session,
            )
            dispatched_ids.append(iid)

        return dispatched_ids

    # -------------------------------------------------------------------------
    # Email Construction & Dispatch
    # -------------------------------------------------------------------------

    def _dispatch_email_async(
        self,
        email_type: str,
        incident_data: Dict[str, Any],
        reminder_number: int = 0,
        session_id: Optional[int] = None,
    ) -> None:
        """Asynchronously dispatches an email via a detached thread."""
        curr_session = session_id if session_id is not None else self._monitoring_session_id
        thread = threading.Thread(
            target=self._send_worker,
            args=(email_type, incident_data, reminder_number, curr_session),
            name=f"SafeVision-EmailWorker-{incident_data.get('incident_id', 'Test')}",
            daemon=True,
        )
        thread.start()

    def _send_worker(
        self,
        email_type: str,
        incident_data: Dict[str, Any],
        reminder_number: int = 0,
        session_id: Optional[int] = None,
    ) -> bool:
        """Worker thread executing SMTP transmission with bounded retries."""
        # 1. Check monitoring state before preparing email
        if email_type != "Test Email":
            with self._lock:
                if not self.is_camera_monitoring_active() or (session_id is not None and session_id != self._monitoring_session_id):
                    logger.info(
                        f"Camera monitoring is inactive or session changed (worker session: {session_id}, current: {self._monitoring_session_id}); "
                        f"cancelling automatic {email_type} email for {incident_data.get('incident_id')}."
                    )
                    return False

        with self._lock:
            enabled = bool(self._config.get("enabled"))
            recipient = str(self._config.get("recipient_email", DEFAULT_RECIPIENT)).strip()
            sender = self.get_configured_sender()

        # If email notifications are disabled globally (except explicit manual test emails)
        if not enabled and email_type != "Test Email":
            logger.info(f"Email notifications are currently disabled; skipped sending {email_type}.")
            return False

        cats = incident_data.get("ppe_categories")
        if not cats:
            raw_c = incident_data.get("ppe_category", "N/A")
            cats = [c.strip() for c in str(raw_c).split(",") if c.strip()] if "," in str(raw_c) else [str(raw_c)]
        violation_type = str(incident_data.get("ppe_category") or ", ".join(cats))

        if not is_valid_email(recipient):
            err_msg = f"Invalid recipient email address: '{recipient}'"
            logger.error(err_msg)
            self._record_history(
                email_type=email_type,
                incident_id=str(incident_data.get("incident_id") or incident_data.get("event_id") or "N/A"),
                worker_id=incident_data.get("worker_track_id"),
                violation_type=violation_type,
                recipient=recipient,
                reminder_number=reminder_number,
                status="failed",
                error=err_msg,
                ppe_categories=cats,
            )
            return False

        if not sender or not is_valid_email(sender):
            err_msg = f"No valid SMTP sender email configured (got: '{sender}'). Please configure your sender email in Settings."
            logger.error(err_msg)
            self._record_history(
                email_type=email_type,
                incident_id=str(incident_data.get("incident_id") or incident_data.get("event_id") or "N/A"),
                worker_id=incident_data.get("worker_track_id"),
                violation_type=violation_type,
                recipient=recipient,
                reminder_number=reminder_number,
                status="failed",
                error=err_msg,
                ppe_categories=cats,
            )
            return False

        # Build email message
        msg, has_attachment = self.build_email_message(
            email_type=email_type,
            incident_data=incident_data,
            recipient=recipient,
            sender=sender,
            reminder_number=reminder_number,
        )

        # 2. Re-check monitoring state immediately before transmission to prevent race conditions
        if email_type != "Test Email":
            with self._lock:
                if not self.is_camera_monitoring_active() or (session_id is not None and session_id != self._monitoring_session_id):
                    logger.info(
                        f"Monitoring stopped immediately before SMTP transmission; aborting {email_type} email for {incident_data.get('incident_id')}."
                    )
                    return False

        # Transmission with retry: explicitly pass sender as envelope sender
        success, error_str = self._transmit_with_retry(msg, recipient, sender=sender, has_attachment=has_attachment)

        # Record result
        self._record_history(
            email_type=email_type,
            incident_id=str(incident_data.get("incident_id") or incident_data.get("event_id") or "N/A"),
            worker_id=incident_data.get("worker_track_id"),
            violation_type=violation_type,
            recipient=recipient,
            reminder_number=reminder_number,
            status="delivered" if success else "failed",
            error=None if success else error_str,
            ppe_categories=cats,
        )

        # Broadcast notification event
        if get_notification_service:
            try:
                notif_svc = get_notification_service()
                if notif_svc:
                    iid = str(incident_data.get("incident_id") or incident_data.get("event_id") or "N/A")
                    w_id = incident_data.get("worker_track_id")
                    if success:
                        notif_svc.create_notification(
                            event_type="email_delivered",
                            category="email",
                            title=f"Email Alert Delivered: {email_type}",
                            description=f"{email_type} accepted by SMTP for {recipient} (Incident: {iid})",
                            severity="info",
                            worker_id=w_id,
                            incident_id=iid,
                            destination="/settings",
                        )
                    else:
                        notif_svc.create_notification(
                            event_type="email_failed",
                            category="email",
                            title=f"Email Alert Delivery Failed: {email_type}",
                            description=f"Transmission failed for {recipient} (Incident: {iid})",
                            severity="high",
                            worker_id=w_id,
                            incident_id=iid,
                            destination="/settings",
                        )
            except Exception as n_err:
                logger.debug(f"Error creating notification for email result: {n_err}")

        return success

    def build_email_message(
        self,
        email_type: str,
        incident_data: Dict[str, Any],
        recipient: str,
        sender: str,
        reminder_number: int = 0,
    ) -> Tuple[MIMEMultipart, bool]:
        """Constructs a professional HTML and plain-text MIME email with optional evidence attachment."""
        incident_id = str(incident_data.get("incident_id") or incident_data.get("event_id") or "EVT-TEST")
        worker_id = incident_data.get("worker_track_id")
        worker_label = f"Worker #{worker_id}" if worker_id is not None and worker_id > 0 else "Unassigned / General"
        
        raw_cats = incident_data.get("ppe_categories")
        if not raw_cats:
            raw_p = str(incident_data.get("ppe_category", "PPE Hazard"))
            if "," in raw_p:
                raw_cats = [c.strip() for c in raw_p.split(",") if c.strip()]
            else:
                raw_cats = [raw_p]
        ppe_categories = [str(c).strip() for c in raw_cats if str(c).strip()]
        if not ppe_categories:
            ppe_categories = ["PPE Hazard"]

        ppe_category_display = ", ".join([c.replace("_", " ").title() for c in ppe_categories])
        ppe_category = ppe_category_display
        severity = str(incident_data.get("severity", "Critical")).upper()
        status_str = str(incident_data.get("status", "OPEN")).upper()

        start_ts = incident_data.get("start_timestamp") or incident_data.get("first_detected_timestamp") or self._now()
        dt_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(start_ts)))
        now_ts = self._now()
        duration_sec = max(0, round(float(now_ts) - float(start_ts), 1))
        duration_str = f"{int(duration_sec // 60)}m {int(duration_sec % 60)}s" if duration_sec >= 60 else f"{duration_sec:.1f}s"

        if email_type == "First Alert":
            subject = f"SafeVision AI - New PPE Violation Detected [{incident_id}]"
            badge_title = "NEW PPE VIOLATION DETECTED"
            badge_color = "#dc2626"  # Red
            if len(ppe_categories) > 1:
                intro_p = f"Multiple mandatory industrial PPE compliance violations ({len(ppe_categories)} items) were detected and confirmed continuous for over 5 seconds at <b>{dt_str}</b>."
            else:
                intro_p = f"A mandatory industrial PPE compliance violation was detected and confirmed continuous for over 5 seconds at <b>{dt_str}</b>."
        elif email_type == "Reminder Alert":
            subject = f"SafeVision AI - Ongoing PPE Violation Reminder #{reminder_number} [{incident_id}]"
            badge_title = f"ONGOING PPE VIOLATION REMINDER #{reminder_number}"
            badge_color = "#ea580c"  # Orange
            if len(ppe_categories) > 1:
                intro_p = f"The following {len(ppe_categories)} PPE compliance violations remain <b>unresolved</b>. Total ongoing duration: <b>{duration_str}</b>."
            else:
                intro_p = f"The following PPE compliance violation remains <b>unresolved</b>. Total ongoing duration: <b>{duration_str}</b>."
        else:
            subject = "SafeVision AI - Email Alert System Test"
            badge_title = "SYSTEM TEST ALERT"
            badge_color = "#2563eb"  # Blue
            intro_p = "This is a verified test email sent from your SafeVision AI Safety Monitoring System. Email notifications are operational."

        # Plain-text fallback listing all violations and corrective actions
        action_lines = []
        for cat in ppe_categories:
            c_name = cat.replace("_", " ").title()
            c_act = CORRECTIVE_ACTIONS.get(
                cat.lower(),
                "Require worker to immediately don approved personal protective equipment before remaining in active zone.",
            )
            action_lines.append(f"  - {c_name}: {c_act}")
        actions_text_block = "\n".join(action_lines)

        text_body = (
            f"=== {badge_title} ===\n\n"
            f"Incident ID: {incident_id}\n"
            f"Worker: {worker_label}\n"
            f"Missing PPE Categories ({len(ppe_categories)}): {ppe_category_display}\n"
            f"Overall Severity: {severity}\n"
            f"Incident Status: {status_str}\n"
            f"Detection Timestamp: {dt_str}\n"
            f"Current Violation Duration: {duration_str}\n\n"
            f"Required Corrective Actions:\n{actions_text_block}\n\n"
            f"SafeVision AI Industrial Safety Monitoring System\n"
        )

        # HTML template listing all violations in styled cards
        action_boxes_html = ""
        for cat in ppe_categories:
            c_name = cat.replace("_", " ").title()
            c_act = CORRECTIVE_ACTIONS.get(
                cat.lower(),
                "Require worker to immediately don approved personal protective equipment before remaining in active zone.",
            )
            action_boxes_html += f"""
            <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 10px 14px; border-radius: 4px; margin-bottom: 8px;">
              <div style="font-weight: 700; color: #991b1b; font-size: 13px;">&bull; {c_name}</div>
              <div style="font-size: 12px; color: #7f1d1d; margin-top: 2px; line-height: 1.4;">{c_act}</div>
            </div>"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
    .container {{ max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 14px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
    .header {{ background: #0f172a; padding: 22px 28px; text-align: left; }}
    .header h1 {{ color: #ffffff; font-size: 20px; margin: 0; font-weight: 700; letter-spacing: -0.3px; }}
    .header p {{ color: #94a3b8; font-size: 12px; margin: 4px 0 0 0; }}
    .badge {{ display: inline-block; background-color: {badge_color}; color: #ffffff; font-size: 11px; font-weight: 700; padding: 5px 12px; border-radius: 6px; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 12px; }}
    .content {{ padding: 28px; }}
    .intro {{ font-size: 14px; line-height: 1.6; color: #334155; margin-bottom: 20px; }}
    .table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 13px; }}
    .table td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }}
    .table td.label {{ color: #64748b; font-weight: 600; width: 38%; }}
    .table td.value {{ color: #0f172a; font-weight: 600; }}
    .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 28px; font-size: 11px; color: #94a3b8; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>SafeVision AI</h1>
      <p>Real-Time Industrial Safety & PPE Monitoring System</p>
    </div>
    <div class="content">
      <div class="badge">{badge_title}</div>
      <p class="intro">{intro_p}</p>

      <table class="table">
        <tr><td class="label">Incident ID</td><td class="value"><code>{incident_id}</code></td></tr>
        <tr><td class="label">Tracked Worker</td><td class="value">{worker_label}</td></tr>
        <tr><td class="label">Missing PPE ({len(ppe_categories)})</td><td class="value"><span style="color: {badge_color};">{ppe_category_display}</span></td></tr>
        <tr><td class="label">Severity Level</td><td class="value">{severity}</td></tr>
        <tr><td class="label">Incident Status</td><td class="value"><span style="text-transform: uppercase;">{status_str}</span></td></tr>
        <tr><td class="label">First Detected At</td><td class="value">{dt_str}</td></tr>
        <tr><td class="label">Violation Duration</td><td class="value">{duration_str}</td></tr>
      </table>

      <div style="margin-bottom: 22px;">
        <h4 style="margin: 0 0 10px 0; font-size: 12px; color: #475569; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
          Detected Violations &amp; Required Actions
        </h4>
        {action_boxes_html}
      </div>

      <p style="font-size: 11px; color: #64748b; margin-top: 20px;">
        Evidence frame attached if captured. Reminders will repeat every 5 minutes until worker PPE compliance is verified.
      </p>
    </div>
    <div class="footer">
      SafeVision AI Automated Notification Service &bull; Do not reply directly to this automated email.
    </div>
  </div>
</body>
</html>"""

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        msg["Date"] = email.utils.formatdate(localtime=True)

        # Alternative body (text + html)
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
        alt_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt_part)

        # Attach local evidence image if available
        has_attachment = False
        clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", incident_id)
        candidates = [
            self.evidence_dir / f"{clean_id}.jpg",
            self.evidence_dir / f"{clean_id.replace('-', '_')}.jpg",
            self.evidence_dir / f"{clean_id.replace('_', '-')}.jpg",
            self.evidence_dir / f"{clean_id}.jpeg",
        ]
        evidence_file = next((c for c in candidates if c.exists() and c.is_file()), None)
        if evidence_file is not None:
            try:
                img_data = evidence_file.read_bytes()
                if img_data:
                    subtype = "png" if evidence_file.suffix.lower() == ".png" else "jpeg"
                    try:
                        img_part = MIMEImage(img_data, _subtype=subtype)
                    except Exception:
                        img_part = MIMEImage(img_data)
                    img_part.add_header("Content-Disposition", "attachment", filename=evidence_file.name)
                    msg.attach(img_part)
                    has_attachment = True
                    logger.debug(f"Attached evidence frame {evidence_file.name} to email {incident_id}")
            except Exception as att_err:
                logger.warning(f"Failed to attach evidence file {evidence_file}: {att_err}")

        return msg, has_attachment

    def _transmit_with_retry(
        self,
        msg: MIMEMultipart,
        recipient: str,
        sender: Optional[str] = None,
        has_attachment: bool = False,
        max_retries: int = 2,
    ) -> Tuple[bool, Optional[str]]:
        """Sends the message via SMTP or mock transport with bounded retries."""
        # 1. Check if mock transport is registered (used in automated unit tests)
        if self._mock_transport is not None:
            try:
                success, err = self._mock_transport(msg, recipient, has_attachment)
                return success, err
            except Exception as me:
                return False, str(me)

        # 2. Real SMTP transmission
        with self._lock:
            host = self._config.get("smtp_host", "")
            port = int(self._config.get("smtp_port", 587))
            username = self._config.get("smtp_username", "")
            password = self._config.get("smtp_password", "")
            use_tls = bool(self._config.get("use_tls", True))
            use_ssl = bool(self._config.get("use_ssl", False))
            envelope_sender = str(sender or self.get_configured_sender() or msg.get("From") or "").strip()

        if not host:
            err = "SMTP host is not configured."
            logger.warning(err)
            return False, err

        if not envelope_sender or not is_valid_email(envelope_sender):
            err = f"Invalid or missing envelope sender address: '{envelope_sender}'"
            logger.error(err)
            return False, err

        last_error = "Unknown error"
        for attempt in range(1, max_retries + 1):
            server = None
            try:
                logger.info(f"Connecting to SMTP {host}:{port} with envelope sender={envelope_sender} (attempt {attempt}/{max_retries})...")
                if use_ssl or port == 465:
                    context = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(host, port, context=context, timeout=15)
                    server.ehlo()
                else:
                    server = smtplib.SMTP(host, port, timeout=15)
                    server.ehlo()
                    if use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()

                if username and password:
                    server.login(username, password)

                server.send_message(msg, from_addr=envelope_sender, to_addrs=[recipient])
                logger.info(f"Email successfully delivered to {recipient} via {host} from {envelope_sender} (attempt {attempt}).")
                return True, None

            except smtplib.SMTPAuthenticationError as auth_err:
                err_text = auth_err.smtp_error.decode("utf-8", errors="replace") if isinstance(auth_err.smtp_error, bytes) else str(auth_err)
                last_error = f"SMTP Authentication failed for '{username}': {err_text}"
                logger.error(last_error)
                break
            except smtplib.SMTPSenderRefused as send_err:
                err_text = send_err.smtp_error.decode("utf-8", errors="replace") if isinstance(send_err.smtp_error, bytes) else str(send_err)
                last_error = f"SMTP Sender refused ('{envelope_sender}'): {err_text}"
                logger.error(last_error)
                break
            except (smtplib.SMTPException, socket.error, TimeoutError, OSError) as e:
                last_error = f"SMTP transmission error: {type(e).__name__}: {str(e)}"
                logger.warning(f"SMTP delivery failed on attempt {attempt}/{max_retries}: {last_error}")
                if attempt < max_retries:
                    time.sleep(1.0)
            except Exception as e:
                last_error = f"Unexpected delivery error: {str(e)}"
                logger.error(last_error, exc_info=True)
                break
            finally:
                if server is not None:
                    try:
                        server.quit()
                    except Exception:
                        pass

        return False, last_error

    def _record_history(
        self,
        email_type: str,
        incident_id: str,
        worker_id: Optional[int],
        violation_type: str,
        recipient: str,
        reminder_number: int,
        status: str,
        error: Optional[str] = None,
        ppe_categories: Optional[List[str]] = None,
    ) -> None:
        """Appends notification record to in-memory history and updates counters."""
        now = self._now()
        record = {
            "id": f"EML-{int(now * 1000)}",
            "timestamp": now,
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "email_type": email_type,
            "incident_id": incident_id,
            "worker_id": worker_id,
            "violation_type": violation_type,
            "ppe_categories": ppe_categories or [violation_type],
            "recipient": recipient,
            "reminder_number": reminder_number,
            "status": status,
            "error": error,
        }

        with self._lock:
            self._history.append(record)
            if status == "delivered":
                self._total_sent += 1
                self._last_sent_timestamp = now
            else:
                self._total_failed += 1
                self._last_delivery_error = error

            # Keep in-memory history bounded to last 500 records
            if len(self._history) > 500:
                self._history = self._history[-500:]

            self._save_state()
            self._save_history()

    # -------------------------------------------------------------------------
    # Test Email Dispatch
    # -------------------------------------------------------------------------

    def send_test_email(self, custom_recipient: Optional[str] = None) -> Tuple[bool, str]:
        """
        Sends an immediate test email to verify SMTP configuration and recipient reachability.
        Operates completely independently of camera monitoring.
        """
        with self._lock:
            target_recipient = str(custom_recipient or self._config.get("recipient_email", DEFAULT_RECIPIENT)).strip()
            sender = self.get_configured_sender()

        if not is_valid_email(target_recipient):
            return False, f"Invalid recipient email address: '{target_recipient}'"

        if not sender or not is_valid_email(sender):
            return False, f"Cannot send test email: no valid SMTP sender email configured. Please configure your email in Settings."

        test_data = {
            "incident_id": "EVT-TEST",
            "worker_track_id": 1,
            "ppe_category": "Safety Helmet",
            "severity": "Test",
            "status": "Test Mode",
            "start_timestamp": self._now(),
        }

        success = self._send_worker(
            email_type="Test Email",
            incident_data=test_data,
            reminder_number=0,
        )

        with self._lock:
            err = self._last_delivery_error

        if success:
            return True, f"Test email successfully sent to {target_recipient} from {sender}."
        else:
            return False, f"Failed to send test email: {err or 'Unknown transmission error'}"

    # -------------------------------------------------------------------------
    # Test Mock Transport & Reset Helpers
    # -------------------------------------------------------------------------

    def set_mock_transport(
        self,
        transport_fn: Optional[Callable[[MIMEMultipart, str, bool], Tuple[bool, str]]],
    ) -> None:
        """Sets a mock transport callable for automated testing."""
        self._mock_transport = transport_fn

    def reset_for_test(self) -> None:
        """Resets active schedules and history in-memory for unit tests."""
        with self._lock:
            self._active_schedules.clear()
            self._history.clear()
            self._total_sent = 0
            self._total_failed = 0
            self._last_sent_timestamp = None
            self._last_delivery_error = None


# Module singleton instance
_email_service_instance: Optional[EmailService] = None


def get_email_service(config: Optional[Dict[str, Any]] = None) -> EmailService:
    """Returns the shared EmailService singleton."""
    global _email_service_instance
    if _email_service_instance is None:
        _email_service_instance = EmailService(config=config)
    elif config:
        _email_service_instance.update_config(config)
    return _email_service_instance
