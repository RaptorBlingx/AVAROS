"""Tests for POST /api/v1/config/metrics/test endpoint."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from fastapi.testclient import TestClient

from skill.services.settings import PlatformConfig, SettingsService


@pytest.fixture(autouse=True)
def active_profile(settings_service: SettingsService) -> None:
    """Ensure test requests run against a non-mock active profile."""
    if settings_service.get_profile("reneryo") is None:
        settings_service.create_profile(
            "reneryo",
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.example.com",
                api_key="server-secret-token",
                extra_settings={"auth_type": "bearer"},
            ),
        )
    settings_service.set_active_profile("reneryo")


class TestMetricMappingValidationEndpoint:
    """Covers metric mapping test endpoint success/error scenarios."""

    def test_test_mapping_valid_returns_value(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(return_value=(200, '{"data": {"energy": 42.5}}')),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["value"] == 42.5
        assert body["error"] is None

    def test_test_mapping_invalid_json_path_returns_error(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.nonexistent.path",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(return_value=(200, '{"data": {"energy": 42.5}}')),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "JSONPath did not resolve to a value"

    def test_test_mapping_supports_wildcard_array_json_path(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.records[*].value",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(
                return_value=(
                    200,
                    '{"records": [{"value": 81.5}, {"value": 82.0}]}',
                ),
            ),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["value"] == 81.5
        assert body["error"] is None

    def test_test_mapping_rejects_absolute_endpoint_url(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "http://169.254.169.254/latest/meta-data",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        fetch_mock = AsyncMock(return_value=(200, '{"data": {"energy": 42.5}}'))
        with patch("services.metric_test_service._fetch_response", new=fetch_mock):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "Connection failed: endpoint must be a relative path"
        assert fetch_mock.await_count == 0

    def test_test_mapping_unreachable_url_returns_error(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(side_effect=aiohttp.ClientConnectionError("refused")),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"].startswith("Connection failed:")

    def test_test_mapping_upstream_4xx_returns_error(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(return_value=(404, '{"error":"missing"}')),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "Connection failed: upstream returned HTTP 404"
        assert body["raw_response_preview"] == '{"error":"missing"}'

    def test_test_mapping_non_numeric_value_returns_error(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(return_value=(200, '{"data": {"energy": "hello"}}')),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "Extracted value is not numeric: hello"

    def test_test_mapping_non_json_response_returns_error(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(return_value=(200, "<html>not-json</html>")),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "Response is not valid JSON"
        assert "<html>" in body["raw_response_preview"]

    def test_test_mapping_bearer_auth_sends_header(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        fetch_mock = AsyncMock(return_value=(200, '{"data": {"energy": 1}}'))
        with patch("services.metric_test_service._fetch_response", new=fetch_mock):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        _, headers, _ = fetch_mock.await_args.args
        assert headers["Authorization"] == "Bearer token-123"

    def test_test_mapping_cookie_auth_sends_header(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "cookie",
            "auth_token": "session-abc",
        }

        fetch_mock = AsyncMock(return_value=(200, '{"data": {"energy": 1}}'))
        with patch("services.metric_test_service._fetch_response", new=fetch_mock):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        _, headers, _ = fetch_mock.await_args.args
        assert headers["Cookie"] == "S=session-abc"

    def test_test_mapping_cookie_auth_uuid_token_sends_dual_cookie_names(
        self,
        client: TestClient,
    ) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "cookie",
            "auth_token": "4efd58f5-c712-4c0d-b329-001122334455",
        }

        fetch_mock = AsyncMock(return_value=(200, '{"data": {"energy": 1}}'))
        with patch("services.metric_test_service._fetch_response", new=fetch_mock):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        _, headers, _ = fetch_mock.await_args.args
        assert headers["Cookie"] == (
            "JSESSIONID=4efd58f5-c712-4c0d-b329-001122334455; "
            "S=4efd58f5-c712-4c0d-b329-001122334455"
        )

    def test_test_mapping_cookie_auth_long_value_with_equals_wraps_s(
        self,
        client: TestClient,
    ) -> None:
        token = (
            "4efd58f5-c712-4c0d-b329-329da0fc8f2e."
            "15lraeYHLMKZIU9Ve8np00eiFWYXn8NZ3vIjaPXebLw="
        )
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "cookie",
            "auth_token": token,
        }

        fetch_mock = AsyncMock(return_value=(200, '{"data": {"energy": 1}}'))
        with patch("services.metric_test_service._fetch_response", new=fetch_mock):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        _, headers, _ = fetch_mock.await_args.args
        assert headers["Cookie"] == f"S={token}"

    def test_test_mapping_none_auth_sends_no_headers(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "none",
            "auth_token": "",
        }

        fetch_mock = AsyncMock(return_value=(200, '{"data": {"energy": 1}}'))
        with patch("services.metric_test_service._fetch_response", new=fetch_mock):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        _, headers, _ = fetch_mock.await_args.args
        assert headers == {}

    def test_test_mapping_timeout_returns_error(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(side_effect=asyncio.TimeoutError),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] == "Connection failed: request timed out"

    def test_test_mapping_empty_endpoint_returns_error(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 422

    def test_test_mapping_raw_response_preview_truncated(self, client: TestClient) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "token-123",
        }

        long_response = "x" * 1000
        with patch(
            "services.metric_test_service._fetch_response",
            new=AsyncMock(return_value=(200, long_response)),
        ):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert len(body["raw_response_preview"]) == 500

    def test_test_mapping_masked_auth_uses_active_profile_secret(
        self,
        client: TestClient,
    ) -> None:
        payload = {
            "base_url": "https://api.example.com",
            "endpoint": "/metrics/energy",
            "json_path": "$.data.energy",
            "auth_type": "bearer",
            "auth_token": "****cret",
        }

        fetch_mock = AsyncMock(return_value=(200, '{"data": {"energy": 1}}'))
        with patch("services.metric_test_service._fetch_response", new=fetch_mock):
            response = client.post("/api/v1/config/metrics/test", json=payload)

        assert response.status_code == 200
        _, headers, _ = fetch_mock.await_args.args
        assert headers["Authorization"] == "Bearer server-secret-token"
