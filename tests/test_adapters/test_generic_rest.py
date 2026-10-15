"""Unit tests for GenericRestAdapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses

from skill.adapters.generic_rest import GenericRestAdapter
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import ComparisonResult, KPIResult, TrendResult


class _StubSettingsService:
    """Minimal settings stub exposing metric mapping APIs."""

    def __init__(
        self,
        mappings: dict[str, dict] | None = None,
        asset_mappings: dict[str, dict] | None = None,
    ) -> None:
        self._mappings = mappings or {}
        self._asset_mappings = asset_mappings or {}

    def get_metric_mapping(
        self,
        metric_name: str,
        profile: str | None = None,
    ) -> dict | None:
        return self._mappings.get(metric_name)

    def list_metric_mappings(
        self,
        profile: str | None = None,
    ) -> dict[str, dict]:
        return dict(self._mappings)

    def get_asset_mappings(self, profile: str | None = None) -> dict[str, dict]:
        _ = profile
        return dict(self._asset_mappings)


@pytest.fixture
def period() -> TimePeriod:
    """Provide a reusable period fixture."""
    return TimePeriod.today()


def _build_adapter(mappings: dict[str, dict], auth_type: str = "bearer") -> GenericRestAdapter:
    return GenericRestAdapter(
        api_url="https://api.example.com",
        api_key="secret-token",
        auth_type=auth_type,
        settings_service=_StubSettingsService(mappings),
        profile_name="custom",
    )


def _build_asset_adapter(asset_mappings: dict[str, dict]) -> GenericRestAdapter:
    return GenericRestAdapter(
        api_url="https://api.example.com",
        api_key="secret-token",
        auth_type="bearer",
        settings_service=_StubSettingsService({}, asset_mappings=asset_mappings),
        profile_name="custom",
    )


def test_build_request_url_deduplicates_base_api_path() -> None:
    """A base URL ending in /api must not produce /api/api endpoints."""
    adapter = GenericRestAdapter(
        api_url="https://api.example.com/api",
        api_key="secret-token",
    )

    assert (
        adapter._build_request_url(
            "/api/u/measurement/metric/resource/resource-1/values",
        )
        == "https://api.example.com/api/u/measurement/metric/resource/resource-1/values"
    )


def test_build_request_url_preserves_distinct_base_path() -> None:
    """Unrelated endpoint paths should still be appended to the configured base."""
    adapter = GenericRestAdapter(
        api_url="https://api.example.com/platform",
        api_key="secret-token",
    )

    assert (
        adapter._build_request_url("/api/metrics")
        == "https://api.example.com/platform/api/metrics"
    )


@pytest.mark.asyncio
async def test_get_kpi_valid_mapping_returns_kpi_result(period: TimePeriod) -> None:
    """Mapped KPI endpoint/json_path returns KPIResult."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={"records": [{"value": 3.14}]})

    result = await adapter.get_kpi(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="line-1",
        period=period,
    )

    assert isinstance(result, KPIResult)
    assert result.value == pytest.approx(3.14)
    assert result.unit == "kWh/unit"


