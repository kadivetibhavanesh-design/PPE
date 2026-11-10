import os
import sys
import time
import json
import psutil
import cv2
import numpy as np

# Ensure root & backend are in sys.path
sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))

from app.services.video_service import VideoCaptureService
from app.services.model_registry import (
    MODEL_CONSTRUCTELLIGENCE,
    MODEL_VYRA,
    get_model_profile,
    get_active_model_id,
)
from app.services.model_service import switch_model, get_model
from app.services.detection_service import process_detections
from app.services.ppe_association_service import PPEAssociationService
from app.services.ppe_compliance_service import PPEComplianceService
from app.services.annotation_service import annotate_frame


def benchmark_model_on_webcam(model_id: str, cap: VideoCaptureService, num_frames: int = 15):
    print(f"\n--- Benchmarking Model: {model_id.upper()} ({get_model_profile(model_id).display_name}) ---")
    process = psutil.Process(os.getpid())
    mem_before_mb = process.memory_info().rss / (1024 * 1024)

    t0_switch = time.time()
    info = switch_model(model_id)
    t_switch = time.time() - t0_switch
    print(f"  * Model Switch & Load Time : {t_switch:.2f} s")
    print(f"  * Total Model Classes      : {info['num_classes']}")
    print(f"  * Memory RSS After Load    : {process.memory_info().rss / (1024 * 1024):.1f} MB (Delta: +{process.memory_info().rss / (1024 * 1024) - mem_before_mb:.1f} MB)")

    model = get_model()
    assoc_svc = PPEAssociationService()
    comp_svc = PPEComplianceService()

    inference_times = []
    total_frame_times = []
    detections_summary = {}

    print(f"  * Capturing and processing {num_frames} frames from webcam...")
    for f_idx in range(num_frames):
        t_f_start = time.time()
        ret, frame = cap.read_frame()
        if not ret or frame is None:
            time.sleep(0.02)
            continue

        # Run inference
        t_inf_start = time.time()
        results = model.track(
            source=frame,
            persist=True,
            tracker="bytetrack.yaml",
            device="cpu",
            conf=0.20,
            imgsz=640,
            verbose=False,
        )
        t_inf = (time.time() - t_inf_start) * 1000.0  # ms
        inference_times.append(t_inf)

        # Parse & structure
        structured = process_detections(results, model.names)
        for det in structured.get("all_detections", []):
            cls_name = det.get("class_name")
            conf = det.get("confidence")
            detections_summary.setdefault(cls_name, []).append(round(conf, 3))

        # Spatial Association & Compliance
        assoc_result = assoc_svc.associate(structured_detections=structured)
        active_track_ids = [w["track_id"] for w in structured.get("workers", []) if w.get("track_id") is not None]
        comp_result = comp_svc.evaluate_all(assoc_result["associations"], active_track_ids)

        t_total = (time.time() - t_f_start) * 1000.0
        total_frame_times.append(t_total)
        time.sleep(0.01)

    mem_after_mb = process.memory_info().rss / (1024 * 1024)
    avg_inf = sum(inference_times) / len(inference_times) if inference_times else 0.0
    avg_total = sum(total_frame_times) / len(total_frame_times) if total_frame_times else 0.0
    fps = 1000.0 / avg_total if avg_total > 0 else 0.0

    print(f"  * Avg YOLO Inference Latency : {avg_inf:.2f} ms")
    print(f"  * Avg End-to-End Latency     : {avg_total:.2f} ms")
    print(f"  * Effective Processing Rate  : {fps:.1f} FPS")
    print(f"  * Peak Memory RSS            : {mem_after_mb:.1f} MB")
    print(f"  * Raw Detections Encountered :")
    for k, v in detections_summary.items():
        print(f"      - '{k}': {len(v)} occurrences (conf min={min(v):.2f}, max={max(v):.2f}, avg={sum(v)/len(v):.2f})")

    return {
        "model_id": model_id,
        "display_name": info["display_name"],
        "switch_time_s": round(t_switch, 2),
        "avg_inference_ms": round(avg_inf, 2),
        "avg_total_ms": round(avg_total, 2),
        "effective_fps": round(fps, 1),
        "memory_mb": round(mem_after_mb, 1),
        "detections_count": sum(len(v) for v in detections_summary.values()),
        "distinct_classes_seen": list(detections_summary.keys()),
    }


def main():
    print("=" * 80)
    print("  SafeVision AI - Comparative Webcam Benchmark: Dual YOLO Models")
    print("=" * 80)

    # 1. Initialize Video Capture Service
    print("\n[Step 1] Initializing Webcam (DirectShow)...")
    cap = VideoCaptureService(camera_index=0)
    if not cap.start():
        print("ERROR: Could not open camera")
        return

    try:
        # Benchmark Model 1: Constructelligence
        res1 = benchmark_model_on_webcam(MODEL_CONSTRUCTELLIGENCE, cap, num_frames=12)

        # Benchmark Model 2: Vyra
        res2 = benchmark_model_on_webcam(MODEL_VYRA, cap, num_frames=12)

        # Restore default model
        switch_model(MODEL_CONSTRUCTELLIGENCE)

        # Comparison Summary
        print("\n" + "=" * 80)
        print("  COMPARATIVE PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)
        print(f"{'Metric':<30} | {'Constructelligence':<22} | {'Vyra':<22}")
        print("-" * 80)
        print(f"{'Model Architecture':<30} | {'YOLOv8 Hazard':<22} | {'YOLOv8 Vyra PPE':<22}")
        print(f"{'Model Weights':<30} | {'buildvision (22.5 MB)':<22} | {'best.pt (6.3 MB)':<22}")
        print(f"{'Positive Mask Support':<30} | {'No (Violation only)':<22} | {'Yes (Compliant & Viol)':<22}")
        s_inf1 = f"{res1['avg_inference_ms']} ms"
        s_inf2 = f"{res2['avg_inference_ms']} ms"
        print(f"{'Avg Inference Time (CPU)':<30} | {s_inf1:<22} | {s_inf2:<22}")
        s_tot1 = f"{res1['avg_total_ms']} ms"
        s_tot2 = f"{res2['avg_total_ms']} ms"
        print(f"{'Total Frame Latency':<30} | {s_tot1:<22} | {s_tot2:<22}")
        s_fps1 = f"{res1['effective_fps']} FPS"
        s_fps2 = f"{res2['effective_fps']} FPS"
        print(f"{'Effective FPS':<30} | {s_fps1:<22} | {s_fps2:<22}")
        s_mem1 = f"{res1['memory_mb']} MB"
        s_mem2 = f"{res2['memory_mb']} MB"
        print(f"{'Process Memory RSS':<30} | {s_mem1:<22} | {s_mem2:<22}")
        print("=" * 80)

        # Save to json file
        with open("backend/dual_model_benchmark_results.json", "w") as f:
            json.dump({"constructelligence": res1, "vyra": res2}, f, indent=2)
        print("Benchmark results saved to 'backend/dual_model_benchmark_results.json'.")

    finally:
        cap.release()
        print("Webcam hardware released cleanly.")


if __name__ == "__main__":
    main()
