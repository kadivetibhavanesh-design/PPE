import os
import sys
import time

sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))

from app.services.model_registry import (
    MODEL_CONSTRUCTELLIGENCE,
    MODEL_VYRA,
    get_active_model_id,
    set_active_model_id,
    get_model_profile,
    list_available_models,
)
from app.services.model_service import (
    get_model,
    get_model_info,
    switch_model,
    load_model,
)
from app.services.ppe_association_service import PPEAssociationService
from app.services.ppe_compliance_service import PPEComplianceService
from app.services.detection_service import categorize_class_name
from app.services.monitoring_controller import MonitoringController
from app.services.ppe_monitoring_service import PPEMonitoringService


def run_dual_model_verification():
    print("=" * 80)
    print("  SafeVision AI - Dual YOLO Model Registry & Pipeline Verification")
    print("=" * 80)

    # 1. Centralized Model Registry Verification
    print("\n[Step 1] Verifying Centralized Model Registry...")
    models = list_available_models()
    print(f"  * Total Registered Models: {len(models)}")
    for m in models:
        print(f"    - [{m['model_id']}] {m['display_name']} ({m['num_classes']} classes, Mask support: {m['positive_mask_support']})")

    assert len(models) == 2, "Registry must contain exactly 2 registered models"
    model_ids = {m["model_id"] for m in models}
    assert MODEL_CONSTRUCTELLIGENCE in model_ids
    assert MODEL_VYRA in model_ids
    print("  ✓ Centralized registry catalog verified.")

    # 2. Independent Model Inspection & Weight Loading
    print("\n[Step 2] Testing Model 1: Constructelligence...")
    info1 = switch_model(MODEL_CONSTRUCTELLIGENCE)
    print(f"  * Active Model: {info1['display_name']}")
    print(f"  * Weights File: {info1['filename']}")
    print(f"  * Total Classes: {info1['num_classes']}")
    print(f"  * Class 5: {info1['classes'].get(5)} (no-mask)")
    print(f"  * Class 6: {info1['classes'].get(6)} (gloves)")
    print(f"  * Class 13: {info1['classes'].get(13)} (no-gloves)")
    assert info1["classes"].get(5) == "no-mask"
    assert info1["classes"].get(6) == "gloves"
    assert info1["classes"].get(13) == "no-gloves"
    assert info1["positive_mask_support"] is False
    print("  ✓ Constructelligence model verified.")

    print("\n[Step 3] Testing Model 2: Vyra (Hexmon)...")
    info2 = switch_model(MODEL_VYRA)
    print(f"  * Active Model: {info2['display_name']}")
    print(f"  * Weights File: {info2['filename']}")
    print(f"  * Total Classes: {info2['num_classes']}")
    print(f"  * Class 1: {info2['classes'].get(1)} (Gloves)")
    print(f"  * Class 5: {info2['classes'].get(5)} (Mask - Positive Class!)")
    print(f"  * Class 6: {info2['classes'].get(6)} (NO-Gloves)")
    print(f"  * Class 9: {info2['classes'].get(9)} (NO-Mask)")
    print(f"  * Class 11: {info2['classes'].get(11)} (Person - Worker!)")
    assert info2["classes"].get(5) == "Mask"
    assert info2["classes"].get(9) == "NO-Mask"
    assert info2["classes"].get(1) == "Gloves"
    assert info2["classes"].get(6) == "NO-Gloves"
    assert info2["classes"].get(11) == "Person"
    assert info2["positive_mask_support"] is True
    print("  ✓ Vyra model verified.")

    # 3. Model-Specific Compliance Evaluation Comparison
    print("\n[Step 4] Verifying Mask & Glove Compliance under Both Models...")

    # Case A: Testing with Vyra (Active)
    print("  -- Testing Vyra Compliance Rules --")
    vyra_comp = PPEComplianceService()
    # A1: Worker wearing a mask with Vyra model
    res_mask_vyra = vyra_comp.evaluate_worker(
        worker_track_id=1,
        worker_associations=[
            {"worker_track_id": 1, "class_name": "hardhat", "confidence": 0.90, "bbox": [100, 100, 200, 200]},
            {"worker_track_id": 1, "class_name": "safety_vest", "confidence": 0.88, "bbox": [100, 200, 200, 400]},
            {"worker_track_id": 1, "class_name": "mask", "confidence": 0.86, "bbox": [120, 150, 180, 220]},
        ],
    )
    print(f"    * Vyra worker with mask: mask status = {res_mask_vyra['ppe_status']['mask']} (Expected: compliant)")
    assert res_mask_vyra["ppe_status"]["mask"] == "compliant", "Vyra must recognize positive mask as compliant"

    # A2: Worker with NO-Mask under Vyra
    res_nomask_vyra = vyra_comp.evaluate_worker(
        worker_track_id=2,
        worker_associations=[
            {"worker_track_id": 2, "class_name": "hardhat", "confidence": 0.90, "bbox": [100, 100, 200, 200]},
            {"worker_track_id": 2, "class_name": "safety_vest", "confidence": 0.88, "bbox": [100, 200, 200, 400]},
            {"worker_track_id": 2, "class_name": "no-mask", "confidence": 0.85, "bbox": [120, 150, 180, 220]},
        ],
    )
    print(f"    * Vyra worker with NO-Mask: mask status = {res_nomask_vyra['ppe_status']['mask']} (Expected: missing)")
    assert res_nomask_vyra["ppe_status"]["mask"] == "missing"
    assert "NO MASK" in res_nomask_vyra["missing_ppe_labels"]
    assert res_nomask_vyra["overall_status"] == "non_compliant"

    # Case B: Switch back to Constructelligence and test
    print("  -- Testing Constructelligence Compliance Rules --")
    switch_model(MODEL_CONSTRUCTELLIGENCE)
    const_comp = PPEComplianceService()
    # B1: If constructelligence worker has no mask detection (model cannot verify mask compliance)
    res_nomask_const = const_comp.evaluate_worker(
        worker_track_id=3,
        worker_associations=[
            {"worker_track_id": 3, "class_name": "hardhat", "confidence": 0.90, "bbox": [100, 100, 200, 200]},
            {"worker_track_id": 3, "class_name": "safety_vest", "confidence": 0.88, "bbox": [100, 200, 200, 400]},
        ],
    )
    print(f"    * Constructelligence mask without detection: {res_nomask_const['ppe_status']['mask']} (Expected: not_detected)")
    assert res_nomask_const["ppe_status"]["mask"] == "not_detected"

    # 4. MonitoringController Protection against Model Switching during Run
    print("\n[Step 5] Testing MonitoringController Model Switch Safety...")
    controller = MonitoringController()
    # Force simulated active state
    controller._state = "active"
    try:
        controller.switch_model(MODEL_VYRA)
        assert False, "Should have thrown RuntimeError when switching while active"
    except RuntimeError as re:
        print(f"  ✓ Safely blocked model switch during active monitoring: {re}")
    finally:
        controller._state = "idle"

    # Switching while idle succeeds
    res_idle_switch = controller.switch_model(MODEL_VYRA)
    assert res_idle_switch["model_id"] == MODEL_VYRA
    print(f"  ✓ Model switch while idle succeeded: {res_idle_switch['display_name']}")

    # Restore default model
    controller.switch_model(MODEL_CONSTRUCTELLIGENCE)
    assert get_active_model_id() == MODEL_CONSTRUCTELLIGENCE
    print(f"  ✓ Restored default model: {MODEL_CONSTRUCTELLIGENCE}")

    print("\n" + "=" * 80)
    print("  [SUCCESS] All dual-model verification tests PASSED! 100%")
    print("=" * 80)


if __name__ == "__main__":
    run_dual_model_verification()

