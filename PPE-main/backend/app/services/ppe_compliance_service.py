import logging
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger("ppe_monitoring.ppe_compliance_service")

try:
    from app.services.model_registry import get_model_profile, normalize_class_name
except ImportError:
    from services.model_registry import get_model_profile, normalize_class_name

# Individual PPE Category Statuses
STATUS_COMPLIANT = "compliant"
STATUS_MISSING = "missing"
STATUS_VIOLATION = "missing"  # Standardized to "missing" per Section 5
STATUS_NOT_DETECTED = "not_detected"
STATUS_UNCERTAIN = "uncertain"

# Overall Worker Compliance Statuses
OVERALL_COMPLIANT = "compliant"
OVERALL_NON_COMPLIANT = "non_compliant"
OVERALL_NEEDS_REVIEW = "needs_review"

# Fallback default PPE Category Mapping to Detection Classes
PPE_CATEGORY_CONFIG: Dict[str, Dict[str, Any]] = {
    "hardhat": {
        "display_name": "Hardhat",
        "compliant_class": "hardhat",
        "violation_class": "no-hardhat",
    },
    "safety_vest": {
        "display_name": "Safety Vest",
        "compliant_class": "safety vest",
        "violation_class": "no-safety vest",
    },
    "gloves": {
        "display_name": "Gloves",
        "compliant_class": "gloves",
        "violation_class": "no-gloves",
    },
    "goggles": {
        "display_name": "Safety Goggles",
        "compliant_class": "goggles",
        "violation_class": "no-goggles",
    },
    "mask": {
        "display_name": "Mask",
        "compliant_class": None,  # Pretrained model has no compliant mask class
        "violation_class": "no-mask",
    },
    "safety_shoes": {
        "display_name": "Safety Shoes",
        "compliant_class": "safety shoes",
        "violation_class": None,  # Pretrained model has no shoes violation class
    },
}

# Reverse lookup: maps model class name -> (category_key, type_str)
CLASS_TO_CATEGORY: Dict[str, tuple[str, str]] = {}
for cat_key, cfg in PPE_CATEGORY_CONFIG.items():
    if cfg.get("compliant_class"):
        cls_name = cfg["compliant_class"].lower().strip()
        CLASS_TO_CATEGORY[cls_name] = (cat_key, "compliant")
        CLASS_TO_CATEGORY[cls_name.replace(" ", "_")] = (cat_key, "compliant")
        CLASS_TO_CATEGORY[cls_name.replace(" ", "-")] = (cat_key, "compliant")
    if cfg.get("violation_class"):
        cls_name = cfg["violation_class"].lower().strip()
        CLASS_TO_CATEGORY[cls_name] = (cat_key, "violation")
        CLASS_TO_CATEGORY[cls_name.replace("-", "_")] = (cat_key, "violation")
        CLASS_TO_CATEGORY[cls_name.replace("-", " ")] = (cat_key, "violation")


