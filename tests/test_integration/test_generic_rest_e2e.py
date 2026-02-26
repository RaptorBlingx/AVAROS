"""Generic REST end-to-end portability evidence tests (P5.5-E05)."""

from __future__ import annotations

import asyncio
import ast
from pathlib import Path
from typing import Any

from aiohttp import web
import pytest
import pytest_asyncio

from skill.adapters.factory import AdapterFactory
from skill.adapters.generic_rest import GenericRestAdapter
from skill.domain.exceptions import AdapterError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import ComparisonResult, KPIResult, TrendResult
from skill.services.settings import PlatformConfig, SettingsService
from skill.use_cases.query_dispatcher import QueryDispatcher


ENERGY_TOTAL_BY_SITE: dict[str, float] = {
    "site-1": 15234.5,
    "site-2": 16800.0,
    "default": 15000.0,
}

PRODUCTION_BY_SITE: dict[str, dict[str, float]] = {
    "site-1": {
        "oee_percent": 87.2,
        "scrap_ppm": 1250.0,
        "good_units": 9840.0,
    },
    "site-2": {
        "oee_percent": 82.6,
        "scrap_ppm": 1500.0,
        "good_units": 9210.0,
    },
    "default": {
        "oee_percent": 85.0,
        "scrap_ppm": 1300.0,
        "good_units": 9500.0,
    },
}

TREND_SERIES: list[dict[str, Any]] = [
    {"timestamp": "2026-02-23T00:00:00Z", "value": 42.1},
    {"timestamp": "2026-02-23T01:00:00Z", "value": 38.7},
    {"timestamp": "2026-02-23T02:00:00Z", "value": 45.2},
]


@pytest_asyncio.fixture
async def acme_server_url() -> str:
    """Start an in-process mock platform server with non-RENERYO schema."""

    async def root(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def energy(request: web.Request) -> web.Response:
        site = request.query.get("site", "default")
        total_kwh = ENERGY_TOTAL_BY_SITE.get(site, ENERGY_TOTAL_BY_SITE["default"])
        return web.json_response(
            {
                "status": "ok",
                "result": {
                    "total_kwh": total_kwh,
                    "peak_kw": 89.3,
                    "readings": 1440,
                },
            },
        )

    async def production(request: web.Request) -> web.Response:
        site = request.query.get("site", "default")
        record = PRODUCTION_BY_SITE.get(site, PRODUCTION_BY_SITE["default"])
        return web.json_response(
            {
                "status": "ok",
                "result": {
                    "oee_percent": record["oee_percent"],
                    "scrap_ppm": record["scrap_ppm"],
                    "good_units": record["good_units"],
                },
            },
        )

    async def energy_trend(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "series": TREND_SERIES})

    app = web.Application()
    app.router.add_get("/", root)
    app.router.add_get("/api/metrics/energy", energy)
    app.router.add_get("/api/metrics/production", production)
    app.router.add_get("/api/metrics/energy/trend", energy_trend)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    assert site._server is not None and site._server.sockets
    port = site._server.sockets[0].getsockname()[1]

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        await runner.cleanup()


@pytest_asyncio.fixture
async def configured_settings(
    acme_server_url: str,
    tmp_path: Path,
) -> SettingsService:
    """Create custom_rest profile and metric mappings for portability flow."""
    db_path = tmp_path / "generic_rest_e2e.sqlite3"
    settings = SettingsService(database_url=f"sqlite:///{db_path}")
    settings.initialize()

    settings.create_profile(
        "acme-custom-rest",
        PlatformConfig(
            platform_type="custom_rest",
            api_url=acme_server_url,
            api_key="acme-secret-token",
            extra_settings={"auth_type": "bearer"},
        ),
    )
    settings.set_active_profile("acme-custom-rest")

    settings.set_metric_mapping(
        "energy_total",
        {
            "endpoint": "/api/metrics/energy?site={asset_id}&from={start_date}&to={end_date}",
            "json_path": "$.result.total_kwh",
            "unit": "kWh",
            "trend_endpoint": (
                "/api/metrics/energy/trend?site={asset_id}&from={start_date}&to={end_date}"
                "&interval=hourly"
            ),
            "trend_json_path": "$.series",
            "transform": None,
        },
    )
    settings.set_metric_mapping(
        "oee",
        {
            "endpoint": "/api/metrics/production?site={asset_id}&from={start_date}&to={end_date}",
            "json_path": "$.result.oee_percent",
            "unit": "%",
            "transform": None,
        },
    )
    settings.set_metric_mapping(
        "scrap_rate",
        {
            "endpoint": "/api/metrics/production?site={asset_id}&from={start_date}&to={end_date}",
            "json_path": "$.result.scrap_ppm",
            "unit": "%",
            "transform": "x/10000",
        },
    )

    try:
        yield settings
    finally:
        settings.close()


@pytest_asyncio.fixture
async def runtime(configured_settings: SettingsService) -> dict[str, Any]:
    """Build factory + initialized adapter + dispatcher for end-to-end queries."""
    factory = AdapterFactory(settings_service=configured_settings)
    adapter = factory.create()
    dispatcher = QueryDispatcher(adapter=adapter)
    await asyncio.to_thread(dispatcher._run_async, adapter.initialize())

    try:
        yield {
            "settings": configured_settings,
            "factory": factory,
            "adapter": adapter,
            "dispatcher": dispatcher,
        }
    finally:
        await asyncio.to_thread(dispatcher.shutdown)


