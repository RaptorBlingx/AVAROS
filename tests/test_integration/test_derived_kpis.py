"""
Derived KPI Integration Tests

Full pipeline tests exercising QueryDispatcher with supplementary
production data:
    - energy_total from MockAdapter + production data → energy_per_unit
    - energy_total + emission factor + production count → co2_per_unit
    - production data only → material_efficiency
    - Error: no production data → MetricNotSupportedError
"""

from __future__ import annotations

from datetime import date

import pytest

from skill.adapters.mock import MockAdapter
from skill.domain.exceptions import MetricNotSupportedError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.production import ProductionRecord
from skill.domain.results import KPIResult
from skill.services.co2_service import CO2DerivationService
from skill.services.production_data import ProductionDataService
from skill.services.settings import SettingsService
from skill.use_cases.query_dispatcher import QueryDispatcher


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def settings_service() -> SettingsService:
    """In-memory SettingsService."""
    svc = SettingsService()
    svc.initialize()
    return svc


@pytest.fixture
def co2_service(settings_service: SettingsService) -> CO2DerivationService:
    """CO2 service with default TR emission factors."""
    return CO2DerivationService(settings_service)


@pytest.fixture
def production_service() -> ProductionDataService:
    """In-memory ProductionDataService with sample data."""
    svc = ProductionDataService(database_url="sqlite:///:memory:")
    svc.initialize()
    return svc


def _today() -> date:
    """Shortcut for today's date."""
    return date.today()


@pytest.fixture
def production_service_with_data(
    production_service: ProductionDataService,
) -> ProductionDataService:
    """Service pre-loaded with test production records for today."""
    records = [
        ProductionRecord(
            record_date=_today(),
            asset_id="Line-1",
            production_count=500,
            good_count=480,
            material_consumed_kg=120.0,
        ),
        ProductionRecord(
            record_date=_today(),
            asset_id="Line-1",
            production_count=500,
            good_count=490,
            material_consumed_kg=118.0,
        ),
    ]
    production_service.add_records_bulk(records)
    return production_service


@pytest.fixture
def adapter() -> MockAdapter:
    """Real MockAdapter with native_carbon disabled for derivation tests."""
    a = MockAdapter()
    original = a.supports_capability

    def _no_carbon_or_supplementary(cap: str) -> bool:
        """Disable native carbon/supplementary so derivation kicks in."""
        if cap in (
            "native_carbon",
            "native_energy_per_unit",
            "native_material_efficiency",
        ):
            return False
        return original(cap)

    a.supports_capability = _no_carbon_or_supplementary  # type: ignore[assignment]
    return a


@pytest.fixture
def period() -> TimePeriod:
    """Standard test period covering today."""
    return TimePeriod.today()


@pytest.fixture
def dispatcher_with_production(
    adapter: MockAdapter,
    co2_service: CO2DerivationService,
    production_service_with_data: ProductionDataService,
) -> QueryDispatcher:
    """Dispatcher with all services wired."""
    return QueryDispatcher(
        adapter=adapter,
        co2_service=co2_service,
        production_data_service=production_service_with_data,
    )


@pytest.fixture
def dispatcher_no_production(
    adapter: MockAdapter,
    co2_service: CO2DerivationService,
) -> QueryDispatcher:
    """Dispatcher WITHOUT production data service."""
    return QueryDispatcher(
        adapter=adapter,
        co2_service=co2_service,
    )


# ══════════════════════════════════════════════════════════
# energy_per_unit Derivation
# ══════════════════════════════════════════════════════════


class TestEnergyPerUnitDerivation:
    """energy_per_unit = energy_total / production_count."""

    def test_derives_energy_per_unit(
        self, dispatcher_with_production: QueryDispatcher,
        period: TimePeriod,
    ) -> None:
        """Pipeline: MockAdapter energy_total + production → energy_per_unit."""
        result = dispatcher_with_production.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert result.value > 0
        assert result.unit == "kWh/unit"


# ══════════════════════════════════════════════════════════
# co2_per_unit Derivation
# ══════════════════════════════════════════════════════════


class TestCo2PerUnitDerivation:
    """co2_per_unit = (energy × emission_factor) / production_count."""

    def test_derives_co2_per_unit(
        self, dispatcher_with_production: QueryDispatcher,
        period: TimePeriod,
    ) -> None:
        """Full pipeline with emission factors and production data."""
        result = dispatcher_with_production.get_kpi(
            metric=CanonicalMetric.CO2_PER_UNIT,
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.CO2_PER_UNIT
        assert result.value > 0
        assert "CO₂" in result.unit

    def test_co2_per_unit_no_production_service_raises(
        self, dispatcher_no_production: QueryDispatcher,
        period: TimePeriod,
    ) -> None:
        """Without production service, CO2_PER_UNIT raises."""
        with pytest.raises(MetricNotSupportedError, match="production data"):
            dispatcher_no_production.get_kpi(
                metric=CanonicalMetric.CO2_PER_UNIT,
                asset_id="Line-1",
                period=period,
            )


# ══════════════════════════════════════════════════════════
# material_efficiency Derivation
# ══════════════════════════════════════════════════════════


class TestMaterialEfficiencyDerivation:
    """material_efficiency from supplementary data only (no adapter call)."""

    def test_derives_material_efficiency(
        self, dispatcher_with_production: QueryDispatcher,
        period: TimePeriod,
    ) -> None:
        """Pipeline: production data only → material_efficiency."""
        result = dispatcher_with_production.get_kpi(
            metric=CanonicalMetric.MATERIAL_EFFICIENCY,
            asset_id="Line-1",
            period=period,
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.MATERIAL_EFFICIENCY
        assert result.value > 0
        assert result.unit == "%"


# ══════════════════════════════════════════════════════════
# Error Cases
# ══════════════════════════════════════════════════════════


class TestDerivedKpiErrors:
    """Error paths for derived KPIs."""

    def test_no_production_data_for_period(
        self, adapter: MockAdapter,
        co2_service: CO2DerivationService,
    ) -> None:
        """Empty production dataset raises MetricNotSupportedError."""
        empty_service = ProductionDataService(
            database_url="sqlite:///:memory:",
        )
        empty_service.initialize()

        dispatcher = QueryDispatcher(
            adapter=adapter,
            co2_service=co2_service,
            production_data_service=empty_service,
        )

        with pytest.raises(MetricNotSupportedError, match="No production data"):
            dispatcher.get_kpi(
                metric=CanonicalMetric.CO2_PER_UNIT,
                asset_id="Line-1",
                period=TimePeriod.today(),
            )

    def test_dispatcher_without_production_falls_through(self) -> None:
        """Dispatcher without production service can still get normal KPIs."""
        # Use a vanilla MockAdapter (supports all capabilities natively)
        vanilla = MockAdapter()
        dispatcher = QueryDispatcher(adapter=vanilla)

        result = dispatcher.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id="Line-1",
            period=TimePeriod.today(),
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.OEE

    def test_co2_total_still_works(
        self, dispatcher_with_production: QueryDispatcher,
    ) -> None:
        """CO2_TOTAL (no production needed) still works."""
        result = dispatcher_with_production.get_kpi(
            metric=CanonicalMetric.CO2_TOTAL,
            asset_id="Line-1",
            period=TimePeriod.today(),
        )
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.CO2_TOTAL
