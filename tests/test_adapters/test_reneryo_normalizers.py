"""
Unit tests for RENERYO response normalizers.

Tests the transformation from native RENERYO API format
to the parser-expected format used by ``_reneryo_parsers.py``.
"""

from __future__ import annotations

import pytest

from skill.adapters.reneryo._normalizers import (
    is_native_format,
    normalize_meter_to_kpi,
    normalize_meters_to_comparison,
    normalize_meters_to_raw,
    normalize_meters_to_trend,
    normalize_metric_to_kpi,
)


# =========================================================================
# Fixtures — Real RENERYO API response samples
# =========================================================================


@pytest.fixture
def meter_response() -> dict:
    """Sample native meter/item response from real RENERYO API."""
    return {
        "records": [
            {
                "id": "cffa4891-c0eb-4dbc-93dc-b104b234d569",
                "name": "Electric Main Meter",
                "energyResource": "ELECTRIC",
                "energyConversionRate": 1,
                "consumption": 22655.28751,
                "metric": {
                    "id": "ca02fbd8-4414-4264-84a6-1f7776aff9f9",
                    "name": "Main Electric Metric",
                    "unitGroup": "ENERGY",
                },
                "consumptionPercentage": None,
                "slices": [
                    {
                        "id": "6fecc770-bc2c-46a5-8772-3d92194a8279",
                        "rate": 1,
                        "isMain": True,
                        "department": {
                            "id": "e1c4fec1-3adc-4801-a313-9db1406cce77",
                            "name": "A Department",
                        },
                    },
                ],
            },
            {
                "id": "6af5690b-6585-4095-a3ad-347f74845295",
                "name": "Gas Main Meter",
                "energyResource": "GAS",
                "energyConversionRate": 1,
                "consumption": 37542.12579,
                "metric": {
                    "id": "5c871284-194b-417f-84bf-0aae2878ab84",
                    "name": "Main Gas Metric",
                    "unitGroup": "ENERGY",
                },
                "consumptionPercentage": None,
                "slices": [],
            },
            {
                "id": "123dcd14-49d4-45fe-803b-15b65ea14066",
                "name": "Water Main Meter",
                "energyResource": "WATER",
                "energyConversionRate": 1,
                "consumption": 13341.64129,
                "metric": {
                    "id": "d786d561-0a51-4ee7-a2f6-a936439d6df8",
                    "name": "Main Water Metric",
                    "unitGroup": "VOLUME",
                },
                "consumptionPercentage": None,
                "slices": [],
            },
        ],
    }


@pytest.fixture
def metric_response() -> dict:
    """Sample native metric/item response from real RENERYO API."""
    return {
        "records": [
            {
                "id": "ca02fbd8-4414-4264-84a6-1f7776aff9f9",
                "name": "Main Electric Metric",
                "description": "Main electric meter metric",
                "type": "COUNTER",
                "unitGroup": "ENERGY",
                "lastValue": 1.654069,
                "lastValueDatetime": "2026-02-10T09:00:00.000Z",
                "valuesUpdatedAt": "2026-02-10T09:17:03.106Z",
            },
            {
                "id": "5c871284-194b-417f-84bf-0aae2878ab84",
                "name": "Main Gas Metric",
                "description": "Main gas meter metric",
                "type": "COUNTER",
                "unitGroup": "ENERGY",
                "lastValue": 50.214131,
                "lastValueDatetime": "2026-02-10T09:15:00.000Z",
                "valuesUpdatedAt": "2026-02-10T09:17:03.106Z",
            },
        ],
    }


# =========================================================================
# Format Detection
# =========================================================================


class TestIsNativeFormat:
    """Tests for native format detection."""

    def test_native_format_detected(self, meter_response: dict) -> None:
        """Dict with 'records' key is detected as native format."""
        assert is_native_format(meter_response) is True

    def test_mock_dict_not_native(self) -> None:
        """Dict without 'records' key is not native format."""
        assert is_native_format({"value": 42.0, "unit": "kWh"}) is False

    def test_list_not_native(self) -> None:
        """List response is not native format."""
        assert is_native_format([{"value": 42.0}]) is False

    def test_empty_records_is_native(self) -> None:
        """Dict with empty 'records' list is still native format."""
        assert is_native_format({"records": []}) is True


# =========================================================================
# Meter → KPI Normalization
# =========================================================================


