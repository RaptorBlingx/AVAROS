"""Metric and KPI-related handler implementations for AVAROSSkill."""

from __future__ import annotations

import re
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from skill.domain.exceptions import AdapterError, AssetNotFoundError, MetricNotSupportedError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import AnomalyResult, ComparisonResult, KPIResult, TrendResult, WhatIfResult

if TYPE_CHECKING:
    from skill import AVAROSSkill


logger = logging.getLogger(__name__)

_ENERGY_PREFERENCE = (
    CanonicalMetric.ENERGY_PER_UNIT,
    CanonicalMetric.ENERGY_TOTAL,
)
_ENERGY_TOTAL_NATIVE_STRATEGY = "asset_consumption_total"
_AGGREGATE_TOTAL_PERIOD_MODE = "aggregate_total"
_AGGREGATE_TOTAL_LABEL = "in total"
_DEFAULT_AGGREGATE_START_ISO = "2021-02-01T00:00:00.000Z"
_DEFAULT_WIDE_START_ISO = "2021-02-01T00:00:00.000Z"
_SUPPORTED_PERIOD_PHRASES = (
    "last two weeks",
    "last 2 weeks",
    "this month",
    "last month",
    "past month",
    "this week",
    "last week",
    "past week",
    "yesterday",
    "today",
)


def _normalize_asset_lookup(value: str) -> str:
    """Normalize asset identifiers for tolerant lookups."""
    return re.sub(r"[^a-z0-9]", "", value.lower().strip())


def _parse_utc_iso(value: str) -> datetime | None:
    """Parse ISO datetime string with optional trailing Z."""
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_period_phrase_from_text(raw: str) -> str | None:
    """Extract the first supported period phrase from arbitrary text."""
    normalized = str(raw or "").strip().lower()
    if not normalized:
        return None
    for phrase in _SUPPORTED_PERIOD_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", normalized):
            return phrase
    return None


def _extract_utterance_period_phrase(message) -> str | None:
    """Extract a supported period phrase from utterance payload fields."""
    data = getattr(message, "data", {}) or {}

    raw_utterance = data.get("utterance")
    if isinstance(raw_utterance, str) and raw_utterance.strip():
        phrase = _extract_period_phrase_from_text(raw_utterance)
        return phrase

    raw_utterances = data.get("utterances")
    if isinstance(raw_utterances, list):
        for item in raw_utterances:
            if not isinstance(item, str):
                continue
            phrase = _extract_period_phrase_from_text(item)
            if phrase is not None:
                return phrase
    return None


def _utterance_mentions_period(message) -> bool:
    """Return True when explicit utterance text contains period phrases."""
    return _extract_utterance_period_phrase(message) is not None


def _extract_supported_period_phrase(raw: str) -> str | None:
    """Extract a supported period phrase from raw period slot text."""
    return _extract_period_phrase_from_text(raw)


def _resolve_requested_period_phrase(
    explicit_period: str,
    utterance_period_phrase: str | None,
) -> str | None:
    """Resolve the effective requested period phrase from slot and utterance."""
    slot_period_phrase = _extract_supported_period_phrase(explicit_period)
    if slot_period_phrase is None:
        return utterance_period_phrase
    if slot_period_phrase == "today" and utterance_period_phrase != "today":
        return None
    return slot_period_phrase


def _wide_default_period() -> TimePeriod:
    """Return a wide default period (2021-02-01 → now) for implicit queries."""
    start = datetime(2021, 2, 1, tzinfo=timezone.utc)
    end = datetime.now(tz=timezone.utc)
    return TimePeriod(start=start, end=end, display_name="")


def _resolve_energy_total_aggregate_period(
    skill: "AVAROSSkill",
    *,
    asset_id: str,
) -> TimePeriod | None:
    """Resolve aggregate total period for cumulative-only energy meter bindings."""
    mapping = _resolve_asset_mapping(skill, asset_id=asset_id)
    if not isinstance(mapping, dict):
        return None
    capability_mode = str(mapping.get("capability_mode", "")).strip().lower()
    if capability_mode != "energy_only":
        return None

    native_bindings = mapping.get("native_metric_bindings")
    if not isinstance(native_bindings, dict):
        return None
    binding = native_bindings.get(CanonicalMetric.ENERGY_TOTAL.value)
    if not isinstance(binding, dict):
        return None

    strategy = str(binding.get("strategy", "")).strip().lower()
    if strategy != _ENERGY_TOTAL_NATIVE_STRATEGY:
        return None

    period_mode = str(binding.get("default_period_mode", "")).strip().lower()
    if period_mode and period_mode != _AGGREGATE_TOTAL_PERIOD_MODE:
        return None

    start = _parse_utc_iso(str(binding.get("aggregate_start_iso", "")).strip())
    if start is None:
        start = _parse_utc_iso(_DEFAULT_AGGREGATE_START_ISO)
    if start is None:
        logger.warning(
            "Energy-only aggregate mode enabled for '%s' but aggregate_start_iso is missing/invalid",
            asset_id,
        )
        return None

    end = datetime.now(tz=timezone.utc)
    if start >= end:
        logger.warning(
            "Energy-only aggregate mode start (%s) is not before now for '%s'",
            start.isoformat(),
            asset_id,
        )
        return None

    return TimePeriod(start=start, end=end, display_name=_AGGREGATE_TOTAL_LABEL)


