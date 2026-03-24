"""
Tests for HttpPreventionClient (GraphQL-based PREVENTION integration).

Tests GraphQL query construction, response parsing, lifecycle,
and fallback behavior. Uses mocked httpx responses — no real
PREVENTION service needed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skill.clients.prevention import PreventionClient
from skill.clients.prevention_http import (
    HttpPreventionClient,
    _build_graphql_query,
    _parse_anomaly_results,
    _parse_drift_results,
    _resolve_anomaly_goal,
    _resolve_drift_goal,
)
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport
from skill.domain.models import CanonicalMetric


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def http_client() -> HttpPreventionClient:
    """Create an HttpPreventionClient pointed at a fake URL."""
    return HttpPreventionClient(
        base_url="http://prevention:8082",
        addon_name="avaros",
        timeout=5.0,
    )


# =========================================================================
# GraphQL Query Builder
# =========================================================================


class TestBuildGraphqlQuery:
    """Test the GraphQL query string builder."""

    def test_contains_analytics_goal(self) -> None:
        """Query must include the analytics goal string."""
        query = _build_graphql_query("ENERGY_ANOMALY_CHECK")
        assert "ENERGY_ANOMALY_CHECK" in query

    def test_contains_result_request(self) -> None:
        """Query must use the resultRequest field."""
        query = _build_graphql_query("PRODUCTION_DRIFT_CHECK")
        assert "resultRequest" in query

    def test_contains_request_from(self) -> None:
        """Query must include requestFrom: DA."""
        query = _build_graphql_query("TEST_GOAL")
        assert '"DA"' in query

    def test_requests_results_and_reason(self) -> None:
        """Query must request both results and reason fields."""
        query = _build_graphql_query("TEST_GOAL")
        assert "results" in query
        assert "reason" in query


# =========================================================================
# Goal Resolution
# =========================================================================


class TestResolveGoals:
    """Test canonical metric to PREVENTION goal mapping."""

    @pytest.mark.parametrize("metric,expected", [
        (CanonicalMetric.ENERGY_PER_UNIT, "ENERGY_ANOMALY_CHECK"),
        (CanonicalMetric.OEE, "PRODUCTION_ANOMALY_CHECK"),
        (CanonicalMetric.SCRAP_RATE, "MATERIAL_ANOMALY_CHECK"),
        (CanonicalMetric.CO2_PER_UNIT, "CO2_ANOMALY_CHECK"),
        (CanonicalMetric.SUPPLIER_LEAD_TIME, "SUPPLIER_ANOMALY_CHECK"),
    ])
    def test_anomaly_goal_mapping(
        self, metric: CanonicalMetric, expected: str,
    ) -> None:
        """Each metric category maps to the correct anomaly goal."""
        assert _resolve_anomaly_goal(metric) == expected

    @pytest.mark.parametrize("metric,expected", [
        (CanonicalMetric.ENERGY_PER_UNIT, "ENERGY_DRIFT_CHECK"),
        (CanonicalMetric.OEE, "PRODUCTION_DRIFT_CHECK"),
        (CanonicalMetric.SCRAP_RATE, "MATERIAL_DRIFT_CHECK"),
        (CanonicalMetric.CO2_PER_UNIT, "CO2_DRIFT_CHECK"),
        (CanonicalMetric.SUPPLIER_LEAD_TIME, "SUPPLIER_DRIFT_CHECK"),
    ])
    def test_drift_goal_mapping(
        self, metric: CanonicalMetric, expected: str,
    ) -> None:
        """Each metric category maps to the correct drift goal."""
        assert _resolve_drift_goal(metric) == expected


# =========================================================================
# Anomaly Response Parsing
# =========================================================================


class TestParseAnomalyResults:
    """Test PREVENTION anomaly response parsing."""

    def test_empty_results_no_anomaly(self) -> None:
        """Empty results list means no anomalies."""
        result = _parse_anomaly_results(CanonicalMetric.OEE, [])
        assert isinstance(result, AnomalyDetectionResult)
        assert result.is_anomalous is False
        assert result.severity == "none"

    def test_anomalous_records_detected(self) -> None:
        """Anomalous records in results trigger is_anomalous=True."""
        raw = [{
            "results": [
                {"is_anomalous": True, "severity": "high", "z_score": 3.5},
                {"is_anomalous": False, "severity": "none", "z_score": 0.2},
            ],
        }]
        result = _parse_anomaly_results(CanonicalMetric.ENERGY_PER_UNIT, raw)
        assert result.is_anomalous is True
        assert result.severity == "high"

    def test_json_string_results_parsed(self) -> None:
        """Results encoded as JSON string should be parsed."""
        records = json.dumps([
            {"is_anomalous": True, "severity": "medium", "z_score": 2.5},
        ])
        raw = [{"results": records}]
        result = _parse_anomaly_results(CanonicalMetric.OEE, raw)
        assert result.is_anomalous is True

    def test_confidence_bounded(self) -> None:
        """Confidence must not exceed 0.95."""
        raw = [{
            "results": [
                {"is_anomalous": True, "severity": "critical", "z_score": 10.0},
            ],
        }]
        result = _parse_anomaly_results(CanonicalMetric.OEE, raw)
        assert result.confidence <= 0.95

    def test_metric_preserved(self) -> None:
        """Result metric must match input metric."""
        result = _parse_anomaly_results(CanonicalMetric.SCRAP_RATE, [])
        assert result.metric == CanonicalMetric.SCRAP_RATE


# =========================================================================
# Drift Response Parsing
# =========================================================================


class TestParseDriftResults:
    """Test PREVENTION drift response parsing."""

    def test_empty_results_no_drift(self) -> None:
        """Empty results means no drift."""
        result = _parse_drift_results(CanonicalMetric.OEE, [])
        assert isinstance(result, DriftReport)
        assert result.has_drift is False
        assert result.drift_direction == "stable"

    def test_drift_record_parsed(self) -> None:
        """Drift data is correctly mapped to DriftReport."""
        raw = [{
            "results": [{
                "has_drift": True,
                "drift_direction": "increasing",
                "drift_rate": 0.05,
                "periods_analyzed": 14,
                "description": "Upward trend detected.",
            }],
        }]
        result = _parse_drift_results(CanonicalMetric.ENERGY_PER_UNIT, raw)
        assert result.has_drift is True
        assert result.drift_direction == "increasing"
        assert result.drift_rate == 0.05
        assert result.periods_analyzed == 14


# =========================================================================
# HttpPreventionClient Lifecycle
# =========================================================================


class TestHttpPreventionClientLifecycle:
    """Test lifecycle methods of HttpPreventionClient."""

    def test_is_prevention_client(
        self, http_client: HttpPreventionClient,
    ) -> None:
        """Must be a PreventionClient subclass."""
        assert isinstance(http_client, PreventionClient)

    def test_service_name(self, http_client: HttpPreventionClient) -> None:
        """service_name must return a non-empty string."""
        assert isinstance(http_client.service_name, str)
        assert len(http_client.service_name) > 0

    def test_not_connected_before_init(
        self, http_client: HttpPreventionClient,
    ) -> None:
        """Client must not be connected before initialize()."""
        assert http_client.is_connected is False

    @pytest.mark.asyncio
    async def test_initialize_sets_connected(
        self, http_client: HttpPreventionClient,
    ) -> None:
        """initialize() must set is_connected to True."""
        await http_client.initialize()
        assert http_client.is_connected is True
        await http_client.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_clears_connected(
        self, http_client: HttpPreventionClient,
    ) -> None:
        """shutdown() must clear is_connected."""
        await http_client.initialize()
        await http_client.shutdown()
        assert http_client.is_connected is False

    @pytest.mark.asyncio
    async def test_health_check_false_without_init(
        self, http_client: HttpPreventionClient,
    ) -> None:
        """health_check() returns False when not initialized."""
        assert await http_client.health_check() is False

    def test_graphql_url(self, http_client: HttpPreventionClient) -> None:
        """GraphQL URL must combine base_url and addon_name."""
        assert http_client._graphql_url == "http://prevention:8082/avaros"


# =========================================================================
# Execute Query (mocked HTTP)
# =========================================================================


class TestExecuteQuery:
    """Test _execute_query with mocked httpx responses."""

    @pytest.mark.asyncio
    async def test_raises_when_not_initialized(
        self, http_client: HttpPreventionClient,
    ) -> None:
        """Must raise ConnectionError if not initialized."""
        with pytest.raises(ConnectionError):
            await http_client._execute_query("TEST_GOAL")

    @pytest.mark.asyncio
    async def test_successful_query(
        self, http_client: HttpPreventionClient,
    ) -> None:
        """Successful GraphQL response returns result list."""
        await http_client.initialize()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "resultRequest": [
                    {"results": [{"is_anomalous": False}], "reason": []},
                ],
            },
        }
        http_client._client.post = AsyncMock(return_value=mock_response)

        results = await http_client._execute_query("ENERGY_ANOMALY_CHECK")
        assert len(results) == 1
        await http_client.shutdown()