@pytest.mark.asyncio
async def test_reneryo_period_paginates_and_aggregates() -> None:
    """Every Reneryo page contributes to the period average and provenance."""
    adapter = _build_adapter({
        "oee": {
            "endpoint": (
                "/u/measurement/metric/resource/{asset_id}/values"
                "?period=RAW&datetimeMin={start_date}&datetimeMax={end_date}&count=1&page=1"
            ),
            "json_path": "$.records[0].value",
            "unit": "%",
            "page_size": 2,
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(side_effect=[
        {
            "recordCount": 3,
            "records": [
                {"value": 60.0, "datetime": "2026-07-01T00:00:00Z"},
                {"value": 90.0, "datetime": "2026-07-02T00:00:00Z"},
            ],
        },
        {
            "recordCount": 3,
            "records": [
                {"value": 75.0, "datetime": "2026-07-03T00:00:00Z"},
            ],
        },
    ])

    result = await adapter.get_kpi(
        metric=CanonicalMetric.OEE,
        asset_id="line-1",
        period=TimePeriod.from_natural_language("July 2026"),
    )

    assert result.value == pytest.approx(75.0)
    assert result.aggregation == "average"
    assert result.sample_count == 3
    assert result.source_observed_at.isoformat() == "2026-07-03T00:00:00+00:00"
    assert result.coverage_status == "complete"
    assert adapter._retry_fetch.await_count == 2
    assert adapter._retry_fetch.await_args_list[0].args[1]["count"] == "2"
    assert adapter._retry_fetch.await_args_list[1].args[1]["page"] == "2"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metric", "expected_aggregation", "expected_value"),
    [
        (CanonicalMetric.ENERGY_TOTAL, "sum", 9.0),
        (CanonicalMetric.PEAK_DEMAND, "max", 5.0),
        (CanonicalMetric.SCRAP_RATE, "average", 3.0),
    ],
)
async def test_canonical_period_aggregation_defaults(
    metric: CanonicalMetric,
    expected_aggregation: str,
    expected_value: float,
) -> None:
    adapter = _build_adapter({
        metric.value: {
            "endpoint": "/values",
            "json_path": "$.records[0].value",
            "unit": metric.default_unit,
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={
        "recordCount": 3,
        "records": [
            {"value": 1.0, "datetime": "2026-07-01T00:00:00Z"},
            {"value": 3.0, "datetime": "2026-07-02T00:00:00Z"},
            {"value": 5.0, "datetime": "2026-07-03T00:00:00Z"},
        ],
    })

    result = await adapter.get_kpi(
        metric=metric,
        asset_id="line-1",
        period=TimePeriod.from_natural_language("July 2026"),
    )

    assert result.aggregation == expected_aggregation
    assert result.value == pytest.approx(expected_value)


@pytest.mark.asyncio
async def test_implicit_latest_uses_descending_single_observation() -> None:
    adapter = _build_adapter({
        "oee": {
            "endpoint": "/values?count=100&page=1",
            "json_path": "$.records[0].value",
            "unit": "%",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={
        "recordCount": 1000,
        "records": [{"value": 88.0, "datetime": "2026-08-14T09:00:00Z"}],
    })

    result = await adapter.get_kpi(
        metric=CanonicalMetric.OEE,
        asset_id="line-1",
        period=TimePeriod.latest(),
    )

    params = adapter._retry_fetch.await_args.args[1]
    assert params["count"] == "1"
    assert params["descending"] == "true"
    assert result.value == pytest.approx(88.0)
    assert result.aggregation == "latest"


@pytest.mark.asyncio
async def test_get_kpi_missing_mapping_raises_adapter_error(period: TimePeriod) -> None:
    """Unmapped metric returns clear mapping error."""
    adapter = _build_adapter({})
    adapter._session = object()

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="line-1",
            period=period,
        )

    assert exc_info.value.code == "GENERIC_REST_MAPPING_NOT_FOUND"
    assert "No mapping configured" in exc_info.value.message


@pytest.mark.asyncio
async def test_get_kpi_uses_auto_mapping_from_metric_resources(period: TimePeriod) -> None:
    """Imported metric_resources should drive KPI calls without manual mapping rows."""
    adapter = _build_asset_adapter(
        {
            "line-1": {
                "display_name": "Line 1",
                "asset_type": "line",
                "metric_resources": {
                    "energy_per_unit": "resource-123",
                },
            },
        },
    )
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={"records": [{"value": 2.47}]})

    result = await adapter.get_kpi(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="Line-1",
        period=period,
    )

    assert result.value == pytest.approx(2.47)
    call_endpoint = adapter._retry_fetch.await_args.args[0]
    call_params = adapter._retry_fetch.await_args.args[1]
    assert call_endpoint == "/api/u/measurement/metric/resource/resource-123/values"
    assert call_params["period"] == "RAW"


@pytest.mark.asyncio
async def test_get_kpi_energy_total_uses_native_seu_binding(period: TimePeriod) -> None:
    """Energy-only SEU assets should resolve energy_total via native binding."""
    seu_id = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
    adapter = _build_asset_adapter(
        {
            seu_id: {
                "display_name": "Seu",
                "asset_type": "machine",
                "mapping_source": "live_discovery",
                "capability_mode": "energy_only",
                "native_metric_bindings": {
                    "energy_total": {
                        "strategy": "asset_consumption_total",
                        "unit": "kWh",
                        "trend_supported": False,
                        "compare_supported": False,
                    },
                },
            },
        },
    )
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(
        return_value={
            "records": [
                {"id": seu_id, "name": "Seu", "consumption": 8654.14},
            ],
        },
    )

    result = await adapter.get_kpi(
        metric=CanonicalMetric.ENERGY_TOTAL,
        asset_id=seu_id,
        period=period,
    )

    assert result.metric == CanonicalMetric.ENERGY_TOTAL
    assert result.value == pytest.approx(8654.14)
    assert result.unit == "kWh"
    call_endpoint = adapter._retry_fetch.await_args.args[0]
    assert call_endpoint == "/api/u/measurement/seu/item"


@pytest.mark.asyncio
async def test_get_kpi_energy_total_uses_native_metric_item_last_value(
) -> None:
    """Counter meter assets can resolve energy_total from metric item lastValue."""
    resource_id = "525c5133-80eb-4c95-8f0c-06e56d2854fe"
    adapter = _build_asset_adapter(
        {
            "Electric-Main-Meter": {
                "display_name": "Electric Main Meter",
                "asset_type": "machine",
                "metric_resources": {"energy_total": resource_id},
                "native_metric_bindings": {
                    "energy_total": {
                        "strategy": "metric_item_last_value",
                        "unit": "kWh",
                    },
                },
            },
        },
    )
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(
        return_value={
            "lastValue": 86761.2343174361,
            "name": "Main Electric Metric",
        },
    )

    result = await adapter.get_kpi(
        metric=CanonicalMetric.ENERGY_TOTAL,
        asset_id="Electric Main Meter",
        period=TimePeriod.latest(),
    )

    assert result.metric == CanonicalMetric.ENERGY_TOTAL
    assert result.value == pytest.approx(86761.2343174361)
    assert result.unit == "kWh"
    call_endpoint = adapter._retry_fetch.await_args.args[0]
    assert call_endpoint == (
        "/api/u/measurement/metric/item/"
        "525c5133-80eb-4c95-8f0c-06e56d2854fe"
    )
    assert adapter._retry_fetch.await_args.args[1] is None


@pytest.mark.asyncio
async def test_native_last_value_rejects_historical_period(period: TimePeriod) -> None:
    """A current counter must never be presented as a historical period total."""
    adapter = _build_asset_adapter(
        {
            "Electric-Main-Meter": {
                "display_name": "Electric Main Meter",
                "metric_resources": {"energy_total": "resource-1"},
                "native_metric_bindings": {
                    "energy_total": {"strategy": "metric_item_last_value"},
                },
            },
        },
    )
    adapter._session = object()

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_kpi(
            CanonicalMetric.ENERGY_TOTAL,
            "Electric-Main-Meter",
            period,
        )

    assert exc_info.value.code == "GENERIC_REST_PERIOD_UNSUPPORTED"
    assert "latest counter value" in exc_info.value.user_message


@pytest.mark.asyncio
async def test_get_kpi_non_energy_metric_on_energy_only_asset_raises_unavailable(
    period: TimePeriod,
) -> None:
    """Energy-only SEU assets should reject non-native KPI metrics cleanly."""
    seu_id = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
    adapter = _build_asset_adapter(
        {
            seu_id: {
                "display_name": "Seu",
                "asset_type": "machine",
                "capability_mode": "energy_only",
                "native_metric_bindings": {
                    "energy_total": {"strategy": "asset_consumption_total"},
                },
            },
        },
    )
    adapter._session = object()

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id=seu_id,
            period=period,
        )

    assert exc_info.value.code == "ASSET_METRIC_UNAVAILABLE"
    assert "Available metric for this asset" in exc_info.value.user_message


@pytest.mark.asyncio
async def test_get_kpi_energy_total_on_energy_only_asset_uses_manual_mapping(
    period: TimePeriod,
) -> None:
    """Energy-only assets may use a generic mapping for their allowed KPI."""
    adapter = GenericRestAdapter(
        api_url="https://api.example.com",
        api_key="secret-token",
        settings_service=_StubSettingsService(
            {
                "energy_total": {
                    "endpoint": "/channels/consumption-energy",
                    "json_path": "$.value",
                    "unit": "Wh",
                },
            },
            asset_mappings={
                "edge-1": {
                    "display_name": "Energy Edge",
                    "capability_mode": "energy_only",
                },
            },
        ),
        profile_name="custom",
    )
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={"value": 54})

    result = await adapter.get_kpi(
        metric=CanonicalMetric.ENERGY_TOTAL,
        asset_id="edge-1",
        period=period,
    )

    assert result.value == pytest.approx(54)
    assert result.unit == "Wh"
    assert adapter._retry_fetch.await_args.args[0] == "/channels/consumption-energy"


@pytest.mark.asyncio
async def test_get_trend_energy_only_asset_raises_unavailable(period: TimePeriod) -> None:
    """Energy-only SEU assets should not expose trend endpoint in V1."""
    seu_id = "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4"
    adapter = _build_asset_adapter(
        {
            seu_id: {
                "display_name": "Seu",
                "asset_type": "machine",
                "capability_mode": "energy_only",
                "native_metric_bindings": {
                    "energy_total": {"strategy": "asset_consumption_total"},
                },
            },
        },
    )
    adapter._session = object()

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_trend(
            metric=CanonicalMetric.ENERGY_TOTAL,
            asset_id=seu_id,
            period=period,
        )

    assert exc_info.value.code == "ASSET_METRIC_UNAVAILABLE"


@pytest.mark.asyncio
async def test_get_kpi_invalid_json_path_raises_adapter_error(period: TimePeriod) -> None:
    """Missing json_path target raises mapping invalid error."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "json_path": "$.missing.value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={"records": [{"value": 2.0}]})

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="line-1",
            period=period,
        )

    assert exc_info.value.code == "GENERIC_REST_MAPPING_INVALID"


@pytest.mark.asyncio
async def test_get_kpi_non_numeric_value_raises_adapter_error(period: TimePeriod) -> None:
    """Non-numeric mapped values are rejected."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={"records": [{"value": "n/a"}]})

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="line-1",
            period=period,
        )

    assert exc_info.value.code == "GENERIC_REST_MAPPING_INVALID"


@pytest.mark.asyncio
async def test_get_kpi_unreachable_endpoint_raises_adapter_error(period: TimePeriod) -> None:
    """Transport failures bubble up as adapter errors."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(side_effect=AdapterError(
        message="Connection failed",
        code="GENERIC_REST_CONNECTION_FAILED",
        platform="generic_rest",
    ))

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="line-1",
            period=period,
        )

    assert exc_info.value.code == "GENERIC_REST_CONNECTION_FAILED"


@pytest.mark.asyncio
async def test_compare_two_assets_builds_comparison_result(period: TimePeriod) -> None:
    """Compare builds ranked items from per-asset mapped fetches."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi/{asset_id}",
            "json_path": "$.value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(side_effect=[
        {"value": 12.0},
        {"value": 10.0},
    ])

    result = await adapter.compare(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_ids=["asset-a", "asset-b"],
        period=period,
    )

    assert isinstance(result, ComparisonResult)
    assert len(result.items) == 2
    assert result.winner_id == "asset-b"
    assert result.difference == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_get_trend_returns_trend_result_with_data_points(period: TimePeriod) -> None:
    """Trend endpoint payload is converted into TrendResult points."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/trend",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={
        "records": [
            {"value": 10.0, "datetime": "2026-02-23T00:00:00Z"},
            {"value": 12.0, "datetime": "2026-02-24T00:00:00Z"},
        ],
    })

    result = await adapter.get_trend(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="asset-a",
        period=period,
        granularity="daily",
    )

    assert isinstance(result, TrendResult)
    assert len(result.data_points) == 2
    assert result.direction == "up"


@pytest.mark.asyncio
async def test_get_trend_uses_trend_endpoint_override(period: TimePeriod) -> None:
    """trend_endpoint mapping override is preferred when configured."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "trend_endpoint": "/trend-override",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    adapter._retry_fetch = AsyncMock(return_value={
        "records": [
            {"value": 9.0, "datetime": "2026-02-23T00:00:00Z"},
            {"value": 9.5, "datetime": "2026-02-24T00:00:00Z"},
        ],
    })

    await adapter.get_trend(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="asset-a",
        period=period,
    )

    call_endpoint = adapter._retry_fetch.await_args.args[0]
    assert call_endpoint == "/trend-override"