def _mapping_supports_period_placeholders(mapping: dict[str, Any]) -> bool:
    """Return True when a configured endpoint can carry explicit time filters."""
    endpoint = str(mapping.get("endpoint", "") or "")
    normalized = endpoint.lower()
    placeholders = (
        "{start_date}",
        "{start_datetime}",
        "{datetimemin}",
        "{end_date}",
        "{end_datetime}",
        "{datetimemax}",
        "{period}",
    )
    return any(token in normalized for token in placeholders)


def _is_total_energy_only_asset_mapping(mapping: dict[str, Any]) -> bool:
    """Return True when an asset effectively only exposes total energy."""
    capability_mode = str(mapping.get("capability_mode", "")).strip().lower()
    if capability_mode == "energy_only":
        return True

    native_bindings = mapping.get("native_metric_bindings")
    if isinstance(native_bindings, dict):
        names = tuple(sorted(str(key).strip() for key in native_bindings if str(key).strip()))
        if names == (CanonicalMetric.ENERGY_TOTAL.value,):
            return True

    metric_resources = mapping.get("metric_resources")
    if isinstance(metric_resources, dict):
        names = tuple(
            sorted(
                str(key).strip()
                for key, value in metric_resources.items()
                if str(key).strip() and str(value).strip()
            ),
        )
        if names == (CanonicalMetric.ENERGY_TOTAL.value,):
            return True

    return False


def _uses_period_insensitive_energy_total_mapping(skill: "AVAROSSkill") -> bool:
    """Return True when active energy_total mapping ignores explicit time filters."""
    settings_service = getattr(skill, "settings_service", None)
    if settings_service is None:
        return False
    try:
        mapping = settings_service.get_metric_mapping(CanonicalMetric.ENERGY_TOTAL.value)
    except Exception:
        logger.warning("Could not read energy_total mapping while resolving KPI period", exc_info=True)
        return False
    if not isinstance(mapping, dict):
        return False
    return not _mapping_supports_period_placeholders(mapping)


def _raise_energy_total_period_unavailable(
    skill: "AVAROSSkill",
    *,
    asset_id: str,
) -> None:
    """Reject explicit time windows for cumulative-only meter totals."""
    mapping = _resolve_asset_mapping(skill, asset_id=asset_id)
    display_name = asset_id
    if isinstance(mapping, dict):
        display_name = str(mapping.get("display_name") or asset_id).strip() or asset_id
    dispatcher = getattr(skill, "dispatcher", None)
    adapter = getattr(dispatcher, "adapter", None)
    raise MetricNotSupportedError(
        message=(
            f"Time-based total energy is not available for cumulative-only asset '{asset_id}'"
        ),
        metric=CanonicalMetric.ENERGY_TOTAL.value,
        platform=getattr(adapter, "platform_name", "unknown"),
        available_metrics=[CanonicalMetric.ENERGY_TOTAL.value],
        user_message=(
            f"Time-based total energy is not available for {display_name}. "
            "This meter only exposes a cumulative total. Ask for total energy without a period."
        ),
    )


def _resolve_asset_mapping(
    skill: "AVAROSSkill",
    *,
    asset_id: str,
) -> dict[str, Any] | None:
    """Resolve an asset mapping row from settings by id/name/alias."""
    settings_service = getattr(skill, "settings_service", None)
    if settings_service is None:
        return None

    try:
        mappings = settings_service.get_asset_mappings()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Could not read asset mappings while resolving KPI period: %s", exc)
        return None

    if not isinstance(mappings, dict):
        return None

    direct = mappings.get(asset_id)
    if isinstance(direct, dict):
        return direct

    target = _normalize_asset_lookup(asset_id)
    if not target:
        return None

    for key, raw_mapping in mappings.items():
        if not isinstance(raw_mapping, dict):
            continue
        lookup_values: list[str] = [str(key), str(raw_mapping.get("display_name", ""))]
        aliases = raw_mapping.get("aliases")
        if isinstance(aliases, list):
            lookup_values.extend(str(alias) for alias in aliases)
        if any(_normalize_asset_lookup(value) == target for value in lookup_values if value):
            return raw_mapping
    return None


