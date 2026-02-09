"""
Tests for GET /health liveness endpoint.

Covers:
    - Returns 200 with status and version fields
    - Response body matches expected structure
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the /health liveness endpoint."""

    def test_health_returns_ok_status(self, client: TestClient) -> None:
        """GET /health returns 200 with status 'ok'."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_includes_version(self, client: TestClient) -> None:
        """GET /health response includes a non-empty version string."""
        response = client.get("/health")

        body = response.json()
        assert "version" in body
        assert isinstance(body["version"], str)
        assert len(body["version"]) > 0

    def test_health_only_expected_keys(self, client: TestClient) -> None:
        """GET /health response contains exactly status and version."""
        response = client.get("/health")

        assert set(response.json().keys()) == {"status", "version"}