@pytest.mark.asyncio
async def test_get_trend_supports_epoch_templates_and_millisecond_timestamps(
    period: TimePeriod,
) -> None:
    """Generic trend mappings support numeric time windows and ``ts`` points."""
    start = period.start.replace(tzinfo=timezone.utc) if period.start.tzinfo is None else period.start
    end = period.end.replace(tzinfo=timezone.utc) if period.end.tzinfo is None else period.end
    start_ms = int(start.timestamp()) * 1000
    end_ms = int(end.timestamp()) * 1000

    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "trend_endpoint": (
                "/telemetry?from={start_epoch_ms}&to={end_epoch_ms}"
            ),
            "trend_json_path": "$.series",
            "json_path": "$.series[0].value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    # Newest-first is common; adapter output must still be chronological.
    adapter._retry_fetch = AsyncMock(return_value={
        "series": [
            {"ts": end_ms, "value": "2.0"},
            {"ts": start_ms, "value": "1.0"},
        ],
    })

    result = await adapter.get_trend(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="asset-a",
        period=period,
    )

    call_endpoint, call_params = adapter._retry_fetch.await_args.args
    assert call_endpoint == "/telemetry"
    assert call_params == {"from": str(start_ms), "to": str(end_ms)}
    assert [point.value for point in result.data_points] == [1.0, 2.0]
    assert [point.timestamp for point in result.data_points] == [
        datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc),
        datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc),
    ]
    assert result.direction == "up"