def _resolve_kpi_period(
    skill: "AVAROSSkill",
    *,
    metric: CanonicalMetric,
    asset_id: str,
    message,
) -> TimePeriod:
    """Resolve KPI period, with aggregate default for energy-only native totals."""
    data = getattr(message, "data", {}) or {}
    explicit_period = str(data.get("period", "")).strip()
    utterance_period_phrase = _extract_utterance_period_phrase(message)
    requested_period_phrase = _resolve_requested_period_phrase(
        explicit_period,
        utterance_period_phrase,
    )

    aggregate_period = None
    if metric is CanonicalMetric.ENERGY_TOTAL:
        mapping = _resolve_asset_mapping(skill, asset_id=asset_id)
        aggregate_period = _resolve_energy_total_aggregate_period(
            skill,
            asset_id=asset_id,
        )
        if aggregate_period is not None and requested_period_phrase is not None:
            _raise_energy_total_period_unavailable(skill, asset_id=asset_id)
        if (
            requested_period_phrase is not None
            and isinstance(mapping, dict)
            and _is_total_energy_only_asset_mapping(mapping)
            and _uses_period_insensitive_energy_total_mapping(skill)
        ):
            _raise_energy_total_period_unavailable(skill, asset_id=asset_id)

    if requested_period_phrase is not None:
        return skill._parse_period(requested_period_phrase)
    if aggregate_period is not None:
        return aggregate_period
    return _wide_default_period()


def _is_metric_mapped_for_active_adapter(
    skill: "AVAROSSkill",
    metric: CanonicalMetric,
) -> bool:
    """Return True when current adapter reports support for the metric."""
    dispatcher = getattr(skill, "dispatcher", None)
    if dispatcher is None:
        return False

    adapter = getattr(dispatcher, "adapter", None)
    if adapter is None:
        return False

    supported_metrics = None
    try:
        supported_metrics = adapter.get_supported_metrics()
    except Exception as exc:
        logger.warning(
            "Could not read supported metrics for '%s': %s",
            metric.value,
            exc,
        )

    if isinstance(supported_metrics, (list, tuple, set, frozenset)):
        return metric in supported_metrics or metric.value in supported_metrics

    try:
        return bool(adapter.supports_capability(metric.value))
    except Exception as exc:
        logger.warning(
            "Capability check failed for '%s'; treating as unmapped: %s",
            metric.value,
            exc,
        )
        return False


def _resolve_and_validate_metric(skill: "AVAROSSkill", message) -> CanonicalMetric | None:
    """Resolve metric from utterance and ensure it is mapped."""
    data = getattr(message, "data", {}) or {}
    metric_text = str(data.get("metric", "")).strip()
    source_text = metric_text or skill._extract_utterance_text(message)
    metric = skill._resolve_metric_from_utterance(source_text)

    if metric is None:
        skill.speak_dialog("metric.not_recognized")
        return None

    if not _is_metric_mapped_for_active_adapter(skill, metric):
        skill.speak_dialog("metric.not_configured", data={"metric": metric.display_name})
        return None

    return metric


def _query_trend_with_period_fallback(
    skill: "AVAROSSkill",
    *,
    metric: CanonicalMetric,
    asset_id: str,
    period,
    granularity: str,
):
    """Query trend and widen period once when narrow-range response is empty."""
    try:
        return skill.dispatcher.get_trend(
            metric=metric,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )
    except AdapterError as exc:
        if exc.code != "EMPTY_RESPONSE":
            raise
        if period.duration_days >= 2:
            raise

        fallback_period = skill._parse_period("last week")
        fallback_granularity = "daily" if granularity == "hourly" else granularity
        logger.info(
            "Trend fallback: metric=%s asset=%s period=%s -> %s",
            metric.value,
            asset_id,
            period.display_name,
            fallback_period.display_name,
        )
        return skill.dispatcher.get_trend(
            metric=metric,
            asset_id=asset_id,
            period=fallback_period,
            granularity=fallback_granularity,
        )


