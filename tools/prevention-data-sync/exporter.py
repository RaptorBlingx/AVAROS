"""
RENERYO → PREVENTION Data Sync Pipeline.

Exports manufacturing KPI data from RENERYO (via REST API) into
JSON files that the PREVENTION addon ingests at startup.

Usage:
    # One-shot export
    python -m tools.prevention_data_sync.exporter --output /path/to/addon/data

    # Daemon mode (hourly export)
    python -m tools.prevention_data_sync.exporter --daemon --interval 3600

Environment:
    RENERYO_API_URL:        RENERYO base URL
    RENERYO_SESSION_COOKIE: Auth cookie for RENERYO API
    PREVENTION_DATA_DIR:    Output directory (default: ./data)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =========================================================================
# Metric Category → File Mapping
# =========================================================================

CATEGORY_METRICS: dict[str, list[str]] = {
    "energy": [
        "energy_per_unit", "energy_total",
        "peak_demand", "peak_tariff_exposure",
    ],
    "production": [
        "oee", "throughput", "cycle_time", "changeover_time",
    ],
    "material": [
        "scrap_rate", "rework_rate",
        "material_efficiency", "recycled_content",
    ],
    "carbon": [
        "co2_per_unit", "co2_total", "co2_per_batch",
    ],
    "supplier": [
        "supplier_lead_time", "supplier_defect_rate",
        "supplier_on_time", "supplier_co2_per_kg",
    ],
}

CATEGORY_FILES: dict[str, str] = {
    "energy": "energy_metrics.json",
    "production": "production_metrics.json",
    "material": "material_metrics.json",
    "carbon": "carbon_metrics.json",
    "supplier": "supplier_metrics.json",
}

# Default assets to export data for
DEFAULT_ASSETS = ["Line-1", "Line-2", "Line-3"]


def _build_headers(session_cookie: str) -> dict[str, str]:
    """Build HTTP headers with RENERYO auth cookie."""
    return {
        "Cookie": session_cookie,
        "Accept": "application/json",
    }


def _fetch_metric_values(
    client: httpx.Client,
    api_url: str,
    resource_id: str,
    days: int = 7,
    count: int = 200,
) -> list[dict[str, Any]]:
    """
    Fetch time-series values for a single metric resource.

    Args:
        client: httpx client with auth headers
        api_url: RENERYO base API URL
        resource_id: Metric resource ID in RENERYO
        days: Number of days of history to fetch
        count: Maximum number of records

    Returns:
        List of {timestamp, value} dictionaries
    """
    now = datetime.now(tz=timezone.utc)
    start = now - timedelta(days=days)

    url = (
        f"{api_url}/u/measurement/metric/resource/"
        f"{resource_id}/values"
    )
    params = {
        "period": "RAW",
        "datetimeMin": start.isoformat(),
        "datetimeMax": now.isoformat(),
        "count": count,
    }

    try:
        resp = client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("records", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "Failed to fetch resource %s: %s", resource_id, exc,
        )
        return []


def _load_mapping_file(mapping_path: str) -> dict[str, dict[str, str]]:
    """
    Load the metric→resource_id mapping from the data generator.

    Expected format: {metric_name: {asset_id: resource_id}}

    Args:
        mapping_path: Path to mapping_output.json

    Returns:
        Mapping dictionary
    """
    path = Path(mapping_path)
    if not path.exists():
        logger.warning("Mapping file not found: %s", mapping_path)
        return {}

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def export_category_data(
    client: httpx.Client,
    api_url: str,
    category: str,
    metric_names: list[str],
    mapping: dict[str, dict[str, str]],
    assets: list[str],
    output_dir: Path,
    days: int = 7,
) -> int:
    """
    Export all metrics in a category to a single JSON file.

    Args:
        client: httpx client with auth headers
        api_url: RENERYO base URL
        category: Category name (energy, production, etc.)
        metric_names: List of canonical metric names in this category
        mapping: metric→asset→resource_id mapping
        assets: Asset IDs to export
        output_dir: Directory to write output files
        days: Days of history to export

    Returns:
        Number of data points exported
    """
    all_records: list[dict[str, Any]] = []
    record_id = 0

    for metric_name in metric_names:
        metric_mapping = mapping.get(metric_name, {})
        for asset_id in assets:
            resource_id = metric_mapping.get(asset_id)
            if not resource_id:
                logger.debug(
                    "No resource_id for %s/%s, skipping",
                    metric_name, asset_id,
                )
                continue

            raw_records = _fetch_metric_values(
                client, api_url, resource_id, days=days,
            )

            for raw in raw_records:
                record_id += 1
                all_records.append({
                    "id": record_id,
                    "metric_name": metric_name,
                    "asset_id": asset_id,
                    "timestamp": raw.get("datetime", raw.get("timestamp", "")),
                    "value": raw.get("value", 0),
                    "unit": raw.get("unit", ""),
                })

    output_file = output_dir / CATEGORY_FILES[category]
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, default=str)

    logger.info(
        "Exported %d records to %s", len(all_records), output_file,
    )
    return len(all_records)


def run_export(
    api_url: str,
    session_cookie: str,
    mapping_path: str,
    output_dir: str,
    assets: list[str] | None = None,
    days: int = 7,
) -> int:
    """
    Run a full data export from RENERYO to PREVENTION data files.

    Args:
        api_url: RENERYO base API URL
        session_cookie: Auth cookie string
        mapping_path: Path to mapping_output.json
        output_dir: Output directory for JSON files
        assets: Asset IDs to export (default: Line-1/2/3)
        days: Days of history

    Returns:
        Total number of records exported
    """
    if assets is None:
        assets = DEFAULT_ASSETS

    mapping = _load_mapping_file(mapping_path)
    if not mapping:
        logger.error("No metric mapping available. Run data generator first.")
        return 0

    headers = _build_headers(session_cookie)
    out_path = Path(output_dir)
    total = 0

    with httpx.Client(headers=headers) as client:
        for category, metrics in CATEGORY_METRICS.items():
            count = export_category_data(
                client=client,
                api_url=api_url,
                category=category,
                metric_names=metrics,
                mapping=mapping,
                assets=assets,
                output_dir=out_path,
                days=days,
            )
            total += count

    logger.info("Export complete: %d total records", total)
    return total


def main() -> None:
    """CLI entrypoint for data sync pipeline."""
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Export RENERYO data for PREVENTION addon",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.environ.get("PREVENTION_DATA_DIR", "./data"),
        help="Output directory for JSON files",
    )
    parser.add_argument(
        "--mapping",
        default=os.environ.get("MAPPING_FILE", "mapping_output.json"),
        help="Path to metric mapping file",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Days of history to export (default: 7)",
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run in daemon mode (periodic export)",
    )
    parser.add_argument(
        "--interval", type=int, default=3600,
        help="Export interval in seconds for daemon mode (default: 3600)",
    )

    args = parser.parse_args()

    api_url = os.environ.get("RENERYO_API_URL", "")
    session_cookie = os.environ.get("RENERYO_SESSION_COOKIE", "")

    if not api_url:
        logger.error("RENERYO_API_URL not set")
        return

    if args.daemon:
        logger.info(
            "Starting daemon mode: export every %ds", args.interval,
        )
        while True:
            run_export(
                api_url=api_url,
                session_cookie=session_cookie,
                mapping_path=args.mapping,
                output_dir=args.output,
                days=args.days,
            )
            time.sleep(args.interval)
    else:
        run_export(
            api_url=api_url,
            session_cookie=session_cookie,
            mapping_path=args.mapping,
            output_dir=args.output,
            days=args.days,
        )


if __name__ == "__main__":
    main()
