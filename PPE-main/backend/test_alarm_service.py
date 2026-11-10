import sys
from pathlib import Path
from typing import List, Tuple

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
    from app.services.alarm_service import (
        STATUS_COOLING_DOWN,
        STATUS_STOPPED,
        STATUS_TRIGGERED,
        AlarmService,
    )
except ImportError as e:
    print(f"[FATAL] Failed to import AlarmService: {e}")
    sys.exit(1)


class MockAudioPlayer:
    """Mock audio player to verify playback events without emitting sound."""

    def __init__(self):
        self.played_events: List[Tuple[int, str]] = []

    def play(self, worker_track_id: int, ppe_category: str) -> None:
        self.played_events.append((worker_track_id, ppe_category))

    def reset(self):
        self.played_events.clear()


def make_eligible_violation(worker_id: int, ppe_category: str = "hardhat", eligible: bool = True) -> dict:
    """Helper to generate simulated violation timer output."""
    return {
        "worker_track_id": worker_id,
        "ppe_category": ppe_category,
        "violation_status": "alarm_eligible" if eligible else "active_violation",
        "alarm_eligible": eligible,
        "elapsed_seconds": 5.0 if eligible else 2.0,
        "threshold_seconds": 5.0,
        "remaining_seconds": 0.0 if eligible else 3.0,
    }


