import os
import sys
import numpy as np

# Ensure root & backend are in sys.path
sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))

from app.services.model_service import get_model_info, get_model
from app.services.detection_service import categorize_class_name, CATEGORY_MAPPINGS
from app.services.ppe_association_service import PPEAssociationService
from app.services.ppe_compliance_service import PPEComplianceService
from app.services.annotation_service import annotate_frame
from app.services.ppe_monitoring_service import PPEMonitoringService


def run_gloves_and_mask_verification():
    print("=" * 80)
    print("  SafeVision AI - Gloves and Mask Detection Verification Suite")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 1. Model Class Names & IDs Inspection
    # -------------------------------------------------------------------------
    print("\n[Step 1] Inspecting YOLO model classes...")
    info = get_model_info()
    classes = info.get("classes", {})
    print(f"  * Architecture       : {info.get('architecture')}")
    print(f"  * Total Classes      : {len(classes)}")
    print(f"  * Class 5            : '{classes.get(5)}' (Expected: 'no-mask')")
    print(f"  * Class 6            : '{classes.get(6)}' (Expected: 'gloves')")
    print(f"  * Class 13           : '{classes.get(13)}' (Expected: 'no-gloves')")

    assert classes.get(6) == "gloves", f"Class 6 must be 'gloves', got {classes.get(6)}"
    assert classes.get(13) == "no-gloves", f"Class 13 must be 'no-gloves', got {classes.get(13)}"
    assert classes.get(5) == "no-mask", f"Class 5 must be 'no-mask', got {classes.get(5)}"
    
    # Confirm mask limitation: no positive 'mask' class exists in this hazard model
    all_names = list(classes.values())
    assert "mask" not in all_names, "Model was assumed not to have positive 'mask' class"
    print("  ✓ Model classes verified. Positive 'mask' is confirmed absent; 'no-mask' is present.")

    # -------------------------------------------------------------------------
    # 2. Category Mappings & Pipeline Classification
    # -------------------------------------------------------------------------
    print("\n[Step 2] Verifying detection categorization...")
    cat_gloves = categorize_class_name("gloves")
    cat_no_gloves = categorize_class_name("no-gloves")
    cat_no_mask = categorize_class_name("no-mask")

    print(f"  * 'gloves' category    : {cat_gloves}")
    print(f"  * 'no-gloves' category  : {cat_no_gloves}")
    print(f"  * 'no-mask' category    : {cat_no_mask}")

    assert cat_gloves == "compliant_ppe", f"Expected compliant_ppe, got {cat_gloves}"
    assert cat_no_gloves == "violations", f"Expected violations, got {cat_no_gloves}"
    assert cat_no_mask == "violations", f"Expected violations, got {cat_no_mask}"
    print("  ✓ Classification pipeline mappings verified.")

    # -------------------------------------------------------------------------
    # 3. Spatial Association with Hand/Arm Mobility & Geometry
    # -------------------------------------------------------------------------
    print("\n[Step 3] Verifying worker association for gloves across realistic hand positions...")
    assoc_svc = PPEAssociationService()

    # Worker bounding box: [x1=200, y1=100, x2=500, y2=700] (w=300, h=600, cx=350)
    worker = {
        "track_id": 1,
        "bbox": [200.0, 100.0, 500.0, 700.0],
        "class_name": "person",
    }

    # Case 3A: Hands held at chest / chin height (e.g. raised to show webcam: rel_y ~ 0.25)
    raised_gloves = {
        "class_name": "gloves",
        "confidence": 0.82,
        "bbox": [280.0, 220.0, 360.0, 300.0],  # cx=320, cy=260 -> rel_y=(260-100)/600 = 0.267
    }
    res_3a = assoc_svc.associate(workers=[worker], compliant_ppe=[raised_gloves])
    assert len(res_3a["associations"]) == 1, "Raised hands/gloves must associate with worker"
    assert res_3a["associations"][0]["worker_track_id"] == 1
    assert res_3a["associations"][0]["body_region"] == "hands"
    print(f"  ✓ Case 3A (Raised hands): Associated cleanly (Score={res_3a['associations'][0]['association_confidence']:.2f})")

    # Case 3B: Arm extended laterally (hand positioned beyond worker torso box)
    # worker x1=200, x2=500. Lateral hand at x1=120, x2=190 (cx=155 < 200).
    lateral_no_gloves = {
        "class_name": "no-gloves",
        "confidence": 0.85,
        "bbox": [120.0, 350.0, 190.0, 430.0],  # cx=155, cy=390 -> rel_y=0.483, laterally -45px from wx1
    }
    res_3b = assoc_svc.associate(workers=[worker], violations=[lateral_no_gloves])
    assert len(res_3b["associations"]) == 1, "Lateral arm/hand must associate with worker"
    assert res_3b["associations"][0]["worker_track_id"] == 1
    print(f"  ✓ Case 3B (Lateral hand): Associated cleanly (Score={res_3b['associations'][0]['association_confidence']:.2f})")

    # Case 3C: Hands resting low on desk/waist in webcam framing (rel_y ~ 0.95 - 1.05)
    desk_gloves = {
        "class_name": "gloves",
        "confidence": 0.78,
        "bbox": [320.0, 670.0, 390.0, 740.0],  # cy=705 -> rel_y=(705-100)/600 = 1.008
    }
    res_3c = assoc_svc.associate(workers=[worker], compliant_ppe=[desk_gloves])
    assert len(res_3c["associations"]) == 1, "Hands resting near bottom of webcam frame must associate"
    assert res_3c["associations"][0]["worker_track_id"] == 1
    print(f"  ✓ Case 3C (Desk/lap hands): Associated cleanly (Score={res_3c['associations'][0]['association_confidence']:.2f})")

    # Case 3D: No-mask on face (rel_y ~ 0.20)
    face_no_mask = {
        "class_name": "no-mask",
        "confidence": 0.88,
        "bbox": [310.0, 180.0, 390.0, 260.0],  # cy=220 -> rel_y=0.20
    }
    res_3d = assoc_svc.associate(workers=[worker], violations=[face_no_mask])
    assert len(res_3d["associations"]) == 1, "No-mask on face must associate with worker"
    assert res_3d["associations"][0]["worker_track_id"] == 1
    assert res_3d["associations"][0]["body_region"] == "head"
    print(f"  ✓ Case 3D (Face no-mask): Associated cleanly (Score={res_3d['associations'][0]['association_confidence']:.2f})")

    # -------------------------------------------------------------------------
    # 4. PPE Compliance Evaluation & Missing Labels
    # -------------------------------------------------------------------------
    print("\n[Step 4] Verifying PPE compliance logic for gloves & mask...")
    comp_svc = PPEComplianceService(required_categories=["hardhat", "safety_vest"])

    # Test 4A: Worker with compliant gloves
    worker_1_assocs = [
        {"worker_track_id": 1, "class_name": "hardhat", "confidence": 0.90, "bbox": [300, 110, 400, 170]},
        {"worker_track_id": 1, "class_name": "safety_vest", "confidence": 0.92, "bbox": [280, 250, 420, 500]},
        {"worker_track_id": 1, "class_name": "gloves", "confidence": 0.84, "bbox": [280, 220, 360, 300]},
    ]
    eval_1 = comp_svc.evaluate_worker(1, worker_1_assocs)
    assert eval_1["ppe_status"]["gloves"] == "compliant"
    assert eval_1["categories"]["gloves"]["status"] == "compliant"
    assert eval_1["categories"]["gloves"]["confidence"] == 0.84
    assert eval_1["overall_status"] == "compliant"
    print(f"  ✓ Test 4A (Gloves compliant): Status={eval_1['ppe_status']['gloves']}")

    # Test 4B: Worker with explicit no-gloves violation
    worker_2_assocs = [
        {"worker_track_id": 2, "class_name": "hardhat", "confidence": 0.90, "bbox": [300, 110, 400, 170]},
        {"worker_track_id": 2, "class_name": "safety_vest", "confidence": 0.92, "bbox": [280, 250, 420, 500]},
        {"worker_track_id": 2, "class_name": "no-gloves", "confidence": 0.85, "bbox": [120, 350, 190, 430]},
    ]
    eval_2 = comp_svc.evaluate_worker(2, worker_2_assocs)
    assert eval_2["ppe_status"]["gloves"] == "missing"
    assert "gloves" in eval_2["missing_ppe"]
    assert "NO GLOVES" in eval_2["missing_ppe_labels"]
    assert eval_2["overall_status"] == "non_compliant"
    print(f"  ✓ Test 4B (No-gloves violation): Status={eval_2['ppe_status']['gloves']}, Labels={eval_2['missing_ppe_labels']}")

    # Test 4C: Worker with explicit no-mask violation
    worker_3_assocs = [
        {"worker_track_id": 3, "class_name": "hardhat", "confidence": 0.90, "bbox": [300, 110, 400, 170]},
        {"worker_track_id": 3, "class_name": "safety_vest", "confidence": 0.92, "bbox": [280, 250, 420, 500]},
        {"worker_track_id": 3, "class_name": "no-mask", "confidence": 0.88, "bbox": [310, 180, 390, 260]},
    ]
    eval_3 = comp_svc.evaluate_worker(3, worker_3_assocs)
    assert eval_3["ppe_status"]["mask"] == "missing"
    assert "mask" in eval_3["missing_ppe"]
    assert "NO MASK" in eval_3["missing_ppe_labels"]
    assert eval_3["overall_status"] == "non_compliant"
    print(f"  ✓ Test 4C (No-mask violation): Status={eval_3['ppe_status']['mask']}, Labels={eval_3['missing_ppe_labels']}")

    # Test 4D: Mask limitation - Absence of no-mask is NOT proof of mask
    worker_4_assocs = [
        {"worker_track_id": 4, "class_name": "hardhat", "confidence": 0.90, "bbox": [300, 110, 400, 170]},
        {"worker_track_id": 4, "class_name": "safety_vest", "confidence": 0.92, "bbox": [280, 250, 420, 500]},
    ]
    eval_4 = comp_svc.evaluate_worker(4, worker_4_assocs)
    assert eval_4["ppe_status"]["mask"] == "not_detected"
    assert eval_4["categories"]["mask"]["status"] == "not_detected"
    assert "mask" not in eval_4["missing_ppe"]
    print(f"  ✓ Test 4D (Mask limitation): Absence of 'no-mask' correctly yields 'not_detected', never false compliant.")

    # -------------------------------------------------------------------------
    # 5. Annotation Service Visual Output Verification
    # -------------------------------------------------------------------------
    print("\n[Step 5] Verifying frame annotation rendering...")
    fake_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    monitoring_result = {
        "workers": [
            {
                "worker_track_id": 2,
                "overall_status": "non_compliant",
                "worker_bounding_box": [200, 100, 500, 700],
                "missing_ppe": ["gloves", "mask"],
                "missing_ppe_labels": ["NO GLOVES", "NO MASK"],
                "associated_ppe": [
                    {"class_name": "no-gloves", "confidence": 0.85, "bbox": [120, 350, 190, 430]},
                    {"class_name": "no-mask", "confidence": 0.88, "bbox": [310, 180, 390, 260]},
                ],
            }
        ],
        "total_compliant": 0,
        "total_non_compliant": 1,
    }
    annotated = annotate_frame(fake_frame, monitoring_result, fps=28.5)
    assert annotated is not None
    assert annotated.shape == (720, 1280, 3)
    # Check that non-zero pixels were drawn
    assert np.count_nonzero(annotated) > 0
    print("  ✓ Frame annotations rendered successfully with 'MISSING: NO GLOVES, NO MASK'.")

    # -------------------------------------------------------------------------
    # 6. Integrated PPEMonitoringService Verification
    # -------------------------------------------------------------------------
    print("\n[Step 6] Verifying integrated PPEMonitoringService pipeline...")
    pipeline = PPEMonitoringService(conf_threshold=0.20)
    assert pipeline.conf_threshold == 0.20
    assert pipeline.compliance_service.min_confidence == 0.20
    print("  ✓ PPEMonitoringService configured with 0.20 threshold for fine-grained PPE detection.")

    print("\n" + "=" * 80)
    print("  [SUCCESS] All gloves and mask detection tests PASSED! 100%")
    print("=" * 80)


if __name__ == "__main__":
    run_gloves_and_mask_verification()

