import json
import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from app.services.model_service import get_model
    from app.services.detection_service import process_detections
except ImportError as e:
    print(f"[FATAL] Import error: {e}")
    sys.exit(1)


def test_empty_results():
    print("\n--- [Test 1] Testing Empty / Edge-Case Inputs ---")
    
    # Test None input
    res_none = process_detections(None)
    assert res_none["total_detections"] == 0, "Failed: None input should yield 0 detections"
    assert isinstance(res_none["workers"], list) and len(res_none["workers"]) == 0
    print("  ✓ Handled None input successfully.")

    # Test empty list input
    res_empty_list = process_detections([])
    assert res_empty_list["total_detections"] == 0, "Failed: Empty list should yield 0 detections"
    print("  ✓ Handled empty list input successfully.")

    # Test dummy object without boxes
    class DummyResult:
        boxes = None
        names = {0: "person"}

    res_dummy = process_detections(DummyResult())
    assert res_dummy["total_detections"] == 0, "Failed: Object with None boxes should yield 0 detections"
    print("  ✓ Handled result object with no boxes successfully.")


def test_sample_image_inference():
    print("\n--- [Test 2] Testing Inference & Structuring on Sample Image ---")

    sample_path = PROJECT_ROOT / "storage" / "sample_construction.jpg"
    if not sample_path.exists():
        # Fallback to assets if needed
        import ultralytics.utils
        assets_dir = Path(ultralytics.utils.ASSETS)
        sample_path = assets_dir / "bus.jpg"
        print(f"  Note: Using fallback image: {sample_path}")

    print(f"  • Sample Image: {sample_path}")

    # 1. Load model
    model = get_model()
    assert model is not None, "Model failed to load"
    print("  ✓ YOLO model loaded via get_model()")

    # 2. Run inference
    results = model.predict(
        source=str(sample_path),
        device="cpu",
        conf=0.25,
        verbose=False,
    )
    assert results is not None and len(results) > 0, "Prediction returned no results"
    print("  ✓ YOLO inference completed on CPU")

    # 3. Process detections
    structured = process_detections(results, model.names)

    # 4. Validate output schema
    required_keys = [
        "total_detections",
        "workers",
        "compliant_ppe",
        "violations",
        "heavy_machinery",
        "all_detections",
    ]
    for key in required_keys:
        assert key in structured, f"Missing key '{key}' in structured output"

    assert structured["total_detections"] == len(structured["all_detections"]), \
        "total_detections does not match length of all_detections"

    categorized_count = (
        len(structured["workers"])
        + len(structured["compliant_ppe"])
        + len(structured["violations"])
        + len(structured["heavy_machinery"])
        + len(structured.get("unknown", []))
    )
    assert categorized_count == structured["total_detections"], \
        f"Categorized sum ({categorized_count}) != total ({structured['total_detections']})"

    print("  ✓ Output schema and category counts validated")

    # 5. Display detailed results
    print("\n" + "=" * 75)
    print("  CATEGORIZED DETECTION SUMMARY")
    print("=" * 75)
    print(f"  • Total Detections   : {structured['total_detections']}")
    print(f"  • Workers Detected   : {len(structured['workers'])}")
    print(f"  • Compliant PPE      : {len(structured['compliant_ppe'])}")
    print(f"  • PPE Violations     : {len(structured['violations'])}")
    print(f"  • Heavy Machinery    : {len(structured['heavy_machinery'])}")
    if structured.get("unknown"):
        print(f"  • Unknown Detections : {len(structured['unknown'])}")
    print("=" * 75)

    categories = [
        ("Workers", structured["workers"]),
        ("Compliant PPE", structured["compliant_ppe"]),
        ("PPE Violations", structured["violations"]),
        ("Heavy Machinery", structured["heavy_machinery"]),
    ]

    for title, items in categories:
        if items:
            print(f"\n  [{title}] ({len(items)} items):")
            for idx, item in enumerate(items, 1):
                print(
                    f"    {idx}. Class: '{item['class_name']}' (ID: {item['class_id']}) "
                    f"| Conf: {item['confidence']:.2%} "
                    f"| Box: {item['bbox']} "
                    f"| Center: ({item['center_x']}, {item['center_y']}) "
                    f"| Size: {item['width']}x{item['height']}"
                )

    print("\n" + "-" * 75)
    print("  Sample Formatted JSON Output (first detection):")
    if structured["all_detections"]:
        sample_item = structured["all_detections"][0]
        print(json.dumps(sample_item, indent=4))
    else:
        print("  (No detections to display)")
    print("-" * 75)

    return structured


def main():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - Detection Service Unit Test")
    print("=" * 75)

    test_empty_results()
    test_sample_image_inference()

    print("\n" + "=" * 75)
    print("  [SUCCESS] All detection processing tests passed successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()

