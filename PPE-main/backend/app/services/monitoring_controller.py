import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple
import cv2
import numpy as np

try:
    from app.services.video_service import VideoCaptureService
    from app.services.ppe_monitoring_service import PPEMonitoringService, get_monitoring_service
    from app.services.websocket_manager import ConnectionManager, get_websocket_manager
    from app.services.annotation_service import annotate_frame
    from app.services.evidence_service import EvidenceService, get_evidence_service
    from app.services.email_service import EmailService, get_email_service
    from app.services.notification_service import get_notification_service
except ImportError:
    from services.video_service import VideoCaptureService
    from services.ppe_monitoring_service import PPEMonitoringService, get_monitoring_service
    from services.websocket_manager import ConnectionManager, get_websocket_manager
    from services.annotation_service import annotate_frame
    from services.evidence_service import EvidenceService, get_evidence_service
    from services.email_service import EmailService, get_email_service
    try:
        from services.notification_service import get_notification_service
    except ImportError:
        get_notification_service = None

logger = logging.getLogger("ppe_monitoring.monitoring_controller")

# Operational lifecycle states
STATUS_IDLE = "idle"
STATUS_STARTING = "starting"
STATUS_ACTIVE = "active"
STATUS_STOPPING = "stopping"
STATUS_ERROR = "error"

MAX_CONSECUTIVE_READ_FAILURES = 100
FRAME_READ_RETRY_DELAY_SECONDS = 0.01


