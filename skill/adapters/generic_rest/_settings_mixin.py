"""Settings and trend-request helpers for GenericRestAdapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from skill.adapters.generic_rest._mapping_helpers import MetricMapping, resolve_request
from skill.domain.models import TimePeriod

if TYPE_CHECKING:
    from skill.services.settings import SettingsService


class GenericRestSettingsMixin:
    """Provide mapping lookup and trend request resolution helpers."""

    _settings_service: SettingsService | None
    _extra_settings: dict[str, Any]

    def _resolve_trend_request(
        self,
        *,
        mapping: MetricMapping,
        period: TimePeriod,
        asset_id: str,
        granularity: str,
    ) -> tuple[str, dict[str, str]]:
        """Resolve trend endpoint and params for a mapped metric.

        Convention: If no explicit trend endpoint is configured, use the KPI
        endpoint and append ``period={start}_{end}`` and
        ``granularity={granularity}`` query params.
        """
        if str(mapping.get("trend_endpoint", "") or "").strip():
            return resolve_request(
                mapping=mapping,
                period=period,
                asset_id=asset_id,
                extra_settings=self._string_settings(),
                endpoint_key="trend_endpoint",
            )

        endpoint, params = resolve_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._string_settings(),
        )
        start_iso = period.start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = period.end.strftime("%Y-%m-%dT%H:%M:%SZ")
        params["period"] = f"{start_iso}_{end_iso}"
        params["granularity"] = granularity
        return endpoint, params

    def _lookup_metric_mapping_by_name(self, metric_name: str) -> MetricMapping | None:
        """Resolve mapping from SettingsService (or extra_settings fallback)."""
        if self._settings_service is not None:
            mapping = self._settings_service.get_metric_mapping(metric_name)
            if isinstance(mapping, dict):
                return mapping

        local_mappings = self._extra_settings.get("metric_mappings")
        if isinstance(local_mappings, dict):
            mapping = local_mappings.get(metric_name)
            if isinstance(mapping, dict):
                return mapping

        return None

    def _list_metric_mappings(self) -> dict[str, MetricMapping]:
        """Return current active profile mappings."""
        if self._settings_service is not None:
            mappings = self._settings_service.list_metric_mappings()
            if isinstance(mappings, dict):
                return {
                    str(name): value
                    for name, value in mappings.items()
                    if isinstance(value, dict)
                }

        local_mappings = self._extra_settings.get("metric_mappings")
        if isinstance(local_mappings, dict):
            return {
                str(name): value
                for name, value in local_mappings.items()
                if isinstance(value, dict)
            }

        return {}

    def _string_settings(self) -> dict[str, str]:
        """Stringify scalar extra settings for placeholder replacement."""
        result: dict[str, str] = {}
        for key, value in self._extra_settings.items():
            if isinstance(value, (dict, list, tuple, set)):
                continue
            if value is None:
                continue
            result[str(key)] = str(value)
        return result
