from fastapi import APIRouter

from app.api.system import router as system_router
from app.api.monitoring import router as monitoring_router
from app.api.violations import router as violations_router
from app.api.alarms import router as alarms_router
from app.api.evidence import router as evidence_router
from app.api.models import router as models_router
from app.api.reports import router as reports_router
from app.api.settings import router as settings_router
from app.api.notifications import router as notifications_router

# Consolidated API router mounted under /api
api_router = APIRouter(prefix="/api")

# Include sub-routers
api_router.include_router(system_router)
api_router.include_router(monitoring_router)
api_router.include_router(violations_router)
api_router.include_router(alarms_router)
api_router.include_router(evidence_router)
api_router.include_router(models_router)
api_router.include_router(reports_router)
api_router.include_router(settings_router)
api_router.include_router(notifications_router)
