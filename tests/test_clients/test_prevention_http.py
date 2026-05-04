"""Tests for HttpPreventionClient — GraphQL-backed anomaly and drift detection."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill.clients.base import ExternalServiceClient
from skill.clients.prevention import PreventionClient
from skill.clients.prevention_http import (
    HttpPreventionClient,
    _CATEGORY_TO_ANOMALY_GOAL,
    _CATEGORY_TO_DRIFT_GOAL,
    _CATEGORY_TO_FORECAST_GOAL,
    _fallback_forecast_result_from_series,
    _parse_anomaly_results,
    _parse_drift_results,
    _parse_forecast_results,
)
from skill.clients._prevention_demo_data import METRIC_CATEGORY_MAP
from skill.domain.anomaly_models import (
    AnomalyDetectionResult,
    DriftReport,
    ForecastReport,
)
from skill.domain.models import CanonicalMetric, DataPoint


# =========================================================================
# Fixtures
# =========================================================================

PREVENTION_URL = "http://prevention:8081"


@pytest.fixture
def client() -> HttpPreventionClient:
    """Create HttpPreventionClient without connecting."""
    return HttpPreventionClient(url=PREVENTION_URL, timeout=5)


@pytest.fixture
def client_with_auth() -> HttpPreventionClient:
    """Create HttpPreventionClient with auth token."""
    return HttpPreventionClient(
        url=PREVENTION_URL, timeout=5, auth_token="test-token-123",
    )


def _make_data_points(
    values: list[float],
    *,
    unit: str = "kWh/unit",
    start: datetime | None = None,
) -> list[DataPoint]:
    """Build DataPoint list from raw values."""
    base = start or datetime(2026, 2, 10, 8, 0, 0)
    return [
        DataPoint(timestamp=base + timedelta(hours=i), value=v, unit=unit)
        for i, v in enumerate(values)
    ]


@pytest.fixture
def sample_data() -> list[DataPoint]:
    """Sample data points for interface compliance."""
    return _make_data_points([2.5, 2.6, 2.4, 2.5, 2.55])


# ── Mock GraphQL responses ──────────────────────────────────────

MOCK_ANOMALY_RESULTS = [
    {
        "timestamp": "2026-02-10T14:00:00",
        "value": 20.0,
        "z_score": 4.5,
        "is_anomalous": True,
        "severity": "critical",
        "anomaly_type": "spike",
        "metric_name": "energy_per_unit",
        "asset_id": "Line-1",
    },
    {
        "timestamp": "2026-02-10T10:00:00",
        "value": 15.0,
        "z_score": 2.8,
        "is_anomalous": True,
        "severity": "medium",
        "anomaly_type": "spike",
        "metric_name": "energy_per_unit",
        "asset_id": "Line-2",
    },
]

MOCK_NO_ANOMALY_RESULTS = [
    {
        "timestamp": "",
        "value": 0,
        "z_score": 0,
        "is_anomalous": False,
        "severity": "none",
        "anomaly_type": "none",
        "metric_name": "",
        "asset_id": "",
    },
]

MOCK_DRIFT_RESULTS = [
    {
        "metric_name": "energy_per_unit",
        "asset_id": "Line-1",
        "has_drift": True,
        "drift_direction": "increasing",
        "drift_rate": 0.0035,
        "r_squared": 0.85,
        "periods_analyzed": 672,
        "description": "energy_per_unit on Line-1: increasing (slope=0.003500, R²=0.8500)",
    },
]

MOCK_FORECAST_RESULTS = [
    {
        "metric_name": "energy_per_unit",
        "asset_id": "Line-1",
        "horizon_periods": 7,
        "predicted_value": 2.75,
        "confidence": 0.82,
        "fit_quality": 0.74,
        "training_points": 30,
        "method_name": "linear_forecast",
        "forecast_timestamp": "2026-05-06T00:00:00",
        "available": True,
        "description": "energy_per_unit on Line-1: increasing forecast",
        "recommended_action": "Review the main operational contributors.",
    },
]


def _graphql_response(data: dict) -> dict:
    """Wrap data in a standard GraphQL response envelope."""
    return {"data": data}


def _result_request_response(results: list, reason: list | None = None) -> dict:
    """Build a resultRequest GraphQL response."""
    entry = {"results": results}
    if reason is not None:
        entry["reason"] = reason
    return _graphql_response({"resultRequest": [entry]})


class _FakeTokenResponse:
    """Minimal async context manager response for token endpoint tests."""

    status = 200

    async def __aenter__(self) -> _FakeTokenResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def json(self) -> dict:
        return {"access_token": "kc-access-token", "expires_in": 300}

    async def text(self) -> str:
        return ""


class _FakeTokenSession:
    """Capture POST form payloads for Keycloak token tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, **kwargs) -> _FakeTokenResponse:
        self.calls.append((url, kwargs))
        return _FakeTokenResponse()