def run_all_alarm_tests():
    print("=" * 75)
    print("  AI-Powered PPE Detection System - PPE Violation Alarm Service Tests")
    print("=" * 75)

    mock_audio = MockAudioPlayer()
    service = AlarmService(
        cooldown_seconds=10.0,
        sound_enabled=True,
        sound_player=mock_audio.play,
    )

    # -------------------------------------------------------------
    # Scenario 1: Alarm triggers when eligibility becomes True
    # -------------------------------------------------------------
    print("\n[Test 1] Alarm triggers when eligibility becomes True...")
    mock_audio.reset()
    v1 = make_eligible_violation(1, "hardhat", eligible=True)
    summary = service.update([v1], current_time=1005.0)

    assert summary["active_alarms_count"] == 1
    assert summary["triggered_alarms_count"] == 1
    assert len(mock_audio.played_events) == 1
    assert mock_audio.played_events[0] == (1, "hardhat")

    alarm_entry = service.get_alarm(1, "hardhat")
    assert alarm_entry is not None
    assert alarm_entry["status"] == STATUS_TRIGGERED
    assert alarm_entry["trigger_count"] == 1
    assert alarm_entry["first_triggered_timestamp"] == 1005.0
    print("  ✓ Alarm successfully triggered on eligibility (Audio played 1 time).")

    # -------------------------------------------------------------
    # Scenario 2: No alarm before 5-second eligibility
    # -------------------------------------------------------------
    print("\n[Test 2] No alarm before 5-second eligibility (alarm_eligible=False)...")
    service.reset_all()
    mock_audio.reset()
    v_not_eligible = make_eligible_violation(2, "hardhat", eligible=False)
    summary = service.update([v_not_eligible], current_time=1002.0)

    assert summary["active_alarms_count"] == 0
    assert summary["triggered_alarms_count"] == 0
    assert len(mock_audio.played_events) == 0
    assert service.get_alarm(2, "hardhat") is None
    print("  ✓ Ineligible violation correctly ignored (No audio, 0 alarms).")

    # -------------------------------------------------------------
    # Scenario 3: No repeated trigger for the same continuous violation (Anti-Spam)
    # -------------------------------------------------------------
    print("\n[Test 3] No repeated sound trigger for same continuous violation...")
    service.reset_all()
    mock_audio.reset()

    # Frame 1: Initial trigger at t=2000.0
    service.update([v1], current_time=2000.0)
    assert len(mock_audio.played_events) == 1

    # Frame 2: Same violation continues 100ms later at t=2000.1
    res2 = service.update([v1], current_time=2000.1)
    assert res2["active_alarms_count"] == 1
    assert res2["triggered_alarms_count"] == 0  # No new sound triggered
    assert len(mock_audio.played_events) == 1    # Audio play count remains 1

    # Frame 3: Same violation continues at t=2005.0 (still inside 10.0s cooldown)
    res3 = service.update([v1], current_time=2005.0)
    assert res3["active_alarms_count"] == 1
    assert res3["triggered_alarms_count"] == 0
    assert len(mock_audio.played_events) == 1
    assert service.get_alarm(1, "hardhat")["status"] == STATUS_COOLING_DOWN
    print("  ✓ Subsequent frames correctly throttled: sound did not re-trigger.")

    # -------------------------------------------------------------
    # Scenario 4: Independent alarms for two workers
    # -------------------------------------------------------------
    print("\n[Test 4] Independent alarms for two distinct workers...")
    service.reset_all()
    mock_audio.reset()

    w1_viol = make_eligible_violation(1, "hardhat", eligible=True)
    w2_viol = make_eligible_violation(2, "hardhat", eligible=True)

    # Worker 1 triggers at t=3000.0
    service.update([w1_viol], current_time=3000.0)
    assert len(mock_audio.played_events) == 1
    assert mock_audio.played_events[-1] == (1, "hardhat")

    # Worker 2 triggers at t=3002.0 while Worker 1 is cooling down
    service.update([w1_viol, w2_viol], current_time=3002.0)
    assert len(mock_audio.played_events) == 2
    assert mock_audio.played_events[-1] == (2, "hardhat")

    assert service.get_alarm(1, "hardhat") is not None
    assert service.get_alarm(2, "hardhat") is not None
    assert service.get_alarm(1, "hardhat")["status"] == STATUS_COOLING_DOWN
    assert service.get_alarm(2, "hardhat")["status"] == STATUS_TRIGGERED
    print("  ✓ Worker 1 and Worker 2 maintain independent alarm states.")

    # -------------------------------------------------------------
    # Scenario 5: Independent alarms for multiple PPE categories
    # -------------------------------------------------------------
    print("\n[Test 5] Independent alarms for multiple PPE categories on same worker...")
    service.reset_all()
    mock_audio.reset()

    w1_hardhat = make_eligible_violation(1, "hardhat", eligible=True)
    w1_vest = make_eligible_violation(1, "safety_vest", eligible=True)

    # Hardhat triggers at t=4000.0
    service.update([w1_hardhat], current_time=4000.0)
    assert len(mock_audio.played_events) == 1
    assert mock_audio.played_events[0] == (1, "hardhat")

    # Vest triggers at t=4003.0
    service.update([w1_hardhat, w1_vest], current_time=4003.0)
    assert len(mock_audio.played_events) == 2
    assert mock_audio.played_events[1] == (1, "safety_vest")

    al_h = service.get_alarm(1, "hardhat")
    al_v = service.get_alarm(1, "safety_vest")
    assert al_h is not None and al_v is not None
    assert al_h["first_triggered_timestamp"] == 4000.0
    assert al_v["first_triggered_timestamp"] == 4003.0
    print("  ✓ Multiple PPE categories trigger independently on the same worker.")

    # -------------------------------------------------------------
    # Scenario 6: Alarm reset after violation resolution
    # -------------------------------------------------------------
    print("\n[Test 6] Alarm reset after violation is resolved...")
    service.reset_all()
    mock_audio.reset()

    # Trigger at t=5000.0
    service.update([w1_hardhat], current_time=5000.0)
    assert service.get_alarm(1, "hardhat") is not None

    # Violation resolved at t=5002.0 (empty list or worker became compliant)
    service.update([], current_time=5002.0)
    assert service.get_alarm(1, "hardhat") is None, "Alarm record must be removed when violation resolves"

    # New violation appears later at t=5015.0 -> must be able to trigger again
    service.update([w1_hardhat], current_time=5015.0)
    assert service.get_alarm(1, "hardhat") is not None
    assert len(mock_audio.played_events) == 2
    print("  ✓ Alarm reset upon violation resolution and cleanly re-triggered on next episode.")

    # -------------------------------------------------------------
    # Scenario 7: Cooldown behavior
    # -------------------------------------------------------------
    print("\n[Test 7] Cooldown expiration and re-trigger behavior...")
    service.reset_all()
    mock_audio.reset()

    # Initial trigger at t=6000.0 (cooldown is 10.0s, so until t=6010.0)
    service.update([w1_hardhat], current_time=6000.0)
    assert len(mock_audio.played_events) == 1

    # At t=6009.9 (still in cooldown)
    service.update([w1_hardhat], current_time=6009.9)
    assert len(mock_audio.played_events) == 1

    # At t=6010.1 (cooldown has expired, violation persists unbroken)
    res_retrigger = service.update([w1_hardhat], current_time=6010.1)
    assert len(mock_audio.played_events) == 2
    assert res_retrigger["triggered_alarms_count"] == 1
    al_re = service.get_alarm(1, "hardhat")
    assert al_re["trigger_count"] == 2
    assert al_re["last_triggered_timestamp"] == 6010.1
    print("  ✓ Cooldown respected: re-alerted after 10.0s unbroken continuous violation.")

    # -------------------------------------------------------------
    # Scenario 8: Stop individual alarm
    # -------------------------------------------------------------
    print("\n[Test 8] Stop individual alarm...")
    service.reset_all()
    mock_audio.reset()

    service.update([w1_hardhat, w1_vest], current_time=7000.0)
    assert len(service.get_active_alarms()) == 2

    # Operator mutes/stops hardhat alarm
    was_stopped = service.stop_alarm(1, "hardhat")
    assert was_stopped is True
    assert service.get_alarm(1, "hardhat")["status"] == STATUS_STOPPED

    # Next update at t=7015.0 (cooldown expired), but stopped status prevents re-trigger
    service.update([w1_hardhat, w1_vest], current_time=7015.0)
    assert service.get_alarm(1, "hardhat")["status"] == STATUS_STOPPED
    print("  ✓ Specific alarm stopped and suppressed without affecting other alarms.")

    # -------------------------------------------------------------
    # Scenario 9: Stop all alarms
    # -------------------------------------------------------------
    print("\n[Test 9] Stop all alarms...")
    service.reset_all()
    mock_audio.reset()

    service.update([w1_hardhat, w2_viol], current_time=8000.0)
    stopped_count = service.stop_all_alarms()
    assert stopped_count == 2
    for al in service.get_active_alarms():
        assert al["status"] == STATUS_STOPPED
    print(f"  ✓ stop_all_alarms() stopped {stopped_count} active alarms.")

    # -------------------------------------------------------------
    # Scenario 10: Empty and invalid inputs
    # -------------------------------------------------------------
    print("\n[Test 10] Handling empty and invalid inputs gracefully...")
    res_none = service.update(None)
    assert res_none["active_alarms_count"] == 0
    assert res_none["triggered_alarms_count"] == 0

    res_invalid = service.update([
        {"invalid": "data"},
        {"worker_track_id": "bad_id", "ppe_category": 123},
        None,
        42,
    ])
    assert res_invalid["active_alarms_count"] == 0
    print("  ✓ None, empty, and malformed inputs handled without exceptions.")

    # -------------------------------------------------------------
    # Scenario 11: Session reset
    # -------------------------------------------------------------
    print("\n[Test 11] Session reset clears all internal state...")
    service.update([w1_hardhat, w2_viol], current_time=9000.0)
    assert len(service.get_active_alarms()) == 2
    service.reset_all()
    assert len(service.get_active_alarms()) == 0
    print("  ✓ reset_all() cleared all alarm records.")

    # -------------------------------------------------------------
    # Scenario 12: Audio playback mocked; zero real sound during test
    # -------------------------------------------------------------
    print("\n[Test 12] Audio playback mocking verified...")
    assert len(mock_audio.played_events) > 0
    print(f"  ✓ Mock audio player intercepted {len(mock_audio.played_events)} sound calls (no hardware sound).")

    print("\n" + "=" * 75)
    print("  FINAL ALARM SERVICE TEST SUMMARY")
    print("=" * 75)
    print("  * Total Scenarios Executed : 12")
    print("  * Scenarios Passed         : 12 (100% assertions verified)")
    print("  * Anti-Spam Throttling     : VERIFIED (No repeated frame-by-frame triggers)")
    print("  * Cooldown Management      : VERIFIED (10.0s cooldown between continuous alerts)")
    print("  * Isolation & Resets       : VERIFIED (Workers, categories, and resolution resets)")
    print("=" * 75)
    print("  [SUCCESS] PPE violation alarm engine verified successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_all_alarm_tests()

