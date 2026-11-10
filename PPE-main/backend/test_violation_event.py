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
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from app.services.violation_event_service import (
        SEVERITY_CRITICAL,
        SEVERITY_HIGH,
        SEVERITY_MEDIUM,
        SEVERITY_UNCLASSIFIED,
        STATUS_CLOSED,
        STATUS_ONGOING,
        STATUS_OPEN,
        STATUS_RESOLVED,
        ViolationEventService,
    )
except ImportError as e:
    print(f"[FATAL] Failed to import ViolationEventService: {e}")
    sys.exit(1)


def make_eligible_item(worker_id: int, ppe_category: str = "hardhat", start_ts: float = 1000.0, eligible: bool = True) -> dict:
    """Helper to simulate alarm-eligible violation data."""
    return {
        "worker_track_id": worker_id,
        "ppe_category": ppe_category,
        "start_timestamp": start_ts,
        "alarm_eligible": eligible,
        "elapsed_seconds": 5.0,
        "violation_status": "alarm_eligible",
    }


def run_all_event_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - Violation Event Service Tests")
    print("=" * 75)

    service = ViolationEventService()

    # -------------------------------------------------------------
    # Scenario 1: Event creation when violation becomes alarm-eligible
    # -------------------------------------------------------------
    print("\n[Test 1] Event creation upon alarm eligibility...")
    item1 = make_eligible_item(1, "hardhat", start_ts=1000.0)
    summary = service.update([item1], current_time=1005.0)

    assert summary["total_events_count"] == 1
    assert summary["active_events_count"] == 1
    events = service.get_all_events()
    assert len(events) == 1
    e1 = events[0]
    assert e1["event_id"] == "EVT-0001"
    assert e1["worker_track_id"] == 1
    assert e1["ppe_category"] == "hardhat"
    assert e1["severity"] == SEVERITY_CRITICAL
    assert e1["status"] == STATUS_OPEN
    assert e1["start_timestamp"] == 1000.0
    assert e1["confirmation_timestamp"] == 1005.0
    assert e1["last_updated_timestamp"] == 1005.0
    assert e1["violation_duration"] == 5.0
    print(f"  ✓ Event {e1['event_id']} created in 'open' status with duration {e1['violation_duration']}s.")

    # -------------------------------------------------------------
    # Scenario 2: Event remains ongoing during continuous violation
    # -------------------------------------------------------------
    print("\n[Test 2] Event transitions to 'ongoing' as continuous violation persists...")
    summary2 = service.update([item1], current_time=1007.5)
    e1_updated = service.get_event("EVT-0001")
    assert e1_updated is not None
    assert e1_updated["status"] == STATUS_ONGOING
    assert e1_updated["last_updated_timestamp"] == 1007.5
    assert e1_updated["violation_duration"] == 7.5
    print(f"  ✓ Event {e1_updated['event_id']} status='ongoing', updated duration: {e1_updated['violation_duration']}s.")

    # -------------------------------------------------------------
    # Scenario 3: No duplicate event per continuous episode
    # -------------------------------------------------------------
    print("\n[Test 3] No duplicate event created during continuous episode...")
    service.update([item1], current_time=1010.0)
    events_all = service.get_all_events()
    assert len(events_all) == 1, "Should have exactly 1 event record for the episode"
    assert events_all[0]["event_id"] == "EVT-0001"
    print("  ✓ Zero duplicate events created across 3 frames of continuous violation.")

    # -------------------------------------------------------------
    # Scenario 4: Event resolves when violation disappears
    # -------------------------------------------------------------
    print("\n[Test 4] Event transitions to 'resolved' when violation is no longer confirmed...")
    # Empty list represents violation resolved or worker compliant
    service.update([], current_time=1012.0)
    e1_resolved = service.get_event("EVT-0001")
    assert e1_resolved is not None
    assert e1_resolved["status"] == STATUS_RESOLVED
    assert e1_resolved["resolution_timestamp"] == 1012.0
    assert e1_resolved["violation_duration"] == 12.0
    assert len(service.get_active_events()) == 0
    print(f"  ✓ Event {e1_resolved['event_id']} resolved at t={e1_resolved['resolution_timestamp']}.")

    # -------------------------------------------------------------
    # Scenario 5: New event ID after a new violation episode
    # -------------------------------------------------------------
    print("\n[Test 5] New event ID created for a subsequent violation episode...")
    item1_new_episode = make_eligible_item(1, "hardhat", start_ts=2000.0)
    service.update([item1_new_episode], current_time=2005.0)

    events_after = service.get_all_events()
    assert len(events_after) == 2
    e2 = service.get_event("EVT-0002")
    assert e2 is not None
    assert e2["event_id"] == "EVT-0002"
    assert e2["worker_track_id"] == 1
    assert e2["ppe_category"] == "hardhat"
    assert e2["status"] == STATUS_OPEN
    assert e2["start_timestamp"] == 2000.0
    print(f"  ✓ Subsequent episode assigned distinct event ID: {e2['event_id']}.")

    # -------------------------------------------------------------
    # Scenario 6: Independent events for two workers
    # -------------------------------------------------------------
    print("\n[Test 6] Independent events for two distinct workers...")
    service.reset_all()
    w1_item = make_eligible_item(10, "hardhat", start_ts=3000.0)
    w2_item = make_eligible_item(20, "hardhat", start_ts=3002.0)

    service.update([w1_item], current_time=3005.0)
    service.update([w1_item, w2_item], current_time=3007.0)

    w1_events = service.get_events_for_worker(10)
    w2_events = service.get_events_for_worker(20)
    assert len(w1_events) == 1 and len(w2_events) == 1
    assert w1_events[0]["event_id"] == "EVT-0001" and w1_events[0]["status"] == STATUS_ONGOING
    assert w2_events[0]["event_id"] == "EVT-0002" and w2_events[0]["status"] == STATUS_OPEN
    print("  ✓ Independent tracking verified across different worker IDs.")

    # -------------------------------------------------------------
    # Scenario 7: Multiple PPE categories consolidated for one worker
    # -------------------------------------------------------------
    print("\n[Test 7] Multiple PPE categories consolidated into one incident per worker...")
    service.reset_all()
    w1_hardhat = make_eligible_item(1, "hardhat", start_ts=4000.0)
    w1_vest = make_eligible_item(1, "safety_vest", start_ts=4001.0)

    service.update([w1_hardhat, w1_vest], current_time=4006.0)
    worker_1_events = service.get_events_for_worker(1)
    assert len(worker_1_events) == 1, f"Expected 1 consolidated incident for Worker #1, got {len(worker_1_events)}"
    e_w1 = worker_1_events[0]
    assert e_w1["event_id"] == "EVT-0001"
    assert "hardhat" in e_w1["ppe_categories"]
    assert "safety_vest" in e_w1["ppe_categories"]
    assert e_w1["severity"] == SEVERITY_CRITICAL, "Highest severity should be critical"
    print(f"  ✓ Multi-category consolidated event created for Worker #1: {e_w1['event_id']} with {e_w1['ppe_categories']} [{e_w1['severity']}]")

    # -------------------------------------------------------------
    # Scenario 8: Severity mapping
    # -------------------------------------------------------------
    print("\n[Test 8] Severity classification mapping verification...")
    assert service.classify_severity("hardhat") == SEVERITY_CRITICAL
    assert service.classify_severity("safety_vest") == SEVERITY_HIGH
    assert service.classify_severity("safety_shoes") == SEVERITY_HIGH
    assert service.classify_severity("gloves") == SEVERITY_MEDIUM
    assert service.classify_severity("goggles") == SEVERITY_MEDIUM
    assert service.classify_severity("mask") == SEVERITY_MEDIUM
    print("  ✓ Severity mapping for all target PPE categories verified.")

    # -------------------------------------------------------------
    # Scenario 9: Unknown category handling
    # -------------------------------------------------------------
    print("\n[Test 9] Unknown PPE category handling...")
    unk_item = make_eligible_item(99, "unknown_gear", start_ts=5000.0)
    service.update([w1_hardhat, w1_vest, unk_item], current_time=5005.0)
    e_unk = service.get_events_for_worker(99)[0]
    assert e_unk["severity"] == SEVERITY_UNCLASSIFIED
    print(f"  ✓ Unknown category safely tagged as: '{e_unk['severity']}'.")

    # -------------------------------------------------------------
    # Scenario 10: Retrieve events by worker
    # -------------------------------------------------------------
    print("\n[Test 10] Retrieve events by worker ID...")
    evts_w1 = service.get_events_for_worker(1)
    assert len(evts_w1) == 1
    evts_w99 = service.get_events_for_worker(99)
    assert len(evts_w99) == 1
    assert len(service.get_events_for_worker(9999)) == 0
    print("  ✓ get_events_for_worker() returned accurate scoped records.")

    # -------------------------------------------------------------
    # Scenario 11: Retrieve events by status
    # -------------------------------------------------------------
    print("\n[Test 11] Retrieve events by status...")
    active_evts = service.get_active_events()
    assert len(active_evts) == 2  # EVT-0001 (Worker 1), EVT-0002 (Worker 99)
    resolved_evts = service.get_events_by_status(STATUS_RESOLVED)
    assert len(resolved_evts) == 0
    print("  ✓ get_events_by_status() matches active and filtered states.")

    # -------------------------------------------------------------
    # Scenario 12: Explicit event closure
    # -------------------------------------------------------------
    print("\n[Test 12] Explicit event closure (audit action)...")
    target_id = active_evts[0]["event_id"]
    was_closed = service.close_event(target_id, current_time=6000.0)
    assert was_closed is True
    closed_record = service.get_event(target_id)
    assert closed_record["status"] == STATUS_CLOSED
    assert closed_record["closure_timestamp"] == 6000.0
    assert len(service.get_events_by_status(STATUS_CLOSED)) == 1
    print(f"  ✓ Event {target_id} successfully closed explicitly.")

    # -------------------------------------------------------------
    # Scenario 13: Session reset
    # -------------------------------------------------------------
    print("\n[Test 13] Session reset clears all in-memory events...")
    service.reset_all()
    assert len(service.get_all_events()) == 0
    assert len(service.get_active_events()) == 0
    summary_empty = service.get_summary()
    assert summary_empty["total_events_count"] == 0
    print("  ✓ reset_all() cleared all storage and reset event ID counter.")

    # -------------------------------------------------------------
    # Scenario 14: Empty and invalid inputs
    # -------------------------------------------------------------
    print("\n[Test 14] Empty and invalid inputs handled safely...")
    res_none = service.update(None)
    assert res_none["total_events_count"] == 0
    res_malformed = service.update([
        {"worker_track_id": None},
        "not_a_dict",
        {"worker_track_id": "invalid", "ppe_category": 123},
    ])
    assert res_malformed["total_events_count"] == 0
    print("  ✓ Malformed, empty, and None payloads handled gracefully without exceptions.")

    # -------------------------------------------------------------
    # Scenario 15: Event summary counts
    # -------------------------------------------------------------
    print("\n[Test 15] Event summary counts validation...")
    service.reset_all()
    # Add 1 worker with critical (hardhat) and high (vest)
    service.update([
        make_eligible_item(1, "hardhat", start_ts=7000.0),
        make_eligible_item(1, "safety_vest", start_ts=7000.0),
    ], current_time=7005.0)

    summary_final = service.get_summary(current_time=7005.0)
    assert summary_final["total_events_count"] == 1
    assert summary_final["active_events_count"] == 1
    assert summary_final["by_status"][STATUS_OPEN] == 1
    assert summary_final["by_severity"][SEVERITY_CRITICAL] == 1
    assert summary_final["by_category"]["hardhat"] == 1
    assert summary_final["by_category"]["safety_vest"] == 1
    print("  ✓ Summary metrics aggregated correctly across status, severity, and category.")

    print("\n" + "=" * 75)
    print("  FINAL VIOLATION EVENT SERVICE TEST SUMMARY")
    print("=" * 75)
    print("  * Total Scenarios Executed : 15")
    print("  * Scenarios Passed         : 15 (100% assertions verified)")
    print("  * Lifecycle Flow           : OPEN -> ONGOING -> RESOLVED -> CLOSED")
    print("  * Severity Classification  : VERIFIED (Critical, High, Medium, Unclassified)")
    print("  * Event Scoping & History  : VERIFIED (Worker & Status lookup, Aggregated metrics)")
    print("=" * 75)
    print("  [SUCCESS] Violation event management service verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_event_tests()
