import os
from pathlib import Path
import sys

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from fastapi.testclient import TestClient
    from main import app
    from app.services.report_service import get_report_service
except ImportError as e:
    print(f"[FATAL] Failed to import report test dependencies: {e}")
    sys.exit(1)


def run_reports_tests():
    print("=" * 70)
    print("  SafeVision AI - Reports & PDF/CSV Export Unit Tests")
    print("=" * 70)

    client = TestClient(app)

    # 1. Summary Report
    print("\n[Test 1] Testing GET /api/reports/summary (default: today)...")
    res = client.get("/api/reports/summary?period=today")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "overall_compliance_percentage" in data
    assert "total_workers_monitored" in data
    assert "total_violations" in data
    assert "violation_category_breakdown" in data
    assert "incident_summary" in data
    print(f"  ✓ Summary OK: {data['total_violations']} violations, {data['overall_compliance_percentage']}% compliance")

    # 2. Date Filtering (last_7_days, last_30_days, custom, all)
    print("\n[Test 2] Testing period filters...")
    for period in ["today", "last_7_days", "last_30_days", "all"]:
        r = client.get(f"/api/reports/summary?period={period}")
        assert r.status_code == 200
        p_data = r.json()
        assert p_data["period"] == period
        print(f"  ✓ Period '{period}' OK: total_violations={p_data['total_violations']}")

    # Custom date filter
    r_custom = client.get("/api/reports/summary?period=custom&start_date=2024-01-01&end_date=2030-01-01")
    assert r_custom.status_code == 200
    assert r_custom.json()["period"] == "custom"
    print("  ✓ Custom date range filter OK")

    # 3. Compliance Report
    print("\n[Test 3] Testing GET /api/reports/compliance...")
    res_comp = client.get("/api/reports/compliance?period=all")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert "category_compliance" in comp_data
    assert len(comp_data["category_compliance"]) == 6
    assert "worker_compliance" in comp_data
    assert "violation_frequency" in comp_data
    print(f"  ✓ Compliance report OK: {len(comp_data['category_compliance'])} categories evaluated")

    # 4. Incidents Report
    print("\n[Test 4] Testing GET /api/reports/incidents...")
    res_inc = client.get("/api/reports/incidents?period=all")
    assert res_inc.status_code == 200
    inc_data = res_inc.json()
    assert "incidents" in inc_data
    assert "total_count" in inc_data
    print(f"  ✓ Incidents report OK: {inc_data['total_count']} incidents returned")

    # 5. PDF Export for all three report types
    print("\n[Test 5] Testing PDF export for 'daily', 'compliance', and 'incidents'...")
    for rtype in ["daily", "compliance", "incidents"]:
        res_pdf = client.get(f"/api/reports/export/pdf?report_type={rtype}&period=all")
        assert res_pdf.status_code == 200, f"PDF export failed for {rtype}: {res_pdf.status_code}"
        assert res_pdf.headers["content-type"] == "application/pdf"
        assert len(res_pdf.content) > 1000, "PDF content is too small"
        assert res_pdf.content[:4] == b"%PDF", "Invalid PDF magic header"
        print(f"  ✓ PDF Export '{rtype}' OK: {len(res_pdf.content)} bytes generated")

    # 6. CSV Export for all three report types
    print("\n[Test 6] Testing CSV export for 'daily', 'compliance', and 'incidents'...")
    for rtype in ["daily", "compliance", "incidents"]:
        res_csv = client.get(f"/api/reports/export/csv?report_type={rtype}&period=all")
        assert res_csv.status_code == 200, f"CSV export failed for {rtype}: {res_csv.status_code}"
        assert "text/csv" in res_csv.headers["content-type"]
        csv_text = res_csv.content.decode("utf-8")
        assert "SafeVision AI" in csv_text
        assert "EXECUTIVE SUMMARY METRICS" in csv_text
        print(f"  ✓ CSV Export '{rtype}' OK: {len(csv_text)} characters generated")

    print("\n" + "=" * 70)
    print("  ALL REPORT ENDPOINTS & EXPORTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 70)


if __name__ == "__main__":
    run_reports_tests()

