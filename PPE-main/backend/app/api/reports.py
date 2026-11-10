import io
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_report_service
from app.services.report_service import ReportService

logger = logging.getLogger("ppe_monitoring.api.reports")

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/summary",
    summary="Safety Reports Summary Metrics",
    description="Returns high-level safety statistics, compliance percentages, and violation breakdowns filtered by date range.",
)
async def get_reports_summary(
    period: str = Query("today", description="Period filter: 'today', 'last_7_days', 'last_30_days', 'custom', 'all'"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="Filter by PPE category (e.g., 'hardhat', 'safety_vest')"),
    status: Optional[str] = Query(None, description="Filter by status: 'open', 'ongoing', 'resolved', 'closed'"),
    report_service: ReportService = Depends(get_report_service),
):
    """Retrieves aggregated safety audit metrics based on actual records."""
    try:
        summary = report_service.get_summary_report(
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            status=status,
        )
        return summary
    except Exception as e:
        logger.error(f"Error generating reports summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate reports summary: {str(e)}",
        )


@router.get(
    "/compliance",
    summary="PPE Compliance Analysis Report",
    description="Returns worker-wise and PPE category compliance breakdowns, missing gear frequencies, and audit details.",
)
async def get_compliance_report(
    period: str = Query("today", description="Period filter: 'today', 'last_7_days', 'last_30_days', 'custom', 'all'"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="Filter by PPE category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    report_service: ReportService = Depends(get_report_service),
):
    """Retrieves worker and equipment compliance statistics."""
    try:
        report = report_service.get_compliance_report(
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            status=status,
        )
        return report
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate compliance report: {str(e)}",
        )


@router.get(
    "/incidents",
    summary="Incident Details Report",
    description="Returns list of recorded safety violations with evidence image status, timestamps, and resolution info.",
)
async def get_incidents_report(
    period: str = Query("today", description="Period filter: 'today', 'last_7_days', 'last_30_days', 'custom', 'all'"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="Filter by PPE category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    report_service: ReportService = Depends(get_report_service),
):
    """Retrieves detailed incident logs."""
    try:
        report = report_service.get_incidents_report(
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            status=status,
        )
        return report
    except Exception as e:
        logger.error(f"Error generating incidents report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate incidents report: {str(e)}",
        )


@router.get(
    "/export/pdf",
    summary="Download PDF Report",
    description="Generates and streams an industrial safety report in PDF format with embedded evidence photos.",
)
async def export_pdf_report(
    report_type: str = Query("daily", description="Report type: 'daily', 'compliance', 'incidents'"),
    period: str = Query("today", description="Period filter: 'today', 'last_7_days', 'last_30_days', 'custom', 'all'"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="Filter by PPE category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    report_service: ReportService = Depends(get_report_service),
):
    """Generates and downloads a formatted PDF report."""
    try:
        pdf_bytes = report_service.generate_pdf(
            report_type=report_type,
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            status=status,
        )

        filename = f"SafeVision_{report_type}_report_{period}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        logger.error(f"Error exporting PDF report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export PDF report: {str(e)}",
        )


@router.get(
    "/export/csv",
    summary="Download CSV Report",
    description="Generates and streams structured safety report data in CSV format.",
)
async def export_csv_report(
    report_type: str = Query("daily", description="Report type: 'daily', 'compliance', 'incidents'"),
    period: str = Query("today", description="Period filter: 'today', 'last_7_days', 'last_30_days', 'custom', 'all'"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    category: Optional[str] = Query(None, description="Filter by PPE category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    report_service: ReportService = Depends(get_report_service),
):
    """Generates and downloads a CSV report."""
    try:
        csv_text = report_service.generate_csv(
            report_type=report_type,
            period=period,
            start_date=start_date,
            end_date=end_date,
            category=category,
            status=status,
        )

        filename = f"SafeVision_{report_type}_report_{period}.csv"
        return StreamingResponse(
            io.BytesIO(csv_text.encode("utf-8")),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        logger.error(f"Error exporting CSV report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export CSV report: {str(e)}",
        )

