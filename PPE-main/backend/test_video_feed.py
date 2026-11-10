import asyncio
import sys
import time
from pathlib import Path
import numpy as np

# Ensure stdout uses UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from fastapi.testclient import TestClient
from main import app
from app.services.monitoring_controller import get_monitoring_controller
from app.services.annotation_service import annotate_frame


class MockStreamCamera:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self._is_opened = False
        self.released = False

    def start(self):
        self._is_opened = True
        return True

    def read_frame(self):
        if not self._is_opened:
            return False, None
        # Return a synthetic 480x640 frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        return True, frame

    def is_opened(self):
        return self._is_opened

    def release(self):
        self._is_opened = False
        self.released = True


def test_annotation_service():
    print("\n[Test 1] Testing annotation_service directly...")
    sample_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    sample_result = {
        "total_workers": 1,
        "total_compliant": 0,
        "total_non_compliant": 1,
        "workers": [
            {
                "worker_track_id": 7,
                "worker_bounding_box": [100.0, 100.0, 300.0, 400.0],
                "overall_status": "non_compliant",
                "associated_ppe": [
                    {
                        "class_name": "no-hardhat",
                        "bbox": [150.0, 100.0, 250.0, 180.0],
                        "confidence": 0.94,
                    }
                ],
            }
        ],
        "unassigned_ppe": [],
    }

    annotated = annotate_frame(sample_frame, sample_result, fps=24.5)
    assert annotated is not None
    assert annotated.shape == (480, 640, 3)
    # Check that pixels were actually modified (not all zero)
    assert np.any(annotated > 0)
    print("  ✓ Frame successfully annotated with bounding boxes, labels, and HUD bar.")


def test_video_feed_endpoints():
    client = TestClient(app)
    controller = get_monitoring_controller()

    print("\n[Test 2] Querying GET /api/monitoring/video_feed when monitoring is idle...")
    res_idle = client.get("/api/monitoring/video_feed")
    assert res_idle.status_code == 503, f"Expected 503 when idle, got {res_idle.status_code}"
    body = res_idle.json()
    error_msg = body.get("message") or body.get("detail", "")
    assert "Monitoring is not active" in error_msg, f"Unexpected error body: {body}"
    print("  ✓ Correctly returned HTTP 503 with helpful message when idle.")

    print("\n[Test 3] Testing video feed streaming with active controller...")
    controller.video_service_factory = lambda idx: MockStreamCamera(idx)
    start_res = controller.start_monitoring(camera_index=0)
    assert start_res["success"] is True

    # Wait for worker thread to process at least 1 frame (CPU model load may take 1-3 seconds)
    jpeg = None
    for _ in range(60):
        jpeg = controller.get_latest_frame_jpeg()
        if jpeg is not None:
            break
        time.sleep(0.1)

    # Verify latest JPEG is available
    assert jpeg is not None, "Controller did not produce latest JPEG frame within timeout"
    assert jpeg.startswith(b"\xff\xd8"), "Invalid JPEG header bytes (SOI missing)"
    print(f"  ✓ Latest JPEG frame generated successfully ({len(jpeg)} bytes, valid JPEG magic bytes).")

    # Stop monitoring
    stop_res = controller.stop_monitoring()
    assert stop_res["success"] is True
    assert controller.get_latest_frame_jpeg() is None
    print("  ✓ Monitoring stopped cleanly and JPEG buffer cleared.")


if __name__ == "__main__":
    test_annotation_service()
    test_video_feed_endpoints()
    print("\n[SUCCESS] All video feed tests passed successfully!")
