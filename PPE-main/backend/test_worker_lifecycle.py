import sys
from pathlib import Path

# Set stdout to UTF-8 on Windows
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
    from app.services.worker_tracking_service import (
        STATUS_ACTIVE,
        STATUS_LEFT,
        STATUS_MISSING,
        WorkerTrackingService,
    )
except ImportError as e:
    print(f"[FATAL] Failed to import WorkerTrackingService: {e}")
    sys.exit(1)


def make_worker(track_id: int, bbox=None) -> dict:
    """Helper to generate a mock worker detection dictionary."""
    if bbox is None:
        bbox = [100.0, 150.0, 200.0, 350.0]
    return {
        "class_id": 0,
        "class_name": "person",
        "category": "workers",
        "track_id": track_id,
        "confidence": 0.88,
        "bbox": bbox,
    }


def run_all_lifecycle_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - Worker Tracking Lifecycle Tests")
    print("=" * 75)

    # 5.0 seconds departure timeout
    service = WorkerTrackingService(timeout_seconds=5.0)
    current_time = 1000.0

    print(f"\nConfigured Worker Departure Timeout: {service.timeout_seconds} seconds")
    print("-" * 75)

    # -------------------------------------------------------------
    # Scenario 1: A new worker appears
    # -------------------------------------------------------------
    print("\n[Scenario 1] A new worker (#1) appears in the scene...")
    stats = service.update([make_worker(1)], current_time=current_time)
    w1 = service.get_worker(1)

    assert w1 is not None, "Worker #1 was not created"
    assert w1.track_id == 1
    assert w1.first_seen == current_time
    assert w1.last_seen == current_time
    assert w1.total_frames_detected == 1
    assert w1.current_status == STATUS_ACTIVE
    assert stats["total_workers_observed"] == 1
    assert stats["active_count"] == 1
    assert stats["active_ids"] == [1]
    print(f"  ✓ Worker #1 registered as ACTIVE (First Seen: {w1.first_seen:.1f}s)")

    # -------------------------------------------------------------
    # Scenario 2: The same worker appears across multiple frames
    # -------------------------------------------------------------
    print("\n[Scenario 2] Worker #1 appears across multiple consecutive frames...")
    for step in range(1, 4):
        current_time += 0.5
        stats = service.update([make_worker(1)], current_time=current_time)

    w1 = service.get_worker(1)
    assert w1.total_frames_detected == 4, f"Expected 4 frames detected, got {w1.total_frames_detected}"
    assert w1.last_seen == current_time
    assert w1.current_status == STATUS_ACTIVE
    assert stats["active_count"] == 1
    print(f"  ✓ Worker #1 detected across {w1.total_frames_detected} frames; status remains ACTIVE")

    # -------------------------------------------------------------
    # Scenario 3: A second worker appears
    # -------------------------------------------------------------
    print("\n[Scenario 3] Second worker (#2) appears alongside Worker #1...")
    current_time += 0.5
    stats = service.update([make_worker(1), make_worker(2)], current_time=current_time)

    assert stats["total_workers_observed"] == 2
    assert stats["active_count"] == 2
    assert stats["active_ids"] == [1, 2]
    w2 = service.get_worker(2)
    assert w2 is not None and w2.current_status == STATUS_ACTIVE
    print(f"  ✓ Worker #2 registered; 2 workers simultaneously ACTIVE: {stats['active_ids']}")

    # -------------------------------------------------------------
    # Scenario 4: Worker #1 temporarily disappears
    # -------------------------------------------------------------
    print("\n[Scenario 4] Worker #1 temporarily disappears (only Worker #2 visible)...")
    current_time += 1.0  # 1.0s elapsed (< 5.0s timeout)
    stats = service.update([make_worker(2)], current_time=current_time)

    w1 = service.get_worker(1)
    w2 = service.get_worker(2)
    assert w1.current_status == STATUS_MISSING, f"Expected Worker #1 MISSING, got {w1.current_status}"
    assert w2.current_status == STATUS_ACTIVE
    assert stats["active_count"] == 1
    assert stats["missing_count"] == 1
    assert stats["active_ids"] == [2]
    assert stats["missing_ids"] == [1]
    print(f"  ✓ Worker #1 marked as MISSING (Absent for 1.0s < 5.0s timeout); Worker #2 ACTIVE")

    # -------------------------------------------------------------
    # Scenario 5: Worker #1 reappears before timeout
    # -------------------------------------------------------------
    print("\n[Scenario 5] Worker #1 reappears before timeout...")
    current_time += 1.5  # Total absent was 2.5s < 5.0s
    stats = service.update([make_worker(1), make_worker(2)], current_time=current_time)

    w1 = service.get_worker(1)
    assert w1.current_status == STATUS_ACTIVE, f"Expected Worker #1 to return to ACTIVE, got {w1.current_status}"
    assert stats["active_count"] == 2
    assert stats["missing_count"] == 0
    print(f"  ✓ Worker #1 successfully reactivated from MISSING to ACTIVE: {stats['active_ids']}")

    # -------------------------------------------------------------
    # Scenario 6: A worker remains absent beyond timeout
    # -------------------------------------------------------------
    print("\n[Scenario 6] Worker #2 remains absent beyond timeout (6.0s > 5.0s)...")
    # Time jumps by 6.0 seconds while only Worker #1 is present
    current_time += 6.0
    stats = service.update([make_worker(1)], current_time=current_time)

    w2 = service.get_worker(2)
    assert w2.current_status == STATUS_LEFT, f"Expected Worker #2 to be LEFT, got {w2.current_status}"
    assert stats["active_count"] == 1
    assert stats["left_count"] == 1
    assert stats["left_ids"] == [2]
    assert stats["active_ids"] == [1]
    print(f"  ✓ Worker #2 marked as LEFT (Absent > 5.0s threshold); Worker #1 remains ACTIVE")

    # -------------------------------------------------------------
    # Scenario 7: Empty detection frames
    # -------------------------------------------------------------
    print("\n[Scenario 7] Processing empty detection frames (no workers detected)...")
    current_time += 1.0
    # Pass empty list
    stats = service.update([], current_time=current_time)

    w1 = service.get_worker(1)
    w2 = service.get_worker(2)
    assert w1.current_status == STATUS_MISSING, f"Expected Worker #1 MISSING on empty frame, got {w1.current_status}"
    assert w2.current_status == STATUS_LEFT
    assert stats["active_count"] == 0
    assert stats["missing_count"] == 1
    assert stats["left_count"] == 1
    print(f"  ✓ Empty frame handled safely: Active=0, Missing=1 (Worker #1), Left=1 (Worker #2)")

    # -------------------------------------------------------------
    # Scenario 8: Multiple workers active simultaneously
    # -------------------------------------------------------------
    print("\n[Scenario 8] Multiple workers active simultaneously (Worker #1 returns + Worker #3 arrives)...")
    current_time += 1.0
    stats = service.update([make_worker(1), make_worker(3)], current_time=current_time)

    w1 = service.get_worker(1)
    w3 = service.get_worker(3)
    w2 = service.get_worker(2)

    assert w1.current_status == STATUS_ACTIVE
    assert w3.current_status == STATUS_ACTIVE
    assert w2.current_status == STATUS_LEFT
    assert stats["total_workers_observed"] == 3
    assert stats["active_count"] == 2
    assert stats["missing_count"] == 0
    assert stats["left_count"] == 1
    assert stats["active_ids"] == [1, 3]
    assert stats["left_ids"] == [2]
    print(f"  ✓ Multiple workers active: Active={stats['active_ids']}, Left={stats['left_ids']}")

    # -------------------------------------------------------------
    # Record Structure Verification
    # -------------------------------------------------------------
    print("\n[Record Schema Check] Validating WorkerRecord structure...")
    record_dict = w1.to_dict()
    expected_fields = [
        "track_id",
        "first_seen",
        "last_seen",
        "confidence",
        "total_frames_detected",
        "current_status",
        "last_known_bounding_box",
    ]
    for field in expected_fields:
        assert field in record_dict, f"Missing field '{field}' in WorkerRecord"
    print("  ✓ WorkerRecord fields and types verified:")
    for k, v in record_dict.items():
        print(f"    - {k:<25}: {v}")

    print("\n" + "=" * 75)
    print("  FINAL SESSION STATISTICS SUMMARY")
    print("=" * 75)
    print(f"  * Total Workers Observed   : {stats['total_workers_observed']}")
    print(f"  * Active Workers Count     : {stats['active_count']} (IDs: {stats['active_ids']})")
    print(f"  * Temporarily Missing      : {stats['missing_count']} (IDs: {stats['missing_ids']})")
    print(f"  * Departed Workers (Left)  : {stats['left_count']} (IDs: {stats['left_ids']})")
    print("=" * 75)
    print("  [SUCCESS] All 8 worker lifecycle scenarios passed with 100% assertions!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_lifecycle_tests()
