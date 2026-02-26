"""Unit tests for GenericRestAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses

from skill.adapters.generic_rest import GenericRestAdapter
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import ComparisonResult, KPIResult, TrendResult


class _StubSettingsService:
    """Minimal settings stub exposing metric mapping APIs."""

    def __init__(self, mappings: dict[str, dict] | None = None) -> None:
        self._mappings = mappings or {}

    def get_metric_mapping(self, metric_name: str) -> dict | None:
        return self._mappings.get(metric_name)

    def list_metric_mappings(self) -> dict[str, dict]:
        return dict(self._mappings)


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


def test_cookie_auth_sends_header() -> None:
    """Cookie auth should normalize to Cookie header."""
    adapter = _build_adapter({}, auth_type="cookie")
    adapter._api_key = "session-id"

    assert adapter._build_auth_headers() == {"Cookie": "S=session-id"}
