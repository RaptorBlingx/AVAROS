#!/usr/bin/env python3
"""
AVAROS Metric Pipeline Validation Script

Validates the full pipeline: adapter reads correct KPI values for all 19
canonical metrics.  Tests get_kpi, get_trend, compare, and get_raw_data.

Usage:
    # Against live AVAROS (requires configured adapter + DB)
    python3 scripts/validate-metric-pipeline.py

    # Against a specific database URL
    AVAROS_DATABASE_URL=postgresql://avaros:avaros@localhost:5432/avaros \
        python3 scripts/validate-metric-pipeline.py

    # With a specific asset (default: tries first configured asset)
    python3 scripts/validate-metric-pipeline.py --asset line-1

    # Quick mode: only test KPI retrieval
    python3 scripts/validate-metric-pipeline.py --quick

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure skill package is importable from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from skill.adapters.factory import AdapterFactory
from skill.adapters.base import ManufacturingAdapter
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.services.settings import SettingsService

logger = logging.getLogger("validate-pipeline")

ALL_METRICS = list(CanonicalMetric)

# Representative metrics for trend / compare / raw_data spot checks.
SAMPLE_ENERGY = CanonicalMetric.ENERGY_PER_UNIT
SAMPLE_MATERIAL = CanonicalMetric.SCRAP_RATE
SAMPLE_PRODUCTION = CanonicalMetric.OEE


@dataclass
class CheckResult:
    """Outcome of a single validation check."""

    name: str
    passed: bool
    detail: str = ""


def _status(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _resolve_assets(settings: SettingsService, cli_asset: str | None) -> list[str]:
    """Return the list of asset IDs to test against."""
    if cli_asset:
        return [cli_asset]
    mappings = settings.get_asset_mappings()
    if mappings:
        return sorted(mappings.keys())
    return ["line-1"]


async def _check_kpi(
    adapter: ManufacturingAdapter,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
) -> CheckResult:
    """Validate get_kpi for a single metric + asset."""
    name = f"get_kpi({metric.value}, {asset_id})"
    try:
        result = await adapter.get_kpi(metric=metric, asset_id=asset_id, period=period)
        if result is None or result.value is None:
            return CheckResult(name=name, passed=False, detail="returned None")
        return CheckResult(
            name=name,
            passed=True,
            detail=f"{result.value} {result.unit}",
        )
    except Exception as exc:
        return CheckResult(name=name, passed=False, detail=str(exc))


async def _check_trend(
    adapter: ManufacturingAdapter,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
) -> CheckResult:
    """Validate get_trend returns non-empty time series."""
    name = f"get_trend({metric.value}, {asset_id})"
    try:
        result = await adapter.get_trend(
            metric=metric, asset_id=asset_id, period=period, granularity="daily",
        )
        if result is None:
            return CheckResult(name=name, passed=False, detail="returned None")
        points = getattr(result, "data_points", None) or ()
        if len(points) == 0:
            return CheckResult(name=name, passed=False, detail="empty time series")
        return CheckResult(
            name=name,
            passed=True,
            detail=f"{len(points)} data points",
        )
    except Exception as exc:
        return CheckResult(name=name, passed=False, detail=str(exc))


async def _check_compare(
    adapter: ManufacturingAdapter,
    metric: CanonicalMetric,
    asset_ids: list[str],
    period: TimePeriod,
) -> CheckResult:
    """Validate compare returns multi-asset results."""
    name = f"compare({metric.value}, {asset_ids})"
    if len(asset_ids) < 2:
        return CheckResult(name=name, passed=True, detail="skipped (need ≥2 assets)")
    try:
        result = await adapter.compare(
            metric=metric, asset_ids=asset_ids, period=period,
        )
        if result is None:
            return CheckResult(name=name, passed=False, detail="returned None")
        items = getattr(result, "items", None) or ()
        if len(items) == 0:
            return CheckResult(name=name, passed=False, detail="no comparison items")
        return CheckResult(
            name=name,
            passed=True,
            detail=f"{len(items)} items, winner={getattr(result, 'winner_id', '?')}",
        )
    except Exception as exc:
        return CheckResult(name=name, passed=False, detail=str(exc))


async def _check_raw_data(
    adapter: ManufacturingAdapter,
    metric: CanonicalMetric,
    asset_id: str,
    period: TimePeriod,
) -> CheckResult:
    """Validate get_raw_data returns data points."""
    name = f"get_raw_data({metric.value}, {asset_id})"
    try:
        result = await adapter.get_raw_data(
            metric=metric, asset_id=asset_id, period=period,
        )
        if result is None:
            return CheckResult(name=name, passed=False, detail="returned None")
        count = len(result) if hasattr(result, "__len__") else 0
        if count == 0:
            return CheckResult(name=name, passed=False, detail="empty result")
        return CheckResult(
            name=name,
            passed=True,
            detail=f"{count} data points",
        )
    except Exception as exc:
        return CheckResult(name=name, passed=False, detail=str(exc))


async def run_validation(
    asset_override: str | None = None,
    quick: bool = False,
) -> list[CheckResult]:
    """Execute all validation checks and return results."""
    settings = SettingsService()
    settings.initialize()
    adapter: ManufacturingAdapter | None = None

    try:
        factory = AdapterFactory(settings_service=settings)
        adapter = await factory.create_async()

        asset_ids = _resolve_assets(settings, asset_override)
        primary_asset = asset_ids[0]
        period = TimePeriod.last_month()

        results: list[CheckResult] = []

        # -- Phase 1: KPI retrieval for all 19 metrics -------------------------
        print(f"\n{'='*70}")
        print(f" KPI Retrieval — {len(ALL_METRICS)} metrics × asset '{primary_asset}'")
        print(f"{'='*70}")

        for metric in ALL_METRICS:
            check = await _check_kpi(adapter, metric, primary_asset, period)
            results.append(check)
            print(f"  [{_status(check.passed)}] {check.name:50s} {check.detail}")

        if not quick:
            # -- Phase 2: Trend for sample metrics ------------------------------
            print(f"\n{'='*70}")
            print(f" Trend Analysis — sample metrics × asset '{primary_asset}'")
            print(f"{'='*70}")

            for metric in (SAMPLE_ENERGY, SAMPLE_MATERIAL, SAMPLE_PRODUCTION):
                check = await _check_trend(adapter, metric, primary_asset, period)
                results.append(check)
                print(f"  [{_status(check.passed)}] {check.name:50s} {check.detail}")

            # -- Phase 3: Compare across assets ---------------------------------
            print(f"\n{'='*70}")
            print(f" Comparison — sample metric across {len(asset_ids)} assets")
            print(f"{'='*70}")

            check = await _check_compare(adapter, SAMPLE_ENERGY, asset_ids, period)
            results.append(check)
            print(f"  [{_status(check.passed)}] {check.name:50s} {check.detail}")

            # -- Phase 4: Raw data retrieval ------------------------------------
            print(f"\n{'='*70}")
            print(f" Raw Data — sample metric × asset '{primary_asset}'")
            print(f"{'='*70}")

            check = await _check_raw_data(adapter, SAMPLE_ENERGY, primary_asset, period)
            results.append(check)
            print(f"  [{_status(check.passed)}] {check.name:50s} {check.detail}")

        # -- Summary -----------------------------------------------------------
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        print(f"\n{'='*70}")
        print(f" Summary: {passed} passed, {failed} failed out of {len(results)} checks")
        print(f"{'='*70}\n")
        return results
    finally:
        if adapter is not None:
            try:
                await adapter.shutdown()
            except Exception:
                pass
        settings.close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the AVAROS metric pipeline end-to-end",
    )
    parser.add_argument(
        "--asset",
        default=None,
        help="Asset ID to test against (default: first configured asset)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Only test KPI retrieval (skip trend, compare, raw_data)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on failure."""
    args = _parse_args(argv)
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    results = asyncio.run(run_validation(asset_override=args.asset, quick=args.quick))

    failed = [r for r in results if not r.passed]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
