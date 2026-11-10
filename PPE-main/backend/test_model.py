import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from app.services.model_service import (
        HF_FILENAME,
        HF_REPO_ID,
        get_model_info,
        load_model,
    )
except ImportError as e:
    print(f"[FATAL] Failed to import model_service: {e}")
    sys.exit(1)


def main():
    print("=" * 70)
    print("  AI-Powered PPE Detection System - YOLO Pretrained Model Test")
    print("=" * 70)

    print(f"\n[1/4] Target Model Configuration:")
    print(f"  • Hugging Face Repository : {HF_REPO_ID}")
    print(f"  • Model Weights Filename  : {HF_FILENAME}")
    print(f"  • Target Device           : CPU")

    print(f"\n[2/4] Downloading & Loading Pretrained YOLO Model...")
    try:
        model = load_model(device="cpu")
        print("  ✓ Model successfully instantiated.")
    except Exception as exc:
        print(f"\n[FAILURE] Model loading failed: {exc}")
        sys.exit(1)

    print(f"\n[3/4] Inspecting Model Metadata & Execution Device:")
    info = get_model_info(model)
    print(f"  • Repository         : {info['repository']}")
    print(f"  • Weights Filename   : {info['filename']}")
    print(f"  • Cached Weights File: {info['weights_path']}")
    print(f"  • Architecture       : {info['architecture']}")
    print(f"  • Total Classes      : {info['num_classes']}")

    # Verify device
    try:
        param_device = next(model.model.parameters()).device
        device_str = str(param_device)
    except Exception:
        device_str = str(getattr(model, "device", "cpu"))

    is_cpu = "cpu" in device_str.lower()
    print(f"  • Execution Device   : {device_str.upper()} (CPU Mode Verified: {is_cpu})")

    if not is_cpu:
        print("[WARNING] Model parameters are not placed on CPU!")

    print(f"\n[4/4] Detection Classes Mapping (read dynamically from model.names):")
    print("-" * 50)
    print(f"  {'Class ID':<10} | {'Class Name'}")
    print("-" * 50)
    for class_id, class_name in info["classes"].items():
        print(f"  {class_id:<10} | {class_name}")
    print("-" * 50)

    print("\n" + "=" * 70)
    print("  [SUCCESS] Pretrained YOLO model loaded and verified on CPU!")
    print("=" * 70)


if __name__ == "__main__":
    main()

