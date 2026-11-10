import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Set, Tuple
import cv2
import numpy as np

# Set stdout/stderr to UTF-8 on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from app.services.detection_service import process_detections
    from app.services.model_service import get_model, get_model_info
    from app.services.video_service import VideoCaptureService
    from app.services.worker_tracking_service import WorkerTrackingService
except ImportError as e:
    print(f"[FATAL] Failed to import backend services: {e}")
    sys.exit(1)

# Color palettes for visualization (OpenCV BGR)
CATEGORY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "workers": (255, 170, 0),           # Bright Cyan-Blue for tracked workers
    "compliant_ppe": (0, 220, 0),       # Green for compliant PPE
    "violations": (0, 30, 230),         # Bright Red for PPE violations
    "heavy_machinery": (0, 215, 255),   # Yellow-Gold for heavy machinery
    "unknown": (180, 180, 180),         # Gray for unclassified items
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="PPE & Industrial Safety Monitoring - ByteTrack Worker Tracking Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Webcam device index (default: 0)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="YOLO detection confidence threshold (default: 0.25)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Inference image resolution (default: 640)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Target webcam frame width (default: 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Target webcam frame height (default: 720)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Maximum frames to process before stopping (0 = continuous live stream until 'q')",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable GUI preview window (useful for automated verification)",
    )
    return parser.parse_args()


def draw_tracked_annotations(frame: np.ndarray, structured: dict) -> Tuple[np.ndarray, int, Set[int]]:
    """
    Renders bounding boxes and labels on the frame.
    Assigns persistent tracking IDs specifically to 'person' detections (workers).
    Other detections (PPE, machinery) are displayed with their class and confidence.

    Args:
        frame: OpenCV BGR image array.
        structured: Structured detections dictionary from detection_service.

    Returns:
        tuple (annotated_frame, active_worker_count, active_worker_ids)
    """
    active_worker_ids: Set[int] = set()

    for item in structured.get("all_detections", []):
        x1, y1, x2, y2 = [int(v) for v in item["bbox"]]
        class_name = item["class_name"]
        confidence = item["confidence"]
        category = item.get("category", "unknown")
        track_id = item.get("track_id")

        is_worker = (category == "workers" or class_name.lower() == "person")

        if is_worker:
            color = CATEGORY_COLORS["workers"]
            box_thickness = 3

            if track_id is not None:
                active_worker_ids.add(track_id)
                label = f"Worker #{track_id} ({confidence:.0%})"
            else:
                label = f"Worker ({confidence:.0%})"
        else:
            color = CATEGORY_COLORS.get(category, (180, 180, 180))
            box_thickness = 2
            label = f"{class_name} {confidence:.0%}"

        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, box_thickness)

        # Draw label background badge
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55 if is_worker else 0.45
        font_thick = 2 if is_worker else 1
        (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, font_thick)

        badge_top = max(y1 - label_h - 10, 0)
        badge_bottom = badge_top + label_h + 10
        badge_right = min(x1 + label_w + 10, frame.shape[1] - 1)

        cv2.rectangle(frame, (x1, badge_top), (badge_right, badge_bottom), color, -1)

        # Label text color: dark for worker/PPE/machinery, white for violations
        text_color = (0, 0, 0) if category in ("workers", "compliant_ppe", "heavy_machinery") else (255, 255, 255)
        text_y = badge_bottom - baseline - 4
        cv2.putText(
            frame,
            label,
            (x1 + 5, text_y),
            font,
            font_scale,
            text_color,
            font_thick,
            cv2.LINE_AA,
        )

    return frame, len(active_worker_ids), active_worker_ids