@pytest.mark.asyncio
async def test_get_raw_data_returns_json(period: TimePeriod) -> None:
    """Raw data path should return payload without transformation."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/raw",
            "json_path": "$.value",
            "unit": "kWh/unit",
        },
    })
    adapter._session = object()
    payload = {"records": [{"value": 1.1}], "meta": {"source": "raw"}}
    adapter._retry_fetch = AsyncMock(return_value=payload)

    result = await adapter.get_raw_data(
        metric=CanonicalMetric.ENERGY_PER_UNIT,
        asset_id="asset-a",
        period=period,
    )

    assert result == payload


def test_supports_capability_true_for_mapped_metric() -> None:
    """Mapped metric capability returns True."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "json_path": "$.value",
            "unit": "kWh/unit",
        },
    })

    assert adapter.supports_capability("energy_per_unit") is True


def test_supports_capability_false_for_unmapped_metric() -> None:
    """Unmapped metric capability returns False."""
    adapter = _build_adapter({
        "energy_total": {
            "endpoint": "/kpi",
            "json_path": "$.value",
            "unit": "kWh",
        },
    })

    assert adapter.supports_capability("energy_per_unit") is False


def test_supports_capability_true_for_native_energy_only_metric() -> None:
    """Native asset bindings should expose supported metric capabilities."""
    adapter = _build_asset_adapter(
        {
            "seu-1": {
                "display_name": "Seu",
                "capability_mode": "energy_only",
                "native_metric_bindings": {
                    "energy_total": {"strategy": "asset_consumption_total"},
                },
            },
        },
    )

    assert adapter.supports_capability("energy_total") is True
    assert CanonicalMetric.ENERGY_TOTAL in adapter.get_supported_metrics()


