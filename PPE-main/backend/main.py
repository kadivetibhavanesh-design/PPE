from contextlib import asynccontextmanager
import logging
from pathlib import Path
import platform
import sys

# Ensure backend directory and project root are always in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ppe_monitoring")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI application lifespan: manages startup and graceful shutdown."""
    # Startup handler: apply persisted settings without opening camera
    try:
        from app.services.settings_service import get_settings_service
        settings_svc = get_settings_service()
        settings_svc.apply_all()
        logger.info("Persisted configuration loaded and applied successfully during startup.")
    except Exception as e:
        logger.warning(f"Could not apply startup settings: {e}")

    yield
    # Graceful shutdown handler
    logger.info("FastAPI application shutting down; cleaning up monitoring resources...")
    try:
        from app.services.monitoring_controller import get_monitoring_controller
        controller = get_monitoring_controller()
        result = controller.shutdown()
        worker_alive = controller._thread is not None and controller._thread.is_alive()
        if not result.get("success") or result.get("status") == "stopping" or worker_alive:
            logger.error(
                f"FastAPI shutdown: monitoring worker shutdown remains pending or worker has not terminated. Result: {result}"
            )
        else:
            logger.info(
                f"FastAPI shutdown: monitoring controller stopped successfully (status: {result.get('status')})."
            )
    except Exception as e:
        logger.error(f"Error cleaning up monitoring controller during FastAPI shutdown: {e}", exc_info=True)


# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API prefix compatibility middleware: transparently handles requests with or without /api
@app.middleware("http")
async def api_prefix_compatibility_middleware(request: Request, call_next):
    """
    Ensures zero 404 errors by transparently routing endpoints whether called with or without /api prefix.
    If a request path starts with a known API domain (e.g., /settings, /models, /monitoring),
    internally routes it to /api/... seamlessly.
    """
    path = request.scope.get("path", "")
    known_api_roots = (
        "/settings",
        "/monitoring",
        "/models",
        "/violations",
        "/alarms",
        "/evidence",
        "/reports",
        "/system",
        "/health",
        "/notifications",
    )
    if not path.startswith("/api/") and any(path == root or path.startswith(root + "/") for root in known_api_roots):
        request.scope["path"] = f"/api{path}"

    response = await call_next(request)
    return response


# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled error processing {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An internal server error occurred.",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )


# Exception handler for HTTP exceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
        },
    )


# Root endpoint
@app.get("/", tags=["General"])
async def root():
    """Root endpoint returning application name and status."""
    return {
        "name": settings.PROJECT_NAME,
        "status": "online",
        "version": settings.VERSION,
    }


# Include modular API router
try:
    from app.api import api_router
    from app.api.websocket import router as ws_router
    from app.api.settings import router as settings_router
    from app.api.notifications import router as notifications_router
except ModuleNotFoundError as err:
    if err.name in ("app", "app.api"):
        from backend.app.api import api_router
        from backend.app.api.websocket import router as ws_router
        from backend.app.api.settings import router as settings_router
        from backend.app.api.notifications import router as notifications_router
    else:
        raise

app.include_router(api_router)
app.include_router(ws_router)
app.include_router(settings_router)
app.include_router(notifications_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

