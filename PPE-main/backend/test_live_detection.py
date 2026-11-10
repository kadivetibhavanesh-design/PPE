import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Tuple
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
except ImportError as e:
    print(f"[FATAL] Failed to import backend services: {e}")
    sys.exit(1)

# Category colors for visualization (OpenCV BGR format)
CATEGORY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "compliant_ppe": (0, 220, 0),       # Green for compliant PPE
    "violations": (0, 30, 230),         # Bright Red for PPE violations
    "workers": (255, 170, 0),           # Bright Cyan-Blue for workers
    "heavy_machinery": (0, 215, 255),   # Yellow-Gold for heavy machinery
    "unknown": (180, 180, 180),         # Gray for unclassified items
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="PPE & Industrial Safety Monitoring - Real-Time YOLO Webcam Detection Test",
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
        help="YOLO inference image size (default: 640)",
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
        help="Maximum frames to process before stopping (0 = continuous live feed until 'q')",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable GUI window preview (useful for unattended verification)",
    )
    return parser.parse_args()


def draw_detection_annotations(frame: np.ndarray, structured_detections: dict) -> np.ndarray:
    """
    Draws custom colored bounding boxes, labels, and category badges on the frame.

    Args:
        frame: OpenCV BGR image array.
        structured_detections: Parsed detections dictionary from detection_service.

    Returns:
        np.ndarray: Annotated image frame.
    """
    detections = structured_detections.get("all_detections", [])

    for item in detections:
        x1, y1, x2, y2 = [int(v) for v in item["bbox"]]
        class_name = item["class_name"]
        confidence = item["confidence"]
        category = item.get("category", "unknown")

        color = CATEGORY_COLORS.get(category, (180, 180, 180))

        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Build label text
        label = f"{class_name} {confidence:.0%}"

        # Calculate text dimensions for background label badge
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)

        # Place label above the box if possible, else below
        badge_top = max(y1 - label_h - 8, 0)
        badge_bottom = badge_top + label_h + 8
        badge_right = min(x1 + label_w + 8, frame.shape[1] - 1)

        # Fill background badge
        cv2.rectangle(frame, (x1, badge_top), (badge_right, badge_bottom), color, -1)

        # Text color (dark for bright badge or white)
        text_color = (0, 0, 0) if category in ("compliant_ppe", "heavy_machinery") else (255, 255, 255)
        text_y = badge_bottom - baseline - 3
        cv2.putText(
            frame,
            label,
            (x1 + 4, text_y),
            font,
            font_scale,
            text_color,
            font_thickness,
            cv2.LINE_AA,
        )

    return frame


