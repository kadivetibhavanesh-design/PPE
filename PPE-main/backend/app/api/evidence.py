import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps import get_evidence_service
from app.api.schemas import EvidenceItem, EvidenceListResponse
from app.services.evidence_service import EvidenceService

logger = logging.getLogger("ppe_monitoring.api.evidence")

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.get(
    "",
    response_model=EvidenceListResponse,
    summary="List Saved Incident Evidence",
    description="Returns all recorded PPE violation incident evidence metadata with optional filtering.",
)
async def list_evidence(
    worker_track_id: Optional[int] = Query(None, description="Filter by worker track ID"),
    ppe_category: Optional[str] = Query(None, description="Filter by PPE category"),
    status: Optional[str] = Query(None, description="Filter by event status (open, ongoing, resolved, closed)"),
    evidence_service: EvidenceService = Depends(get_evidence_service),
):
    """Lists saved incident evidence records with optional filtering."""
    try:
        all_records = evidence_service.get_all_evidence()

        filtered = all_records
        if worker_track_id is not None:
            filtered = [r for r in filtered if r.get("worker_track_id") == worker_track_id]
        if ppe_category is not None:
            filtered = [r for r in filtered if str(r.get("ppe_category", "")).lower() == ppe_category.lower()]
        if status is not None:
            filtered = [r for r in filtered if str(r.get("status", "")).lower() == status.lower()]

        return {
            "total_count": len(filtered),
            "evidence": filtered,
        }
    except Exception as e:
        logger.error(f"Error listing evidence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to query evidence: {str(e)}")


@router.get(
    "/{event_id}",
    response_model=EvidenceItem,
    summary="Retrieve Evidence Metadata",
    description="Returns metadata details for a specific violation event ID.",
)
async def get_evidence_metadata(
    event_id: str,
    evidence_service: EvidenceService = Depends(get_evidence_service),
):
    """Retrieves metadata for a specific incident evidence record."""
    try:
        record = evidence_service.get_evidence(event_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Evidence for event '{event_id}' not found.")
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving evidence for {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve evidence: {str(e)}")


@router.get(
    "/{event_id}/image",
    summary="View Evidence Image by Event ID",
    description="Returns the saved annotated JPEG camera frame for a specific violation event ID.",
)
async def get_evidence_image(
    event_id: str,
    evidence_service: EvidenceService = Depends(get_evidence_service),
):
    """Returns the evidence JPEG image corresponding to the violation event ID."""
    try:
        record = evidence_service.get_evidence(event_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Evidence event '{event_id}' not found.")

        image_path = evidence_service.get_image_path(event_id)
        if not image_path or not image_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No evidence image available on disk for event '{event_id}'.",
            )

        return FileResponse(
            path=str(image_path),
            media_type="image/jpeg",
            filename=image_path.name,
        )
    except HTTPException:
        raise
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Error retrieving image for event {event_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve evidence image: {str(e)}")


@router.get(
    "/file/{filename:path}",
    summary="Download Evidence Image by Filename",
    description="Validates filename against path traversal and streams the evidence JPEG image.",
)
async def get_evidence_by_filename(
    filename: str,
    evidence_service: EvidenceService = Depends(get_evidence_service),
):
    """Validates filename, prevents path traversal, and returns the requested evidence image."""
    try:
        target_path = evidence_service.validate_filename(filename)
        if not target_path.exists() or not target_path.is_file():
            raise HTTPException(status_code=404, detail=f"Evidence file '{filename}' not found.")

        return FileResponse(
            path=str(target_path),
            media_type="image/jpeg",
            filename=target_path.name,
        )
    except HTTPException:
        raise
    except ValueError as val_err:
        logger.warning(f"Path traversal attempt or invalid filename rejected: {val_err}")
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Error retrieving evidence file {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve evidence file: {str(e)}")
