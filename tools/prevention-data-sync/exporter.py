#!/usr/bin/env python3
"""Data exporter for PREVENTION analytics.

Pulls time-series data from a configured REST adapter and writes
PREVENTION-compatible JSON files. The output files are consumed by
the AVAROS PREVENTION addon's ``load_data.py``.

Usage:
    python3 tools/prevention-data-sync/exporter.py \\
        --platform generic_rest \\
        --api-url https://api.example.com \\
        --api-key SECRET \\
        --days 30

    python3 tools/prevention-data-sync/exporter.py \\
        --platform generic_rest \\
        --api-url https://api.example.com \\
        --output /tmp/prevention-data
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Allow imports from the skill package when running from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from skill.domain.models import Asset, CanonicalMetric, DataPoint, TimePeriod  # noqa: E402
from skill.services.settings import SettingsService  # noqa: E402

logger = logging.getLogger("prevention-data-sync")

# Map category → output filename (matches load_data.py expectations).
_CATEGORY_FILES: dict[str, str] = {
    "energy": "energy_metrics.json",
    "production": "production_metrics.json",
    "material": "material_metrics.json",
    "carbon": "carbon_metrics.json",
    "supplier": "supplier_metrics.json",
}

_DEFAULT_OUTPUT = _REPO_ROOT / "tools" / "prevention-addon" / "data"
_MANIFEST_FILENAME = "export_manifest.json"
_METRIC_CATEGORY_MAP: dict[str, str] = {
    "energy_per_unit": "energy",
    "energy_total": "energy",
    "peak_demand": "energy",
    "peak_tariff_exposure": "energy",
    "scrap_rate": "material",
    "rework_rate": "material",
    "material_efficiency": "material",
    "recycled_content": "material",
    "supplier_lead_time": "supplier",
    "supplier_defect_rate": "supplier",
    "supplier_on_time": "supplier",
    "supplier_co2_per_kg": "supplier",
    "oee": "production",
    "throughput": "production",
    "cycle_time": "production",
    "changeover_time": "production",
    "co2_per_unit": "carbon",
    "co2_total": "carbon",
    "co2_per_batch": "carbon",
}


# ── Adapter creation ─────────────────────────────────────────────


async def _create_adapter(
    platform: str,
    api_url: str,
    api_key: str,
    *,
    auth_type: str = "bearer",
    profile_name: str = "",
    settings_service: SettingsService | None = None,
) -> Any:
    """Instantiate and initialise a ManufacturingAdapter.

    Args:
        platform: Adapter type (currently ``generic_rest`` only).
        api_url: Base URL for REST-based adapters.
        api_key: API key / bearer token.

    Returns:
        An initialised ManufacturingAdapter instance.

    Raises:
        SystemExit: If the platform is unknown or config is missing.
    """
    if platform == "generic_rest":
        extra_settings: dict[str, Any] = {}
        if not api_url:
            settings_service = settings_service or SettingsService()
            active_profile = profile_name or settings_service.get_active_profile_name()
            if active_profile == settings_service.DEFAULT_PROFILE:
                raise RuntimeError(
                    "No active platform profile is configured; PREVENTION export skipped.",
                )
            config = settings_service.get_profile(active_profile)
            if config is None or not config.api_url:
                raise RuntimeError(
                    f"Platform profile '{active_profile}' is missing API configuration.",
                )
            api_url = config.api_url
            api_key = config.api_key
            extra_settings = dict(config.extra_settings or {})
            auth_type = str(extra_settings.get("auth_type", auth_type)).strip().lower()
            profile_name = active_profile

        if not api_url:
            logger.error("--api-url is required for generic_rest")
            raise SystemExit(1)

        from skill.adapters.generic_rest import GenericRestAdapter

        adapter = GenericRestAdapter(
            api_url=api_url,
            api_key=api_key,
            auth_type=auth_type,
            extra_settings=extra_settings,
            settings_service=settings_service,
            profile_name=profile_name or "export",
        )
        await adapter.initialize()
        return adapter

    logger.error("Unknown platform '%s'. Supported: generic_rest", platform)
    raise SystemExit(1)


# ── Data collection ──────────────────────────────────────────────


async def _get_export_points(
    adapter: Any,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
) -> list[DataPoint]:
    """Return normalized time-series points for export.

    Adapters should expose trend data as normalized ``DataPoint`` values.
    The older raw-data path is kept as a compatibility fallback for tests and
    adapters that already return ``DataPoint`` lists from ``get_raw_data``.
    """
    trend_fn = getattr(adapter, "get_trend", None)
    if callable(trend_fn) and inspect.iscoroutinefunction(trend_fn):
        trend = await trend_fn(
            metric=metric,
            asset_id=asset_id,
            period=period,
            granularity="daily",
        )
        points = getattr(trend, "data_points", [])
        return [point for point in points if isinstance(point, DataPoint)]

    raw = await adapter.get_raw_data(
        metric=metric,
        asset_id=asset_id,
        period=period,
    )
    return _coerce_raw_points(raw)


def _coerce_raw_points(raw: Any) -> list[DataPoint]:
    """Best-effort conversion of raw payloads into ``DataPoint`` values."""
    if isinstance(raw, DataPoint):
        return [raw]
    if isinstance(raw, list):
        points: list[DataPoint] = []
        for item in raw:
            points.extend(_coerce_raw_points(item))
        return points
    if isinstance(raw, dict):
        nested = raw.get("data")
        if isinstance(nested, list):
            return _coerce_raw_points(nested)

        timestamp = raw.get("timestamp") or raw.get("datetime") or raw.get("date")
        value = raw.get("value")
        if timestamp is None or value is None:
            return []
        try:
            parsed = (
                datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if not isinstance(timestamp, datetime)
                else timestamp
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return [
                DataPoint(
                    timestamp=parsed,
                    value=float(value),
                    unit=str(raw.get("unit", "")),
                ),
            ]
        except (TypeError, ValueError):
            return []
    return []


def _requires_metric_resource(adapter: Any, metric_name: str) -> bool:
    """Return True when the metric mapping needs a per-asset resource id."""
    lookup = getattr(adapter, "_lookup_metric_mapping_by_name", None)
    if not callable(lookup):
        return False
    mapping = lookup(metric_name)
    if not isinstance(mapping, dict):
        return False
    templates = [
        str(mapping.get("endpoint", "")),
        str(mapping.get("trend_endpoint", "")),
        str(mapping.get("raw_endpoint", "")),
    ]
    return any(
        "{resource_id}" in template or "{resource_uuid}" in template
        for template in templates
    )


def _has_metric_resource(adapter: Any, metric_name: str, asset_id: str) -> bool:
    """Return True when asset_id is linked to metric_name."""
    resolver = getattr(adapter, "_resolve_metric_resource_id", None)
    if not callable(resolver):
        return True
    return bool(str(resolver(metric_name, asset_id)).strip())


async def _collect_data(
    adapter: Any,
    days: int,
) -> dict[str, list[dict[str, Any]]]:
    """Collect raw time-series from the adapter for all metrics/assets.

    Groups records by PREVENTION category.

    Args:
        adapter: An initialised ManufacturingAdapter.
        days: Number of historical days to export.

    Returns:
        Mapping of category name → list of flat JSON records.
    """
    period = TimePeriod(
        start=datetime.now(tz=timezone.utc) - timedelta(days=days),
        end=datetime.now(tz=timezone.utc),
        display_name=f"last {days} days",
    )

    assets = await adapter.list_assets()
    if not assets:
        logger.warning("Adapter returned no assets — output will be empty")
        return {}

    metrics = adapter.get_supported_metrics()
    logger.info(
        "Exporting %d metrics × %d assets × %d days",
        len(metrics), len(assets), days,
    )

    buckets: dict[str, list[dict[str, Any]]] = {
        cat: [] for cat in _CATEGORY_FILES
    }
    record_id = 0

    for metric in metrics:
        category = _METRIC_CATEGORY_MAP.get(metric.value)
        if category is None:
            logger.debug("Skipping unmapped metric %s", metric.value)
            continue

        for asset in assets:
            aid = getattr(asset, "asset_id", str(asset))
            if _requires_metric_resource(adapter, metric.value) and not _has_metric_resource(
                adapter,
                metric.value,
                aid,
            ):
                logger.debug(
                    "Skipping unlinked asset/metric pair %s/%s",
                    metric.value,
                    aid,
                )
                continue
            try:
                points = await _get_export_points(
                    adapter=adapter,
                    metric=metric,
                    asset_id=aid,
                    period=period,
                )
            except Exception as exc:
                logger.warning(
                    "PREVENTION export data fetch failed for %s/%s: %s",
                    metric.value, aid, exc,
                )
                continue

            for pt in points:
                record_id += 1
                buckets[category].append({
                    "id": record_id,
                    "metric_name": metric.value,
                    "asset_id": aid,
                    "timestamp": pt.timestamp.strftime(
                        "%Y-%m-%dT%H:%M:%S.000Z",
                    ),
                    "value": round(pt.value, 4),
                    "unit": pt.unit,
                })

    return buckets


# ── File writing ─────────────────────────────────────────────────


def _write_files(
    buckets: dict[str, list[dict[str, Any]]],
    output_dir: Path,
    *,
    platform: str = "unknown",
    days: int | None = None,
) -> int:
    """Write category JSON files to *output_dir*.

    Args:
        buckets: Category → records mapping from ``_collect_data``.
        output_dir: Target directory (created if needed).

    Returns:
        Total number of records written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    total = 0

    manifest_files: dict[str, dict[str, int | str]] = {}

    for category, filename in _CATEGORY_FILES.items():
        records = buckets.get(category, [])
        path = output_dir / filename
        with open(path, "w") as fh:
            json.dump(records, fh, indent=2)
        logger.info("Wrote %d records → %s", len(records), path)
        manifest_files[category] = {
            "filename": filename,
            "records": len(records),
        }
        total += len(records)

    manifest = {
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "platform": platform,
        "days": days,
        "total_records": total,
        "files": manifest_files,
    }
    with open(output_dir / _MANIFEST_FILENAME, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    return total


# ── CLI entry point ──────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv).

    Returns:
        Parsed namespace.
    """
    parser = argparse.ArgumentParser(
        description="Export adapter data to PREVENTION-compatible JSON.",
    )
    parser.add_argument(
        "--platform",
        default="generic_rest",
        help="Adapter type: generic_rest (default: generic_rest)",
    )
    parser.add_argument(
        "--api-url",
        default="",
        help="Base URL for REST-based adapters",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="API key / bearer token",
    )
    parser.add_argument(
        "--auth-type",
        default="bearer",
        choices=("bearer", "cookie", "none"),
        help="Authentication type when --api-url is supplied directly",
    )
    parser.add_argument(
        "--profile",
        default=os.environ.get("PREVENTION_EXPORT_PROFILE", ""),
        help="Named AVAROS platform profile to export (default: active profile)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.environ.get("PREVENTION_EXPORT_DAYS", "7")),
        help="Number of historical days to export (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            os.environ.get("PREVENTION_EXPORT_OUTPUT", str(_DEFAULT_OUTPUT)),
        ),
        help="Output directory (default: tools/prevention-addon/data/)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("PREVENTION_EXPORT_INTERVAL_SECONDS", "0")),
        help="Seconds between exports. 0 runs once (default: 0)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously, sleeping --interval seconds between exports.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


async def _async_main(args: argparse.Namespace) -> None:
    """Async entry point.

    Args:
        args: Parsed CLI arguments.
    """
    if args.daemon or args.interval > 0:
        interval = max(60, int(args.interval or 900))
        logger.info("Starting PREVENTION exporter daemon (interval=%ss)", interval)
        while True:
            try:
                await _run_export_once(args)
            except Exception as exc:  # noqa: BLE001
                logger.warning("PREVENTION export cycle failed: %s", exc)
            await asyncio.sleep(interval)
        return

    await _run_export_once(args)


async def _run_export_once(args: argparse.Namespace) -> None:
    """Run one export cycle."""
    settings_service = SettingsService() if not args.api_url else None
    adapter: Any | None = None
    try:
        adapter = await _create_adapter(
            platform=args.platform,
            api_url=args.api_url,
            api_key=args.api_key,
            auth_type=args.auth_type,
            profile_name=args.profile,
            settings_service=settings_service,
        )
        buckets = await _collect_data(adapter, days=args.days)
        total = _write_files(
            buckets,
            output_dir=args.output,
            platform=args.platform,
            days=args.days,
        )
        logger.info("Export complete: %d records total", total)
    finally:
        if adapter is not None and hasattr(adapter, "shutdown"):
            await adapter.shutdown()
        if settings_service is not None:
            settings_service.close()


def main(argv: list[str] | None = None) -> None:
    """CLI entry point.

    Args:
        argv: Argument list (defaults to sys.argv).
    """
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
