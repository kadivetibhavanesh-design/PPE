import json
from pathlib import Path
import shutil
import sys
import tempfile
import cv2
import numpy as np

# Ensure stdout uses UTF-8 on Windows
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
from app.services.evidence_service import EvidenceService
from app.api.deps import get_evidence_service


def create_dummy_jpeg() -> bytes:
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.putText(dummy_img, "PPE TEST", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    success, buf = cv2.imencode(".jpg", dummy_img)
    assert success
    return buf.tobytes()


def test_incident_history_frontend_backend_integration():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - Incident History Integration Tests")
    print("=" * 75)

    temp_dir = Path(tempfile.mkdtemp(prefix="safevision_incident_test_"))
    storage_dir = temp_dir / "evidence"

    try:
        isolated_service = EvidenceService(storage_dir=storage_dir)
        app.dependency_overrides[get_evidence_service] = lambda: isolated_service
        client = TestClient(app)

        # -------------------------------------------------------------
        # Scenario 1: Empty Evidence State (Verification 6)
        # -------------------------------------------------------------
        print("\n[Verification 1] Testing empty evidence state (empty repository)...")
        res_empty = client.get("/api/evidence")
        assert res_empty.status_code == 200
        empty_data = res_empty.json()
        assert empty_data["total_count"] == 0
        assert empty_data["evidence"] == []
        print("  ✓ Empty repository returned zero records for frontend empty-state rendering.")

        # Populate test evidence records
        sample_jpeg = create_dummy_jpeg()

        # Record 1: Hardhat violation, open, with captured image
        rec1 = {
            "event_id": "EVT-0001",
            "worker_track_id": 101,
            "ppe_category": "hardhat",
            "severity": "critical",
            "start_timestamp": 1700000000.0,
            "status": "open",
        }
        isolated_service.capture_evidence(rec1, sample_jpeg)

        # Record 2: Vest violation, resolved, with captured image
        rec2 = {
            "event_id": "EVT-0002",
            "worker_track_id": 102,
            "ppe_category": "safety_vest",
            "severity": "high",
            "start_timestamp": 1700000100.0,
            "status": "open",
        }
        isolated_service.capture_evidence(rec2, sample_jpeg)
        isolated_service.update_event_status("EVT-0002", status="resolved", resolution_timestamp=1700000150.0)

        # Record 3: Gloves violation, missing camera frame
        rec3 = {
            "event_id": "EVT-0003",
            "worker_track_id": 103,
            "ppe_category": "gloves",
            "severity": "medium",
            "start_timestamp": 1700000200.0,
            "status": "ongoing",
        }
        isolated_service.capture_evidence(rec3, frame_bytes=None)

        # -------------------------------------------------------------
        # Scenario 2: Fetch Actual Evidence Records (Verification 1)
        # -------------------------------------------------------------
        print("\n[Verification 2] Fetching actual evidence records via GET /api/evidence...")
        res_list = client.get("/api/evidence")
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["total_count"] == 3
        assert len(list_data["evidence"]) == 3
        print(f"  ✓ Successfully fetched {list_data['total_count']} real evidence records.")

        # -------------------------------------------------------------
        # Scenario 3: Display Incident Metadata Correctly (Verification 2)
        # -------------------------------------------------------------
        print("\n[Verification 3] Verifying incident metadata fields match frontend schema...")
        res_evt1 = client.get("/api/evidence/EVT-0001")
        assert res_evt1.status_code == 200
        e1 = res_evt1.json()
        assert e1["event_id"] == "EVT-0001"
        assert e1["worker_track_id"] == 101
        assert e1["ppe_category"] == "hardhat"
        assert e1["severity"] == "critical"
        assert e1["first_detected_timestamp"] == 1700000000.0
        assert e1["event_status"] == "open"
        assert e1["resolution_timestamp"] is None
        assert e1["evidence_image_filename"] == "EVT-0001.jpg"

        res_evt2 = client.get("/api/evidence/EVT-0002")
        assert res_evt2.status_code == 200
        e2 = res_evt2.json()
        assert e2["event_status"] == "resolved"
        assert e2["resolution_timestamp"] == 1700000150.0
        print("  ✓ All required metadata fields (event_id, worker, category, severity, timestamps, status) verified.")

        # -------------------------------------------------------------
        # Scenario 4: Open Captured Evidence Images (Verification 3)
        # -------------------------------------------------------------
        print("\n[Verification 4] Fetching captured evidence image via GET /api/evidence/{event_id}/image...")
        res_img = client.get("/api/evidence/EVT-0001/image")
        assert res_img.status_code == 200
        assert res_img.headers["content-type"] == "image/jpeg"
        assert res_img.content.startswith(b"\xff\xd8")
        assert len(res_img.content) > 0
        print(f"  ✓ Evidence JPEG streamed correctly ({len(res_img.content)} bytes, Content-Type: image/jpeg).")

        # -------------------------------------------------------------
        # Scenario 5: Missing-Image Handling (Verification 5)
        # -------------------------------------------------------------
        print("\n[Verification 5] Testing missing-image handling on event without camera frame...")
        res_no_img = client.get("/api/evidence/EVT-0003/image")
        assert res_no_img.status_code == 404
        e3_meta = client.get("/api/evidence/EVT-0003").json()
        assert e3_meta["evidence_image_filename"] is None
        assert e3_meta["image_filename"] is None
        print("  ✓ Missing-image handled cleanly: metadata available with null image pointer, image query returns 404.")

        # -------------------------------------------------------------
        # Scenario 6: Search and Filters (Verification 4)
        # -------------------------------------------------------------
        print("\n[Verification 6] Verifying server query filters (worker, category, status)...")
        # Filter by worker_track_id
        res_w101 = client.get("/api/evidence?worker_track_id=101")
        assert res_w101.json()["total_count"] == 1
        assert res_w101.json()["evidence"][0]["event_id"] == "EVT-0001"

        # Filter by ppe_category
        res_vest = client.get("/api/evidence?ppe_category=safety_vest")
        assert res_vest.json()["total_count"] == 1
        assert res_vest.json()["evidence"][0]["event_id"] == "EVT-0002"

        # Filter by status
        res_resolved = client.get("/api/evidence?status=resolved")
        assert res_resolved.json()["total_count"] == 1
        assert res_resolved.json()["evidence"][0]["event_id"] == "EVT-0002"
        print("  ✓ Server-side filtering by worker, category, and status fully verified.")

        # -------------------------------------------------------------
        # Scenario 7: Non-existent Event 404 Handling (Verification 7)
        # -------------------------------------------------------------
        print("\n[Verification 7] Testing non-existent incident handling...")
        res_404 = client.get("/api/evidence/EVT-9999")
        assert res_404.status_code == 404
        assert "not found" in res_404.json().get("message", "").lower()
        print("  ✓ Non-existent event returns HTTP 404 with descriptive error.")

        app.dependency_overrides.clear()

        print("\n" + "=" * 75)
        print("  ALL INCIDENT HISTORY INTEGRATION VERIFICATIONS PASSED")
        print("=" * 75)

    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


if __name__ == "__main__":
    test_incident_history_frontend_backend_integration()

