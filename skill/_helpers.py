"""Helper functions extracted from AVAROSSkill for smaller __init__.py."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from skill._asset_resolution import (
    get_asset_registry as _get_asset_registry,
    resolve_asset_id_from_text as _resolve_asset_id_from_text,
)
from skill.domain.exceptions import ValidationError
from skill.domain.models import Asset, CanonicalMetric, TimePeriod
from skill.services.language import normalize_phrase
from skill.services.language import normalize_language_tag
from skill._intent_resolver import resolve_intent_name as _resolve_intent_name
from skill._metric_resolver import resolve_metric_from_utterance as _resolve_metric_from_utterance
from skill._slot_resolution import (  # noqa: F401 — re-exported for __init__.py
    extract_line_assets_from_text,
    resolve_asset_id,
    resolve_compare_assets,
)

if TYPE_CHECKING:
    from ovos_bus_client.message import Message


def request_clock(message=None) -> datetime:
    """Reuse one clock across existing handoffs without changing wire context."""
    clock = getattr(message, "_avaros_request_clock", None) if message is not None else None
    if not isinstance(clock, datetime):
        clock = datetime.now(timezone.utc)
        if message is not None:
            message._avaros_request_clock = clock
    return clock


def request_timezone(self, message=None) -> str | None:
    """Read an administrator-verified org binding, never a browser timezone.

    Reneryo currently exposes no organization timezone field. Signed sessions
    therefore require a server profile binding rather than an unassociated
    site_timezone or a default derived from language, hostname or machine time.
    """
    settings = getattr(self, "settings_service", None)
    resolve_profile = getattr(self, "_resolve_active_profile", None)
    profile_name = resolve_profile() if callable(resolve_profile) else getattr(self, "_loaded_profile", "")
    profile = settings.get_profile(profile_name) if settings and callable(getattr(settings, "get_profile", None)) else None
    extra = profile.extra_settings if profile else {}
    context = (getattr(message, "context", {}) or {}).get("reneryo_context", {})
    organization = context.get("organization_id") if isinstance(context, dict) else None
    if organization:
        bindings = extra.get("organization_timezones", {})
        value = bindings.get(str(organization)) if isinstance(bindings, dict) else None
        return value if isinstance(value, str) and value else None
    return str(extra.get("site_timezone", "UTC") or "UTC")


def parse_period(self, period_str: str, message=None, *, now=None) -> TimePeriod:
    """Parse natural language period into TimePeriod value object."""
    try:
        return TimePeriod.from_natural_language(
            period_str,
            timezone_name=request_timezone(self, message),
            now=now or request_clock(message),
        )
    except ValueError as exc:
        raise ValidationError(
            message=str(exc),
            field="period",
            value=period_str,
            user_message=str(exc),
        ) from exc


def resolve_metric_from_utterance(
    self,
    utterance: str,
) -> CanonicalMetric | None:
    """Resolve a canonical metric from free-form KPI utterance text.

    Args:
        self: Bound skill instance (kept for method compatibility).
        utterance: Raw user utterance text.

    Returns:
        Matched canonical metric, otherwise ``None``.
    """
    return _resolve_metric_from_utterance(utterance)


def has_configured_profile(self) -> bool:
    """Return True when active profile is a real configured adapter."""
    profile = self._resolve_active_profile()
    return profile not in ("unconfigured", "")


def get_intent_binding(self, intent_name: str) -> dict | None:
    """Return configured binding for a non-metric intent."""
    if self.settings_service is None:
        return None
    try:
        return self.settings_service.get_intent_binding(intent_name)
    except Exception as exc:  # pragma: no cover - defensive logging path
        self.log.warning(
            "Intent binding read failed for %s: %s",
            intent_name,
            exc,
        )
        return None


def require_intent_binding(self, intent_name: str) -> bool:
    """Require binding on configured profiles before executing handler."""
    if not self._has_configured_profile():
        return True

    binding = self._get_intent_binding(intent_name)
    if binding is not None:
        return True

    self.speak(
        "This command is not configured for the active profile yet. "
        "Add an intent binding in Settings first."
    )
    return False


def power_state_key(self, profile: str) -> str:
    """Build profile-scoped runtime power-state key."""
    return f"runtime:power_state:{profile}"


def get_power_state(self) -> str:
    """Return profile-scoped runtime power state (on/off)."""
    profile = self._resolve_active_profile()
    if self.settings_service is None:
        return "on"

    value = self.settings_service.get_setting(
        self._power_state_key(profile),
        default="on",
    )
    state = str(value or "on").strip().lower()
    return "off" if state == "off" else "on"


def set_power_state(self, state: str) -> None:
    """Persist profile-scoped runtime power state."""
    profile = self._resolve_active_profile()
    if self.settings_service is None:
        return

    normalized = "off" if str(state).strip().lower() == "off" else "on"
    self.settings_service.set_setting(
        self._power_state_key(profile),
        normalized,
    )


def parse_numeric_amount(self, raw_amount: str) -> float | None:
    """Parse numeric amount from free-form speech text."""
    if not raw_amount:
        return None

    normalized = raw_amount.strip().lower().replace(",", ".")
    word_amounts = {
        "zero": 0.0,
        "one": 1.0,
        "two": 2.0,
        "three": 3.0,
        "four": 4.0,
        "five": 5.0,
        "six": 6.0,
        "seven": 7.0,
        "eight": 8.0,
        "nine": 9.0,
        "ten": 10.0,
        "sıfır": 0.0,
        "bir": 1.0,
        "iki": 2.0,
        "üç": 3.0,
        "dört": 4.0,
        "beş": 5.0,
        "altı": 6.0,
        "yedi": 7.0,
        "sekiz": 8.0,
        "dokuz": 9.0,
        "on": 10.0,
    }
    if normalized in word_amounts:
        return word_amounts[normalized]

    match = re.search(r"[-+]?\d+(?:\.\d+)?", normalized)
    if match:
        return float(match.group(0))

    return None


def resolve_temperature_amount(
    self,
    message: Message,
    default: float = 5.0,
) -> float:
    """Resolve what-if temperature delta from slots or raw utterance."""
    data = getattr(message, "data", {}) or {}
    slot_amount = self._parse_numeric_amount(str(data.get("amount", "")))
    if slot_amount is not None:
        return slot_amount

    utterance = self._extract_utterance_text(message).lower()
    phrase_match = re.search(
        (
            r"\b(?:by|to)\s+"
            r"([-+]?\d+(?:[\.,]\d+)?|zero|one|two|three|four|"
            r"five|six|seven|eight|nine|ten)\b"
        ),
        utterance,
    )
    if phrase_match:
        parsed = self._parse_numeric_amount(phrase_match.group(1))
        if parsed is not None:
            return parsed

    fallback_amount = self._parse_numeric_amount(utterance)
    if fallback_amount is not None:
        return fallback_amount

    return default


def extract_utterance_text(self, message: Message) -> str:
    """Extract raw utterance text from message payload/context."""
    sync_response_language(self, message)
    data = getattr(message, "data", {}) or {}
    utterance = data.get("utterance")
    if isinstance(utterance, str):
        return utterance

    utterances = data.get("utterances")
    if isinstance(utterances, list) and utterances and isinstance(utterances[0], str):
        return utterances[0]

    return ""


def sync_response_language(self, message: Message) -> str:
    """Select the response formatter for the language carried by HiveMind."""
    data = getattr(message, "data", {}) or {}
    context = getattr(message, "context", {}) or {}
    session = context.get("session", {}) if isinstance(context, dict) else {}
    requested = data.get("lang") if isinstance(data, dict) else None
    signed = context.get("reneryo_context") if isinstance(context, dict) else None
    if isinstance(signed, dict) and context.get("reneryo_widget_session_validated") is True:
        # Turkish widget turns use en-US only for OVOS recognition. The verified
        # conversational locale remains the authority for response formatting.
        requested = signed.get("language") or requested
    if not requested and isinstance(context, dict):
        requested = context.get("lang")
    if not requested and isinstance(session, dict):
        requested = session.get("lang")
    if not requested:
        # Unit-test doubles and non-HiveMind OVOS messages often omit language.
        # Keep the builder selected during skill initialization in that case.
        current = getattr(self, "_response_language", None)
        if isinstance(current, str) and current:
            return normalize_language_tag(current)
        return normalize_language_tag(getattr(self, "lang", "en-US"))

    language = normalize_language_tag(requested)

    if getattr(self, "_response_language", None) != language:
        from skill.services.response_builder import create_response_builder

        self.response_builder = create_response_builder(
            language,
            verbosity="normal",
            asset_name_resolver=self._resolve_asset_name_for_voice,
        )
        self._response_language = language
    return language


def get_asset_registry(self, force_refresh: bool = False) -> list[Asset]:
    """Return active-profile asset registry from adapter/settings cache."""
    return _get_asset_registry(self, force_refresh=force_refresh)


def canonicalize_asset_id(
    self,
    raw_asset: str,
    *,
    raise_on_unknown: bool = False,
) -> str:
    """Normalize spoken asset text into canonical asset IDs."""
    return _resolve_asset_id_from_text(
        self,
        raw_asset,
        raise_on_unknown=raise_on_unknown,
    )


def is_anomaly_query(self, utterance: str) -> bool:
    """Return True when utterance asks for anomaly/unusual pattern checks."""
    if not utterance:
        return False

    normalized = normalize_phrase(utterance)
    anomaly_patterns = (
        "anomaly",
        "anomalies",
        "anomalous",
        "check anomalies",
        "check anomaly",
        "check for anomalies",
        "anomaly check",
        "any anomalies",
        "unusual patterns",
        "anything unusual",
        "spikes or issues",
        "anomali",
        "anomaliler",
        "olağan dışı",
        "alışılmadık örüntü",
    )
    return any(pattern in normalized for pattern in anomaly_patterns)


def is_drift_query(self, utterance: str) -> bool:
    """Return True when utterance asks for drift or trend analysis."""
    if not utterance:
        return False

    normalized = normalize_phrase(utterance)
    drift_patterns = (
        "drift",
        "drifting",
        "trending",
        "gradual changes",
        "gradual degradation",
        "degradation",
        "declining",
        "getting worse",
        "drift check",
        "drift analysis",
        "drift report",
        "any trends",
        "check for gradual",
        "sapma",
        "sapma eğilimi",
        "kademeli değişiklik",
        "kötüleşiyor",
        "eğilim nasıl",
    )
    return any(pattern in normalized for pattern in drift_patterns)


def is_forecast_query(self, utterance: str) -> bool:
    """Return True when utterance asks for a predictive forecast."""
    if not utterance:
        return False

    normalized = normalize_phrase(utterance)
    forecast_patterns = (
        "forecast",
        "predict",
        "prediction",
        "expected",
        "what is expected",
        "tahmin",
        "tahmini",
        "öngör",
        "beklenen",
    )
    return any(pattern in normalized for pattern in forecast_patterns)


def is_whatif_query(self, utterance: str) -> bool:
    """Return True when utterance asks for a what-if scenario."""
    if not utterance:
        return False

    normalized = normalize_phrase(utterance)
    whatif_patterns = (
        "what if",
        "what would happen if",
        "simulate",
        "scenario",
        "project impact",
        "impact if",
        "if we",
        "ne olur",
        "simüle et",
        "senaryo",
    )
    return any(pattern in normalized for pattern in whatif_patterns)


def extract_intent_name(self, message: Message) -> str:
    """Extract normalized KPI intent name from bus message payload."""
    return _resolve_intent_name(message)
