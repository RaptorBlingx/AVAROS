from datetime import datetime, timedelta, timezone

import pytest

from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMetric, ReneryoTrendPoint
from skill.clients.reneryo import ReneryoClient
from skill.services.futuregen import FutureGenService, match_metric


class FakeReneryo:
    async def recent_metric_values(self, metric, count=12):
        return [], 0

    async def list_metrics(self):
        return [
            ReneryoMetric(
                "electricity-id", "Electricity consumption", "COUNTER", "ENERGY"
            )
        ]

    async def metric_values(self, metric_id, start, end, period):
        assert metric_id == "electricity-id"
        assert period == "DAILY"
        return [
            ReneryoTrendPoint(start, 100, 24),
            ReneryoTrendPoint(end, 125, 24),
        ]


class FutureGenNamedReneryo(FakeReneryo):
    async def list_metrics(self):
        return [
            ReneryoMetric(
                "electricity-id",
                "Tesis Toplam Elektrik Tüketimi",
                "COUNTER",
                "ENERGY",
            )
        ]


@pytest.mark.asyncio
async def test_trend_uses_reneryo_aggregates_and_matches_turkish_alias():
    end = datetime.now(timezone.utc)
    period = TimePeriod(end - timedelta(days=30), end, "last 30 days")
    result = await FutureGenService(FakeReneryo()).trend("elektrik eğilimi", period)
    assert result.metric.metric_id == "electricity-id"
    assert result.direction == "increasing"
    assert result.change_percent == 25


@pytest.mark.asyncio
async def test_trend_alias_matches_tenant_metric_in_other_language():
    end = datetime.now(timezone.utc)
    period = TimePeriod(end - timedelta(days=30), end, "last 30 days")
    result = await FutureGenService(FutureGenNamedReneryo()).trend(
        "electricity trend", period
    )
    assert result.metric.metric_id == "electricity-id"


def test_short_metric_alias_does_not_match_inside_unrelated_word():
    metrics = [ReneryoMetric("humidity-id", "Humidity - Open Weather", "GAUGE", "HUMIDITY")]

    result = match_metric("Bu değişim hangi döneme ait?", metrics)

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [[], [(100, 0)], [(0, 0), (100, 1)]])
async def test_trend_does_not_infer_stability_from_insufficient_values(values):
    end = datetime.now(timezone.utc)
    period = TimePeriod(end - timedelta(days=30), end, "last 30 days")

    class SparseReneryo(FakeReneryo):
        async def metric_values(self, metric_id, start, end, aggregation):
            return [
                ReneryoTrendPoint(start + timedelta(days=index), value, 1)
                for value, index in values
            ]

    result = await FutureGenService(SparseReneryo()).trend("electricity trend", period)

    assert result.direction == "unavailable"
    assert result.change_percent is None
    assert len(result.points) == len(values)


def test_metric_correction_uses_replacement_name():
    metrics = [
        ReneryoMetric("humidity-id", "Humidity - Open Weather", "GAUGE", "RATE"),
        ReneryoMetric(
            "electricity-id", "Tesis Toplam Elektrik Tüketimi", "COUNTER", "ENERGY"
        ),
    ]

    assert (
        match_metric("Not humidity, electricity", metrics).metric_id == "electricity-id"
    )
    assert match_metric("Nem değil elektrik", metrics).metric_id == "electricity-id"


@pytest.mark.asyncio
async def test_metric_history_reads_all_pages_before_describing_the_trend():
    client = ReneryoClient("https://example.invalid/api", {"X-Token": "test"})
    requested_pages = []

    async def get(_path, params):
        requested_pages.append(params["page"])
        offset = (int(params["page"]) - 1) * 100
        rows = [
            {
                "datetime": (
                    datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)
                ).isoformat(),
                "value": i,
                "sampleCount": 1,
            }
            for i in range(offset, min(offset + 100, 101))
        ]
        return {"records": rows, "recordCount": 101}

    client._get = get
    points = await client.metric_values(
        "metric-1",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 1, tzinfo=timezone.utc),
        "DAILY",
    )

    assert requested_pages == ["1", "2"]
    assert len(points) == 101
    assert points[-1].value == 100
