"""
Tests for Pydantic schema validation and serialisation.

Covers:
    - PlatformConfigRequest model_validator (URL, key, mock bypass)
    - PlatformType literal rejects unknown values
    - MetricMappingRequest field validation
    - SystemStatusResponse serialisation round-trip
    - CanonicalMetricName enforcement
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure Web UI schemas are importable.
_WEB_UI_DIR = str(Path(__file__).resolve().parents[2] / "web-ui")
if _WEB_UI_DIR not in sys.path:
    sys.path.insert(0, _WEB_UI_DIR)

from schemas.config import (  # noqa: E402
    ConnectionTestResponse,
    PlatformConfigRequest,
    PlatformConfigResponse,
    ResetResponse,
)
from schemas.metrics import (  # noqa: E402
    CANONICAL_METRIC_VALUES,
    MetricMappingListResponse,
    MetricMappingRequest,
    MetricMappingResponse,
    MetricMappingTestRequest,
    MetricMappingTestResponse,
)
from schemas.status import SystemStatusResponse  # noqa: E402


# ══════════════════════════════════════════════════════════
# PlatformConfigRequest
# ══════════════════════════════════════════════════════════


class TestPlatformConfigRequest:
    """Tests for the PlatformConfigRequest Pydantic model."""

    def test_mock_platform_type_rejected(self) -> None:
        """'mock' is not a valid platform type."""
        with pytest.raises(ValidationError):
            PlatformConfigRequest(platform_type="mock")  # type: ignore[arg-type]

    def test_reneryo_with_valid_url_and_key(self) -> None:
        """Valid reneryo config passes validation."""
        model = PlatformConfigRequest(
            platform_type="reneryo",
            api_url="https://api.reneryo.com/v1",
            api_key="reneryo-secret",
        )

        assert model.platform_type == "reneryo"
        assert model.api_url == "https://api.reneryo.com/v1"

    def test_non_mock_missing_url_raises(self) -> None:
        """Non-mock without api_url raises ValidationError."""
        with pytest.raises(ValidationError, match="api_url"):
            PlatformConfigRequest(
                platform_type="reneryo",
                api_url="",
                api_key="secret",
            )

    def test_non_mock_missing_key_raises(self) -> None:
        """Non-mock without api_key raises ValidationError."""
        with pytest.raises(ValidationError, match="api_key"):
            PlatformConfigRequest(
                platform_type="reneryo",
                api_url="https://api.example.com",
                api_key="",
            )

    def test_non_mock_invalid_url_raises(self) -> None:
        """Non-mock with malformed URL raises ValidationError."""
        with pytest.raises(ValidationError, match="valid URL"):
            PlatformConfigRequest(
                platform_type="reneryo",
                api_url="not-a-url",
                api_key="secret",
            )

    def test_unknown_platform_type_raises(self) -> None:
        """Literal type rejects values outside the allowed set."""
        with pytest.raises(ValidationError):
            PlatformConfigRequest(
                platform_type="totally_unknown",  # type: ignore[arg-type]
                api_url="https://api.example.com",
                api_key="key",
            )

    def test_extra_settings_default_empty_dict(self) -> None:
        """extra_settings defaults to an empty dict."""
        model = PlatformConfigRequest(
            platform_type="reneryo",
            api_url="https://api.example.com",
            api_key="key",
        )

        assert model.extra_settings == {}

    def test_custom_rest_platform_accepted(self) -> None:
        """custom_rest is a valid PlatformType."""
        model = PlatformConfigRequest(
            platform_type="custom_rest",
            api_url="https://custom.example.com",
            api_key="key",
        )

        assert model.platform_type == "custom_rest"


# ══════════════════════════════════════════════════════════
# PlatformConfigResponse
# ══════════════════════════════════════════════════════════


class TestPlatformConfigResponse:
    """Tests for PlatformConfigResponse serialisation."""

    def test_serialises_all_fields(self) -> None:
        """Response model serialises all expected fields."""
        model = PlatformConfigResponse(
            platform_type="reneryo",
            api_url="https://api.example.com",
            api_key="****5678",
            extra_settings={"tenant_id": "abc"},
        )

        data = model.model_dump()

        assert data["platform_type"] == "reneryo"
        assert data["api_url"] == "https://api.example.com"
        assert data["api_key"] == "****5678"
        assert data["extra_settings"] == {"tenant_id": "abc"}


# ══════════════════════════════════════════════════════════
# ConnectionTestResponse & ResetResponse
# ══════════════════════════════════════════════════════════


class TestConnectionTestResponse:
    """Tests for ConnectionTestResponse serialisation."""

    def test_success_response(self) -> None:
        """Successful connection test serialises correctly."""
        model = ConnectionTestResponse(success=True, message="OK")

        assert model.success is True
        assert model.message == "OK"

    def test_failure_response(self) -> None:
        """Failed connection test serialises correctly."""
        model = ConnectionTestResponse(success=False, message="Timeout")

        assert model.success is False


class TestResetResponse:
    """Tests for ResetResponse serialisation."""

    def test_reset_response(self) -> None:
        """Reset response contains expected fields."""
        model = ResetResponse(status="reset", platform_type="unconfigured")

        assert model.status == "reset"
        assert model.platform_type == "unconfigured"


# ══════════════════════════════════════════════════════════
# MetricMappingRequest
# ══════════════════════════════════════════════════════════


class TestMetricMappingRequest:
    """Tests for MetricMappingRequest Pydantic model."""

    def test_valid_mapping_request(self) -> None:
        """Valid canonical metric with all fields passes."""
        model = MetricMappingRequest(
            canonical_metric="energy_per_unit",
            endpoint="/api/v1/kpis/energy",
            json_path="$.data.value",
            unit="kWh/unit",
        )

        assert model.canonical_metric == "energy_per_unit"

    def test_invalid_canonical_metric_raises(self) -> None:
        """Unknown canonical metric raises ValidationError."""
        with pytest.raises(ValidationError):
            MetricMappingRequest(
                canonical_metric="totally_invalid",  # type: ignore[arg-type]
                endpoint="/api",
                json_path="$.x",
                unit="u",
            )

    def test_empty_endpoint_raises(self) -> None:
        """Empty endpoint violates min_length=1."""
        with pytest.raises(ValidationError):
            MetricMappingRequest(
                canonical_metric="energy_per_unit",
                endpoint="",
                json_path="$.data",
                unit="kWh",
            )

    def test_empty_json_path_raises(self) -> None:
        """Empty json_path violates min_length=1."""
        with pytest.raises(ValidationError):
            MetricMappingRequest(
                canonical_metric="energy_per_unit",
                endpoint="/api",
                json_path="",
                unit="kWh",
            )

    def test_empty_unit_raises(self) -> None:
        """Empty unit violates min_length=1."""
        with pytest.raises(ValidationError):
            MetricMappingRequest(
                canonical_metric="energy_per_unit",
                endpoint="/api",
                json_path="$.data",
                unit="",
            )

    def test_transform_defaults_to_none(self) -> None:
        """transform field defaults to None when not provided."""
        model = MetricMappingRequest(
            canonical_metric="scrap_rate",
            endpoint="/api/v1/kpis/scrap",
            json_path="$.data.rate",
            unit="%",
        )

        assert model.transform is None

    def test_all_canonical_metrics_accepted(self) -> None:
        """Every CanonicalMetric enum value is accepted."""
        for metric_name in CANONICAL_METRIC_VALUES:
            model = MetricMappingRequest(
                canonical_metric=metric_name,
                endpoint="/api/test",
                json_path="$.v",
                unit="u",
            )
            assert model.canonical_metric == metric_name


# ══════════════════════════════════════════════════════════
# MetricMappingResponse & MetricMappingListResponse
# ══════════════════════════════════════════════════════════


class TestMetricMappingResponse:
    """Tests for MetricMappingResponse serialisation."""

    def test_serialises_all_fields(self) -> None:
        """Response includes all expected fields."""
        model = MetricMappingResponse(
            canonical_metric="energy_per_unit",
            endpoint="/api",
            json_path="$.v",
            unit="kWh",
            transform="mul",
        )

        data = model.model_dump()
        assert data["canonical_metric"] == "energy_per_unit"
        assert data["transform"] == "mul"


class TestMetricMappingListResponse:
    """Tests for the list wrapper response."""

    def test_empty_list(self) -> None:
        """Empty list serialises to empty array."""
        model = MetricMappingListResponse(root=[])

        assert model.model_dump() == []

    def test_list_with_items(self) -> None:
        """List with items serialises correctly."""
        item = MetricMappingResponse(
            canonical_metric="oee",
            endpoint="/api",
            json_path="$.v",
            unit="%",
            transform=None,
        )
        model = MetricMappingListResponse(root=[item])

        data = model.model_dump()
        assert len(data) == 1
        assert data[0]["canonical_metric"] == "oee"


class TestMetricMappingTestRequest:
    """Tests for MetricMappingTestRequest schema."""

    def test_valid_metric_mapping_test_request(self) -> None:
        model = MetricMappingTestRequest(
            base_url="https://api.example.com",
            endpoint="/metrics/energy",
            json_path="$.data.value",
            auth_type="bearer",
            auth_token="token",
        )

        assert model.auth_type == "bearer"

    def test_invalid_auth_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            MetricMappingTestRequest(
                base_url="https://api.example.com",
                endpoint="/metrics/energy",
                json_path="$.data.value",
                auth_type="basic",  # type: ignore[arg-type]
                auth_token="token",
            )

    def test_empty_endpoint_raises(self) -> None:
        with pytest.raises(ValidationError):
            MetricMappingTestRequest(
                base_url="https://api.example.com",
                endpoint="",
                json_path="$.data.value",
                auth_type="cookie",
                auth_token="token",
            )

    def test_none_auth_type_is_valid(self) -> None:
        model = MetricMappingTestRequest(
            base_url="https://api.example.com",
            endpoint="/metrics/energy",
            json_path="$.data.value",
            auth_type="none",
            auth_token="",
        )

        assert model.auth_type == "none"


class TestMetricMappingTestResponse:
    """Tests for MetricMappingTestResponse serialisation."""

    def test_success_response_serialises(self) -> None:
        model = MetricMappingTestResponse(
            success=True,
            value=11.25,
            raw_response_preview='{"data":{"value":11.25}}',
            error=None,
        )

        data = model.model_dump()
        assert data["success"] is True
        assert data["value"] == 11.25
        assert data["error"] is None


# ══════════════════════════════════════════════════════════
# SystemStatusResponse
# ══════════════════════════════════════════════════════════


class TestSystemStatusResponse:
    """Tests for SystemStatusResponse schema."""

    def test_serialises_all_fields(self) -> None:
        """All fields serialise with correct types."""
        model = SystemStatusResponse(
            configured=True,
            active_adapter="reneryo",
            platform_type="reneryo",
            loaded_intents=15,
            database_connected=True,
            version="0.1.0",
        )

        data = model.model_dump()
        assert data["configured"] is True
        assert data["loaded_intents"] == 15
        assert isinstance(data["version"], str)

    def test_unconfigured_status(self) -> None:
        """Default unconfigured values serialise correctly."""
        model = SystemStatusResponse(
            configured=False,
            active_adapter="unconfigured",
            platform_type="unconfigured",
            loaded_intents=0,
            database_connected=False,
            version="0.0.0",
        )

        data = model.model_dump()
        assert data["configured"] is False
        assert data["active_adapter"] == "unconfigured"
        assert data["database_connected"] is False
