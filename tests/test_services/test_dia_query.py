"""Quality corpus and dialogue-state tests for deterministic DIA parsing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from skill.domain.models import Asset, CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult
from skill.services.conversation_state import DialogueState, DialogueStateStore
from skill.services.dia_dialogue import remember_kpi_result, try_handle_structured_query
from skill.services.dia_query import QueryOperation, parse_structured_query
from skill.services.dia_response import build_response_metadata

ASSETS = [
    Asset("Line-1", "Line 1", "line", aliases=["line one", "first line"]),
    Asset("Line-2", "Line 2", "line", aliases=["line two", "second line"]),
    Asset("Line-3", "Line 3", "line", aliases=["line three", "third line"]),
]


@pytest.mark.parametrize(
    ("utterance", "operation", "metrics", "assets"),
    [
        ("Show OEE for Line 1", QueryOperation.KPI, (CanonicalMetric.OEE,), ("Line-1",)),
        ("Compare scrap rate for Line 1 versus Line 2", QueryOperation.COMPARE, (CanonicalMetric.SCRAP_RATE,), ("Line-1", "Line-2")),
        ("Rank all lines by energy per unit", QueryOperation.RANK, (CanonicalMetric.ENERGY_PER_UNIT,), ("Line-1", "Line-2", "Line-3")),
        ("Show OEE, scrap rate, and throughput for Line 2", QueryOperation.KPI, (CanonicalMetric.OEE, CanonicalMetric.SCRAP_RATE, CanonicalMetric.THROUGHPUT), ("Line-2",)),
        ("Why did OEE change on Line 3?", QueryOperation.DIAGNOSE, (CanonicalMetric.OEE,), ("Line-3",)),
        ("How is scrap rate calculated?", QueryOperation.DEFINE, (CanonicalMetric.SCRAP_RATE,), ()),
        ("Is OEE good on Line 1?", QueryOperation.TARGET, (CanonicalMetric.OEE,), ("Line-1",)),
        ("What do you recommend for energy per unit on Line 2?", QueryOperation.RECOMMEND, (CanonicalMetric.ENERGY_PER_UNIT,), ("Line-2",)),
        ("What if scrap rate drops by 10 percent on Line 1?", QueryOperation.WHAT_IF, (CanonicalMetric.SCRAP_RATE,), ("Line-1",)),
        ("What is energy consumed on Line 1?", QueryOperation.KPI, (CanonicalMetric.ENERGY_TOTAL,), ("Line-1",)),
        ("How much energy was consumed by Line 3 last month?", QueryOperation.KPI, (CanonicalMetric.ENERGY_TOTAL,), ("Line-3",)),
        ("Show the energy trend for Line 1", QueryOperation.TREND, (CanonicalMetric.ENERGY_PER_UNIT,), ("Line-1",)),
        ("Check all assets for anomalies", QueryOperation.ANOMALY, (), ("Line-1", "Line-2", "Line-3")),
    ],
)
def test_structured_query_resolves_operation_and_all_entities(
    utterance, operation, metrics, assets
) -> None:
    query = parse_structured_query(utterance, assets=ASSETS)

    assert query.operation is operation
    assert query.metrics == metrics
    assert query.asset_ids == assets


def test_unknown_asset_is_explicitly_ambiguous() -> None:
    query = parse_structured_query("Compare OEE for Line 1 and Line-99", assets=ASSETS)

    assert "Line-99 is not configured" in query.ambiguity
    assert "Line 1" in query.ambiguity


def test_energy_cost_is_not_reinterpreted_as_energy_intensity() -> None:
    query = parse_structured_query("What is the energy cost for Line 1?", assets=ASSETS)

    assert not query.metrics
    assert "not a configured canonical metric" in query.ambiguity


def test_unsupported_period_is_not_silently_replaced_with_latest() -> None:
    query = parse_structured_query("Show OEE for Line 1 next month", assets=ASSETS)

    assert query.period is None
    assert "Unsupported time period" in query.ambiguity


def test_simple_kpi_with_unsupported_period_speaks_clarification() -> None:
    spoken: list[tuple[str, dict]] = []
    skill = type("Skill", (), {
        "_dialogue_state_store": None,
        "_extract_utterance_text": staticmethod(lambda message: message.data["utterance"]),
        "_get_asset_registry": staticmethod(lambda: ASSETS),
        "speak": staticmethod(lambda utterance, **kwargs: spoken.append((utterance, kwargs))),
        "settings_service": None,
    })()
    message = type("Message", (), {
        "data": {"utterance": "Show OEE for Line 1 next month"},
        "context": {"source": "avaros-web-ui"},
    })()

    assert try_handle_structured_query(skill, message)
    assert "Unsupported time period" in spoken[0][0]
    assert spoken[0][1]["meta"]["avaros_response"]["response_type"] == "clarification"


def test_definition_mean_phrase_is_not_routed_to_average() -> None:
    query = parse_structured_query("What does OEE mean?", assets=ASSETS)

    assert query.operation is QueryOperation.DEFINE


@pytest.mark.parametrize(
    ("utterance", "metric"),
    (
        ("How much power is OpenEMS Edge consuming?", CanonicalMetric.CONSUMPTION_POWER),
        ("How much power is OpenEMS Edge producing?", CanonicalMetric.PRODUCTION_POWER),
        ("What is the battery state of charge for OpenEMS Edge?", CanonicalMetric.STORAGE_STATE_OF_CHARGE),
        ("What is the battery power for OpenEMS Edge?", CanonicalMetric.STORAGE_POWER),
        ("What is the grid power for OpenEMS Edge?", CanonicalMetric.GRID_POWER),
        ("How much energy has OpenEMS Edge produced?", CanonicalMetric.ENERGY_PRODUCTION_TOTAL),
        ("How much energy has OpenEMS Edge imported from grid?", CanonicalMetric.ENERGY_GRID_IMPORT_TOTAL),
        ("How much energy has OpenEMS Edge exported to grid?", CanonicalMetric.ENERGY_GRID_EXPORT_TOTAL),
    ),
)
def test_parse_live_energy_kpi_query(utterance: str, metric: CanonicalMetric) -> None:
    openems = [Asset("openems-edge", "OpenEMS Edge", "seu")]

    query = parse_structured_query(utterance, assets=openems)

    assert query.operation is QueryOperation.KPI
    assert query.metrics == (metric,)
    assert query.asset_ids == ("openems-edge",)


def test_follow_up_reuses_entities_but_not_conversation_text() -> None:
    prior = DialogueState(
        metrics=(CanonicalMetric.OEE,),
        asset_ids=("Line-1",),
        period=TimePeriod.from_natural_language("last month"),
        operation="kpi",
    )

    query = parse_structured_query("What about Line 2?", assets=ASSETS, prior=prior)

    assert query.metrics == (CanonicalMetric.OEE,)
    assert query.asset_ids == ("Line-2",)
    assert query.period == prior.period
    assert query.operation is QueryOperation.KPI


def test_compare_them_uses_bounded_candidate_evidence() -> None:
    prior = DialogueState(
        metrics=(CanonicalMetric.OEE,),
        asset_ids=("Line-2",),
        period=TimePeriod.today(),
        operation="kpi",
        answer_evidence=({"asset_id": "Line-1"}, {"asset_id": "Line-2"}),
    )

    query = parse_structured_query("Compare them", assets=ASSETS, prior=prior)

    assert query.operation is QueryOperation.COMPARE
    assert query.asset_ids == ("Line-1", "Line-2")


def test_legacy_kpi_result_refreshes_follow_up_state() -> None:
    store = DialogueStateStore()
    skill = type("Skill", (), {"_dialogue_state_store": store})()
    message = type("Message", (), {
        "context": {"session": {"session_id": "browser-1"}},
        "data": {},
    })()
    result = KPIResult(
        metric=CanonicalMetric.OEE,
        value=69,
        unit="%",
        asset_id="Line-1",
        period=TimePeriod.latest(),
        timestamp=datetime.now(timezone.utc),
    )

    remember_kpi_result(skill, message, result)

    state = store.get("browser-1")
    assert state is not None
    assert state.metrics == (CanonicalMetric.OEE,)
    assert state.asset_ids == ("Line-1",)
    assert state.operation == QueryOperation.KPI.value
    assert state.answer_evidence == ({"asset_id": "Line-1"},)


def test_dialogue_store_expires_and_bounds_sessions() -> None:
    store = DialogueStateStore(ttl_minutes=15, max_sessions=2)
    expired = DialogueState(updated_at=datetime.now(timezone.utc) - timedelta(minutes=16))
    store._items["expired"] = expired
    store.put("one", DialogueState())
    store.put("two", DialogueState())
    store.put("three", DialogueState())

    assert store.get("expired") is None
    assert store.get("one") is None
    assert store.get("two") is not None
    assert store.get("three") is not None


def test_kpi_metadata_contains_browser_evidence_contract() -> None:
    observed = datetime(2026, 7, 31, tzinfo=timezone.utc)
    result = KPIResult(
        metric=CanonicalMetric.OEE,
        value=82.5,
        unit="%",
        asset_id="Line-1",
        period=TimePeriod.from_natural_language("July 2026"),
        timestamp=datetime.now(timezone.utc),
        source_observed_at=observed,
        source_period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        source_period_end=observed,
        sample_count=31,
        aggregation="average",
        source_profile="reneryo",
    )

    metadata = build_response_metadata("OEE is 82.5 percent.", result)

    assert metadata["response_type"] == "kpi"
    assert metadata["aggregation"] == "average"
    assert metadata["period"]["label"] == "July 2026"
    assert metadata["source_times"]["observed_at"] == observed.isoformat()
    assert metadata["evidence_rows"][0]["sample_count"] == 31


_CORPUS_METRICS = {
    CanonicalMetric.ENERGY_PER_UNIT: "energy per unit",
    CanonicalMetric.ENERGY_TOTAL: "total energy",
    CanonicalMetric.PEAK_DEMAND: "peak demand",
    CanonicalMetric.PEAK_TARIFF_EXPOSURE: "peak tariff exposure",
    CanonicalMetric.SCRAP_RATE: "scrap rate",
    CanonicalMetric.REWORK_RATE: "rework rate",
    CanonicalMetric.MATERIAL_EFFICIENCY: "material efficiency",
    CanonicalMetric.RECYCLED_CONTENT: "recycled content",
    CanonicalMetric.SUPPLIER_LEAD_TIME: "supplier lead time",
    CanonicalMetric.SUPPLIER_DEFECT_RATE: "supplier defect rate",
    CanonicalMetric.SUPPLIER_ON_TIME: "supplier on time",
    CanonicalMetric.SUPPLIER_CO2_PER_KG: "supplier co2 per kg",
    CanonicalMetric.OEE: "oee",
    CanonicalMetric.THROUGHPUT: "throughput",
    CanonicalMetric.CYCLE_TIME: "cycle time",
    CanonicalMetric.CHANGEOVER_TIME: "changeover time",
    CanonicalMetric.CO2_PER_UNIT: "co2 per unit",
    CanonicalMetric.CO2_TOTAL: "total co2",
    CanonicalMetric.CO2_PER_BATCH: "co2 per batch",
}


def _build_quality_corpus():
    rows = []
    asset_names = ["Line 1", "Line 2", "Line 3"]
    for metric, alias in _CORPUS_METRICS.items():
        for asset_index, asset_name in enumerate(asset_names):
            asset_id = f"Line-{asset_index + 1}"
            rows.extend([
                (f"Please show {alias} for {asset_name}", QueryOperation.KPI, metric, (asset_id,), ""),
                (f"How has {alias} trended on {asset_name}?", QueryOperation.TREND, metric, (asset_id,), ""),
                (f"Is {alias} good for {asset_name}?", QueryOperation.TARGET, metric, (asset_id,), ""),
                (
                    f"Compare {alias} for {asset_name} versus Line {((asset_index + 1) % 3) + 1}",
                    QueryOperation.COMPARE,
                    metric,
                    (asset_id, f"Line-{((asset_index + 1) % 3) + 1}"),
                    "",
                ),
            ])
        rows.extend([
            (f"Show {alias} for Line 1 last month", QueryOperation.KPI, metric, ("Line-1",), "last month"),
            (f"Show {alias} for Line 1 in July 2026", QueryOperation.KPI, metric, ("Line-1",), "July 2026"),
        ])
    return rows


QUALITY_CORPUS = _build_quality_corpus()


def test_quality_corpus_contains_at_least_250_queries() -> None:
    assert len(QUALITY_CORPUS) >= 250


@pytest.mark.parametrize(
    ("utterance", "operation", "metric", "asset_ids", "period_label"),
    QUALITY_CORPUS,
)
def test_250_plus_query_quality_corpus(
    utterance, operation, metric, asset_ids, period_label
) -> None:
    query = parse_structured_query(utterance, assets=ASSETS)

    assert query.operation is operation
    assert query.metrics == (metric,)
    assert query.asset_ids == asset_ids
    if period_label:
        assert query.period is not None
        assert query.period.display_name == period_label


@pytest.mark.parametrize(
    ("utterance", "metric"),
    [
        ("show overal equipment effectivness for line one", CanonicalMetric.OEE),
        ("show througput for line two", CanonicalMetric.THROUGHPUT),
        ("show scrap rte for line three", CanonicalMetric.SCRAP_RATE),
        ("show engery per unit for line one", CanonicalMetric.ENERGY_PER_UNIT),
    ],
)
def test_conservative_typo_tolerance(utterance, metric) -> None:
    query = parse_structured_query(utterance, assets=ASSETS)
    assert query.metrics == (metric,)
