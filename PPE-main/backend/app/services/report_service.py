import csv
from datetime import datetime, time as dtime, timedelta
import io
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.services.evidence_service import EvidenceService, get_evidence_service
    from app.services.violation_event_service import ViolationEventService
    from app.services.ppe_monitoring_service import PPEMonitoringService, get_monitoring_service
    from app.services.monitoring_controller import MonitoringController, get_monitoring_controller
    from app.services.model_registry import get_active_model_id, get_model_profile
except ImportError:
    from services.evidence_service import EvidenceService, get_evidence_service
    from services.violation_event_service import ViolationEventService
    from services.ppe_monitoring_service import PPEMonitoringService, get_monitoring_service
    from services.monitoring_controller import MonitoringController, get_monitoring_controller
    from services.model_registry import get_active_model_id, get_model_profile

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logger = logging.getLogger("ppe_monitoring.report_service")

MANDATORY_CATEGORIES = [
    "hardhat",
    "safety_vest",
    "gloves",
    "goggles",
    "mask",
    "safety_shoes",
]

CATEGORY_LABELS = {
    "hardhat": "Hardhat",
    "safety_vest": "Safety Vest",
    "gloves": "Safety Gloves",
    "goggles": "Eye Protection (Goggles)",
    "mask": "Protective Mask",
    "safety_shoes": "Safety Footwear",
}


