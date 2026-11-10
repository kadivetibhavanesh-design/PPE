import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("ppe_monitoring.model_registry")

# Model Identifiers
MODEL_CONSTRUCTELLIGENCE = "constructelligence"
MODEL_VYRA = "vyra"


@dataclass
class ModelProfile:
    """
    Centralized metadata and configuration profile for a YOLO PPE detection model.
    Encapsulates weights repository, class names, category mappings, and compliance rules.
    """
    model_id: str
    display_name: str
    repo_id: str
    filename: str
    description: str
    is_default: bool
    classes: Dict[int, str]
    category_mappings: Dict[str, Set[str]]
    ppe_category_config: Dict[str, Dict[str, Any]]
    positive_mask_support: bool = False
    positive_glove_support: bool = True
    supported_ppe: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MODEL 1: constructelligence/construction-site-safety-hazards
# ---------------------------------------------------------------------------
CONSTRUCTELLIGENCE_CLASSES = {
    0: "person",
    1: "hardhat",
    2: "no-hardhat",
    3: "safety vest",
    4: "no-safety vest",
    5: "no-mask",
    6: "gloves",
    7: "safety shoes",
    8: "excavator",
    9: "wheel loader",
    10: "dump truck",
    11: "goggles",
    12: "no-goggles",
    13: "no-gloves",
}

CONSTRUCTELLIGENCE_CATEGORY_MAPPINGS = {
    "workers": {"person"},
    "compliant_ppe": {"hardhat", "safety vest", "gloves", "safety shoes", "goggles"},
    "violations": {"no-hardhat", "no-safety vest", "no-mask", "no-goggles", "no-gloves"},
    "heavy_machinery": {"excavator", "wheel loader", "dump truck"},
}

CONSTRUCTELLIGENCE_PPE_CONFIG = {
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
        "compliant_class": None,  # Model has no positive mask class
        "violation_class": "no-mask",
    },
    "safety_shoes": {
        "display_name": "Safety Shoes",
        "compliant_class": "safety shoes",
        "violation_class": None,
    },
}

# ---------------------------------------------------------------------------
# MODEL 2: Hexmon/vyra-yolo-ppe-detection
# ---------------------------------------------------------------------------
VYRA_CLASSES = {
    0: "Fall-Detected",
    1: "Gloves",
    2: "Goggles",
    3: "Hardhat",
    4: "Ladder",
    5: "Mask",
    6: "NO-Gloves",
    7: "NO-Goggles",
    8: "NO-Hardhat",
    9: "NO-Mask",
    10: "NO-Safety Vest",
    11: "Person",
    12: "Safety Cone",
    13: "Safety Vest",
}

VYRA_CATEGORY_MAPPINGS = {
    "workers": {"person"},
    "compliant_ppe": {"hardhat", "safety vest", "gloves", "goggles", "mask"},
    "violations": {"no-hardhat", "no-safety vest", "no-mask", "no-goggles", "no-gloves", "fall-detected"},
    "heavy_machinery": {"ladder", "safety cone"},
}

VYRA_PPE_CONFIG = {
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
        "compliant_class": "mask",  # Vyra supports BOTH positive mask and no-mask!
        "violation_class": "no-mask",
    },
    "safety_shoes": {
        "display_name": "Safety Shoes",
        "compliant_class": None,  # Not in Vyra dataset
        "violation_class": None,
    },
}

