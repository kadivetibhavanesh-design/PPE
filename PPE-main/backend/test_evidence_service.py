import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import cv2
import numpy as np

# Ensure stdout uses UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from app.services.evidence_service import EvidenceService
from app.services.violation_event_service import ViolationEventService
from fastapi.testclient import TestClient
from main import app


def create_sample_jpeg_bytes() -> bytes:
    """Helper creating valid JPEG encoded bytes with magic numbers."""
    dummy_img = np.zeros((240, 320, 3), dtype=np.uint8)
    # Draw some color shapes
    cv2.rectangle(dummy_img, (50, 50), (200, 200), (0, 0, 255), 2)
    cv2.putText(dummy_img, "EVIDENCE TEST", (60, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    success, buf = cv2.imencode(".jpg", dummy_img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    assert success, "Failed to encode sample JPEG"
    return buf.tobytes()


def run_all_evidence_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - Evidence Storage Service Tests")
    print("=" * 75)

    temp_root = Path(tempfile.mkdtemp(prefix="safevision_evidence_test_"))
    storage_dir = temp_root / "evidence"

    try:
        service = EvidenceService(storage_dir=storage_dir)
        sample_jpeg = create_sample_jpeg_bytes()

        # -------------------------------------------------------------
        # Test 1: Evidence image creation
        # -------------------------------------------------------------
        print("\n[Test 1] Testing evidence image creation...")
        event1 = {
            "event_id": "EVT-0001",
            "worker_track_id": 101,
            "ppe_category": "hardhat",
            "severity": "critical",
            "start_timestamp": 1700000000.0,
            "status": "open",
        }
        res1 = service.capture_evidence(event1, sample_jpeg)
        assert res1 is not None, "Failed to return captured evidence record"

        expected_img_path = storage_dir / "EVT-0001.jpg"
        assert expected_img_path.exists(), f"Image file {expected_img_path} was not created on disk"
        img_bytes = expected_img_path.read_bytes()
        assert len(img_bytes) > 0, "Saved image file is empty"
        assert img_bytes.startswith(b"\xff\xd8"), "Saved image does not have valid JPEG magic bytes"
        print(f"  ✓ Evidence image created successfully at {expected_img_path.name} ({len(img_bytes)} bytes).")

        # -------------------------------------------------------------
        # Test 2: Metadata JSON creation
        # -------------------------------------------------------------
        print("\n[Test 2] Testing metadata JSON creation...")
        expected_json_path = storage_dir / "EVT-0001.json"
        assert expected_json_path.exists(), f"Event metadata JSON {expected_json_path} was not created"

        parsed_json = json.loads(expected_json_path.read_text(encoding="utf-8"))
        required_keys = [
            "event_id",
            "worker_track_id",
            "ppe_category",
            "severity",
            "first_detected_timestamp",
            "evidence_image_filename",
            "event_status",
            "resolution_timestamp",
        ]
        for key in required_keys:
            assert key in parsed_json, f"Missing required key '{key}' in metadata JSON"

        assert parsed_json["event_id"] == "EVT-0001"
        assert parsed_json["worker_track_id"] == 101
        assert parsed_json["ppe_category"] == "hardhat"
        assert parsed_json["severity"] == "critical"
        assert parsed_json["event_status"] == "open"
        assert parsed_json["resolution_timestamp"] is None
        print("  ✓ Metadata JSON created with all required schema fields.")

        # -------------------------------------------------------------
        # Test 3: Correct event ID association
        # -------------------------------------------------------------
        print("\n[Test 3] Testing correct event ID association...")
        assert res1["event_id"] == "EVT-0001"
        assert res1["evidence_image_filename"] == "EVT-0001.jpg"
        assert res1["image_filename"] == "EVT-0001.jpg"

        queried_record = service.get_evidence("EVT-0001")
        assert queried_record is not None
        assert queried_record["event_id"] == "EVT-0001"
        assert queried_record["evidence_image_filename"] == "EVT-0001.jpg"

        resolved_img = service.get_image_path("EVT-0001")
        assert resolved_img is not None
        assert resolved_img.name == "EVT-0001.jpg"
        print("  ✓ Event ID 'EVT-0001' accurately associated with metadata and image path.")

        # -------------------------------------------------------------
        # Test 4: Duplicate prevention
        # -------------------------------------------------------------
        print("\n[Test 4] Testing duplicate prevention...")
        original_mtime = expected_img_path.stat().st_mtime_ns
        time.sleep(0.01)

        # Attempt to capture evidence again for the same event (e.g. repeated frame update)
        second_jpeg = b"\xff\xd8\xff\xe0" + b"DIFFERENT_DATA"
        res_dup = service.capture_evidence(event1, second_jpeg)

        # Image should NOT be overwritten
        new_mtime = expected_img_path.stat().st_mtime_ns
        assert original_mtime == new_mtime, "Duplicate capture modified existing evidence image"
        assert expected_img_path.read_bytes() == img_bytes, "Duplicate capture altered original JPEG content"
        assert len(service.get_all_evidence()) == 1, "Duplicate record inserted into registry"
        print("  ✓ Duplicate evidence capture prevented; existing frame preserved untouched.")

        # -------------------------------------------------------------
        # Test 5: Event resolution metadata update
        # -------------------------------------------------------------
        print("\n[Test 5] Testing event resolution metadata update...")
        res_update = service.update_event_status("EVT-0001", status="resolved", resolution_timestamp=1700000050.0)
        assert res_update is True, "Failed to update event status"

        updated_record = service.get_evidence("EVT-0001")
        assert updated_record is not None
        assert updated_record["status"] == "resolved"
        assert updated_record["event_status"] == "resolved"
        assert updated_record["resolution_timestamp"] == 1700000050.0

        # Verify on-disk JSON file is updated
        disk_json = json.loads(expected_json_path.read_text(encoding="utf-8"))
        assert disk_json["status"] == "resolved"
        assert disk_json["resolution_timestamp"] == 1700000050.0
        print("  ✓ Event resolution status and timestamp persisted successfully to disk.")

        # -------------------------------------------------------------
        # Test 6: Persistence after service restart
        # -------------------------------------------------------------
        print("\n[Test 6] Testing persistence across service restart...")
        # Instantiate a brand new EvidenceService pointing to the same storage_dir
        restarted_service = EvidenceService(storage_dir=storage_dir)

        restored_records = restarted_service.get_all_evidence()
        assert len(restored_records) == 1, f"Expected 1 persisted record, found {len(restored_records)}"
        r_rec = restarted_service.get_evidence("EVT-0001")
        assert r_rec is not None
        assert r_rec["event_id"] == "EVT-0001"
        assert r_rec["status"] == "resolved"
        assert r_rec["resolution_timestamp"] == 1700000050.0
        assert r_rec["evidence_image_filename"] == "EVT-0001.jpg"

        # Verify image retrieval still works
        restored_img_path = restarted_service.get_image_path("EVT-0001")
        assert restored_img_path is not None
        assert restored_img_path.exists()
        print("  ✓ Historical evidence metadata and images fully reloaded after service restart.")

        # -------------------------------------------------------------
        # Test 7: Missing frame handling
        # -------------------------------------------------------------
        print("\n[Test 7] Testing missing frame handling...")
        event_no_frame = {
            "event_id": "EVT-0002",
            "worker_track_id": 102,
            "ppe_category": "safety_vest",
            "severity": "high",
            "start_timestamp": 1700000100.0,
            "status": "open",
        }
        res_no_frame = restarted_service.capture_evidence(event_no_frame, frame_bytes=None)
        assert res_no_frame is not None, "Failed to record metadata when frame was None"
        assert res_no_frame["evidence_image_filename"] is None
        assert res_no_frame["image_filename"] is None

        # Image path should cleanly return None without raising error
        assert restarted_service.get_image_path("EVT-0002") is None
        # JSON metadata should still exist on disk
        evt2_json = storage_dir / "EVT-0002.json"
        assert evt2_json.exists(), "Event metadata JSON not created for missing frame"
        print("  ✓ Missing frame handled gracefully: metadata recorded with null image pointer.")

        # -------------------------------------------------------------
        # Test 8: Invalid filename and directory traversal rejection
        # -------------------------------------------------------------
        print("\n[Test 8] Testing invalid filename and directory traversal rejection...")
        traversal_attempts = [
            "../secret.txt",
            "..\\boot.ini",
            "../../etc/passwd",
            "/absolute/root.jpg",
            "nested/file.jpg",
            "evil\0name.jpg",
            "invalid*char.jpg",
            "",
            "   ",
        ]
        for malicious_name in traversal_attempts:
            rejected = False
            try:
                restarted_service.validate_filename(malicious_name)
            except ValueError:
                rejected = True
            assert rejected, f"Failed to reject traversal attempt: '{malicious_name}'"
        print("  ✓ All directory traversal and malicious filenames rejected with ValueError.")

        # -------------------------------------------------------------
        # Test 9: Multiple violation events
        # -------------------------------------------------------------
        print("\n[Test 9] Testing multiple violation events...")
        event3 = {
            "event_id": "EVT-0003",
            "worker_track_id": 103,
            "ppe_category": "gloves",
            "severity": "medium",
            "start_timestamp": 1700000200.0,
            "status": "open",
        }
        event4 = {
            "event_id": "EVT-0004",
            "worker_track_id": 104,
            "ppe_category": "goggles",
            "severity": "medium",
            "start_timestamp": 1700000300.0,
            "status": "open",
        }
        restarted_service.capture_evidence(event3, sample_jpeg)
        restarted_service.capture_evidence(event4, sample_jpeg)

        all_events = restarted_service.get_all_evidence()
        assert len(all_events) == 4, f"Expected 4 events, found {len(all_events)}"
        event_ids = {e["event_id"] for e in all_events}
        assert event_ids == {"EVT-0001", "EVT-0002", "EVT-0003", "EVT-0004"}

        assert (storage_dir / "EVT-0003.jpg").exists()
        assert (storage_dir / "EVT-0004.jpg").exists()
        assert (storage_dir / "EVT-0003.json").exists()
        assert (storage_dir / "EVT-0004.json").exists()
        print("  ✓ Multiple distinct violation events stored independently with unique filenames.")

        # -------------------------------------------------------------
        # Test 10: Missing evidence directory creation
        # -------------------------------------------------------------
        print("\n[Test 10] Testing missing evidence directory creation...")
        deep_dir = temp_root / "deep" / "nested" / "storage" / "evidence"
        assert not deep_dir.exists(), "Deep dir unexpectedly exists"

        deep_service = EvidenceService(storage_dir=deep_dir)
        assert deep_dir.exists(), "EvidenceService failed to create missing directory hierarchy"

        event5 = {
            "event_id": "EVT-0005",
            "worker_track_id": 105,
            "ppe_category": "safety_shoes",
            "severity": "high",
            "start_timestamp": 1700000400.0,
            "status": "open",
        }
        deep_service.capture_evidence(event5, sample_jpeg)
        assert (deep_dir / "EVT-0005.jpg").exists()
        assert (deep_dir / "EVT-0005.json").exists()
        print("  ✓ Missing directory tree automatically created and evidence stored successfully.")

        # -------------------------------------------------------------
        # Test 11: REST API Integration
        # -------------------------------------------------------------
        print("\n[Test 11] Testing REST API endpoints with TestClient...")
        from app.api.deps import get_evidence_service as get_api_evidence_service

        # Override FastAPI dependency to use our isolated test service
        app.dependency_overrides[get_api_evidence_service] = lambda: restarted_service

        client = TestClient(app)

        # GET /api/evidence
        res_list = client.get("/api/evidence")
        assert res_list.status_code == 200, f"Expected 200, got {res_list.status_code}"
        list_data = res_list.json()
        assert list_data["total_count"] == 4
        assert len(list_data["evidence"]) == 4

        # Filter by worker_track_id
        res_filtered = client.get("/api/evidence?worker_track_id=101")
        assert res_filtered.status_code == 200
        assert res_filtered.json()["total_count"] == 1
        assert res_filtered.json()["evidence"][0]["event_id"] == "EVT-0001"

        # GET /api/evidence/{event_id}
        res_single = client.get("/api/evidence/EVT-0001")
        assert res_single.status_code == 200
        assert res_single.json()["event_id"] == "EVT-0001"
        assert res_single.json()["status"] == "resolved"

        # GET /api/evidence/{event_id}/image
        res_img = client.get("/api/evidence/EVT-0001/image")
        assert res_img.status_code == 200
        assert res_img.headers["content-type"] == "image/jpeg"
        assert len(res_img.content) > 0
        assert res_img.content.startswith(b"\xff\xd8")

        # GET /api/evidence/{event_id}/image for event without image (EVT-0002)
        res_no_img = client.get("/api/evidence/EVT-0002/image")
        assert res_no_img.status_code == 404

        # GET /api/evidence/file/{filename}
        res_file = client.get("/api/evidence/file/EVT-0001.jpg")
        assert res_file.status_code == 200
        assert res_file.headers["content-type"] == "image/jpeg"

        # Path traversal attack via API
        res_attack = client.get("/api/evidence/file/..%2Fsecret.txt")
        assert res_attack.status_code == 400

        print("  ✓ REST API endpoints verified: listing, filtering, image streaming, and traversal defense.")

        # Clean up dependency override
        app.dependency_overrides.clear()

        print("\n" + "=" * 75)
        print("  FINAL EVIDENCE SERVICE TEST SUMMARY")
        print("=" * 75)
        print("  * Total Scenarios Executed : 11")
        print("  * Scenarios Passed         : 11 (100% assertions verified)")
        print("  * Image Storage            : VERIFIED (Annotated JPEG frames, unique names)")
        print("  * Metadata JSON            : VERIFIED (Complete schema, local JSON persistence)")
        print("  * Duplicate Prevention     : VERIFIED (Safe single-capture per event)")
        print("  * Lifecycle Updates        : VERIFIED (Status and resolution timestamps)")
        print("  * Service Restart          : VERIFIED (Full persistence reload)")
        print("  * Missing Frame Safety     : VERIFIED (Graceful fallback)")
        print("  * Path Traversal Defense   : VERIFIED (Rejects illegal paths)")
        print("  * REST API & Image Feeds   : VERIFIED (List, details, image download, 400 rejection)")
        print("=" * 75)
        print("  [SUCCESS] Local incident evidence storage verified successfully!")
        print("=" * 75 + "\n")

    finally:
        # Clean up temp root directory
        try:
            shutil.rmtree(temp_root)
        except Exception:
            pass


if __name__ == "__main__":
    run_all_evidence_tests()