def test_supports_asset_discovery_returns_true_with_api_url() -> None:
    """Generic REST adapter exposes best-effort discovery when URL exists."""
    adapter = _build_adapter({})
    assert adapter.supports_asset_discovery() is True


@pytest.mark.asyncio
async def test_list_assets_returns_assets_from_saved_mappings() -> None:
    """Asset list should be derived from SettingsService asset mappings."""
    adapter = _build_asset_adapter(
        {
            "line-2": {"display_name": "Line 2", "asset_type": "line"},
            "line-1": {"display_name": "Line 1", "asset_type": "line"},
        },
    )

    assets = await adapter.list_assets()

    assert [asset.asset_id for asset in assets] == ["line-1", "line-2"]
    assert assets[0].display_name == "Line 1"
    assert assets[0].asset_type == "line"


@pytest.mark.asyncio
async def test_list_assets_returns_empty_without_saved_mappings() -> None:
    """No saved mappings should yield an empty asset list."""
    adapter = _build_asset_adapter({})
    assets = await adapter.list_assets()
    assert assets == []


@pytest.mark.asyncio
async def test_list_assets_discovers_from_api_when_no_saved_mappings() -> None:
    """Live discovery should hydrate wizard suggestions on first run."""
    adapter = _build_asset_adapter({})

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        mocked.get(
            "https://api.example.com/api/u/measurement/seu/names?count=100",
            status=200,
            payload={
                "records": [
                    {
                        "id": "seu-1",
                        "name": "SEU Alpha",
                        "energyResource": "ELECTRIC",
                    },
                ],
            },
        )
        await adapter.initialize()
        assets = await adapter.list_assets()
        await adapter.shutdown()

    assert [asset.asset_id for asset in assets] == ["seu-1"]
    assert assets[0].display_name == "SEU Alpha"


