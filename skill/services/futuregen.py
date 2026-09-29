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
        change = None
        if len(points) > 1 and points[0].value != 0:
            change = ((points[-1].value - points[0].value) / abs(points[0].value)) * 100
        direction = "unavailable"
        if change is not None and change > 1:
            direction = "increasing"
        elif change is not None and change < -1:
            direction = "decreasing"
        elif change is not None:
            direction = "stable"
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

    async def filtered_findings(
        self,
        organization_id: str,
        *,
        status: str = "ACTIVE",
        severity: str = "",
        domain: str = "",
    ) -> MdspFindingList:
        if self.mdsp is None:
            raise RuntimeError("MDSP is not configured")
        return await self.mdsp.list_findings(
            organization_id, status=status, severity=severity, domain=domain
        )

    async def finding(self, organization_id: str, finding_id: str) -> MdspFinding:
        if self.mdsp is None:
            raise RuntimeError("MDSP is not configured")
        return await self.mdsp.get_finding(organization_id, finding_id)

    async def evaluate(self, organization_id: str):
        if self.mdsp is None:
            raise RuntimeError("MDSP is not configured")
        return await self.mdsp.evaluate(organization_id)


def default_period(days: int = 30) -> TimePeriod:
    end = datetime.now(timezone.utc)
    return TimePeriod(
        start=end - timedelta(days=days), end=end, display_name=f"last {days} days"
    )


def match_metric(utterance: str, metrics):
    """Ground a natural metric reference in Reneryo-owned inventory data."""
    normalized = normalize_phrase(utterance)
    # A correction names the unwanted metric first. Match only the replacement.
    correction = re.match(
        r"^(?:no|not)\b[^,]+,\s*(.+)$", utterance.strip(), re.IGNORECASE
    )
    if correction:
        normalized = normalize_phrase(correction.group(1))
    else:
        turkish_correction = re.match(r"^.+?\b(?:değil|degil)\b\s+(.+)$", normalized)
        if turkish_correction:
            normalized = turkish_correction.group(1)
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