class TestGenericRestEndToEnd:
    """Proves zero-code platform onboarding for any REST API."""

    @pytest.mark.asyncio
    async def test_kpi_energy_total_from_custom_rest(self, runtime: dict[str, Any]) -> None:
        """custom_rest profile -> energy_total query -> correct KPIResult."""
        dispatcher: QueryDispatcher = runtime["dispatcher"]

        result = await asyncio.to_thread(
            dispatcher.get_kpi,
            CanonicalMetric.ENERGY_TOTAL,
            "site-1",
            TimePeriod.last_week(),
        )

        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.ENERGY_TOTAL
        assert result.value == pytest.approx(15234.5)

    @pytest.mark.asyncio
    async def test_kpi_oee_from_custom_rest(self, runtime: dict[str, Any]) -> None:
        """custom_rest profile -> OEE query -> correct KPIResult."""
        dispatcher: QueryDispatcher = runtime["dispatcher"]

        result = await asyncio.to_thread(
            dispatcher.get_kpi,
            CanonicalMetric.OEE,
            "site-1",
            TimePeriod.today(),
        )

        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.OEE
        assert result.value == pytest.approx(87.2)

    @pytest.mark.asyncio
    async def test_kpi_scrap_rate_from_custom_rest(self, runtime: dict[str, Any]) -> None:
        """custom_rest profile -> scrap_rate query -> mapped transform is applied."""
        dispatcher: QueryDispatcher = runtime["dispatcher"]

        result = await asyncio.to_thread(
            dispatcher.get_kpi,
            CanonicalMetric.SCRAP_RATE,
            "site-1",
            TimePeriod.today(),
        )

        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.SCRAP_RATE
        assert result.value == pytest.approx(0.125)

    @pytest.mark.asyncio
    async def test_compare_two_assets(self, runtime: dict[str, Any]) -> None:
        """custom_rest profile -> compare energy for 2 assets -> ComparisonResult."""
        dispatcher: QueryDispatcher = runtime["dispatcher"]

        result = await asyncio.to_thread(
            dispatcher.compare,
            CanonicalMetric.ENERGY_TOTAL,
            ["site-1", "site-2"],
            TimePeriod.last_week(),
        )

        assert isinstance(result, ComparisonResult)
        assert len(result.items) == 2
        values = {item.asset_id: item.value for item in result.items}
        assert values["site-1"] == pytest.approx(15234.5)
        assert values["site-2"] == pytest.approx(16800.0)

    @pytest.mark.asyncio
    async def test_trend_returns_time_series(self, runtime: dict[str, Any]) -> None:
        """custom_rest profile -> energy trend -> TrendResult with data points."""
        dispatcher: QueryDispatcher = runtime["dispatcher"]

        result = await asyncio.to_thread(
            dispatcher.get_trend,
            CanonicalMetric.ENERGY_TOTAL,
            "site-1",
            TimePeriod.last_week(),
            "hourly",
        )

        assert isinstance(result, TrendResult)
        assert len(result.data_points) == 3
        assert result.data_points[0].value == pytest.approx(42.1)
        assert result.data_points[2].value == pytest.approx(45.2)

    @pytest.mark.asyncio
    async def test_supports_capability_mapped_vs_unmapped(self, runtime: dict[str, Any]) -> None:
        """Mapped metrics -> True, unmapped -> False."""
        adapter: GenericRestAdapter = runtime["adapter"]

        assert adapter.supports_capability("energy_total") is True
        assert adapter.supports_capability("oee") is True
        assert adapter.supports_capability("scrap_rate") is True
        assert adapter.supports_capability("supplier_lead_time") is False

    @pytest.mark.asyncio
    async def test_unmapped_metric_raises_clear_error(self, runtime: dict[str, Any]) -> None:
        """Querying an unmapped metric returns clear AdapterError."""
        dispatcher: QueryDispatcher = runtime["dispatcher"]

        with pytest.raises(AdapterError) as exc_info:
            await asyncio.to_thread(
                dispatcher.get_kpi,
                CanonicalMetric.THROUGHPUT,
                "site-1",
                TimePeriod.today(),
            )

        assert exc_info.value.code == "GENERIC_REST_MAPPING_NOT_FOUND"
        assert "No mapping configured for throughput" in exc_info.value.message

    def test_no_reneryo_imports_in_test(self) -> None:
        """Meta-proof: this test file imports no RENERYO adapter module."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("skill.adapters.reneryo")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("skill.adapters.reneryo")

    @pytest.mark.asyncio
    async def test_factory_creates_generic_rest_for_custom_rest_profile(
        self,
        configured_settings: SettingsService,
    ) -> None:
        """AdapterFactory with custom_rest profile -> GenericRestAdapter instance."""
        factory = AdapterFactory(settings_service=configured_settings)
        adapter = factory.create()

        assert isinstance(adapter, GenericRestAdapter)
