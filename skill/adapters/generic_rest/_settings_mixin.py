"""Settings and trend-request helpers for GenericRestAdapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from skill.adapters.generic_rest._mapping_helpers import MetricMapping, resolve_request
from skill.domain.models import CanonicalMetric, TimePeriod

if TYPE_CHECKING:
    from skill.services.settings import SettingsService


class GenericRestSettingsMixin:
    """Provide mapping lookup and trend request resolution helpers."""

    _settings_service: SettingsService | None
    _extra_settings: dict[str, Any]
    _profile_name: str

    _AUTO_ENDPOINT_TEMPLATE = (
        "/api/u/measurement/metric/resource/{resource_id}/values"
        "?period=RAW&datetimeMin={start_date}&datetimeMax={end_date}&count=1&page=1"
    )
    _AUTO_TREND_ENDPOINT_TEMPLATE = (
        "/api/u/measurement/metric/resource/{resource_id}/values"
        "?period=RAW&datetimeMin={start_date}&datetimeMax={end_date}&count=100&page=1"
    )

    _GRANULARITY_TO_RENERYO_PERIOD = {
        "hourly": "HOURLY",
        "daily": "DAILY",
    }
    _RENERYO_TREND_COUNT = "31"

    def _resolve_trend_request(
        self,
        *,
        mapping: MetricMapping,
        metric_name: str,
        period: TimePeriod,
        asset_id: str,
        granularity: str,
    ) -> tuple[str, dict[str, str]]:
        """Resolve trend endpoint and params for a mapped metric.

        Convention: If no explicit trend endpoint is configured, derive
        from the KPI endpoint. For RENERYO-style endpoints that use a
        ``period`` enum (RAW/DAILY/HOURLY), map granularity to the
        enum value and increase count.
        """
        if str(mapping.get("trend_endpoint", "") or "").strip():
            return resolve_request(
                mapping=mapping,
                period=period,
                asset_id=asset_id,
                extra_settings=self._runtime_settings_for(metric_name, asset_id),
                endpoint_key="trend_endpoint",
            )

        endpoint, params = resolve_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._runtime_settings_for(metric_name, asset_id),
        )

        current_period = params.get("period", "")
        if current_period.upper() in {"RAW", "HOURLY", "DAILY"}:
            # RENERYO's aggregate periods can return sparse/empty windows for
            # generated demo resources. Raw points are reliable for trend math.
            params["period"] = "RAW"
            params["count"] = self._RENERYO_TREND_COUNT
        else:
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

        return self._build_auto_metric_mapping(metric_name)

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

    def _runtime_settings_for(self, metric_name: str, asset_id: str) -> dict[str, str]:
        """Return placeholder settings enriched with per-asset resource IDs."""
        settings = self._string_settings()
        resource_id = self._resolve_metric_resource_id(metric_name, asset_id)
        if resource_id:
            settings["resource_id"] = resource_id
            settings["resource_uuid"] = resource_id
        return settings

    @staticmethod
    def _normalize_asset_lookup(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _resolve_metric_resource_id(self, metric_name: str, asset_id: str) -> str:
        """Resolve metric resource UUID for a given asset from asset mappings."""
        if self._settings_service is not None:
            mappings = self._settings_service.get_asset_mappings(
                profile=self._profile_name or None,
            )
        else:
            mappings = self._extra_settings.get("asset_mappings")

        if not isinstance(mappings, dict):
            return ""

        target = self._normalize_asset_lookup(asset_id)
        if not target:
            return ""

        for key, mapping in mappings.items():
            if not isinstance(mapping, dict):
                continue

            lookup_values = [str(key)]
            display_name = str(mapping.get("display_name", "")).strip()
            if display_name:
                lookup_values.append(display_name)

            raw_aliases = mapping.get("aliases", [])
            if isinstance(raw_aliases, list):
                lookup_values.extend(str(alias).strip() for alias in raw_aliases if str(alias).strip())

            if not any(self._normalize_asset_lookup(value) == target for value in lookup_values):
                continue

            metric_resources = mapping.get("metric_resources", {})
            if not isinstance(metric_resources, dict):
                continue
            resource_id = str(metric_resources.get(metric_name, "")).strip()
            if resource_id:
                return resource_id

        return ""

    def _has_any_metric_resource(self, metric_name: str) -> bool:
        """Return True when at least one asset has a resource for metric_name."""
        if self._settings_service is not None:
            mappings = self._settings_service.get_asset_mappings(
                profile=self._profile_name or None,
            )
        else:
            mappings = self._extra_settings.get("asset_mappings")

        if not isinstance(mappings, dict):
            return False

        for mapping in mappings.values():
            if not isinstance(mapping, dict):
                continue
            metric_resources = mapping.get("metric_resources", {})
            if not isinstance(metric_resources, dict):
                continue
            resource_id = str(metric_resources.get(metric_name, "")).strip()
            if resource_id:
                return True
        return False

    def _build_auto_metric_mapping(self, metric_name: str) -> MetricMapping | None:
        """Synthesize mapping from imported metric_resources when manual mapping is absent."""
        if not self._has_any_metric_resource(metric_name):
            return None

        try:
            unit = CanonicalMetric.from_string(metric_name).default_unit
        except ValueError:
            unit = ""

        return {
            "endpoint": self._AUTO_ENDPOINT_TEMPLATE,
            "trend_endpoint": self._AUTO_TREND_ENDPOINT_TEMPLATE,
            # Generic REST JSONPath resolver supports explicit numeric indexes.
            # Auto requests use `count=1`, so first record is the latest value.
            "json_path": "$.records[0].value",
            "unit": unit,
            "transform": None,
        }