class ReportService:
    """
    Consolidated reporting service for SafeVision AI.
    Aggregates data from local evidence storage, violation events, ByteTrack tracking,
    and monitoring controller to produce dashboard metrics, PDF, and CSV reports.
    """

    def __init__(
        self,
        evidence_service: Optional[EvidenceService] = None,
        monitoring_service: Optional[PPEMonitoringService] = None,
        monitoring_controller: Optional[MonitoringController] = None,
    ) -> None:
        self.evidence_service = evidence_service or get_evidence_service()
        self.monitoring_service = monitoring_service or get_monitoring_service()
        self.monitoring_controller = monitoring_controller or get_monitoring_controller()

    def _resolve_time_range(
        self,
        period: str = "today",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Tuple[float, float, str, str]:
        """
        Calculates start and end epoch timestamps for a given period or custom date range.
        Returns (start_ts, end_ts, formatted_start_str, formatted_end_str).
        """
        now = datetime.now()
        period_lower = (period or "today").lower().strip()

        if period_lower == "today":
            start_dt = datetime.combine(now.date(), dtime.min)
            end_dt = datetime.combine(now.date(), dtime.max)
        elif period_lower == "yesterday":
            yest_date = (now - timedelta(days=1)).date()
            start_dt = datetime.combine(yest_date, dtime.min)
            end_dt = datetime.combine(yest_date, dtime.max)
        elif period_lower == "last_7_days":
            start_dt = now - timedelta(days=7)
            end_dt = now
        elif period_lower == "last_30_days":
            start_dt = now - timedelta(days=30)
            end_dt = now
        elif period_lower == "custom" and start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                start_dt = now - timedelta(days=1)

            if end_date:
                try:
                    end_dt = datetime.combine(
                        datetime.strptime(end_date, "%Y-%m-%d").date(), dtime.max
                    )
                except ValueError:
                    end_dt = now
            else:
                end_dt = now
        else:  # "all" or fallback
            start_dt = datetime(2020, 1, 1)
            end_dt = now + timedelta(days=1)

        start_ts = start_dt.timestamp()
        end_ts = end_dt.timestamp()
        return start_ts, end_ts, start_dt.strftime("%Y-%m-%d %H:%M"), end_dt.strftime("%Y-%m-%d %H:%M")

    def get_unified_events(
        self,
        period: str = "today",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Merges persisted evidence records and active session violation events,
        filters by time range and optional category/status, and returns sorted events.
        """
        start_ts, end_ts, _, _ = self._resolve_time_range(period, start_date, end_date)

        # 1. Fetch persisted evidence records
        persisted_records = self.evidence_service.get_all_evidence()

        # 2. Fetch session violation events
        session_events: List[Dict[str, Any]] = []
        if (
            hasattr(self.monitoring_service, "violation_event_service")
            and self.monitoring_service.violation_event_service
        ):
            session_events = self.monitoring_service.violation_event_service.get_all_events()

        # 3. Merge by event_id (session events take precedence for latest active duration)
        events_by_id: Dict[str, Dict[str, Any]] = {}

        for rec in persisted_records:
            eid = str(rec.get("event_id"))
            events_by_id[eid] = {
                "event_id": eid,
                "worker_track_id": int(rec.get("worker_track_id", 0)),
                "ppe_category": str(rec.get("ppe_category", "unknown")).lower(),
                "severity": str(rec.get("severity", "high")).lower(),
                "status": str(rec.get("status") or rec.get("event_status") or "open").lower(),
                "start_timestamp": float(
                    rec.get("first_detected_timestamp") or rec.get("start_timestamp") or time.time()
                ),
                "last_updated_timestamp": float(rec.get("last_updated_timestamp") or time.time()),
                "resolution_timestamp": rec.get("resolution_timestamp"),
                "duration_seconds": float(rec.get("violation_duration", 0.0)),
                "evidence_image_filename": rec.get("evidence_image_filename") or rec.get("image_filename"),
                "has_evidence_image": bool(rec.get("evidence_image_filename") or rec.get("image_filename")),
            }

        for ev in session_events:
            eid = str(ev.get("event_id"))
            start_time = float(ev.get("start_timestamp") or time.time())
            dur = float(ev.get("violation_duration", 0.0))

            if eid in events_by_id:
                # Update with latest session metrics
                events_by_id[eid]["status"] = str(ev.get("status", events_by_id[eid]["status"])).lower()
                events_by_id[eid]["duration_seconds"] = dur
                events_by_id[eid]["last_updated_timestamp"] = float(ev.get("last_updated_timestamp") or time.time())
                events_by_id[eid]["resolution_timestamp"] = ev.get("resolution_timestamp") or events_by_id[eid].get("resolution_timestamp")
            else:
                events_by_id[eid] = {
                    "event_id": eid,
                    "worker_track_id": int(ev.get("worker_track_id", 0)),
                    "ppe_category": str(ev.get("ppe_category", "unknown")).lower(),
                    "severity": str(ev.get("severity", "high")).lower(),
                    "status": str(ev.get("status", "open")).lower(),
                    "start_timestamp": start_time,
                    "last_updated_timestamp": float(ev.get("last_updated_timestamp") or time.time()),
                    "resolution_timestamp": ev.get("resolution_timestamp"),
                    "duration_seconds": dur,
                    "evidence_image_filename": None,
                    "has_evidence_image": False,
                }

        # 4. Filter by date range, category, status
        filtered: List[Dict[str, Any]] = []
        for e in events_by_id.values():
            ts = e["start_timestamp"]
            if not (start_ts <= ts <= end_ts):
                continue
            if category and category.lower() != "all" and e["ppe_category"] != category.lower():
                continue
            if status and status.lower() != "all":
                req_status = status.lower()
                if req_status in ("open", "ongoing", "active") and e["status"] not in ("open", "ongoing"):
                    continue
                elif req_status in ("resolved", "closed") and e["status"] not in ("resolved", "closed"):
                    continue
                elif req_status not in ("open", "ongoing", "active", "resolved", "closed") and e["status"] != req_status:
                    continue

            # Check if actual image file exists on disk
            if e.get("has_evidence_image") and self.evidence_service:
                img_path = self.evidence_service.get_image_path(e["event_id"])
                e["image_path"] = str(img_path) if img_path else None
                e["has_evidence_image"] = img_path is not None and img_path.exists()
            else:
                e["image_path"] = None

            filtered.append(e)

        filtered.sort(key=lambda x: x["start_timestamp"], reverse=True)
        return filtered

    def get_summary_report(
        self,
        period: str = "today",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Computes consolidated metrics for the Reports Dashboard.
        """
        start_ts, end_ts, start_str, end_str = self._resolve_time_range(period, start_date, end_date)
        events = self.get_unified_events(period, start_date, end_date, category, status)

        # Violation counters
        total_violations = len(events)
        active_violations = 0
        resolved_violations = 0
        critical_violations = 0
        high_violations = 0
        medium_violations = 0
        with_image_count = 0

        cat_breakdown = {cat: 0 for cat in MANDATORY_CATEGORIES}

        unique_workers_in_events = set()

        for ev in events:
            st = ev["status"]
            sev = ev["severity"]
            cat = ev["ppe_category"]

            unique_workers_in_events.add(ev["worker_track_id"])

            if st in ("open", "ongoing"):
                active_violations += 1
            elif st in ("resolved", "closed"):
                resolved_violations += 1

            if sev == "critical":
                critical_violations += 1
            elif sev == "high":
                high_violations += 1
            elif sev == "medium":
                medium_violations += 1

            if cat in cat_breakdown:
                cat_breakdown[cat] += 1
            else:
                cat_breakdown[cat] = cat_breakdown.get(cat, 0) + 1

            if ev.get("has_evidence_image"):
                with_image_count += 1

        # Current session worker tracking metrics
        ctrl_status = self.monitoring_controller.get_status()
        is_running = ctrl_status.get("is_running", False)
        uptime = ctrl_status.get("uptime_seconds", 0.0)

        # Uptime formatted
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        uptime_formatted = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

        session_snap = self.monitoring_service.get_latest_monitoring_data()
        active_workers = session_snap.get("workers", [])
        total_tracked_count = session_snap.get("worker_lifecycle", {}).get(
            "total_tracked_count", len(active_workers)
        )

        total_workers = max(total_tracked_count, len(active_workers), len(unique_workers_in_events))
        compliant_workers = session_snap.get("total_compliant", 0)
        non_compliant_workers = session_snap.get("total_non_compliant", 0)
        review_workers = session_snap.get("total_needs_review", 0)

        # Overall compliance rate
        if total_workers > 0:
            overall_comp_pct = round((compliant_workers / total_workers) * 100, 1)
        elif total_violations == 0:
            overall_comp_pct = 100.0
        else:
            overall_comp_pct = 0.0

        resolved_rate = round((resolved_violations / total_violations * 100), 1) if total_violations > 0 else 100.0

        active_model_id = ctrl_status.get("active_model_id", "constructelligence")
        active_model_name = {
            "constructelligence": "Detection Profile A",
            "vyra": "Detection Profile B",
        }.get(active_model_id, "Detection Profile")

        return {
            "period": period,
            "start_time": start_str,
            "end_time": end_str,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "monitoring_duration_seconds": round(uptime, 1),
            "monitoring_uptime_formatted": uptime_formatted,
            "is_monitoring_active": is_running,
            "active_model_id": active_model_id,
            "active_model_name": active_model_name,
            "total_workers_monitored": total_workers,
            "compliant_workers": compliant_workers,
            "non_compliant_workers": non_compliant_workers,
            "review_workers": review_workers,
            "overall_compliance_percentage": overall_comp_pct,
            "total_violations": total_violations,
            "active_violations": active_violations,
            "resolved_violations": resolved_violations,
            "critical_violations": critical_violations,
            "high_violations": high_violations,
            "medium_violations": medium_violations,
            "violation_category_breakdown": cat_breakdown,
            "incident_summary": {
                "total_incidents": total_violations,
                "with_evidence_image": with_image_count,
                "resolved_count": resolved_violations,
                "active_count": active_violations,
                "resolution_rate_percentage": resolved_rate,
            },
        }

    def get_compliance_report(
        self,
        period: str = "today",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates worker-wise and category-wise PPE compliance analysis.
        """
        summary = self.get_summary_report(period, start_date, end_date, category, status)
        events = self.get_unified_events(period, start_date, end_date, category, status)

        # Worker-wise aggregation
        workers_map: Dict[int, Dict[str, Any]] = {}
        session_snap = self.monitoring_service.get_latest_monitoring_data()
        active_workers = session_snap.get("workers", [])

        # Seed from active workers in frame
        for w in active_workers:
            wid = int(w.get("worker_track_id", 0))
            comp_status = str(w.get("overall_status") or w.get("compliance_status") or "needs_review")
            missing = [m.replace("NO ", "") for m in w.get("missing_ppe_labels", [])]
            workers_map[wid] = {
                "worker_id": wid,
                "status": "In View (Active)",
                "compliance_status": comp_status.capitalize().replace("_", " "),
                "missing_categories": missing,
                "violations_count": 0,
                "last_seen": "Current Live Session",
            }

        # Add / update violation statistics from events
        for ev in events:
            wid = ev["worker_track_id"]
            cat = ev["ppe_category"]
            dt_str = datetime.fromtimestamp(ev["start_timestamp"]).strftime("%Y-%m-%d %H:%M:%S")

            if wid not in workers_map:
                workers_map[wid] = {
                    "worker_id": wid,
                    "status": "Logged in Incident History",
                    "compliance_status": "Non-Compliant" if ev["status"] in ("open", "ongoing") else "Resolved",
                    "missing_categories": [cat],
                    "violations_count": 1,
                    "last_seen": dt_str,
                }
            else:
                workers_map[wid]["violations_count"] += 1
                if cat not in workers_map[wid]["missing_categories"]:
                    workers_map[wid]["missing_categories"].append(cat)

        workers_list = sorted(workers_map.values(), key=lambda x: x["worker_id"])

        # Category compliance summary
        total_monitored = max(summary["total_workers_monitored"], 1)
        category_summaries = []
        for cat_key in MANDATORY_CATEGORIES:
            label = CATEGORY_LABELS.get(cat_key, cat_key.capitalize())
            v_count = summary["violation_category_breakdown"].get(cat_key, 0)
            comp_count = max(0, total_monitored - v_count)
            rate = round((comp_count / total_monitored) * 100, 1)

            category_summaries.append({
                "category": label,
                "key": cat_key,
                "total_monitored": total_monitored,
                "compliant_count": comp_count,
                "violation_count": v_count,
                "compliance_rate": rate,
            })

        # Violation frequency list
        total_viols = max(summary["total_violations"], 1)
        frequency = []
        for cat_key, cnt in sorted(
            summary["violation_category_breakdown"].items(), key=lambda item: item[1], reverse=True
        ):
            frequency.append({
                "category": CATEGORY_LABELS.get(cat_key, cat_key.capitalize()),
                "key": cat_key,
                "count": cnt,
                "percentage": round((cnt / total_viols) * 100, 1) if summary["total_violations"] > 0 else 0.0,
            })

        return {
            "summary": summary,
            "overall_compliance_percentage": summary["overall_compliance_percentage"],
            "category_compliance": category_summaries,
            "worker_compliance": workers_list,
            "violation_frequency": frequency,
            "historical_limitation_note": (
                "Historical worker records reflect captured violation events and current session tracking. "
                "Real-time ByteTrack tracking is maintained during active surveillance camera sessions."
            ),
        }

    def get_incidents_report(
        self,
        period: str = "today",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns structured incident records for the Incident Report.
        """
        summary = self.get_summary_report(period, start_date, end_date, category, status)
        events = self.get_unified_events(period, start_date, end_date, category, status)

        incidents = []
        for ev in events:
            dt_str = datetime.fromtimestamp(ev["start_timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            res_str = None
            if ev.get("resolution_timestamp"):
                res_str = datetime.fromtimestamp(ev["resolution_timestamp"]).strftime("%Y-%m-%d %H:%M:%S")

            cat_label = CATEGORY_LABELS.get(ev["ppe_category"], ev["ppe_category"].capitalize())

            incidents.append({
                "incident_id": ev["event_id"],
                "timestamp": ev["start_timestamp"],
                "datetime": dt_str,
                "worker_id": ev["worker_track_id"],
                "violation_type": cat_label,
                "category_key": ev["ppe_category"],
                "severity": ev["severity"].capitalize(),
                "status": ev["status"].capitalize(),
                "duration_seconds": round(ev["duration_seconds"], 1),
                "evidence_image_available": ev["has_evidence_image"],
                "evidence_image_url": f"/api/evidence/{ev['event_id']}/image" if ev["has_evidence_image"] else None,
                "image_path": ev.get("image_path"),
                "resolution_datetime": res_str,
            })

        return {
            "summary": summary,
            "total_count": len(incidents),
            "incidents": incidents,
        }

    def generate_pdf(
        self,
        report_type: str = "daily",
        period: str = "today",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bytes:
        """
        Builds a comprehensive industrial safety PDF report with embedded evidence photos.
        """
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom paragraph styles
        header_title_style = ParagraphStyle(
            "HeaderTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            fontName="Helvetica-Bold",
        )
        header_sub_style = ParagraphStyle(
            "HeaderSub",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            fontName="Helvetica",
        )
        section_heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica-Bold",
            spaceBefore=12,
            spaceAfter=6,
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0f172a"),
            fontName="Helvetica-Bold",
        )
        cell_normal = ParagraphStyle(
            "CellNormal",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
            fontName="Helvetica",
        )
        cell_header = ParagraphStyle(
            "CellHeader",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.white,
            fontName="Helvetica-Bold",
        )

        story = []

        # 1. Title Banner
        report_names = {
            "daily": "Daily Industrial Safety & PPE Monitoring Report",
            "compliance": "PPE Compliance & Worker Safety Audit Report",
            "incidents": "Industrial Incident & Evidence Log Report",
        }
        title_text = report_names.get(report_type.lower(), "SafeVision AI - Safety Audit Report")

        story.append(Paragraph("SAFEVISION AI · INDUSTRIAL MONITORING SYSTEM", ParagraphStyle("Brand", fontSize=9, fontName="Helvetica-Bold", textColor=colors.HexColor("#2563eb"))))
        story.append(Spacer(1, 3))
        story.append(Paragraph(title_text, header_title_style))
        story.append(Spacer(1, 4))

        summary = self.get_summary_report(period, start_date, end_date, category, status)

        filter_desc = f"Time Range: {summary['start_time']} to {summary['end_time']} ({summary['period'].replace('_', ' ').title()})"
        meta_info = f"Generated: {summary['generated_at']} | Model: {summary['active_model_name']} | Surveillance: Zone A"
        story.append(Paragraph(filter_desc, header_sub_style))
        story.append(Paragraph(meta_info, header_sub_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1"), spaceAfter=12))

        # 2. Executive KPI Summary Table
        kpi_data = [
            [
                Paragraph("Total Workers Monitored", cell_bold),
                Paragraph(str(summary["total_workers_monitored"]), cell_normal),
                Paragraph("Overall PPE Compliance", cell_bold),
                Paragraph(f"{summary['overall_compliance_percentage']}%", cell_bold),
            ],
            [
                Paragraph("Compliant Workers", cell_bold),
                Paragraph(str(summary["compliant_workers"]), cell_normal),
                Paragraph("Non-Compliant Workers", cell_bold),
                Paragraph(str(summary["non_compliant_workers"]), cell_normal),
            ],
            [
                Paragraph("Total Safety Violations", cell_bold),
                Paragraph(str(summary["total_violations"]), cell_normal),
                Paragraph("Active Safety Hazards", cell_bold),
                Paragraph(str(summary["active_violations"]), cell_normal),
            ],
            [
                Paragraph("Resolved Violations", cell_bold),
                Paragraph(str(summary["resolved_violations"]), cell_normal),
                Paragraph("Critical Violations (Hardhat)", cell_bold),
                Paragraph(str(summary["critical_violations"]), cell_normal),
            ],
            [
                Paragraph("Surveillance Uptime", cell_bold),
                Paragraph(summary["monitoring_uptime_formatted"], cell_normal),
                Paragraph("Evidence Frames Captured", cell_bold),
                Paragraph(str(summary["incident_summary"]["with_evidence_image"]), cell_normal),
            ],
        ]

        t_kpi = Table(kpi_data, colWidths=[150, 110, 150, 110])
        t_kpi.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_kpi)
        story.append(Spacer(1, 14))

        # 3. Report-Specific Details
        if report_type.lower() == "daily":
            # PPE Category Breakdown Table
            story.append(Paragraph("PPE Category Violation Distribution", section_heading_style))
            cat_rows = [
                [
                    Paragraph("Mandatory Equipment Standard", cell_header),
                    Paragraph("Violations Count", cell_header),
                    Paragraph("Risk Severity", cell_header),
                    Paragraph("Category Compliance Rate", cell_header),
                ]
            ]

            total_m = max(summary["total_workers_monitored"], 1)
            for c_key in MANDATORY_CATEGORIES:
                label = CATEGORY_LABELS.get(c_key, c_key.capitalize())
                v_cnt = summary["violation_category_breakdown"].get(c_key, 0)
                sev = "Critical" if c_key == "hardhat" else "High" if c_key in ("safety_vest", "safety_shoes") else "Medium"
                rate = max(0.0, round(((total_m - v_cnt) / total_m) * 100, 1))

                cat_rows.append([
                    Paragraph(label, cell_bold),
                    Paragraph(str(v_cnt), cell_normal),
                    Paragraph(sev, cell_normal),
                    Paragraph(f"{rate}%", cell_bold),
                ])

            t_cat = Table(cat_rows, colWidths=[180, 100, 110, 130])
            t_cat.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_cat)
            story.append(Spacer(1, 14))

            # Recent Incidents Table
            story.append(Paragraph("Recorded Safety Incidents (Recent Session Log)", section_heading_style))
            inc_data = self.get_incidents_report(period, start_date, end_date, category, status)
            inc_list = inc_data["incidents"][:12]

            if not inc_list:
                story.append(Paragraph("No safety violation incidents recorded within the selected period.", cell_normal))
            else:
                inc_rows = [
                    [
                        Paragraph("Event ID", cell_header),
                        Paragraph("Worker", cell_header),
                        Paragraph("Violation Type", cell_header),
                        Paragraph("Severity", cell_header),
                        Paragraph("Timestamp", cell_header),
                        Paragraph("Status", cell_header),
                    ]
                ]
                for inc in inc_list:
                    inc_rows.append([
                        Paragraph(inc["incident_id"], cell_bold),
                        Paragraph(f"Worker #{inc['worker_id']}", cell_normal),
                        Paragraph(inc["violation_type"], cell_normal),
                        Paragraph(inc["severity"], cell_normal),
                        Paragraph(inc["datetime"], cell_normal),
                        Paragraph(inc["status"], cell_bold),
                    ])

                t_inc = Table(inc_rows, colWidths=[90, 70, 130, 70, 100, 60])
                t_inc.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(t_inc)

        elif report_type.lower() == "compliance":
            comp_data = self.get_compliance_report(period, start_date, end_date, category, status)

            # Category Standards Compliance Table
            story.append(Paragraph("PPE Category Compliance Standards", section_heading_style))
            cat_rows = [
                [
                    Paragraph("PPE Standard", cell_header),
                    Paragraph("Monitored Count", cell_header),
                    Paragraph("Compliant Count", cell_header),
                    Paragraph("Violation Count", cell_header),
                    Paragraph("Compliance %", cell_header),
                ]
            ]
            for cat_item in comp_data["category_compliance"]:
                cat_rows.append([
                    Paragraph(cat_item["category"], cell_bold),
                    Paragraph(str(cat_item["total_monitored"]), cell_normal),
                    Paragraph(str(cat_item["compliant_count"]), cell_normal),
                    Paragraph(str(cat_item["violation_count"]), cell_normal),
                    Paragraph(f"{cat_item['compliance_rate']}%", cell_bold),
                ])

            t_comp = Table(cat_rows, colWidths=[160, 85, 90, 90, 95])
            t_comp.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_comp)
            story.append(Spacer(1, 14))

            # Worker Compliance Breakdown
            story.append(Paragraph("Worker-Wise PPE Compliance Matrix", section_heading_style))
            workers_list = comp_data["worker_compliance"]
            if not workers_list:
                story.append(Paragraph("No active workers evaluated yet in current surveillance session.", cell_normal))
            else:
                w_rows = [
                    [
                        Paragraph("Worker ID", cell_header),
                        Paragraph("Surveillance Status", cell_header),
                        Paragraph("Compliance State", cell_header),
                        Paragraph("Total Violations", cell_header),
                        Paragraph("Missing Gear Categories", cell_header),
                    ]
                ]
                for w in workers_list:
                    missing_str = ", ".join(w["missing_categories"]) if w["missing_categories"] else "None (Fully Compliant)"
                    w_rows.append([
                        Paragraph(f"Worker #{w['worker_id']}", cell_bold),
                        Paragraph(w["status"], cell_normal),
                        Paragraph(w["compliance_status"], cell_bold),
                        Paragraph(str(w["violations_count"]), cell_normal),
                        Paragraph(missing_str, cell_normal),
                    ])

                t_w = Table(w_rows, colWidths=[75, 120, 100, 75, 150])
                t_w.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(t_w)

        elif report_type.lower() == "incidents":
            inc_data = self.get_incidents_report(period, start_date, end_date, category, status)
            inc_list = inc_data["incidents"]

            story.append(Paragraph(f"Detailed Incident Log & Photo Evidence ({len(inc_list)} Incidents)", section_heading_style))

            if not inc_list:
                story.append(Paragraph("No safety incident records match the criteria.", cell_normal))
            else:
                for idx, inc in enumerate(inc_list[:25], 1):
                    # Incident entry box with embedded evidence image if available
                    incident_info = [
                        [
                            Paragraph(f"<b>Incident:</b> {inc['incident_id']}", cell_normal),
                            Paragraph(f"<b>Worker:</b> Worker #{inc['worker_id']}", cell_normal),
                            Paragraph(f"<b>Violation:</b> {inc['violation_type']}", cell_normal),
                        ],
                        [
                            Paragraph(f"<b>Severity:</b> {inc['severity']}", cell_normal),
                            Paragraph(f"<b>Status:</b> {inc['status']}", cell_normal),
                            Paragraph(f"<b>Detected:</b> {inc['datetime']}", cell_normal),
                        ],
                    ]

                    # If resolution exists
                    if inc.get("resolution_datetime"):
                        incident_info.append([
                            Paragraph(f"<b>Resolved At:</b> {inc['resolution_datetime']}", cell_normal),
                            Paragraph(f"<b>Duration:</b> {inc['duration_seconds']}s", cell_normal),
                            Paragraph("", cell_normal),
                        ])

                    t_inc_meta = Table(incident_info, colWidths=[170, 170, 180])
                    t_inc_meta.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))

                    entry_elements = [t_inc_meta]

                    # Embed Photo Evidence Image if available on disk
                    if inc.get("image_path") and Path(inc["image_path"]).exists():
                        try:
                            # Width: 280, Height: 160
                            rl_img = RLImage(inc["image_path"], width=280, height=157)
                            entry_elements.append(Spacer(1, 4))
                            entry_elements.append(Paragraph("<b>Captured Camera Evidence Snapshot:</b>", cell_normal))
                            entry_elements.append(Spacer(1, 2))
                            entry_elements.append(rl_img)
                        except Exception as img_err:
                            logger.warning(f"Failed to embed image in PDF for {inc['incident_id']}: {img_err}")
                            entry_elements.append(Paragraph("[Evidence Image Format Error]", cell_normal))

                    entry_elements.append(Spacer(1, 10))
                    story.append(KeepTogether(entry_elements))

        # 4. Footer Note
        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=6))
        story.append(Paragraph(
            "SafeVision AI Automated Safety Audit Report · Generated by Computer Vision Industrial Safety Monitoring Pipeline.",
            ParagraphStyle("FooterNote", fontSize=8, fontName="Helvetica-Oblique", textColor=colors.HexColor("#64748b"), alignment=1),
        ))

        doc.build(story)
        return buf.getvalue()

    def generate_csv(
        self,
        report_type: str = "daily",
        period: str = "today",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> str:
        """
        Generates CSV report output based on the requested report type and filters.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        summary = self.get_summary_report(period, start_date, end_date, category, status)

        # Header Metadata
        writer.writerow(["SafeVision AI - Industrial Safety & PPE Compliance Report"])
        writer.writerow(["Report Type", report_type.upper()])
        writer.writerow(["Time Range", f"{summary['start_time']} to {summary['end_time']} ({period})"])
        writer.writerow(["Generated At", summary["generated_at"]])
        writer.writerow(["Active Model", summary["active_model_name"]])
        writer.writerow([])

        # Summary Metrics
        writer.writerow(["--- EXECUTIVE SUMMARY METRICS ---"])
        writer.writerow(["Total Workers Monitored", summary["total_workers_monitored"]])
        writer.writerow(["Compliant Workers", summary["compliant_workers"]])
        writer.writerow(["Non-Compliant Workers", summary["non_compliant_workers"]])
        writer.writerow(["Overall Compliance Percentage", f"{summary['overall_compliance_percentage']}%"])
        writer.writerow(["Total Safety Violations", summary["total_violations"]])
        writer.writerow(["Active Violations", summary["active_violations"]])
        writer.writerow(["Resolved Violations", summary["resolved_violations"]])
        writer.writerow(["Critical Severity Violations", summary["critical_violations"]])
        writer.writerow(["High Severity Violations", summary["high_violations"]])
        writer.writerow(["Medium Severity Violations", summary["medium_violations"]])
        writer.writerow(["Monitoring Duration", summary["monitoring_uptime_formatted"]])
        writer.writerow([])

        if report_type.lower() == "compliance":
            comp_data = self.get_compliance_report(period, start_date, end_date, category, status)
            writer.writerow(["--- PPE CATEGORY COMPLIANCE STANDARDS ---"])
            writer.writerow(["Category", "Total Monitored", "Compliant Count", "Violation Count", "Compliance Rate (%)"])
            for c in comp_data["category_compliance"]:
                writer.writerow([c["category"], c["total_monitored"], c["compliant_count"], c["violation_count"], f"{c['compliance_rate']}%"])
            writer.writerow([])

            writer.writerow(["--- WORKER-WISE COMPLIANCE ---"])
            writer.writerow(["Worker ID", "Surveillance Status", "Compliance State", "Total Violations", "Missing Gear"])
            for w in comp_data["worker_compliance"]:
                writer.writerow([
                    f"Worker #{w['worker_id']}",
                    w["status"],
                    w["compliance_status"],
                    w["violations_count"],
                    "; ".join(w["missing_categories"]) if w["missing_categories"] else "None",
                ])

        else:
            # Daily or Incidents: Tabular incidents list
            inc_data = self.get_incidents_report(period, start_date, end_date, category, status)
            writer.writerow(["--- SAFETY INCIDENTS AUDIT LOG ---"])
            writer.writerow([
                "Incident ID",
                "Worker ID",
                "Violation Type",
                "Severity",
                "Status",
                "Detected Timestamp",
                "Resolution Timestamp",
                "Duration (seconds)",
                "Evidence Image Available",
            ])
            for inc in inc_data["incidents"]:
                writer.writerow([
                    inc["incident_id"],
                    f"Worker #{inc['worker_id']}",
                    inc["violation_type"],
                    inc["severity"],
                    inc["status"],
                    inc["datetime"],
                    inc["resolution_datetime"] or "Pending",
                    inc["duration_seconds"],
                    "Yes" if inc["evidence_image_available"] else "No",
                ])

        return output.getvalue()


# Module-level singleton
_report_service_instance: Optional[ReportService] = None


def get_report_service() -> ReportService:
    """Returns the shared ReportService singleton."""
    global _report_service_instance
    if _report_service_instance is None:
        _report_service_instance = ReportService()
    return _report_service_instance