def dispatch_kpi_for_metric(
    skill: "AVAROSSkill",
    *,
    metric: CanonicalMetric,
    message,
    handler_name: str,
) -> None:
    """Execute KPI dispatch for a resolved canonical metric."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = _resolve_kpi_period(
            skill,
            metric=metric,
            asset_id=asset_id,
            message=message,
        )

        result: KPIResult = skill.dispatcher.get_kpi(
            metric=metric,
            asset_id=asset_id,
            period=period,
        )

        response = skill.response_builder.format_kpi_result(result)
        skill.speak(response)

    skill._safe_dispatch(handler_name, _execute)


def _resolve_handler_period(skill: "AVAROSSkill", message, default: str = "today") -> TimePeriod:
    """Resolve period from message, falling back to wide default when implicit."""
    data = getattr(message, "data", {}) or {}
    explicit = str(data.get("period", "")).strip()
    utterance_period_phrase = _extract_utterance_period_phrase(message)
    phrase = _resolve_requested_period_phrase(explicit, utterance_period_phrase)
    if phrase is not None:
        return skill._parse_period(phrase)
    if _utterance_mentions_period(message):
        return skill._parse_period(default)
    return _wide_default_period()


def handle_compare_energy(skill: "AVAROSSkill", message) -> None:
    """Handle: 'Compare energy between {asset_a} and {asset_b}'."""

    def _execute() -> None:
        asset_a, asset_b = skill._resolve_compare_assets(message)
        period = _resolve_handler_period(skill, message)

        result: ComparisonResult = skill.dispatcher.compare(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_ids=[asset_a, asset_b],
            period=period,
        )

        response = skill.response_builder.format_comparison_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_compare_energy", _execute)


def handle_compare_metric(skill: "AVAROSSkill", message) -> None:
    """Handle generic compare requests for any canonical metric."""
    metric = _resolve_and_validate_metric(skill, message)
    if metric is None:
        return

    def _execute() -> None:
        asset_a, asset_b = skill._resolve_compare_assets(message)
        period = _resolve_handler_period(skill, message)
        result: ComparisonResult = skill.dispatcher.compare(
            metric=metric,
            asset_ids=[asset_a, asset_b],
            period=period,
        )
        response = skill.response_builder.format_comparison_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_compare_metric", _execute)


def handle_trend_scrap(skill: "AVAROSSkill", message) -> None:
    """Handle: 'Show scrap rate trend for {period}'."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = _resolve_handler_period(skill, message, default="last week")
        granularity = message.data.get("granularity", "daily")

        result: TrendResult = _query_trend_with_period_fallback(
            skill,
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )

        response = skill.response_builder.format_trend_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_trend_scrap", _execute)


def handle_trend_metric(skill: "AVAROSSkill", message) -> None:
    """Handle generic trend requests for any canonical metric."""
    metric = _resolve_and_validate_metric(skill, message)
    if metric is None:
        return

    def _execute() -> None:
        data = getattr(message, "data", {}) or {}
        asset_id = skill._resolve_asset_id(message)
        period = _resolve_handler_period(skill, message, default="last week")
        granularity = data.get("granularity", "daily")

        result: TrendResult = _query_trend_with_period_fallback(
            skill,
            metric=metric,
            asset_id=asset_id,
            period=period,
            granularity=granularity,
        )

        response = skill.response_builder.format_trend_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_trend_metric", _execute)


def handle_trend_energy(skill: "AVAROSSkill", message) -> None:
    """Handle: 'Show energy trend for {period}'."""

    def _execute() -> None:
        asset_id = skill._resolve_asset_id(message)
        period = _resolve_handler_period(skill, message, default="last week")
        granularity = message.data.get("granularity", "daily")
        if period.duration_days < 2 and granularity == "daily":
            granularity = "hourly"
        try:
            result: TrendResult = _query_trend_with_period_fallback(
                skill,
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id=asset_id,
                period=period,
                granularity=granularity,
            )
            response = skill.response_builder.format_trend_result(result)
            skill.speak(response)
            return
        except AdapterError as exc:
            if exc.code != "EMPTY_RESPONSE":
                raise

        # Last-resort UX fallback: if trend points are unavailable, still return
        # the current energy KPI so the command stays useful.
        kpi_result: KPIResult = skill.dispatcher.get_kpi(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id=asset_id,
            period=skill._parse_period("today"),
        )
        kpi_response = skill.response_builder.format_kpi_result(kpi_result)
        skill.speak(
            f"I couldn't find enough trend points for {period.display_name}. {kpi_response}",
        )

    skill._safe_dispatch("handle_trend_energy", _execute)


