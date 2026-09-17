from datetime import datetime, timedelta, timezone

import pytest

from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMetric, ReneryoTrendPoint
from skill.services.futuregen import FutureGenService


class FakeReneryo:
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
