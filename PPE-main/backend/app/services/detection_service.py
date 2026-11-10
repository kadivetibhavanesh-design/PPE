import logging
from typing import Any, Dict, List, Optional, Union
import numpy as np

try:
    from app.services.model_registry import normalize_class_name
except ImportError:
    from services.model_registry import normalize_class_name

logger = logging.getLogger("ppe_monitoring.detection_service")

# Standard classification sets mapped by canonical normalized class names (never hardcoded IDs)
CATEGORY_MAPPINGS = {
    "workers": {"person"},
    "compliant_ppe": {
        "hardhat",
        "safety vest",
        "gloves",
        "safety shoes",
        "goggles",
        "mask",
    },
    "violations": {
        "no-hardhat",
        "no-safety vest",
        "no-mask",
        "no-goggles",
        "no-gloves",
        "fall-detected",
    },
    "heavy_machinery": {
        "excavator",
        "wheel loader",
        "dump truck",
        "ladder",
        "safety cone",
    },
}


def _empty_detection_structure() -> Dict[str, Any]:
    """Returns an empty structured detection response."""
    return {
        "total_detections": 0,
        "workers": [],
        "tracked_workers": [],
        "compliant_ppe": [],
        "violations": [],
        "heavy_machinery": [],
        "unknown": [],
        "all_detections": [],
    }


def categorize_class_name(class_name: str) -> str:
    """
    Categorizes a detection based on its dynamic class name.

    Args:
        class_name: Name of the detected class.

    Returns:
        str: Category key ('workers', 'compliant_ppe', 'violations', 'heavy_machinery', or 'unknown').
    """
    normalized = normalize_class_name(class_name)
    for category, name_set in CATEGORY_MAPPINGS.items():
        if normalized in name_set:
            return category
    return "unknown"


def process_detections(
    results: Any,
    model_names: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    """
    Parses and structures raw YOLO detection results into categorized Python data.

    Args:
        results: Raw YOLO prediction results (Results object, list of Results, or None).
        model_names: Optional dictionary mapping class ID (int) to class name (str).
                     If omitted, attempts to extract names directly from results.

    Returns:
        dict: Structured dictionary containing:
            - total_detections: int
            - workers: raw person detections
            - tracked_workers: person detections with valid tracker IDs
            - compliant_ppe: list
            - violations: list
            - heavy_machinery: list
            - unknown: list
            - all_detections: list
    """
    output = _empty_detection_structure()

    if results is None:
        return output

    # Normalize input: handle list or single Results object
    result_obj = None
    if isinstance(results, (list, tuple)):
        if len(results) == 0:
            return output
        result_obj = results[0]
    else:
        result_obj = results

    # Ensure names dictionary is available
    if model_names is None:
        model_names = getattr(result_obj, "names", {})

    # Check for detected boxes
    boxes = getattr(result_obj, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return output

    all_detections: List[Dict[str, Any]] = []

    for box in boxes:
        try:
            # Extract class ID
            cls_tensor = getattr(box, "cls", None)
            if cls_tensor is None or len(cls_tensor) == 0:
                continue
            cls_id = int(cls_tensor[0].item() if hasattr(cls_tensor[0], "item") else cls_tensor[0])

            # Extract confidence score
            conf_tensor = getattr(box, "conf", None)
            if conf_tensor is None or len(conf_tensor) == 0:
                continue
            confidence = float(conf_tensor[0].item() if hasattr(conf_tensor[0], "item") else conf_tensor[0])
            confidence = max(0.0, min(1.0, confidence))

            # Extract coordinates [x1, y1, x2, y2]
            xyxy_tensor = getattr(box, "xyxy", None)
            if xyxy_tensor is None or len(xyxy_tensor) == 0:
                continue
            coords = xyxy_tensor[0].tolist() if hasattr(xyxy_tensor[0], "tolist") else list(xyxy_tensor[0])

            if len(coords) < 4:
                continue

            x1, y1, x2, y2 = [float(c) for c in coords[:4]]

            # Ensure valid numeric bounding box
            if any(np.isnan([x1, y1, x2, y2])) or any(np.isinf([x1, y1, x2, y2])):
                logger.warning(f"Skipping detection with NaN/Inf coordinates: {coords}")
                continue

            # Ensure proper ordering
            left = min(x1, x2)
            top = min(y1, y2)
            right = max(x1, x2)
            bottom = max(y1, y2)

            width = max(0.0, right - left)
            height = max(0.0, bottom - top)
            center_x = left + (width / 2.0)
            center_y = top + (height / 2.0)

            # Extract optional tracking ID (from ByteTrack / BoT-SORT)
            id_tensor = getattr(box, "id", None)
            track_id = None
            if id_tensor is not None and len(id_tensor) > 0:
                track_id = int(id_tensor[0].item() if hasattr(id_tensor[0], "item") else id_tensor[0])

            # Retrieve class name dynamically
            if model_names and cls_id in model_names:
                raw_class_name = str(model_names[cls_id])
            elif model_names and str(cls_id) in model_names:
                raw_class_name = str(model_names[str(cls_id)])
            else:
                raw_class_name = f"unknown_{cls_id}"

            canonical_name = normalize_class_name(raw_class_name)
            category = categorize_class_name(canonical_name)

            detection_item = {
                "class_id": cls_id,
                "class_name": canonical_name,
                "raw_class_name": raw_class_name,
                "track_id": track_id,
                "category": category,
                "confidence": round(confidence, 4),
                "bbox": [round(left, 2), round(top, 2), round(right, 2), round(bottom, 2)],
                "x1": round(left, 2),
                "y1": round(top, 2),
                "x2": round(right, 2),
                "y2": round(bottom, 2),
                "center": {
                    "center_x": round(center_x, 2),
                    "center_y": round(center_y, 2),
                },
                "center_x": round(center_x, 2),
                "center_y": round(center_y, 2),
                "width": round(width, 2),
                "height": round(height, 2),
            }

            all_detections.append(detection_item)

            # Categorize into respective list
            if category in output:
                output[category].append(detection_item)
                if category == "workers" and track_id is not None:
                    output["tracked_workers"].append(detection_item)
            else:
                output["unknown"].append(detection_item)

        except Exception as e:
            logger.warning(f"Error processing single detection box: {e}", exc_info=True)
            continue

    output["all_detections"] = all_detections
    output["total_detections"] = len(all_detections)

    return output