# =========================================================================
# Interface Tests
# =========================================================================


class TestHttpClientInterface:
    """Verify HttpPreventionClient implements required ABCs."""

    def test_is_external_service_client(self, client: HttpPreventionClient) -> None:
        assert isinstance(client, ExternalServiceClient)

    def test_is_prevention_client(self, client: HttpPreventionClient) -> None:
        assert isinstance(client, PreventionClient)


# =========================================================================
# Constructor Tests
# =========================================================================


class TestHttpClientInit:
    """Test initialization and configuration."""

    def test_url_stored_without_trailing_slash(self) -> None:
        c = HttpPreventionClient(url="http://host:8081/")
        assert c._base_url == "http://host:8081"
        assert c._graphql_url == "http://host:8081/graphql"

    def test_auth_token_stored(self, client_with_auth: HttpPreventionClient) -> None:
        assert client_with_auth._auth_token == "test-token-123"

    def test_keycloak_config_stored(self) -> None:
        c = HttpPreventionClient(
            url=PREVENTION_URL,
            keycloak_token_url="http://keycloak/token",
            keycloak_client_id="avaros",
            keycloak_client_secret="secret",
            keycloak_scope="openid",
        )

        assert c._keycloak_token_url == "http://keycloak/token"
        assert c._keycloak_client_id == "avaros"
        assert c._keycloak_client_secret == "secret"
        assert c._keycloak_scope == "openid"

    def test_default_not_connected(self, client: HttpPreventionClient) -> None:
        assert not client.is_connected

    def test_service_name_platform_agnostic(self, client: HttpPreventionClient) -> None:
        name = client.service_name
        assert "prevention" not in name.lower()
        assert "PREVENTION" not in name
        assert isinstance(name, str)
        assert len(name) > 0


# =========================================================================
# Lifecycle Tests
# =========================================================================