@pytest.mark.asyncio
async def test_list_assets_prefers_seu_item_discovery_with_uuid_ids() -> None:
    """SEU item discovery should preserve real UUID-based asset IDs."""
    adapter = _build_asset_adapter({})

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        mocked.get(
            "https://api.example.com/api/u/measurement/seu/item?datetimeMin=2021-02-01T00:00:00.000Z&datetimeMax=2027-02-01T00:00:00.000Z",
            status=200,
            payload={
                "records": [
                    {
                        "id": "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4",
                        "name": "Seu",
                        "energyResource": "ELECTRIC",
                    },
                    {
                        "id": "8e7a03ca-2992-4ca1-aea4-2cdcfc911c5d",
                        "name": "Seu 4 for reporting",
                        "energyResource": "ELECTRIC",
                    },
                ],
            },
        )
        await adapter.initialize()
        assets = await adapter.list_assets()
        await adapter.shutdown()

    assert [asset.asset_id for asset in assets] == [
        "620aa6a4-c1b3-431b-8bec-dc82ac0cd6b4",
        "8e7a03ca-2992-4ca1-aea4-2cdcfc911c5d",
    ]
    assert assets[0].display_name == "Seu"
    assert assets[1].display_name == "Seu 4 for reporting"


@pytest.mark.asyncio
async def test_list_assets_ignores_plain_name_discovery_records() -> None:
    """Plain-string discovery responses should not be converted to fake assets."""
    adapter = _build_asset_adapter({})

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        mocked.get(
            "https://api.example.com/api/u/measurement/seu/item?datetimeMin=2021-02-01T00:00:00.000Z&datetimeMax=2027-02-01T00:00:00.000Z",
            status=404,
            payload={"detail": "not found"},
        )
        mocked.get(
            "https://api.example.com/u/measurement/seu/item?datetimeMin=2021-02-01T00:00:00.000Z&datetimeMax=2027-02-01T00:00:00.000Z",
            status=404,
            payload={"detail": "not found"},
        )
        mocked.get(
            "https://api.example.com/api/u/measurement/seu/names?count=100",
            status=200,
            payload={"records": ["Line-1", "Line-2", "seu"]},
        )
        await adapter.initialize()
        assets = await adapter.list_assets()
        await adapter.shutdown()

    assert assets == []


@pytest.mark.asyncio
async def test_initialize_validates_base_url(period: TimePeriod) -> None:
    """initialize() should succeed when base URL probe is reachable."""
    adapter = _build_adapter({
        "energy_per_unit": {
            "endpoint": "/kpi",
            "json_path": "$.value",
            "unit": "kWh/unit",
        },
    })

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        await adapter.initialize()

    assert adapter._session is not None
    await adapter.shutdown()


@pytest.mark.asyncio
async def test_initialize_unreachable_endpoint_raises_adapter_error() -> None:
    """initialize() should fail when probe returns 5xx."""
    adapter = _build_adapter({})

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=503)
        with pytest.raises(AdapterError) as exc_info:
            await adapter.initialize()

    assert exc_info.value.code == "GENERIC_REST_INIT_FAILED"


