"""
Mock RENERYO HTTP Server

A lightweight FastAPI application serving all 19 KPI endpoints from
ReneryoAdapter._ENDPOINT_MAP with realistic manufacturing JSON data.

This is a **development tool** — it enables testing the full RENERYO
HTTP client pipeline without real API credentials.

Usage:
    cd tools/reneryo-mock
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8090

The server does NOT import anything from skill/ — it is fully standalone.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from data import (
    DEFAULT_ASSETS,
    METRIC_CONFIG,
    generate_comparison_data,
    generate_native_measurement,
    generate_single_value,
    generate_trend_data,
)


# =========================================================================
# App & Middleware
# =========================================================================

app = FastAPI(
    title="Mock RENERYO Server",
    description="Development mock for RENERYO manufacturing API endpoints",
    version="0.1.0",
)


# =========================================================================
# Auth Dependency
# =========================================================================

def _verify_auth(
    authorization: Annotated[str | None, Header()] = None,
    cookie: Annotated[str | None, Header()] = None,
) -> str:
    """
    Accept any non-empty Cookie: S=... or Authorization: Bearer ... header.

    We're testing the HTTP pipeline, not real auth. Returns a label
    indicating which auth method was used.

    Raises:
        HTTPException: 401 if neither credential is present.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token:
            return "bearer"
    if cookie:
        # Accept any cookie that contains "S=" or is non-empty
        if "S=" in cookie or cookie.strip():
            return "cookie"
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Cookie: S=... or Authorization: Bearer ...",
    )


# =========================================================================
# Optional delay middleware
# =========================================================================

@app.middleware("http")
async def delay_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Add artificial latency when ?delay_ms=N is provided."""
    delay = request.query_params.get("delay_ms")
    if delay:
        try:
            ms = int(delay)
            if 0 < ms <= 10000:
                await asyncio.sleep(ms / 1000.0)
        except (ValueError, TypeError):
            pass
    return await call_next(request)


# =========================================================================
# Health endpoint (no auth required)
# =========================================================================

@app.get("/health")
async def health() -> dict:
    """Health check — returns status and endpoint count."""
    return {
        "status": "ok",
        "service": "reneryo-mock",
        "endpoints": len(METRIC_CONFIG),
    }


# =========================================================================
# Endpoint path → metric name mapping
# Exactly mirrors ReneryoAdapter._ENDPOINT_MAP
# =========================================================================

_PATH_TO_METRIC: dict[str, str] = {
    "/api/v1/kpis/energy/per-unit": "energy_per_unit",
    "/api/v1/kpis/energy/total": "energy_total",
    "/api/v1/kpis/energy/peak-demand": "peak_demand",
    "/api/v1/kpis/energy/tariff-exposure": "peak_tariff_exposure",
    "/api/v1/kpis/material/scrap-rate": "scrap_rate",
    "/api/v1/kpis/material/rework-rate": "rework_rate",
    "/api/v1/kpis/material/efficiency": "material_efficiency",
    "/api/v1/kpis/material/recycled-content": "recycled_content",
    "/api/v1/kpis/supplier/lead-time": "supplier_lead_time",
    "/api/v1/kpis/supplier/defect-rate": "supplier_defect_rate",
    "/api/v1/kpis/supplier/on-time": "supplier_on_time",
    "/api/v1/kpis/supplier/co2-per-kg": "supplier_co2_per_kg",
    "/api/v1/kpis/production/oee": "oee",
    "/api/v1/kpis/production/throughput": "throughput",
    "/api/v1/kpis/production/cycle-time": "cycle_time",
    "/api/v1/kpis/production/changeover-time": "changeover_time",
    "/api/v1/kpis/carbon/per-unit": "co2_per_unit",
    "/api/v1/kpis/carbon/total": "co2_total",
    "/api/v1/kpis/carbon/per-batch": "co2_per_batch",
}

# Trend endpoints (subset that support granularity)
_TREND_METRICS: set[str] = {
    "energy_per_unit",
    "energy_total",
    "peak_demand",
    "scrap_rate",
    "rework_rate",
    "oee",
    "throughput",
    "co2_per_unit",
    "co2_total",
}


# =========================================================================
# Canonical KPI endpoints (/api/v1/kpis/...)
# =========================================================================

def _build_kpi_handler(metric_name: str):  # noqa: ANN202
    """
    Factory that creates a route handler for a single KPI endpoint.

    Supports three modes based on query parameters:
    - Comparison: ?asset_ids=Line-1,Line-2 → array of per-asset values
    - Trend: ?granularity=daily|hourly|weekly → array of time-series points
    - Single: default → single data point

    Args:
        metric_name: Canonical metric name for this endpoint.
    """

    async def handler(
        _auth: str = Depends(_verify_auth),
        period: str = Query("today", description="Time period"),
        asset_id: str = Query("Line-1", description="Single asset ID"),
        asset_ids: str | None = Query(
            None, description="Comma-separated asset IDs for comparison"
        ),
        granularity: str | None = Query(
            None, description="Trend granularity: hourly, daily, weekly"
        ),
        datetimeMin: str | None = Query(  # noqa: N803
            None, alias="datetimeMin", description="ISO start"
        ),
        datetimeMax: str | None = Query(  # noqa: N803
            None, alias="datetimeMax", description="ISO end"
        ),
    ) -> JSONResponse:
        # Comparison mode
        if asset_ids:
            ids = [a.strip() for a in asset_ids.split(",") if a.strip()]
            data = generate_comparison_data(metric_name, ids, period)
            return JSONResponse(content=data)

        # Trend mode
        if granularity and metric_name in _TREND_METRICS:
            data = generate_trend_data(
                metric_name,
                asset_id,
                granularity,
                period,
                datetimeMin,
                datetimeMax,
            )
            return JSONResponse(content=data)

        # Also treat granularity on non-trend metrics as trend
        if granularity:
            data = generate_trend_data(
                metric_name,
                asset_id,
                granularity,
                period,
                datetimeMin,
                datetimeMax,
            )
            return JSONResponse(content=data)

        # Single value mode
        data = generate_single_value(metric_name, asset_id, period)
        return JSONResponse(content=data)

    handler.__name__ = f"get_{metric_name}"
    handler.__doc__ = f"Get {metric_name} KPI data."
    return handler


# Register all 19 KPI endpoints
for _path, _metric in _PATH_TO_METRIC.items():
    app.get(_path, tags=["KPIs"])(_build_kpi_handler(_metric))


# =========================================================================
# Reneryo native measurement endpoint
# =========================================================================

@app.get(
    "/api/u/measurement/meter/item",
    tags=["Native"],
    summary="Reneryo native measurement format",
)
async def native_measurement(
    _auth: str = Depends(_verify_auth),
    metric: str = Query("energy_per_unit", description="Metric name"),
    meter: str = Query("Line-1", description="Meter/asset ID"),
    datetimeMin: str | None = Query(  # noqa: N803
        None, alias="datetimeMin", description="ISO start"
    ),
    datetimeMax: str | None = Query(  # noqa: N803
        None, alias="datetimeMax", description="ISO end"
    ),
) -> JSONResponse:
    """
    Simulate the real Reneryo /api/u/measurement/meter/item endpoint.

    Returns data in Reneryo's native array-of-measurements format so the
    response-parsing layer can be tested independently from endpoint mapping.
    """
    data = generate_native_measurement(
        metric, meter, datetimeMin, datetimeMax
    )
    return JSONResponse(content=data)