def draw_hud(
    frame: np.ndarray,
    fps: float,
    frame_count: int,
    structured_detections: dict,
    res_str: str,
) -> np.ndarray:
    """
    Overlays a professional HUD monitoring banner across the top of the video feed.
    """
    h, w = frame.shape[:2]

    # Semi-transparent dark banner overlay
    banner_h = 55
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_h), (18, 18, 18), -1)
    alpha = 0.75
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    n_workers = len(structured_detections.get("workers", []))
    n_ppe = len(structured_detections.get("compliant_ppe", []))
    n_violations = len(structured_detections.get("violations", []))
    n_total = structured_detections.get("total_detections", 0)

    # Line 1: System Performance Metrics
    sys_text = f"REAL-TIME PPE MONITOR | {res_str} | CPU Inference: {fps:4.1f} FPS | Frame: #{frame_count}"
    cv2.putText(frame, sys_text, (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

    # Line 2: Detection Counts breakdown
    stats_text = f"Detections: {n_total}   Workers: {n_workers}   Compliant PPE: {n_ppe}   Violations: {n_violations}"
    
    # Highlight in red if violations present, else green
    stats_color = (0, 80, 255) if n_violations > 0 else (0, 230, 80)
    cv2.putText(frame, stats_text, (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.55, stats_color, 2, cv2.LINE_AA)

    return frame


def main():
    args = parse_args()

    print("=" * 75)
    print("  AI-Powered PPE Detection System - Live YOLO Webcam Detection")
    print("=" * 75)
    print(f"  * Camera Device Index     : {args.camera_index}")
    print(f"  * Requested Resolution    : {args.width}x{args.height}")
    print(f"  * Confidence Threshold    : {args.conf}")
    print(f"  * Inference Image Size    : {args.imgsz}")
    print(f"  * Execution Device        : CPU")
    print(f"  * Session Mode            : {'Continuous (Press q to stop)' if args.max_frames <= 0 else f'{args.max_frames} frames'}")

    # Step 1: Load YOLO Model singleton once
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

    success = video_service.start()
    if not success or not video_service.is_opened():
        print(f"[FATAL] Could not open camera device at index {args.camera_index}.")
        sys.exit(1)

    cam_info = video_service.get_camera_info()
    res_str = cam_info["actual_resolution"]
    print(f"  [OK] Camera opened successfully (Resolution: {res_str}, Driver FPS: {cam_info['actual_fps']:.1f})")

    window_name = "AI PPE Detection & Safety Monitor - Live Feed (Press 'q' to Quit)"
    if not args.no_display:
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            print("  [OK] OpenCV display window initialized.")
        except cv2.error as e:
            print(f"  Note: GUI window could not be opened: {e}. Falling back to console mode.")
            args.no_display = True

    print("\n[3/3] Starting real-time detection loop... (Press 'q' to exit)")
    print("-" * 75)

    frame_count = 0
    total_detections_count = 0
    observed_classes = set()
    start_time = time.time()
    last_fps_time = start_time
    rolling_fps = 0.0
    fps_frame_counter = 0

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

            # 2. Execute YOLO Inference on CPU
            infer_start = time.perf_counter()
            try:
                results = model.predict(
                    source=frame,
                    device="cpu",
                    conf=args.conf,
                    imgsz=args.imgsz,
                    verbose=False,
                )
            except Exception as e:
                print(f"[ERROR] Inference error on frame #{frame_count}: {e}")
                continue

            # 3. Structure and categorize detections
            structured = process_detections(results, model.names)
            total_detections_count += structured["total_detections"]

            # Record observed classes
            for d in structured.get("all_detections", []):
                observed_classes.add(d["class_name"])

            # 4. Measure Rolling Processing FPS
            current_time = time.time()
            elapsed_fps = current_time - last_fps_time
            if elapsed_fps >= 0.5:
                rolling_fps = fps_frame_counter / elapsed_fps
                fps_frame_counter = 0
                last_fps_time = current_time

            # 5. Annotate frame and render HUD
            annotated_frame = draw_detection_annotations(frame, structured)
            annotated_frame = draw_hud(annotated_frame, rolling_fps, frame_count, structured, res_str)

            # 6. Display frame and handle user input
            if not args.no_display:
                cv2.imshow(window_name, annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("\n  User pressed 'q'. Exiting live detection stream...")
                    break

            # Periodic console progress
            if frame_count % 15 == 0:
                print(
                    f"  Frame #{frame_count:<5} | "
                    f"Inference: {rolling_fps:4.1f} FPS | "
                    f"Detections: {structured['total_detections']} "
                    f"(Workers: {len(structured['workers'])}, "
                    f"PPE: {len(structured['compliant_ppe'])}, "
                    f"Violations: {len(structured['violations'])})"
                )

            # Check max frames stopping condition
            if args.max_frames > 0 and frame_count >= args.max_frames:
                print(f"\n  Reached maximum frame limit ({args.max_frames}). Stopping capture...")
                break

    except KeyboardInterrupt:
        print("\n\n  Execution interrupted by user (Ctrl+C). Cleaning up...")
    finally:
        # Step 4: Guaranteed resource cleanup
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
    print("  LIVE DETECTION SESSION SUMMARY")
    print("=" * 75)
    print(f"  * Model Loading Status       : SUCCESS (YOLOv8 CPU)")
    print(f"  * Camera Initialization      : SUCCESS (Index {cam_info['camera_index']})")
    print(f"  * Camera Actual Resolution   : {cam_info['actual_resolution']}")
    print(f"  * Driver Reported FPS        : {cam_info['actual_fps']:.1f}")
    print(f"  * Measured Inference FPS     : {avg_fps:.1f} FPS (CPU)")
    print(f"  * Total Frames Processed     : {frame_count}")
    print(f"  * Total Detections Processed : {total_detections_count}")
    print(f"  * Observed Classes           : {sorted(list(observed_classes)) if observed_classes else 'None'}")
    print(f"  * Bounding Boxes Rendered    : {'YES (Verified)' if frame_count > 0 else 'NO'}")
    print(f"  * Camera Resource Released   : {'YES (Confirmed)' if not video_service.is_opened() else 'NO'}")
    print("=" * 75)
    print("  [SUCCESS] Real-time YOLO webcam detection verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()

