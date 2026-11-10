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
    from app.services.violation_timer_service import (
        STATUS_ALARM_ELIGIBLE,
        STATUS_ACTIVE_VIOLATION,
        ViolationTimerService,
    )
except ImportError as e:
    print(f"[FATAL] Failed to import ViolationTimerService: {e}")
    sys.exit(1)


def make_worker_eval(worker_id: int, hardhat_status: str = "compliant", vest_status: str = "compliant") -> dict:
    """Helper to generate simulated worker compliance output."""
    return {
        "worker_track_id": worker_id,
        "categories": {
            "hardhat": {"status": hardhat_status},
            "safety_vest": {"status": vest_status},
        },
    }


def run_all_timer_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - Violation Timer Service Tests")
    print("=" * 75)

    service = ViolationTimerService(default_threshold_seconds=5.0)

    # -------------------------------------------------------------
    # Scenario 1: Violation starts at time 1000
    # -------------------------------------------------------------
    print("\n[Test 1] Violation starts at time 1000.0...")
    w1 = make_worker_eval(1, hardhat_status="violation_detected")
    summary = service.update([w1], current_time=1000.0)
    timer1 = service.get_timer(1, "hardhat")

    assert timer1 is not None, "Timer should be initialized"
    assert timer1["worker_track_id"] == 1
    assert timer1["ppe_category"] == "hardhat"
    assert timer1["start_timestamp"] == 1000.0
    assert timer1["last_confirmed_timestamp"] == 1000.0
    assert timer1["elapsed_seconds"] == 0.0
    assert timer1["remaining_seconds"] == 5.0
    assert timer1["alarm_eligible"] is False
    assert timer1["violation_status"] == STATUS_ACTIVE_VIOLATION
    print("  ✓ Timer initialized at t=1000.0 (Elapsed: 0.0s, Remaining: 5.0s, Alarm-Eligible: False)")

    # -------------------------------------------------------------
    # Scenario 2: Same violation continues for 2 seconds (t=1002.0)
    # -------------------------------------------------------------
    print("\n[Test 2] Same violation continues for 2 seconds (t=1002.0)...")
    service.update([w1], current_time=1002.0)
    timer2 = service.get_timer(1, "hardhat")

    assert timer2["elapsed_seconds"] == 2.0
    assert timer2["remaining_seconds"] == 3.0
    assert timer2["alarm_eligible"] is False
    assert timer2["start_timestamp"] == 1000.0
    print(f"  ✓ Timer accumulated continuous duration: {timer2['elapsed_seconds']}s (Remaining: {timer2['remaining_seconds']}s)")

    # -------------------------------------------------------------
    # Scenario 3: Violation reaches 5 seconds and becomes alarm-eligible (t=1005.0)
    # -------------------------------------------------------------
    print("\n[Test 3] Violation reaches 5 seconds threshold (t=1005.0)...")
    service.update([w1], current_time=1005.0)
    timer3 = service.get_timer(1, "hardhat")

    assert timer3["elapsed_seconds"] == 5.0
    assert timer3["remaining_seconds"] == 0.0
    assert timer3["alarm_eligible"] is True
    assert timer3["violation_status"] == STATUS_ALARM_ELIGIBLE

    alarm_timers = service.get_alarm_eligible_timers()
    assert len(alarm_timers) == 1
    assert alarm_timers[0]["worker_track_id"] == 1
    print("  ✓ Violation reached 5.0s and transitioned to ALARM_ELIGIBLE!")

    # -------------------------------------------------------------
    # Scenario 4: Violation disappears before 5 seconds and resets
    # -------------------------------------------------------------
    print("\n[Test 4] Violation disappears before 5 seconds threshold (t=2000 to t=2003)...")
    service.reset_all()
    # Start at 2000.0
    w_viol = make_worker_eval(10, hardhat_status="violation_detected")
    service.update([w_viol], current_time=2000.0)
    service.update([w_viol], current_time=2002.0)
    assert service.get_timer(10, "hardhat")["elapsed_seconds"] == 2.0

    # Disappears at 2003.0 (e.g. category missing from worker dict)
    w_empty = {"worker_track_id": 10, "categories": {}}
    service.update([w_empty], current_time=2003.0)
    assert service.get_timer(10, "hardhat") is None, "Timer should reset when violation disappears"
    print("  ✓ Timer cleanly reset when violation disappeared before reaching 5s threshold.")

    # -------------------------------------------------------------
    # Scenario 5: Worker becomes compliant and timer resets
    # -------------------------------------------------------------
    print("\n[Test 5] Worker becomes compliant (status='compliant') -> timer resets...")
    service.reset_all()
    service.update([w_viol], current_time=3000.0)
    service.update([w_viol], current_time=3002.0)
    # Becomes compliant at 3003.0
    w_comp = make_worker_eval(10, hardhat_status="compliant")
    service.update([w_comp], current_time=3003.0)
    assert service.get_timer(10, "hardhat") is None, "Timer must reset upon compliance"
    print("  ✓ Timer reset immediately when worker became compliant.")

    # -------------------------------------------------------------
    # Scenario 6: Status becomes not_detected and timer resets
    # -------------------------------------------------------------
    print("\n[Test 6] Status becomes not_detected (absence is not violation) -> timer resets...")
    service.reset_all()
    service.update([w_viol], current_time=4000.0)
    service.update([w_viol], current_time=4002.0)
    # Becomes not_detected
    w_not_det = make_worker_eval(10, hardhat_status="not_detected")
    service.update([w_not_det], current_time=4003.0)
    assert service.get_timer(10, "hardhat") is None, "Timer must reset when status is not_detected"
    print("  ✓ Timer reset when status became not_detected (never accumulated unconfirmed time).")

    # -------------------------------------------------------------
    # Scenario 7: Status becomes uncertain and timer resets
    # -------------------------------------------------------------
    print("\n[Test 7] Status becomes uncertain (conflicting/unverified) -> timer resets...")
    service.reset_all()
    service.update([w_viol], current_time=5000.0)
    # Becomes uncertain
    w_unc = make_worker_eval(10, hardhat_status="uncertain")
    service.update([w_unc], current_time=5002.0)
    assert service.get_timer(10, "hardhat") is None, "Timer must reset when status is uncertain"
    print("  ✓ Timer reset when evidence became uncertain.")

    # -------------------------------------------------------------
    # Scenario 8: Two workers have independent violation timers
    # -------------------------------------------------------------
    print("\n[Test 8] Two workers with independent violation timelines...")
    service.reset_all()
    w_a = make_worker_eval(1, hardhat_status="violation_detected")
    w_b = make_worker_eval(2, hardhat_status="violation_detected")

    # Worker 1 violation starts at 6000.0
    service.update([w_a], current_time=6000.0)
    # Worker 2 violation starts at 6002.0 (Worker 1 continues)
    service.update([w_a, w_b], current_time=6002.0)
    # Check at 6005.0
    service.update([w_a, w_b], current_time=6005.0)

    t_a = service.get_timer(1, "hardhat")
    t_b = service.get_timer(2, "hardhat")

    assert t_a["elapsed_seconds"] == 5.0 and t_a["alarm_eligible"] is True
    assert t_b["elapsed_seconds"] == 3.0 and t_b["alarm_eligible"] is False
    print(f"  ✓ Independent timers confirmed: Worker #1 (Elapsed: {t_a['elapsed_seconds']}s, Alarm: {t_a['alarm_eligible']}) vs Worker #2 (Elapsed: {t_b['elapsed_seconds']}s, Alarm: {t_b['alarm_eligible']})")

    # -------------------------------------------------------------
    # Scenario 9: One worker has multiple independent PPE violation timers
    # -------------------------------------------------------------
    print("\n[Test 9] One worker with multiple independent category timers (hardhat + vest)...")
    service.reset_all()
    # At 7000.0: Worker has hardhat violation
    w_multi_1 = make_worker_eval(1, hardhat_status="violation_detected", vest_status="compliant")
    service.update([w_multi_1], current_time=7000.0)

    # At 7002.0: Worker additionally acquires vest violation
    w_multi_2 = make_worker_eval(1, hardhat_status="violation_detected", vest_status="violation_detected")
    service.update([w_multi_2], current_time=7002.0)

    # Check at 7005.0
    service.update([w_multi_2], current_time=7005.0)
    t_h = service.get_timer(1, "hardhat")
    t_v = service.get_timer(1, "safety_vest")

    assert t_h["elapsed_seconds"] == 5.0 and t_h["alarm_eligible"] is True
    assert t_v["elapsed_seconds"] == 3.0 and t_v["alarm_eligible"] is False
    print(f"  ✓ Multi-category independent timers: Hardhat ({t_h['elapsed_seconds']}s, Alarm: True) vs Vest ({t_v['elapsed_seconds']}s, Alarm: False)")

    # -------------------------------------------------------------
    # Scenario 10: Worker temporarily disappears
    # -------------------------------------------------------------
    print("\n[Test 10] Worker temporarily disappears from frame -> timer resets...")
    service.reset_all()
    service.update([w_viol], current_time=8000.0)
    # Next frame has 0 workers detected
    service.update([], current_time=8002.0)
    assert service.get_timer(10, "hardhat") is None, "Timer must reset when worker disappears"
    print("  ✓ Timer reset when worker was absent from frame.")

    # -------------------------------------------------------------
    # Scenario 11: Worker leaves the monitoring session
    # -------------------------------------------------------------
    print("\n[Test 11] Worker leaves the monitoring session...")
    service.reset_all()
    service.update([w_viol], current_time=9000.0)
    # Frame with other workers, Worker 10 departed
    other_worker = make_worker_eval(99, hardhat_status="compliant")
    service.update([other_worker], current_time=9005.0)
    assert service.get_timer(10, "hardhat") is None
    print("  ✓ Timer for departed worker safely cleared.")

    # -------------------------------------------------------------
    # Scenario 12: Explicit timer reset works
    # -------------------------------------------------------------
    print("\n[Test 12] Explicit single timer reset...")
    service.reset_all()
    service.update([w_viol], current_time=10000.0)
    assert service.get_timer(10, "hardhat") is not None
    was_reset = service.reset_timer(10, "hardhat")
    assert was_reset is True
    assert service.get_timer(10, "hardhat") is None
    print("  ✓ reset_timer(10, 'hardhat') executed successfully.")

    # -------------------------------------------------------------
    # Scenario 13: Entire session reset clears all timers
    # -------------------------------------------------------------
    print("\n[Test 13] Entire session reset clears all timers...")
    service.update([w_a, w_b], current_time=11000.0)
    assert len(service.get_active_timers()) == 2
    service.reset_all()
    assert len(service.get_active_timers()) == 0
    print("  ✓ reset_all() cleared all in-memory timers.")

    # -------------------------------------------------------------
    # Scenario 14: Empty input handled safely
    # -------------------------------------------------------------
    print("\n[Test 14] Empty and None inputs handled safely...")
    res_none = service.update(None)
    assert res_none["active_timers_count"] == 0
    res_empty = service.update([])
    assert res_empty["active_timers_count"] == 0
    print("  ✓ Empty and None inputs handled gracefully without exceptions.")

    # -------------------------------------------------------------
    # Scenario 15: Configurable timer threshold (e.g. 3.0 seconds)
    # -------------------------------------------------------------
    print("\n[Test 15] Configurable confirmation threshold (3.0s instead of 5.0s)...")
    custom_service = ViolationTimerService(default_threshold_seconds=3.0)
    custom_service.update([w_viol], current_time=12000.0)
    custom_service.update([w_viol], current_time=12003.0)
    t_cust = custom_service.get_timer(10, "hardhat")
    assert t_cust["threshold_seconds"] == 3.0
    assert t_cust["elapsed_seconds"] == 3.0
    assert t_cust["alarm_eligible"] is True
    print("  ✓ Custom 3.0s threshold verified: Alarm-Eligible at 3.0s.")

    print("\n" + "=" * 75)
    print("  FINAL VIOLATION TIMER SUMMARY")
    print("=" * 75)
    print("  * Total Scenarios Executed : 15")
    print("  * Scenarios Passed         : 15 (100% assertions verified)")
    print("  * Continuous 5s Rule       : PASSED (Must persist unbroken for 5.0s)")
    print("  * Immediate Reset Rules    : PASSED (Resets on compliant, not_detected, uncertain, absent)")
    print("  * Worker & Category Isolation : PASSED (Full independent tracking)")
    print("=" * 75)
    print("  [SUCCESS] Continuous PPE violation timer service verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_timer_tests()

