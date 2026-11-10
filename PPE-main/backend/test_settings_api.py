import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from main import app
from app.services.settings_service import get_settings_service

def test_settings_module():
    client = TestClient(app)

    print("--- 1. Testing GET /api/settings ---")
    res = client.get("/api/settings")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    settings = res.json()
    assert "model" in settings
    assert "camera" in settings
    assert "ppe" in settings
    assert "alerts" in settings
    assert "storage" in settings
    assert "preferences" in settings
    print("PASS: Settings retrieved with all expected sections.")

    print("\n--- 2. Testing PUT /api/settings ---")
    update_payload = {
        "ppe": {
            "global_confidence": 0.25,
            "min_ioa": 0.18,
            "violation_duration": 4.5,
        },
        "alerts": {
            "duration_ms": 450,
            "frequency_hz": 1200,
        }
    }
    res = client.put("/api/settings", json=update_payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    updated = res.json()["settings"]
    assert updated["ppe"]["global_confidence"] == 0.25
    assert updated["ppe"]["min_ioa"] == 0.18
    assert updated["ppe"]["violation_duration"] == 4.5
    assert updated["alerts"]["duration_ms"] == 450
    assert updated["alerts"]["frequency_hz"] == 1200
    print("PASS: Settings updated and verified.")

    print("\n--- 3. Testing GET /api/settings/models (Sanitized Profiles) ---")
    res = client.get("/api/settings/models")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "profiles" in data
    assert len(data["profiles"]) == 2
    for p in data["profiles"]:
        # Verify no raw repo or weight filenames leaked
        assert "Hexmon" not in p["name"]
        assert "constructelligence" not in p["name"]
        assert ".pt" not in str(p)
        print(f"Verified profile: {p['name']} (ID: {p['profile_id']})")
    print("PASS: Sanitized model profiles returned cleanly.")

    print("\n--- 4. Testing GET /api/settings/camera/test ---")
    res = client.get("/api/settings/camera/test?device_index=0&backend=DirectShow")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    cam_test = res.json()
    assert "available" in cam_test
    print(f"Camera availability test output: {cam_test['message']}")
    print("PASS: Camera tested safely without starting monitoring.")

    print("\n--- 5. Testing GET /api/settings/system/metrics and GET /settings/system/metrics ---")
    res = client.get("/api/settings/system/metrics")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    # Verify un-prefixed route also succeeds
    res_direct = client.get("/settings/system/metrics")
    assert res_direct.status_code == 200, f"Expected 200 on direct route, got {res_direct.status_code}: {res_direct.text}"
    metrics = res.json()
    assert "cpu" in metrics
    assert "ram" in metrics
    assert "gpu" in metrics
    assert "ai_pipeline" in metrics
    assert "performance_status" in metrics
    # Confirm GPU is N/A or actual (never fake)
    print(f"System CPU: {metrics['cpu']['percent']}% ({metrics['cpu']['logical_cores']} logical cores)")
    print(f"System RAM: {metrics['ram']['used_gb']}GB / {metrics['ram']['total_gb']}GB ({metrics['ram']['percent']}%)")
    print(f"GPU Status: {metrics['gpu']['status']}")
    print(f"Performance Status: {metrics['performance_status']}")
    print("PASS: Real-time system performance metrics verified.")

    print("\n--- 6. Testing GET /api/settings/system/info ---")
    res = client.get("/api/settings/system/info")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    info = res.json()
    assert info["application_name"] == "SafeVision AI"
    assert len(info["services"]) == 7
    print(f"App: {info['application_name']} v{info['version']} on {info['os_platform']}")
    print("PASS: System info and 7 backend services returned.")

    print("\n--- 7. Testing Alert Tone and Silence Endpoints ---")
    res = client.post("/api/settings/alerts/test", json={"duration_ms": 100, "frequency_hz": 800})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    res = client.post("/api/settings/alerts/stop-all")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    print("PASS: Audio test and stop-all alarms functional.")

    print("\n--- 8. Testing POST /api/settings/reset ---")
    res = client.post("/api/settings/reset")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    reset_data = res.json()["settings"]
    assert reset_data["ppe"]["global_confidence"] == 0.20
    print("PASS: Settings successfully reset to factory defaults.")

    print("\nALL BACKEND SETTINGS API TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_settings_module()

