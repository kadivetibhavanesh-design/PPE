import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("ppe_monitoring.ppe_association_service")

# Anatomical body regions defining expected vertical relative positions (rel_y) on worker bounding box
# rel_y = (ppe_center_y - worker_y1) / (worker_y2 - worker_y1)
ANATOMICAL_CONFIG: Dict[str, Dict[str, Any]] = {
    # Head region (covers standing, upper-body and seated webcam framing)
    "hardhat": {"region": "head", "rel_y_min": -0.25, "rel_y_max": 0.65, "ideal_y": 0.12},
    "no-hardhat": {"region": "head", "rel_y_min": -0.25, "rel_y_max": 0.65, "ideal_y": 0.12},
    "no_hardhat": {"region": "head", "rel_y_min": -0.25, "rel_y_max": 0.65, "ideal_y": 0.12},
    "goggles": {"region": "head", "rel_y_min": -0.10, "rel_y_max": 0.65, "ideal_y": 0.18},
    "no-goggles": {"region": "head", "rel_y_min": -0.10, "rel_y_max": 0.65, "ideal_y": 0.18},
    "no_goggles": {"region": "head", "rel_y_min": -0.10, "rel_y_max": 0.65, "ideal_y": 0.18},
    "mask": {"region": "head", "rel_y_min": -0.10, "rel_y_max": 0.65, "ideal_y": 0.22},
    "no-mask": {"region": "head", "rel_y_min": -0.10, "rel_y_max": 0.65, "ideal_y": 0.22},
    "no_mask": {"region": "head", "rel_y_min": -0.10, "rel_y_max": 0.65, "ideal_y": 0.22},
    # Upper-body / Torso region
    "safety vest": {"region": "upper_body", "rel_y_min": 0.10, "rel_y_max": 0.95, "ideal_y": 0.45},
    "safety_vest": {"region": "upper_body", "rel_y_min": 0.10, "rel_y_max": 0.95, "ideal_y": 0.45},
    "no-safety vest": {"region": "upper_body", "rel_y_min": 0.10, "rel_y_max": 0.95, "ideal_y": 0.45},
    "no_safety_vest": {"region": "upper_body", "rel_y_min": 0.10, "rel_y_max": 0.95, "ideal_y": 0.45},
    "no-safety-vest": {"region": "upper_body", "rel_y_min": 0.10, "rel_y_max": 0.95, "ideal_y": 0.45},
    # Hand / Arm region (broad range & horizontal reach for hands held up, on desk, or lateral)
    "gloves": {"region": "hands", "rel_y_min": -0.10, "rel_y_max": 1.15, "ideal_y": 0.50, "h_margin_factor": 0.45},
    "no-gloves": {"region": "hands", "rel_y_min": -0.10, "rel_y_max": 1.15, "ideal_y": 0.50, "h_margin_factor": 0.45},
    "no_gloves": {"region": "hands", "rel_y_min": -0.10, "rel_y_max": 1.15, "ideal_y": 0.50, "h_margin_factor": 0.45},
    # Lower-body / Feet region
    "safety shoes": {"region": "lower_body", "rel_y_min": 0.50, "rel_y_max": 1.25, "ideal_y": 0.92},
    "safety_shoes": {"region": "lower_body", "rel_y_min": 0.50, "rel_y_max": 1.25, "ideal_y": 0.92},
    "no-safety shoes": {"region": "lower_body", "rel_y_min": 0.50, "rel_y_max": 1.25, "ideal_y": 0.92},
    "no_safety_shoes": {"region": "lower_body", "rel_y_min": 0.50, "rel_y_max": 1.25, "ideal_y": 0.92},
}

DEFAULT_ANATOMICAL = {"region": "general", "rel_y_min": -0.10, "rel_y_max": 1.10, "ideal_y": 0.50}


