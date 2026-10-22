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
from skill.services.response_localization import source_metric_label
from skill.services.reneryo_periods import history_resolution


class FutureGenService:
    """Coordinate read-only Reneryo and MDSP queries without recalculation."""

    def __init__(self, reneryo: ReneryoClient, mdsp: MdspClient | None = None):
        self.reneryo = reneryo
        self.mdsp = mdsp

    async def meters(self, period: TimePeriod):
        return await self.reneryo.list_meters(period.start, period.end)

    async def metrics(self):
        return await self.reneryo.list_metrics()

    async def trend(self, utterance: str, period: TimePeriod, *, metric=None, allow_history_fallback: bool = True,
                    period_phrase: str | None = None) -> ReneryoTrend:
        """Read a trend; *period_phrase* is the phrase that selected *period*.

        Callers reusing an already-resolved window pass its phrase so the
        same resolution rules apply as when it was first requested.
        """
        if metric is None:
            references = metric_references(utterance, await self.metrics())
            if len(references) > 1:
                raise ValidationError(message="Ambiguous trend subject", code="METRIC_AMBIGUOUS")
            metric = references[0] if references else None
        if metric is None:
            raise ValidationError(
                message="No Future Gen metric matched the request",
                code="METRIC_NOT_FOUND",
                user_message="Please name the metric whose trend you want to see.",
            )
        days = max(1, (period.end - period.start).days)
        aggregation = "HOURLY" if days <= 2 else "DAILY" if days <= 120 else "MONTHLY"
        # Explicit multi-month counter comparisons request Reneryo's monthly
        # aggregates, not the endpoints of daily readings across both months.
        from skill.services.period_resolution import _NAMED_MONTH_RANGE, extract_period_phrase

        phrase = extract_period_phrase(utterance) if period_phrase is None else period_phrase
        if metric.metric_type == "COUNTER" and _NAMED_MONTH_RANGE.fullmatch(phrase):
            aggregation = "MONTHLY"
        if phrase not in {"", "latest", "en güncel"}:
            aggregation = history_resolution(period, aggregation)
        points = await self.reneryo.metric_values(
            metric.metric_id, period.start, period.end, aggregation
        )
        requested_period_label = ""
        if not points and allow_history_fallback and not phrase:
            historical, _ = await self.reneryo.recent_metric_values(metric)
            if historical:
                requested_period_label = period.display_name
                points = historical
                aggregation = "MONTHLY"
                period = TimePeriod(
                    points[0].timestamp,
                    next_month(points[-1].timestamp),
                    f"available monthly history {points[0].timestamp:%Y-%m} – {points[-1].timestamp:%Y-%m}",
                )
        change = None
        delta = points[-1].value - points[0].value if len(points) > 1 else None
        temperature = metric.unit_group == "TEMPERATURE"
        # Celsius is Reneryo's base temperature unit. Its zero is arbitrary:
        # narrate an endpoint difference, never a relative percentage.
        if delta is not None and not temperature and points[0].value != 0:
            change = (delta / abs(points[0].value)) * 100
        direction = "unavailable"
        directional_change = delta if temperature else change
        threshold = 0 if temperature else 1
        if directional_change is not None:
            direction = (
                "increasing" if directional_change > threshold else
                "decreasing" if directional_change < -threshold else "stable"
            )
        return ReneryoTrend(
            metric=metric,
            period_label=period.display_name,
            aggregation=aggregation,
            points=tuple(points),
            direction=direction,
            change_percent=change,
            change_absolute=delta,
            requested_period_label=requested_period_label,
            period_start=period.start,
            period_end=period.end,
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


def default_period(days: int = 30, *, now: datetime | None = None) -> TimePeriod:
    end = now or datetime.now(timezone.utc)
    return TimePeriod(
        start=end - timedelta(days=days), end=end, display_name=f"last {days} days"
    )


def next_month(value: datetime) -> datetime:
    """Exclusive end of a monthly bucket returned by Reneryo."""
    return value.replace(
        year=value.year + (value.month == 12),
        month=1 if value.month == 12 else value.month + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


_METRIC_ALIASES = (
    ("electric", "elektrik", "energy", "enerji"),
    ("production", "produce", "output", "uretim", "üretim", "üretti", "uretti"),
    ("temperature", "sicaklik", "sıcaklık"),
    ("humidity", "humid", "nem"),
    ("heating degree", "isitma", "ısıtma"),
    ("cooling degree", "sogutma", "soğutma"),
    # "yağış miktarı" is AVAROS's own Turkish label for rain.
    ("rain", "yagmur", "yağmur", "yağış", "yagis", "precipitation"),
)


def _metric_reference_text(utterance: str) -> str:
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
    return normalized


def metric_references(utterance: str, metrics):
    """Return inventory-backed references without choosing an ambiguous subject.

    Exact names narrow aliases within their family. Unlike the legacy single
    match helper, all explicit families must be available; callers must clarify multiple matches.
    """
    text = _key(_metric_reference_text(utterance))
    exact = [m for m in metrics if m.name and (re.search(
        rf"(?<!\w){re.escape(_key(m.name))}(?!\w)", text
    ) or _localized_name_reference(text, m))]
    found = {m.metric_id: m for m in exact}
    for terms in _METRIC_ALIASES:
        if not any(_contains_alias(text, _key(t)) for t in terms):
            continue
        family = [m for m in metrics if any(
            _contains_alias(_key(m.name), _key(t)) for t in terms
        )]
        if not family:
            return []
        selected = [m for m in family if m in exact] or family
        found.update((m.metric_id, m) for m in selected)
    return list(found.values())


def has_metric_alias(utterance: str) -> bool:
    """Whether a request names a supported family, even if inventory lacks it."""
    text = _key(_metric_reference_text(utterance))
    return any(_contains_alias(text, _key(term))
               for family in _METRIC_ALIASES for term in family)


def match_metric(utterance: str, metrics):
    """Ground a natural metric reference in Reneryo-owned inventory data."""
    normalized = _key(_metric_reference_text(utterance))
    for metric in metrics:
        name = _key(metric.name)
        if name and (name in normalized or normalized in name):
            return metric
    for metric in metrics:
        if _localized_name_reference(normalized, metric):
            return metric
    for terms in _METRIC_ALIASES:
        normalized_terms = tuple(_key(term) for term in terms)
        if any(_contains_alias(normalized, term) for term in normalized_terms):
            return next(
                (
                    metric
                    for metric in metrics
                    if any(
                        _contains_alias(_key(metric.name), term)
                        for term in normalized_terms
                    )
                ),
                None,
            )
    return None


# Turkish softens a final voiceless stop before a vowel suffix:
# sıcaklık → sıcaklığı, elektrik → elektriği.
_SOFTENED = {"k": "kğg", "ç": "çc", "p": "pb", "t": "td"}


def _alias_pattern(alias: str) -> str:
    stem, last = alias[:-1], alias[-1:]
    if " " in alias or last not in _SOFTENED:
        return re.escape(alias)
    return re.escape(stem) + f"[{_SOFTENED[last]}]"


def _contains_alias(text: str, alias: str) -> bool:
    """Match an alias at a word start, avoiding fragments such as nem/döneme."""
    ending = r"(?!\w)" if alias == "humid" else ""
    return re.search(rf"(?<!\w){_alias_pattern(alias)}{ending}", text) is not None


def _localized_name_reference(text: str, metric) -> bool:
    """Whether a request repeats the Turkish label AVAROS shows for *metric*.

    Users answer with the words they heard, so every displayed label must be
    understood as well as the source name. Inflected endings are allowed.
    """
    label = source_metric_label(metric.name, "tr-TR")
    if not label or label == metric.name:
        return False
    return _contains_alias(text, _key(label))


def _key(value: str) -> str:
    """Comparison form: ı and i are equal, so casing never splits a name."""
    return normalize_phrase(value).replace("ı", "i")


def metric_reference_remainder(utterance: str, metric) -> str:
    """The words of a reply left after removing its reference to *metric*."""
    text = _key(utterance)
    name = _key(metric.name)
    phrases = {name, _key(source_metric_label(metric.name, "tr-TR"))}
    for terms in _METRIC_ALIASES:
        keys = {_key(term) for term in terms}
        if any(_contains_alias(name, key) for key in keys):
            phrases |= keys
    for phrase in sorted(phrases, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){_alias_pattern(phrase)}\w*", " ", text)
    return " ".join(text.split())