# ---------------------------------------------------------------------------
# Registry Catalog
# ---------------------------------------------------------------------------
REGISTERED_MODELS: Dict[str, ModelProfile] = {
    MODEL_CONSTRUCTELLIGENCE: ModelProfile(
        model_id=MODEL_CONSTRUCTELLIGENCE,
        display_name="Constructelligence - Construction Site Hazards (YOLOv8)",
        repo_id="constructelligence/construction-site-safety-hazards",
        filename="buildvision-hazards-v0.3.pt",
        description="General construction safety hazard model covering hardhat, safety vest, gloves, goggles, and shoes. Detects no-mask violations (no positive mask class).",
        is_default=True,
        classes=CONSTRUCTELLIGENCE_CLASSES,
        category_mappings=CONSTRUCTELLIGENCE_CATEGORY_MAPPINGS,
        ppe_category_config=CONSTRUCTELLIGENCE_PPE_CONFIG,
        positive_mask_support=False,
        positive_glove_support=True,
        supported_ppe=["Hardhat", "Safety Vest", "Gloves", "Safety Goggles", "Safety Shoes", "Mask (Violations only)"],
    ),
    MODEL_VYRA: ModelProfile(
        model_id=MODEL_VYRA,
        display_name="Vyra - Real-Time PPE Detection (YOLOv8)",
        repo_id="Hexmon/vyra-yolo-ppe-detection",
        filename="best.pt",
        description="Fine-grained industrial PPE detection model with comprehensive positive and negative verification for Hardhat, Safety Vest, Mask, Gloves, and Goggles.",
        is_default=False,
        classes=VYRA_CLASSES,
        category_mappings=VYRA_CATEGORY_MAPPINGS,
        ppe_category_config=VYRA_PPE_CONFIG,
        positive_mask_support=True,
        positive_glove_support=True,
        supported_ppe=["Hardhat", "Safety Vest", "Mask (Compliant & Violation)", "Gloves", "Safety Goggles", "Fall-Detected"],
    ),
}

# Thread-safe global active model selection
_registry_lock = threading.Lock()
_active_model_id = MODEL_CONSTRUCTELLIGENCE


def get_active_model_id() -> str:
    """Returns the identifier of the currently active model."""
    with _registry_lock:
        return _active_model_id


def set_active_model_id(model_id: str) -> ModelProfile:
    """
    Sets the active model identifier in the registry.

    Args:
        model_id: One of 'constructelligence' or 'vyra'.

    Returns:
        ModelProfile: The selected model's profile.

    Raises:
        ValueError: If model_id is not registered.
    """
    global _active_model_id
    normalized = model_id.lower().strip()
    with _registry_lock:
        if normalized not in REGISTERED_MODELS:
            valid_ids = list(REGISTERED_MODELS.keys())
            raise ValueError(f"Unknown model identifier '{model_id}'. Valid models are: {valid_ids}")
        _active_model_id = normalized
        logger.info(f"Active model switched to: '{_active_model_id}' ({REGISTERED_MODELS[_active_model_id].display_name})")
        return REGISTERED_MODELS[_active_model_id]


def get_model_profile(model_id: Optional[str] = None) -> ModelProfile:
    """
    Retrieves the ModelProfile for a specific model_id, or the currently active model if omitted.
    """
    with _registry_lock:
        mid = (model_id.lower().strip() if model_id else _active_model_id)
        if mid not in REGISTERED_MODELS:
            mid = MODEL_CONSTRUCTELLIGENCE
        return REGISTERED_MODELS[mid]


def list_available_models() -> List[Dict[str, Any]]:
    """
    Returns list of all available models with inspection metadata for UI selection.
    """
    current_active = get_active_model_id()
    result = []
    for mid, profile in REGISTERED_MODELS.items():
        result.append({
            "model_id": profile.model_id,
            "display_name": profile.display_name,
            "repo_id": profile.repo_id,
            "filename": profile.filename,
            "description": profile.description,
            "is_active": profile.model_id == current_active,
            "is_default": profile.is_default,
            "num_classes": len(profile.classes),
            "classes": profile.classes,
            "positive_mask_support": profile.positive_mask_support,
            "positive_glove_support": profile.positive_glove_support,
            "supported_ppe": profile.supported_ppe,
        })
    return result


def normalize_class_name(raw_name: str) -> str:
    """
    Normalizes any raw model class name (e.g., 'NO-Hardhat', 'Safety Vest', 'Gloves')
    into a standardized canonical lower-case string (e.g., 'no-hardhat', 'safety vest', 'gloves').
    """
    cleaned = str(raw_name).strip().lower()
    # Normalize hyphens and underscores
    cleaned = cleaned.replace("_", " ")
    if cleaned.startswith("no "):
        cleaned = "no-" + cleaned[3:]
    elif cleaned.startswith("no-"):
        pass
    return cleaned