class MonitoringController:
    """
    Manages the lifecycle of live PPE webcam monitoring.
    Controls the background capture and inference worker thread, manages camera resources,
    coordinates real-time WebSocket broadcasts, and provides thread-safe start/stop controls.
    """

    def __init__(
        self,
        monitoring_service: Optional[PPEMonitoringService] = None,
        websocket_manager: Optional[ConnectionManager] = None,
        video_service_factory: Optional[Callable[[int], VideoCaptureService]] = None,
        evidence_service: Optional[Any] = None,
    ) -> None:
        """
        Initializes the MonitoringController.

        Args:
            monitoring_service: Optional PPEMonitoringService instance. Defaults to singleton.
            websocket_manager: Optional ConnectionManager instance. Defaults to singleton.
            video_service_factory: Optional factory callable(camera_index) returning VideoCaptureService.
                                   Enables mocking camera devices during automated testing.
            evidence_service: Optional EvidenceService instance. Defaults to singleton.
        """
        self.monitoring_service = monitoring_service or get_monitoring_service()
        self.websocket_manager = websocket_manager or get_websocket_manager()
        self.video_service_factory = video_service_factory
        self.evidence_service = evidence_service or get_evidence_service()
        self.email_service = get_email_service()

        if hasattr(self.evidence_service, "attach_to_violation_event_service") and hasattr(
            self.monitoring_service, "violation_event_service"
        ):
            self.evidence_service.attach_to_violation_event_service(
                self.monitoring_service.violation_event_service
            )

        if hasattr(self.email_service, "attach_to_violation_event_service") and hasattr(
            self.monitoring_service, "violation_event_service"
        ):
            self.email_service.attach_to_violation_event_service(
                self.monitoring_service.violation_event_service
            )

        if hasattr(self.email_service, "set_monitoring_active_checker"):
            self.email_service.set_monitoring_active_checker(lambda: self.is_running)

        # Attach real-time notification listeners to violation event lifecycle
        if get_notification_service and hasattr(self.monitoring_service, "violation_event_service"):
            ves = self.monitoring_service.violation_event_service
            if hasattr(ves, "register_listener"):
                def _on_notif_created(rec):
                    try:
                        n_svc = get_notification_service()
                        if n_svc:
                            n_svc.create_notification(
                                event_type="ppe_violation_confirmed",
                                category="ppe",
                                title=f"PPE Violation Confirmed [{rec.event_id}]",
                                description=f"Worker #{rec.worker_track_id}: Missing {rec.ppe_category}",
                                severity=rec.severity,
                                worker_id=rec.worker_track_id,
                                incident_id=rec.event_id,
                                destination="/incident-history",
                            )
                    except Exception as err:
                        logger.debug(f"Error dispatching notification for created event: {err}")

                def _on_notif_resolved(rec):
                    try:
                        n_svc = get_notification_service()
                        if n_svc:
                            n_svc.create_notification(
                                event_type="ppe_violation_resolved",
                                category="ppe",
                                title=f"PPE Violation Resolved [{rec.event_id}]",
                                description=f"Worker #{rec.worker_track_id} corrected PPE ({rec.ppe_category})",
                                severity="info",
                                worker_id=rec.worker_track_id,
                                incident_id=rec.event_id,
                                destination="/incident-history",
                            )
                    except Exception as err:
                        logger.debug(f"Error dispatching notification for resolved event: {err}")

                def _on_notif_interrupted(rec):
                    try:
                        n_svc = get_notification_service()
                        if n_svc:
                            n_svc.create_notification(
                                event_type="incident_interrupted",
                                category="ppe",
                                title=f"Incident Interrupted [{rec.event_id}]",
                                description=f"Monitoring stopped while Worker #{rec.worker_track_id} had active violations ({rec.ppe_category})",
                                severity="medium",
                                worker_id=rec.worker_track_id,
                                incident_id=rec.event_id,
                                destination="/incident-history",
                            )
                    except Exception as err:
                        logger.debug(f"Error dispatching notification for interrupted event: {err}")

                ves.register_listener(
                    on_created=_on_notif_created,
                    on_resolved=_on_notif_resolved,
                    on_interrupted=_on_notif_interrupted,
                )

        # Threading and synchronization state
        self._state: str = STATUS_IDLE
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Camera and runtime state
        self._video_service: Optional[VideoCaptureService] = None
        self._camera_index: int = 0
        self._frame_count: int = 0
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None
        self._last_error: Optional[str] = None
        self._last_exit_reason: Optional[str] = None
        self._current_fps: float = 0.0
        self._last_frame_timestamp: Optional[float] = None

        # Live MJPEG streaming state
        self._latest_jpeg: Optional[bytes] = None
        self._latest_frame_id: int = 0
        self._frame_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """Returns True if the background monitoring thread is currently active."""
        return self._state == STATUS_ACTIVE

    @property
    def state(self) -> str:
        """Returns current operational lifecycle state ('idle', 'active', 'stopping', 'error')."""
        return self._state

    def start_monitoring(
        self,
        camera_index: int = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Starts live PPE webcam monitoring in a detached background thread.
        Guards against duplicate starts and rejects starting while a previous thread is stopping.

        Args:
            camera_index: Integer index of webcam device (default: 0).
            width: Optional target frame width.
            height: Optional target frame height.
            fps: Optional target frame rate.

        Returns:
            dict: Operation status, success flag, and descriptive message.
        """
        with self._lock:
            # Check if previous worker thread finished while lock was not held
            if self._thread is not None and not self._thread.is_alive():
                self._thread = None
                if self._state == STATUS_STOPPING:
                    self._state = STATUS_IDLE if self._last_error is None else STATUS_ERROR

            # 1. Guard against duplicate start if active or starting
            if self._state == STATUS_ACTIVE:
                logger.warning("Attempted to start monitoring while already running.")
                return {
                    "success": False,
                    "message": "Monitoring is already active.",
                    "status": STATUS_ACTIVE,
                    "camera_index": self._camera_index,
                    "frames_processed": self._frame_count,
                }

            if self._state == STATUS_STARTING:
                logger.warning("Attempted to start monitoring while startup is already in progress.")
                return {
                    "success": False,
                    "message": "Monitoring startup is already in progress.",
                    "status": STATUS_STARTING,
                    "camera_index": self._camera_index,
                    "frames_processed": self._frame_count,
                }

            # 2. Guard against starting while previous worker thread is still alive / stopping
            if self._state == STATUS_STOPPING or (self._thread is not None and self._thread.is_alive()):
                logger.warning("Attempted to start monitoring while previous worker thread is still stopping/shutting down.")
                return {
                    "success": False,
                    "message": "Previous monitoring session shutdown is still pending; please wait.",
                    "status": STATUS_STOPPING,
                    "camera_index": self._camera_index,
                    "frames_processed": self._frame_count,
                }

            logger.info(f"Starting PPE monitoring on camera index {camera_index}...")
            self._state = STATUS_STARTING
            self._camera_index = camera_index
            self._last_error = None
            self._last_exit_reason = None
            self._frame_count = 0
            self._current_fps = 0.0
            self._stop_event.clear()

            # 3. Initialize capture device
            cap = None
            try:
                if self.video_service_factory is not None:
                    cap = self.video_service_factory(camera_index)
                else:
                    target_w = width if width is not None else 1280
                    target_h = height if height is not None else 720
                    target_f = fps if fps is not None else 30
                    cap = VideoCaptureService(
                        camera_index=camera_index,
                        target_width=target_w,
                        target_height=target_h,
                        target_fps=target_f,
                    )

                if not cap.start():
                    err_msg = f"Failed to initialize camera on index {camera_index}."
                    logger.error(err_msg)
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception as rel_err:
                            logger.warning(f"Error releasing camera after start failure: {rel_err}")
                    self._last_error = err_msg
                    self._state = STATUS_ERROR
                    self._video_service = None
                    if hasattr(self.email_service, "set_camera_monitoring_active"):
                        self.email_service.set_camera_monitoring_active(False, reason="camera_init_failed")
                    if get_notification_service:
                        try:
                            n_svc = get_notification_service()
                            if n_svc:
                                n_svc.create_notification(
                                    event_type="camera_failed",
                                    category="monitoring",
                                    title="Camera Monitoring Error",
                                    description=err_msg,
                                    severity="high",
                                    destination="/live-monitoring",
                                )
                        except Exception as n_err:
                            logger.debug(f"Error notifying camera failure: {n_err}")
                    return {
                        "success": False,
                        "message": err_msg,
                        "status": STATUS_ERROR,
                        "camera_index": camera_index,
                        "frames_processed": 0,
                    }

                self._video_service = cap
            except Exception as e:
                err_msg = f"Camera initialization exception: {str(e)}"
                logger.error(err_msg, exc_info=True)
                if cap is not None:
                    try:
                        cap.release()
                    except Exception as rel_err:
                        logger.warning(f"Error releasing camera after initialization exception: {rel_err}")
                self._last_error = err_msg
                self._state = STATUS_ERROR
                self._video_service = None
                if hasattr(self.email_service, "set_camera_monitoring_active"):
                    self.email_service.set_camera_monitoring_active(False, reason="camera_init_exception")
                if get_notification_service:
                    try:
                        n_svc = get_notification_service()
                        if n_svc:
                            n_svc.create_notification(
                                event_type="camera_failed",
                                category="monitoring",
                                title="Camera Initialization Exception",
                                description=err_msg,
                                severity="high",
                                destination="/live-monitoring",
                            )
                    except Exception as n_err:
                        logger.debug(f"Error notifying camera init exception: {n_err}")
                return {
                    "success": False,
                    "message": err_msg,
                    "status": STATUS_ERROR,
                    "camera_index": camera_index,
                    "frames_processed": 0,
                }

            # 4. Launch background processing thread (non-daemon for controlled shutdown)
            self._state = STATUS_ACTIVE
            self._start_time = time.time()

            # Ensure timer service starts fresh without stale counts
            if hasattr(self.monitoring_service, "violation_timer_service"):
                self.monitoring_service.violation_timer_service.reset_all()

            # Enable camera-dependent email alert notifications
            if hasattr(self.email_service, "set_camera_monitoring_active"):
                self.email_service.set_camera_monitoring_active(True)

            # Record monitoring start notification
            if get_notification_service:
                try:
                    n_svc = get_notification_service()
                    if n_svc:
                        n_svc.create_notification(
                            event_type="camera_started",
                            category="monitoring",
                            title="Camera Monitoring Started",
                            description=f"Live camera #{camera_index} is now active and monitoring site safety.",
                            severity="info",
                            destination="/live-monitoring",
                        )
                except Exception as n_err:
                    logger.debug(f"Error notifying camera start: {n_err}")

            self._thread = threading.Thread(
                target=self._processing_loop,
                daemon=False,
                name="PPEMonitoringWorker",
            )
            self._thread.start()

            logger.info(f"PPE monitoring started successfully on camera index {camera_index}.")
            return {
                "success": True,
                "message": f"PPE monitoring started on camera index {camera_index}.",
                "status": STATUS_ACTIVE,
                "camera_index": camera_index,
                "frames_processed": 0,
            }

    def stop_monitoring(self, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Stops live PPE webcam monitoring and signals the worker thread to exit.
        Delegates camera hardware cleanup safely to the worker's own finally block
        so that timeout expiration never yanks resources while the worker is reading.

        Args:
            timeout: Maximum seconds to wait for worker thread to terminate (default: 3.0s).

        Returns:
            dict: Operation status, success flag, and final metrics.
        """
        with self._lock:
            # Check if previous worker thread finished while lock was not held
            if self._thread is not None and not self._thread.is_alive():
                self._thread = None
                if self._state == STATUS_STOPPING:
                    self._state = STATUS_IDLE if self._last_error is None else STATUS_ERROR

            # 1. Handle stop while already inactive
            if self._state == STATUS_IDLE and self._thread is None:
                logger.info("stop_monitoring called but monitoring is already inactive.")
                return {
                    "success": True,
                    "message": "Monitoring is not currently active.",
                    "status": STATUS_IDLE,
                    "frames_processed": self._frame_count,
                }

            # 2. If already stopping, worker_thread is already signaled
            if self._state == STATUS_STOPPING:
                logger.info("stop_monitoring called while already stopping; awaiting worker exit...")
                worker_thread = self._thread
            else:
                logger.info("Signaling background monitoring thread to stop...")
                self._stop_event.set()
                self._state = STATUS_STOPPING
                self._stop_time = time.time()
                worker_thread = self._thread

                # Immediately disable automatic email alerts and cancel active reminder schedules
                if hasattr(self.email_service, "set_camera_monitoring_active"):
                    self.email_service.set_camera_monitoring_active(False, reason="monitoring_stopped")

                # Interrupt active violation episodes with explicit interrupted status (not resolved)
                if hasattr(self.monitoring_service, "violation_event_service"):
                    self.monitoring_service.violation_event_service.interrupt_active_events(reason="monitoring_stopped")

                # Clear continuous timers
                if hasattr(self.monitoring_service, "violation_timer_service"):
                    self.monitoring_service.violation_timer_service.reset_all()

                # Record monitoring stopped notification
                if get_notification_service:
                    try:
                        n_svc = get_notification_service()
                        if n_svc:
                            n_svc.create_notification(
                                event_type="camera_stopped",
                                category="monitoring",
                                title="Camera Monitoring Stopped",
                                description="Live camera monitoring has been safely stopped.",
                                severity="info",
                                destination="/live-monitoring",
                            )
                    except Exception as n_err:
                        logger.debug(f"Error notifying camera stop: {n_err}")

        # 3. Wait safely for worker thread to exit without holding the lock
        thread_joined = True
        if worker_thread is not None and worker_thread.is_alive():
            worker_thread.join(timeout=timeout)
            if worker_thread.is_alive():
                thread_joined = False
                logger.warning(
                    f"Worker thread join timed out after {timeout}s; "
                    "camera release remains safely delegated to worker thread's finally block."
                )

        # 4. Synchronize post-stop state
        with self._lock:
            if thread_joined:
                self._thread = None
                # If worker finished, state is set by worker finally block; ensure it's not 'stopping'
                if self._state == STATUS_STOPPING:
                    self._state = STATUS_IDLE if self._last_error is None else STATUS_ERROR
            elif self._thread is not None and not self._thread.is_alive():
                # Worker thread finished right after join timeout check
                self._thread = None
                thread_joined = True
                if self._state == STATUS_STOPPING:
                    self._state = STATUS_IDLE if self._last_error is None else STATUS_ERROR

            total_frames = self._frame_count
            current_status = self._state

        if thread_joined:
            msg = "PPE monitoring stopped successfully."
            logger.info(f"{msg} Total frames processed: {total_frames}, Status: {current_status}")
            return {
                "success": True,
                "message": msg,
                "status": current_status,
                "frames_processed": total_frames,
            }
        else:
            msg = f"Shutdown is still pending: worker thread did not finish within {timeout}s."
            logger.warning(f"{msg} Total frames processed: {total_frames}, Status: {current_status}")
            return {
                "success": False,
                "message": msg,
                "status": STATUS_STOPPING,
                "frames_processed": total_frames,
            }

    def _processing_loop(self) -> None:
        """
        Internal worker loop executing synchronous OpenCV capture and YOLO pipeline processing.
        Guarantees camera resource release and state transition inside a robust finally block.
        """
        logger.info("Monitoring background thread started.")
        fps_counter = 0
        fps_timer = time.time()
        consecutive_read_failures = 0
        exit_reason: Optional[str] = None
        processing_stage = "camera availability check"

        try:
            while True:
                try:
                    if self._stop_event.is_set():
                        exit_reason = "stop_requested"
                        break

                    cap = self._video_service
                    if cap is None:
                        exit_reason = "camera_handle_unavailable"
                        self._last_error = "Camera handle became unavailable during monitoring."
                        logger.error("%s", self._last_error)
                        break

                    if not cap.is_opened():
                        exit_reason = "camera_closed"
                        self._last_error = "Camera closed unexpectedly during monitoring."
                        logger.error("%s", self._last_error)
                        break

                    processing_stage = "camera frame read"
                    ret, frame = cap.read_frame()
                    if not ret or frame is None or frame.size == 0:
                        consecutive_read_failures += 1
                        if not cap.is_opened():
                            exit_reason = "camera_closed_during_read"
                            self._last_error = "Camera closed while reading a frame."
                            logger.error("%s", self._last_error)
                            break
                        if consecutive_read_failures == 1:
                            logger.warning(
                                "Camera returned an unreadable frame; retrying "
                                "(failure %d/%d).",
                                consecutive_read_failures,
                                MAX_CONSECUTIVE_READ_FAILURES,
                            )
                        if consecutive_read_failures >= MAX_CONSECUTIVE_READ_FAILURES:
                            exit_reason = "repeated_camera_read_failures"
                            self._last_error = (
                                f"Camera returned {consecutive_read_failures} consecutive "
                                "unreadable frames."
                            )
                            logger.error("%s", self._last_error)
                            break
                        time.sleep(FRAME_READ_RETRY_DELAY_SECONDS)
                        continue

                    if consecutive_read_failures:
                        logger.info(
                            "Camera frame reads recovered after %d consecutive failure(s).",
                            consecutive_read_failures,
                        )
                        consecutive_read_failures = 0

                    ts = time.time()

                    # Process frame through the consolidated monitoring pipeline
                    processing_stage = "frame processing"
                    result = self.monitoring_service.process_frame(frame, timestamp=ts)
                    self._frame_count += 1
                    self._last_frame_timestamp = ts
                    if result.get("error"):
                        logger.error(
                            "Frame %d pipeline returned an error: %s",
                            self._frame_count,
                            result["error"],
                        )

                    # Annotate frame and encode latest JPEG for real-time video streaming
                    processing_stage = "frame annotation"
                    try:
                        annotated = annotate_frame(frame, result, fps=self._current_fps)
                        success, buf = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                        if success:
                            latest_bytes = buf.tobytes()
                            with self._frame_lock:
                                self._latest_jpeg = latest_bytes
                                self._latest_frame_id += 1

                            # Automatically capture evidence for newly created confirmed violation events
                            if self.evidence_service is not None:
                                new_events = result.get("violation_event_summary", {}).get("new_events", [])
                                for evt in new_events:
                                    try:
                                        self.evidence_service.capture_evidence(evt, latest_bytes)
                                    except Exception as ev_err:
                                        logger.error(f"Error capturing evidence for event {evt.get('event_id')}: {ev_err}")

                                resolved_events = result.get("violation_event_summary", {}).get("resolved_events", [])
                                for evt in resolved_events:
                                    try:
                                        self.evidence_service.update_event_status(
                                            evt.get("event_id"),
                                            status=evt.get("status", "resolved"),
                                            resolution_timestamp=evt.get("resolution_timestamp"),
                                        )
                                    except Exception as ev_err:
                                        logger.error(f"Error updating evidence status for event {evt.get('event_id')}: {ev_err}")
                    except Exception as ann_err:
                        logger.debug(f"Frame annotation error: {ann_err}")

                    # Calculate rolling FPS
                    processing_stage = "frame metrics"
                    fps_counter += 1
                    elapsed = time.time() - fps_timer
                    if elapsed >= 1.0:
                        self._current_fps = round(fps_counter / elapsed, 2)
                        fps_counter = 0
                        fps_timer = time.time()

                except Exception as e:
                    exit_reason = "runtime_exception"
                    logger.error(
                        "Monitoring worker failed during %s: %s",
                        processing_stage,
                        e,
                        exc_info=True,
                    )
                    self._last_error = str(e)
                    break
        finally:
            # Guaranteed cleanup in worker's own finally block
            if exit_reason is None:
                exit_reason = (
                    "stop_requested"
                    if self._stop_event.is_set()
                    else "unexpected_loop_exit"
                )
            logger.info(
                "Monitoring loop exiting: reason=%s, stop_event_set=%s, "
                "frames_processed=%d, last_error=%s",
                exit_reason,
                self._stop_event.is_set(),
                self._frame_count,
                self._last_error,
            )
            logger.info("Worker thread entering finally block: releasing camera resources...")
            with self._frame_lock:
                self._latest_jpeg = None

            with self._lock:
                self._last_exit_reason = exit_reason
                if self._video_service is not None:
                    try:
                        self._video_service.release()
                    except Exception as e:
                        logger.warning(f"Error releasing camera in worker finally: {e}")
                    finally:
                        self._video_service = None

                # Update lifecycle state
                if self._last_error is not None:
                    self._state = STATUS_ERROR
                else:
                    self._state = STATUS_IDLE

                # Guarantee automatic email reminders stop when worker exits
                if hasattr(self.email_service, "set_camera_monitoring_active"):
                    self.email_service.set_camera_monitoring_active(False, reason="camera_worker_terminated")

                # Interrupt active violation episodes with explicit interrupted status
                if hasattr(self.monitoring_service, "violation_event_service"):
                    self.monitoring_service.violation_event_service.interrupt_active_events(reason="camera_worker_terminated")

                # Clear timers so fresh confirmation is required upon restart
                if hasattr(self.monitoring_service, "violation_timer_service"):
                    self.monitoring_service.violation_timer_service.reset_all()

                if self._last_error is not None and get_notification_service:
                    try:
                        n_svc = get_notification_service()
                        if n_svc:
                            n_svc.create_notification(
                                event_type="camera_disconnected",
                                category="monitoring",
                                title="Camera Disconnected Unexpectedly",
                                description=f"Monitoring terminated with error: {self._last_error}",
                                severity="high",
                                destination="/live-monitoring",
                            )
                    except Exception as n_err:
                        logger.debug(f"Error notifying worker loop error: {n_err}")

            logger.info(f"Monitoring background thread safely terminated. Final state: {self._state}")

    def get_latest_frame_jpeg(self) -> Optional[bytes]:
        """
        Thread-safe retrieval of the latest annotated JPEG frame bytes.
        Returns None if monitoring is idle or no frame has been encoded yet.
        """
        with self._frame_lock:
            return self._latest_jpeg

    def get_latest_frame_info(self) -> Tuple[int, Optional[bytes]]:
        """
        Atomic retrieval of (frame_id, frame_bytes) to eliminate redundant byte-by-byte
        comparisons in video streaming loops.
        """
        with self._frame_lock:
            return self._latest_frame_id, self._latest_jpeg

    def switch_model(self, model_id: str) -> Dict[str, Any]:
        """
        Safely switches the active detection model if monitoring is not currently running.

        Args:
            model_id: Target model identifier ('constructelligence' or 'vyra').

        Returns:
            dict: Updated model inspection metadata.

        Raises:
            RuntimeError: If camera monitoring is currently active or starting.
        """
        with self._lock:
            if self._state in (STATUS_ACTIVE, STATUS_STARTING):
                raise RuntimeError(
                    "Cannot switch detection model while camera monitoring is running. "
                    "Please stop camera monitoring before switching models."
                )

        from app.services.model_service import switch_model as do_switch_model
        info = do_switch_model(model_id)
        if self.monitoring_service and hasattr(self.monitoring_service, "refresh_model"):
            self.monitoring_service.refresh_model()
        return info

    def get_status(self) -> Dict[str, Any]:
        """
        Returns real-time operational status, FPS, processed frames, and uptime metrics.
        Accurately reports 'active', 'stopping', 'error', and 'idle' states.
        """
        with self._lock:
            # Check if previous worker thread finished while lock was not held
            if self._thread is not None and not self._thread.is_alive():
                self._thread = None
                if self._state == STATUS_STOPPING:
                    self._state = STATUS_IDLE if self._last_error is None else STATUS_ERROR

            now = time.time()
            uptime = 0.0
            if self._state == STATUS_ACTIVE and self._start_time:
                uptime = round(now - self._start_time, 2)

            try:
                from app.services.model_registry import get_model_profile
                prof = get_model_profile()
                active_model_id = prof.model_id
                active_model_name = prof.display_name
            except Exception:
                active_model_id = "constructelligence"
                active_model_name = "Constructelligence (YOLOv8)"

            return {
                "is_running": self._state == STATUS_ACTIVE,
                "status": self._state,
                "camera_index": self._camera_index,
                "frames_processed": self._frame_count,
                "current_fps": self._current_fps,
                "uptime_seconds": uptime,
                "last_error": self._last_error,
                "last_exit_reason": self._last_exit_reason,
                "last_frame_timestamp": self._last_frame_timestamp,
                "active_model_id": active_model_id,
                "active_model_name": active_model_name,
            }

    def shutdown(self, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Gracefully halts monitoring during FastAPI shutdown, waiting up to timeout
        seconds for the worker thread to exit and release resources.
        Logs an ERROR if shutdown remains pending or the worker thread has not terminated.
        """
        logger.info(f"Executing MonitoringController shutdown (timeout={timeout}s)...")
        res = self.stop_monitoring(timeout=timeout)
        worker_alive = self._thread is not None and self._thread.is_alive()
        if not res.get("success") or res.get("status") == STATUS_STOPPING or worker_alive:
            logger.error(
                f"MonitoringController shutdown timed out after {timeout}s; "
                "worker shutdown remains pending and worker thread is still alive."
            )
        else:
            logger.info("MonitoringController shutdown completed successfully.")
        return res


# Shared singleton instance
_controller_instance: Optional[MonitoringController] = None


def get_monitoring_controller() -> MonitoringController:
    """Returns the shared MonitoringController singleton."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = MonitoringController()
    return _controller_instance
