import sys
from pathlib import Path

# Ensure stdout uses UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from app.services.ppe_compliance_service import (
        OVERALL_COMPLIANT,
        OVERALL_NEEDS_REVIEW,
        OVERALL_NON_COMPLIANT,
        PPEComplianceService,
        STATUS_COMPLIANT,
        STATUS_NOT_DETECTED,
        STATUS_UNCERTAIN,
        STATUS_VIOLATION,
    )
except ImportError as e:
    print(f"[FATAL] Failed to import PPEComplianceService: {e}")
    sys.exit(1)


def make_assoc(worker_id: int, ppe_class: str, category: str = "compliant", conf: float = 0.85) -> dict:
    """Helper to create a mock associated PPE detection dictionary."""
    return {
        "worker_track_id": worker_id,
        "ppe_class": ppe_class,
        "ppe_category": category,
        "ppe_confidence": conf,
        "ppe_bounding_box": [100.0, 100.0, 200.0, 200.0],
        "association_confidence": 0.95,
    }


def run_all_compliance_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - PPE Compliance Engine Tests")
    print("=" * 75)

    service = PPEComplianceService(
        required_categories=["hardhat", "safety_vest"],
        min_confidence=0.30,
    )

    print("\n[Test 1] Worker with all required PPE detected...")
    w1_assocs = [
        make_assoc(1, "hardhat", "compliant", 0.85),
        make_assoc(1, "safety vest", "compliant", 0.90),
    ]
    r1 = service.evaluate_worker(1, w1_assocs)
    assert r1["overall_status"] == OVERALL_COMPLIANT
    assert r1["compliant_count"] == 2
    assert r1["violation_count"] == 0
    assert r1["categories"]["hardhat"]["status"] == STATUS_COMPLIANT
    assert r1["categories"]["safety_vest"]["status"] == STATUS_COMPLIANT
    print(f"  ✓ Worker #1 is {r1['overall_status'].upper()} ({r1['overall_reason']})")

    print("\n[Test 2] Worker with explicit no-hardhat violation...")
    w2_assocs = [
        make_assoc(2, "no-hardhat", "violation", 0.88),
        make_assoc(2, "safety vest", "compliant", 0.85),
    ]
    r2 = service.evaluate_worker(2, w2_assocs)
    assert r2["overall_status"] == OVERALL_NON_COMPLIANT
    assert r2["violation_count"] == 1
    assert r2["categories"]["hardhat"]["status"] == STATUS_VIOLATION
    assert r2["categories"]["safety_vest"]["status"] == STATUS_COMPLIANT
    print(f"  ✓ Worker #2 is {r2['overall_status'].upper()} (Hardhat: {r2['categories']['hardhat']['status']})")

    print("\n[Test 3] Worker with no-safety-vest violation...")
    w3_assocs = [
        make_assoc(3, "hardhat", "compliant", 0.85),
        make_assoc(3, "no-safety vest", "violation", 0.82),
    ]
    r3 = service.evaluate_worker(3, w3_assocs)
    assert r3["overall_status"] == OVERALL_NON_COMPLIANT
    assert r3["violation_count"] == 1
    assert r3["categories"]["safety_vest"]["status"] == STATUS_VIOLATION
    print(f"  ✓ Worker #3 is {r3['overall_status'].upper()} (Vest: {r3['categories']['safety_vest']['status']})")

    print("\n[Test 4] Worker with multiple explicit violations...")
    w4_assocs = [
        make_assoc(4, "no-hardhat", "violation", 0.85),
        make_assoc(4, "no-safety vest", "violation", 0.88),
    ]
    r4 = service.evaluate_worker(4, w4_assocs)
    assert r4["overall_status"] == OVERALL_NON_COMPLIANT
    assert r4["violation_count"] == 2
    print(f"  ✓ Worker #4 is {r4['overall_status'].upper()} (Violations: {r4['violation_count']})")

    print("\n[Test 5] Worker with NO PPE detections (Absence is NOT a violation)...")
    r5 = service.evaluate_worker(5, [])
    assert r5["overall_status"] == OVERALL_NEEDS_REVIEW
    assert r5["violation_count"] == 0, "Absence of detection must NEVER be marked as violation"
    assert r5["not_detected_count"] == 2
    assert r5["categories"]["hardhat"]["status"] == STATUS_NOT_DETECTED
    assert r5["categories"]["safety_vest"]["status"] == STATUS_NOT_DETECTED
    print(f"  ✓ Worker #5 is {r5['overall_status'].upper()} (Violations: {r5['violation_count']}, Missing: {r5['not_detected_count']})")

    print("\n[Test 6] Worker with missing PPE evidence (partial detection)...")
    w6_assocs = [make_assoc(6, "hardhat", "compliant", 0.85)]
    r6 = service.evaluate_worker(6, w6_assocs)
    assert r6["overall_status"] == OVERALL_NEEDS_REVIEW
    assert r6["compliant_count"] == 1
    assert r6["not_detected_count"] == 1
    assert r6["violation_count"] == 0
    print(f"  ✓ Worker #6 is {r6['overall_status'].upper()} (Hardhat compliant, vest unconfirmed)")

    print("\n[Test 7] Worker with conflicting compliant and violation detections...")
    w7_assocs = [
        make_assoc(7, "hardhat", "compliant", 0.85),
        make_assoc(7, "no-hardhat", "violation", 0.80),
        make_assoc(7, "safety vest", "compliant", 0.90),
    ]
    r7 = service.evaluate_worker(7, w7_assocs)
    assert r7["categories"]["hardhat"]["status"] == STATUS_UNCERTAIN
    assert "Conflicting evidence" in r7["categories"]["hardhat"]["reason"]
    assert r7["overall_status"] == OVERALL_NEEDS_REVIEW
    print(f"  ✓ Worker #7 conflict handled: Hardhat={r7['categories']['hardhat']['status']} ({r7['categories']['hardhat']['reason']})")

    print("\n[Test 8] Worker with uncertain evidence (low confidence)...")
    w8_assocs = [
        make_assoc(8, "hardhat", "compliant", 0.20),  # < 0.30 threshold
        make_assoc(8, "safety vest", "compliant", 0.85),
    ]
    r8 = service.evaluate_worker(8, w8_assocs)
    assert r8["categories"]["hardhat"]["status"] == STATUS_UNCERTAIN
    assert "below confidence threshold" in r8["categories"]["hardhat"]["reason"]
    assert r8["overall_status"] == OVERALL_NEEDS_REVIEW
    print(f"  ✓ Worker #8 low confidence handled: Hardhat={r8['categories']['hardhat']['status']}")

    print("\n[Test 9] Category without compliant model class (mask)...")
    # Category 'mask' has 'no-mask' violation, but no compliant class
    r9_empty = service.evaluate_worker(9, [], required_categories=["mask"])
    assert r9_empty["categories"]["mask"]["status"] == STATUS_NOT_DETECTED
    assert r9_empty["overall_status"] == OVERALL_NEEDS_REVIEW

    # If no-mask violation detected
    r9_viol = service.evaluate_worker(9, [make_assoc(9, "no-mask", "violation", 0.85)], required_categories=["mask"])
    assert r9_viol["categories"]["mask"]["status"] == STATUS_VIOLATION
    assert r9_viol["overall_status"] == OVERALL_NON_COMPLIANT
    print("  ✓ Mask category correctly distinguishes 'violation_detected' vs 'not_detected' (never false compliant).")

    print("\n[Test 10] Multiple workers with different statuses in single payload...")
    frame_assocs = [
        make_assoc(101, "hardhat", "compliant", 0.85),
        make_assoc(101, "safety vest", "compliant", 0.85),
        make_assoc(102, "no-hardhat", "violation", 0.88),
        make_assoc(102, "safety vest", "compliant", 0.85),
    ]
    # Worker 103 has no detections in frame
    frame_eval = service.evaluate_all(frame_assocs, worker_track_ids=[101, 102, 103])
    assert frame_eval["total_workers"] == 3
    assert frame_eval["compliant_workers"] == 1
    assert frame_eval["non_compliant_workers"] == 1
    assert frame_eval["needs_review_workers"] == 1
    assert frame_eval["worker_evaluations"][101]["overall_status"] == OVERALL_COMPLIANT
    assert frame_eval["worker_evaluations"][102]["overall_status"] == OVERALL_NON_COMPLIANT
    assert frame_eval["worker_evaluations"][103]["overall_status"] == OVERALL_NEEDS_REVIEW
    print("  ✓ Multi-worker evaluation verified: 1 Compliant, 1 Non-Compliant, 1 Needs Review.")

    print("\n[Test 11] Unassigned PPE detections do not affect worker compliance...")
    payload_with_unassigned = {
        "associations": [
            make_assoc(201, "hardhat", "compliant", 0.85),
            make_assoc(201, "safety vest", "compliant", 0.85),
        ],
        "unassigned_ppe": [
            {"ppe_class": "no-hardhat", "ppe_category": "violation", "ppe_confidence": 0.95, "reason": "no_worker_match"}
        ],
    }
    eval11 = service.evaluate_all(payload_with_unassigned, worker_track_ids=[201])
    assert eval11["worker_evaluations"][201]["overall_status"] == OVERALL_COMPLIANT
    print("  ✓ Stray unassigned violation in frame did NOT taint Worker #201 compliance.")

    print("\n[Test 12] Configurable required PPE categories and confidence threshold...")
    # Expand required categories to include 'gloves'
    custom_service = PPEComplianceService(
        required_categories=["hardhat", "safety_vest", "gloves"],
        min_confidence=0.50,
    )
    # Worker with hardhat (0.85) and vest (0.85), but no gloves
    r12_a = custom_service.evaluate_worker(301, [
        make_assoc(301, "hardhat", "compliant", 0.85),
        make_assoc(301, "safety vest", "compliant", 0.85),
    ])
    assert r12_a["overall_status"] == OVERALL_NEEDS_REVIEW
    assert r12_a["not_detected_count"] == 1  # gloves missing

    # Add compliant gloves
    r12_b = custom_service.evaluate_worker(301, [
        make_assoc(301, "hardhat", "compliant", 0.85),
        make_assoc(301, "safety vest", "compliant", 0.85),
        make_assoc(301, "gloves", "compliant", 0.85),
    ])
    assert r12_b["overall_status"] == OVERALL_COMPLIANT

    # High confidence threshold test (e.g. 0.90)
    r12_c = custom_service.evaluate_worker(301, [
        make_assoc(301, "hardhat", "compliant", 0.85),
        make_assoc(301, "safety vest", "compliant", 0.85),
        make_assoc(301, "gloves", "compliant", 0.85),
    ], min_confidence=0.90)
    assert r12_c["overall_status"] == OVERALL_NEEDS_REVIEW
    print("  ✓ Configurable required categories (3 items) and confidence threshold verified.")

    print("\n" + "=" * 75)
    print("  FINAL PPE COMPLIANCE ENGINE SUMMARY")
    print("=" * 75)
    print("  * Total Scenarios Executed    : 12")
    print("  * Scenarios Passed            : 12 (100% assertions verified)")
    print("  * Absence != Violation Rule   : PASSED (Never infers violation from missing data)")
    print("  * Conflict Resolution (Uncertain): PASSED")
    print("  * Unassigned Isolation        : PASSED")
    print("=" * 75)
    print("  [SUCCESS] PPE compliance evaluation engine verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_compliance_tests()

