import asyncio
import json
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
    from app.services.websocket_manager import ConnectionManager, get_websocket_manager
    from app.services.ppe_monitoring_service import get_monitoring_service
except ImportError as e:
    print(f"[FATAL] Failed to import WebSocket test dependencies: {e}")
    sys.exit(1)


def make_sample_frame_payload():
    """Generates a structured test frame payload for monitoring."""
    return {
        "workers": [
            {
                "track_id": 1,
                "bbox": [100.0, 150.0, 200.0, 400.0],
                "confidence": 0.90,
            }
        ],
        "compliant_ppe": [
            {
                "class_name": "hardhat",
                "bbox": [110.0, 150.0, 150.0, 190.0],
                "confidence": 0.95,
            }
        ],
        "violations": [],
        "heavy_machinery": [],
        "unknown": [],
        "total_detections": 2,
    }


def run_all_websocket_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - WebSocket Real-Time Stream Tests")
    print("=" * 75)

    client = TestClient(app)
    manager = get_websocket_manager()
    monitoring_service = get_monitoring_service()

    # Reset state before testing
    manager.clear()

    # -------------------------------------------------------------
    # Scenario 1: WebSocket connection accepted
    # -------------------------------------------------------------
    print("\n[Test 1] Establishing WebSocket connection to /ws/monitoring...")
    with client.websocket_connect("/ws/monitoring") as ws:
        assert manager.get_connected_count() == 1
        print("  ✓ WebSocket handshake successful, connection accepted.")

        # -------------------------------------------------------------
        # Scenario 2: Initial connection confirmation
        # -------------------------------------------------------------
        print("\n[Test 2] Receiving connection confirmation message...")
        msg1 = ws.receive_json()
        assert msg1["type"] == "connection_established"
        assert msg1["status"] == "connected"
        assert "client_count" in msg1
        assert msg1["client_count"] >= 1
        print(f"  ✓ Message 1 confirmed: type='{msg1['type']}', status='{msg1['status']}'")

        # -------------------------------------------------------------
        # Scenario 3: Initial monitoring snapshot
        # -------------------------------------------------------------
        print("\n[Test 3] Receiving initial monitoring snapshot...")
        msg2 = ws.receive_json()
        assert msg2["type"] == "monitoring_snapshot"
        assert "data" in msg2
        snap_data = msg2["data"]
        assert "workers" in snap_data
        assert "worker_lifecycle" in snap_data
        print(f"  ✓ Message 2 confirmed: type='{msg2['type']}', timestamp={msg2.get('timestamp')}")

    # -------------------------------------------------------------
    # Scenario 6: Client disconnection
    # -------------------------------------------------------------
    print("\n[Test 6] Client disconnection safely recorded...")
    # The 'with' block exited, so connection should be closed/disconnected
    assert manager.get_connected_count() == 0
    print("  ✓ Manager active connection count dropped to 0 after client disconnect.")

    # -------------------------------------------------------------
    # Scenario 4: Broadcast to one client
    # -------------------------------------------------------------
    print("\n[Test 4] Broadcasting real-time frame update to 1 client...")
    manager.clear()
    with client.websocket_connect("/ws/monitoring") as ws:
        # Drain initial two messages (handshake & snapshot)
        ws.receive_json()  # connection_established
        ws.receive_json()  # monitoring_snapshot

        # Process a frame through monitoring pipeline (triggers broadcast)
        monitoring_service.process_structured_data(
            make_sample_frame_payload(),
            timestamp=2000.0,
        )

        broadcast_msg = ws.receive_json()
        assert broadcast_msg["type"] == "monitoring_update"
        assert broadcast_msg["timestamp"] == 2000.0
        assert "data" in broadcast_msg
        assert broadcast_msg["data"]["total_workers"] == 1
        print("  ✓ Live broadcast delivered to connected client successfully.")

    # -------------------------------------------------------------
    # Scenario 5: Broadcast to multiple clients simultaneously
    # -------------------------------------------------------------
    print("\n[Test 5] Broadcasting to multiple clients simultaneously...")
    manager.clear()
    with client.websocket_connect("/ws/monitoring") as ws1:
        # Drain ws1 handshake
        ws1.receive_json()
        ws1.receive_json()

        with client.websocket_connect("/ws/monitoring") as ws2:
            # Drain ws2 handshake
            ws2.receive_json()
            ws2.receive_json()

            assert manager.get_connected_count() == 2

            # Dispatch broadcast message
            test_payload = {
                "timestamp": 3000.0,
                "total_workers": 2,
                "status": "active",
                "workers": [{"worker_track_id": 1}, {"worker_track_id": 2}],
            }
            # Trigger broadcast
            monitoring_service.process_structured_data(
                make_sample_frame_payload(),
                timestamp=3000.0,
            )

            rec1 = ws1.receive_json()
            rec2 = ws2.receive_json()

            assert rec1["type"] == "monitoring_update"
            assert rec2["type"] == "monitoring_update"
            assert rec1["timestamp"] == 3000.0
            assert rec2["timestamp"] == 3000.0
            print("  ✓ Both concurrent clients received the identical live broadcast.")

    # -------------------------------------------------------------
    # Scenario 7: Invalid / disconnected client handling
    # -------------------------------------------------------------
    print("\n[Test 7] Invalid or dropping client handling during broadcast...")
    manager.clear()

    class FakeBrokenWebSocket:
        async def send_json(self, msg):
            raise RuntimeError("Network socket broken")

    loop = asyncio.new_event_loop()
    try:
        broken_sock = FakeBrokenWebSocket()
        manager._active_connections[broken_sock] = loop
        assert manager.get_connected_count() == 1

        # Broadcast should not raise exception and should remove dead socket
        sent = loop.run_until_complete(manager.broadcast({"test": "data"}))
        assert sent == 0
        assert manager.get_connected_count() == 0
        print("  ✓ Dead socket detected and removed cleanly without throwing uncaught exceptions.")
    finally:
        loop.close()

    # -------------------------------------------------------------
    # Scenario 8: Empty and invalid monitoring data
    # -------------------------------------------------------------
    print("\n[Test 8] Empty and invalid monitoring payloads...")
    manager.clear()
    res_none = manager.broadcast_monitoring_update(None)
    assert res_none == 0
    res_empty = manager.broadcast_monitoring_update({})
    assert res_empty == 0
    print("  ✓ None and empty payloads safely ignored.")

    # -------------------------------------------------------------
    # Scenario 9: Monitoring payload serialization
    # -------------------------------------------------------------
    print("\n[Test 9] Monitoring payload JSON serialization...")
    latest_snap = monitoring_service.get_latest_monitoring_data()
    serialized = json.dumps(latest_snap)
    deserialized = json.loads(serialized)
    assert isinstance(deserialized, dict)
    assert "timestamp" in deserialized
    assert "workers" in deserialized
    print(f"  ✓ Full monitoring payload ({len(serialized)} bytes) cleanly serializes to JSON.")

    # -------------------------------------------------------------
    # Scenario 10: REST API regression after WebSocket integration
    # -------------------------------------------------------------
    print("\n[Test 10] REST API regression after mounting WebSocket router...")
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    r_sys = client.get("/api/system/info")
    assert r_sys.status_code == 200

    r_status = client.get("/api/monitoring/status")
    assert r_status.status_code == 200

    r_viol = client.get("/api/violations")
    assert r_viol.status_code == 200

    r_alarms = client.get("/api/alarms")
    assert r_alarms.status_code == 200
    print("  ✓ All core REST endpoints remain 100% operational alongside WebSocket router.")

    print("\n" + "=" * 75)
    print("  FINAL WEBSOCKET COMMUNICATION TEST SUMMARY")
    print("=" * 75)
    print("  * Total Scenarios Executed : 10")
    print("  * Scenarios Passed         : 10 (100% assertions verified)")
    print("  * Multi-Client Broadcast   : VERIFIED (Concurrent delivery)")
    print("  * Fault Tolerance          : VERIFIED (Dead socket eviction)")
    print("  * REST API Compatibility   : CONFIRMED (Zero regression)")
    print("=" * 75)
    print("  [SUCCESS] WebSocket real-time communication verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_websocket_tests()
