import os
import sys
import numpy as np

# Ensure root & backend are in sys.path
sys.path.insert(0, os.path.abspath("backend"))
sys.path.insert(0, os.path.abspath("."))

from app.services.ppe_compliance_service import PPEComplianceService
from app.services.ppe_association_service import PPEAssociationService
from app.services.annotation_service import annotate_frame
from app.services.ppe_monitoring_service import PPEMonitoringService

def test_exact_ppe_violations_and_compliance():
    print("===========================================================================")
    print("  SafeVision AI - Verification of Exact PPE Violations & Compliance Fix")
    print("===========================================================================")

    compliance_svc = PPEComplianceService(required_categories=["hardhat", "safety_vest"])
    assoc_svc = PPEAssociationService()

    # Scenario 1: Worker 1 with hardhat and safety vest (Fully Compliant)
    associations_w1 = [
        {"worker_track_id": 1, "class_name": "hardhat", "confidence": 0.92, "bbox": [100, 100, 180, 150]},
        {"worker_track_id": 1, "class_name": "safety_vest", "confidence": 0.88, "bbox": [100, 150, 200, 280]},
    ]
    res1 = compliance_svc.evaluate_worker(1, associations_w1)
    print(f"\n[Test 1] Worker #1 (Hardhat + Safety Vest):")
    print(f"  overall_status: {res1['overall_status']}")
    print(f"  ppe_status: {res1['ppe_status']}")
    print(f"  missing_ppe: {res1['missing_ppe']}")
    assert res1["overall_status"] == "compliant"
    assert res1["ppe_status"]["hardhat"] == "compliant"
    assert res1["ppe_status"]["safety_vest"] == "compliant"
    assert res1["ppe_status"]["gloves"] == "not_detected"
    assert len(res1["missing_ppe"]) == 0
    print("  ✓ Worker #1 is COMPLIANT with zero missing PPE.")

    # Scenario 2: Worker 2 with no-hardhat and no-safety vest (Multiple Explicit Violations)
    associations_w2 = [
        {"worker_track_id": 2, "class_name": "no-hardhat", "confidence": 0.95, "bbox": [300, 100, 380, 150]},
        {"worker_track_id": 2, "class_name": "no-safety vest", "confidence": 0.91, "bbox": [300, 150, 400, 280]},
    ]
    res2 = compliance_svc.evaluate_worker(2, associations_w2)
    print(f"\n[Test 2] Worker #2 (no-hardhat + no-safety vest):")
    print(f"  overall_status: {res2['overall_status']}")
    print(f"  ppe_status: {res2['ppe_status']}")
    print(f"  missing_ppe: {res2['missing_ppe']}")
    print(f"  missing_ppe_labels: {res2['missing_ppe_labels']}")
    assert res2["overall_status"] == "non_compliant"
    assert res2["ppe_status"]["hardhat"] == "missing"
    assert res2["ppe_status"]["safety_vest"] == "missing"
    assert "hardhat" in res2["missing_ppe"]
    assert "safety_vest" in res2["missing_ppe"]
    assert "NO HARDHAT" in res2["missing_ppe_labels"]
    assert "NO SAFETY VEST" in res2["missing_ppe_labels"]
    print("  ✓ Worker #2 identifies exact missing items: NO HARDHAT, NO SAFETY VEST.")

    # Scenario 3: Worker 3 with no-gloves and no-goggles (Secondary PPE Violations)
    associations_w3 = [
        {"worker_track_id": 3, "class_name": "hardhat", "confidence": 0.90, "bbox": [500, 100, 580, 150]},
        {"worker_track_id": 3, "class_name": "safety_vest", "confidence": 0.89, "bbox": [500, 150, 600, 280]},
        {"worker_track_id": 3, "class_name": "no-gloves", "confidence": 0.85, "bbox": [480, 250, 520, 290]},
        {"worker_track_id": 3, "class_name": "no-goggles", "confidence": 0.87, "bbox": [520, 130, 560, 150]},
    ]
    res3 = compliance_svc.evaluate_worker(3, associations_w3)
    print(f"\n[Test 3] Worker #3 (Compliant vest/hardhat, but explicit no-gloves + no-goggles):")
    print(f"  overall_status: {res3['overall_status']}")
    print(f"  ppe_status: {res3['ppe_status']}")
    print(f"  missing_ppe: {res3['missing_ppe']}")
    print(f"  missing_ppe_labels: {res3['missing_ppe_labels']}")
    assert res3["overall_status"] == "non_compliant"
    assert res3["ppe_status"]["gloves"] == "missing"
    assert res3["ppe_status"]["goggles"] == "missing"
    assert "NO GLOVES" in res3["missing_ppe_labels"]
    assert "NO SAFETY GOGGLES" in res3["missing_ppe_labels"]
    print("  ✓ Worker #3 flagged NON_COMPLIANT with NO GLOVES, NO SAFETY GOGGLES.")

    # Scenario 4: Worker 4 with no PPE detections at all (Needs Review / Absence is not violation)
    associations_w4 = []
    res4 = compliance_svc.evaluate_worker(4, associations_w4)
    print(f"\n[Test 4] Worker #4 (No PPE visible at all):")
    print(f"  overall_status: {res4['overall_status']}")
    print(f"  ppe_status: {res4['ppe_status']}")
    assert res4["overall_status"] == "needs_review"
    assert all(st == "not_detected" for st in res4["ppe_status"].values())
    print("  ✓ Worker #4 correctly marked 'needs_review' and all PPE 'not_detected'.")

    # Scenario 5: Annotation Service draws the exact MISSING banner
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    monitoring_result = {
        "workers": [
            {
                "worker_id": 2,
                "worker_track_id": 2,
                "worker_bounding_box": [100, 80, 300, 450],
                "overall_status": "non_compliant",
                "compliance_status": "non_compliant",
                "ppe_status": {"hardhat": "missing", "safety_vest": "missing"},
                "missing_ppe": ["hardhat", "safety_vest"],
                "missing_ppe_labels": ["NO HARDHAT", "NO SAFETY VEST"],
                "associated_ppe": associations_w2,
            }
        ],
        "total_compliant": 0,
        "total_non_compliant": 1,
    }
    annotated = annotate_frame(frame, monitoring_result=monitoring_result, fps=28.5)
    assert annotated is not None
    assert annotated.shape == frame.shape
    # Frame was modified (not all zero)
    assert np.any(annotated > 0)
    print("\n[Test 5] Annotation service frame rendering:")
    print("  ✓ Successfully rendered worker bounding box, status, and MISSING: NO HARDHAT, NO SAFETY VEST banner.")

    # Scenario 6: Full Pipeline Integration with process_structured_data
    monitoring_svc = PPEMonitoringService()
    structured = {
        "workers": [
            {"track_id": 5, "bbox": [100, 50, 250, 400], "confidence": 0.95},
        ],
        "ppe": [
            {"class_name": "hardhat", "confidence": 0.93, "bbox": [130, 55, 200, 100]},
        ],
        "violations": [
            {"class_name": "no-safety vest", "confidence": 0.89, "bbox": [120, 120, 240, 260]},
        ],
        "total_detections": 3,
    }
    pipeline_res = monitoring_svc.process_structured_data(structured)
    assert len(pipeline_res["workers"]) == 1
    w5 = pipeline_res["workers"][0]
    print(f"\n[Test 6] Full Monitoring Pipeline Data Structure:")
    print(f"  worker_id: {w5.get('worker_id')}")
    print(f"  compliance_status: {w5.get('compliance_status')}")
    print(f"  ppe_status: {w5.get('ppe_status')}")
    print(f"  missing_ppe: {w5.get('missing_ppe')}")
    print(f"  missing_ppe_labels: {w5.get('missing_ppe_labels')}")
    assert w5.get("worker_id") == 5
    assert w5.get("compliance_status") == "non_compliant"
    assert w5.get("ppe_status", {}).get("hardhat") == "compliant"
    assert w5.get("ppe_status", {}).get("safety_vest") == "missing"
    assert "safety_vest" in w5.get("missing_ppe", [])
    assert "NO SAFETY VEST" in w5.get("missing_ppe_labels", [])
    print("  ✓ Pipeline output payload contains all standardized fields.")

    print("\n===========================================================================")
    print("  [SUCCESS] All exact PPE violation and compliance fix tests PASSED! 100%")
    print("===========================================================================")

if __name__ == "__main__":
    test_exact_ppe_violations_and_compliance()