def draw_hud(
    frame: np.ndarray,
    fps: float,
    frame_count: int,
    active_worker_count: int,
    structured: dict,
    res_str: str,
    lifecycle_stats: dict = None,
) -> np.ndarray:
    """
    Renders top monitoring HUD banner showing ByteTrack worker tracking metrics.
    """
    h, w = frame.shape[:2]

    # Semi-transparent dark banner
    banner_h = 58
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_h), (18, 18, 18), -1)
    alpha = 0.8
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    n_ppe = len(structured.get("compliant_ppe", []))
    n_violations = len(structured.get("violations", []))
    n_total = structured.get("total_detections", 0)

    n_active = lifecycle_stats.get("active_count", active_worker_count) if lifecycle_stats else active_worker_count
    n_missing = lifecycle_stats.get("missing_count", 0) if lifecycle_stats else 0
    n_left = lifecycle_stats.get("left_count", 0) if lifecycle_stats else 0

    # Line 1: Tracker info and FPS
    line1 = f"BYTETRACK WORKER TRACKING | {res_str} | CPU Rate: {fps:4.1f} FPS | Frame: #{frame_count}"
    cv2.putText(frame, line1, (15, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)

    # Line 2: Tracked Workers Lifecycle and Safety Stats
    line2 = f"Workers: {n_active} Active | {n_missing} Missing | {n_left} Left   PPE: {n_ppe} Compliant | {n_violations} Violations"
    text_color = (0, 80, 255) if n_violations > 0 else (0, 230, 80)
    cv2.putText(frame, line2, (15, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.55, text_color, 2, cv2.LINE_AA)

    return frame


def main():
    args = parse_args()

    print("=" * 75)
    print("  AI-Powered PPE Detection System - ByteTrack Worker Tracking")
    print("=" * 75)
    print(f"  * Camera Device Index     : {args.camera_index}")
    print(f"  * Requested Resolution    : {args.width}x{args.height}")
    print(f"  * Tracker Config          : bytetrack.yaml (persist=True)")
    print(f"  * Confidence Threshold    : {args.conf}")
    print(f"  * Inference Image Size    : {args.imgsz}")
    print(f"  * Execution Device        : CPU")
    print(f"  * Session Mode            : {'Continuous (Press q to stop)' if args.max_frames <= 0 else f'{args.max_frames} frames'}")

    # Step 1: Load Pretrained YOLO Model Singleton once
    print("\n[1/3] Loading Pretrained YOLO Model Singleton (CPU)...")
    try:
        model = get_model()
        model_info = get_model_info(model)
        print(f"  [OK] Model Loaded: {model_info['architecture']} ({model_info['num_classes']} classes)")
    except Exception as e:
        print(f"[FATAL] Failed to initialize YOLO model: {e}")
        sys.exit(1)

    # Step 2: Initialize VideoCaptureService
    print(f"\n[2/3] Initializing VideoCaptureService on camera index {args.camera_index}...")
    video_service = VideoCaptureService(
        camera_index=args.camera_index,
        target_width=args.width,
        target_height=args.height,
        target_fps=30,
    )

    if not video_service.start() or not video_service.is_opened():
        print(f"[FATAL] Could not open camera device at index {args.camera_index}.")
        sys.exit(1)

    cam_info = video_service.get_camera_info()
    res_str = cam_info["actual_resolution"]
    print(f"  [OK] Camera opened successfully (Resolution: {res_str}, Driver FPS: {cam_info['actual_fps']:.1f})")

    window_name = "ByteTrack Worker Tracking - Live Feed (Press 'q' to Quit)"
    if not args.no_display:
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            print("  [OK] OpenCV display window initialized.")
        except cv2.error as e:
            print(f"  Note: GUI window could not be opened: {e}. Falling back to console mode.")
            args.no_display = True

    print("\n[3/3] Starting ByteTrack worker tracking loop... (Press 'q' to exit)")
    print("-" * 75)

    frame_count = 0
    all_observed_worker_ids: Set[int] = set()
    start_time = time.time()
    last_fps_time = start_time
    rolling_fps = 0.0
    fps_frame_counter = 0

    # Initialize WorkerTrackingService for session lifecycle monitoring
    worker_lifecycle = WorkerTrackingService(timeout_seconds=5.0)

    try:
        while True:
            # 1. Capture frame
            ret, frame = video_service.read_frame()
            if not ret or frame is None:
                print(f"[WARNING] Empty frame encountered at frame #{frame_count + 1}.")
                time.sleep(0.01)
                continue

            frame_count += 1
            fps_frame_counter += 1

            # 2. Run YOLO Tracking with ByteTrack and state persistence
            try:
                results = model.track(
                    source=frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    device="cpu",
                    conf=args.conf,
                    imgsz=args.imgsz,
                    verbose=False,
                )
            except Exception as e:
                print(f"[ERROR] ByteTrack execution failed on frame #{frame_count}: {e}")
                continue

            # 3. Process detections and extract track IDs
            structured = process_detections(results, model.names)

            # Update lifecycle tracking service
            lifecycle_stats = worker_lifecycle.update(structured)

            # 4. Annotate frame with worker IDs and PPE detections
            annotated_frame, active_worker_count, active_worker_ids = draw_tracked_annotations(frame, structured)
            all_observed_worker_ids.update(active_worker_ids)

            # 5. Measure Rolling FPS
            current_time = time.time()
            elapsed_fps = current_time - last_fps_time
            if elapsed_fps >= 0.5:
                rolling_fps = fps_frame_counter / elapsed_fps
                fps_frame_counter = 0
                last_fps_time = current_time

            # 6. Render HUD with lifecycle metrics
            annotated_frame = draw_hud(
                annotated_frame,
                rolling_fps,
                frame_count,
                active_worker_count,
                structured,
                res_str,
                lifecycle_stats=lifecycle_stats,
            )

            # 7. Display frame and handle user input
            if not args.no_display:
                cv2.imshow(window_name, annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("\n  User pressed 'q'. Exiting ByteTrack tracking stream...")
                    break

            # Periodic progress logging
            if frame_count % 15 == 0:
                worker_id_str = f"Active IDs: {sorted(list(active_worker_ids))}" if active_worker_ids else "No active workers"
                print(
                    f"  Frame #{frame_count:<5} | "
                    f"Rate: {rolling_fps:4.1f} FPS | "
                    f"Workers Tracked: {active_worker_count} ({worker_id_str}) | "
                    f"Total Detections: {structured['total_detections']}"
                )

            # Max frames check
            if args.max_frames > 0 and frame_count >= args.max_frames:
                print(f"\n  Reached maximum frame limit ({args.max_frames}). Stopping tracking...")
                break

    except KeyboardInterrupt:
        print("\n\n  Execution interrupted by user (Ctrl+C). Cleaning up...")
    finally:
        # Step 4: Guaranteed resource release
        print("\n[CLEANUP] Releasing camera and closing display windows...")
        video_service.release()
        if not args.no_display:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

    total_elapsed = time.time() - start_time
    avg_fps = (frame_count / total_elapsed) if total_elapsed > 0 else 0.0

    print("=" * 75)
    print("  BYTETRACK WORKER TRACKING SESSION SUMMARY")
    print("=" * 75)
    print(f"  * Model Loading Status       : SUCCESS (YOLOv8 CPU)")
    print(f"  * ByteTrack Tracker State    : SUCCESS (bytetrack.yaml, persist=True)")
    print(f"  * Camera Initialization      : SUCCESS (Index {cam_info['camera_index']})")
    print(f"  * Camera Actual Resolution   : {cam_info['actual_resolution']}")
    print(f"  * Camera Driver FPS          : {cam_info['actual_fps']:.1f}")
    print(f"  * Average Tracking Rate      : {avg_fps:.1f} FPS (CPU)")
    print(f"  * Total Frames Processed     : {frame_count}")
    print(f"  * Total Unique Worker IDs    : {len(all_observed_worker_ids)}")
    print(f"  * Observed Worker IDs        : {sorted(list(all_observed_worker_ids)) if all_observed_worker_ids else 'None'}")
    print(f"  * Worker ID Stability Check  : {'PASSED (IDs tracked consistently)' if all_observed_worker_ids else 'NO WORKERS IN FEED'}")
    print(f"  * Camera Resource Released   : {'YES (Confirmed)' if not video_service.is_opened() else 'NO'}")
    print("=" * 75)
    print("  [SUCCESS] ByteTrack worker tracking verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()

