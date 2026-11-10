import logging
import time
from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("ppe_monitoring.video_service")


class VideoCaptureService:
    """
    Reusable video capture service for managing camera devices (e.g., built-in laptop webcam).
    Provides safe initialization, frame reading, hardware capability querying,
    and guaranteed resource cleanup.
    """

    def __init__(
        self,
        camera_index: int = 0,
        target_width: int = 1280,
        target_height: int = 720,
        target_fps: int = 30,
    ) -> None:
        """
        Initializes video capture configuration.

        Args:
            camera_index: Device index for the webcam (default: 0).
            target_width: Desired frame width in pixels (default: 1280).
            target_height: Desired frame height in pixels (default: 720).
            target_fps: Desired capture frame rate (default: 30).
        """
        self.camera_index = camera_index
        self.target_width = target_width
        self.target_height = target_height
        self.target_fps = target_fps

        self._cap: Optional[cv2.VideoCapture] = None
        self._is_running: bool = False
        self._actual_width: int = 0
        self._actual_height: int = 0
        self._actual_fps: float = 0.0

    def is_opened(self) -> bool:
        """Checks whether the capture device is currently active and opened."""
        return self._cap is not None and self._cap.isOpened()

    def start(self) -> bool:
        """
        Opens the camera device and configures requested properties.
        Prevents duplicate connections if already open.

        Returns:
            bool: True if camera initialized and opened successfully, False otherwise.
        """
        if self.is_opened():
            logger.warning(f"Camera index {self.camera_index} is already open and running.")
            return True

        logger.info(f"Attempting to open camera index {self.camera_index}...")

        try:
            # On Windows, cv2.CAP_DSHOW provides fast, direct DirectShow access (0.5s vs 6s with default MSMF).
            # Attempt DirectShow first on Windows; fall back to default backend if needed.
            import platform
            if platform.system() == "Windows":
                self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                if not self._cap or not self._cap.isOpened():
                    logger.info(f"CAP_DSHOW failed; falling back to default backend on index {self.camera_index}...")
                    self._cap = cv2.VideoCapture(self.camera_index)
            else:
                self._cap = cv2.VideoCapture(self.camera_index)

            if not self._cap or not self._cap.isOpened():
                logger.error(f"Failed to open webcam at index {self.camera_index}.")
                self._cleanup_cap()
                return False

            # Request desired resolution and FPS
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
            self._cap.set(cv2.CAP_PROP_FPS, self.target_fps)

            # Query actual hardware-reported properties
            self._actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._actual_fps = float(self._cap.get(cv2.CAP_PROP_FPS))

            # In case driver reports 0 FPS (common for some webcams), fall back to target
            if self._actual_fps <= 0.0:
                self._actual_fps = float(self.target_fps)

            self._is_running = True
            logger.info(
                f"Webcam index {self.camera_index} initialized successfully. "
                f"Reported resolution: {self._actual_width}x{self._actual_height}, "
                f"FPS: {self._actual_fps:.1f}"
            )
            return True

        except Exception as e:
            logger.error(f"Exception encountered while opening camera index {self.camera_index}: {e}", exc_info=True)
            self._cleanup_cap()
            return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Reads a single BGR video frame from the active capture device.

        Returns:
            tuple (bool, Optional[np.ndarray]):
                - bool: True if the frame was successfully decoded and non-empty.
                - frame: Decoded OpenCV BGR image array, or None on failure.
        """
        if not self.is_opened():
            logger.warning("read_frame called on closed VideoCaptureService.")
            return False, None

        try:
            ret, frame = self._cap.read()
            if not ret or frame is None or frame.size == 0:
                logger.warning("Empty or corrupted frame returned by camera device.")
                return False, None

            return True, frame

        except Exception as e:
            logger.error(f"Exception during frame read: {e}", exc_info=True)
            return False, None

    def get_camera_info(self) -> Dict[str, Any]:
        """
        Returns a dictionary containing actual hardware properties and status.

        Returns:
            dict: Camera status, actual dimensions, and FPS.
        """
        return {
            "camera_index": self.camera_index,
            "is_opened": self.is_opened(),
            "target_resolution": f"{self.target_width}x{self.target_height}",
            "actual_resolution": f"{self._actual_width}x{self._actual_height}",
            "actual_width": self._actual_width,
            "actual_height": self._actual_height,
            "target_fps": self.target_fps,
            "actual_fps": self._actual_fps,
        }

    def _cleanup_cap(self) -> None:
        """Internal helper to safely close and dereference the cv2.VideoCapture instance."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug(f"Error releasing capture handle: {e}")
            finally:
                self._cap = None
        self._is_running = False

    def release(self) -> None:
        """Safely stops capture and releases camera hardware resources."""
        if self._cap is not None or self._is_running:
            logger.info(f"Releasing camera device (index {self.camera_index})...")
            self._cleanup_cap()
            logger.info("Camera resources released successfully.")

    def __enter__(self) -> "VideoCaptureService":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

