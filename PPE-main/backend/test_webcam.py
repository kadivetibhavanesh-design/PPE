
import argparse
import sys
import time
from pathlib import Path
import cv2

# Set stdout/stderr to UTF-8 on Windows terminals if possible
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
    from app.services.video_service import VideoCaptureService
except ImportError as e:
    print(f"[FATAL] Failed to import VideoCaptureService: {e}")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="PPE & Industrial Safety Monitoring - Live Webcam Capture Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Webcam device index (default: 0)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Target frame width (default: 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Target frame height (default: 720)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target frame rate (default: 30)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Optional maximum number of frames to capture before auto-exiting (0 = run indefinitely until 'q')",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Disable GUI preview window (useful for headless verification)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 75)
    print("  AI-Powered PPE Detection System - Live Webcam Capture Test")
    print("=" * 75)
    print(f"  * Requested Camera Index : {args.camera_index}")
    print(f"  * Requested Resolution   : {args.width}x{args.height}")
    print(f"  * Requested Target FPS   : {args.fps}")
    print(f"  * Max Frames Mode        : {'Unlimited (Press q to stop)' if args.max_frames <= 0 else f'{args.max_frames} frames'}")

    # Step 1: Initialize service
    print("\n[1/4] Initializing VideoCaptureService...")
    video_service = VideoCaptureService(
        camera_index=args.camera_index,
        target_width=args.width,
        target_height=args.height,
        target_fps=args.fps,
    )

    # Step 2: Open webcam
    print(f"[2/4] Opening webcam device at index {args.camera_index}...")
    success = video_service.start()
    if not success or not video_service.is_opened():
        print(f"\n[ERROR] Failed to open webcam at index {args.camera_index}.")
        print("Please verify that:")
        print("  1. A webcam is connected/integrated.")
        print("  2. Camera privacy permissions are granted in Windows Settings.")
        print("  3. No other application (Teams, Zoom, browser) is exclusively locking the webcam.")
        sys.exit(1)

    info = video_service.get_camera_info()
    print("  [OK] Webcam opened successfully!")
    print(f"  * Hardware Actual Resolution : {info['actual_resolution']}")
    print(f"  * Hardware Reported FPS      : {info['actual_fps']:.1f}")

    window_name = "Live Webcam Feed - PPE Monitoring System (Press 'q' to Quit)"
    if not args.no_display:
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            print("  [OK] OpenCV display window created.")
        except cv2.error as e:
            print(f"  Note: GUI window could not be created: {e}. Falling back to console mode.")
            args.no_display = True

    print("\n[3/4] Streaming live frames... (Press 'q' in video window or Ctrl+C to stop)")
    print("-" * 75)

    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    measured_fps = 0.0
    fps_frame_counter = 0

    try:
        while True:
            ret, frame = video_service.read_frame()

            if not ret or frame is None:
                print(f"[WARNING] Failed or empty frame received at frame #{frame_count + 1}.")
                time.sleep(0.01)
                continue

            frame_count += 1
            fps_frame_counter += 1

            # Compute real-time rolling FPS every 0.5s
            current_time = time.time()
            elapsed_since_last_fps = current_time - last_fps_time
            if elapsed_since_last_fps >= 0.5:
                measured_fps = fps_frame_counter / elapsed_since_last_fps
                fps_frame_counter = 0
                last_fps_time = current_time

            # Overlay HUD stats on frame for display
            if not args.no_display:
                h, w = frame.shape[:2]
                hud_text = f"Live Feed | Res: {w}x{h} | FPS: {measured_fps:.1f} | Frame: #{frame_count}"
                
                # Dark banner background for high readability
                cv2.rectangle(frame, (10, 10), (520, 50), (20, 20, 20), -1)
                cv2.putText(
                    frame,
                    hud_text,
                    (20, 37),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 200),
                    2,
                    cv2.LINE_AA,
                )

                cv2.imshow(window_name, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("\n  'q' key pressed by user. Terminating camera feed...")
                    break

            # Print console progress every 30 frames
            if frame_count % 30 == 0:
                print(f"  Captured Frame #{frame_count:<5} | Measured FPS: {measured_fps:5.1f} | Resolution: {info['actual_resolution']}")

            # Check max frames condition
            if args.max_frames > 0 and frame_count >= args.max_frames:
                print(f"\n  Reached maximum requested frame count ({args.max_frames}). Terminating feed...")
                break

    except KeyboardInterrupt:
        print("\n\n  Capture interrupted by user (Ctrl+C). Stopping...")
    finally:
        # Step 4: Guaranteed resource release
        print("\n[4/4] Cleaning up resources...")
        video_service.release()
        if not args.no_display:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

    total_elapsed = time.time() - start_time
    avg_fps = (frame_count / total_elapsed) if total_elapsed > 0 else 0.0

    print("=" * 75)
    print("  WEBCAM CAPTURE SESSION SUMMARY")
    print("=" * 75)
    print(f"  * Initialization Status    : SUCCESS")
    print(f"  * Device Index             : {info['camera_index']}")
    print(f"  * Actual Frame Resolution  : {info['actual_resolution']}")
    print(f"  * Camera Driver FPS        : {info['actual_fps']:.1f}")
    print(f"  * Average Measured FPS     : {avg_fps:.1f}")
    print(f"  * Total Frames Captured    : {frame_count}")
    print(f"  * Session Duration         : {total_elapsed:.2f} seconds")
    print(f"  * Camera Resource Released : {'YES (Confirmed)' if not video_service.is_opened() else 'NO'}")
    print("=" * 75)
    print("  [SUCCESS] Webcam capture verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