class PPEComplianceService:
    """
    Evaluates industrial PPE compliance independently for each tracked worker.
    Uses spatial associations output from PPEAssociationService to determine
    evidence-based compliance, explicit violations, and unconfirmed states.
    Supports dynamic category configuration from centralized model registry.
    """

    DEFAULT_REQUIRED_CATEGORIES = ["hardhat", "safety_vest"]

    def __init__(
        self,
        required_categories: Optional[List[str]] = None,
        min_confidence: float = 0.30,
        category_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """
        Initializes the PPE Compliance Service.

        Args:
            required_categories: List of mandatory PPE category keys to evaluate for overall status.
                                 Defaults to ['hardhat', 'safety_vest'].
            min_confidence: Minimum detection confidence required to treat evidence as valid.
                            Default: 0.30.
            category_config: Optional explicit PPE category configuration dict.
        """
        if required_categories is None:
            self.required_categories = list(self.DEFAULT_REQUIRED_CATEGORIES)
        else:
            self.required_categories = list(required_categories)

        self.min_confidence = float(min_confidence)
        self.category_thresholds: Dict[str, float] = {}
        self.explicit_config = category_config
        self.category_config: Dict[str, Dict[str, Any]] = {}
        self.class_to_category: Dict[str, tuple[str, str]] = {}
        self.refresh_config()

    def refresh_config(self) -> None:
        """Re-syncs category configuration and reverse class lookup from active model profile."""
        if self.explicit_config is not None:
            cfg = dict(self.explicit_config)
        else:
            try:
                cfg = dict(get_model_profile().ppe_category_config)
            except Exception:
                cfg = dict(PPE_CATEGORY_CONFIG)

        self.category_config = cfg
        self.class_to_category = {}

        for cat_key, c_info in self.category_config.items():
            comp = c_info.get("compliant_class")
            if comp:
                c_name = str(comp).lower().strip()
                self.class_to_category[c_name] = (cat_key, "compliant")
                self.class_to_category[c_name.replace(" ", "_")] = (cat_key, "compliant")
                self.class_to_category[c_name.replace(" ", "-")] = (cat_key, "compliant")
            viol = c_info.get("violation_class")
            if viol:
                v_name = str(viol).lower().strip()
                self.class_to_category[v_name] = (cat_key, "violation")
                self.class_to_category[v_name.replace("-", "_")] = (cat_key, "violation")
                self.class_to_category[v_name.replace("-", " ")] = (cat_key, "violation")

    def evaluate_worker(
        self,
        worker_track_id: int,
        worker_associations: List[Dict[str, Any]],
        required_categories: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates a single worker's PPE compliance based on their associated detections.

        Args:
            worker_track_id: Integer tracking ID for the worker.
            worker_associations: List of PPE association records for this worker.
            required_categories: Optional override for mandatory categories.
            min_confidence: Optional override for confidence threshold.

        Returns:
            dict: Detailed worker compliance report.
        """
        req_cats = required_categories if required_categories is not None else self.required_categories
        conf_thresh = min_confidence if min_confidence is not None else self.min_confidence

        # Group valid associated detections by category
        grouped_by_category: Dict[str, List[Dict[str, Any]]] = {k: [] for k in self.category_config}

        for assoc in worker_associations:
            if not isinstance(assoc, dict):
                continue

            ppe_class = normalize_class_name(str(assoc.get("ppe_class") or assoc.get("class_name") or ""))
            if ppe_class in self.class_to_category:
                cat_key, _ = self.class_to_category[ppe_class]
                grouped_by_category[cat_key].append(assoc)
            elif ppe_class in CLASS_TO_CATEGORY:
                cat_key, _ = CLASS_TO_CATEGORY[ppe_class]
                if cat_key in grouped_by_category:
                    grouped_by_category[cat_key].append(assoc)

        category_evaluations: Dict[str, Any] = {}
        ppe_status: Dict[str, str] = {}
        missing_ppe: List[str] = []
        missing_ppe_labels: List[str] = []
        compliant_count = 0
        violation_count = 0
        not_detected_count = 0
        uncertain_count = 0

        # Evaluate each configured category
        for cat_key, cfg in self.category_config.items():
            detections = grouped_by_category[cat_key]
            eval_result = self._evaluate_category(cat_key, cfg, detections, conf_thresh)
            category_evaluations[cat_key] = eval_result
            status = eval_result["status"]
            ppe_status[cat_key] = status

            # Check for explicit missing/violation PPE
            if status in (STATUS_MISSING, "violation_detected", "violation"):
                violation_count += 1
                missing_ppe.append(cat_key)
                missing_ppe_labels.append(f"NO {cfg['display_name'].upper()}")
            elif status == STATUS_COMPLIANT:
                if cat_key in req_cats:
                    compliant_count += 1
            elif status == STATUS_NOT_DETECTED:
                if cat_key in req_cats:
                    not_detected_count += 1
            elif status == STATUS_UNCERTAIN:
                if cat_key in req_cats:
                    uncertain_count += 1

        # Determine overall worker compliance status
        if violation_count > 0:
            overall_status = OVERALL_NON_COMPLIANT
            overall_reason = f"Confirmed missing PPE: {', '.join(missing_ppe)}."
        elif compliant_count == len(req_cats) and len(req_cats) > 0 and violation_count == 0:
            overall_status = OVERALL_COMPLIANT
            overall_reason = "All required PPE categories verified compliant."
        else:
            overall_status = OVERALL_NEEDS_REVIEW
            overall_reason = (
                f"Missing or unconfirmed evidence for required PPE "
                f"({not_detected_count} not detected, {uncertain_count} uncertain, 0 violations)."
            )

        # Structured debug log for worker compliance evaluation
        detected_classes = [
            str(a.get("ppe_class") or a.get("class_name") or "unknown")
            for a in worker_associations
        ]
        detected_confs = [
            round(float(a.get("ppe_confidence") or a.get("confidence") or 0.0), 3)
            for a in worker_associations
        ]
        logger.info(
            f"[PPE EVALUATION] Worker #{worker_track_id} | "
            f"compliance_status={overall_status.upper()} | "
            f"detected_classes={detected_classes} | "
            f"confidences={detected_confs} | "
            f"missing_ppe={missing_ppe} | "
            f"missing_ppe_labels={missing_ppe_labels} | "
            f"ppe_status={ppe_status} | "
            f"associated_objects={len(worker_associations)}"
        )

        return {
            "worker_track_id": worker_track_id,
            "worker_id": worker_track_id,
            "overall_status": overall_status,
            "compliance_status": overall_status,
            "overall_reason": overall_reason,
            "required_categories": list(req_cats),
            "compliant_count": compliant_count,
            "violation_count": violation_count,
            "not_detected_count": not_detected_count,
            "uncertain_count": uncertain_count,
            "categories": category_evaluations,
            "ppe_status": ppe_status,
            "missing_ppe": missing_ppe,
            "missing_ppe_labels": missing_ppe_labels,
        }

    def _evaluate_category(
        self,
        cat_key: str,
        cfg: Dict[str, Any],
        detections: List[Dict[str, Any]],
        conf_thresh: float,
    ) -> Dict[str, Any]:
        """Evaluates compliance for an individual PPE category."""
        if not detections:
            # Important Rule: Absence of detection is NOT a violation
            reason = "No detection associated with this worker."
            if cfg["compliant_class"] is None:
                reason += " Note: Model has no compliant class for this category."
            return {
                "category": cat_key,
                "display_name": cfg["display_name"],
                "status": STATUS_NOT_DETECTED,
                "reason": reason,
                "confidence": None,
                "evidence": [],
            }

        valid_compliant = []
        valid_violations = []
        low_confidence_items = []

        effective_conf_thresh = self.category_thresholds.get(cat_key, conf_thresh)

        for d in detections:
            conf = float(d.get("ppe_confidence") or d.get("confidence") or 0.0)
            ppe_class = normalize_class_name(str(d.get("ppe_class") or d.get("class_name") or ""))
            cat_type = self.class_to_category.get(ppe_class, CLASS_TO_CATEGORY.get(ppe_class, (None, None)))[1]

            if conf < effective_conf_thresh:
                low_confidence_items.append(d)
            elif cat_type == "compliant":
                valid_compliant.append(d)
            elif cat_type == "violation":
                valid_violations.append(d)

        def _get_conf(item: Dict[str, Any]) -> float:
            return float(item.get("ppe_confidence") or item.get("confidence") or 0.0)

        # Case 1: Low confidence items only
        if not valid_compliant and not valid_violations and low_confidence_items:
            best_conf = max(_get_conf(x) for x in low_confidence_items)
            return {
                "category": cat_key,
                "display_name": cfg["display_name"],
                "status": STATUS_UNCERTAIN,
                "reason": f"Detections present but below confidence threshold ({best_conf:.2f} < {conf_thresh:.2f}).",
                "confidence": best_conf,
                "evidence": low_confidence_items,
            }

        # Case 2: Conflicting evidence (both compliant and violation detected)
        if valid_compliant and valid_violations:
            c_conf = max(_get_conf(x) for x in valid_compliant)
            v_conf = max(_get_conf(x) for x in valid_violations)
            return {
                "category": cat_key,
                "display_name": cfg["display_name"],
                "status": STATUS_UNCERTAIN,
                "reason": f"Conflicting evidence: both compliant ({c_conf:.2f}) and violation ({v_conf:.2f}) associated.",
                "confidence": max(c_conf, v_conf),
                "evidence": valid_compliant + valid_violations,
            }

        # Case 3: Confirmed Violation / Missing PPE
        if valid_violations:
            best_violation = max(valid_violations, key=_get_conf)
            conf = _get_conf(best_violation)
            item_cls = best_violation.get("ppe_class") or best_violation.get("class_name")
            return {
                "category": cat_key,
                "display_name": cfg["display_name"],
                "status": STATUS_MISSING,
                "reason": f"Confirmed explicit violation: '{item_cls}' detected.",
                "confidence": conf,
                "evidence": valid_violations,
            }

        # Case 4: Compliant Detection
        if valid_compliant:
            # Special check: Categories without compliant class cannot be marked compliant
            if cfg["compliant_class"] is None:
                return {
                    "category": cat_key,
                    "display_name": cfg["display_name"],
                    "status": STATUS_NOT_DETECTED,
                    "reason": "Model cannot verify compliance for this category.",
                    "confidence": None,
                    "evidence": valid_compliant,
                }

            best_compliant = max(valid_compliant, key=_get_conf)
            conf = _get_conf(best_compliant)
            item_cls = best_compliant.get("ppe_class") or best_compliant.get("class_name")
            return {
                "category": cat_key,
                "display_name": cfg["display_name"],
                "status": STATUS_COMPLIANT,
                "reason": f"Compliant PPE item '{item_cls}' verified.",
                "confidence": conf,
                "evidence": valid_compliant,
            }

        # Fallback
        return {
            "category": cat_key,
            "display_name": cfg["display_name"],
            "status": STATUS_NOT_DETECTED,
            "reason": "No actionable detections.",
            "confidence": None,
            "evidence": [],
        }

    def evaluate_all(
        self,
        associations_payload: Union[Dict[str, Any], List[Dict[str, Any]]],
        worker_track_ids: Optional[List[int]] = None,
        required_categories: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates compliance across all workers in a frame payload.

        Args:
            associations_payload: Either association dictionary with 'associations' key,
                                 or raw list of association items.
            worker_track_ids: Optional list of all active worker IDs in frame.
            required_categories: Optional override for required PPE.
            min_confidence: Optional override for confidence threshold.

        Returns:
            dict: Comprehensive compliance summary for the frame.
        """
        if isinstance(associations_payload, dict):
            raw_associations = associations_payload.get("associations", [])
        elif isinstance(associations_payload, list):
            raw_associations = associations_payload
        else:
            raw_associations = []

        # Group associations by worker track ID
        worker_assoc_map: Dict[int, List[Dict[str, Any]]] = {}
        for item in raw_associations:
            if not isinstance(item, dict):
                continue
            tid = item.get("worker_track_id")
            if tid is not None:
                worker_assoc_map.setdefault(tid, []).append(item)

        # Consolidate target workers
        target_ids: Set[int] = set()
        if worker_track_ids is not None:
            target_ids.update(worker_track_ids)
        target_ids.update(worker_assoc_map.keys())

        worker_evaluations: Dict[int, Dict[str, Any]] = {}
        compliant_workers = 0
        non_compliant_workers = 0
        needs_review_workers = 0

        for tid in sorted(target_ids):
            worker_assocs = worker_assoc_map.get(tid, [])
            eval_result = self.evaluate_worker(
                worker_track_id=tid,
                worker_associations=worker_assocs,
                required_categories=required_categories,
                min_confidence=min_confidence,
            )
            worker_evaluations[tid] = eval_result

            status = eval_result["overall_status"]
            if status == OVERALL_COMPLIANT:
                compliant_workers += 1
            elif status == OVERALL_NON_COMPLIANT:
                non_compliant_workers += 1
            elif status == OVERALL_NEEDS_REVIEW:
                needs_review_workers += 1

        return {
            "total_workers": len(target_ids),
            "compliant_workers": compliant_workers,
            "non_compliant_workers": non_compliant_workers,
            "needs_review_workers": needs_review_workers,
            "worker_evaluations": worker_evaluations,
            "required_categories": required_categories or self.required_categories,
        }

    def set_category_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Sets individual confidence thresholds for specific PPE categories."""
        if isinstance(thresholds, dict):
            self.category_thresholds = {
                str(k): max(0.01, min(0.99, float(v))) for k, v in thresholds.items()
            }
            logger.info(f"PPEComplianceService category thresholds set to {self.category_thresholds}")

    def set_required_categories(self, categories: List[str]) -> None:
        """Sets active required categories for worker compliance."""
        if isinstance(categories, list):
            self.required_categories = [str(c).lower().strip() for c in categories]
            logger.info(f"PPEComplianceService required categories updated to {self.required_categories}")

