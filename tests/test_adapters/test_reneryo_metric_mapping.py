"""Tests for ReneryoAdapter metric-mapping execution path."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from skill.adapters.reneryo import ReneryoAdapter
from skill.adapters.reneryo._metric_mapping import (
    extract_mapped_value,
    resolve_kpi_request,
)
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod


class _StubSettingsService:
    """Minimal stub for metric mapping lookup."""

    def __init__(self, mapping: dict | None = None) -> None:
        self._mapping = mapping

    def get_metric_mapping(self, metric_name: str) -> dict | None:
        if metric_name != "energy_per_unit":
            return None
        return self._mapping


class TestMetricMappingHelpers:
    """Unit tests for mapping helper functions."""

    def test_resolve_kpi_request_fills_placeholders(self) -> None:
        """Placeholder values are injected into endpoint path."""
        period = TimePeriod.today()
        mapping = {
            "endpoint": "/api/u/measurement/seu/item/{SEU_ID}/values?period=DAILY",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        }

        endpoint, params = resolve_kpi_request(
            mapping=mapping,
            period=period,
            asset_id="line-1",
            extra_settings={"SEU_ID": "seu-123"},
        )

        assert endpoint == "/api/u/measurement/seu/item/seu-123/values"
        assert params["period"] == "DAILY"
        assert "datetimeMin" in params
        assert "datetimeMax" in params

    def test_extract_mapped_value_reads_json_path(self) -> None:
        """JSON path $.records[0].value returns numeric value."""
        payload = {"records": [{"value": 2.91}]}

        result = extract_mapped_value(payload, "$.records[0].value")

        assert result == pytest.approx(2.91)

    def test_extract_mapped_value_raises_no_data_on_null(self) -> None:
        """Null mapped values surface a no-data adapter error."""
        payload = {"consumption": None}

        with pytest.raises(AdapterError) as exc_info:
            extract_mapped_value(payload, "$.consumption")

        assert exc_info.value.code == "RENERYO_NO_DATA"

    def test_resolve_kpi_request_fills_period_placeholders(self) -> None:
        """Date placeholders are resolved from TimePeriod automatically."""
        period = TimePeriod.today()
        mapping = {
            "endpoint": (
                "/api/u/measurement/seu/item?"
                "datetimeMin={start_date}&datetimeMax={end_date}"
            ),
            "json_path": "$.records[0].consumption",
            "unit": "kWh/unit",
        }

        endpoint, params = resolve_kpi_request(
            mapping=mapping,
            period=period,
            asset_id="line-1",
            extra_settings={},
        )

        assert endpoint == "/api/u/measurement/seu/item"
        assert params["datetimeMin"] == period.start.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert params["datetimeMax"] == period.end.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_resolve_kpi_request_normalizes_u_prefix(self) -> None:
        """Native endpoint path '/u/...' is normalized to '/api/u/...'."""
        mapping = {
            "endpoint": "/u/measurement/seu/item?period=DAILY",
            "json_path": "$.records[0].consumption",
            "unit": "kWh/unit",
        }

        endpoint, params = resolve_kpi_request(
            mapping=mapping,
            period=TimePeriod.today(),
            asset_id="line-1",
            extra_settings={},
        )

        assert endpoint == "/api/u/measurement/seu/item"
        assert params["period"] == "DAILY"


class TestReneryoAdapterMappingPath:
    """Adapter behavior when profile-scoped mapping is configured."""

    @pytest.mark.asyncio
    async def test_get_kpi_uses_metric_mapping_when_available(self) -> None:
        """Mapped endpoint/json_path are used before default endpoint map."""
        mapping = {
            "endpoint": "/api/u/measurement/seu/item/{SEU_ID}/values",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        }
        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="key",
            api_format="native",
            settings_service=_StubSettingsService(mapping),
            profile_name="reneryo",
            extra_settings={"SEU_ID": "seu-9"},
        )
        adapter._session = object()
        adapter._retry_fetch = AsyncMock(
            return_value={"records": [{"value": 3.14}]},
        )

        result = await adapter.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="default",
            period=TimePeriod.today(),
        )

        assert result.value == pytest.approx(3.14)
        assert result.unit == "kWh/unit"
        adapter._retry_fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_kpi_raises_when_placeholder_unresolved(self) -> None:
        """Unresolved endpoint placeholders produce a clear mapping error."""
        mapping = {
            "endpoint": "/api/u/measurement/seu/item/{SEU_ID}/values",
            "json_path": "$.records[0].value",
            "unit": "kWh/unit",
        }
        adapter = ReneryoAdapter(
            api_url="https://reneryo.example.com",
            api_key="key",
            api_format="native",
            settings_service=_StubSettingsService(mapping),
            profile_name="reneryo",
            extra_settings={},
        )
        adapter._session = object()

        with pytest.raises(AdapterError) as exc_info:
            await adapter.get_kpi(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id="default",
                period=TimePeriod.today(),
            )

        assert exc_info.value.code == "RENERYO_MAPPING_INVALID"
        assert "SEU_ID" in exc_info.value.message
