"""
Tests for reneryo_client.py — Async Reneryo API client.

Validates auth handling, retry logic, batch splitting on 500,
and all CRUD operations using mocked HTTP responses.

Run:
    cd tools/reneryo-mock
    pip install -r requirements.txt pytest pytest-asyncio respx
    pytest tests/test_reneryo_client.py -v
"""

from __future__ import annotations

import pytest
import httpx
import respx

from reneryo_client import (
    ReneryoApiError,
    ReneryoAuthError,
    ReneryoClient,
    ReneryoClientError,
    ReneryoServerError,
)

BASE_URL = "http://test-reneryo:31290/api"
COOKIE = "test-session-cookie"


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def client() -> ReneryoClient:
    """Create a client with test credentials."""
    return ReneryoClient(base_url=BASE_URL, session_cookie=COOKIE)


# =========================================================================
# Auth tests
# =========================================================================


class TestAuth:
    """Authentication configuration tests."""

    def test_missing_cookie_raises(self) -> None:
        with pytest.raises(ReneryoAuthError, match="RENERYO_SESSION_COOKIE"):
            ReneryoClient(base_url=BASE_URL, session_cookie="")

    def test_cookie_header_set(self, client: ReneryoClient) -> None:
        assert client._cookie_header == f"S={COOKIE}"

    def test_cookie_with_prefix_not_doubled(self) -> None:
        c = ReneryoClient(base_url=BASE_URL, session_cookie="S=abc123")
        assert c._cookie_header == "S=abc123"


# =========================================================================
# Request retry tests
# =========================================================================


class TestRetryLogic:
    """5xx retry and error classification tests."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_retry_on_500(self, client: ReneryoClient) -> None:
        """500 → retry → success on second attempt."""
        route = respx.get(f"{BASE_URL}/u/measurement/metric/item").mock(
            side_effect=[
                httpx.Response(500, text="Server Error"),
                httpx.Response(200, json={"records": []}),
            ]
        )
        async with client:
            result = await client.list_metrics()
        assert result == []
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, client: ReneryoClient) -> None:
        """3 consecutive 500s → ReneryoServerError."""
        respx.get(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(500, text="Crash")
        )
        async with client:
            with pytest.raises(ReneryoServerError, match="500"):
                await client.list_metrics()

    @respx.mock
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, client: ReneryoClient) -> None:
        respx.get(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        async with client:
            with pytest.raises(ReneryoAuthError, match="401"):
                await client.list_metrics()

    @respx.mock
    @pytest.mark.asyncio
    async def test_400_raises_api_error(self, client: ReneryoClient) -> None:
        respx.post(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        async with client:
            with pytest.raises(ReneryoApiError, match="400"):
                await client.create_metric("test")

    @respx.mock
    @pytest.mark.asyncio
    async def test_404_raises_api_error(self, client: ReneryoClient) -> None:
        respx.get(
            f"{BASE_URL}/u/measurement/metric/resource/bad-id/values"
        ).mock(return_value=httpx.Response(404, text="Not Found"))
        async with client:
            with pytest.raises(ReneryoApiError, match="404"):
                await client.read_values("bad-id")


# =========================================================================
# Create metric tests
# =========================================================================


class TestCreateMetric:
    """Metric creation tests."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_returns_id(self, client: ReneryoClient) -> None:
        respx.post(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(200, json={"id": "metric-123"})
        )
        async with client:
            result = await client.create_metric("AVAROS Test")
        assert result == "metric-123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_sends_correct_payload(
        self, client: ReneryoClient
    ) -> None:
        route = respx.post(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(200, json={"id": "m1"})
        )
        async with client:
            await client.create_metric(
                "AVAROS OEE", metric_type="GAUGE",
                unit_group="SCALAR", description="OEE %",
            )
        body = route.calls[0].request.content
        import json
        payload = json.loads(body)
        assert payload["name"] == "AVAROS OEE"
        assert payload["type"] == "GAUGE"
        assert payload["unitGroup"] == "SCALAR"
        assert payload["description"] == "OEE %"


# =========================================================================
# Write values tests
# =========================================================================