class PPEAssociationService:
    """
    Spatial association service that pairs PPE and violation detections
    with tracked workers based on bounding-box geometry, containment (IoA),
    and anatomical body-region constraints.
    """

    def __init__(
        self,
        min_association_score: float = 0.30,
        ambiguity_margin: float = 0.15,
        min_ioa_threshold: float = 0.08,
    ) -> None:
        """
        Initializes the spatial association service with configurable geometric thresholds.

        Args:
            min_association_score: Minimum composite score required to accept association (default: 0.30).
            ambiguity_margin: If difference between top 2 candidate scores is smaller than this margin,
                              the association is considered ambiguous and returned as unassigned (default: 0.15).
            min_ioa_threshold: Minimum intersection over PPE area required for containment check (default: 0.08).
        """
        self.min_association_score = float(min_association_score)
        self.ambiguity_margin = float(ambiguity_margin)
        self.min_ioa_threshold = float(min_ioa_threshold)

    @staticmethod
    def _is_valid_box(box: Any) -> bool:
        """Validates that a bounding box is a valid 4-element numeric array."""
        if not isinstance(box, (list, tuple)) or len(box) < 4:
            return False
        try:
            x1, y1, x2, y2 = [float(v) for v in box[:4]]
            return (x2 > x1) and (y2 > y1)
        except (ValueError, TypeError):
            return False

    def _compute_geometric_score(
        self,
        ppe_box: List[float],
        worker_box: List[float],
        ppe_class: str,
    ) -> Tuple[float, str]:
        """
        Calculates a composite spatial-anatomical association score between a PPE item and a worker.

        Returns:
            Tuple (score, region_name):
                score: Float between 0.0 and 1.0.
                region_name: The anatomical body region matched.
        """
        px1, py1, px2, py2 = ppe_box
        wx1, wy1, wx2, wy2 = worker_box

        ppe_w = max(0.0, px2 - px1)
        ppe_h = max(0.0, py2 - py1)
        ppe_area = ppe_w * ppe_h

        worker_w = max(0.0, wx2 - wx1)
        worker_h = max(0.0, wy2 - wy1)

        if ppe_area <= 0.0 or worker_w <= 0.0 or worker_h <= 0.0:
            return 0.0, "general"

        ppe_cx = px1 + (ppe_w / 2.0)
        ppe_cy = py1 + (ppe_h / 2.0)
        worker_cx = wx1 + (worker_w / 2.0)

        # 1. Intersection over PPE Area (IoA)
        ix1 = max(wx1, px1)
        iy1 = max(wy1, py1)
        ix2 = min(wx2, px2)
        iy2 = min(wy2, py2)

        if ix2 > ix1 and iy2 > iy1:
            inter_area = (ix2 - ix1) * (iy2 - iy1)
            ioa = inter_area / ppe_area
        else:
            ioa = 0.0

        # Resolve anatomical configuration
        clean_cls = ppe_class.lower().strip()
        config = (
            ANATOMICAL_CONFIG.get(clean_cls)
            or ANATOMICAL_CONFIG.get(clean_cls.replace("-", " ").replace("_", " "))
            or ANATOMICAL_CONFIG.get(clean_cls.replace(" ", "_"))
            or ANATOMICAL_CONFIG.get(clean_cls.replace(" ", "-"))
            or DEFAULT_ANATOMICAL
        )
        region = config["region"]

        # 2. Horizontal centering alignment with adaptive lateral margin (wider for arms/hands)
        h_margin_factor = float(config.get("h_margin_factor", 0.25))
        h_margin = h_margin_factor * worker_w
        if (ppe_cx < (wx1 - h_margin)) or (ppe_cx > (wx2 + h_margin)):
            return 0.0, region

        h_dist = abs(ppe_cx - worker_cx) / (worker_w / 2.0 + h_margin + 1e-6)
        h_score = max(0.0, 1.0 - min(1.0, h_dist))

        # 3. Anatomical vertical position
        rel_y = (ppe_cy - wy1) / worker_h
        if rel_y < config["rel_y_min"] or rel_y > config["rel_y_max"]:
            # PPE is outside the plausible anatomical region for this item
            return 0.0, region

        ideal_y = config["ideal_y"]
        y_dist = abs(rel_y - ideal_y)
        # Hands exhibit wider natural mobility across chest, desk, and sides
        y_penalty = 1.0 if region == "hands" else 2.0
        anatomical_score = max(0.0, 1.0 - (y_penalty * y_dist))

        # 4. Check if PPE center falls within worker expanded bounding region
        v_margin = 0.15 * worker_h
        center_in_worker = (
            (wx1 - h_margin <= ppe_cx <= wx2 + h_margin)
            and (wy1 - v_margin <= ppe_cy <= wy2 + v_margin)
        )

        if not center_in_worker and ioa < self.min_ioa_threshold:
            return 0.0, region

        # Composite association score: 40% IoA + 35% Anatomical + 25% Horizontal alignment
        composite_score = (0.40 * ioa) + (0.35 * anatomical_score) + (0.25 * h_score)
        composite_score = max(0.0, min(1.0, composite_score))

        return composite_score, region

    def associate(
        self,
        workers: Optional[List[Dict[str, Any]]] = None,
        compliant_ppe: Optional[List[Dict[str, Any]]] = None,
        violations: Optional[List[Dict[str, Any]]] = None,
        structured_detections: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Associates PPE and violation detections with tracked workers.

        Can be called with `structured_detections` directly, or individual lists.

        Returns:
            dict containing:
                - associations: list of matched association records.
                - unassigned_ppe: list of unassigned PPE items with reasons.
                - summary: counts of processed, associated, and unassigned items.
        """
        # Resolve inputs
        if structured_detections is not None:
            workers = structured_detections.get("workers", [])
            compliant_ppe = structured_detections.get("compliant_ppe") or structured_detections.get("ppe", [])
            violations = structured_detections.get("violations", [])
        else:
            workers = workers or []
            compliant_ppe = compliant_ppe or []
            violations = violations or []

        # Filter valid workers that have tracking IDs and valid bounding boxes
        valid_workers = []
        for w in workers:
            if not isinstance(w, dict):
                continue
            track_id = w.get("track_id")
            bbox = w.get("bbox")
            if track_id is not None and self._is_valid_box(bbox):
                valid_workers.append(w)

        # Build list of all PPE items to associate
        ppe_items = []
        for item in compliant_ppe:
            if isinstance(item, dict):
                ppe_items.append((item, "compliant"))
        for item in violations:
            if isinstance(item, dict):
                ppe_items.append((item, "violation"))

        associations: List[Dict[str, Any]] = []
        unassigned_ppe: List[Dict[str, Any]] = []

        for ppe, ppe_cat in ppe_items:
            ppe_class = ppe.get("class_name", "unknown")
            ppe_conf = float(ppe.get("confidence", 0.0))
            ppe_box = ppe.get("bbox")

            # Check invalid bounding box
            if not self._is_valid_box(ppe_box):
                unassigned_ppe.append({
                    "ppe_class": ppe_class,
                    "ppe_category": ppe_cat,
                    "ppe_confidence": ppe_conf,
                    "ppe_bounding_box": ppe_box,
                    "reason": "invalid_bounding_box",
                })
                continue

            # If no valid workers available in frame
            if not valid_workers:
                unassigned_ppe.append({
                    "ppe_class": ppe_class,
                    "ppe_category": ppe_cat,
                    "ppe_confidence": ppe_conf,
                    "ppe_bounding_box": ppe_box,
                    "reason": "no_tracked_workers_in_frame",
                })
                continue

            # Evaluate match score against all valid candidate workers
            candidate_scores = []
            for w in valid_workers:
                score, region = self._compute_geometric_score(
                    ppe_box=ppe_box,
                    worker_box=w["bbox"],
                    ppe_class=ppe_class,
                )
                if score >= self.min_association_score:
                    candidate_scores.append((score, w, region))

            # Case A: No candidate achieved the minimum score
            if not candidate_scores:
                unassigned_ppe.append({
                    "ppe_class": ppe_class,
                    "ppe_category": ppe_cat,
                    "ppe_confidence": ppe_conf,
                    "ppe_bounding_box": ppe_box,
                    "reason": "no_worker_spatial_match",
                })
                continue

            # Sort candidate workers by score descending
            candidate_scores.sort(key=lambda x: x[0], reverse=True)
            top_score, best_worker, matched_region = candidate_scores[0]

            # Case B: Ambiguity check between multiple candidates
            if len(candidate_scores) > 1:
                second_score = candidate_scores[1][0]
                diff = top_score - second_score
                if diff < self.ambiguity_margin:
                    # Score gap is too narrow; ambiguous spatial boundary
                    unassigned_ppe.append({
                        "ppe_class": ppe_class,
                        "ppe_category": ppe_cat,
                        "ppe_confidence": ppe_conf,
                        "ppe_bounding_box": ppe_box,
                        "reason": f"ambiguous_between_workers (scores: {top_score:.2f} vs {second_score:.2f})",
                    })
                    continue

            # Case C: Confirmed unambiguous association
            logger.info(
                f"[PPE ASSOCIATION] Worker #{best_worker['track_id']} <- '{ppe_class}' "
                f"(confidence={ppe_conf:.2f}, score={top_score:.2f}, region={matched_region})"
            )
            associations.append({
                "worker_track_id": best_worker["track_id"],
                "worker_bounding_box": list(best_worker["bbox"]),
                "ppe_class": ppe_class,
                "class_name": ppe_class,
                "ppe_category": ppe_cat,
                "category": ppe_cat,
                "ppe_confidence": round(ppe_conf, 4),
                "confidence": round(ppe_conf, 4),
                "ppe_bounding_box": list(ppe_box),
                "bbox": list(ppe_box),
                "body_region": matched_region,
                "association_method": "spatial_anatomical_overlap",
                "association_confidence": round(top_score, 4),
            })

        # Calculate summary statistics
        workers_with_ppe = len({a["worker_track_id"] for a in associations})

        return {
            "associations": associations,
            "unassigned_ppe": unassigned_ppe,
            "summary": {
                "total_ppe_detections": len(ppe_items),
                "total_associated": len(associations),
                "total_unassigned": len(unassigned_ppe),
                "workers_with_ppe": workers_with_ppe,
            },
        }

