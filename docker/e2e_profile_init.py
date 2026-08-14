"""Bootstrap the isolated E2E database with a deterministic REST profile."""

from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skill.domain.models import CanonicalMetric
from skill.services.models import PlatformConfig
from skill.services.settings import SettingsService


PROFILE = "e2e-demo"

ENDPOINTS = {
    "energy_per_unit": "/api/v1/kpis/energy/per-unit",
    "energy_total": "/api/v1/kpis/energy/total",
    "peak_demand": "/api/v1/kpis/energy/peak-demand",
    "peak_tariff_exposure": "/api/v1/kpis/energy/tariff-exposure",
    "scrap_rate": "/api/v1/kpis/material/scrap-rate",
    "rework_rate": "/api/v1/kpis/material/rework-rate",
    "material_efficiency": "/api/v1/kpis/material/efficiency",
    "recycled_content": "/api/v1/kpis/material/recycled-content",
    "supplier_lead_time": "/api/v1/kpis/supplier/lead-time",
    "supplier_defect_rate": "/api/v1/kpis/supplier/defect-rate",
    "supplier_on_time": "/api/v1/kpis/supplier/on-time",
    "supplier_co2_per_kg": "/api/v1/kpis/supplier/co2-per-kg",
    "oee": "/api/v1/kpis/production/oee",
    "throughput": "/api/v1/kpis/production/throughput",
    "cycle_time": "/api/v1/kpis/production/cycle-time",
    "changeover_time": "/api/v1/kpis/production/changeover-time",
    "co2_per_unit": "/api/v1/kpis/carbon/per-unit",
    "co2_total": "/api/v1/kpis/carbon/total",
    "co2_per_batch": "/api/v1/kpis/carbon/per-batch",
}


def main() -> None:
    """Create a complete deterministic profile before the skill starts."""
    service = SettingsService(database_url=os.environ["AVAROS_DATABASE_URL"])
    service.initialize()
    try:
        if service.get_profile(PROFILE) is None:
            service.create_profile(
                PROFILE,
                PlatformConfig(
                    platform_type="custom_rest",
                    api_url=os.environ.get(
                        "E2E_PLATFORM_URL",
                        "http://e2e-reneryo-data-generator:8090",
                    ),
                    api_key="e2e-token",
                    extra_settings={
                        "auth_type": "bearer",
                        "display_name": "Deterministic E2E Manufacturing",
                        "site_timezone": "UTC",
                    },
                ),
            )
        service.set_active_profile(PROFILE)

        for metric in CanonicalMetric:
            endpoint = ENDPOINTS.get(metric.value)
            if endpoint is None:
                continue
            request = (
                f"{endpoint}?asset_id={{asset_id}}&period={{period}}"
            )
            service.set_metric_mapping(
                metric.value,
                {
                    "endpoint": request,
                    "json_path": "$.value",
                    "unit": metric.default_unit,
                    "aggregation": (
                        "sum"
                        if metric in {
                            CanonicalMetric.ENERGY_TOTAL,
                            CanonicalMetric.CO2_TOTAL,
                        }
                        else "max"
                        if metric is CanonicalMetric.PEAK_DEMAND
                        else "average"
                    ),
                    "timestamp_path": "$.timestamp",
                    "trend_endpoint": f"{request}&granularity=daily",
                },
            )

        assets = {
            asset_id: {
                "display_name": asset_id.replace("-", " "),
                "asset_type": "production_line"
                if asset_id.startswith("Line-")
                else "machine",
                "aliases": [asset_id, asset_id.replace("-", " ")],
            }
            for asset_id in (
                "Line-1",
                "Line-2",
                "Line-3",
                "Compressor-1",
                "Compressor-2",
            )
        }
        service.set_asset_mappings(assets, profile=PROFILE)
    finally:
        service.close()


if __name__ == "__main__":
    main()
