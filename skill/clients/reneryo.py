"""Focused read-only client for Reneryo domains not covered by KPI mappings."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from skill.domain.exceptions import AdapterError
from skill.domain.reneryo_models import (
    ReneryoMeter,
    ReneryoMetric,
    ReneryoRegression,
    ReneryoTrendPoint,
)
from skill.services.settings import SettingsService


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _api_base_url(raw_url: str) -> str:
    """Normalize a profile URL to the Reneryo API root."""
    url = raw_url.rstrip("/")
    parsed = urlsplit(url)
    path = parsed.path.rstrip("/")
    if path.endswith("/api"):
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/api", "", ""))


def _profile_headers(settings: SettingsService) -> tuple[str, dict[str, str]]:
    profile = settings.get_profile(settings.get_active_profile_name())
    if profile is None or not profile.api_url or not profile.api_key:
        raise AdapterError(
            message="Reneryo profile is not configured",
            code="RENERYO_NOT_CONFIGURED",
            platform="reneryo",
            user_message="The Reneryo data source is not configured.",
        )
    auth_type = str(profile.extra_settings.get("auth_type", "bearer")).lower()
    if auth_type == "custom_header":
        name = str(profile.extra_settings.get("auth_header_name", "X-Token")).strip()
        prefix = str(profile.extra_settings.get("auth_header_prefix", "")).strip()
        value = " ".join(part for part in (prefix, profile.api_key) if part)
        return profile.api_url, {name: value}
    if auth_type == "cookie":
        value = profile.api_key
        return profile.api_url, {"Cookie": value if "=" in value else f"S={value}"}
    if auth_type == "none":
        return profile.api_url, {}
    return profile.api_url, {"Authorization": f"Bearer {profile.api_key}"}


class ReneryoClient:
    """Query Reneryo through its scoped `/a` access-token APIs."""

    def __init__(self, base_url: str, headers: dict[str, str], timeout: int = 30):
        self._base_url = _api_base_url(base_url)
        self._headers = {**headers, "Accept": "application/json"}
        self._timeout = timeout

    @classmethod
    def from_runtime(cls, settings: SettingsService) -> ReneryoClient:
        """Use deployment overrides or the active AVAROS profile."""
        base_url = os.environ.get("RENERYO_API_BASE_URL", "").strip()
        token = os.environ.get("RENERYO_ACCESS_TOKEN", "").strip()
        if base_url and token:
            return cls(base_url, {"X-Token": token})
        profile_url, headers = _profile_headers(settings)
        return cls(profile_url, headers)

    async def list_metrics(self) -> list[ReneryoMetric]:
        payload = await self._get("/a/metric/item")
        return [self._metric(row) for row in self._records(payload)]

    async def list_meters(self, start: datetime, end: datetime) -> list[ReneryoMeter]:
        payload = await self._get(
            "/a/meter/item",
            {
                "datetimeMin": start.isoformat(),
                "datetimeMax": (end - timedelta(microseconds=1)).isoformat(),
            },
        )
        meters: list[ReneryoMeter] = []
        for row in self._records(payload):
            metric = row.get("metric") if isinstance(row.get("metric"), dict) else {}
            slices = row.get("slices") if isinstance(row.get("slices"), list) else []
            meters.append(
                ReneryoMeter(
                    meter_id=str(row.get("id", "")),
                    name=str(row.get("name", "")),
                    energy_resource=str(row.get("energyResource", "")),
                    consumption=_optional_float(row.get("consumption")),
                    metric_id=str(metric.get("id", "")),
                    metric_name=str(metric.get("name", "")),
                    slice_names=tuple(
                        str(item.get("department", {}).get("name", ""))
                        for item in slices
                        if isinstance(item, dict)
                    ),
                )
            )
        return meters

    async def metric_values(
        self,
        metric_id: str,
        start: datetime,
        end: datetime,
        period: str,
    ) -> list[ReneryoTrendPoint]:
        points: list[ReneryoTrendPoint] = []
        page = 1
        while True:
            payload = await self._get(
                f"/a/metric/values/{metric_id}",
                {
                    "datetimeMin": start.isoformat(),
                    "datetimeMax": (end - timedelta(microseconds=1)).isoformat(),
                    "period": period,
                    "count": "100",
                    "page": str(page),
                },
            )
            rows = self._records(payload)
            for row in rows:
                timestamp = _parse_datetime(row.get("datetime"))
                value = _optional_float(row.get("value"))
                if (
                    timestamp is None
                    or value is None
                    or not start <= timestamp < end
                    or int(row.get("sampleCount") or 0) <= 0
                ):
                    continue
                points.append(
                    ReneryoTrendPoint(
                        timestamp=timestamp,
                        value=value,
                        sample_count=int(row.get("sampleCount") or 0),
                    )
                )
            if not rows or page * 100 >= int(payload.get("recordCount") or 0):
                break
            page += 1
        return sorted(points, key=lambda point: point.timestamp)

    async def recent_metric_values(
        self, metric: ReneryoMetric, count: int = 12
    ) -> tuple[list[ReneryoTrendPoint], int]:
        """Read a bounded tail of Reneryo monthly aggregates, regardless of age.

        Reneryo owns counter deltas and gauge aggregation. Never derive period
        consumption from the inventory's cumulative lastValue.
        """
        payload = await self._get(
            f"/a/metric/values/{metric.metric_id}",
            {
                "datetimeMin": "1900-01-01T00:00:00+00:00",
                "datetimeMax": (
                    (metric.last_value_at + timedelta(days=1))
                    if metric.last_value_at
                    else datetime.now(timezone.utc)
                ).isoformat(),
                "period": "MONTHLY",
                "count": str(min(100, max(1, count))),
                "page": "1",
                "descending": "true",
            },
        )
        points = []
        for row in self._records(payload):
            timestamp = _parse_datetime(row.get("datetime"))
            value = _optional_float(row.get("value"))
            samples = int(row.get("sampleCount") or 0)
            if timestamp is not None and value is not None and samples > 0:
                points.append(ReneryoTrendPoint(timestamp, value, samples))
        return sorted(points, key=lambda p: p.timestamp), int(
            payload.get("recordCount") or 0
        )

    async def list_regressions(self) -> list[ReneryoRegression]:
        advanced, linear = await _gather(
            self._get("/a/analysis/advanced-regression/results"),
            self._get("/a/analysis/linear-regression/results"),
        )
        return [
            *[self._advanced_regression(row) for row in self._records(advanced)],
            *[self._linear_regression(row) for row in self._records(linear)],
        ]

    async def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=self._timeout)
        async with aiohttp.ClientSession(
            timeout=timeout, headers=self._headers
        ) as session:
            try:
                async with session.get(
                    f"{self._base_url}{path}", params=params
                ) as response:
                    if response.status < 200 or response.status >= 300:
                        raise AdapterError(
                            message=f"Reneryo returned HTTP {response.status} for {path}",
                            code="RENERYO_REQUEST_FAILED",
                            platform="reneryo",
                            status_code=response.status,
                            user_message="Reneryo data is temporarily unavailable.",
                        )
                    payload = await response.json()
            except (aiohttp.ClientError, TimeoutError) as exc:
                raise AdapterError(
                    message=f"Reneryo request failed for {path}: {exc}",
                    code="RENERYO_REQUEST_FAILED",
                    platform="reneryo",
                    user_message="Reneryo data is temporarily unavailable.",
                ) from exc
        if not isinstance(payload, dict):
            raise AdapterError(
                message=f"Unexpected Reneryo response for {path}",
                code="RENERYO_INVALID_RESPONSE",
                platform="reneryo",
            )
        return payload

    @staticmethod
    def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        records = payload.get("records", [])
        return (
            [row for row in records if isinstance(row, dict)]
            if isinstance(records, list)
            else []
        )

    @staticmethod
    def _metric(row: dict[str, Any]) -> ReneryoMetric:
        return ReneryoMetric(
            metric_id=str(row.get("id", "")),
            name=str(row.get("name", "")),
            metric_type=str(row.get("type", "")),
            unit_group=str(row.get("unitGroup", "")),
            last_value=_optional_float(row.get("lastValue")),
            last_value_at=_parse_datetime(row.get("lastValueDatetime")),
        )

    @staticmethod
    def _advanced_regression(row: dict[str, Any]) -> ReneryoRegression:
        drivers = row.get("drivers") if isinstance(row.get("drivers"), list) else []
        slices = row.get("slices") if isinstance(row.get("slices"), list) else []
        return ReneryoRegression(
            regression_id=str(row.get("id", "")),
            regression_type="advanced",
            driver_names=tuple(
                str(item.get("name", "")) for item in drivers if isinstance(item, dict)
            ),
            slice_names=tuple(
                str(item.get("name", "")) for item in slices if isinstance(item, dict)
            ),
            period=str(row.get("period", "")),
            r_squared=_optional_float(row.get("rSquared")),
            rmse=_optional_float(row.get("rmse")),
            primary=bool(row.get("primary")),
            train_start=_parse_datetime(row.get("dateTrainStart"))
            or datetime.min.replace(tzinfo=timezone.utc),
            train_end=_parse_datetime(row.get("dateTrainEnd"))
            or datetime.min.replace(tzinfo=timezone.utc),
            predict_start=_parse_datetime(row.get("datePredictStart")),
            predict_end=_parse_datetime(row.get("datePredictEnd")),
        )

    @staticmethod
    def _linear_regression(row: dict[str, Any]) -> ReneryoRegression:
        driver = row.get("driver") if isinstance(row.get("driver"), dict) else {}
        slices = (
            row.get("meterSlices") if isinstance(row.get("meterSlices"), list) else []
        )
        start = _parse_datetime(row.get("datetimeStart")) or datetime.min.replace(
            tzinfo=timezone.utc
        )
        end = _parse_datetime(row.get("datetimeEnd")) or datetime.min.replace(
            tzinfo=timezone.utc
        )
        return ReneryoRegression(
            regression_id=str(row.get("id", "")),
            regression_type="linear",
            driver_names=(str(driver.get("name", "")),),
            slice_names=tuple(
                str(item.get("name", "")) for item in slices if isinstance(item, dict)
            ),
            period=str(row.get("period", "")),
            r_squared=_optional_float(row.get("rSquared")),
            rmse=None,
            primary=False,
            train_start=start,
            train_end=end,
            predict_start=start,
            predict_end=end,
        )


async def _gather(*coroutines):
    import asyncio

    return await asyncio.gather(*coroutines)


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
