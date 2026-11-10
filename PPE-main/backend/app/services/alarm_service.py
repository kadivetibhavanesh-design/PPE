import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("ppe_monitoring.alarm_service")

# Status constants
STATUS_TRIGGERED = "triggered"
STATUS_COOLING_DOWN = "cooling_down"
STATUS_STOPPED = "stopped"


@dataclass
class AlarmRecord:
    """
    In-memory record tracking an active or cooling-down alarm for a specific
    (worker_track_id, ppe_category) violation.
    """
    worker_track_id: int
    ppe_category: str
    status: str
    first_triggered_timestamp: float
    last_triggered_timestamp: float
    trigger_count: int = 1
    cooldown_seconds: float = 10.0

    def is_in_cooldown(self, current_time: float) -> bool:
        """Returns True if the alarm was triggered recently and cooldown has not expired."""
        return (current_time - self.last_triggered_timestamp) < self.cooldown_seconds

    def remaining_cooldown(self, current_time: float) -> float:
        """Returns remaining cooldown seconds before this alarm can trigger sound again."""
        elapsed = current_time - self.last_triggered_timestamp
        return max(0.0, round(self.cooldown_seconds - elapsed, 3))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes alarm record to a JSON-serializable dictionary."""
        return {
            "worker_track_id": self.worker_track_id,
            "ppe_category": self.ppe_category,
            "status": self.status,
            "trigger_count": self.trigger_count,
            "first_triggered_timestamp": round(self.first_triggered_timestamp, 3),
            "last_triggered_timestamp": round(self.last_triggered_timestamp, 3),
            "cooldown_seconds": round(self.cooldown_seconds, 3),
        }


class AlarmService:
    """
    PPE Violation Alarm Service.
    Activates local sound alerts when a worker's PPE violation becomes alarm-eligible.
    Prevents repeated alarm spam per frame using independent per-violation cooldowns.
    """

    def __init__(
        self,
        cooldown_seconds: float = 10.0,
        sound_enabled: bool = True,
        sound_file_path: Optional[str] = None,
        sound_duration_ms: int = 400,
        sound_frequency_hz: int = 1000,
        sound_player: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        """
        Initializes the AlarmService.

        Args:
            cooldown_seconds: Cooldown in seconds before an ongoing continuous violation
                              can trigger sound again (default: 10.0s).
            sound_enabled: Global toggle for sound playback. False disables all audio.
            sound_file_path: Optional path to a local .wav file for audio playback.
            sound_duration_ms: Duration of synthesized fallback tone in ms (default: 400ms).
            sound_frequency_hz: Frequency of fallback beep tone in Hz (default: 1000Hz).
            sound_player: Optional callable(worker_track_id, ppe_category) for custom/mocked audio.
        """
        self.cooldown_seconds = float(cooldown_seconds)
        self.sound_enabled = bool(sound_enabled)
        self.sound_file_path = sound_file_path
        self.sound_duration_ms = int(sound_duration_ms)
        self.sound_frequency_hz = int(sound_frequency_hz)
        self.sound_player = sound_player
        self.visual_alerts_enabled: bool = True

        # In-memory alarm registry: {(worker_track_id, ppe_category): AlarmRecord}
        self._alarms: Dict[Tuple[int, str], AlarmRecord] = {}

    def update(
        self,
        alarm_eligible_violations: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
        current_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Updates alarm states based on the latest alarm-eligible violations.

        Rules:
            1. Trigger sound ONLY for newly eligible violations or violations whose cooldown has passed.
            2. Do NOT trigger sound repeatedly on every frame for the same continuous violation.
            3. Reset/remove alarms when a violation is no longer alarm-eligible (resolved or timer reset).
            4. Keep workers and PPE categories isolated.

        Args:
            alarm_eligible_violations: List of alarm-eligible violation dicts or payload containing them.
            current_time: Optional float timestamp for deterministic testing.

        Returns:
            dict: Summary containing active alarms and newly triggered alarms for this update.
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

        # Track keys currently eligible in this frame
        current_eligible_keys: Set[Tuple[int, str]] = set()
        triggered_this_update: List[Dict[str, Any]] = []

        for item in eligible_items:
            if not isinstance(item, dict):
                continue

            track_id = item.get("worker_track_id")
            cat = item.get("ppe_category")
            if track_id is None or cat is None:
                continue

            try:
                track_id = int(track_id)
                cat = str(cat)
            except (ValueError, TypeError):
                continue

            # Must have alarm_eligible flag True
            if not item.get("alarm_eligible", True):
                continue

            alarm_key = (track_id, cat)
            current_eligible_keys.add(alarm_key)

            if alarm_key in self._alarms:
                record = self._alarms[alarm_key]

                if record.status == STATUS_STOPPED:
                    # Manually stopped; do not re-trigger during this continuous episode
                    continue

                if record.is_in_cooldown(now):
                    # In cooldown; do not trigger sound again
                    record.status = STATUS_COOLING_DOWN
                else:
                    # Cooldown expired while still in violation; re-trigger
                    record.trigger_count += 1
                    record.last_triggered_timestamp = now
                    record.status = STATUS_TRIGGERED
                    self._play_sound(track_id, cat)
                    triggered_this_update.append(record.to_dict())
            else:
                # First time this violation reaches alarm eligibility!
                record = AlarmRecord(
                    worker_track_id=track_id,
                    ppe_category=cat,
                    status=STATUS_TRIGGERED,
                    first_triggered_timestamp=now,
                    last_triggered_timestamp=now,
                    trigger_count=1,
                    cooldown_seconds=self.cooldown_seconds,
                )
                self._alarms[alarm_key] = record
                self._play_sound(track_id, cat)
                triggered_this_update.append(record.to_dict())

                try:
                    from app.services.notification_service import get_notification_service
                    notif_svc = get_notification_service()
                    if notif_svc:
                        notif_svc.create_notification(
                            event_type="alarm_activated",
                            category="alarm",
                            title=f"Safety Alarm Triggered: Worker #{track_id}",
                            description=f"Audio alert activated for missing {cat.replace('_', ' ')}.",
                            severity="high",
                            worker_id=track_id,
                            destination="/violations",
                            dedup_window_sec=self.cooldown_seconds,
                        )
                except Exception as n_err:
                    logger.debug(f"Error creating notification for alarm trigger: {n_err}")

        # Reset/clear alarms for violations that are NO LONGER alarm-eligible
        keys_to_remove = [k for k in self._alarms.keys() if k not in current_eligible_keys]
        for k in keys_to_remove:
            w_id, cat_name = k
            logger.debug(f"Resetting resolved alarm for Worker #{w_id} -> {cat_name}")
            del self._alarms[k]

        return {
            "timestamp": now,
            "active_alarms_count": len(self._alarms),
            "triggered_alarms_count": len(triggered_this_update),
            "active_alarms": [a.to_dict() for a in self._alarms.values()],
            "triggered_alarms": triggered_this_update,
        }

    def _play_sound(self, worker_track_id: int, ppe_category: str) -> None:
        """
        Executes non-blocking sound playback.
        Uses custom/mock player if provided, or safe fallback to local audio.
        """
        if not self.sound_enabled:
            return

        if self.sound_player is not None:
            try:
                self.sound_player(worker_track_id, ppe_category)
            except Exception as e:
                logger.error(f"Error in custom sound_player: {e}", exc_info=True)
            return

        # Default local audio player (runs in background thread to avoid blocking inference)
        def _audio_worker():
            try:
                # 1. If valid sound file path is provided, attempt file playback
                if self.sound_file_path and os.path.isfile(self.sound_file_path):
                    if sys.platform == "win32":
                        import winsound
                        winsound.PlaySound(
                            self.sound_file_path,
                            winsound.SND_FILENAME | winsound.SND_ASYNC,
                        )
                        return

                # 2. Safe fallback: Windows synthesized tone
                if sys.platform == "win32":
                    import winsound
                    winsound.Beep(self.sound_frequency_hz, self.sound_duration_ms)
                else:
                    # Generic fallback: terminal bell
                    sys.stdout.write("\a")
                    sys.stdout.flush()
            except Exception as e:
                logger.warning(f"Audio playback encountered warning: {e}")

        thread = threading.Thread(target=_audio_worker, daemon=True)
        thread.start()

    def play_test_alarm(
        self,
        duration_ms: Optional[int] = None,
        frequency_hz: Optional[int] = None,
    ) -> bool:
        """
        Triggers an asynchronous test tone to verify audio output hardware.
        Uses specified parameters or falls back to instance configuration.
        """
        dur = int(duration_ms if duration_ms is not None else self.sound_duration_ms)
        freq = int(frequency_hz if frequency_hz is not None else self.sound_frequency_hz)

        def _test_audio_worker():
            try:
                if sys.platform == "win32":
                    import winsound
                    winsound.Beep(freq, dur)
                else:
                    sys.stdout.write("\a")
                    sys.stdout.flush()
            except Exception as e:
                logger.warning(f"Test alarm playback failed: {e}")

        th = threading.Thread(target=_test_audio_worker, daemon=True)
        th.start()
        return True

    def get_alarm(self, worker_track_id: int, ppe_category: str) -> Optional[Dict[str, Any]]:
        """Returns the specific alarm dictionary for a worker and PPE category, if active."""
        record = self._alarms.get((int(worker_track_id), str(ppe_category)))
        return record.to_dict() if record else None

    def get_active_alarms(self) -> List[Dict[str, Any]]:
        """Returns all currently active or cooling-down alarms."""
        return [a.to_dict() for a in self._alarms.values()]

    def stop_alarm(self, worker_track_id: int, ppe_category: str) -> bool:
        """
        Stops a specific alarm, preventing further audio alerts during this continuous episode.

        Returns:
            bool: True if the alarm was found and stopped, False otherwise.
        """
        key = (int(worker_track_id), str(ppe_category))
        if key in self._alarms:
            self._alarms[key].status = STATUS_STOPPED
            logger.info(f"Stopped alarm for Worker #{worker_track_id} -> {ppe_category}")
            return True
        return False

    def stop_all_alarms(self) -> int:
        """
        Stops all currently active alarms.

        Returns:
            int: Number of alarms stopped.
        """
        count = 0
        for record in self._alarms.values():
            if record.status != STATUS_STOPPED:
                record.status = STATUS_STOPPED
                count += 1
        logger.info(f"Stopped all {count} active alarms.")
        return count

    def reset_alarm(self, worker_track_id: int, ppe_category: str) -> bool:
        """
        Explicitly resets and removes a specific alarm.

        Returns:
            bool: True if the alarm existed and was removed, False otherwise.
        """
        key = (int(worker_track_id), str(ppe_category))
        if key in self._alarms:
            del self._alarms[key]
            return True
        return False

    def reset_worker_alarms(self, worker_track_id: int) -> int:
        """
        Resets and removes all active alarms for a given worker.

        Returns:
            int: Number of alarms reset.
        """
        w_id = int(worker_track_id)
        keys_to_remove = [k for k in self._alarms.keys() if k[0] == w_id]
        for k in keys_to_remove:
            del self._alarms[k]
        return len(keys_to_remove)

    def reset_all(self) -> None:
        """Clears all in-memory alarm records across the entire session."""
        self._alarms.clear()
        logger.info("Cleared all in-memory alarms.")

    def get_summary(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """Returns a snapshot summary of current alarms."""
        now = float(current_time if current_time is not None else time.time())
        active = self.get_active_alarms()
        return {
            "timestamp": now,
            "active_alarms_count": len(active),
            "active_alarms": active,
        }

