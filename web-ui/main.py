"""FastAPI entry point for AVAROS Web UI backend."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import APP_VERSION, CORS_ORIGINS, DATABASE_URL, WEB_API_KEY
from dependencies import get_kpi_scheduler, get_settings_service
from routers.assets import router as assets_router
from routers.config import router as config_router
from routers.emission_factors import router as emission_factors_router
from routers.intents import router as intents_router
from routers.intent_bindings import router as intent_bindings_router
from routers.metrics import router as metrics_router
from routers.kpi_progress import router as kpi_progress_router
from routers.production_data import router as production_data_router
from routers.profiles import router as profiles_router
from routers.status import router as status_router
from routers.voice import router as voice_router


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


def _resolve_sqlite_db_path(database_url: str) -> Path | None:
    """Return SQLite filesystem path when DATABASE_URL targets sqlite."""
    if not database_url.startswith("sqlite:///"):
        return None
    raw_path = database_url.removeprefix("sqlite:///")
    if not raw_path:
        return None
    if not raw_path.startswith("/"):
        raw_path = f"/{raw_path}"
    return Path(raw_path)


def _ensure_shared_sqlite_permissions(database_url: str) -> None:
    """Keep shared sqlite file writable by both web-ui and skill containers."""
    db_path = _resolve_sqlite_db_path(database_url)
    if db_path is None:
        return

    db_dir = db_path.parent
    db_dir.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        db_path.touch(exist_ok=True)

    shared_uid = int(os.environ.get("AVAROS_SHARED_DB_UID", "1000"))
    shared_gid = int(os.environ.get("AVAROS_SHARED_DB_GID", "1000"))
    try:
        os.chown(db_dir, shared_uid, shared_gid)
        os.chown(db_path, shared_uid, shared_gid)
    except (PermissionError, OSError) as exc:
        logger.warning("Could not apply shared DB ownership: %s", exc)

    try:
        os.chmod(db_dir, 0o775)
        os.chmod(db_path, 0o664)
    except (PermissionError, OSError) as exc:
        logger.warning("Could not apply shared DB permissions: %s", exc)


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
async def startup_check() -> None:
    """Validate shared skill imports and DB-backed settings init path."""
    _ensure_shared_sqlite_permissions(DATABASE_URL)
    settings_service = get_settings_service()
    settings_service.initialize()
    logger.info(
        "SettingsService import successful: %s (db_url_set=%s)",
        settings_service.__class__.__name__,
        bool(DATABASE_URL),
    )
    scheduler = get_kpi_scheduler()
    try:
        await scheduler.start()
    except Exception as exc:
        logger.warning(
            "KPI scheduler startup skipped: %s",
            exc,
        )


@app.on_event("shutdown")
def shutdown_scheduler() -> None:
    """Stop KPI scheduler background task during app shutdown."""
    scheduler = get_kpi_scheduler()
    scheduler.stop()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness endpoint for local and container health checks."""
    return {"status": "ok", "version": APP_VERSION}


app.include_router(status_router)
app.include_router(assets_router)
app.include_router(config_router)
app.include_router(profiles_router)
app.include_router(emission_factors_router)
app.include_router(intents_router)
app.include_router(intent_bindings_router)
app.include_router(metrics_router)
app.include_router(production_data_router)
app.include_router(kpi_progress_router)
app.include_router(voice_router)


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