class TestHttpClientLifecycle:
    """Test initialize, shutdown, health_check."""

    @pytest.mark.asyncio
    async def test_initialize_sets_connected_on_healthy(
        self, client: HttpPreventionClient,
    ) -> None:
        with patch.object(client, "_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = {
                "allAnalysis": [{"name": "Energy", "analyticsGoal": "ENERGY_ANOMALY_CHECK"}],
            }
            await client.initialize()
            assert client.is_connected

    @pytest.mark.asyncio
    async def test_initialize_not_connected_on_failure(
        self, client: HttpPreventionClient,
    ) -> None:
        with patch.object(client, "_query", new_callable=AsyncMock) as mock_q:
            mock_q.side_effect = ConnectionError("unreachable")
            await client.initialize()
            assert not client.is_connected

    @pytest.mark.asyncio
    async def test_shutdown_clears_connection(
        self, client: HttpPreventionClient,
    ) -> None:
        client._connected = True
        client._session = MagicMock()
        client._session.closed = False
        client._session.close = AsyncMock()
        await client.shutdown()
        assert not client.is_connected
        assert client._session is None

    @pytest.mark.asyncio
    async def test_health_check_true_with_analyses(
        self, client: HttpPreventionClient,
    ) -> None:
        with patch.object(client, "_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = {
                "allAnalysis": [{"name": "test"}],
            }
            assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_false_on_empty(
        self, client: HttpPreventionClient,
    ) -> None:
        with patch.object(client, "_query", new_callable=AsyncMock) as mock_q:
            mock_q.return_value = {"allAnalysis": []}
            assert await client.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_false_on_error(
        self, client: HttpPreventionClient,
    ) -> None:
        with patch.object(client, "_query", new_callable=AsyncMock) as mock_q:
            mock_q.side_effect = ConnectionError("boom")
            assert await client.health_check() is False

    @pytest.mark.asyncio
    async def test_build_headers_uses_static_bearer_token(
        self, client_with_auth: HttpPreventionClient,
    ) -> None:
        headers = await client_with_auth._build_headers(MagicMock())

        assert headers["Authorization"] == "Bearer test-token-123"

    @pytest.mark.asyncio
    async def test_build_headers_fetches_keycloak_client_credentials(self) -> None:
        c = HttpPreventionClient(
            url=PREVENTION_URL,
            keycloak_token_url="http://keycloak/token",
            keycloak_client_id="avaros",
            keycloak_client_secret="secret",
            keycloak_scope="openid",
        )
        session = _FakeTokenSession()

        headers = await c._build_headers(session)  # type: ignore[arg-type]

        assert headers["Authorization"] == "Bearer kc-access-token"
        assert session.calls == [
            (
                "http://keycloak/token",
                {
                    "data": {
                        "grant_type": "client_credentials",
                        "client_id": "avaros",
                        "client_secret": "secret",
                        "scope": "openid",
                    },
                    "headers": {"Accept": "application/json"},
                },
            ),
        ]


# =========================================================================
# Anomaly Detection Tests
# =========================================================================


