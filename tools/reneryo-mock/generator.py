#!/usr/bin/env python3
"""
Reneryo Data Generator — seeds and continuously feeds realistic
manufacturing data into Reneryo for all 19 AVAROS canonical metrics.

CLI modes:
    --seed     Create metrics + push 90 days of historical data
    --daemon   After seeding, push a new data point every 15 min
    --verify   Read back latest values and print summary
    --list     Show current metric/resource mapping table

Environment variables:
    RENERYO_API_URL          Base URL (default: http://deploys.int.arti.ac:31290/api)
    RENERYO_SESSION_COOKIE   Session cookie value (required)
    GENERATOR_MODE           daemon | seed | verify | list
    GENERATOR_INTERVAL       Seconds between daemon writes (default 900)
    GENERATOR_SEED_DAYS      Days of historical data to seed (default 90)
    GENERATOR_BATCH_DELAY    Milliseconds between batches (default 100)

This is a standalone tool — it does NOT import from skill/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from patterns import (
    DEFAULT_ASSETS,
    MetricProfile,
    METRIC_PROFILES,
    generate_all_metrics,
    generate_single_metric,
)
from reneryo_client import (
    ReneryoApiError,
    ReneryoClient,
    ReneryoClientError,
)

logger = logging.getLogger("generator")

BATCH_SIZE = 500
MAPPING_FILE = Path(__file__).parent / "mapping_output.json"


# =========================================================================
# Metric discovery / creation
# =========================================================================


async def _find_existing_metrics(
    client: ReneryoClient,
) -> dict[str, str]:
    """List existing AVAROS metrics and map display name → metric ID.

    Returns:
        Dict mapping display_name → metric_id for metrics prefixed "AVAROS ".
    """
    metrics = await client.list_metrics(count=500)
    found: dict[str, str] = {}
    for m in metrics:
        name = m.get("name", "")
        if name.startswith("AVAROS "):
            found[name] = m["id"]
    return found


async def ensure_metrics_exist(
    client: ReneryoClient,
) -> dict[str, str]:
    """Create all 19 AVAROS metrics (skip if already exist).

    Returns:
        Dict mapping canonical metric_name → metric_id.
    """
    existing = await _find_existing_metrics(client)
    name_to_id: dict[str, str] = {}

    for profile in METRIC_PROFILES:
        if profile.display_name in existing:
            metric_id = existing[profile.display_name]
            logger.info(
                "Found existing metric '%s' → %s",
                profile.display_name, metric_id,
            )
        else:
            metric_id = await _create_or_reuse_metric(client, profile)
        name_to_id[profile.name] = metric_id

    logger.info("All 19 metrics ensured (%d created, %d existing)",
                19 - len(existing), min(len(existing), 19))
    return name_to_id


async def _create_or_reuse_metric(
    client: ReneryoClient,
    profile: MetricProfile,
) -> str:
    """Create a metric, or reuse existing metric when duplicate-name create fails.

    This guards against partial metric listings in large tenants where
    `list_metrics(count=500)` might miss an existing AVAROS metric.
    """
    try:
        return await client.create_metric(
            name=profile.display_name,
            metric_type="GAUGE",
            unit_group="SCALAR",
            description=f"{profile.name} ({profile.unit})",
        )
    except ReneryoApiError:
        existing = await _find_existing_metrics(client)
        metric_id = existing.get(profile.display_name, "")
        if metric_id:
            logger.info(
                "Reused existing metric after create failure '%s' → %s",
                profile.display_name,
                metric_id,
            )
            return metric_id
        raise


# =========================================================================
# Seed mode
# =========================================================================


async def seed(
    client: ReneryoClient,
    days: int = 90,
    batch_delay_ms: int = 100,
) -> dict[str, dict[str, str]]:
    """Create metrics and push historical data for all assets.

    Args:
        client: Initialized ReneryoClient.
        days: Number of days of historical data.
        batch_delay_ms: Delay between batch writes in milliseconds.

    Returns:
        Mapping: {metric_name: {asset: resource_id}}.
    """
    metric_ids = await ensure_metrics_exist(client)
    mapping: dict[str, dict[str, str]] = {
        name: {} for name in metric_ids
    }

    end = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )
    start = end - timedelta(days=days)
    delay_s = batch_delay_ms / 1000.0

    total_assets = len(DEFAULT_ASSETS)
    for asset_idx, asset in enumerate(DEFAULT_ASSETS, 1):
        logger.info(
            "=== Generating data for %s (%d/%d) ===",
            asset, asset_idx, total_assets,
        )
        all_data = generate_all_metrics(start, end, asset)

        for metric_name, points in all_data.items():
            metric_id = metric_ids[metric_name]
            resource_id = await _write_batched(
                client, metric_id, points,
                asset=asset, delay_s=delay_s,
            )
            mapping[metric_name][asset] = resource_id
            logger.info(
                "  %s/%s: %d points → resource %s",
                metric_name, asset, len(points), resource_id[:12],
            )

    _save_mapping(mapping)
    logger.info("Seed complete. Mapping saved to %s", MAPPING_FILE)
    return mapping


async def _write_batched(
    client: ReneryoClient,
    metric_id: str,
    points: list[dict[str, Any]],
    *,
    asset: str,
    delay_s: float,
) -> str:
    """Write points in batches of BATCH_SIZE, return resource ID.

    Args:
        client: Initialized ReneryoClient.
        metric_id: Reneryo metric UUID.
        points: All data points for this metric/asset.
        asset: Asset identifier for labels.
        delay_s: Delay between batches.

    Returns:
        Resource ID from the first successful write.
    """
    labels = [{"key": "asset", "value": asset}]
    resource_id = ""

    for batch_start in range(0, len(points), BATCH_SIZE):
        batch = points[batch_start : batch_start + BATCH_SIZE]
        rid = await client.write_values(
            metric_id, "SCALAR", batch, labels
        )
        if not resource_id:
            resource_id = rid
        if delay_s > 0:
            await asyncio.sleep(delay_s)

    return resource_id


# =========================================================================
# Daemon mode
# =========================================================================


async def daemon(
    client: ReneryoClient,
    interval_s: int = 900,
    seed_days: int = 90,
    batch_delay_ms: int = 100,
) -> None:
    """Seed data, then push new data points on a schedule.

    Args:
        client: Initialized ReneryoClient.
        interval_s: Seconds between daemon writes.
        seed_days: Days of historical data to seed.
        batch_delay_ms: Delay between batch writes in milliseconds.
    """
    await seed(client, days=seed_days, batch_delay_ms=batch_delay_ms)
    metric_ids = await ensure_metrics_exist(client)

    # Reference start for improvement trend
    ref_start = datetime.now(timezone.utc) - timedelta(days=seed_days)

    logger.info("Entering daemon mode (interval=%ds)", interval_s)
    while True:
        await asyncio.sleep(interval_s)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        await _push_single_round(client, metric_ids, now, ref_start)


async def _push_single_round(
    client: ReneryoClient,
    metric_ids: dict[str, str],
    now: datetime,
    ref_start: datetime,
) -> None:
    """Push one data point per metric per asset.

    Args:
        client: Initialized ReneryoClient.
        metric_ids: metric_name → metric_id mapping.
        now: Current timestamp.
        ref_start: Reference start for improvement trend.
    """
    for profile in METRIC_PROFILES:
        metric_id = metric_ids[profile.name]
        for asset in DEFAULT_ASSETS:
            point = generate_single_metric(
                profile, now, ref_start, asset,
            )
            labels = [{"key": "asset", "value": asset}]
            await client.write_values(
                metric_id, "SCALAR", [point], labels
            )
    logger.info("Daemon: pushed %d values at %s",
                len(METRIC_PROFILES) * len(DEFAULT_ASSETS),
                now.isoformat())


# =========================================================================
# Verify mode
# =========================================================================


async def verify(client: ReneryoClient, count: int = 5) -> None:
    """Read back latest values from each resource and print summary.

    Args:
        client: Initialized ReneryoClient.
        count: Number of recent values to read per resource.
    """
    mapping = _load_mapping()
    if not mapping:
        logger.error("No mapping_output.json found. Run --seed first.")
        return

    ok_count = 0
    fail_count = 0

    for metric_name, assets in sorted(mapping.items()):
        for asset, resource_id in sorted(assets.items()):
            try:
                result = await client.read_values(
                    resource_id, period="RAW", count=count,
                )
                records = result.get("records", [])
                total = result.get("recordCount", 0)
                status = "OK" if records else "EMPTY"
                if records:
                    latest = records[-1]
                    print(
                        f"  {status} {metric_name:25s} {asset:8s} "
                        f"total={total:>6d}  latest={latest['value']:>10.2f} "
                        f" @ {latest['datetime']}"
                    )
                    ok_count += 1
                else:
                    print(
                        f"  {status} {metric_name:25s} {asset:8s} "
                        f"total={total:>6d}  (no records)"
                    )
                    fail_count += 1
            except ReneryoClientError as exc:
                print(
                    f"  ERR  {metric_name:25s} {asset:8s}  {exc}"
                )
                fail_count += 1

    total_resources = ok_count + fail_count
    print(f"\nSummary: {ok_count}/{total_resources} resources verified OK")


# =========================================================================
# List mode
# =========================================================================


async def list_mapping(client: ReneryoClient) -> None:
    """Print the metric/resource mapping table.

    Args:
        client: Initialized ReneryoClient (used for live lookup).
    """
    mapping = _load_mapping()
    if mapping:
        _print_mapping(mapping, source="mapping_output.json")
        return

    # Fall back to live lookup
    logger.info("No mapping file found, querying Reneryo...")
    metric_ids = await ensure_metrics_exist(client)
    mapping = {}
    for metric_name, metric_id in metric_ids.items():
        resources = await client.list_resources(metric_id)
        asset_map: dict[str, str] = {}
        for r in resources:
            resource_id = r.get("id", "")
            labels = r.get("labels", [])
            asset_label = _extract_asset_label(labels)
            if asset_label:
                asset_map[asset_label] = resource_id
        if asset_map:
            mapping[metric_name] = asset_map

    _print_mapping(mapping, source="live Reneryo query")


def _extract_asset_label(labels: list[dict[str, str]]) -> str:
    """Extract asset value from a labels list."""
    for label in labels:
        if label.get("key") == "asset":
            return label.get("value", "")
    return ""


def _print_mapping(
    mapping: dict[str, dict[str, str]],
    source: str,
) -> None:
    """Pretty-print the mapping table."""
    total = sum(len(v) for v in mapping.values())
    print(f"\nResource mapping ({total} resources from {source}):")
    print(f"{'Metric':<28s} {'Asset':<10s} {'Resource ID'}")
    print("-" * 80)
    for metric_name in sorted(mapping):
        for asset, rid in sorted(mapping[metric_name].items()):
            print(f"  {metric_name:<26s} {asset:<10s} {rid}")
    print(f"\nTotal: {len(mapping)} metrics × {total} resources")


# =========================================================================
# Mapping file I/O
# =========================================================================


def _save_mapping(mapping: dict[str, dict[str, str]]) -> None:
    """Write mapping to mapping_output.json."""
    MAPPING_FILE.write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n"
    )


def _load_mapping() -> dict[str, dict[str, str]]:
    """Load mapping from mapping_output.json, or return empty dict."""
    if not MAPPING_FILE.exists():
        return {}
    try:
        return json.loads(MAPPING_FILE.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return {}


# =========================================================================
# CLI
# =========================================================================


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Reneryo Data Generator for AVAROS canonical metrics",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--seed", action="store_true",
        help="Create metrics and seed historical data",
    )
    modes.add_argument(
        "--daemon", action="store_true",
        help="Seed, then continuously push data",
    )
    modes.add_argument(
        "--verify", action="store_true",
        help="Read back data and verify round-trip",
    )
    modes.add_argument(
        "--list", action="store_true",
        help="Show metric/resource mapping table",
    )
    parser.add_argument(
        "--days", type=int,
        default=int(os.environ.get("GENERATOR_SEED_DAYS", "90")),
        help="Days of historical data to seed (default: 90)",
    )
    parser.add_argument(
        "--interval", type=int,
        default=int(os.environ.get("GENERATOR_INTERVAL", "900")),
        help="Daemon interval in seconds (default: 900)",
    )
    parser.add_argument(
        "--batch-delay", type=int,
        default=int(os.environ.get("GENERATOR_BATCH_DELAY", "100")),
        help="Delay between batches in ms (default: 100)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


async def _async_main(args: argparse.Namespace) -> None:
    """Async entry point dispatching to the selected mode."""
    async with ReneryoClient() as client:
        if args.daemon:
            await daemon(
                client,
                interval_s=args.interval,
                seed_days=args.days,
                batch_delay_ms=args.batch_delay,
            )
        elif args.verify:
            await verify(client)
        elif args.list:
            await list_mapping(client)
        else:
            # Default to --seed (also handles env GENERATOR_MODE)
            await seed(
                client,
                days=args.days,
                batch_delay_ms=args.batch_delay,
            )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = _parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Support env-based mode (for Docker)
    env_mode = os.environ.get("GENERATOR_MODE", "").lower()
    if not any([args.seed, args.daemon, args.verify, args.list]):
        if env_mode == "daemon":
            args.daemon = True
        elif env_mode == "verify":
            args.verify = True
        elif env_mode == "list":
            args.list = True
        else:
            args.seed = True

    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")
    except ReneryoClientError as exc:
        logger.error("Reneryo client error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
