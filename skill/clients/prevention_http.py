"""HttpPreventionClient — GraphQL-backed Anomaly Detection and Drift Monitoring.

Connects to the PREVENTION analytics platform via its GraphQL API
to retrieve pre-computed anomaly detection and drift monitoring results.

Platform-agnostic (DEC-001), domain models in skill.domain (DEC-003),
graceful degradation when unavailable (DEC-005).

Note:
    PREVENTION uses a batch analytics model — data is pre-loaded into
    MongoDB and analyses are pre-computed at startup. The ``data_points``
    parameter in ``detect_anomaly`` / ``check_drift`` is accepted for
    interface compatibility but not sent to PREVENTION (which already
    has the data). Results are fetched from pre-computed analytics.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from skill.clients._prevention_demo_data import METRIC_CATEGORY_MAP
from skill.clients.prevention import (
    PreventionClient,
    _build_anomaly_description,
    _get_category_for_metric,
    _get_detection_timestamp,
    _get_recommended_action,
)
from skill.domain.anomaly_models import AnomalyDetectionResult, DriftReport

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric, DataPoint

logger = logging.getLogger(__name__)


# ── Category → PREVENTION Analytics Goal ──────────────────────────

_CATEGORY_TO_ANOMALY_GOAL: dict[str, str] = {
    "energy": "ENERGY_ANOMALY_CHECK",
    "production": "PRODUCTION_ANOMALY_CHECK",
    "material": "MATERIAL_ANOMALY_CHECK",
    "carbon": "CO2_ANOMALY_CHECK",
    "supplier": "SUPPLIER_ANOMALY_CHECK",
}

_CATEGORY_TO_DRIFT_GOAL: dict[str, str] = {
    "energy": "ENERGY_DRIFT_CHECK",
    "production": "PRODUCTION_DRIFT_CHECK",
    "material": "MATERIAL_DRIFT_CHECK",
    "supplier": "SUPPLIER_DRIFT_CHECK",
}

_GRAPHQL_RESULT_REQUEST = (
    '{{ resultRequest(request: [{{request: ["{goal}"]}}])'
    " {{ results reason }} }}"
)

_GRAPHQL_HEALTH_CHECK = "{ allAnalysis { name analyticsGoal } }"


class HttpPreventionClient(PreventionClient):
    """GraphQL client for the PREVENTION analytics platform.

    Sends queries to PREVENTION's ``/graphql`` endpoint to retrieve
    pre-computed anomaly and drift analysis results. Data has already
    been loaded into PREVENTION's MongoDB by the AVAROS addon.

    Args:
        url: Base URL of the PREVENTION service (e.g. ``http://prevention:8081``).
        timeout: HTTP request timeout in seconds.
        auth_token: Optional bearer token for Keycloak authentication.
    """

    def __init__(
        self,
        url: str,
        timeout: int = 30,
        auth_token: str = "",
    ) -> None:
        self._base_url = url.rstrip("/")
        self._graphql_url = f"{self._base_url}/graphql"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._auth_token = auth_token
        self._session: aiohttp.ClientSession | None = None
        self._connected: bool = False

    # =====================================================================
    # Lifecycle (ExternalServiceClient)
    # =====================================================================

    async def initialize(self) -> None:
        """Open the HTTP session and verify connectivity."""
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        try:
            healthy = await self.health_check()
            self._connected = healthy
            if healthy:
                logger.info(
                    "HttpPreventionClient connected to %s",
                    self._graphql_url,
                )
            else:
                logger.warning(
                    "PREVENTION at %s responded but health check failed",
                    self._graphql_url,
                )
        except Exception:
            self._connected = False
            logger.warning(
                "PREVENTION at %s is not reachable",
                self._graphql_url,
            )

    async def shutdown(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        self._connected = False
        logger.info("HttpPreventionClient shut down")

    async def health_check(self) -> bool:
        """Verify PREVENTION is reachable and has analytics goals."""
        try:
            data = await self._query(_GRAPHQL_HEALTH_CHECK)
            analyses = data.get("allAnalysis", [])
            return len(analyses) > 0
        except Exception:
            logger.debug("Health check failed", exc_info=True)
            return False

    @property
    def service_name(self) -> str:
        """Human-readable name (DEC-001: no platform names)."""
        return "Anomaly Detection"

    @property
    def is_connected(self) -> bool:
        """Whether the client has an active connection."""
        return self._connected

    # =====================================================================
    # Anomaly Detection
    # =====================================================================

    async def detect_anomaly(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        threshold: float = 2.0,
    ) -> AnomalyDetectionResult:
        """Retrieve pre-computed anomaly results from PREVENTION.

        Args:
            metric: The canonical metric to analyze.
            data_points: Accepted for interface compatibility (not sent).
            threshold: Deviation threshold (used for result filtering).

        Returns:
            AnomalyDetectionResult from PREVENTION analytics.

        Raises:
            ConnectionError: If PREVENTION is unreachable.
        """
        category = _get_category_for_metric(metric)
        goal = _CATEGORY_TO_ANOMALY_GOAL.get(category)
        if goal is None:
            return self._no_goal_result(metric, category, data_points)

        try:
            results = await self._fetch_results(goal)
        except ConnectionError:
            raise
        except Exception as exc:
            logger.error("Anomaly query failed for %s: %s", goal, exc)
            raise ConnectionError(
                f"Failed to query PREVENTION for {goal}",
            ) from exc

        return _parse_anomaly_results(
            results, metric, category, data_points, threshold,
        )

    # =====================================================================
    # Drift Detection
    # =====================================================================

    async def check_drift(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        periods: int = 7,
    ) -> DriftReport:
        """Retrieve pre-computed drift results from PREVENTION.

        Args:
            metric: The canonical metric to monitor.
            data_points: Accepted for interface compatibility (not sent).
            periods: Number of periods for context in the report.

        Returns:
            DriftReport from PREVENTION analytics.

        Raises:
            ConnectionError: If PREVENTION is unreachable.
        """
        category = _get_category_for_metric(metric)
        goal = _CATEGORY_TO_DRIFT_GOAL.get(category)
        if goal is None:
            return DriftReport(
                metric=metric,
                has_drift=False,
                drift_direction="stable",
                drift_rate=0.0,
                periods_analyzed=0,
                description=f"No drift analysis available for {category} metrics.",
            )

        try:
            results = await self._fetch_results(goal)
        except ConnectionError:
            raise
        except Exception as exc:
            logger.error("Drift query failed for %s: %s", goal, exc)
            raise ConnectionError(
                f"Failed to query PREVENTION for {goal}",
            ) from exc

        return _parse_drift_results(results, metric, periods)

    # =====================================================================
    # GraphQL Communication
    # =====================================================================

    async def _query(self, query_str: str) -> dict[str, Any]:
        """Send a GraphQL query and return the parsed data dict.

        Raises:
            ConnectionError: If the request fails or returns errors.
        """
        session = self._session or aiohttp.ClientSession(
            timeout=self._timeout,
        )
        owns_session = self._session is None

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        try:
            async with session.post(
                self._graphql_url,
                json={"query": query_str},
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise ConnectionError(
                        f"PREVENTION returned HTTP {resp.status}: {body[:200]}",
                    )
                payload = await resp.json()
        except aiohttp.ClientError as exc:
            raise ConnectionError(
                f"Cannot reach PREVENTION at {self._graphql_url}",
            ) from exc
        finally:
            if owns_session:
                await session.close()

        if "errors" in payload:
            error_msg = payload["errors"][0].get("message", "Unknown")
            raise ConnectionError(f"GraphQL error: {error_msg}")

        return payload.get("data", {})

    async def _fetch_results(self, goal: str) -> list[dict]:
        """Fetch resultRequest for a specific analytics goal.

        Returns:
            List of result dicts from PREVENTION.

        Raises:
            ConnectionError: On network or GraphQL errors.
        """
        query = _GRAPHQL_RESULT_REQUEST.format(goal=goal)
        data = await self._query(query)

        result_list = data.get("resultRequest", [])
        if not result_list:
            return []

        entry = result_list[0]
        reason = entry.get("reason")
        if reason:
            _log_prevention_reason(goal, reason)

        raw_results = entry.get("results", [])
        if isinstance(raw_results, str):
            raw_results = json.loads(raw_results)
        return raw_results if isinstance(raw_results, list) else []

    def _no_goal_result(
        self,
        metric: CanonicalMetric,
        category: str,
        data_points: list[DataPoint],
    ) -> AnomalyDetectionResult:
        """Return a safe no-data result when no goal exists."""
        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=False,
            severity="none",
            confidence=0.0,
            anomaly_type=None,
            description=f"No anomaly analysis configured for {category} metrics.",
            detected_at=_get_detection_timestamp(data_points),
            recommended_action=None,
        )


# ── Result Parsing ─────────────────────────────────────────────────


def _parse_anomaly_results(
    results: list[dict],
    metric: CanonicalMetric,
    category: str,
    data_points: list[DataPoint],
    threshold: float,
) -> AnomalyDetectionResult:
    """Parse PREVENTION anomaly results into domain model.

    Uses the caller-supplied *threshold* to re-filter results by
    ``z_score`` rather than trusting the pre-computed ``is_anomalous``
    flag, which was set at PREVENTION container startup with a
    potentially different threshold.
    """
    metric_name = metric.value
    relevant = [
        r for r in results
        if r.get("metric_name") == metric_name
        and float(r.get("z_score", 0)) >= threshold
    ]

    if not relevant:
        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=False,
            severity="none",
            confidence=0.95,
            anomaly_type=None,
            description=_build_anomaly_description(category, False, 0.0),
            detected_at=_get_detection_timestamp(data_points),
            recommended_action=None,
        )

    worst = max(relevant, key=lambda r: r.get("z_score", 0))
    z_score = float(worst.get("z_score", 0))
    severity = str(worst.get("severity", "low"))
    anomaly_type = str(worst.get("anomaly_type", "spike"))
    detected_at = str(worst.get("timestamp", ""))
    if not detected_at:
        detected_at = _get_detection_timestamp(data_points)

    description = _build_anomaly_description(category, True, z_score)
    action = _get_recommended_action(category, True)

    confidence = min(0.99, 0.7 + (len(results) / 500.0))

    return AnomalyDetectionResult(
        metric=metric,
        is_anomalous=True,
        severity=severity,
        confidence=round(confidence, 2),
        anomaly_type=anomaly_type,
        description=description,
        detected_at=detected_at,
        recommended_action=action,
    )


def _parse_drift_results(
    results: list[dict],
    metric: CanonicalMetric,
    periods: int,
) -> DriftReport:
    """Parse PREVENTION drift results into domain model."""
    metric_name = metric.value
    match = next(
        (r for r in results if r.get("metric_name") == metric_name),
        None,
    )

    if match is None:
        return DriftReport(
            metric=metric,
            has_drift=False,
            drift_direction="stable",
            drift_rate=0.0,
            periods_analyzed=0,
            description=(
                f"No drift data found for {metric.display_name} in "
                f"PREVENTION results."
            ),
        )

    has_drift = bool(match.get("has_drift", False))
    direction = str(match.get("drift_direction", "stable"))
    rate = float(match.get("drift_rate", 0.0))
    analyzed = int(match.get("periods_analyzed", 0))
    description = str(
        match.get("description", f"{metric.display_name}: {direction}"),
    )

    return DriftReport(
        metric=metric,
        has_drift=has_drift,
        drift_direction=direction,
        drift_rate=rate,
        periods_analyzed=analyzed or periods,
        description=description,
    )


def _log_prevention_reason(goal: str, reason: Any) -> None:
    """Log PREVENTION error reasons if present."""
    if isinstance(reason, list) and reason:
        for item in reason:
            if isinstance(item, dict):
                code = item.get("code", 0)
                params = item.get("parameters", [])
                if code:
                    logger.warning(
                        "PREVENTION %s reason code=%s: %s",
                        goal, code, params,
                    )