@pytest.mark.asyncio
async def test_initialize_uses_configured_read_endpoint_when_base_returns_5xx() -> None:
    """A profile probe endpoint should support APIs without a healthy root."""
    adapter = _build_adapter({})
    adapter._extra_settings["connection_test_endpoint"] = "/channels/total"

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=500)
        mocked.get("https://api.example.com/channels/total", status=200)
        await adapter.initialize()

    assert adapter._session is not None
    await adapter.shutdown()


@pytest.mark.asyncio
async def test_shutdown_closes_session() -> None:
    """shutdown() should clear session after initialize()."""
    adapter = _build_adapter({})

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        await adapter.initialize()

    assert adapter._session is not None
    await adapter.shutdown()
    assert adapter._session is None


def test_bearer_auth_sends_header() -> None:
    """Bearer auth should populate Authorization header."""
    adapter = _build_adapter({}, auth_type="bearer")
    adapter._api_key = "abc123"

    assert adapter._build_auth_headers() == {"Authorization": "Bearer abc123"}


def test_basic_auth_sends_encoded_credentials() -> None:
    """Basic auth should encode the configured username:password value."""
    adapter = _build_adapter({}, auth_type="basic")
    adapter._api_key = "x:admin"

    assert adapter._build_auth_headers() == {
        "Authorization": "Basic eDphZG1pbg==",
    }


def test_custom_header_auth_uses_configured_name_and_prefix() -> None:
    """Custom-header auth should support platform API-key conventions."""
    adapter = GenericRestAdapter(
        api_url="https://api.example.com",
        api_key="tb_example",
        auth_type="custom_header",
        extra_settings={
            "auth_header_name": "X-Authorization",
            "auth_header_prefix": "ApiKey",
        },
    )

    assert adapter._build_auth_headers() == {
        "X-Authorization": "ApiKey tb_example",
    }


def test_custom_header_auth_rejects_invalid_header_name() -> None:
    """Custom-header auth must reject header-injection characters."""
    adapter = GenericRestAdapter(
        api_url="https://api.example.com",
        api_key="secret",
        auth_type="custom_header",
        extra_settings={"auth_header_name": "X-Bad\r\nHeader"},
    )

    with pytest.raises(AdapterError, match="auth_header_name"):
        adapter._build_auth_headers()


def test_cookie_auth_sends_header() -> None:
    """Cookie auth should normalize to Cookie header."""
    adapter = _build_adapter({}, auth_type="cookie")
    adapter._api_key = "session-id"

    assert adapter._build_auth_headers() == {"Cookie": "S=session-id"}


def test_cookie_auth_uuid_token_sends_dual_cookie_names() -> None:
    """Bare UUID cookie token should include JSESSIONID and S variants."""
    adapter = _build_adapter({}, auth_type="cookie")
    token = "4efd58f5-c712-4c0d-b329-001122334455"
    adapter._api_key = token

    assert adapter._build_auth_headers() == {
        "Cookie": f"JSESSIONID={token}; S={token}",
    }


def test_none_auth_sends_no_headers() -> None:
    """No-auth mode should not send auth headers."""
    adapter = _build_adapter({}, auth_type="none")
    adapter._api_key = "unused"

    assert adapter._build_auth_headers() == {}


@pytest.mark.asyncio
async def test_test_connection_cookie_auth_rejected_returns_failure() -> None:
    """401 on auth probe endpoint should fail connection test."""
    adapter = _build_adapter({}, auth_type="cookie")
    adapter._api_key = "invalid-cookie"

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        mocked.get(
            "https://api.example.com/api/u/measurement/seu/names?count=1",
            status=401,
            payload={"detail": "unauthorized"},
        )
        result = await adapter.test_connection()

    assert result.success is False
    assert result.error_code == "GENERIC_REST_AUTH_FAILED"
    assert "Authentication failed" in result.message


