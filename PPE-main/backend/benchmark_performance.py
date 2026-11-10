import os
import sys
import time
import json
import psutil

# Ensure UTF-8 console output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))

from app.services.video_service import VideoCaptureService
from app.services.ppe_monitoring_service import PPEMonitoringService
from app.services.annotation_service import annotate_frame
import cv2

def run_performance_benchmarks():
    print("=" * 80)
    print("  SafeVision AI - End-to-End Performance Benchmarking")
    print("=" * 80)

    process = psutil.Process(os.getpid())
    initial_mem_mb = process.memory_info().rss / (1024 * 1024)
    print(f"  Initial Process Memory: {initial_mem_mb:.1f} MB")

    # 1. Camera Startup Benchmark
    print("\n--- 1. Camera Hardware Startup Benchmark ---")
    t0 = time.time()
    cap = VideoCaptureService(camera_index=0)
    opened = cap.start()
    t_camera_start = time.time() - t0
    print(f"  * Backend Camera Startup Time : {t_camera_start:.2f} s")
    print(f"  * Hardware Resolution         : {cap._actual_width}x{cap._actual_height} @ {cap._actual_fps:.1f} FPS")
    assert opened is True, "Camera failed to open"

    # 2. Pipeline Initialization & Model Loading
    print("\n--- 2. YOLO Model Initialization ---")
    t0 = time.time()
    service = PPEMonitoringService()
    _ = service.model  # Trigger lazy load
    t_model_load = time.time() - t0
    print(f"  * Model Load & Warmup Time    : {t_model_load:.2f} s")

    # 3. Continuous Monitoring Loop Benchmark (30 frames)
    print("\n--- 3. Continuous Video Pipeline Benchmark (30 Frames) ---")
    inference_times = []
    annotation_times = []
    total_frame_times = []
    cpu_measurements = []

    for frame_idx in range(30):
        t_frame_start = time.time()
        ret, frame = cap.read_frame()
        if not ret or frame is None:
            time.sleep(0.01)
            continue

        # Pipeline inference & compliance
        t_infer_start = time.time()
        result = service.process_frame(frame, timestamp=t_infer_start)
        t_infer = (time.time() - t_infer_start) * 1000.0  # ms
        inference_times.append(t_infer)

        # Annotation & JPEG encoding
        t_ann_start = time.time()
        annotated = annotate_frame(frame, result, fps=30.0)
        success, buf = cv2.imencode('.jpg', annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        t_ann = (time.time() - t_ann_start) * 1000.0  # ms
        annotation_times.append(t_ann)

        t_total = (time.time() - t_frame_start) * 1000.0
        total_frame_times.append(t_total)

        cpu_measurements.append(process.cpu_percent(interval=None))
        time.sleep(0.01)

    cap.release()
    print("  * Physical webcam released cleanly.")

    # Calculate statistics
    avg_infer_ms = sum(inference_times) / len(inference_times) if inference_times else 0.0
    avg_ann_ms = sum(annotation_times) / len(annotation_times) if annotation_times else 0.0
    avg_total_ms = sum(total_frame_times) / len(total_frame_times) if total_frame_times else 0.0
    effective_fps = 1000.0 / avg_total_ms if avg_total_ms > 0 else 0.0

    final_mem_mb = process.memory_info().rss / (1024 * 1024)
    avg_cpu = sum(cpu_measurements) / len(cpu_measurements) if cpu_measurements else 0.0

    print("\n--- 4. Benchmarking Summary ---")
    print(f"  * Average YOLO Inference Time : {avg_infer_ms:.2f} ms")
    print(f"  * Average Annotation + Encode : {avg_ann_ms:.2f} ms")
    print(f"  * Average Total Frame Latency : {avg_total_ms:.2f} ms")
    print(f"  * Effective Processing Rate   : {effective_fps:.1f} FPS")
    print(f"  * Average CPU Utilization    : {avg_cpu:.1f} %")
    print(f"  * Memory RSS (Start -> End)   : {initial_mem_mb:.1f} MB -> {final_mem_mb:.1f} MB (Delta: +{final_mem_mb - initial_mem_mb:.1f} MB)")

    # Save benchmark results to JSON
    benchmark_data = {
        "camera_startup_time_s": round(t_camera_start, 2),
        "model_load_time_s": round(t_model_load, 2),
        "avg_inference_time_ms": round(avg_infer_ms, 2),
        "avg_annotation_encode_time_ms": round(avg_ann_ms, 2),
        "avg_total_frame_latency_ms": round(avg_total_ms, 2),
        "effective_fps": round(effective_fps, 1),
        "avg_cpu_percent": round(avg_cpu, 1),
        "initial_memory_mb": round(initial_mem_mb, 1),
        "final_memory_mb": round(final_mem_mb, 1),
        "memory_growth_mb": round(final_mem_mb - initial_mem_mb, 1),
    }

    with open("backend/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print("\n  Benchmark results persisted to 'backend/benchmark_results.json'.")
    print("=" * 80)

if __name__ == "__main__":
    run_performance_benchmarks()

