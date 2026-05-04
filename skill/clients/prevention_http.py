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
import statistics
import time
from datetime import timedelta
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
from skill.domain.anomaly_models import (
    AnomalyDetectionResult,
    DriftReport,
    ForecastReport,
)

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
    "carbon": "CO2_DRIFT_CHECK",
    "supplier": "SUPPLIER_DRIFT_CHECK",
}

_CATEGORY_TO_FORECAST_GOAL: dict[str, str] = {
    "energy": "ENERGY_FORECAST",
    "production": "PRODUCTION_FORECAST",
    "material": "MATERIAL_FORECAST",
    "carbon": "CO2_FORECAST",
    "supplier": "SUPPLIER_FORECAST",
}

_HIGHER_IS_BETTER_METRICS = frozenset({
    "oee",
    "throughput",
    "material_efficiency",
    "recycled_content",
    "supplier_on_time",
})

_GRAPHQL_RESULT_REQUEST = (
    '{{ resultRequest(request: [{{request: ["{goal}"]}}])'
    " {{ results reason }} }}"
)

_GRAPHQL_HEALTH_CHECK = "{ allAnalysis { name analyticsGoal analyticsType } }"


class HttpPreventionClient(PreventionClient):
    """GraphQL client for the PREVENTION analytics platform.

    Sends queries to PREVENTION's ``/graphql`` endpoint to retrieve
    pre-computed anomaly and drift analysis results. Data has already
    been loaded into PREVENTION's MongoDB by the AVAROS addon.

    Args:
        url: Base URL of the PREVENTION service (e.g. ``http://prevention:8081``).
        timeout: HTTP request timeout in seconds.
        auth_token: Optional pre-issued bearer token.
        keycloak_token_url: Optional Keycloak/OIDC token endpoint for
            client-credentials authentication.
        keycloak_client_id: Optional Keycloak/OIDC client ID.
        keycloak_client_secret: Optional Keycloak/OIDC client secret.
        keycloak_scope: Optional OAuth scope for token requests.
    """

    def __init__(
        self,
        url: str,
        timeout: int = 30,
        auth_token: str = "",
        keycloak_token_url: str = "",
        keycloak_client_id: str = "",
        keycloak_client_secret: str = "",
        keycloak_scope: str = "",
    ) -> None:
        self._base_url = url.rstrip("/")
        self._graphql_url = f"{self._base_url}/graphql"
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._auth_token = auth_token
        self._keycloak_token_url = keycloak_token_url.strip()
        self._keycloak_client_id = keycloak_client_id.strip()
        self._keycloak_client_secret = keycloak_client_secret.strip()
        self._keycloak_scope = keycloak_scope.strip()
        self._keycloak_access_token = ""
        self._keycloak_token_expires_at = 0.0
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

    async def list_analytics(self) -> list[dict[str, str]]:
        """Return configured PREVENTION analyses for capability reporting."""
        data = await self._query(_GRAPHQL_HEALTH_CHECK)
        analyses = data.get("allAnalysis", [])
        if not isinstance(analyses, list):
            return []
        normalized: list[dict[str, str]] = []
        for item in analyses:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "name": str(item.get("name", "")),
                "analytics_goal": str(
                    item.get("analyticsGoal") or item.get("analytics_goal") or "",
                ),
                "analytics_type": str(
                    item.get("analyticsType") or item.get("analytics_type") or "",
                ).upper(),
            })
        return normalized

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
        asset_id: str | None = None,
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
        except Exception as exc:
            logger.warning(
                "Anomaly query failed for %s; falling back to local series analysis: %s",
                goal,
                exc,
            )
            return _fallback_anomaly_result_from_series(
                metric,
                category,
                data_points,
                threshold,
            )

        return _parse_anomaly_results(
            results,
            metric,
            category,
            data_points,
            threshold,
            asset_id=asset_id,
        )

    # =====================================================================
    # Drift Detection
    # =====================================================================

    async def check_drift(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        periods: int = 7,
        asset_id: str | None = None,
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

        return _parse_drift_results(
            results,
            metric,
            periods,
            asset_id=asset_id,
        )

    # =====================================================================
    # Forecasting
    # =====================================================================

    async def forecast_metric(
        self,
        metric: CanonicalMetric,
        data_points: list[DataPoint],
        horizon_periods: int = 7,
        asset_id: str | None = None,
    ) -> ForecastReport:
        """Retrieve PREVENTION forecast results, with a local series fallback.

        Some PREVENTION deployments expose predictive analysis metadata but do
        not yet return custom KPI forecasts through GraphQL. In that case we
        still use the same explainable linear method over the live series that
        AVAROS collected for the request, and clearly label the method as a
        fallback rather than pretending it was a full provider-side prediction.
        """
        category = _get_category_for_metric(metric)
        goal = _CATEGORY_TO_FORECAST_GOAL.get(category)
        if goal is None:
            return _no_forecast_result(
                metric,
                asset_id,
                horizon_periods,
                f"No forecast analysis configured for {category} metrics.",
            )

        try:
            results = await self._fetch_results(goal)
        except ConnectionError as exc:
            logger.warning(
                "PREVENTION forecast results unavailable for %s; "
                "falling back to local linear forecast: %s",
                goal,
                exc,
            )
            return _fallback_forecast_result_from_series(
                metric,
                data_points,
                horizon_periods,
                asset_id=asset_id,
            )
        except Exception as exc:
            logger.error("Forecast query failed for %s: %s", goal, exc)
            raise ConnectionError(
                f"Failed to query PREVENTION for {goal}",
            ) from exc

        parsed = _parse_forecast_results(
            results,
            metric,
            horizon_periods,
            asset_id=asset_id,
        )
        if parsed.available or results:
            return parsed

        logger.info(
            "PREVENTION returned no forecast rows for %s; "
            "using local linear forecast fallback.",
            goal,
        )
        return _fallback_forecast_result_from_series(
            metric,
            data_points,
            horizon_periods,
            asset_id=asset_id,
        )

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

        try:
            headers = await self._build_headers(session)
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

    async def _build_headers(
        self,
        session: aiohttp.ClientSession,
    ) -> dict[str, str]:
        """Build GraphQL request headers, including optional auth."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        token = await self._resolve_bearer_token(session)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _resolve_bearer_token(
        self,
        session: aiohttp.ClientSession,
    ) -> str:
        """Return a static token or fetch one via Keycloak/OIDC."""
        if self._auth_token:
            return self._auth_token
        if not self._has_keycloak_credentials:
            return ""
        return await self._fetch_keycloak_access_token(session)

    @property
    def _has_keycloak_credentials(self) -> bool:
        """Whether enough Keycloak/OIDC client-credentials config exists."""
        return bool(
            self._keycloak_token_url
            and self._keycloak_client_id
            and self._keycloak_client_secret
        )

    async def _fetch_keycloak_access_token(
        self,
        session: aiohttp.ClientSession,
    ) -> str:
        """Fetch/cache a Keycloak/OIDC access token using client credentials."""
        now = time.monotonic()
        if (
            self._keycloak_access_token
            and now < self._keycloak_token_expires_at - 30
        ):
            return self._keycloak_access_token

        form = {
            "grant_type": "client_credentials",
            "client_id": self._keycloak_client_id,
            "client_secret": self._keycloak_client_secret,
        }
        if self._keycloak_scope:
            form["scope"] = self._keycloak_scope

        try:
            async with session.post(
                self._keycloak_token_url,
                data=form,
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise ConnectionError(
                        "PREVENTION Keycloak token request returned "
                        f"HTTP {resp.status}: {body[:200]}",
                    )
                payload = await resp.json()
        except aiohttp.ClientError as exc:
            raise ConnectionError(
                "Cannot reach PREVENTION Keycloak token endpoint "
                f"at {self._keycloak_token_url}",
            ) from exc

        token = str(payload.get("access_token", "")).strip()
        if not token:
            raise ConnectionError(
                "PREVENTION Keycloak token response did not include access_token",
            )

        try:
            expires_in = int(payload.get("expires_in", 300))
        except (TypeError, ValueError):
            expires_in = 300
        self._keycloak_access_token = token
        self._keycloak_token_expires_at = now + max(expires_in, 60)
        return token

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
    asset_id: str | None = None,
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
        and (asset_id is None or r.get("asset_id") == asset_id)
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
    # Enforce invariant: anomalous results must never have severity "none".
    if severity == "none":
        severity = "low"
    anomaly_type = str(worst.get("anomaly_type", "spike"))
    detected_at = str(worst.get("timestamp", ""))
    if not detected_at:
        detected_at = _get_detection_timestamp(data_points)

    description = _build_anomaly_description(category, True, z_score)
    if len(relevant) > 1:
        description += (
            f" ({len(relevant)} anomalous readings detected; "
            f"showing worst at {z_score:.1f}σ.)"
        )
    action = _get_recommended_action(category, True)

    confidence = min(0.99, 0.7 + (len(results) / 500.0))

    actual_value = float(worst.get("value", 0.0))

    return AnomalyDetectionResult(
        metric=metric,
        is_anomalous=True,
        severity=severity,
        confidence=round(confidence, 2),
        anomaly_type=anomaly_type,
        description=description,
        detected_at=detected_at,
        recommended_action=action,
        expected_value=None,
        actual_value=actual_value,
        deviation=round(z_score, 2),
    )


def _fallback_anomaly_result_from_series(
    metric: CanonicalMetric,
    category: str,
    data_points: list[DataPoint],
    threshold: float,
) -> AnomalyDetectionResult:
    """Derive an anomaly result from the collected series when GraphQL fails."""
    if len(data_points) < 3:
        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=False,
            severity="none",
            confidence=0.4,
            anomaly_type=None,
            description=(
                "Anomaly service is unavailable and there is not enough local "
                "history to evaluate this metric yet."
            ),
            detected_at=_get_detection_timestamp(data_points),
            recommended_action=None,
        )

    baseline_values = [float(point.value) for point in data_points[:-1]]
    latest_point = data_points[-1]
    latest_value = float(latest_point.value)
    baseline_mean = statistics.fmean(baseline_values)
    baseline_std = (
        statistics.pstdev(baseline_values)
        if len(baseline_values) > 1
        else 0.0
    )

    if baseline_std <= 1e-9:
        deviation = 0.0 if abs(latest_value - baseline_mean) <= 1e-9 else threshold + 1.0
    else:
        deviation = abs(latest_value - baseline_mean) / baseline_std

    if deviation < threshold:
        return AnomalyDetectionResult(
            metric=metric,
            is_anomalous=False,
            severity="none",
            confidence=min(0.9, 0.6 + (len(data_points) / 100.0)),
            anomaly_type=None,
            description=_build_anomaly_description(category, False, deviation),
            detected_at=latest_point.timestamp.isoformat(),
            recommended_action=None,
            expected_value=round(baseline_mean, 2),
            actual_value=latest_value,
            deviation=round(deviation, 2),
        )

    anomaly_type = "spike" if latest_value >= baseline_mean else "dip"
    severity = _severity_from_deviation(deviation)
    confidence = min(
        0.95,
        0.65 + (min(deviation, 6.0) / 10.0) + (min(len(data_points), 30) / 200.0),
    )

    return AnomalyDetectionResult(
        metric=metric,
        is_anomalous=True,
        severity=severity,
        confidence=round(confidence, 2),
        anomaly_type=anomaly_type,
        description=_build_anomaly_description(category, True, deviation),
        detected_at=latest_point.timestamp.isoformat(),
        recommended_action=_get_recommended_action(category, True),
        expected_value=round(baseline_mean, 2),
        actual_value=latest_value,
        deviation=round(deviation, 2),
    )


def _severity_from_deviation(deviation: float) -> str:
    """Map z-score style deviation into conversational severity bands."""
    if deviation >= 4.0:
        return "critical"
    if deviation >= 3.0:
        return "high"
    if deviation >= 2.5:
        return "medium"
    return "low"


def _parse_drift_results(
    results: list[dict],
    metric: CanonicalMetric,
    periods: int,
    asset_id: str | None = None,
) -> DriftReport:
    """Parse PREVENTION drift results into domain model."""
    metric_name = metric.value
    match = next(
        (
            r for r in results
            if r.get("metric_name") == metric_name
            and (asset_id is None or r.get("asset_id") == asset_id)
        ),
        None,
    )

    if match is None:
        asset_text = f" for {asset_id}" if asset_id else ""
        return DriftReport(
            metric=metric,
            has_drift=False,
            drift_direction="stable",
            drift_rate=0.0,
            periods_analyzed=0,
            description=(
                f"No drift data found for {metric.display_name}{asset_text} in "
                f"PREVENTION results."
            ),
        )

    has_drift = bool(match.get("has_drift", False))
    rate = float(match.get("drift_rate", 0.0))
    direction = _normalize_drift_direction(
        metric,
        str(match.get("drift_direction", "stable")),
        rate,
    )
    analyzed = int(match.get("periods_analyzed", 0))
    description = str(match.get("description", "")).strip()
    if not description or description == "No data":
        description = _default_drift_description(
            metric,
            direction,
            analyzed or periods,
            asset_id,
        )

    return DriftReport(
        metric=metric,
        has_drift=has_drift,
        drift_direction=direction,
        drift_rate=rate,
        periods_analyzed=analyzed or periods,
        description=description,
    )


def _parse_forecast_results(
    results: list[dict],
    metric: CanonicalMetric,
    horizon_periods: int,
    asset_id: str | None = None,
) -> ForecastReport:
    """Parse PREVENTION forecast rows into a domain forecast report."""
    metric_name = metric.value
    match = next(
        (
            r for r in results
            if r.get("metric_name") == metric_name
            and (asset_id is None or r.get("asset_id") == asset_id)
        ),
        None,
    )

    if match is None:
        asset_text = f" for {asset_id}" if asset_id else ""
        return _no_forecast_result(
            metric,
            asset_id,
            horizon_periods,
            (
                f"No forecast data found for {metric.display_name}"
                f"{asset_text} in PREVENTION results."
            ),
        )

    available = _as_bool(match.get("available", True))
    predicted_value = _optional_float(match.get("predicted_value"))
    analyzed_horizon = _safe_int(match.get("horizon_periods"), horizon_periods)
    description = str(match.get("description", "")).strip()
    if not description:
        description = f"Forecast generated for {metric.display_name}."

    return ForecastReport(
        metric=metric,
        asset_id=str(match.get("asset_id") or asset_id or ""),
        horizon_periods=analyzed_horizon,
        predicted_value=predicted_value,
        unit=metric.default_unit,
        confidence=_bounded_float(match.get("confidence"), 0.0, 0.0, 1.0),
        fit_quality=_bounded_float(match.get("fit_quality"), 0.0, 0.0, 1.0),
        training_points=_safe_int(match.get("training_points"), 0),
        method_name=str(match.get("method_name") or "linear_forecast"),
        forecast_timestamp=str(match.get("forecast_timestamp") or ""),
        description=description,
        recommended_action=(
            str(match.get("recommended_action")).strip()
            if match.get("recommended_action") is not None
            else None
        ),
        available=available and predicted_value is not None,
    )


def _fallback_forecast_result_from_series(
    metric: CanonicalMetric,
    data_points: list[DataPoint],
    horizon_periods: int,
    asset_id: str | None = None,
    min_points: int = 10,
) -> ForecastReport:
    """Build an explainable forecast from caller-supplied live series data."""
    points = sorted(data_points, key=lambda point: point.timestamp)
    values = [float(point.value) for point in points]
    training_points = len(values)
    if training_points < min_points:
        return ForecastReport(
            metric=metric,
            asset_id=asset_id or "",
            horizon_periods=horizon_periods,
            predicted_value=None,
            unit=metric.default_unit,
            confidence=0.0,
            fit_quality=0.0,
            training_points=training_points,
            method_name="local_linear_forecast_fallback",
            forecast_timestamp="",
            description=(
                f"Insufficient data for {metric.display_name}"
                f"{f' on {asset_id}' if asset_id else ''}: "
                f"{training_points} points available, {min_points} required."
            ),
            recommended_action="Collect more history before using this forecast.",
            available=False,
        )

    x_values = list(range(training_points))
    x_mean = statistics.fmean(x_values)
    y_mean = statistics.fmean(values)
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    slope = (
        sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
        / denominator
        if denominator
        else 0.0
    )
    intercept = y_mean - slope * x_mean
    predicted = max(0.0, slope * (training_points + horizon_periods) + intercept)

    fitted = [slope * x + intercept for x in x_values]
    ss_res = sum((actual - expected) ** 2 for actual, expected in zip(values, fitted))
    ss_tot = sum((actual - y_mean) ** 2 for actual in values)
    fit_quality = 1.0 if ss_tot == 0 else 1 - (ss_res / ss_tot)
    fit_quality = max(0.0, min(1.0, fit_quality))
    confidence = max(0.1, min(0.95, fit_quality * min(training_points / 30.0, 1.0)))

    last_timestamp = points[-1].timestamp
    forecast_timestamp = (
        last_timestamp + timedelta(days=horizon_periods)
    ).isoformat()

    direction = "stable"
    if abs(slope) > 0.001:
        direction = "increasing" if slope > 0 else "decreasing"
    action = _forecast_recommended_action(direction)
    asset_text = f" on {asset_id}" if asset_id else ""

    return ForecastReport(
        metric=metric,
        asset_id=asset_id or "",
        horizon_periods=horizon_periods,
        predicted_value=round(float(predicted), 6),
        unit=metric.default_unit,
        confidence=round(float(confidence), 4),
        fit_quality=round(float(fit_quality), 4),
        training_points=training_points,
        method_name="local_linear_forecast_fallback",
        forecast_timestamp=forecast_timestamp,
        description=(
            f"{metric.display_name}{asset_text}: {direction} forecast "
            f"from live series fallback (slope={slope:.6f}, "
            f"R2={fit_quality:.4f})."
        ),
        recommended_action=action,
        available=True,
    )


def _no_forecast_result(
    metric: CanonicalMetric,
    asset_id: str | None,
    horizon_periods: int,
    description: str,
) -> ForecastReport:
    """Return a safe unavailable forecast report."""
    return ForecastReport(
        metric=metric,
        asset_id=asset_id or "",
        horizon_periods=horizon_periods,
        predicted_value=None,
        unit=metric.default_unit,
        confidence=0.0,
        fit_quality=0.0,
        training_points=0,
        method_name="unavailable",
        forecast_timestamp="",
        description=description,
        recommended_action=None,
        available=False,
    )


def _forecast_recommended_action(direction: str) -> str:
    """Generate bounded decision support from a forecast direction."""
    if direction == "increasing":
        return (
            "Review the main operational contributors before this increase "
            "becomes material."
        )
    if direction == "decreasing":
        return (
            "Verify whether this decrease is expected and beneficial for the "
            "process."
        )
    return "Monitor this KPI and review operational drivers if the trend changes."


def _optional_float(value: Any) -> float | None:
    """Parse a float, treating missing/NaN values as unavailable."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _bounded_float(
    value: Any,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    """Parse and clamp a float."""
    parsed = _optional_float(value)
    if parsed is None:
        return default
    return max(minimum, min(maximum, parsed))


def _safe_int(value: Any, default: int) -> int:
    """Parse an int with a default."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    """Parse bool-like result values from PREVENTION output."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"false", "0", "no", "none", ""}
    return bool(value)


def _normalize_drift_direction(
    metric: CanonicalMetric,
    raw_direction: str,
    rate: float,
) -> str:
    """Normalize raw slope directions into domain-level semantics."""
    normalized = raw_direction.strip().lower()
    if normalized in {"stable", "improving", "degrading"}:
        return normalized

    if normalized not in {"increasing", "decreasing"}:
        if abs(rate) < 1e-12:
            return "stable"
        normalized = "increasing" if rate > 0 else "decreasing"

    if metric.value in _HIGHER_IS_BETTER_METRICS:
        return "improving" if normalized == "increasing" else "degrading"
    return "degrading" if normalized == "increasing" else "improving"


def _default_drift_description(
    metric: CanonicalMetric,
    direction: str,
    periods: int,
    asset_id: str | None,
) -> str:
    """Build a fallback drift description when PREVENTION omits one."""
    asset_text = f" on {asset_id}" if asset_id else ""
    if direction == "stable":
        return (
            f"{metric.display_name} is stable{asset_text} across "
            f"{periods} analyzed data points."
        )
    return (
        f"{metric.display_name} is {direction}{asset_text} across "
        f"{periods} analyzed data points."
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
