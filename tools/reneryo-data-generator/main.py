"""Deterministic demo manufacturing API for AVAROS."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from data import (
    METRIC_CONFIG,
    generate_comparison_data,
    generate_native_measurement,
    generate_single_value,
    generate_trend_data,
)


app = FastAPI(
    title="AVAROS Demo Manufacturing API",
    description="Deterministic evaluation API for AVAROS KPI mappings",
    version="0.1.0",
)


def _verify_auth(
    authorization: Annotated[str | None, Header()] = None,
    cookie: Annotated[str | None, Header()] = None,
) -> str:
    """Accept a non-empty bearer token or cookie for demo purposes."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token:
            return "bearer"
    if cookie and cookie.strip():
        return "cookie"
    raise HTTPException(
        status_code=401,
        detail="Provide a non-empty bearer token or cookie.",
    )


@app.middleware("http")
async def delay_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Add optional test latency with ``?delay_ms=N``."""
    delay = request.query_params.get("delay_ms")
    if delay:
        try:
            milliseconds = int(delay)
            if 0 < milliseconds <= 10_000:
                await asyncio.sleep(milliseconds / 1000)
        except (TypeError, ValueError):
            pass
    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "service": "avaros-demo-platform",
        "endpoints": len(METRIC_CONFIG),
    }


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


def _build_kpi_handler(metric_name: str):  # noqa: ANN202
    async def handler(
        _auth: str = Depends(_verify_auth),
        period: str = Query("today"),
        asset_id: str = Query("Line-1"),
        asset_ids: str | None = Query(None),
        granularity: str | None = Query(None),
        datetime_min: str | None = Query(None, alias="datetimeMin"),
        datetime_max: str | None = Query(None, alias="datetimeMax"),
    ) -> JSONResponse:
        if asset_ids:
            identifiers = [
                value.strip()
                for value in asset_ids.split(",")
                if value.strip()
            ]
            return JSONResponse(
                content=generate_comparison_data(
                    metric_name,
                    identifiers,
                    period,
                ),
            )
        if granularity:
            return JSONResponse(
                content=generate_trend_data(
                    metric_name,
                    asset_id,
                    granularity,
                    period,
                    datetime_min,
                    datetime_max,
                ),
            )
        return JSONResponse(
            content=generate_single_value(metric_name, asset_id, period),
        )

    handler.__name__ = f"get_{metric_name}"
    handler.__doc__ = f"Return deterministic {metric_name} demo data."
    return handler


for _path, _metric in _PATH_TO_METRIC.items():
    app.get(_path, tags=["KPIs"])(_build_kpi_handler(_metric))


@app.get("/api/u/measurement/meter/item", tags=["Compatibility"])
async def native_measurement(
    _auth: str = Depends(_verify_auth),
    metric: str = Query("energy_per_unit"),
    meter: str = Query("Line-1"),
    datetime_min: str | None = Query(None, alias="datetimeMin"),
    datetime_max: str | None = Query(None, alias="datetimeMax"),
) -> JSONResponse:
    return JSONResponse(
        content=generate_native_measurement(
            metric,
            meter,
            datetime_min,
            datetime_max,
        ),
    )
