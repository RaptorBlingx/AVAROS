"""HttpPreventionClient — GraphQL-based PREVENTION Integration.

Real client for the PREVENTION analytics platform (DEC-019).
Sends GraphQL POST queries to PREVENTION's addon endpoint for
anomaly detection and drift monitoring results.

Platform-agnostic (DEC-001) — translates between AVAROS canonical
metrics and PREVENTION analytics_goal strings. Credentials via
SettingsService (DEC-006). Graceful degradation (DEC-005).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from skill.clients.prevention import PreventionClient
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric, DataPoint

logger = logging.getLogger(__name__)


# =========================================================================
# Canonical Metric → PREVENTION Analytics Goal Mapping
# =========================================================================

_ANOMALY_GOAL_MAP: dict[str, str] = {
    "energy_per_unit": "ENERGY_ANOMALY_CHECK",
    "energy_total": "ENERGY_ANOMALY_CHECK",
    "peak_demand": "ENERGY_ANOMALY_CHECK",
    "peak_tariff_exposure": "ENERGY_ANOMALY_CHECK",
    "oee": "PRODUCTION_ANOMALY_CHECK",
    "throughput": "PRODUCTION_ANOMALY_CHECK",
    "cycle_time": "PRODUCTION_ANOMALY_CHECK",
    "changeover_time": "PRODUCTION_ANOMALY_CHECK",
    "scrap_rate": "MATERIAL_ANOMALY_CHECK",
    "rework_rate": "MATERIAL_ANOMALY_CHECK",
    "material_efficiency": "MATERIAL_ANOMALY_CHECK",
    "recycled_content": "MATERIAL_ANOMALY_CHECK",
    "co2_per_unit": "CO2_ANOMALY_CHECK",
    "co2_total": "CO2_ANOMALY_CHECK",
    "co2_per_batch": "CO2_ANOMALY_CHECK",
    "supplier_lead_time": "SUPPLIER_ANOMALY_CHECK",
    "supplier_defect_rate": "SUPPLIER_ANOMALY_CHECK",
    "supplier_on_time": "SUPPLIER_ANOMALY_CHECK",
    "supplier_co2_per_kg": "SUPPLIER_ANOMALY_CHECK",
}

_DRIFT_GOAL_MAP: dict[str, str] = {
    "energy_per_unit": "ENERGY_DRIFT_CHECK",
    "energy_total": "ENERGY_DRIFT_CHECK",
    "peak_demand": "ENERGY_DRIFT_CHECK",
    "peak_tariff_exposure": "ENERGY_DRIFT_CHECK",
    "oee": "PRODUCTION_DRIFT_CHECK",
    "throughput": "PRODUCTION_DRIFT_CHECK",
    "cycle_time": "PRODUCTION_DRIFT_CHECK",
    "changeover_time": "PRODUCTION_DRIFT_CHECK",
    "scrap_rate": "MATERIAL_DRIFT_CHECK",
    "rework_rate": "MATERIAL_DRIFT_CHECK",
    "material_efficiency": "MATERIAL_DRIFT_CHECK",
    "recycled_content": "MATERIAL_DRIFT_CHECK",
    "co2_per_unit": "CO2_DRIFT_CHECK",
    "co2_total": "CO2_DRIFT_CHECK",
    "co2_per_batch": "CO2_DRIFT_CHECK",
    "supplier_lead_time": "SUPPLIER_DRIFT_CHECK",
    "supplier_defect_rate": "SUPPLIER_DRIFT_CHECK",
    "supplier_on_time": "SUPPLIER_DRIFT_CHECK",
    "supplier_co2_per_kg": "SUPPLIER_DRIFT_CHECK",
}


def _build_graphql_query(analytics_goal: str) -> str:
    """Build a PREVENTION GraphQL resultRequest query."""
    return (
        "query avaros_check {\n"
        "  resultRequest(request: {\n"
        f'    request: "{analytics_goal}"\n'
        '    requestFrom: "DA"\n'
        "  }) {\n"
        "    results\n"
        "    reason\n"
        "  }\n"
        "}"
    )


def _resolve_anomaly_goal(metric: CanonicalMetric) -> str:
    """Map a canonical metric to its PREVENTION anomaly goal."""
    goal = _ANOMALY_GOAL_MAP.get(metric.value)
    if not goal:
        msg = f"No PREVENTION anomaly goal for metric: {metric.value}"
        raise ValueError(msg)
    return goal


def _resolve_drift_goal(metric: CanonicalMetric) -> str:
    """Map a canonical metric to its PREVENTION drift goal."""
    goal = _DRIFT_GOAL_MAP.get(metric.value)
    if not goal:
        msg = f"No PREVENTION drift goal for metric: {metric.value}"
        raise ValueError(msg)
    return goal


def _parse_anomaly_results(
    metric: CanonicalMetric,
    raw_results: list[dict],
) -> AnomalyDetectionResult:
    """
    Parse PREVENTION GraphQL results into AnomalyDetectionResult.

    Examines the results array for anomalous data points returned
    by the ZSCORE_ANOMALY algorithm.
    """
    anomalies = []
    max_severity = "none"
    max_z_score = 0.0
    anomaly_type = None
    severity_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

    for result_set in raw_results:
        records = result_set.get("results", [])
        if isinstance(records, str):
            records = json.loads(records)
        if not isinstance(records, list):
            continue

        for record in records:
            is_flag = record.get("is_anomalous", False)
            if is_flag:
                anomalies.append(record)
                sev = record.get("severity", "low")
                z = abs(record.get("z_score", 0.0))
                if severity_rank.get(sev, 0) > severity_rank.get(max_severity, 0):
                    max_severity = sev
                if z > max_z_score:
                    max_z_score = z
                    anomaly_type = record.get("anomaly_type", "spike")

    is_anomalous = len(anomalies) > 0
    confidence = min(0.95, 0.5 + max_z_score * 0.1) if is_anomalous else 0.9

    description = (
        f"Found {len(anomalies)} anomalous data points with "
        f"max z-score {max_z_score:.1f}σ."
        if is_anomalous
        else "No anomalies detected in the analyzed period."
    )

    return AnomalyDetectionResult(
        metric=metric,
        is_anomalous=is_anomalous,
        severity=max_severity,
        confidence=round(confidence, 2),
        anomaly_type=anomaly_type,
        description=description,
        detected_at=datetime.now(tz=timezone.utc).isoformat(),
        recommended_action=None,
    )


def _parse_drift_results(
    metric: CanonicalMetric,
    raw_results: list[dict],
) -> DriftReport:
    """
    Parse PREVENTION GraphQL results into DriftReport.

    Examines the results array for drift analysis returned
    by the LINEAR_DRIFT algorithm.
    """
    for result_set in raw_results:
        records = result_set.get("results", [])
        if isinstance(records, str):
            records = json.loads(records)
        if not isinstance(records, list):
            continue

        for record in records:
            return DriftReport(
                metric=metric,
                has_drift=record.get("has_drift", False),
                drift_direction=record.get("drift_direction", "stable"),
                drift_rate=record.get("drift_rate", 0.0),
                periods_analyzed=record.get("periods_analyzed", 0),
                description=record.get(
                    "description",
                    "Drift analysis completed.",
                ),
            )

    return DriftReport(
        metric=metric,
        has_drift=False,
        drift_direction="stable",
        drift_rate=0.0,
        periods_analyzed=0,
        description="No drift data returned from PREVENTION.",
    )


class HttpPreventionClient(PreventionClient):
    """
    Real PREVENTION client using GraphQL API.

    Sends GraphQL POST queries to the PREVENTION platform's addon
    endpoint. Maps canonical metrics to PREVENTION analytics_goal
    strings and parses results into domain models.

    Args:
        base_url: PREVENTION GraphQL endpoint base URL
        addon_name: PREVENTION addon name (default: "avaros")
        timeout: HTTP request timeout in seconds
    """

    def __init__(
        self,
        base_url: str,
        addon_name: str = "avaros",
        timeout: float = 30.0,
    ) -> None:
        """Initialize the HTTP PREVENTION client."""
        self._base_url = base_url.rstrip("/")
        self._addon_name = addon_name
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._initialized: bool = False

    @property
    def _graphql_url(self) -> str:
        """Full GraphQL endpoint URL."""
        return f"{self._base_url}/{self._addon_name}"

    # =====================================================================
    # Lifecycle Methods (ExternalServiceClient)
    # =====================================================================

    async def initialize(self) -> None:
        """Establish HTTP connection to PREVENTION."""
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            headers={"Content-Type": "application/json"},
        )
        self._initialized = True
        logger.info(
            "HttpPreventionClient initialized: %s", self._graphql_url,
        )

    async def shutdown(self) -> None:
        """Close HTTP connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._initialized = False
        logger.info("HttpPreventionClient shut down")

    async def health_check(self) -> bool:
        """
        Check if PREVENTION platform is reachable.

        Returns:
            True if the GraphQL endpoint responds
        """
        if not self._client:
            return False
        try:
            resp = await self._client.get(
                self._base_url,
                timeout=5.0,
            )
            return resp.status_code < 500
        except httpx.HTTPError:
            return False

    @property
    def service_name(self) -> str:
        """Human-readable service name."""
        return "PREVENTION Analytics"

    @property
    def is_connected(self) -> bool:
        """Whether the client has an active connection."""
        return self._initialized and self._client is not None

    # =====================================================================
    # GraphQL Query Execution
    # =====================================================================

    async def _execute_query(
        self,
        analytics_goal: str,
    ) -> list[dict]:
        """
        Execute a GraphQL query against PREVENTION.

        Args:
            analytics_goal: PREVENTION analytics goal string

        Returns:
            List of result dictionaries from the response

        Raises:
            ConnectionError: If PREVENTION is unreachable
        """
        if not self._client:
            msg = "HttpPreventionClient not initialized"
            raise ConnectionError(msg)

        query = _build_graphql_query(analytics_goal)
        payload = {"query": query}

        try:
            resp = await self._client.post(
                self._graphql_url,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            msg = f"PREVENTION request failed: {exc}"
            logger.error(msg)
            raise ConnectionError(msg) from exc

        # Extract resultRequest from GraphQL response
        gql_data = data.get("data", {})
        results = gql_data.get("resultRequest", [])

        if not results:
            errors = data.get("errors", [])
            if errors:
                logger.warning("PREVENTION GraphQL errors: %s", errors)

        return results

    # =====================================================================
    # PreventionClient Methods
    # =====================================================================

    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        threshold: float = 2.0,
    ) -> AnomalyDetectionResult:
        """
        Detect anomalies via PREVENTION's ZSCORE_ANOMALY analysis.

        Sends a GraphQL query for the metric's anomaly goal and
        parses the results into an AnomalyDetectionResult.

        Args:
            metric: The canonical metric to analyze
            data_points: Time-series data (used for context)
            threshold: Deviation threshold (configured in addon)

        Returns:
            AnomalyDetectionResult with detection findings

        Raises:
            ConnectionError: If PREVENTION is unreachable
        """
        goal = _resolve_anomaly_goal(metric)
        raw_results = await self._execute_query(goal)
        return _parse_anomaly_results(metric, raw_results)

    async def check_drift(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        periods: int = 7,
    ) -> DriftReport:
        """
        Check for drift via PREVENTION's LINEAR_DRIFT analysis.

        Sends a GraphQL query for the metric's drift goal and
        parses the results into a DriftReport.

        Args:
            metric: The canonical metric to monitor
            data_points: Time-series data (used for context)
            periods: Number of periods (configured in addon)

        Returns:
            DriftReport with drift analysis findings

        Raises:
            ConnectionError: If PREVENTION is unreachable
        """
        goal = _resolve_drift_goal(metric)
        raw_results = await self._execute_query(goal)
        return _parse_drift_results(metric, raw_results)
