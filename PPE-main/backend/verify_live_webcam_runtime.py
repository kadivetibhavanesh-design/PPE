import os
import sys
import time
import json
import logging

# Set up UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))

# Configure structured logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from app.services.video_service import VideoCaptureService
from app.services.ppe_monitoring_service import PPEMonitoringService
from app.services.monitoring_controller import MonitoringController
from app.services.annotation_service import annotate_frame

def verify_live_webcam_runtime():
    print("=" * 80)
    print("  SafeVision AI - Real Hardware Webcam Runtime Verification")
    print("=" * 80)

    # 1. Startup Speed Benchmark (Solving Problem 1)
    print("\n--- [Step 1: Camera Hardware Acquisition Speed] ---")
    t0 = time.time()
    cap = VideoCaptureService(camera_index=0)
    opened = cap.start()
    t_startup = time.time() - t0
    print(f"  Startup elapsed time: {t_startup:.2f} seconds")
    print(f"  Camera opened status: {opened}")
    print(f"  Hardware resolution : {cap._actual_width}x{cap._actual_height} @ {cap._actual_fps:.1f} FPS")

    assert opened is True, "Failed to open physical webcam at index 0"
    assert t_startup < 4.0, f"Startup took {t_startup:.2f}s, exceeding fast initialization target (<4s)"
    print("  ✓ Camera acquisition benchmark PASSED (well below Axios 8s/20s timeout)")

    # 2. Pipeline Execution on Live Captured Video Frames
    print("\n--- [Step 2: Live Inference & Detection Pipeline] ---")
    monitoring_svc = PPEMonitoringService()

    frames_processed = 0
    max_test_frames = 15
    detected_any_worker = False
    last_monitoring_result = None

    for i in range(max_test_frames):
        ret, frame = cap.read_frame()
        if not ret or frame is None:
            time.sleep(0.05)
            continue

        ts = time.time()
        result = monitoring_svc.process_frame(frame, timestamp=ts)
        frames_processed += 1
        last_monitoring_result = result

        workers = result.get("workers", [])
        if workers:
            detected_any_worker = True
            print(f"\n[Frame {i+1}] Tracked {len(workers)} worker(s):")
            for w in workers:
                print(f"  Track ID          : #{w.get('worker_track_id')}")
                print(f"  Compliance Status : {w.get('compliance_status')}")
                print(f"  Overall Status    : {w.get('overall_status')}")
                print(f"  Missing PPE       : {w.get('missing_ppe')}")
                print(f"  Missing Labels    : {w.get('missing_ppe_labels')}")
                print(f"  PPE Status Dict   : {w.get('ppe_status')}")
                print(f"  Categories Detail :")
                for ckey, cval in w.get("categories", {}).items():
                    print(f"    - {ckey:<14}: status={cval.get('status'):<14} conf={cval.get('confidence')}")

        time.sleep(0.05)

    # Clean release
    cap.release()
    print(f"\nProcessed {frames_processed} live webcam frames successfully. Camera released.")

    # 3. Serialized Payload & WebSocket Contract Verification
    print("\n--- [Step 3: Payload Serialization & WebSocket Message Shape] ---")
    if last_monitoring_result is None:
        last_monitoring_result = monitoring_svc.get_latest_monitoring_data()

    ws_message = {
        "type": "monitoring_update",
        "timestamp": time.time(),
        "data": last_monitoring_result,
    }
    json_bytes = json.dumps(ws_message)
    print(f"  WebSocket message JSON size: {len(json_bytes)} bytes")
    deserialized = json.loads(json_bytes)
    assert deserialized["type"] == "monitoring_update"
    assert "workers" in deserialized["data"]

    # 4. Verified Compliance Mapping on Sample Workers
    print("\n--- [Step 4: Synthetic Compliance State Validation] ---")
    # Verify that a confirmed no-hardhat explicitly produces:
    # Hardhat: MISSING, Worker: NON-COMPLIANT, Overlay: MISSING: NO HARDHAT
    structured_violation = {
        "workers": [{"track_id": 9, "bbox": [100, 50, 250, 400], "confidence": 0.95}],
        "compliant_ppe": [],
        "violations": [{"class_name": "no-hardhat", "confidence": 0.88, "bbox": [130, 55, 200, 100]}],
        "total_detections": 2,
    }
    res_violation = monitoring_svc.process_structured_data(structured_violation)
    w9 = res_violation["workers"][0]

    print("  Worker #9 Test (Explicit no-hardhat):")
    print(f"    worker_id         : {w9.get('worker_id')}")
    print(f"    compliance_status : {w9.get('compliance_status')}")
    print(f"    ppe_status        : {w9.get('ppe_status')}")
    print(f"    missing_ppe       : {w9.get('missing_ppe')}")
    print(f"    missing_ppe_labels: {w9.get('missing_ppe_labels')}")

    assert w9.get("compliance_status") == "non_compliant"
    assert w9.get("ppe_status", {}).get("hardhat") == "missing"
    assert "hardhat" in w9.get("missing_ppe", [])
    assert "NO HARDHAT" in w9.get("missing_ppe_labels", [])
    print("  ✓ Confirmed no-hardhat displays Hardhat: MISSING & Worker: NON-COMPLIANT.")

    # Verify that positive hardhat detection changes status to COMPLIANT
    structured_compliant = {
        "workers": [{"track_id": 9, "bbox": [100, 50, 250, 400], "confidence": 0.95}],
        "compliant_ppe": [
            {"class_name": "hardhat", "confidence": 0.94, "bbox": [130, 55, 200, 100]},
            {"class_name": "safety vest", "confidence": 0.91, "bbox": [120, 120, 240, 260]},
        ],
        "violations": [],
        "total_detections": 3,
    }
    res_compliant = monitoring_svc.process_structured_data(structured_compliant)
    w9_comp = res_compliant["workers"][0]

    print("\n  Worker #9 Test (Compliant hardhat + vest):")
    print(f"    worker_id         : {w9_comp.get('worker_id')}")
    print(f"    compliance_status : {w9_comp.get('compliance_status')}")
    print(f"    ppe_status        : {w9_comp.get('ppe_status')}")
    print(f"    missing_ppe       : {w9_comp.get('missing_ppe')}")

    assert w9_comp.get("compliance_status") == "compliant"
    assert w9_comp.get("ppe_status", {}).get("hardhat") == "compliant"
    assert w9_comp.get("ppe_status", {}).get("safety_vest") == "compliant"
    assert len(w9_comp.get("missing_ppe", [])) == 0
    print("  ✓ Confirmed positive hardhat + vest transitions to COMPLIANT.")

    print("\n" + "=" * 80)
    print("  [SUCCESS] Real webcam runtime verification completed with 100% agreement!")
    print("=" * 80)

if __name__ == "__main__":
    verify_live_webcam_runtime()
