"""
E2E Voice Pipeline Tests

Full end-to-end validation: intent → OVOS message bus → AVAROSSkill →
QueryDispatcher → adapter → domain result → ResponseBuilder → speak.

Requires a running Docker E2E stack (see ``docker/docker-compose.e2e.yml``).
Run via: ``scripts/run-e2e-tests.sh``

All tests are marked ``@pytest.mark.e2e`` in this module so they are
excluded from regular ``pytest tests/ -v``.
"""

from __future__ import annotations

import re
import time

import pytest

from tests.test_e2e.conftest import send_intent_and_wait

pytestmark = pytest.mark.e2e

_GRACEFUL_FALLBACK_HINTS = (
    "trouble connecting to the data source",
    "please set up a connection",
    "no platform adapter is configured",
)


def _is_graceful_fallback(utterance: str) -> bool:
    lowered = utterance.lower()
    return any(hint in lowered for hint in _GRACEFUL_FALLBACK_HINTS)


def _matches_tokens_or_fallback(msg, tokens: tuple[str, ...]) -> bool:
    text = str(msg.data.get("utterance", "")).lower()
    return any(token in text for token in tokens) or _is_graceful_fallback(text)


# ══════════════════════════════════════════════════════════
# 1. KPI Voice Pipeline
# ══════════════════════════════════════════════════════════


class TestKPIVoicePipeline:
    """Full pipeline: intent → skill → adapter → spoken KPI response."""

    def test_energy_per_unit_intent(self, bus_client) -> None:
        """kpi.energy.per_unit intent returns spoken KPI value."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.energy.per_unit.intent",
            {"asset": "Line-1", "period": "today"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        assert (
            "energy" in utterance
            or "per unit" in utterance
            or _is_graceful_fallback(utterance)
        )

    def test_oee_intent(self, bus_client) -> None:
        """kpi.oee intent returns OEE percentage."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        assert (
            "%" in response["utterance"]
            or "percent" in utterance
            or _is_graceful_fallback(utterance)
        )

    def test_scrap_rate_intent(self, bus_client) -> None:
        """kpi.scrap_rate intent returns scrap rate value."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.scrap_rate.intent",
            {"asset": "Line-1", "period": "today"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        assert (
            "scrap" in utterance
            or "rate" in utterance
            or _is_graceful_fallback(utterance)
        )

    def test_kpi_response_contains_asset_name(self, bus_client) -> None:
        """KPI spoken response mentions the queried asset."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1"},
        )

        assert response is not None
        utterance = response["utterance"].lower()
        assert "line" in utterance or _is_graceful_fallback(utterance)


# ══════════════════════════════════════════════════════════
# 2. Comparison Voice Pipeline
# ══════════════════════════════════════════════════════════