class TestNormalizeMeterToKpi:
    """Tests for meter record → KPI dict normalization."""

    def test_normalizes_by_name(self, meter_response: dict) -> None:
        """Finds meter by name and extracts consumption as value."""
        result = normalize_meter_to_kpi(meter_response, "Electric Main Meter")
        assert result["value"] == 22655.28751
        assert result["unit"] == "kWh"
        assert "timestamp" in result

    def test_normalizes_by_uuid(self, meter_response: dict) -> None:
        """Finds meter by UUID and extracts consumption."""
        result = normalize_meter_to_kpi(
            meter_response, "cffa4891-c0eb-4dbc-93dc-b104b234d569",
        )
        assert result["value"] == 22655.28751

    def test_volume_unit_group(self, meter_response: dict) -> None:
        """Water meter maps unitGroup=VOLUME to m³."""
        result = normalize_meter_to_kpi(meter_response, "Water Main Meter")
        assert result["unit"] == "m³"

    def test_fallback_to_first_record(self, meter_response: dict) -> None:
        """Unknown asset falls back to first record."""
        result = normalize_meter_to_kpi(meter_response, "Unknown-Meter")
        assert result["value"] == 22655.28751

    def test_empty_records_raises(self) -> None:
        """Empty records list raises KeyError."""
        with pytest.raises(KeyError):
            normalize_meter_to_kpi({"records": []}, "Any")


# =========================================================================
# Meter → Comparison Normalization
# =========================================================================


class TestNormalizeMetersToComparison:
    """Tests for meter records → comparison list normalization."""

    def test_normalizes_two_assets(self, meter_response: dict) -> None:
        """Extracts two matching meters as comparison items."""
        result = normalize_meters_to_comparison(
            meter_response,
            ["Electric Main Meter", "Gas Main Meter"],
        )
        assert len(result) == 2
        assert result[0]["asset_id"] == "Electric Main Meter"
        assert result[0]["value"] == 22655.28751
        assert result[1]["asset_id"] == "Gas Main Meter"
        assert result[1]["value"] == 37542.12579

    def test_includes_unit(self, meter_response: dict) -> None:
        """Each item includes resolved unit."""
        result = normalize_meters_to_comparison(
            meter_response, ["Electric Main Meter"],
        )
        assert result[0]["unit"] == "kWh"


# =========================================================================
# Meter → Trend Normalization
# =========================================================================


class TestNormalizeMetersToTrend:
    """Tests for meter records → trend data points normalization."""

    def test_all_records_become_data_points(
        self, meter_response: dict,
    ) -> None:
        """Each meter record becomes a trend data point."""
        result = normalize_meters_to_trend(meter_response)
        assert len(result) == 3
        assert all("value" in pt for pt in result)
        assert all("timestamp" in pt for pt in result)
        assert all("unit" in pt for pt in result)

    def test_consumption_mapped_to_value(
        self, meter_response: dict,
    ) -> None:
        """Consumption field maps to value."""
        result = normalize_meters_to_trend(meter_response)
        assert result[0]["value"] == 22655.28751

    def test_empty_records_returns_empty(self) -> None:
        """Empty records list returns empty trend."""
        result = normalize_meters_to_trend({"records": []})
        assert result == []


# =========================================================================
# Meter → Raw Data Normalization
# =========================================================================


class TestNormalizeMetersToRaw:
    """Tests for meter records → raw data point list normalization."""

    def test_all_records_returned(self, meter_response: dict) -> None:
        """All meter records become raw data points."""
        result = normalize_meters_to_raw(meter_response)
        assert len(result) == 3

    def test_data_point_format(self, meter_response: dict) -> None:
        """Each data point has value, unit, timestamp."""
        result = normalize_meters_to_raw(meter_response)
        for pt in result:
            assert "value" in pt
            assert "unit" in pt
            assert "timestamp" in pt


# =========================================================================
# Metric → KPI Normalization
# =========================================================================


class TestNormalizeMetricToKpi:
    """Tests for metric-item record → KPI dict normalization."""

    def test_normalizes_by_name(self, metric_response: dict) -> None:
        """Finds metric by name and extracts lastValue."""
        result = normalize_metric_to_kpi(metric_response, "Main Electric Metric")
        assert result["value"] == 1.654069
        assert result["unit"] == "kWh"
        assert result["timestamp"] == "2026-02-10T09:00:00.000Z"

    def test_partial_name_match(self, metric_response: dict) -> None:
        """Finds metric by partial name match."""
        result = normalize_metric_to_kpi(metric_response, "Electric")
        assert result["value"] == 1.654069

    def test_fallback_to_first(self, metric_response: dict) -> None:
        """Unknown name falls back to first record."""
        result = normalize_metric_to_kpi(metric_response, "Unknown")
        assert result["value"] == 1.654069

    def test_empty_records_raises(self) -> None:
        """Empty records list raises KeyError."""
        with pytest.raises(KeyError):
            normalize_metric_to_kpi({"records": []}, "Any")