def _resolve_default_metric(skill: "AVAROSSkill", utterance: str) -> CanonicalMetric:
    """Pick the best metric from utterance text or adapter capabilities."""
    from_text = skill._resolve_metric_from_utterance(utterance)
    if from_text is not None:
        return from_text
    supported = _get_adapter_metrics(skill)
    for preferred in _ENERGY_PREFERENCE:
        if preferred in supported:
            return preferred
    if supported:
        return supported[0]
    return CanonicalMetric.ENERGY_PER_UNIT


def _get_adapter_metrics(skill: "AVAROSSkill") -> list[CanonicalMetric]:
    """Safely read supported metrics from the adapter."""
    adapter = getattr(skill.dispatcher, "adapter", None)
    if adapter is None:
        return []
    try:
        result = adapter.get_supported_metrics()
        if not isinstance(result, list):
            return []
        return result
    except Exception:
        return []


def _resolve_anomaly_query_scope(
    skill: "AVAROSSkill",
    message,
    utterance: str,
) -> tuple[CanonicalMetric | None, str | None]:
    """Resolve optional metric/asset filters for anomaly query scope."""
    metric = skill._resolve_metric_from_utterance(utterance)
    data = getattr(message, "data", {}) or {}

    raw_slot_asset = str(data.get("asset", "")).strip()
    if raw_slot_asset:
        try:
            return metric, skill._canonicalize_asset_id(
                raw_slot_asset,
                raise_on_unknown=True,
            )
        except Exception:
            pass

    utterance_assets = skill._extract_line_assets_from_text(utterance)
    if utterance_assets:
        return metric, utterance_assets[0]

    utterance_asset = skill._canonicalize_asset_id(utterance)
    if utterance_asset and utterance_asset != utterance:
        return metric, utterance_asset

    return metric, None


def _format_anomaly_query_response(
    skill: "AVAROSSkill",
    *,
    metric: CanonicalMetric | None,
    asset_id: str | None,
) -> str:
    """Format anomaly output based on targeted or broad query scope."""
    if metric is not None and asset_id is not None:
        result: AnomalyResult = skill.dispatcher.check_anomaly(
            metric=metric,
            asset_id=asset_id,
        )
        return skill.response_builder.format_anomaly_result(result)

    scan_result = skill.dispatcher.scan_anomalies(metric=metric, asset_id=asset_id)
    return skill.response_builder.format_anomaly_scan_result(scan_result)


def handle_anomaly_check(skill: "AVAROSSkill", message) -> None:
    """Handle: 'Any unusual patterns in production?'."""

    def _execute() -> None:
        text = skill._extract_utterance_text(message)
        metric, asset_id = _resolve_anomaly_query_scope(
            skill,
            message,
            text,
        )
        response = _format_anomaly_query_response(
            skill,
            metric=metric,
            asset_id=asset_id,
        )
        skill.speak(response)

    skill._safe_dispatch("handle_anomaly_check", _execute)


def _resolve_drift_asset(skill: "AVAROSSkill", message) -> str:
    """Resolve asset for drift queries, falling back to default on failure."""
    try:
        return skill._resolve_asset_id(message)
    except AssetNotFoundError:
        from skill._slot_resolution import _resolve_default_asset_id

        return _resolve_default_asset_id(skill, fallback="default")


def handle_drift_check(skill: "AVAROSSkill", message) -> None:
    """Handle: 'How has energy been trending?' / 'Check for drift'."""

    def _execute() -> None:
        asset_id = _resolve_drift_asset(skill, message)
        text = skill._extract_utterance_text(message)
        metric = _resolve_default_metric(skill, text)

        result = skill.dispatcher.check_drift(
            metric=metric,
            asset_id=asset_id,
        )

        response = skill.response_builder.format_drift_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_drift_check", _execute)


def handle_whatif_temperature(skill: "AVAROSSkill", message) -> None:
    """Handle: 'What if we reduce temperature by {amount} degrees?'."""

    def _execute() -> None:
        from skill.domain.models import ScenarioParameter, WhatIfScenario

        amount = skill._resolve_temperature_amount(message)
        asset_id = skill._resolve_asset_id(message)

        scenario = WhatIfScenario(
            name="temperature_change",
            asset_id=asset_id,
            parameters=[
                ScenarioParameter(
                    name="temperature",
                    baseline_value=25.0,
                    proposed_value=25.0 - amount,
                    unit="°C",
                )
            ],
            target_metric=CanonicalMetric.ENERGY_PER_UNIT,
        )

        result: WhatIfResult = skill.dispatcher.simulate_whatif(scenario)

        response = skill.response_builder.format_whatif_result(result)
        skill.speak(response)

    skill._safe_dispatch("handle_whatif_temperature", _execute)