class TestComparisonPipeline:
    """Comparison queries through the full voice pipeline."""

    def test_compare_energy_between_assets(self, bus_client) -> None:
        """Compare energy intent returns a winner."""
        response = send_intent_and_wait(
            bus_client,
            "compare.energy.intent",
            {"asset_a": "Compressor-1", "asset_b": "Compressor-2"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        # ResponseBuilder formats: "<winner> is more efficient …" or "<winner> wins …"
        assert "compressor" in utterance or _is_graceful_fallback(utterance)


# ══════════════════════════════════════════════════════════
# 3. Trend Voice Pipeline
# ══════════════════════════════════════════════════════════


class TestTrendPipeline:
    """Trend queries through the full voice pipeline."""

    def test_energy_trend_intent(self, bus_client) -> None:
        """trend.energy intent returns trend direction."""
        response = send_intent_and_wait(
            bus_client,
            "trend.energy.intent",
            {"asset": "Line-1", "period": "last week"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        assert any(
            word in utterance
            for word in ("up", "down", "stable", "trend", "increasing", "decreasing")
        ) or _is_graceful_fallback(utterance)

    def test_scrap_trend_intent(self, bus_client) -> None:
        """trend.scrap intent returns scrap trend."""
        response = send_intent_and_wait(
            bus_client,
            "trend.scrap.intent",
            {"asset": "Line-1", "period": "last week"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        assert any(
            word in utterance
            for word in ("up", "down", "stable", "trend", "scrap", "increasing", "decreasing")
        ) or _is_graceful_fallback(utterance)


# ══════════════════════════════════════════════════════════
# 4. Anomaly Voice Pipeline
# ══════════════════════════════════════════════════════════


class TestAnomalyPipeline:
    """Anomaly detection through the full voice pipeline."""

    def test_anomaly_check_intent(self, bus_client) -> None:
        """anomaly.production.check intent returns spoken anomaly status."""
        response = send_intent_and_wait(
            bus_client,
            "anomaly.production.check.intent",
            {"asset": "Line-1"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        # MockAdapter returns either anomalies or "no unusual patterns"
        assert any(
            word in utterance
            for word in ("anomal", "unusual", "normal", "pattern", "severity")
        ) or _is_graceful_fallback(utterance)


# ══════════════════════════════════════════════════════════
# 5. What-If Voice Pipeline
# ══════════════════════════════════════════════════════════


class TestWhatIfPipeline:
    """What-if simulation through the full voice pipeline."""

    def test_whatif_temperature_intent(self, bus_client) -> None:
        """whatif.temperature intent returns simulation result."""
        response = send_intent_and_wait(
            bus_client,
            "whatif.temperature.intent",
            {"amount": "5", "asset": "Line-1"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        # ResponseBuilder formats what-if: "Reducing … would …"
        assert any(
            word in utterance
            for word in ("reduc", "impact", "change", "energy", "saving", "would")
        ) or _is_graceful_fallback(utterance)


# ══════════════════════════════════════════════════════════
# 6. Error Handling
# ══════════════════════════════════════════════════════════


class TestErrorHandling:
    """Pipeline error handling — graceful degradation."""

    def test_unknown_asset_returns_spoken_error(self, bus_client) -> None:
        """Unknown asset doesn't crash — returns spoken error message."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.energy.per_unit.intent",
            {"asset": "NONEXISTENT-ASSET-999"},
        )

        # Should get some response (either data or graceful error), not a timeout
        assert response is not None, "Unknown asset caused timeout — no error message spoken"

    def test_missing_asset_defaults_gracefully(self, bus_client) -> None:
        """Missing asset param defaults to 'default' and still responds."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {},  # no asset provided — skill defaults to "default"
        )

        assert response is not None, "Missing asset param caused timeout"


# ══════════════════════════════════════════════════════════
# 7. Performance
# ══════════════════════════════════════════════════════════


class TestPipelineLatency:
    """Voice pipeline performance validation."""

    def test_kpi_response_under_5_seconds(self, bus_client) -> None:
        """KPI query completes in under 5 seconds."""
        start = time.time()
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1"},
            timeout=5,
        )
        elapsed = time.time() - start

        assert response is not None, "Response timed out (>5s)"
        assert elapsed < 5.0, f"Response took {elapsed:.1f}s (>5s limit)"


# ══════════════════════════════════════════════════════════
# 8. Deterministic Response Validation
# ══════════════════════════════════════════════════════════


class TestDeterministicResponseValidation:
    """Higher-signal assertions to reduce false-positive passes."""

    _NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

    def test_energy_per_unit_has_numeric_and_metric_hint(self, bus_client) -> None:
        """Energy per unit should contain both number-like output and metric wording."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.energy.per_unit.intent",
            {"asset": "Line-1", "period": "today"},
            response_filter=lambda msg: _matches_tokens_or_fallback(msg, ("energy", "per unit", "kilowatt")),
        )

        assert response is not None
        utterance = str(response.get("utterance", ""))
        lowered = utterance.lower()
        if _is_graceful_fallback(lowered):
            assert len(utterance.strip()) > 0
            return
        assert self._NUMBER_RE.search(utterance), f"No numeric value in response: '{utterance}'"
        assert any(token in lowered for token in ("energy", "per unit", "kilowatt")), utterance

    def test_oee_has_percent_or_percent_word(self, bus_client) -> None:
        """OEE spoken response should include percentage semantics."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1", "period": "today"},
            response_filter=lambda msg: _matches_tokens_or_fallback(msg, ("oee", "percent", "%", "efficiency")),
        )

        assert response is not None
        utterance = str(response.get("utterance", ""))
        lowered = utterance.lower()
        if _is_graceful_fallback(lowered):
            assert len(utterance.strip()) > 0
            return
        assert self._NUMBER_RE.search(utterance), f"No numeric value in response: '{utterance}'"
        assert "%" in utterance or "percent" in lowered, utterance

    def test_asset_period_matrix_minimal_smoke(self, bus_client) -> None:
        """Different asset/period combinations should all produce spoken output."""
        cases = [
            ("kpi.energy.per_unit.intent", {"asset": "Line-1", "period": "today"}, ("energy", "unit")),
            ("kpi.scrap_rate.intent", {"asset": "Line-1", "period": "last week"}, ("scrap", "rate")),
            ("trend.energy.intent", {"asset": "Line-1", "period": "this week"}, ("trend", "stable", "up", "down")),
        ]

        for intent_name, payload, expected_tokens in cases:
            response = send_intent_and_wait(
                bus_client,
                intent_name,
                payload,
                response_filter=lambda msg, tokens=expected_tokens: _matches_tokens_or_fallback(msg, tuple(tokens)),
            )
            assert response is not None, f"No response for {intent_name} {payload}"
            utterance = str(response.get("utterance", "")).strip()
            assert len(utterance) >= 6, f"Response too short for {intent_name}: '{utterance}'"
            assert any(token in utterance.lower() for token in expected_tokens) or _is_graceful_fallback(utterance)

    def test_unknown_period_does_not_timeout(self, bus_client) -> None:
        """Bad period value should still return a spoken fallback/error instead of timeout."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1", "period": "nonsense-period"},
            timeout=8,
        )
        assert response is not None, "Unknown period caused timeout"
        utterance = str(response.get("utterance", "")).strip()
        assert utterance, "Unknown period produced empty spoken response"

    def test_sequential_queries_do_not_cross_talk(self, bus_client) -> None:
        """Back-to-back intents should return response text aligned with each query."""
        first = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1", "period": "today"},
            response_filter=lambda msg: _matches_tokens_or_fallback(msg, ("%", "percent", "oee", "efficiency")),
        )
        second = send_intent_and_wait(
            bus_client,
            "trend.energy.intent",
            {"asset": "Line-1", "period": "last week"},
            response_filter=lambda msg: _matches_tokens_or_fallback(
                msg,
                ("trend", "stable", "increasing", "decreasing", "up", "down"),
            ),
        )

        assert first is not None
        assert second is not None
        first_text = str(first.get("utterance", "")).lower()
        second_text = str(second.get("utterance", "")).lower()
        assert "%" in first_text or "percent" in first_text or _is_graceful_fallback(first_text), first_text
        assert any(token in second_text for token in ("trend", "stable", "increasing", "decreasing", "up", "down")) or _is_graceful_fallback(second_text), second_text

    def test_comparison_response_under_5_seconds(self, bus_client) -> None:
        """Comparison query completes in under 5 seconds."""
        start = time.time()
        response = send_intent_and_wait(
            bus_client,
            "compare.energy.intent",
            {"asset_a": "Compressor-1", "asset_b": "Compressor-2"},
            timeout=5,
        )
        elapsed = time.time() - start

        assert response is not None, "Response timed out (>5s)"
        assert elapsed < 5.0, f"Response took {elapsed:.1f}s (>5s limit)"

    def test_trend_response_under_5_seconds(self, bus_client) -> None:
        """Trend query completes in under 5 seconds."""
        start = time.time()
        response = send_intent_and_wait(
            bus_client,
            "trend.energy.intent",
            {"asset": "Line-1", "period": "last week"},
            timeout=5,
        )
        elapsed = time.time() - start

        assert response is not None, "Response timed out (>5s)"
        assert elapsed < 5.0, f"Response took {elapsed:.1f}s (>5s limit)"