class TestHttpClientAnomalyDetection:
    """Test detect_anomaly with mocked GraphQL responses."""

    @pytest.mark.asyncio
    async def test_detect_anomaly_returns_result_type(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_ANOMALY_RESULTS
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert isinstance(result, AnomalyDetectionResult)

    @pytest.mark.asyncio
    async def test_detect_anomaly_finds_anomalous(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_ANOMALY_RESULTS
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert result.is_anomalous is True
            assert result.severity == "critical"
            assert result.anomaly_type == "spike"
            assert result.metric == CanonicalMetric.ENERGY_PER_UNIT

    @pytest.mark.asyncio
    async def test_detect_anomaly_no_anomaly(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_NO_ANOMALY_RESULTS
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert result.is_anomalous is False
            assert result.severity == "none"

    @pytest.mark.asyncio
    async def test_detect_anomaly_empty_results(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert result.is_anomalous is False

    @pytest.mark.asyncio
    async def test_detect_anomaly_preserves_metric(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            result = await client.detect_anomaly(
                CanonicalMetric.OEE, sample_data,
            )
            assert result.metric == CanonicalMetric.OEE

    @pytest.mark.asyncio
    async def test_detect_anomaly_has_recommended_action_when_anomalous(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_ANOMALY_RESULTS
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert result.recommended_action is not None
            assert len(result.recommended_action) > 0

    @pytest.mark.asyncio
    async def test_detect_anomaly_no_action_when_normal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_NO_ANOMALY_RESULTS
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert result.recommended_action is None

    @pytest.mark.asyncio
    async def test_detect_anomaly_confidence_range(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_ANOMALY_RESULTS
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_connection_error_falls_back_to_local_series(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.side_effect = ConnectionError("unreachable")
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT,
                sample_data,
            )
            assert result.is_anomalous is False
            assert result.severity == "none"
            assert result.expected_value is not None

    @pytest.mark.asyncio
    async def test_detect_anomaly_fallback_detects_spike_from_local_series(
        self, client: HttpPreventionClient,
    ) -> None:
        series = _make_data_points([2.5, 2.4, 2.6, 2.5, 5.4])

        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.side_effect = ConnectionError("unreachable")
            result = await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT,
                series,
            )

        assert result.is_anomalous is True
        assert result.anomaly_type == "spike"
        assert result.severity in {"medium", "high", "critical"}
        assert result.expected_value is not None
        assert result.actual_value == 5.4

    @pytest.mark.asyncio
    async def test_detect_anomaly_queries_correct_goal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            await client.detect_anomaly(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            mock_f.assert_called_once_with("ENERGY_ANOMALY_CHECK")

    @pytest.mark.asyncio
    async def test_detect_anomaly_production_metric_goal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            await client.detect_anomaly(CanonicalMetric.OEE, sample_data)
            mock_f.assert_called_once_with("PRODUCTION_ANOMALY_CHECK")

    @pytest.mark.asyncio
    async def test_detect_anomaly_material_metric_goal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            await client.detect_anomaly(
                CanonicalMetric.SCRAP_RATE, sample_data,
            )
            mock_f.assert_called_once_with("MATERIAL_ANOMALY_CHECK")

    @pytest.mark.asyncio
    async def test_detect_anomaly_carbon_metric_goal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            await client.detect_anomaly(
                CanonicalMetric.CO2_PER_UNIT, sample_data,
            )
            mock_f.assert_called_once_with("CO2_ANOMALY_CHECK")

    @pytest.mark.asyncio
    async def test_detect_anomaly_supplier_metric_goal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            await client.detect_anomaly(
                CanonicalMetric.SUPPLIER_LEAD_TIME, sample_data,
            )
            mock_f.assert_called_once_with("SUPPLIER_ANOMALY_CHECK")


# =========================================================================
# Drift Detection Tests
# =========================================================================


class TestHttpClientDriftDetection:
    """Test check_drift with mocked GraphQL responses."""

    @pytest.mark.asyncio
    async def test_check_drift_returns_report_type(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_DRIFT_RESULTS
            result = await client.check_drift(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert isinstance(result, DriftReport)

    @pytest.mark.asyncio
    async def test_check_drift_detects_drift(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_DRIFT_RESULTS
            result = await client.check_drift(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert result.has_drift is True
            assert result.drift_direction == "degrading"
            assert result.drift_rate == 0.0035

    @pytest.mark.asyncio
    async def test_check_drift_no_drift_on_empty(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            result = await client.check_drift(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            assert result.has_drift is False
            assert result.drift_direction == "stable"

    @pytest.mark.asyncio
    async def test_check_drift_preserves_metric(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            result = await client.check_drift(CanonicalMetric.OEE, sample_data)
            assert result.metric == CanonicalMetric.OEE

    @pytest.mark.asyncio
    async def test_check_drift_connection_error_propagates(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.side_effect = ConnectionError("unreachable")
            with pytest.raises(ConnectionError):
                await client.check_drift(
                    CanonicalMetric.ENERGY_PER_UNIT, sample_data,
                )

    @pytest.mark.asyncio
    async def test_check_drift_queries_correct_goal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            await client.check_drift(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data,
            )
            mock_f.assert_called_once_with("ENERGY_DRIFT_CHECK")

    @pytest.mark.asyncio
    async def test_check_drift_periods_in_result(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_DRIFT_RESULTS
            result = await client.check_drift(
                CanonicalMetric.ENERGY_PER_UNIT, sample_data, periods=14,
            )
            assert result.periods_analyzed > 0


# =========================================================================
# Forecast Tests
# =========================================================================


class TestHttpClientForecast:
    """Test forecast_metric with mocked GraphQL responses."""

    @pytest.mark.asyncio
    async def test_forecast_metric_returns_report_type(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_FORECAST_RESULTS
            result = await client.forecast_metric(
                CanonicalMetric.ENERGY_PER_UNIT,
                sample_data,
                horizon_periods=7,
                asset_id="Line-1",
            )

        assert isinstance(result, ForecastReport)
        assert result.available is True
        assert result.predicted_value == 2.75

    @pytest.mark.asyncio
    async def test_forecast_metric_queries_correct_goal(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            await client.forecast_metric(
                CanonicalMetric.ENERGY_PER_UNIT,
                sample_data,
            )

        mock_f.assert_called_once_with("ENERGY_FORECAST")

    @pytest.mark.asyncio
    async def test_forecast_metric_falls_back_when_prevention_returns_no_rows(
        self, client: HttpPreventionClient,
    ) -> None:
        data_points = _make_data_points(
            [10.0, 10.5, 10.8, 11.1, 11.5, 11.8, 12.0, 12.4, 12.9, 13.1],
        )
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = []
            result = await client.forecast_metric(
                CanonicalMetric.ENERGY_PER_UNIT,
                data_points,
                horizon_periods=7,
                asset_id="Line-1",
            )

        assert result.available is True
        assert result.method_name == "local_linear_forecast_fallback"
        assert result.predicted_value is not None
        assert result.training_points == 10

    @pytest.mark.asyncio
    async def test_forecast_metric_falls_back_when_prevention_unreachable(
        self, client: HttpPreventionClient,
    ) -> None:
        data_points = _make_data_points([float(v) for v in range(10, 22)])
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.side_effect = ConnectionError("unreachable")
            result = await client.forecast_metric(
                CanonicalMetric.SCRAP_RATE,
                data_points,
                horizon_periods=7,
                asset_id="Line-1",
            )

        assert result.available is True
        assert result.method_name == "local_linear_forecast_fallback"

    @pytest.mark.asyncio
    async def test_forecast_metric_missing_row_returns_unavailable(
        self, client: HttpPreventionClient, sample_data: list[DataPoint],
    ) -> None:
        with patch.object(client, "_fetch_results", new_callable=AsyncMock) as mock_f:
            mock_f.return_value = MOCK_FORECAST_RESULTS
            result = await client.forecast_metric(
                CanonicalMetric.ENERGY_PER_UNIT,
                sample_data,
                asset_id="Line-2",
            )

        assert result.available is False
        assert result.predicted_value is None
        assert "No forecast data found" in result.description


# =========================================================================
# Metric-to-Goal Mapping Tests
# =========================================================================


class TestMetricToGoalMapping:
    """Verify all canonical metrics map to analytics goals."""

    def test_all_categories_have_anomaly_goal(self) -> None:
        categories = set(METRIC_CATEGORY_MAP.values())
        for cat in categories:
            assert cat in _CATEGORY_TO_ANOMALY_GOAL, (
                f"Category '{cat}' has no anomaly goal"
            )

    def test_all_drift_categories_covered(self) -> None:
        drift_categories = {"energy", "production", "material", "carbon", "supplier"}
        for cat in drift_categories:
            assert cat in _CATEGORY_TO_DRIFT_GOAL, (
                f"Category '{cat}' has no drift goal"
            )

    def test_all_forecast_categories_covered(self) -> None:
        forecast_categories = {"energy", "production", "material", "carbon", "supplier"}
        for cat in forecast_categories:
            assert cat in _CATEGORY_TO_FORECAST_GOAL, (
                f"Category '{cat}' has no forecast goal"
            )

    def test_energy_metrics_map_to_energy_goals(self) -> None:
        energy_metrics = [k for k, v in METRIC_CATEGORY_MAP.items() if v == "energy"]
        assert len(energy_metrics) >= 3
        assert _CATEGORY_TO_ANOMALY_GOAL["energy"] == "ENERGY_ANOMALY_CHECK"
        assert _CATEGORY_TO_DRIFT_GOAL["energy"] == "ENERGY_DRIFT_CHECK"
        assert _CATEGORY_TO_FORECAST_GOAL["energy"] == "ENERGY_FORECAST"

    def test_carbon_has_drift_goal(self) -> None:
        assert _CATEGORY_TO_DRIFT_GOAL["carbon"] == "CO2_DRIFT_CHECK"


# =========================================================================
# Result Parsing Tests
# =========================================================================


class TestAnomalyResultParsing:
    """Test _parse_anomaly_results function."""

    def test_parses_worst_anomaly(self) -> None:
        result = _parse_anomaly_results(
            MOCK_ANOMALY_RESULTS,
            CanonicalMetric.ENERGY_PER_UNIT,
            "energy",
            [],
            2.0,
        )
        assert result.is_anomalous is True
        assert result.severity == "critical"
        assert result.anomaly_type == "spike"
        assert result.deviation == 4.5
        assert result.actual_value == 20.0

    def test_returns_normal_when_no_match(self) -> None:
        results_for_other_metric = [
            {
                "metric_name": "oee",
                "is_anomalous": True,
                "z_score": 3.0,
                "severity": "high",
            },
        ]
        result = _parse_anomaly_results(
            results_for_other_metric,
            CanonicalMetric.ENERGY_PER_UNIT,
            "energy",
            [],
            2.0,
        )
        assert result.is_anomalous is False

    def test_frozen_result(self) -> None:
        result = _parse_anomaly_results(
            MOCK_ANOMALY_RESULTS,
            CanonicalMetric.ENERGY_PER_UNIT,
            "energy",
            [],
            2.0,
        )
        with pytest.raises(AttributeError):
            result.severity = "low"  # type: ignore[misc]


class TestDriftResultParsing:
    """Test _parse_drift_results function."""

    def test_parses_drift_result(self) -> None:
        result = _parse_drift_results(
            MOCK_DRIFT_RESULTS, CanonicalMetric.ENERGY_PER_UNIT, 7,
        )
        assert result.has_drift is True
        assert result.drift_direction == "degrading"
        assert result.drift_rate == 0.0035

    def test_parses_drift_result_for_asset(self) -> None:
        results = [
            {
                "metric_name": "energy_per_unit",
                "asset_id": "Line-2",
                "has_drift": True,
                "drift_direction": "decreasing",
                "drift_rate": -0.0025,
                "periods_analyzed": 12,
                "description": "energy_per_unit on Line-2: decreasing",
            },
            {
                "metric_name": "energy_per_unit",
                "asset_id": "Line-1",
                "has_drift": True,
                "drift_direction": "increasing",
                "drift_rate": 0.0035,
                "periods_analyzed": 16,
                "description": "energy_per_unit on Line-1: increasing",
            },
        ]

        result = _parse_drift_results(
            results,
            CanonicalMetric.ENERGY_PER_UNIT,
            7,
            asset_id="Line-2",
        )

        assert result.has_drift is True
        assert result.drift_direction == "improving"
        assert result.periods_analyzed == 12

    def test_returns_stable_when_no_match(self) -> None:
        result = _parse_drift_results(
            MOCK_DRIFT_RESULTS, CanonicalMetric.OEE, 7,
        )
        assert result.has_drift is False
        assert result.drift_direction == "stable"

    def test_frozen_result(self) -> None:
        result = _parse_drift_results(
            MOCK_DRIFT_RESULTS, CanonicalMetric.ENERGY_PER_UNIT, 7,
        )
        with pytest.raises(AttributeError):
            result.drift_rate = 0.0  # type: ignore[misc]


class TestForecastResultParsing:
    """Test _parse_forecast_results function."""

    def test_parses_forecast_result_for_asset(self) -> None:
        result = _parse_forecast_results(
            MOCK_FORECAST_RESULTS,
            CanonicalMetric.ENERGY_PER_UNIT,
            7,
            asset_id="Line-1",
        )

        assert result.available is True
        assert result.asset_id == "Line-1"
        assert result.predicted_value == 2.75
        assert result.confidence == 0.82
        assert result.fit_quality == 0.74
        assert result.training_points == 30
        assert result.method_name == "linear_forecast"
        assert result.recommended_action is not None

    def test_returns_unavailable_when_no_match(self) -> None:
        result = _parse_forecast_results(
            MOCK_FORECAST_RESULTS,
            CanonicalMetric.OEE,
            7,
        )

        assert result.available is False
        assert result.predicted_value is None
        assert "No forecast data found" in result.description

    def test_returns_unavailable_when_prediction_missing(self) -> None:
        results = [
            {
                **MOCK_FORECAST_RESULTS[0],
                "predicted_value": None,
                "available": True,
            }
        ]

        result = _parse_forecast_results(
            results,
            CanonicalMetric.ENERGY_PER_UNIT,
            7,
            asset_id="Line-1",
        )

        assert result.available is False
        assert result.predicted_value is None

    def test_local_forecast_fallback_reports_insufficient_data(self) -> None:
        result = _fallback_forecast_result_from_series(
            CanonicalMetric.ENERGY_PER_UNIT,
            _make_data_points([2.5, 2.6, 2.4]),
            horizon_periods=7,
            asset_id="Line-1",
        )

        assert result.available is False
        assert result.training_points == 3
        assert result.method_name == "local_linear_forecast_fallback"

    def test_local_forecast_fallback_handles_flat_data(self) -> None:
        result = _fallback_forecast_result_from_series(
            CanonicalMetric.OEE,
            _make_data_points([90.0] * 10, unit="%"),
            horizon_periods=7,
            asset_id="Line-1",
        )

        assert result.available is True
        assert result.predicted_value == 90.0
        assert result.fit_quality == 1.0

    def test_frozen_result(self) -> None:
        result = _parse_forecast_results(
            MOCK_FORECAST_RESULTS,
            CanonicalMetric.ENERGY_PER_UNIT,
            7,
            asset_id="Line-1",
        )
        with pytest.raises(AttributeError):
            result.predicted_value = 3.0  # type: ignore[misc]


# =========================================================================
# Threshold Sensitivity Tests — verify z_score filtering works
# =========================================================================


class TestThresholdFiltering:
    """Verify _parse_anomaly_results re-filters by z_score, not is_anomalous."""

    MIXED_RESULTS = [
        {
            "metric_name": "energy_per_unit",
            "z_score": 1.5,
            "is_anomalous": True,
            "severity": "low",
            "anomaly_type": "spike",
            "timestamp": "2026-02-10T08:00:00",
            "value": 12.0,
            "asset_id": "Line-1",
        },
        {
            "metric_name": "energy_per_unit",
            "z_score": 3.2,
            "is_anomalous": True,
            "severity": "high",
            "anomaly_type": "spike",
            "timestamp": "2026-02-10T14:00:00",
            "value": 20.0,
            "asset_id": "Line-1",
        },
    ]

    def test_low_threshold_catches_both(self) -> None:
        """At threshold=1.0, both z=1.5 and z=3.2 are anomalous."""
        result = _parse_anomaly_results(
            self.MIXED_RESULTS,
            CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 1.0,
        )
        assert result.is_anomalous is True

    def test_high_threshold_filters_weak_anomaly(self) -> None:
        """At threshold=2.0, only z=3.2 passes; z=1.5 is filtered out."""
        result = _parse_anomaly_results(
            self.MIXED_RESULTS,
            CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert result.is_anomalous is True
        assert result.severity == "high"

    def test_very_high_threshold_filters_all(self) -> None:
        """At threshold=4.0, even z=3.2 is NOT anomalous."""
        result = _parse_anomaly_results(
            self.MIXED_RESULTS,
            CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 4.0,
        )
        assert result.is_anomalous is False

    def test_threshold_ignores_precomputed_flag(self) -> None:
        """A result with is_anomalous=True but z_score below threshold is filtered."""
        flagged_but_weak = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 1.8,
                "is_anomalous": True,
                "severity": "low",
                "anomaly_type": "dip",
                "timestamp": "2026-02-10T09:00:00",
                "value": 5.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            flagged_but_weak,
            CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert result.is_anomalous is False


# =========================================================================
# Severity Invariant Tests (P9.1 Phase 7) — HTTP client parse layer
# =========================================================================


class TestHttpSeverityInvariant:
    """Verify _parse_anomaly_results enforces severity != 'none' for anomalies."""

    def test_server_returns_none_severity_gets_corrected(self) -> None:
        """Backend returns severity='none' with high z_score → corrected to 'low'."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 3.5,
                "is_anomalous": True,
                "severity": "none",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T10:00:00",
                "value": 25.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert result.is_anomalous is True
        assert result.severity != "none"
        assert result.severity == "low"

    def test_valid_severity_preserved(self) -> None:
        """Backend returns severity='high' → kept as-is."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 3.5,
                "is_anomalous": True,
                "severity": "high",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T10:00:00",
                "value": 25.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert result.severity == "high"

    def test_no_anomaly_severity_stays_none(self) -> None:
        """When no results pass threshold, severity='none' is correct."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 1.0,
                "is_anomalous": False,
                "severity": "none",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T10:00:00",
                "value": 5.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert result.is_anomalous is False
        assert result.severity == "none"

    @pytest.mark.parametrize("threshold", [1.0, 1.5, 2.0, 2.5, 3.0])
    def test_invariant_across_thresholds(self, threshold: float) -> None:
        """For any threshold: anomalous → severity != 'none'."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 3.2,
                "is_anomalous": True,
                "severity": "none",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T12:00:00",
                "value": 18.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], threshold,
        )
        if result.is_anomalous:
            assert result.severity != "none", (
                f"threshold={threshold}: anomalous but severity='none'"
            )
        else:
            assert result.severity == "none"


# =========================================================================
# Multi-Result Description Tests (P9.1 Phase 4 & 7)
# =========================================================================


class TestHttpMultiResultParsing:
    """Verify multi-result descriptions include count and worst z-score."""

    def test_single_result_no_count_suffix(self) -> None:
        """Single anomalous result: no parenthetical count appended."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 3.0,
                "is_anomalous": True,
                "severity": "high",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T10:00:00",
                "value": 20.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert "anomalous readings detected" not in result.description

    def test_multiple_results_include_count(self) -> None:
        """Two anomalous results: description includes count."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 2.5,
                "is_anomalous": True,
                "severity": "medium",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T08:00:00",
                "value": 15.0,
                "asset_id": "Line-1",
            },
            {
                "metric_name": "energy_per_unit",
                "z_score": 4.0,
                "is_anomalous": True,
                "severity": "critical",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T14:00:00",
                "value": 30.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert result.is_anomalous is True
        assert "2 anomalous readings detected" in result.description
        assert "4.0σ" in result.description

    def test_multi_result_shows_worst_zscore(self) -> None:
        """Multi-result description shows the z-score of the worst reading."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 2.1,
                "is_anomalous": True,
                "severity": "low",
                "anomaly_type": "dip",
                "timestamp": "2026-02-10T06:00:00",
                "value": 8.0,
                "asset_id": "Line-1",
            },
            {
                "metric_name": "energy_per_unit",
                "z_score": 2.8,
                "is_anomalous": True,
                "severity": "medium",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T12:00:00",
                "value": 17.0,
                "asset_id": "Line-1",
            },
            {
                "metric_name": "energy_per_unit",
                "z_score": 5.1,
                "is_anomalous": True,
                "severity": "critical",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T18:00:00",
                "value": 40.0,
                "asset_id": "Line-1",
            },
        ]
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.0,
        )
        assert "3 anomalous readings detected" in result.description
        assert "5.1σ" in result.description
        assert result.severity == "critical"

    def test_filtered_count_not_total_count(self) -> None:
        """Count reflects only results above threshold, not total."""
        results = [
            {
                "metric_name": "energy_per_unit",
                "z_score": 1.5,
                "is_anomalous": True,
                "severity": "low",
                "anomaly_type": "dip",
                "timestamp": "2026-02-10T06:00:00",
                "value": 8.0,
                "asset_id": "Line-1",
            },
            {
                "metric_name": "energy_per_unit",
                "z_score": 3.0,
                "is_anomalous": True,
                "severity": "high",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T12:00:00",
                "value": 20.0,
                "asset_id": "Line-1",
            },
            {
                "metric_name": "energy_per_unit",
                "z_score": 4.5,
                "is_anomalous": True,
                "severity": "critical",
                "anomaly_type": "spike",
                "timestamp": "2026-02-10T18:00:00",
                "value": 35.0,
                "asset_id": "Line-1",
            },
        ]
        # threshold=2.5 filters out z=1.5 → only 2 pass
        result = _parse_anomaly_results(
            results, CanonicalMetric.ENERGY_PER_UNIT, "energy", [], 2.5,
        )
        assert "2 anomalous readings detected" in result.description
