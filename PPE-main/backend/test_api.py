import sys
from pathlib import Path

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

try:
    from fastapi.testclient import TestClient
    from main import app
    from app.api.deps import (
        get_alarm_service,
        get_monitoring_service,
        get_violation_event_service,
    )
    from app.services.alarm_service import AlarmService
    from app.services.ppe_monitoring_service import PPEMonitoringService
    from app.services.violation_event_service import ViolationEventService
except ImportError as e:
    print(f"[FATAL] Failed to import API test dependencies: {e}")
    sys.exit(1)


def run_all_api_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - FastAPI REST API Unit Tests")
    print("=" * 75)

    client = TestClient(app)

    # -------------------------------------------------------------
    # 1. Root & Health Endpoints
    # -------------------------------------------------------------
    print("\n[Test 1] Testing Root '/' and Health '/api/health' endpoints...")
    res_root = client.get("/")
    assert res_root.status_code == 200
    root_data = res_root.json()
    assert root_data["status"] == "online"
    assert "version" in root_data

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "healthy"
    assert "python_version" in health_data
    assert "pytorch_version" in health_data
    assert "device" in health_data
    print(f"  ✓ GET /api/health returned 200: {health_data['status']} ({health_data['device']})")

    # -------------------------------------------------------------
    # 2. System Info Endpoint
    # -------------------------------------------------------------
    print("\n[Test 2] Testing System Information '/api/system/info' endpoint...")
    res_info = client.get("/api/system/info")
    assert res_info.status_code == 200
    info_data = res_info.json()
    assert info_data["status"] == "online"
    assert "os" in info_data
    assert "model" in info_data
    assert "num_classes" in info_data["model"] or "error" in info_data["model"]
    print(f"  ✓ GET /api/system/info returned 200: OS='{info_data['os']}'")

    # -------------------------------------------------------------
    # 3. Monitoring Status Endpoint (Baseline / Idle)
    # -------------------------------------------------------------
    print("\n[Test 3] Testing Monitoring Status '/api/monitoring/status'...")
    res_status = client.get("/api/monitoring/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "status" in status_data
    assert "active_workers_count" in status_data
    assert "compliant_workers_count" in status_data
    assert "worker_lifecycle" in status_data
    assert status_data["active_model_id"]
    assert status_data["active_model_name"]
    print(f"  ✓ GET /api/monitoring/status returned 200: status='{status_data['status']}'")

    # -------------------------------------------------------------
    # 4. Monitoring Workers & Compliance Endpoints
    # -------------------------------------------------------------
    print("\n[Test 4] Testing Monitoring Workers & Compliance...")
    res_workers = client.get("/api/monitoring/workers")
    assert res_workers.status_code == 200
    workers_data = res_workers.json()
    assert "total_workers" in workers_data
    assert isinstance(workers_data["workers"], list)

    res_compliance = client.get("/api/monitoring/compliance")
    assert res_compliance.status_code == 200
    comp_data = res_compliance.json()
    assert "total_workers" in comp_data
    assert "compliant_workers" in comp_data
    print(f"  ✓ GET /api/monitoring/workers and /compliance returned 200 (Total Workers: {workers_data['total_workers']})")

    # -------------------------------------------------------------
    # 5. Populate Mock Data in Pipeline & Verify Dynamic API Updates
    # -------------------------------------------------------------
    print("\n[Test 5] Injecting mock monitoring data and verifying dynamic updates...")
    monitoring_svc = get_monitoring_service()
    mock_payload = {
        "workers": [
            {
                "track_id": 101,
                "bbox": [100.0, 150.0, 200.0, 400.0],
                "confidence": 0.88,
            },
            {
                "track_id": 102,
                "bbox": [300.0, 150.0, 400.0, 400.0],
                "confidence": 0.92,
            },
        ],
        "compliant_ppe": [
            {
                "class_name": "hardhat",
                "bbox": [110.0, 150.0, 150.0, 190.0],
                "confidence": 0.90,
            },
            {
                "class_name": "safety vest",
                "bbox": [110.0, 200.0, 180.0, 300.0],
                "confidence": 0.85,
            },
        ],
        "violations": [
            {
                "class_name": "no-hardhat",
                "bbox": [310.0, 150.0, 350.0, 190.0],
                "confidence": 0.89,
            },
        ],
        "heavy_machinery": [],
        "unknown": [],
        "total_detections": 5,
    }
    # Process structured data into monitoring service
    monitoring_svc.process_structured_data(mock_payload, timestamp=1000.0)

    # Re-query API endpoints
    res_status2 = client.get("/api/monitoring/status")
    status_data2 = res_status2.json()
    assert status_data2["active_workers_count"] == 0
    assert status_data2["status"] == "idle"

    res_workers2 = client.get("/api/monitoring/workers")
    workers_data2 = res_workers2.json()
    assert workers_data2["total_workers"] == 2
    track_ids = [w["worker_track_id"] for w in workers_data2["workers"]]
    assert 101 in track_ids and 102 in track_ids
    tracked_worker = next(w for w in workers_data2["workers"] if w["worker_track_id"] == 101)
    assert tracked_worker["confidence"] == 0.88
    assert tracked_worker["first_seen"] == 1000.0
    assert tracked_worker["last_seen"] == 1000.0
    print(f"  ✓ Dynamic state reflected via API: Active Workers = {track_ids}")

    # -------------------------------------------------------------
    # 6. Violations Endpoints
    # -------------------------------------------------------------
    print("\n[Test 6] Testing Violation endpoints '/api/violations'...")
    # Inject a confirmed violation event
    event_svc = monitoring_svc.violation_event_service
    event_svc.update(
        alarm_eligible_violations=[{
            "worker_track_id": 102,
            "ppe_category": "hardhat",
            "start_timestamp": 995.0,
            "alarm_eligible": True,
        }],
        current_time=1000.0,
    )

    res_viol = client.get("/api/violations")
    assert res_viol.status_code == 200
    viol_data = res_viol.json()
    assert viol_data["total_count"] >= 1
    first_evt = viol_data["events"][0]
    assert first_evt["worker_track_id"] == 102
    assert first_evt["ppe_category"] == "hardhat"

    # Test filtering by status
    res_viol_filter = client.get("/api/violations?status=open")
    assert res_viol_filter.status_code == 200
    assert len(res_viol_filter.json()["events"]) >= 1

    # Test active violations
    res_active = client.get("/api/violations/active")
    assert res_active.status_code == 200
    assert res_active.json()["total_count"] >= 1

    # Test violation summary
    res_summary = client.get("/api/violations/summary")
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    assert "by_status" in summary_data
    assert "by_severity" in summary_data
    assert summary_data["by_severity"]["critical"] >= 1
    print(f"  ✓ GET /api/violations and /summary returned confirmed event {first_evt['event_id']}")

    # -------------------------------------------------------------
    # 7. Alarms Endpoints (Retrieval & Actions)
    # -------------------------------------------------------------
    print("\n[Test 7] Testing Alarms endpoints '/api/alarms'...")
    alarm_svc = monitoring_svc.alarm_service
    # Trigger an alarm
    alarm_svc.update(
        alarm_eligible_violations=[{
            "worker_track_id": 102,
            "ppe_category": "hardhat",
            "alarm_eligible": True,
        }],
        current_time=1000.0,
    )

    res_alarms = client.get("/api/alarms")
    assert res_alarms.status_code == 200
    alarms_data = res_alarms.json()
    assert alarms_data["active_alarms_count"] >= 1
    print(f"  ✓ GET /api/alarms returned {alarms_data['active_alarms_count']} active alarm(s)")

    # -------------------------------------------------------------
    # 8. Stop Specific Alarm (POST /api/alarms/stop)
    # -------------------------------------------------------------
    print("\n[Test 8] Testing POST /api/alarms/stop...")
    # Stop existing alarm
    res_stop = client.post("/api/alarms/stop", json={"worker_track_id": 102, "ppe_category": "hardhat"})
    assert res_stop.status_code == 200
    stop_data = res_stop.json()
    assert stop_data["success"] is True
    assert stop_data["stopped"] is True
    print(f"  ✓ POST /api/alarms/stop successfully stopped alarm for Worker #102")

    # Stop non-existent alarm
    res_stop_none = client.post("/api/alarms/stop", json={"worker_track_id": 999, "ppe_category": "gloves"})
    assert res_stop_none.status_code == 200
    assert res_stop_none.json()["success"] is False
    assert res_stop_none.json()["stopped"] is False
    print("  ✓ Non-existent alarm gracefully handled (success=False, stopped=False)")

    # -------------------------------------------------------------
    # 9. Stop All Alarms (POST /api/alarms/stop-all)
    # -------------------------------------------------------------
    print("\n[Test 9] Testing POST /api/alarms/stop-all...")
    # Trigger another alarm
    alarm_svc.reset_all()
    alarm_svc.update([
        {"worker_track_id": 201, "ppe_category": "hardhat", "alarm_eligible": True},
        {"worker_track_id": 202, "ppe_category": "safety_vest", "alarm_eligible": True},
    ], current_time=2000.0)

    res_stop_all = client.post("/api/alarms/stop-all")
    assert res_stop_all.status_code == 200
    stop_all_data = res_stop_all.json()
    assert stop_all_data["success"] is True
    assert stop_all_data["stopped_count"] == 2
    print(f"  ✓ POST /api/alarms/stop-all stopped {stop_all_data['stopped_count']} alarms")

    # -------------------------------------------------------------
    # 10. Request Validation (Pydantic 422 Errors)
    # -------------------------------------------------------------
    print("\n[Test 10] Testing Request Validation (422 Unprocessable Entity)...")
    # Empty body to POST /api/alarms/stop
    res_val1 = client.post("/api/alarms/stop", json={})
    assert res_val1.status_code == 422

    # Invalid type for worker_track_id
    res_val2 = client.post("/api/alarms/stop", json={"worker_track_id": "not-an-int", "ppe_category": "hardhat"})
    assert res_val2.status_code == 422

    # Empty string for ppe_category (min_length=1)
    res_val3 = client.post("/api/alarms/stop", json={"worker_track_id": 1, "ppe_category": ""})
    assert res_val3.status_code == 422

    # Query param limit < 1 (ge=1)
    res_val4 = client.get("/api/violations?limit=0")
    assert res_val4.status_code == 422
    print("  ✓ All 4 invalid input schemas properly rejected with HTTP 422.")

    # -------------------------------------------------------------
    # 11. Mocking Dependencies / Clean Isolation
    # -------------------------------------------------------------
    print("\n[Test 11] Testing Dependency Overrides Isolation...")
    mock_alarm_service = AlarmService(sound_enabled=False)
    app.dependency_overrides[get_alarm_service] = lambda: mock_alarm_service

    res_override = client.get("/api/alarms")
    assert res_override.status_code == 200
    assert res_override.json()["active_alarms_count"] == 0
    app.dependency_overrides.clear()
    print("  ✓ Dependency injection successfully overridden and restored.")

    print("\n" + "=" * 75)
    print("  FINAL REST API TEST SUMMARY")
    print("=" * 75)
    print("  * System Endpoints       : PASSED (/api/health, /api/system/info)")
    print("  * Monitoring Endpoints   : PASSED (/api/monitoring/status, /workers, /compliance)")
    print("  * Violation Endpoints    : PASSED (/api/violations, /active, /summary)")
    print("  * Alarm Endpoints        : PASSED (/api/alarms, /stop, /stop-all)")
    print("  * Schema Validation      : PASSED (HTTP 422 properly returned)")
    print("  * Dependency Injection   : PASSED (Pluggable and testable)")
    print("=" * 75)
    print("  [SUCCESS] All REST API endpoints verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_api_tests()
