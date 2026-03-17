"""Unconfigured adapter — returned when no platform is configured.

Provides clear error messages instructing the user to configure
a platform adapter via the Web UI. Replaces the former MockAdapter
to eliminate confusion between demo and real data paths.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from skill.adapters.base import ManufacturingAdapter
from skill.domain.exceptions import AdapterError

if TYPE_CHECKING:
    from skill.domain.models import (
        Asset,
        CanonicalMetric,
        DataPoint,
        TimePeriod,
    )
    from skill.domain.results import (
        ComparisonResult,
        ConnectionTestResult,
        KPIResult,
        TrendResult,
    )

logger = logging.getLogger(__name__)

_NOT_CONFIGURED_MSG = (
    "No platform adapter is configured. "
    "Please set up a connection in the AVAROS Web UI."
)


class UnconfiguredAdapter(ManufacturingAdapter):
    """Placeholder adapter active when no platform is configured.

    All data methods raise ``AdapterError`` with a user-friendly
    message.  ``test_connection`` returns a failed result pointing
    the user to the Web UI.
    """

    @property
    def platform_name(self) -> str:
        return "Unconfigured"

    async def get_kpi(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> KPIResult:
        raise AdapterError(_NOT_CONFIGURED_MSG)

    async def compare(
        self,
        metric: CanonicalMetric,
        asset_ids: list[str],
        period: TimePeriod,
    ) -> ComparisonResult:
        raise AdapterError(_NOT_CONFIGURED_MSG)

    async def get_trend(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
        granularity: str = "daily",
    ) -> TrendResult:
        raise AdapterError(_NOT_CONFIGURED_MSG)

    async def get_raw_data(
        self,
        metric: CanonicalMetric,
        asset_id: str,
        period: TimePeriod,
    ) -> list[DataPoint]:
        raise AdapterError(_NOT_CONFIGURED_MSG)

    async def list_assets(self) -> list[Asset]:
        return []

    def supports_capability(self, capability: str) -> bool:
        return False

    def supports_asset_discovery(self) -> bool:
        return False

    async def test_connection(self) -> ConnectionTestResult:
        from skill.domain.results import ConnectionTestResult

        return ConnectionTestResult(
            success=False,
            latency_ms=0.0,
            message=_NOT_CONFIGURED_MSG,
            adapter_name=self.platform_name,
        )
