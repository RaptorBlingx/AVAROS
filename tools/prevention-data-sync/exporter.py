#!/usr/bin/env python3
"""Platform-agnostic data exporter for PREVENTION analytics.

Pulls time-series data from ANY ManufacturingAdapter and writes
PREVENTION-compatible JSON files. The output files are consumed by
the AVAROS PREVENTION addon's ``load_data.py``.

Usage:
    # Export from mock adapter (demo / CI):
    python3 tools/prevention-data-sync/exporter.py --platform mock

    # Export from a configured REST backend:
    python3 tools/prevention-data-sync/exporter.py \\
        --platform generic_rest \\
        --api-url https://api.example.com \\
        --api-key SECRET \\
        --days 30

    # Custom output directory:
    python3 tools/prevention-data-sync/exporter.py \\
        --platform mock \\
        --output /tmp/prevention-data

DEC-001: No platform names — works with any adapter.
DEC-005: Defaults to mock adapter for zero-config demo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Allow imports from the skill package when running from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from skill.clients._prevention_demo_data import METRIC_CATEGORY_MAP  # noqa: E402
from skill.domain.models import CanonicalMetric, DataPoint, TimePeriod  # noqa: E402

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


# ── Adapter creation ─────────────────────────────────────────────


async def _create_adapter(
    platform: str,
    api_url: str,
    api_key: str,
) -> Any:
    """Instantiate and initialise a ManufacturingAdapter.

    Args:
        platform: Adapter type (``mock``, ``generic_rest``).
        api_url: Base URL for REST-based adapters.
        api_key: API key / bearer token.

    Returns:
        An initialised ManufacturingAdapter instance.

    Raises:
        SystemExit: If the platform is unknown or config is missing.
    """
    if platform == "mock":
        from skill.adapters.unconfigured import UnconfiguredAdapter

        adapter = UnconfiguredAdapter()
        await adapter.initialize()
        return adapter

    if platform == "generic_rest":
        if not api_url:
            logger.error("--api-url is required for generic_rest")
            raise SystemExit(1)

        from skill.adapters.generic_rest import GenericRestAdapter

        adapter = GenericRestAdapter(
            api_url=api_url,
            api_key=api_key,
            profile_name="export",
        )
        await adapter.initialize()
        return adapter

    logger.error("Unknown platform '%s'. Supported: mock, generic_rest", platform)
    raise SystemExit(1)


# ── Data collection ──────────────────────────────────────────────


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
        category = METRIC_CATEGORY_MAP.get(metric.value)
        if category is None:
            logger.debug("Skipping unmapped metric %s", metric.value)
            continue

        for asset in assets:
            aid = getattr(asset, "asset_id", str(asset))
            try:
                points: list[DataPoint] = await adapter.get_raw_data(
                    metric=metric,
                    asset_id=aid,
                    period=period,
                )
            except Exception as exc:
                logger.warning(
                    "get_raw_data failed for %s/%s: %s",
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

    for category, filename in _CATEGORY_FILES.items():
        records = buckets.get(category, [])
        path = output_dir / filename
        with open(path, "w") as fh:
            json.dump(records, fh, indent=2)
        logger.info("Wrote %d records → %s", len(records), path)
        total += len(records)

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
        default="mock",
        help="Adapter type: mock, generic_rest (default: mock)",
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
        "--days",
        type=int,
        default=7,
        help="Number of historical days to export (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Output directory (default: tools/prevention-addon/data/)",
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
    adapter = await _create_adapter(
        platform=args.platform,
        api_url=args.api_url,
        api_key=args.api_key,
    )
    try:
        buckets = await _collect_data(adapter, days=args.days)
        total = _write_files(buckets, output_dir=args.output)
        logger.info("Export complete: %d records total", total)
    finally:
        if hasattr(adapter, "shutdown"):
            await adapter.shutdown()


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
