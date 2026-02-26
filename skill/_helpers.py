"""Helper functions extracted from AVAROSSkill for smaller __init__.py."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from skill.domain.models import CanonicalMetric, TimePeriod
from skill._intent_resolver import resolve_intent_name as _resolve_intent_name
from skill._metric_resolver import resolve_metric_from_utterance as _resolve_metric_from_utterance

if TYPE_CHECKING:
    from ovos_bus_client.message import Message


def parse_period(self, period_str: str) -> TimePeriod:
    """Parse natural language period into TimePeriod value object."""
    return TimePeriod.from_natural_language(period_str)


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


def is_non_mock_profile(self) -> bool:
    """Return True when active profile is not built-in mock."""
    return self._resolve_active_profile() != "mock"


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
    """Require binding on non-mock profiles before executing handler."""
    if not self._is_non_mock_profile():
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
    data = getattr(message, "data", {}) or {}
    utterance = data.get("utterance")
    if isinstance(utterance, str):
        return utterance

    utterances = data.get("utterances")
    if isinstance(utterances, list) and utterances and isinstance(utterances[0], str):
        return utterances[0]

    return ""


def canonicalize_asset_id(self, raw_asset: str) -> str:
    """Normalize common spoken asset forms into stable IDs."""
    token = (raw_asset or "").strip()
    if not token:
        return ""

    normalized = re.sub(r"[-_]+", " ", token.lower()).strip()
    line_match = re.fullmatch(
        r"line\s+(1|2|3|4|5|one|two|three|four|five|to|too)",
        normalized,
    )
    if not line_match:
        return token

    digits = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "to": "2",
        "too": "2",
    }
    suffix = digits.get(line_match.group(1), line_match.group(1))
    return f"Line-{suffix}"


def extract_line_assets_from_text(self, text: str) -> list[str]:
    """Extract spoken line assets from utterance text (e.g., line two)."""
    if not text:
        return []

    matches = re.findall(
        r"\bline\s+(1|2|3|4|5|one|two|three|four|five|to|too)\b",
        text.lower(),
    )
    return [self._canonicalize_asset_id(f"line {value}") for value in matches]


def resolve_asset_id(self, message: Message, default: str = "default") -> str:
    """Resolve asset_id using slot first, then utterance fallback parsing."""
    data = getattr(message, "data", {}) or {}
    slot_asset = self._canonicalize_asset_id(str(data.get("asset", "")))
    if slot_asset and slot_asset.lower() not in {"to", "too", "for", "on", "line"}:
        return slot_asset

    utterance_assets = self._extract_line_assets_from_text(
        self._extract_utterance_text(message)
    )
    if utterance_assets:
        return utterance_assets[0]

    return default


def resolve_compare_assets(self, message: Message) -> tuple[str, str]:
    """Resolve comparison assets with utterance fallback for line references."""
    data = getattr(message, "data", {}) or {}
    asset_a = self._canonicalize_asset_id(str(data.get("asset_a", "")))
    asset_b = self._canonicalize_asset_id(str(data.get("asset_b", "")))
    if asset_a and asset_b:
        return asset_a, asset_b

    utterance_assets = self._extract_line_assets_from_text(
        self._extract_utterance_text(message)
    )
    if len(utterance_assets) >= 2:
        return utterance_assets[0], utterance_assets[1]

    return asset_a or "Asset-1", asset_b or "Asset-2"


def is_anomaly_query(self, utterance: str) -> bool:
    """Return True when utterance asks for anomaly/unusual pattern checks."""
    if not utterance:
        return False

    normalized = re.sub(r"[^a-z0-9\s]", " ", utterance.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    anomaly_patterns = (
        "check anomalies",
        "check anomaly",
        "check for anomalies",
        "anomaly check",
        "any anomalies",
        "unusual patterns",
        "anything unusual",
        "spikes or issues",
    )
    return any(pattern in normalized for pattern in anomaly_patterns)


def extract_intent_name(self, message: Message) -> str:
    """Extract normalized KPI intent name from bus message payload."""
    return _resolve_intent_name(message)
