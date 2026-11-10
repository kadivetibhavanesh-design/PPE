import argparse
import os
import sys
from pathlib import Path
import cv2

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from app.services.model_service import get_model, get_model_info
except ImportError as e:
    print(f"[FATAL] Failed to import model_service: {e}")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="PPE & Industrial Safety Monitoring - YOLO Image Inference Test",
        epilog="Example:\n  .\\.venv\\Scripts\\python.exe backend\\test_inference.py storage\\sample_construction.jpg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "image_path",
        nargs="?",
        default=None,
        help="Path to the input image file (JPEG, PNG, WebP, etc.)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold for detections (default: 0.25)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="storage/evidence/image_inference_result.jpg",
        help="Path to save the annotated output image (default: storage/evidence/image_inference_result.jpg)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open an OpenCV desktop GUI window to display the annotated image",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Step 1: Validate argument presence
    if not args.image_path:
        print("\n" + "=" * 70)
        print("  [ERROR] No image path provided.")
        print("=" * 70)
        print("\nUsage:")
        print("  .\\.venv\\Scripts\\python.exe backend\\test_inference.py <IMAGE_PATH> [--conf 0.25] [--show]")
        print("\nExample:")
        print("  .\\.venv\\Scripts\\python.exe backend\\test_inference.py storage\\sample_construction.jpg")
        print("\nPlease provide a valid image path to run inference.\n")
        sys.exit(1)

    image_path = Path(args.image_path)

    # Step 2: Validate file existence
    if not image_path.is_file():
        print(f"\n[ERROR] File not found: '{image_path}'")
        print("Please check the path and try again.")
        sys.exit(1)

    print("=" * 70)
    print("  AI-Powered PPE Detection System - Image Inference Test")
    print("=" * 70)
    print(f"  • Input Image   : {image_path.resolve()}")
    print(f"  • Confidence    : {args.conf}")
    print(f"  • Execution Dev : CPU")

    # Step 3: Load image using OpenCV
    print("\n[1/4] Loading image with OpenCV...")
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        print(f"[ERROR] Could not decode image at '{image_path}'.")
        print("Supported formats include: .jpg, .jpeg, .png, .bmp, .webp")
        sys.exit(1)

    h, w, c = image_bgr.shape
    print(f"  ✓ Image loaded successfully (Dimensions: {w}x{h}, Channels: {c})")

    # Step 4: Load YOLO model singleton
    print("\n[2/4] Loading YOLO model via model_service...")
    try:
        model = get_model()
        model_info = get_model_info(model)
        print(f"  ✓ Model loaded: {model_info['architecture']} ({model_info['num_classes']} classes)")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        sys.exit(1)

    # Step 5: Run inference on CPU
    print(f"\n[3/4] Running YOLO inference on CPU (conf={args.conf})...")
    try:
        results = model.predict(
            source=image_bgr,
            device="cpu",
            conf=args.conf,
            verbose=False,
        )
    except Exception as e:
        print(f"[ERROR] Inference execution failed: {e}")
        sys.exit(1)

    result = results[0]
    boxes = result.boxes

    # Step 6: Extract & Display detection details
    print("\n[4/4] Detection Results:")
    print("-" * 75)
    print(f"  {'#':<4} | {'Class ID':<8} | {'Class Name':<18} | {'Conf':<8} | {'Bounding Box [x1, y1, x2, y2]'}")
    print("-" * 75)

    num_detections = len(boxes) if boxes is not None else 0
    if num_detections == 0:
        print("  No objects detected above the confidence threshold.")
    else:
        for idx, box in enumerate(boxes, start=1):
            cls_id = int(box.cls[0].item())
            cls_name = model.names.get(cls_id, f"unknown_{cls_id}")
            conf = float(box.conf[0].item())
            x1, y1, x2, y2 = [round(float(coord), 1) for coord in box.xyxy[0].tolist()]

            print(f"  {idx:<4} | {cls_id:<8} | {cls_name:<18} | {conf:.2%}   | [{x1}, {y1}, {x2}, {y2}]")

    print("-" * 75)
    print(f"  Total Detections: {num_detections}")

    # Step 7: Generate and save annotated image
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    annotated_img = result.plot()
    success = cv2.imwrite(str(output_path), annotated_img)

    if success and output_path.is_file():
        file_size_kb = output_path.stat().st_size / 1024
        print(f"\n  ✓ Annotated image saved successfully to:")
        print(f"    -> {output_path.resolve()} ({file_size_kb:.1f} KB)")
    else:
        print(f"\n  [ERROR] Failed to write annotated image to: {output_path}")
        sys.exit(1)

    # Step 8: Display annotated image when possible
    if args.show:
        try:
            print("\n  Opening display window (press any key to close)...")
            cv2.imshow("PPE Detection Result", annotated_img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except cv2.error as e:
            print(f"  Note: GUI window could not be opened: {e}")

    print("\n" + "=" * 70)
    print("  [SUCCESS] Image inference test completed successfully!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

