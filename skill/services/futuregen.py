"""Small orchestration layer for the Reneryo Future Gen conversational slice."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from skill.clients.mdsp import MdspClient
from skill.clients.reneryo import ReneryoClient
from skill.domain.exceptions import ValidationError
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import MdspFinding, MdspFindingList, ReneryoTrend
from skill.services.language import normalize_phrase


class FutureGenService:
    """Coordinate read-only Reneryo and MDSP queries without recalculation."""

    def __init__(self, reneryo: ReneryoClient, mdsp: MdspClient | None = None):
        self.reneryo = reneryo
        self.mdsp = mdsp

    async def meters(self, period: TimePeriod):
        return await self.reneryo.list_meters(period.start, period.end)

    async def metrics(self):
        return await self.reneryo.list_metrics()

    async def trend(self, utterance: str, period: TimePeriod) -> ReneryoTrend:
        metrics = await self.metrics()
        metric = match_metric(utterance, metrics)
        if metric is None:
            raise ValidationError(
                message="No Future Gen metric matched the request",
                code="METRIC_NOT_FOUND",
                user_message="Please name the metric whose trend you want to see.",
            )
        days = max(1, (period.end - period.start).days)
        aggregation = "HOURLY" if days <= 2 else "DAILY" if days <= 120 else "MONTHLY"
        points = await self.reneryo.metric_values(
            metric.metric_id, period.start, period.end, aggregation
        )
        change = 0.0
        if len(points) > 1 and points[0].value != 0:
            change = ((points[-1].value - points[0].value) / abs(points[0].value)) * 100
        direction = "stable"
        if change > 1:
            direction = "increasing"
        elif change < -1:
            direction = "decreasing"
        return ReneryoTrend(
            metric=metric,
            period_label=period.display_name,
            aggregation=aggregation,
            points=tuple(points),
            direction=direction,
            change_percent=change,
        )

    async def regressions(self):
        return await self.reneryo.list_regressions()

    async def findings(self, organization_id: str) -> MdspFindingList:
        if self.mdsp is None:
            raise RuntimeError("MDSP is not configured")
        return await self.mdsp.list_findings(organization_id)

    async def finding(self, organization_id: str, finding_id: str) -> MdspFinding:
        if self.mdsp is None:
            raise RuntimeError("MDSP is not configured")
        return await self.mdsp.get_finding(organization_id, finding_id)


def default_period(days: int = 30) -> TimePeriod:
    end = datetime.now(timezone.utc)
    return TimePeriod(
        start=end - timedelta(days=days), end=end, display_name=f"last {days} days"
    )


def match_metric(utterance: str, metrics):
    """Ground a natural metric reference in Reneryo-owned inventory data."""
    normalized = normalize_phrase(utterance)
    aliases = (
        ("electric", "elektrik", "energy", "enerji"),
        ("production", "uretim", "üretim"),
        ("temperature", "sicaklik", "sıcaklık"),
        ("humidity", "nem"),
        ("heating degree", "isitma", "ısıtma"),
        ("cooling degree", "sogutma", "soğutma"),
        ("rain", "yagmur", "yağmur"),
    )
    for metric in metrics:
        name = normalize_phrase(metric.name)
        if name and (name in normalized or normalized in name):
            return metric
    for terms in aliases:
        normalized_terms = tuple(normalize_phrase(term) for term in terms)
        if any(_contains_alias(normalized, term) for term in normalized_terms):
            return next(
                (
                    metric
                    for metric in metrics
                    if any(
                        _contains_alias(normalize_phrase(metric.name), term)
                        for term in normalized_terms
                    )
                ),
                None,
            )
    return None


def _contains_alias(text: str, alias: str) -> bool:
    """Match an alias at a word start, avoiding fragments such as nem/döneme."""
    return re.search(rf"(?<!\w){re.escape(alias)}", text) is not None