class TestWriteValues:
    """Value writing and batch splitting tests."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_write_returns_resource_id(
        self, client: ReneryoClient
    ) -> None:
        respx.post(
            f"{BASE_URL}/u/measurement/metric/item/m1/values"
        ).mock(
            return_value=httpx.Response(
                200, json={"resourceId": "res-456"}
            )
        )
        async with client:
            result = await client.write_values(
                "m1", "SCALAR",
                [{"value": 1.0, "datetime": "2026-01-01T00:00:00.000Z"}],
                [{"key": "asset", "value": "Line-1"}],
            )
        assert result == "res-456"

    @respx.mock
    @pytest.mark.asyncio
    async def test_batch_split_on_500(self, client: ReneryoClient) -> None:
        """500 on full batch → split into halves → both succeed."""
        call_count = 0
        values = [
            {"value": float(i), "datetime": f"2026-01-01T{i:02d}:00:00.000Z"}
            for i in range(4)
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            import json
            body = json.loads(request.content)
            if len(body["values"]) > 2:
                return httpx.Response(500, text="Duplicate timestamp")
            return httpx.Response(200, json={"resourceId": "res-split"})

        respx.post(
            f"{BASE_URL}/u/measurement/metric/item/m1/values"
        ).mock(side_effect=handler)

        async with client:
            result = await client.write_values(
                "m1", "SCALAR", values,
                [{"key": "asset", "value": "Line-1"}],
            )
        assert result == "res-split"
        assert call_count >= 3  # 1 fail + 2 halves (minimum)

    @respx.mock
    @pytest.mark.asyncio
    async def test_single_value_500_raises(
        self, client: ReneryoClient
    ) -> None:
        """Single-value batch 500 → cannot split → raises."""
        respx.post(
            f"{BASE_URL}/u/measurement/metric/item/m1/values"
        ).mock(return_value=httpx.Response(500, text="Error"))
        async with client:
            with pytest.raises(ReneryoServerError):
                await client.write_values(
                    "m1", "SCALAR",
                    [{"value": 1.0, "datetime": "2026-01-01T00:00:00.000Z"}],
                    [{"key": "asset", "value": "Line-1"}],
                )


# =========================================================================
# List / read tests
# =========================================================================


class TestListAndRead:
    """Listing and reading tests."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_metrics_returns_records(
        self, client: ReneryoClient
    ) -> None:
        respx.get(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(200, json={
                "records": [{"id": "m1", "name": "AVAROS OEE"}]
            })
        )
        async with client:
            result = await client.list_metrics()
        assert len(result) == 1
        assert result[0]["name"] == "AVAROS OEE"

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_metrics_handles_array_response(
        self, client: ReneryoClient
    ) -> None:
        respx.get(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(
                200, json=[{"id": "m1", "name": "AVAROS OEE"}]
            )
        )
        async with client:
            result = await client.list_metrics()
        assert len(result) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_resources(self, client: ReneryoClient) -> None:
        respx.get(f"{BASE_URL}/u/measurement/metric/resources").mock(
            return_value=httpx.Response(200, json={
                "records": [
                    {"id": "r1", "labels": [{"key": "asset", "value": "Line-1"}]},
                ]
            })
        )
        async with client:
            result = await client.list_resources("m1")
        assert len(result) == 1
        assert result[0]["id"] == "r1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_read_values(self, client: ReneryoClient) -> None:
        respx.get(
            f"{BASE_URL}/u/measurement/metric/resource/r1/values"
        ).mock(
            return_value=httpx.Response(200, json={
                "recordCount": 2,
                "records": [
                    {"value": 82.5, "datetime": "2026-01-01T08:00:00.000Z"},
                    {"value": 83.1, "datetime": "2026-01-01T08:15:00.000Z"},
                ],
            })
        )
        async with client:
            result = await client.read_values(
                "r1",
                datetime_min="2026-01-01T00:00:00Z",
                datetime_max="2026-01-02T00:00:00Z",
            )
        assert result["recordCount"] == 2
        assert len(result["records"]) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_read_values_count_capped_at_100(
        self, client: ReneryoClient
    ) -> None:
        route = respx.get(
            f"{BASE_URL}/u/measurement/metric/resource/r1/values"
        ).mock(
            return_value=httpx.Response(200, json={
                "recordCount": 0, "records": [],
            })
        )
        async with client:
            await client.read_values("r1", count=500)
        # Verify count was capped at 100
        assert route.calls[0].request.url.params["count"] == "100"


# =========================================================================
# Context manager tests
# =========================================================================


class TestContextManager:
    """Lifecycle tests."""

    @pytest.mark.asyncio
    async def test_request_without_context_raises(
        self, client: ReneryoClient
    ) -> None:
        with pytest.raises(ReneryoClientError, match="not initialized"):
            await client.list_metrics()

    @respx.mock
    @pytest.mark.asyncio
    async def test_client_closes_on_exit(
        self, client: ReneryoClient
    ) -> None:
        respx.get(f"{BASE_URL}/u/measurement/metric/item").mock(
            return_value=httpx.Response(200, json={"records": []})
        )
        async with client:
            await client.list_metrics()
        assert client._client is None
