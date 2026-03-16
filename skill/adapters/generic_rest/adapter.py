"""Generic REST adapter using profile metric mappings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional in minimal OVOS images
    aiohttp = None  # type: ignore[assignment]

from skill.adapters.base import ManufacturingAdapter
from skill.adapters.generic_rest._config_mixin import GenericRestConfigMixin
from skill.adapters.generic_rest._http import GenericRestHttpMixin
from skill.adapters.generic_rest._mapping_helpers import (
    MetricMapping,
    compute_trend_change,
    extract_mapped_value,
    extract_trend_points,
    get_mapping_json_path,
    get_mapping_unit,
    parse_mapped_kpi_response,
    rank_descending,
    resolve_request,
)
from skill.adapters.generic_rest._settings_mixin import GenericRestSettingsMixin
from skill.domain.exceptions import AdapterError
from skill.domain.models import Asset, CanonicalMetric, TimePeriod
from skill.domain.results import ComparisonItem, ComparisonResult, KPIResult, TrendResult

if TYPE_CHECKING:
    from skill.services.settings import SettingsService

logger = logging.getLogger(__name__)


class GenericRestAdapter(
    GenericRestHttpMixin,
    GenericRestConfigMixin,
    GenericRestSettingsMixin,
    ManufacturingAdapter,
):
    """Platform-agnostic adapter driven by metric mappings."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = 30,
        auth_type: str = "bearer",
        settings_service: SettingsService | None = None,
        profile_name: str = "",
        extra_settings: dict[str, Any] | None = None,
    ) -> None:
        self._api_url = (api_url or "").strip().rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._auth_type = (auth_type or "bearer").strip().lower()
        self._settings_service = settings_service
        self._profile_name = profile_name
        self._extra_settings: dict[str, Any] = dict(extra_settings or {})
        self._session: aiohttp.ClientSession | None = None

        self._max_retries = self._parse_max_retries(self._extra_settings)
        self._backoff_factors = self._parse_backoff_factors(self._extra_settings)

    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        """Fetch KPI from mapped endpoint and parse mapped value."""
        self._ensure_initialized()
        mapping = self._require_metric_mapping(metric)

        endpoint, params = resolve_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._string_settings(),
        )
        data = await self._retry_fetch(endpoint, params)
        return parse_mapped_kpi_response(data, mapping, metric, asset_id, period)

    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        """Fetch mapped KPI for each asset and return ranked comparison."""
        self._ensure_initialized()
        if len(asset_ids) < 2:
            raise AdapterError(
                message="Comparison requires at least two asset IDs",
                code="GENERIC_REST_COMPARE_INVALID",
                platform="generic_rest",
            )

        mapping = self._require_metric_mapping(metric)
        json_path = get_mapping_json_path(mapping)
        unit = get_mapping_unit(mapping, metric)

        values: list[tuple[str, float]] = []
        for asset_id in asset_ids:
            endpoint, params = resolve_request(
                mapping=mapping,
                period=period,
                asset_id=asset_id,
                extra_settings=self._string_settings(),
            )
            data = await self._retry_fetch(endpoint, params)
            value = extract_mapped_value(data, json_path, mapping)
            values.append((asset_id, value))

        sorted_values = sorted(
            values,
            key=lambda item: item[1],
            reverse=rank_descending(metric),
        )
        items = [
            ComparisonItem(asset_id=asset_id, value=value, rank=index + 1)
            for index, (asset_id, value) in enumerate(sorted_values)
        ]

        winner_id = items[0].asset_id
        difference = round(abs(max(value for _, value in values) - min(value for _, value in values)), 2)

        return ComparisonResult(
            metric=metric,
            items=items,
            winner_id=winner_id,
            difference=difference,
            unit=unit,
            period=period,
        )

    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        """Fetch trend endpoint and parse generic time-series payload."""
        self._ensure_initialized()
        mapping = self._require_metric_mapping(metric)

        endpoint, params = self._resolve_trend_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            granularity=granularity,
        )
        data = await self._retry_fetch(endpoint, params)

        points = extract_trend_points(
            payload=data,
            mapping=mapping,
            metric=metric,
            period=period,
        )
        if not points:
            raise AdapterError(
                message="No trend data points returned",
                code="GENERIC_REST_NO_DATA",
                platform="generic_rest",
                user_message=(
                    "I couldn't find trend data for that period. "
                    "Please try a wider period."
                ),
            )

        direction, change_percent = compute_trend_change(points)
        return TrendResult(
            metric=metric,
            asset_id=asset_id,
            data_points=points,
            direction=direction,
            change_percent=change_percent,
            period=period,
            granularity=granularity,
        )

    async def get_raw_data(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> dict | list:
        """Fetch and return mapped endpoint payload without normalization."""
        self._ensure_initialized()
        mapping = self._require_metric_mapping(metric)

        endpoint_key = "raw_endpoint" if str(mapping.get("raw_endpoint", "")).strip() else "endpoint"
        endpoint, params = resolve_request(
            mapping=mapping,
            period=period,
            asset_id=asset_id,
            extra_settings=self._string_settings(),
            endpoint_key=endpoint_key,
        )
        return await self._retry_fetch(endpoint, params)

    async def list_assets(self) -> list[Asset]:
        """Return assets from profile-scoped asset mappings."""
        mappings = self._load_asset_mappings()
        assets: list[Asset] = []
        for asset_id, mapping in sorted(mappings.items(), key=lambda item: item[0]):
            if not isinstance(mapping, dict):
                continue
            asset = self._build_asset_from_mapping(asset_id, mapping)
            if asset is not None:
                assets.append(asset)
        return assets

    def supports_asset_discovery(self) -> bool:
        """Generic REST adapter does not perform live asset discovery."""
        return False

    def supports_capability(self, capability: str) -> bool:
        """Return True only when capability maps to a configured metric."""
        metric_name = self._normalize_metric_name(capability)
        if not metric_name:
            return False
        return self._lookup_metric_mapping_by_name(metric_name) is not None

    def get_supported_metrics(self) -> list[CanonicalMetric]:
        """List canonical metrics that currently have mappings configured."""
        mappings = self._list_metric_mappings()
        supported: list[CanonicalMetric] = []
        for metric_name in mappings.keys():
            try:
                supported.append(CanonicalMetric.from_string(metric_name))
            except ValueError:
                logger.debug("Ignoring unknown mapped metric name: %s", metric_name)
        return supported

    async def initialize(self) -> None:
        """Create HTTP session and validate configured base URL is reachable."""
        if not self._api_url:
            raise AdapterError(
                message="API URL is required for GenericRestAdapter",
                code="GENERIC_REST_INIT_FAILED",
                platform="generic_rest",
            )

        if self._session is not None and not self._session.closed:
            await self._session.close()

        timeout = aiohttp.ClientTimeout(total=self._timeout)
        headers = self._build_auth_headers()
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)

        try:
            await self._probe_base_url()
        except Exception:
            await self.shutdown()
            raise

        logger.info(
            "GenericRestAdapter initialized — API URL: %s, auth: %s, retries: %d",
            self._api_url,
            self._auth_type,
            self._max_retries,
        )

    async def shutdown(self) -> None:
        """Close HTTP session gracefully."""
        if self._session is not None:
            await self._session.close()
            self._session = None
        logger.info("GenericRestAdapter shut down")

    @property
    def platform_name(self) -> str:
        """Return platform name used in logs/UI."""
        return "GENERIC_REST"

    def _require_metric_mapping(self, metric: CanonicalMetric) -> MetricMapping:
        """Load mapping for metric or raise clear missing-mapping error."""
        mapping = self._lookup_metric_mapping_by_name(metric.value)
        if mapping is not None:
            return mapping

        raise AdapterError(
            message=f"No mapping configured for {metric.value}",
            code="GENERIC_REST_MAPPING_NOT_FOUND",
            platform="generic_rest",
            user_message=(
                f"This command is not configured for {metric.display_name} yet. "
                "Add a metric mapping in Settings first."
            ),
        )

    def _load_asset_mappings(self) -> dict[str, dict[str, Any]]:
        """Load profile asset mappings from SettingsService or local fallback."""
        if self._settings_service is not None:
            mappings = self._settings_service.get_asset_mappings(
                profile=self._profile_name or None,
            )
            if isinstance(mappings, dict):
                return mappings
        local = self._extra_settings.get("asset_mappings")
        return local if isinstance(local, dict) else {}

    @staticmethod
    def _build_asset_from_mapping(asset_id: str, mapping: dict[str, Any]) -> Asset | None:
        """Convert a mapping row into a canonical Asset instance."""
        normalized_id = str(asset_id).strip()
        if not normalized_id:
            return None

        display_name = str(
            mapping.get("display_name")
            or mapping.get("name")
            or normalized_id,
        ).strip()
        asset_type = str(mapping.get("asset_type") or "machine").strip().lower()
        if asset_type not in {"machine", "line", "sensor", "seu"}:
            asset_type = "machine"

        aliases: list[str] = []
        raw_aliases = mapping.get("aliases", [])
        if isinstance(raw_aliases, list):
            aliases = [str(alias).strip() for alias in raw_aliases if str(alias).strip()]
        metadata = {
            key: value
            for key, value in mapping.items()
            if key not in {"display_name", "name", "asset_type", "aliases"}
        }

        try:
            return Asset(
                asset_id=normalized_id,
                display_name=display_name or normalized_id,
                asset_type=asset_type,
                aliases=aliases,
                metadata=metadata,
            )
        except ValueError:
            return None
