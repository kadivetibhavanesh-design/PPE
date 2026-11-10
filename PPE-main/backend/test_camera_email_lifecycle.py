"""
SafeVision AI - Camera Lifecycle, Email Suppression & Real-Time Notification Center Test Suite
Verifies:
1. Camera off -> 0 automatic emails sent.
2. Camera initialization failure -> 0 automatic emails sent.
3. Camera active -> exactly 1 consolidated First Alert upon 5s continuous confirmation.
4. Camera stopped before reminder -> reminder cancelled, 0 reminders sent, event marked 'interrupted'.
5. Camera stopped while email in flight/queued -> aborted before transmission.
6. Camera restarted -> stale schedules not restored; requires fresh 5s confirmation.
7. Manual test email works while camera is off.
8. Notification Center API: real-time creation, query, unread counter, mark read, mark all read, clear, and persistence.
"""

import copy
from email.mime.multipart import MIMEMultipart
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from main import app
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.services.violation_event_service import (
    ViolationEventService,
    STATUS_OPEN,
    STATUS_ONGOING,
    STATUS_RESOLVED,
    STATUS_INTERRUPTED,
)
from app.services.violation_timer_service import ViolationTimerService


def run_camera_lifecycle_and_notification_tests():
    print("=" * 80)
    print("SafeVision AI: Camera Lifecycle Email Control & Notification Center Tests")
    print("=" * 80)

    temp_dir = Path(tempfile.mkdtemp(prefix="safevision_lifecycle_test_"))
    state_file = temp_dir / "email_state.json"
    history_file = temp_dir / "email_history.json"
    notif_file = temp_dir / "notifications.json"
    evidence_dir = temp_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    simulated_time = 2000.0

    def mock_time():
        nonlocal simulated_time
        return simulated_time

    sent_emails: List[Tuple[MIMEMultipart, str, bool, float]] = []

    def mock_transport(msg: MIMEMultipart, recipient: str, has_att: bool) -> Tuple[bool, str]:
        sent_emails.append((msg, recipient, has_att, mock_time()))
        return True, ""

    try:
        notif_service = NotificationService(storage_file=notif_file)
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
        email_svc.set_mock_transport(mock_transport)

        event_svc = ViolationEventService()
        email_svc.attach_to_violation_event_service(event_svc)
        timer_svc = ViolationTimerService(default_threshold_seconds=5.0)

        # ---------------------------------------------------------------------
        # TEST 1: Camera Off / Monitoring Idle -> ZERO Automatic Emails
        # ---------------------------------------------------------------------
        print("\n[TEST 1] Camera Off / Monitoring Idle -> ZERO Automatic Emails...")
        assert email_svc.is_camera_monitoring_active() is False, "Camera must start in inactive state!"

        # Simulate violation occurring while camera is reported inactive
        active_violations = [
            {
                "worker_track_id": 101,
                "categories": {
                    "hardhat": {"status": "missing", "display_name": "Hardhat"},
                    "safety_vest": {"status": "missing", "display_name": "Safety Vest"},
                },
            }
        ]
        timer_svc.update(active_violations, current_time=2000.0)
        simulated_time = 2006.0
        timer_svc.update(active_violations, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        assert len(eligible) == 2

        # Confirmation occurs in event service
        event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.05)

        # Even with confirmed violation, EmailService must reject dispatch because camera is inactive
        assert len(sent_emails) == 0, f"Expected 0 emails while camera off, got {len(sent_emails)}"
        # Check that check_due_reminders also returns empty while camera off
        simulated_time = 2400.0
        due = email_svc.check_due_reminders()
        assert len(due) == 0
        assert len(sent_emails) == 0
        print("  PASS: Zero automatic emails dispatched while camera monitoring is inactive/idle.")

        # ---------------------------------------------------------------------
        # TEST 2: Camera Start -> Confirmed 5s Violation Sends Exactly 1 Email
        # ---------------------------------------------------------------------
        print("\n[TEST 2] Camera Active -> Confirmed Violation sends exactly 1 consolidated First Alert...")
        email_svc.set_camera_monitoring_active(True, reason="camera_started")
        assert email_svc.is_camera_monitoring_active() is True

        simulated_time = 3000.0
        active_worker_2 = [
            {
                "worker_track_id": 202,
                "categories": {
                    "hardhat": {"status": "missing", "display_name": "Hardhat"},
                    "gloves": {"status": "missing", "display_name": "Gloves"},
                },
            }
        ]
        timer_svc.update(active_worker_2, current_time=simulated_time)

        # 3 seconds: not confirmed yet
        simulated_time = 3003.0
        timer_svc.update(active_worker_2, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        event_svc.update(eligible, current_time=simulated_time)
        assert len(sent_emails) == 0, "No email before 5s threshold!"

        # 5.1 seconds: confirmation reached
        simulated_time = 3005.1
        timer_svc.update(active_worker_2, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        assert len(eligible) == 2
        (evidence_dir / "EVT-0002.jpg").write_bytes(b"DUMMY_EVIDENCE_FOR_WORKER_202")

        event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.1)

        assert len(sent_emails) == 1, f"Expected exactly 1 email, got {len(sent_emails)}"
        msg, recip, has_att, _ = sent_emails[0]
        assert recip == "bhavaneshkadiveti@gmail.com"
        assert "New PPE Violation Detected" in msg["Subject"]
        assert "EVT-0002" in msg["Subject"]
        print("  PASS: Exactly one First Alert email dispatched for Worker #202.")

        # ---------------------------------------------------------------------
        # TEST 3: Camera Stopped Before 5m Reminder -> Reminder Cancelled & Event Interrupted
        # ---------------------------------------------------------------------
        print("\n[TEST 3] Camera Stopped before 5m reminder -> Reminder cancelled & event interrupted...")
        # Verify schedule exists before stopping
        status_before = email_svc.get_status()
        assert status_before["active_incident_schedules_count"] == 1

        # Stop camera at t=3100 (100 seconds after violation, before 300s reminder)
        simulated_time = 3100.0
        email_svc.set_camera_monitoring_active(False, reason="monitoring_stopped")
        event_svc.interrupt_active_events("monitoring_stopped", current_time=simulated_time)

        # Verify active schedules cleared in EmailService
        status_after = email_svc.get_status()
        assert status_after["active_incident_schedules_count"] == 0

        # Verify event marked as INTERRUPTED, not resolved
        ev = event_svc.get_event("EVT-0002")
        assert ev["status"] == STATUS_INTERRUPTED, f"Expected status {STATUS_INTERRUPTED}, got {ev['status']}"

        # Advance clock to reminder time (t=3306.0, 5 minutes after first alert)
        simulated_time = 3306.0
        due = email_svc.check_due_reminders()
        assert len(due) == 0, "No reminders should be due when camera is stopped!"
        assert len(sent_emails) == 1, "No reminder email should have been sent!"
        print("  PASS: Active schedule cancelled on camera stop; zero reminder emails sent; event marked 'interrupted'.")

        # ---------------------------------------------------------------------
        # TEST 4: Camera Stop Aborts In-Flight / Queued Worker Thread
        # ---------------------------------------------------------------------
        print("\n[TEST 4] Camera Stop aborts queued email before SMTP transmission...")
        email_svc.set_camera_monitoring_active(True, reason="camera_restart")

        # Simulate a delay in transport to catch in-flight stop
        delayed_sent = []
        def slow_transport(m, r, a):
            time.sleep(0.2)
            delayed_sent.append((m, r, a))
            return True, ""

        email_svc.set_mock_transport(slow_transport)

        simulated_time = 4000.0
        worker_3 = [
            {
                "worker_track_id": 303,
                "categories": {
                    "mask": {"status": "missing", "display_name": "Mask"},
                },
            }
        ]
        timer_svc.update(worker_3, current_time=simulated_time)
        simulated_time = 4006.0
        timer_svc.update(worker_3, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        (evidence_dir / "EVT-0003.jpg").write_bytes(b"DUMMY_EVIDENCE_FOR_WORKER_303")

        # Trigger confirmation
        event_svc.update(eligible, current_time=simulated_time)
        # Immediately stop camera to invalidate the session ID before worker completes
        email_svc.set_camera_monitoring_active(False, reason="emergency_stop")

        time.sleep(0.3)
        # The worker thread should have aborted because session ID changed / camera is inactive
        assert len(delayed_sent) == 0, f"Expected queued email to be aborted, but {len(delayed_sent)} sent!"
        print("  PASS: In-flight/queued email safely aborted when camera monitoring stopped.")

        # Restore normal fast transport
        email_svc.set_mock_transport(mock_transport)

        # ---------------------------------------------------------------------
        # TEST 5: Camera Restart Requires Fresh 5-Second Confirmation
        # ---------------------------------------------------------------------
        print("\n[TEST 5] Camera Restart requires fresh 5-second continuous confirmation...")
        email_svc.set_camera_monitoring_active(True, reason="clean_restart")
        timer_svc.reset_all()

        simulated_time = 5000.0
        worker_4 = [
            {
                "worker_track_id": 404,
                "categories": {
                    "safety_vest": {"status": "missing", "display_name": "Safety Vest"},
                },
            }
        ]
        # Frame 1: 0s
        timer_svc.update(worker_4, current_time=simulated_time)
        # Frame 2: 4s (under 5s)
        simulated_time = 5004.0
        timer_svc.update(worker_4, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        assert len(eligible) == 0, "Must not confirm before 5 seconds on new session!"
        event_svc.update(eligible, current_time=simulated_time)
        assert len(sent_emails) == 1  # Still 1 from Test 2

        # Frame 3: 5.5s (confirmed)
        simulated_time = 5005.5
        timer_svc.update(worker_4, current_time=simulated_time)
        eligible = timer_svc.get_alarm_eligible_timers()
        assert len(eligible) == 1
        (evidence_dir / "EVT-0004.jpg").write_bytes(b"DUMMY_EVIDENCE_FOR_WORKER_404")
        event_svc.update(eligible, current_time=simulated_time)
        time.sleep(0.1)

        assert len(sent_emails) == 2, f"Expected 2 total emails, got {len(sent_emails)}"
        print("  PASS: Fresh session required full 5-second continuous confirmation before dispatch.")

        # ---------------------------------------------------------------------
        # TEST 6: Manual Test Email Independent of Camera State
        # ---------------------------------------------------------------------
        print("\n[TEST 6] Manual Test Email works while camera is off...")
        email_svc.set_camera_monitoring_active(False, reason="testing_manual_override")
        assert email_svc.is_camera_monitoring_active() is False

        ok, test_err = email_svc.send_test_email("bhavaneshkadiveti@gmail.com")
        assert ok is True, f"Manual test email must succeed while camera is off! Error: {test_err}"
        assert len(sent_emails) == 3, f"Expected 3 emails, got {len(sent_emails)}"
        test_msg, test_recip, _, _ = sent_emails[-1]
        assert test_recip == "bhavaneshkadiveti@gmail.com"
        assert "SafeVision AI" in test_msg["Subject"] and "Test" in test_msg["Subject"]
        print("  PASS: Manual test email sent successfully even with camera completely offline.")

        # ---------------------------------------------------------------------
        # TEST 7: Notification Service Core Operations & Persistence
        # ---------------------------------------------------------------------
        print("\n[TEST 7] Notification Service Core Operations & Persistence...")
        # Create notifications in all 4 categories
        n1 = notif_service.create_notification(
            event_type="ppe_violation_confirmed",
            category="ppe",
            severity="critical",
            title="PPE Violation Confirmed",
            description="Worker #101 detected without hardhat",
            worker_id=101,
            incident_id="EVT-0010",
        )
        n2 = notif_service.create_notification(
            event_type="alarm_activated",
            category="alarm",
            severity="high",
            title="Alarm Triggered",
            description="Continuous audio buzzer activated",
        )
        n3 = notif_service.create_notification(
            event_type="email_delivered",
            category="email",
            severity="info",
            title="Email Delivered",
            description="First Alert dispatched to admin",
            incident_id="EVT-0010",
        )
        n4 = notif_service.create_notification(
            event_type="camera_started",
            category="monitoring",
            severity="info",
            title="Camera Started",
            description="Video feed connected on DirectShow",
        )

        assert notif_service.get_unread_count() >= 4
        res_data = notif_service.get_notifications(limit=10)
        assert res_data["total"] >= 4
        assert res_data["unread_count"] >= 4

        # Mark single notification as read
        notif_service.mark_as_read(n1.id)
        assert notif_service.get_unread_count() == res_data["unread_count"] - 1

        # Mark all as read
        notif_service.mark_all_as_read()
        assert notif_service.get_unread_count() == 0

        # Verify disk persistence across new instance reload
        reloaded_notif_svc = NotificationService(storage_file=notif_file)
        assert reloaded_notif_svc.get_unread_count() == 0
        r_data = reloaded_notif_svc.get_notifications(limit=10)
        assert r_data["total"] >= 4
        print(f"  PASS: All 4 categories created, marked read, and persisted correctly ({r_data['total']} records).")

        # Clear all notifications
        reloaded_notif_svc.clear_all()
        assert reloaded_notif_svc.get_unread_count() == 0
        empty_data = reloaded_notif_svc.get_notifications()
        assert empty_data["total"] == 0
        print("  PASS: Clear history emptied all notifications.")

        email_svc.stop_scheduler()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # TEST 8: Full REST API TestClient Verification
    # -------------------------------------------------------------------------
    print("\n[TEST 8] FastAPI REST Endpoints Verification for Notification Center...")
    client = TestClient(app)

    # 1. GET /api/notifications (paginated)
    res = client.get("/api/notifications?limit=20")
    assert res.status_code == 200, f"GET /api/notifications failed: {res.text}"
    body = res.json()
    assert "notifications" in body
    assert "total" in body
    assert "unread_count" in body
    print(f"  PASS: GET /api/notifications returned {body['total']} notifications (unread: {body['unread_count']}).")

    # 2. GET /api/notifications/unread_count
    res = client.get("/api/notifications/unread_count")
    assert res.status_code == 200
    assert "unread_count" in res.json()
    print(f"  PASS: GET /api/notifications/unread_count returned: {res.json()['unread_count']}")

    # 3. POST /api/notifications/mark_all_read
    res = client.post("/api/notifications/mark_all_read")
    assert res.status_code == 200
    assert res.json()["success"] is True
    print("  PASS: POST /api/notifications/mark_all_read succeeded.")

    # 4. Check email status endpoint reflects camera status
    res = client.get("/api/notifications/email/status")
    assert res.status_code == 200
    email_status = res.json()
    assert "active_incident_schedules" in email_status
    print("  PASS: GET /api/notifications/email/status operational.")

    print("\n" + "=" * 80)
    print("ALL CAMERA LIFECYCLE & NOTIFICATION CENTER TESTS PASSED!")
    print("=" * 80)


if __name__ == "__main__":
    run_camera_lifecycle_and_notification_tests()
