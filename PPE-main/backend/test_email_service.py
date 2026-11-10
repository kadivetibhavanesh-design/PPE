import copy
from email.mime.multipart import MIMEMultipart
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import List, Tuple

# Route logging to sys.stdout to prevent PowerShell NativeCommandError
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from main import app
from app.services.email_service import EmailService, is_valid_email
from app.services.violation_event_service import (
    ViolationEventService,
    ViolationEventRecord,
    STATUS_OPEN,
    STATUS_ONGOING,
    STATUS_RESOLVED,
    STATUS_CLOSED,
)
from app.services.violation_timer_service import ViolationTimerService
from app.services.settings_service import get_settings_service


def run_comprehensive_email_tests():
    print("=" * 70)
    print("SafeVision AI - Automatic Email Alert & Reminder System Test Suite")
    print("=" * 70)

    # Setup isolated temporary storage directory
    temp_dir = Path(tempfile.mkdtemp(prefix="safevision_email_test_"))
    state_file = temp_dir / "email_state.json"
    history_file = temp_dir / "email_history.json"
    evidence_dir = temp_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Controllable virtual clock
    simulated_time = 1000.0

    def mock_time():
        nonlocal simulated_time
        return simulated_time

    # Captured dispatched emails: [(msg, recipient, has_attachment, timestamp)]
    sent_emails: List[Tuple[MIMEMultipart, str, bool, float]] = []

    def mock_smtp_transport(msg: MIMEMultipart, recipient: str, has_attachment: bool) -> Tuple[bool, str]:
        sent_emails.append((msg, recipient, has_attachment, mock_time()))
        return True, ""

    try:
        # ---------------------------------------------------------------------
        # TEST 1: Email Address Validation
        # ---------------------------------------------------------------------
        print("\n[TEST 1] Email Address Validation...")
        assert is_valid_email("bhavaneshkadiveti@gmail.com") is True
        assert is_valid_email("safety-admin@industrial-site.co.uk") is True
        assert is_valid_email("invalid-email") is False
        assert is_valid_email("@no-user.com") is False
        assert is_valid_email("user@no-tld") is False
        assert is_valid_email("") is False
        print("PASS: Email validator correctly validated valid and rejected invalid emails.")

        # ---------------------------------------------------------------------
        # TEST 2: EmailService Initialization & Default Recipient
        # ---------------------------------------------------------------------
        print("\n[TEST 2] Initialization & Default Recipient...")
        email_svc = EmailService(
            config={
                "enabled": True,
                "recipient_email": "bhavaneshkadiveti@gmail.com",
                "reminder_interval_minutes": 5,
            },
            state_file=state_file,
            history_file=history_file,
            evidence_dir=evidence_dir,
            time_provider=mock_time,
        )
        email_svc.set_mock_transport(mock_smtp_transport)
        # Enable camera monitoring for active monitoring tests
        email_svc.set_camera_monitoring_active(True, reason="test_start")
        cfg = email_svc.get_config(mask_password=True)
        assert cfg["recipient_email"] == "bhavaneshkadiveti@gmail.com"
        assert cfg["reminder_interval_minutes"] == 5
        print(f"PASS: Default recipient is '{cfg['recipient_email']}', interval: {cfg['reminder_interval_minutes']}m.")

        # ---------------------------------------------------------------------
        # TEST 3: Short Violation (< 5s) Sends NO Email
        # ---------------------------------------------------------------------
        print("\n[TEST 3] Violation shorter than 5 seconds sends no email...")
        timer_svc = ViolationTimerService(default_threshold_seconds=5.0)
        event_svc = ViolationEventService()
        email_svc.attach_to_violation_event_service(event_svc)

        # Worker #1 missing hardhat detected at t=1000.0
        active_violations = [
            {
                "worker_track_id": 1,
                "categories": {
                    "hardhat": {"status": "missing", "display_name": "Hardhat"}
                },
            }
        ]
        timer_svc.update(active_violations, current_time=1000.0)

        # At t=1003.0 (3.0s elapsed - below 5s confirmation threshold)
        timers = timer_svc.update(active_violations, current_time=1003.0)
        alarm_eligible = timer_svc.get_alarm_eligible_timers()
        assert len(alarm_eligible) == 0, "Timer should not be alarm-eligible before 5 seconds!"
        event_svc.update(alarm_eligible, current_time=1003.0)

        assert len(sent_emails) == 0, "No emails should be sent for violation < 5 seconds!"
        print("PASS: 3.0s violation did not confirm and sent 0 emails.")

        # ---------------------------------------------------------------------
        # TEST 4: Confirmed Violation (>= 5s) Immediately Sends First Alert
        # ---------------------------------------------------------------------
        print("\n[TEST 4] Violation confirmed after 5 seconds sends First Alert...")
        # Create dummy evidence image file EVT-0001.jpg
        (evidence_dir / "EVT_0001.jpg").write_bytes(b"DUMMY_JPEG_EVIDENCE_BYTES")

        simulated_time = 1005.1
        timer_svc.update(active_violations, current_time=simulated_time)
        alarm_eligible = timer_svc.get_alarm_eligible_timers()
        assert len(alarm_eligible) == 1, "Violation should now be alarm eligible (>= 5s)!"

        # Event service updates, creates EVT-0001, fires on_created
        event_svc.update(alarm_eligible, current_time=simulated_time)

        # Allow worker thread to execute
        time.sleep(0.1)

        assert len(sent_emails) == 1, f"Expected exactly 1 email sent, got {len(sent_emails)}"
        msg, recipient, has_att, ts = sent_emails[0]
        assert recipient == "bhavaneshkadiveti@gmail.com"
        assert "New PPE Violation Detected" in msg["Subject"]
        assert "EVT-0001" in msg["Subject"]
        assert has_att is True, "Evidence image EVT_0001.jpg should be attached!"
        print(f"PASS: First Alert sent immediately to {recipient} with Subject: '{msg['Subject']}' and attachment.")

        # ---------------------------------------------------------------------
        # TEST 5: Repeated Frames Within 5 Minutes Send No Duplicate Emails
        # ---------------------------------------------------------------------
        print("\n[TEST 5] Repeated video frames do NOT send duplicate emails...")
        # Simulate 10 frames over next 60 seconds
        for step in range(1, 10):
            simulated_time = 1005.1 + (step * 5.0)
            timer_svc.update(active_violations, current_time=simulated_time)
            eligible = timer_svc.get_alarm_eligible_timers()
            event_svc.update(eligible, current_time=simulated_time)
            email_svc.check_due_reminders()

        time.sleep(0.05)
        assert len(sent_emails) == 1, "No duplicate emails should be sent during the 5-minute interval!"
        print("PASS: Repeated frames over 45s sent 0 duplicate emails.")

        # ---------------------------------------------------------------------
        # TEST 6: Ongoing Violation Triggers Reminder After 5 Minutes (300s)
        # ---------------------------------------------------------------------
        print("\n[TEST 6] Ongoing violation triggers Reminder #1 after 5 minutes...")
        # Advance clock to exactly 1005.1 + 300.0 = 1305.1
        simulated_time = 1306.0
        timer_svc.update(active_violations, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        event_svc.update(eligible, current_time=simulated_time)

        # Evaluate reminder scheduler
        dispatched = email_svc.check_due_reminders()
        time.sleep(0.1)

        assert "EVT-0001" in dispatched
        assert len(sent_emails) == 2, f"Expected 2 emails, got {len(sent_emails)}"
        rem1_msg, rem1_recip, _, _ = sent_emails[1]
        assert "Ongoing PPE Violation Reminder #1" in rem1_msg["Subject"]
        assert "EVT-0001" in rem1_msg["Subject"]
        print(f"PASS: Reminder #1 triggered at 5-minute mark with Subject: '{rem1_msg['Subject']}'.")

        # ---------------------------------------------------------------------
        # TEST 7: Further Ongoing Violation Triggers Reminder #2 at +5 min (600s)
        # ---------------------------------------------------------------------
        print("\n[TEST 7] Ongoing violation triggers Reminder #2 after another 5 minutes...")
        simulated_time = 1607.0  # +301 seconds
        timer_svc.update(active_violations, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        event_svc.update(eligible, current_time=simulated_time)

        dispatched = email_svc.check_due_reminders()
        time.sleep(0.1)

        assert "EVT-0001" in dispatched
        assert len(sent_emails) == 3, f"Expected 3 emails, got {len(sent_emails)}"
        rem2_msg, _, _, _ = sent_emails[2]
        assert "Ongoing PPE Violation Reminder #2" in rem2_msg["Subject"]
        print(f"PASS: Reminder #2 triggered at 10-minute mark with Subject: '{rem2_msg['Subject']}'.")

        # ---------------------------------------------------------------------
        # TEST 8: Incident Resolution IMMEDIATELY Cancels Future Reminders
        # ---------------------------------------------------------------------
        print("\n[TEST 8] Incident resolution cancels all future reminders...")
        # Worker equips hardhat at t=1650.0
        simulated_time = 1650.0
        timer_svc.update([], current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        assert len(eligible) == 0, "No violations eligible once corrected."
        event_svc.update(eligible, current_time=simulated_time)

        # Verify event EVT-0001 is now RESOLVED
        rec = event_svc.get_event("EVT-0001")
        assert rec is not None
        rec_status = rec.get("status") if isinstance(rec, dict) else getattr(rec, "status", None)
        assert rec_status == STATUS_RESOLVED

        # Advance time by another 10 minutes (to t=2250.0)
        simulated_time = 2250.0
        dispatched = email_svc.check_due_reminders()
        time.sleep(0.05)

        assert len(dispatched) == 0
        assert len(sent_emails) == 3, "No reminders should be sent after resolution!"
        print("PASS: After worker corrected hardhat, 0 reminders were sent despite 10 minutes elapsed.")

        # ---------------------------------------------------------------------
        # TEST 9: New Incident After Resolution Starts Fresh Schedule
        # ---------------------------------------------------------------------
        print("\n[TEST 9] New incident after resolution starts fresh notification schedule...")
        simulated_time = 3000.0
        active_violations = [{
            "worker_track_id": 1,
            "categories": {
                "safety_vest": {"status": "missing", "display_name": "Safety Vest"}
            }
        }]
        timer_svc.update(active_violations, current_time=simulated_time)

        # Confirm after 5 seconds at t=3006.0
        simulated_time = 3006.0
        timer_svc.update(active_violations, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.1)

        assert len(sent_emails) == 4, f"Expected 4 total emails, got {len(sent_emails)}"
        new_msg, _, _, _ = sent_emails[3]
        assert "New PPE Violation Detected" in new_msg["Subject"]
        assert "EVT-0002" in new_msg["Subject"]
        print("PASS: New incident EVT-0002 started fresh schedule with First Alert.")

        # ---------------------------------------------------------------------
        # TEST 10: Multiple Active Incidents Maintain Independent Schedules
        # ---------------------------------------------------------------------
        print("\n[TEST 10] Multiple active incidents maintain independent schedules...")
        # Worker #2 also commits a violation at t=3010.0
        simulated_time = 3010.0
        multi_violations = [
            {
                "worker_track_id": 1,
                "categories": {
                    "safety_vest": {"status": "missing", "display_name": "Safety Vest"}
                }
            },
            {
                "worker_track_id": 2,
                "categories": {
                    "gloves": {"status": "missing", "display_name": "Gloves"}
                }
            }
        ]
        timer_svc.update(multi_violations, current_time=simulated_time)

        # Confirm Worker #2 at t=3016.0
        simulated_time = 3016.0
        timer_svc.update(multi_violations, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.1)

        assert len(sent_emails) == 5, f"Expected 5 total emails, got {len(sent_emails)}"
        evt3_msg, _, _, _ = sent_emails[4]
        assert "EVT-0003" in evt3_msg["Subject"]

        # Status check: two active schedules exist
        status_data = email_svc.get_status()
        active_schedules = status_data["active_incident_schedules"]
        active_eids = [s["incident_id"] for s in active_schedules]
        assert "EVT-0002" in active_eids
        assert "EVT-0003" in active_eids
        print(f"PASS: Two concurrent incidents (EVT-0002, EVT-0003) tracked with independent schedules.")

        # ---------------------------------------------------------------------
        # TEST 11: Backend Restart Restores State Without Duplicate First Alerts
        # ---------------------------------------------------------------------
        print("\n[TEST 11] Backend restart restores schedule without duplicate first alert...")
        email_svc.stop_scheduler()

        # Instantiate a new EmailService loading from the same state and history files
        restarted_svc = EmailService(
            config={
                "enabled": True,
                "recipient_email": "bhavaneshkadiveti@gmail.com",
                "reminder_interval_minutes": 5,
            },
            state_file=state_file,
            history_file=history_file,
            evidence_dir=evidence_dir,
            time_provider=mock_time,
        )
        restarted_svc.set_mock_transport(mock_smtp_transport)

        # Check restored state: total_emails_sent is preserved, but stale reminder schedules are NOT restored
        restored_status = restarted_svc.get_status()
        assert restored_status["total_emails_sent"] >= 5
        # Per camera-state lifecycle rules, idle startup clears active reminder schedules to prevent ghost emails
        assert len(restored_status["active_incident_schedules"]) == 0

        # When camera is started, already notified events in history must still NOT resend duplicate first alert
        restarted_svc.set_camera_monitoring_active(True, reason="restart_camera")
        count_before = len(sent_emails)
        restarted_svc.on_incident_confirmed({"event_id": "EVT-0002", "worker_track_id": 1, "ppe_category": "safety_vest"})
        time.sleep(0.05)
        assert len(sent_emails) == count_before, "Restarted service must NOT send duplicate first alert!"
        print("PASS: Restarted service safely handled state without restoring stale reminder jobs or duplicate first alert.")

        # ---------------------------------------------------------------------
        # TEST 12: Disabled Notifications Send No Emails
        # ---------------------------------------------------------------------
        print("\n[TEST 12] Disabled notifications send no emails...")
        restarted_svc.update_config({"enabled": False})
        restarted_svc.on_incident_confirmed({"event_id": "EVT-0099", "worker_track_id": 9, "ppe_category": "goggles"})
        time.sleep(0.05)
        assert len(sent_emails) == count_before, "No email when notifications are disabled!"
        print("PASS: Disabled email notifications suppressed transmission.")

        # ---------------------------------------------------------------------
        # TEST 13: Test Email Verification
        # ---------------------------------------------------------------------
        print("\n[TEST 13] Test Email independent verification...")
        success, msg_result = restarted_svc.send_test_email("bhavaneshkadiveti@gmail.com")
        time.sleep(0.05)
        assert success is True
        assert len(sent_emails) == count_before + 1
        test_email_msg, test_recip, _, _ = sent_emails[-1]
        assert "Test" in test_email_msg["Subject"]
        assert test_recip == "bhavaneshkadiveti@gmail.com"
        print(f"PASS: Test email dispatched successfully: {msg_result}")

        # ---------------------------------------------------------------------
        # TEST 14: SMTP Failure Handling & Bounded Retry
        # ---------------------------------------------------------------------
        print("\n[TEST 14] SMTP failure handling does not crash monitoring...")
        def failing_transport(msg, recip, att):
            return False, "Simulated SMTP connection timeout"

        restarted_svc.set_mock_transport(failing_transport)
        restarted_svc.update_config({"enabled": True})
        success, _ = restarted_svc.send_test_email("bhavaneshkadiveti@gmail.com")
        assert success is False
        history = restarted_svc.get_history(limit=5)
        assert history[0]["status"] == "failed"
        assert "Simulated SMTP" in history[0]["error"]
        print("PASS: SMTP failure recorded gracefully in history without crashing.")

        restarted_svc.stop_scheduler()

        # ---------------------------------------------------------------------
        # TEST 15: Consolidated Single Email Per Worker Incident Verification
        # ---------------------------------------------------------------------
        print("\n[TEST 15] Multi-Violation Single Email Consolidation...")
        consol_timer_svc = ViolationTimerService(default_threshold_seconds=5.0)
        consol_event_svc = ViolationEventService()
        consol_email_svc = EmailService(
            config={
                "enabled": True,
                "recipient_email": "bhavaneshkadiveti@gmail.com",
                "reminder_interval_minutes": 5,
            },
            state_file=temp_dir / "consol_email_state.json",
            history_file=temp_dir / "consol_email_history.json",
            evidence_dir=evidence_dir,
            time_provider=mock_time,
        )
        consol_emails: List[Tuple[MIMEMultipart, str, bool, float]] = []

        def mock_consol_transport(msg: MIMEMultipart, recipient: str, has_att: bool) -> Tuple[bool, str]:
            consol_emails.append((msg, recipient, has_att, mock_time()))
            return True, ""

        consol_email_svc.set_mock_transport(mock_consol_transport)
        consol_email_svc.set_camera_monitoring_active(True, reason="test_consol_start")
        consol_email_svc.attach_to_violation_event_service(consol_event_svc)

        # Step 1: Worker #10 has 3 simultaneous violations (hardhat, safety_vest, gloves)
        simulated_time = 5000.0
        multi_cats_worker10 = [
            {
                "worker_track_id": 10,
                "categories": {
                    "hardhat": {"status": "missing", "display_name": "Hardhat"},
                    "safety_vest": {"status": "missing", "display_name": "Safety Vest"},
                    "gloves": {"status": "missing", "display_name": "Gloves"},
                },
            }
        ]
        consol_timer_svc.update(multi_cats_worker10, current_time=simulated_time)

        # Before 5s confirmation threshold: 0 emails
        simulated_time = 5003.0
        consol_timer_svc.update(multi_cats_worker10, current_time=simulated_time)
        eligible = consol_timer_svc.get_alarm_eligible_timers()
        consol_event_svc.update(eligible, current_time=simulated_time)
        assert len(consol_emails) == 0, "No email before 5s continuous confirmation"

        # At 5.1s threshold: confirmation reached
        simulated_time = 5005.1
        consol_timer_svc.update(multi_cats_worker10, current_time=simulated_time)
        eligible = consol_timer_svc.get_alarm_eligible_timers()
        assert len(eligible) == 3, f"Expected 3 eligible violation categories, got {len(eligible)}"

        # Create dummy evidence image EVT_0001.jpg
        (evidence_dir / "EVT-0001.jpg").write_bytes(b"DUMMY_EVIDENCE_FOR_CONSOLIDATED_TEST")

        consol_event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.1)

        # Core Assertion 1: EXACTLY ONE EMAIL SENT FOR ALL 3 VIOLATIONS
        assert len(consol_emails) == 1, (
            f"REQUIRED BEHAVIOR FAILED: Expected exactly 1 consolidated email for Worker #10, "
            f"but {len(consol_emails)} were sent!"
        )
        first_msg, first_recip, first_att, _ = consol_emails[0]
        assert "New PPE Violation Detected" in first_msg["Subject"]
        assert "EVT-0001" in first_msg["Subject"]
        assert first_recip == "bhavaneshkadiveti@gmail.com"
        assert first_att is True, "Consolidated incident must attach evidence photo"

        # Verify all 3 violations are listed in the email payload
        def get_all_text(m):
            parts = []
            for p in m.walk():
                if p.get_content_type() in ("text/plain", "text/html"):
                    data = p.get_payload(decode=True)
                    if data:
                        parts.append(data.decode("utf-8", errors="replace"))
            return "\n".join(parts)

        body_text = get_all_text(first_msg)
        assert "Hardhat" in body_text
        assert "Safety Vest" in body_text
        assert "Gloves" in body_text
        print("  ✓ Exactly ONE consolidated First Alert sent for Worker #10 containing all 3 violations.")

        # Step 2: Additional violation (goggles) detected for Worker #10 while incident is active
        simulated_time = 5030.0
        multi_cats_worker10[0]["categories"]["goggles"] = {"status": "missing", "display_name": "Goggles"}
        # Pre-seed goggles timer so it becomes eligible after 5s at 5035.1
        consol_timer_svc.update(multi_cats_worker10, current_time=simulated_time)

        simulated_time = 5036.0
        consol_timer_svc.update(multi_cats_worker10, current_time=simulated_time)
        eligible = consol_timer_svc.get_alarm_eligible_timers()
        consol_event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.05)

        # Core Assertion 2: NO NEW IMMEDIATE EMAIL SENT when adding violation to active worker
        assert len(consol_emails) == 1, (
            f"REQUIRED BEHAVIOR FAILED: Adding a violation while incident is active must not send an immediate email! "
            f"Total emails: {len(consol_emails)}"
        )
        print("  ✓ Adding 'goggles' updated existing incident without sending immediate duplicate email.")

        # Step 3: Repeated frames over next 4 minutes send 0 duplicate emails
        for step in range(1, 10):
            simulated_time = 5040.0 + (step * 20.0)
            consol_timer_svc.update(multi_cats_worker10, current_time=simulated_time)
            eligible = consol_timer_svc.get_alarm_eligible_timers()
            consol_event_svc.update(eligible, current_time=simulated_time)
            consol_email_svc.check_due_reminders()

        time.sleep(0.05)
        assert len(consol_emails) == 1, "Repeated frames sent duplicate email during 5m window!"
        print("  ✓ 10 repeated frames within 5-minute interval sent 0 duplicate emails.")

        # Step 4: 5-minute mark reached -> ONE consolidated reminder sent with ALL 4 violations
        simulated_time = 5306.0
        consol_timer_svc.update(multi_cats_worker10, current_time=simulated_time)
        eligible = consol_timer_svc.get_alarm_eligible_timers()
        consol_event_svc.update(eligible, current_time=simulated_time)

        dispatched = consol_email_svc.check_due_reminders()
        time.sleep(0.1)

        assert "EVT-0001" in dispatched
        assert len(consol_emails) == 2, f"Expected exactly 2 total emails (1 initial + 1 reminder), got {len(consol_emails)}"
        rem1_msg, _, _, _ = consol_emails[1]
        assert "Ongoing PPE Violation Reminder #1" in rem1_msg["Subject"]
        rem1_str = get_all_text(rem1_msg)
        assert "Hardhat" in rem1_str
        assert "Safety Vest" in rem1_str
        assert "Gloves" in rem1_str
        assert "Goggles" in rem1_str
        print("  ✓ Consolidated Reminder #1 dispatched at 5m mark containing all 4 violations.")

        # Step 5: Worker #20 (different worker) commits violation -> gets independent consolidated incident
        simulated_time = 5310.0
        worker20_payload = [
            multi_cats_worker10[0],
            {
                "worker_track_id": 20,
                "categories": {
                    "mask": {"status": "missing", "display_name": "Mask"},
                    "safety_shoes": {"status": "missing", "display_name": "Safety Shoes"},
                },
            },
        ]
        consol_timer_svc.update(worker20_payload, current_time=simulated_time)

        simulated_time = 5316.0
        consol_timer_svc.update(worker20_payload, current_time=simulated_time)
        eligible = consol_timer_svc.get_alarm_eligible_timers()
        consol_event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.1)

        assert len(consol_emails) == 3, f"Expected 3 emails, got {len(consol_emails)}"
        w20_msg, _, _, _ = consol_emails[2]
        assert "EVT-0002" in w20_msg["Subject"]
        w20_str = get_all_text(w20_msg)
        assert "Mask" in w20_str
        assert "Safety Shoes" in w20_str
        print("  ✓ Worker #20 received independent consolidated incident (EVT-0002) with 1 initial email.")

        # Step 6: Worker #10 corrects all PPE -> reminders stop immediately for Worker #10
        simulated_time = 5400.0
        only_worker20 = [worker20_payload[1]]  # Worker 10 has 0 violations now
        consol_timer_svc.update(only_worker20, current_time=simulated_time)
        eligible = consol_timer_svc.get_alarm_eligible_timers()
        consol_event_svc.update(eligible, current_time=simulated_time)

        # Worker 10 event EVT-0001 is now resolved
        e10 = consol_event_svc.get_event("EVT-0001")
        assert e10["status"] == STATUS_RESOLVED

        # Advance to Worker #20's reminder time (5316 + 300 = 5616s)
        simulated_time = 5617.0
        consol_timer_svc.update(only_worker20, current_time=simulated_time)
        eligible = consol_timer_svc.get_alarm_eligible_timers()
        consol_event_svc.update(eligible, current_time=simulated_time)

        dispatched = consol_email_svc.check_due_reminders()
        time.sleep(0.1)

        # Reminder dispatched ONLY for Worker #20 (EVT-0002), NEVER for resolved Worker #10
        assert "EVT-0002" in dispatched
        assert "EVT-0001" not in dispatched
        assert len(consol_emails) == 4, f"Expected 4 total emails, got {len(consol_emails)}"
        rem_w20_msg, _, _, _ = consol_emails[3]
        assert "EVT-0002" in rem_w20_msg["Subject"]
        print("  ✓ Worker #10 reminders stopped immediately upon resolution; Worker #20 continued independently.")

        consol_email_svc.stop_scheduler()

    finally:
        # Cleanup temporary files
        shutil.rmtree(temp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # TEST 16: REST API Endpoints Verification via FastAPI TestClient
    # -------------------------------------------------------------
    print("\n[TEST 16] REST API Endpoints Verification...")
    client = TestClient(app)

    # 1. GET /api/settings/email
    res = client.get("/api/settings/email")
    assert res.status_code == 200, f"GET /api/settings/email failed: {res.text}"
    email_settings = res.json()
    assert email_settings["recipient_email"] == "bhavaneshkadiveti@gmail.com"
    assert "smtp_password" not in email_settings or email_settings["smtp_password"] == "******" or email_settings["smtp_password"] == ""
    print(f"PASS: GET /api/settings/email returned default recipient: {email_settings['recipient_email']}")

    # 2. PUT /api/settings/email (Valid update)
    res = client.put(
        "/api/settings/email",
        json={
            "recipient_email": "bhavaneshkadiveti@gmail.com",
            "enabled": True,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "reminder_interval_minutes": 5,
        },
    )
    assert res.status_code == 200, f"PUT /api/settings/email failed: {res.text}"
    assert res.json()["success"] is True
    print("PASS: PUT /api/settings/email saved configuration successfully.")

    # 3. PUT /api/settings/email (Invalid email validation)
    res = client.put("/api/settings/email", json={"recipient_email": "invalid-email-format"})
    assert res.status_code == 400, "Invalid email must return HTTP 400 Bad Request!"
    print("PASS: PUT /api/settings/email rejected invalid email format.")

    # 4. GET /api/notifications/email/status
    res = client.get("/api/notifications/email/status")
    assert res.status_code == 200, f"GET status failed: {res.text}"
    status_payload = res.json()
    assert "recipient_email" in status_payload
    assert "total_emails_sent" in status_payload
    assert "active_incident_schedules" in status_payload
    print(f"PASS: GET /api/notifications/email/status operational.")

    # 5. GET /api/notifications/email/history
    res = client.get("/api/notifications/email/history")
    assert res.status_code == 200, f"GET history failed: {res.text}"
    history_payload = res.json()
    assert "history" in history_payload
    print(f"PASS: GET /api/notifications/email/history returned {history_payload['total_records']} records.")

    print("\n" + "=" * 70)
    print("ALL 16 AUTOMATIC EMAIL ALERT & REMINDER SYSTEM TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    run_comprehensive_email_tests()
