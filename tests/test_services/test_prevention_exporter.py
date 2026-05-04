"""Tests for the platform-agnostic PREVENTION data exporter.

Validates that the exporter:
- Uses the ManufacturingAdapter ABC (platform-agnostic)
- Writes PREVENTION-compatible JSON files
- Correctly categorises metrics by PREVENTION category
- Handles adapter errors gracefully
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill.domain.models import Asset, CanonicalMetric, DataPoint

# Import from tools — the exporter adds repo root to sys.path
import sys
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "tools" / "prevention-data-sync"),
)
from exporter import (  # noqa: E402
    _CATEGORY_FILES,
    _MANIFEST_FILENAME,
    _collect_data,
    _create_adapter,
    _has_metric_resource,
    _requires_metric_resource,
    _write_files,
)


# ── Fixtures ─────────────────────────────────────────


def _make_adapter(
    *,
    metrics: list[CanonicalMetric] | None = None,
    assets: list[Asset] | None = None,
    points: list[DataPoint] | None = None,
    raw_data_error: Exception | None = None,
) -> MagicMock:
    """Build a mock ManufacturingAdapter.

    Args:
        metrics: Metrics the adapter claims to support.
        assets: Assets for list_assets().
        points: DataPoints returned by get_raw_data().
        raw_data_error: If set, get_raw_data() raises this.

    Returns:
        Mock adapter with async methods.
    """
    adapter = MagicMock()
    adapter.get_supported_metrics.return_value = (
        metrics if metrics is not None else [CanonicalMetric.ENERGY_PER_UNIT]
    )
    adapter.list_assets = AsyncMock(
        return_value=assets if assets is not None else [
            Asset(asset_id="Line-1", display_name="Line 1", asset_type="line"),
        ],
    )
    if raw_data_error is not None:
        adapter.get_raw_data = AsyncMock(side_effect=raw_data_error)
    else:
        adapter.get_raw_data = AsyncMock(
            return_value=points if points is not None else [
                DataPoint(
                    timestamp=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
                    value=2.51,
                    unit="kWh/unit",
                ),
                DataPoint(
                    timestamp=datetime(2026, 4, 1, 10, 15, tzinfo=timezone.utc),
                    value=2.64,
                    unit="kWh/unit",
                ),
            ],
        )
    adapter.shutdown = AsyncMock()
    return adapter


# ── Data Collection Tests ────────────────────────────


class TestCollectData:
    """Tests for _collect_data — platform-agnostic data gathering."""

    @pytest.mark.asyncio
    async def test_single_metric_single_asset(self) -> None:
        adapter = _make_adapter()
        buckets = await _collect_data(adapter, days=7)

        assert "energy" in buckets
        assert len(buckets["energy"]) == 2
        rec = buckets["energy"][0]
        assert rec["metric_name"] == "energy_per_unit"
        assert rec["asset_id"] == "Line-1"
        assert rec["value"] == 2.51

    @pytest.mark.asyncio
    async def test_multiple_categories(self) -> None:
        adapter = _make_adapter(
            metrics=[
                CanonicalMetric.ENERGY_PER_UNIT,
                CanonicalMetric.SCRAP_RATE,
                CanonicalMetric.OEE,
                CanonicalMetric.CO2_PER_UNIT,
                CanonicalMetric.SUPPLIER_LEAD_TIME,
            ],
            points=[
                DataPoint(
                    timestamp=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
                    value=1.0,
                ),
            ],
        )
        buckets = await _collect_data(adapter, days=7)

        assert len(buckets["energy"]) == 1
        assert len(buckets["material"]) == 1
        assert len(buckets["production"]) == 1
        assert len(buckets["carbon"]) == 1
        assert len(buckets["supplier"]) == 1

    @pytest.mark.asyncio
    async def test_ids_are_sequential(self) -> None:
        adapter = _make_adapter(
            points=[
                DataPoint(
                    timestamp=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
                    value=1.0,
                ),
                DataPoint(
                    timestamp=datetime(2026, 4, 1, 10, 15, tzinfo=timezone.utc),
                    value=2.0,
                ),
            ],
        )
        buckets = await _collect_data(adapter, days=7)

        ids = [r["id"] for r in buckets["energy"]]
        assert ids == [1, 2]

    @pytest.mark.asyncio
    async def test_no_assets_returns_empty(self) -> None:
        adapter = _make_adapter(assets=[])
        buckets = await _collect_data(adapter, days=7)

        assert buckets == {}

    @pytest.mark.asyncio
    async def test_adapter_error_skips_metric(self) -> None:
        adapter = _make_adapter(raw_data_error=RuntimeError("API timeout"))
        buckets = await _collect_data(adapter, days=7)

        assert buckets.get("energy", []) == []

    @pytest.mark.asyncio
    async def test_timestamp_format_matches_prevention(self) -> None:
        adapter = _make_adapter()
        buckets = await _collect_data(adapter, days=7)

        ts = buckets["energy"][0]["timestamp"]
        assert ts == "2026-04-01T10:00:00.000Z"

    @pytest.mark.asyncio
    async def test_multiple_assets(self) -> None:
        adapter = _make_adapter(
            assets=[
                Asset(asset_id="L-1", display_name="L1", asset_type="line"),
                Asset(asset_id="L-2", display_name="L2", asset_type="line"),
            ],
            points=[
                DataPoint(
                    timestamp=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
                    value=5.0,
                ),
            ],
        )
        buckets = await _collect_data(adapter, days=7)

        # 1 metric × 2 assets × 1 point each = 2 records
        assert len(buckets["energy"]) == 2
        asset_ids = {r["asset_id"] for r in buckets["energy"]}
        assert asset_ids == {"L-1", "L-2"}

    @pytest.mark.asyncio
    async def test_skips_assets_without_metric_resource_for_resource_templates(self) -> None:
        adapter = _make_adapter(
            assets=[
                Asset(asset_id="Line-1", display_name="Line 1", asset_type="line"),
                Asset(asset_id="Meter-1", display_name="Meter 1", asset_type="sensor"),
            ],
            points=[
                DataPoint(
                    timestamp=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
                    value=5.0,
                ),
            ],
        )
        adapter._lookup_metric_mapping_by_name.return_value = {
            "endpoint": "/api/resource/{resource_id}/values",
        }
        adapter._resolve_metric_resource_id.side_effect = (
            lambda metric, asset_id: "rid-line-1" if asset_id == "Line-1" else ""
        )

        buckets = await _collect_data(adapter, days=7)

        assert len(buckets["energy"]) == 1
        assert buckets["energy"][0]["asset_id"] == "Line-1"


class TestResourceLinkHelpers:
    """Tests for exporter asset/metric link filtering."""

    def test_requires_metric_resource_detects_endpoint_placeholder(self) -> None:
        adapter = MagicMock()
        adapter._lookup_metric_mapping_by_name.return_value = {
            "endpoint": "/api/resource/{resource_id}/values",
        }

        assert _requires_metric_resource(adapter, "energy_per_unit") is True

    def test_requires_metric_resource_ignores_non_resource_template(self) -> None:
        adapter = MagicMock()
        adapter._lookup_metric_mapping_by_name.return_value = {
            "endpoint": "/api/assets/{asset_id}/values",
        }

        assert _requires_metric_resource(adapter, "energy_per_unit") is False

    def test_has_metric_resource_uses_adapter_resolver(self) -> None:
        adapter = MagicMock()
        adapter._resolve_metric_resource_id.return_value = "rid-123"

        assert _has_metric_resource(adapter, "energy_per_unit", "Line-1") is True

# ── File Writing Tests ───────────────────────────────


class TestWriteFiles:
    """Tests for _write_files — JSON output."""

    def test_writes_all_five_category_files(self, tmp_path: Path) -> None:
        buckets = {cat: [] for cat in _CATEGORY_FILES}
        buckets["energy"].append({
            "id": 1, "metric_name": "energy_per_unit",
            "asset_id": "X", "timestamp": "2026-04-01T00:00:00.000Z",
            "value": 1.0, "unit": "",
        })
        total = _write_files(buckets, tmp_path)

        for filename in _CATEGORY_FILES.values():
            assert (tmp_path / filename).exists()
        assert (tmp_path / _MANIFEST_FILENAME).exists()
        assert total == 1

    def test_json_is_valid(self, tmp_path: Path) -> None:
        buckets = {
            "energy": [{"id": 1, "metric_name": "e", "asset_id": "a",
                         "timestamp": "t", "value": 1.0, "unit": ""}],
            "production": [],
            "material": [],
            "carbon": [],
            "supplier": [],
        }
        _write_files(buckets, tmp_path)

        data = json.loads((tmp_path / "energy_metrics.json").read_text())
        assert isinstance(data, list)
        assert data[0]["id"] == 1

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir"
        buckets = {cat: [] for cat in _CATEGORY_FILES}
        _write_files(buckets, target)

        assert target.is_dir()

    def test_empty_buckets_write_empty_arrays(self, tmp_path: Path) -> None:
        buckets = {cat: [] for cat in _CATEGORY_FILES}
        total = _write_files(buckets, tmp_path)

        assert total == 0
        for filename in _CATEGORY_FILES.values():
            data = json.loads((tmp_path / filename).read_text())
            assert data == []

    def test_manifest_contains_record_counts(self, tmp_path: Path) -> None:
        buckets = {cat: [] for cat in _CATEGORY_FILES}
        buckets["energy"].append({
            "id": 1,
            "metric_name": "energy_per_unit",
            "asset_id": "Line-1",
            "timestamp": "2026-04-01T00:00:00.000Z",
            "value": 1.0,
            "unit": "kWh/unit",
        })

        _write_files(buckets, tmp_path, platform="generic_rest", days=7)

        manifest = json.loads((tmp_path / _MANIFEST_FILENAME).read_text())
        assert manifest["platform"] == "generic_rest"
        assert manifest["days"] == 7
        assert manifest["total_records"] == 1
        assert manifest["files"]["energy"]["records"] == 1
