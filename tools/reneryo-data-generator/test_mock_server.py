"""
Tests for the Mock RENERYO HTTP Server.

Validates all 19 KPI endpoints, auth checks, trend/comparison modes,
the native measurement endpoint, and deterministic data generation.

Run:
    cd tools/reneryo-mock
    pip install -r requirements.txt pytest httpx
    pytest test_mock_server.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import _PATH_TO_METRIC, app

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def client() -> TestClient:
    """Create a test client for the mock server."""
    return TestClient(app)


AUTH_HEADER = {"Authorization": "Bearer test-token"}
COOKIE_HEADER = {"Cookie": "S=test-session"}


# =========================================================================
# Health endpoint
# =========================================================================


class TestHealth:
    """Health endpoint tests — no auth required."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "reneryo-mock"

    def test_health_reports_19_endpoints(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.json()["endpoints"] == 19


# =========================================================================
# Auth checks
# =========================================================================


class TestAuth:
    """Authentication validation tests."""

    def test_no_auth_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/kpis/energy/per-unit")
        assert resp.status_code == 401

    def test_bearer_token_returns_200(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/kpis/energy/per-unit", headers=AUTH_HEADER
        )
        assert resp.status_code == 200

    def test_cookie_auth_returns_200(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/kpis/energy/per-unit", headers=COOKIE_HEADER
        )
        assert resp.status_code == 200

    def test_empty_bearer_returns_401(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/kpis/energy/per-unit",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401


# =========================================================================
# All 19 KPI endpoints
# =========================================================================


class TestKPIEndpoints:
    """Verify all 19 KPI endpoints return valid responses."""

    @pytest.mark.parametrize("path,metric", list(_PATH_TO_METRIC.items()))
    def test_endpoint_returns_200(
        self, client: TestClient, path: str, metric: str
    ) -> None:
        resp = client.get(path, headers=AUTH_HEADER)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"

    @pytest.mark.parametrize("path,metric", list(_PATH_TO_METRIC.items()))
    def test_endpoint_response_schema(
        self, client: TestClient, path: str, metric: str
    ) -> None:
        resp = client.get(path, headers=AUTH_HEADER)
        body = resp.json()
        assert body["metric_name"] == metric
        assert "value" in body
        assert "unit" in body
        assert "timestamp" in body
        assert "asset_id" in body
        assert "metadata" in body
        assert body["metadata"]["source"] == "reneryo-mock"

    def test_all_19_endpoints_registered(self) -> None:
        assert len(_PATH_TO_METRIC) == 19


# =========================================================================
# Trend mode
# =========================================================================


class TestTrendMode:
    """Trend query parameter returns array of data points."""

    def test_granularity_daily_returns_array(
        self, client: TestClient
    ) -> None:
        resp = client.get(
            "/api/v1/kpis/energy/per-unit",
            params={"granularity": "daily"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 3

    def test_granularity_hourly_returns_array(
        self, client: TestClient
    ) -> None:
        resp = client.get(
            "/api/v1/kpis/production/oee",
            params={"granularity": "hourly"},
            headers=AUTH_HEADER,
        )
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 3

    def test_trend_points_have_timestamps(
        self, client: TestClient
    ) -> None:
        resp = client.get(
            "/api/v1/kpis/energy/per-unit",
            params={"granularity": "daily"},
            headers=AUTH_HEADER,
        )
        for point in resp.json():
            assert "timestamp" in point
            assert "value" in point
            assert "unit" in point

    def test_trend_with_datetime_range(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/kpis/energy/per-unit",
            params={
                "granularity": "daily",
                "datetimeMin": "2026-02-01T00:00:00",
                "datetimeMax": "2026-02-10T00:00:00",
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 3


# =========================================================================
# Comparison mode
# =========================================================================


class TestComparisonMode:
    """Comparison query returns per-asset array."""

    def test_asset_ids_returns_array(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/kpis/production/oee",
            params={"asset_ids": "Line-1,Line-2,Line-3"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3

    def test_comparison_items_have_asset_ids(
        self, client: TestClient
    ) -> None:
        resp = client.get(
            "/api/v1/kpis/production/oee",
            params={"asset_ids": "Line-1,Line-2"},
            headers=AUTH_HEADER,
        )
        asset_ids = {item["asset_id"] for item in resp.json()}
        assert asset_ids == {"Line-1", "Line-2"}


# =========================================================================
# Native measurement endpoint
# =========================================================================


class TestNativeMeasurement:
    """Test the Reneryo native-format endpoint."""

    def test_native_returns_array(self, client: TestClient) -> None:
        resp = client.get(
            "/api/u/measurement/meter/item",
            params={"metric": "energy_per_unit", "meter": "Line-1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_native_response_format(self, client: TestClient) -> None:
        resp = client.get(
            "/api/u/measurement/meter/item",
            params={"metric": "energy_per_unit"},
            headers=AUTH_HEADER,
        )
        item = resp.json()[0]
        assert "id" in item
        assert "meter" in item
        assert "value" in item
        assert "unit" in item
        assert "datetime" in item
        assert "type" in item

    def test_native_requires_auth(self, client: TestClient) -> None:
        resp = client.get(
            "/api/u/measurement/meter/item",
            params={"metric": "energy_per_unit"},
        )
        assert resp.status_code == 401


# =========================================================================
# Deterministic data
# =========================================================================


class TestDeterminism:
    """Same request must produce same response."""

    def test_same_request_same_response(self, client: TestClient) -> None:
        url = "/api/v1/kpis/energy/per-unit"
        params = {"asset_id": "Line-1", "period": "today"}
        resp1 = client.get(url, params=params, headers=AUTH_HEADER)
        resp2 = client.get(url, params=params, headers=AUTH_HEADER)
        # Value should be identical (deterministic seed)
        assert resp1.json()["value"] == resp2.json()["value"]

    def test_different_asset_different_value(
        self, client: TestClient
    ) -> None:
        url = "/api/v1/kpis/energy/per-unit"
        resp1 = client.get(
            url, params={"asset_id": "Line-1"}, headers=AUTH_HEADER
        )
        resp2 = client.get(
            url, params={"asset_id": "Line-2"}, headers=AUTH_HEADER
        )
        # Different assets should (very likely) produce different values
        assert resp1.json()["value"] != resp2.json()["value"]

    def test_trend_deterministic(self, client: TestClient) -> None:
        url = "/api/v1/kpis/energy/per-unit"
        params = {"granularity": "daily", "asset_id": "Line-1"}
        resp1 = client.get(url, params=params, headers=AUTH_HEADER)
        resp2 = client.get(url, params=params, headers=AUTH_HEADER)
        vals1 = [p["value"] for p in resp1.json()]
        vals2 = [p["value"] for p in resp2.json()]
        assert vals1 == vals2
