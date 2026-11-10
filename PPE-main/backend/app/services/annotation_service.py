import logging
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("ppe_monitoring.annotation_service")

# Color palette (BGR for OpenCV)
COLOR_COMPLIANT = (34, 197, 94)      # Green #22c55e
COLOR_VIOLATION = (68, 68, 239)      # Red #ef4444
COLOR_REVIEW = (11, 158, 245)        # Amber #f59e0b
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_MUTED = (148, 163, 184)        # Slate #94a3b8

COMPLIANT_CLASSES = {
    "hardhat",
    "safety vest",
    "safety_vest",
    "gloves",
    "safety shoes",
    "safety_shoes",
    "goggles",
    "mask",
}

VIOLATION_CLASSES = {
    "no-hardhat",
    "no_hardhat",
    "no-safety vest",
    "no_safety_vest",
    "no-safety-vest",
    "no-mask",
    "no_mask",
    "no-goggles",
    "no_goggles",
    "no-gloves",
    "no_gloves",
}


def draw_label(
    img: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    bg_color: Tuple[int, int, int],
    text_color: Tuple[int, int, int] = COLOR_WHITE,
    font_scale: float = 0.45,
    thickness: int = 1,
    padding: int = 3,
) -> None:
    """Draws text with a solid colored background box for high visibility."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)

    x, y = pos
    x1 = max(0, x)
    y1 = max(0, y - text_h - padding * 2)
    x2 = min(img.shape[1], x + text_w + padding * 2)
    y2 = min(img.shape[0], y)

    # Background filled rectangle
    cv2.rectangle(img, (x1, y1), (x2, y2), bg_color, -1)
    # Text label
    cv2.putText(
        img,
        text,
        (x1 + padding, y2 - padding - baseline // 2),
        font,
        font_scale,
        text_color,
        thickness,
        cv2.LINE_AA,
    )


def annotate_frame(
    frame: np.ndarray,
    monitoring_result: Optional[Dict[str, Any]] = None,
    fps: float = 0.0,
) -> np.ndarray:
    """
    Annotates a video frame with worker tracking bounding boxes, PPE detection boxes,
    compliance status colors, confidence scores, and real-time telemetry HUD.

    Args:
        frame: OpenCV BGR image array.
        monitoring_result: Dictionary returned from PPEMonitoringService.process_frame().
        fps: Rolling processing frames-per-second metric.

    Returns:
        np.ndarray: Annotated BGR frame.
    """
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return frame

    # Create a writeable copy to ensure original capture buffer remains clean
    annotated = frame.copy()
    h, w = annotated.shape[:2]

    if not monitoring_result:
        return annotated

    workers: List[Dict[str, Any]] = monitoring_result.get("workers", [])

    # 1. Annotate tracked workers
    for worker in workers:
        bbox = worker.get("worker_bounding_box", [])
        if len(bbox) >= 4:
            x1 = int(max(0, min(w - 1, bbox[0])))
            y1 = int(max(0, min(h - 1, bbox[1])))
            x2 = int(max(0, min(w - 1, bbox[2])))
            y2 = int(max(0, min(h - 1, bbox[3])))

            track_id = worker.get("worker_track_id", "?")
            status = str(worker.get("overall_status", "needs_review")).lower()

            if status == "compliant":
                box_color = COLOR_COMPLIANT
                status_text = "COMPLIANT"
            elif status in ("non_compliant", "violation"):
                box_color = COLOR_VIOLATION
                status_text = "VIOLATION"
            else:
                box_color = COLOR_REVIEW
                status_text = "REVIEW"

            # Draw worker person bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2)

            # Draw worker track ID and overall status header
            header_text = f"WORKER #{track_id} | {status_text}"
            draw_label(
                annotated,
                header_text,
                (x1, max(18, y1)),
                bg_color=box_color,
                text_color=COLOR_WHITE,
                font_scale=0.5,
                thickness=1,
            )

            # Draw explicit missing PPE violations banner if non-compliant
            missing_labels = worker.get("missing_ppe_labels") or [
                f"NO {m.upper().replace('_', ' ')}" for m in worker.get("missing_ppe", [])
            ]
            if missing_labels and status in ("non_compliant", "violation"):
                missing_str = "MISSING: " + ", ".join(missing_labels)
                draw_label(
                    annotated,
                    missing_str,
                    (x1, min(h - 5, max(36, y1 + 18))),
                    bg_color=COLOR_VIOLATION,
                    text_color=COLOR_WHITE,
                    font_scale=0.45,
                    thickness=1,
                )

            # Draw associated PPE detections inside/around this worker
            for ppe in worker.get("associated_ppe", []):
                p_box = ppe.get("bbox") or ppe.get("ppe_bounding_box") or []
                p_name = str(ppe.get("class_name") or ppe.get("ppe_class") or "").strip().lower()
                p_conf = float(ppe.get("confidence") or ppe.get("ppe_confidence") or 0.0)

                if len(p_box) >= 4:
                    px1 = int(max(0, min(w - 1, p_box[0])))
                    py1 = int(max(0, min(h - 1, p_box[1])))
                    px2 = int(max(0, min(w - 1, p_box[2])))
                    py2 = int(max(0, min(h - 1, p_box[3])))

                    if p_name in VIOLATION_CLASSES or p_name.startswith("no-") or p_name.startswith("no_"):
                        p_color = COLOR_VIOLATION
                    elif p_name in COMPLIANT_CLASSES:
                        p_color = COLOR_COMPLIANT
                    else:
                        p_color = COLOR_MUTED

                    cv2.rectangle(annotated, (px1, py1), (px2, py2), p_color, 1)
                    p_label = f"{p_name.upper()} {int(p_conf * 100)}%"
                    draw_label(
                        annotated,
                        p_label,
                        (px1, py1),
                        bg_color=p_color,
                        font_scale=0.38,
                    )

    # 2. Draw any unassigned PPE items or detections
    for unassigned in monitoring_result.get("unassigned_ppe", []):
        u_box = unassigned.get("bbox") or unassigned.get("ppe_bounding_box") or []
        u_name = str(unassigned.get("class_name") or unassigned.get("ppe_class") or "").strip().lower()
        u_conf = float(unassigned.get("confidence") or unassigned.get("ppe_confidence") or 0.0)

        if len(u_box) >= 4:
            ux1 = int(max(0, min(w - 1, u_box[0])))
            uy1 = int(max(0, min(h - 1, u_box[1])))
            ux2 = int(max(0, min(w - 1, u_box[2])))
            uy2 = int(max(0, min(h - 1, u_box[3])))

            u_color = (
                COLOR_VIOLATION
                if (u_name in VIOLATION_CLASSES or u_name.startswith("no-") or u_name.startswith("no_"))
                else COLOR_MUTED
            )
            cv2.rectangle(annotated, (ux1, uy1), (ux2, uy2), u_color, 1)
            draw_label(
                annotated,
                f"{u_name.upper()} {int(u_conf * 100)}%",
                (ux1, uy1),
                bg_color=u_color,
                font_scale=0.38,
            )

    # 3. Top Telemetry HUD Bar (optimized in-place ROI darkening avoiding full-frame copy)
    hud_bg_height = 30
    if h >= hud_bg_height and w > 0:
        roi = annotated[0:hud_bg_height, 0:w]
        cv2.addWeighted(roi, 0.4, np.zeros_like(roi), 0.6, 0, roi)

    hud_text = (
        f"SafeVision AI  |  Live Monitoring  |  FPS: {fps:.1f}  |  "
        f"Workers: {len(workers)} (Compliant: {monitoring_result.get('total_compliant', 0)}, "
        f"Violations: {monitoring_result.get('total_non_compliant', 0)})"
    )
    cv2.putText(
        annotated,
        hud_text,
        (10, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        COLOR_WHITE,
        1,
        cv2.LINE_AA,
    )

    return annotated

