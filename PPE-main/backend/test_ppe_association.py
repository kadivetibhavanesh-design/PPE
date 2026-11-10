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
    from app.services.ppe_association_service import PPEAssociationService
except ImportError as e:
    print(f"[FATAL] Failed to import PPEAssociationService: {e}")
    sys.exit(1)


def make_worker(track_id: int, bbox: list) -> dict:
    """Helper to create a tracked worker dictionary."""
    return {
        "class_id": 0,
        "class_name": "person",
        "category": "workers",
        "track_id": track_id,
        "confidence": 0.90,
        "bbox": bbox,
    }


def make_ppe(class_name: str, bbox: list, category: str = "compliant", conf: float = 0.85) -> dict:
    """Helper to create a PPE detection dictionary."""
    return {
        "class_id": 1,
        "class_name": class_name,
        "category": category,
        "confidence": conf,
        "bbox": bbox,
    }


def run_all_association_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - PPE-to-Worker Association Tests")
    print("=" * 75)

    service = PPEAssociationService(
        min_association_score=0.35,
        ambiguity_margin=0.15,
        min_ioa_threshold=0.10,
    )

    # Base Worker definitions
    # Worker 1: [100, 100, 300, 500] (Width: 200, Height: 400)
    w1 = make_worker(track_id=1, bbox=[100.0, 100.0, 300.0, 500.0])
    # Worker 2: [500, 100, 700, 500] (Width: 200, Height: 400)
    w2 = make_worker(track_id=2, bbox=[500.0, 100.0, 700.0, 500.0])

    print("\n[Test 1] Hardhat correctly associated with Worker #1...")
    # Hardhat located in Worker 1 head region (ideal rel_y ~ 0.08)
    # cy = 130 -> rel_y = (130 - 100) / 400 = 0.075
    h1 = make_ppe("hardhat", [170.0, 105.0, 230.0, 155.0])
    res1 = service.associate(workers=[w1], compliant_ppe=[h1])
    assert len(res1["associations"]) == 1, "Failed: Hardhat was not associated"
    assoc = res1["associations"][0]
    assert assoc["worker_track_id"] == 1
    assert assoc["ppe_class"] == "hardhat"
    assert assoc["ppe_category"] == "compliant"
    assert assoc["body_region"] == "head"
    assert assoc["association_confidence"] > 0.60
    print(f"  ✓ Associated with Worker #{assoc['worker_track_id']} (Region: {assoc['body_region']}, Conf: {assoc['association_confidence']:.2%})")

    print("\n[Test 2] Safety vest correctly associated with Worker #1...")
    # Vest located in Worker 1 torso region (ideal rel_y ~ 0.42)
    # cy = 270 -> rel_y = (270 - 100) / 400 = 0.425
    v1 = make_ppe("safety vest", [130.0, 190.0, 270.0, 350.0])
    res2 = service.associate(workers=[w1], compliant_ppe=[v1])
    assert len(res2["associations"]) == 1
    assoc = res2["associations"][0]
    assert assoc["worker_track_id"] == 1
    assert assoc["ppe_class"] == "safety vest"
    assert assoc["body_region"] == "upper_body"
    print(f"  ✓ Associated with Worker #{assoc['worker_track_id']} (Region: {assoc['body_region']}, Conf: {assoc['association_confidence']:.2%})")

    print("\n[Test 3] No-hardhat violation associated with Worker #2...")
    nh2 = make_ppe("no-hardhat", [570.0, 105.0, 630.0, 155.0], category="violation")
    res3 = service.associate(workers=[w1, w2], violations=[nh2])
    assert len(res3["associations"]) == 1
    assoc = res3["associations"][0]
    assert assoc["worker_track_id"] == 2
    assert assoc["ppe_class"] == "no-hardhat"
    assert assoc["ppe_category"] == "violation"
    print(f"  ✓ Violation correctly mapped to Worker #{assoc['worker_track_id']} ({assoc['ppe_class']})")

    print("\n[Test 4] Two workers standing near each other (clear assignments)...")
    # Worker A [100, 100, 250, 500] and Worker B [270, 100, 420, 500]
    wa = make_worker(10, [100.0, 100.0, 250.0, 500.0])
    wb = make_worker(20, [270.0, 100.0, 420.0, 500.0])
    vest_a = make_ppe("safety vest", [120.0, 200.0, 230.0, 350.0])
    vest_b = make_ppe("safety vest", [290.0, 200.0, 400.0, 350.0])
    res4 = service.associate(workers=[wa, wb], compliant_ppe=[vest_a, vest_b])
    assert len(res4["associations"]) == 2
    worker_map = {a["ppe_bounding_box"][0]: a["worker_track_id"] for a in res4["associations"]}
    assert worker_map[120.0] == 10
    assert worker_map[290.0] == 20
    print("  ✓ Both workers received their respective safety vests cleanly.")

    print("\n[Test 5 & 9] Ambiguous PPE between workers returned as unassigned...")
    # PPE placed right on the borderline between Worker A and Worker B
    # cx = 260, overlapping both boxes equally
    borderline_ppe = make_ppe("safety vest", [210.0, 200.0, 310.0, 350.0])
    res5 = service.associate(workers=[wa, wb], compliant_ppe=[borderline_ppe])
    assert len(res5["associations"]) == 0, "Ambiguous PPE should not be forcefully assigned"
    assert len(res5["unassigned_ppe"]) == 1
    unassigned = res5["unassigned_ppe"][0]
    assert "ambiguous_between_workers" in unassigned["reason"]
    print(f"  ✓ Ambiguity detected; unassigned with reason: '{unassigned['reason']}'")

    print("\n[Test 6] PPE detection outside all worker bounding boxes...")
    stray_hardhat = make_ppe("hardhat", [800.0, 800.0, 850.0, 850.0])
    res6 = service.associate(workers=[w1, w2], compliant_ppe=[stray_hardhat])
    assert len(res6["associations"]) == 0
    assert len(res6["unassigned_ppe"]) == 1
    assert res6["unassigned_ppe"][0]["reason"] == "no_worker_spatial_match"
    print("  ✓ Stray hardhat cleanly marked as unassigned (no worker spatial match).")

    print("\n[Test 7] Missing worker tracking ID...")
    w_noid = {"class_id": 0, "class_name": "person", "track_id": None, "bbox": [100.0, 100.0, 300.0, 500.0]}
    h_test = make_ppe("hardhat", [170.0, 105.0, 230.0, 155.0])
    res7 = service.associate(workers=[w_noid], compliant_ppe=[h_test])
    assert len(res7["associations"]) == 0
    assert res7["unassigned_ppe"][0]["reason"] == "no_tracked_workers_in_frame"
    print("  ✓ Worker without valid track_id safely rejected; PPE remains unassigned.")

    print("\n[Test 8] Invalid and empty bounding boxes handled safely...")
    invalid_ppe1 = {"class_name": "hardhat", "confidence": 0.8, "bbox": []}
    invalid_ppe2 = {"class_name": "hardhat", "confidence": 0.8, "bbox": [200.0, 200.0, 100.0, 100.0]}  # x2 < x1
    res8 = service.associate(workers=[w1], compliant_ppe=[invalid_ppe1, invalid_ppe2])
    assert len(res8["associations"]) == 0
    assert len(res8["unassigned_ppe"]) == 2
    assert all(u["reason"] == "invalid_bounding_box" for u in res8["unassigned_ppe"])
    print("  ✓ Corrupted / inverted bounding boxes safely rejected without crashing.")

    print("\n[Test 10] Multiple PPE detections associated with different workers...")
    # Worker 1 has hardhat & gloves; Worker 2 has safety vest & no-hardhat
    w1_hardhat = make_ppe("hardhat", [170.0, 105.0, 230.0, 155.0])
    w1_gloves = make_ppe("gloves", [90.0, 300.0, 130.0, 350.0])
    w2_vest = make_ppe("safety vest", [530.0, 190.0, 670.0, 350.0])
    w2_no_hardhat = make_ppe("no-hardhat", [570.0, 105.0, 630.0, 155.0], category="violation")

    res10 = service.associate(
        workers=[w1, w2],
        compliant_ppe=[w1_hardhat, w1_gloves, w2_vest],
        violations=[w2_no_hardhat],
    )

    assert len(res10["associations"]) == 4
    assert res10["summary"]["total_associated"] == 4
    assert res10["summary"]["total_unassigned"] == 0
    assert res10["summary"]["workers_with_ppe"] == 2

    w1_items = [a["ppe_class"] for a in res10["associations"] if a["worker_track_id"] == 1]
    w2_items = [a["ppe_class"] for a in res10["associations"] if a["worker_track_id"] == 2]

    assert "hardhat" in w1_items and "gloves" in w1_items
    assert "safety vest" in w2_items and "no-hardhat" in w2_items
    print(f"  ✓ Multi-item association verified:")
    print(f"    - Worker #1 items : {w1_items}")
    print(f"    - Worker #2 items : {w2_items}")

    print("\n" + "=" * 75)
    print("  FINAL PPE ASSOCIATION SUMMARY")
    print("=" * 75)
    print(f"  * Total Test Scenarios Executed : 10")
    print(f"  * Total Scenarios Passed        : 10 (100% assertions verified)")
    print(f"  * Ambiguity Avoidance Tested    : PASSED (No arbitrary nearest-worker guessing)")
    print(f"  * Edge Cases & Safety Checks    : PASSED")
    print("=" * 75)
    print("  [SUCCESS] PPE-to-Worker spatial association verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_association_tests()

