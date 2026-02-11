"""FastAPI entry point for AVAROS Web UI backend."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import APP_VERSION, CORS_ORIGINS, DATABASE_URL, WEB_API_KEY
from dependencies import get_settings_service
from routers.config import router as config_router
from routers.emission_factors import router as emission_factors_router
from routers.intents import router as intents_router
from routers.metrics import router as metrics_router
from routers.production_data import router as production_data_router
from routers.status import router as status_router


logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="AVAROS Web UI", version=APP_VERSION)
FRONTEND_DIST_DIR = Path(__file__).resolve().parent / "frontend" / "dist"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"^http://localhost(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Enforce API-key authentication on ``/api/v1/`` routes.

    ``/health``, ``/docs``, ``/openapi.json``, and SPA static assets
    are excluded — they remain publicly accessible.
    """
    if request.url.path.startswith("/api/v1/"):
        key = request.headers.get("X-API-Key", "")
        if key != WEB_API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
    return await call_next(request)


@app.on_event("startup")
def startup_check() -> None:
    """Validate shared skill imports and DB-backed settings init path."""
    settings_service = get_settings_service()
    settings_service.initialize()
    logger.info(
        "SettingsService import successful: %s (db_url_set=%s)",
        settings_service.__class__.__name__,
        bool(DATABASE_URL),
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness endpoint for local and container health checks."""
    return {"status": "ok", "version": APP_VERSION}


app.include_router(status_router)
app.include_router(config_router)
app.include_router(emission_factors_router)
app.include_router(intents_router)
app.include_router(metrics_router)
app.include_router(production_data_router)


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str) -> FileResponse:
    """Serve built React frontend and support SPA client-side routing."""
    if full_path.startswith(("api/", "health", "docs", "openapi.json", "redoc")):
        raise HTTPException(status_code=404, detail="Not Found")

    if not FRONTEND_INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found")

    requested_path = (FRONTEND_DIST_DIR / full_path).resolve()
    dist_root = FRONTEND_DIST_DIR.resolve()
    if not str(requested_path).startswith(str(dist_root)):
        raise HTTPException(status_code=404, detail="Not Found")

    if requested_path.is_file():
        return FileResponse(requested_path)
    return FileResponse(FRONTEND_INDEX_FILE)