@pytest.mark.asyncio
async def test_test_connection_cookie_auth_accepted_returns_success() -> None:
    """200 on auth probe endpoint should pass connection test."""
    adapter = _build_adapter({}, auth_type="cookie")
    adapter._api_key = "valid-cookie"

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        mocked.get(
            "https://api.example.com/api/u/measurement/seu/names?count=1",
            status=200,
            payload={"records": []},
        )
        result = await adapter.test_connection()

    assert result.success is True
    assert result.error_code == ""


@pytest.mark.asyncio
async def test_connection_probe_preserves_initialized_runtime_session() -> None:
    """Status probes must not shut down the skill's shared adapter session."""
    adapter = _build_adapter({}, auth_type="cookie")
    adapter._api_key = "valid-cookie"

    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        await adapter.initialize()
        session = adapter._session
        mocked.get(
            "https://api.example.com/api/u/measurement/seu/names?count=1",
            status=200,
            payload={"records": []},
        )
        result = await adapter.test_connection()

    assert result.success is True
    assert adapter._session is session
    assert adapter._session is not None and not adapter._session.closed
    await adapter.shutdown()


@pytest.mark.asyncio
async def test_get_kpi_rejects_unbound_metric_on_natively_bound_asset(
    period: TimePeriod,
) -> None:
    """Asset with native bindings but no capability_mode tag still rejects unbound metrics."""
    adapter = _build_asset_adapter(
        {
            "electric_main_meter": {
                "display_name": "Electric Main Meter",
                "native_metric_bindings": {
                    "energy_total": {
                        "strategy": "asset_consumption_total",
                        "unit": "kWh",
                    },
                },
            },
        },
    )
    adapter._session = object()

    with pytest.raises(AdapterError) as exc_info:
        await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="electric_main_meter",
            period=period,
        )

    assert exc_info.value.code == "ASSET_METRIC_UNAVAILABLE"
    assert "energy per unit" in exc_info.value.user_message.lower()
    assert "total energy" in exc_info.value.user_message.lower()


def test_get_natively_bound_metrics_empty_when_no_bindings() -> None:
    """Assets without native_metric_bindings return an empty list."""
    adapter = _build_asset_adapter(
        {"line_1": {"display_name": "Line 1"}},
    )

    assert adapter._get_natively_bound_metrics("line_1") == []


def test_get_natively_bound_metrics_returns_bound_metrics() -> None:
    """Assets with native_metric_bindings return their bound canonical metrics."""
    adapter = _build_asset_adapter(
        {
            "meter": {
                "display_name": "Meter",
                "native_metric_bindings": {
                    "energy_total": {"strategy": "asset_consumption_total"},
                },
            },
        },
    )

    result = adapter._get_natively_bound_metrics("meter")

    assert result == [CanonicalMetric.ENERGY_TOTAL]


@pytest.mark.asyncio
async def test_requested_read_recovers_after_failed_startup_probe(period):
    """An outage must not permanently strand the configured adapter."""
    adapter = _build_adapter({"oee": {"endpoint": "/kpi", "json_path": "$.value", "unit": "%"}})
    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=503)
        with pytest.raises(AdapterError):
            await adapter.initialize()
        assert adapter._session is None
        mocked.head("https://api.example.com", status=200)
        mocked.get("https://api.example.com/kpi", payload={"value": 75})
        result = await adapter.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        assert result.value == 75 and result.asset_id == "Line-1"
        assert result.period == period
    await adapter.shutdown()


@pytest.mark.asyncio
async def test_disconnect_is_typed_and_next_read_can_recover(period):
    """A dropped response must use the same error boundary as refusal."""
    import aiohttp

    adapter = _build_adapter({"oee": {"endpoint": "/kpi", "json_path": "$.value", "unit": "%"}})
    with aioresponses() as mocked:
        mocked.head("https://api.example.com", status=200)
        await adapter.initialize()
        mocked.get("https://api.example.com/kpi", exception=aiohttp.ServerDisconnectedError())
        with pytest.raises(AdapterError) as error:
            await adapter.get_kpi(CanonicalMetric.OEE, "Line-1", period)
        assert error.value.code == "GENERIC_REST_CONNECTION_FAILED"
        mocked.get("https://api.example.com/kpi", payload={"value": 80})
        assert (await adapter.get_kpi(CanonicalMetric.OEE, "Line-1", period)).value == 80
    await adapter.shutdown()
