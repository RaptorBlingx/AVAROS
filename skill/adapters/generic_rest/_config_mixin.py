"""Config parsing helpers for GenericRestAdapter."""

from __future__ import annotations

from typing import Any

from skill.adapters.generic_rest._http import DEFAULT_BACKOFF_FACTORS, DEFAULT_MAX_RETRIES
from skill.domain.models import CanonicalMetric


class GenericRestConfigMixin:
    """Provide config/capability parsing helpers."""

    @staticmethod
    def _normalize_metric_name(capability: str) -> str:
        """Normalize capability string to canonical metric naming."""
        normalized = str(capability or "").strip().lower().replace(" ", "_")
        if not normalized:
            return ""
        try:
            metric = CanonicalMetric.from_string(normalized)
        except ValueError:
            return ""
        return metric.value

    @staticmethod
    def _parse_max_retries(extra_settings: dict[str, Any]) -> int:
        """Parse retry count from extra settings with safe fallback."""
        value = extra_settings.get("max_retries", extra_settings.get("retry_count", DEFAULT_MAX_RETRIES))
        try:
            retries = int(value)
        except (TypeError, ValueError):
            return DEFAULT_MAX_RETRIES
        return max(0, retries)

    @staticmethod
    def _parse_backoff_factors(extra_settings: dict[str, Any]) -> tuple[float, ...]:
        """Parse retry backoff factors from extra settings."""
        raw = extra_settings.get("backoff_factors")
        if isinstance(raw, (list, tuple)):
            factors: list[float] = []
            for item in raw:
                try:
                    factors.append(float(item))
                except (TypeError, ValueError):
                    continue
            if factors:
                return tuple(factors)

        base_value = extra_settings.get("backoff_base")
        if base_value is not None:
            try:
                base = float(base_value)
            except (TypeError, ValueError):
                base = 0.5
            return tuple(base * (2**idx) for idx in range(DEFAULT_MAX_RETRIES))

        return DEFAULT_BACKOFF_FACTORS
