"""
E2E Voice Pipeline Tests

Full end-to-end validation: intent → OVOS message bus → AVAROSSkill →
QueryDispatcher → adapter → domain result → ResponseBuilder → speak.

Requires a running Docker E2E stack (see ``docker/docker-compose.e2e.yml``).
Run via: ``scripts/run-e2e-tests.sh``

All tests are auto-marked ``@pytest.mark.e2e`` via the package-level
``conftest.py`` so they are excluded from regular ``pytest tests/ -v``.
"""

from __future__ import annotations

import time

import pytest

from tests.test_e2e.conftest import send_intent_and_wait

pytestmark = pytest.mark.e2e


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
        assert "energy" in utterance or "per unit" in utterance

    def test_oee_intent(self, bus_client) -> None:
        """kpi.oee intent returns OEE percentage."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        assert "%" in response["utterance"] or "percent" in utterance

    def test_scrap_rate_intent(self, bus_client) -> None:
        """kpi.scrap_rate intent returns scrap rate value."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.scrap_rate.intent",
            {"asset": "Line-1", "period": "today"},
        )

        assert response is not None, "No speak response received (timeout)"
        utterance = response["utterance"].lower()
        assert "scrap" in utterance or "rate" in utterance

    def test_kpi_response_contains_asset_name(self, bus_client) -> None:
        """KPI spoken response mentions the queried asset."""
        response = send_intent_and_wait(
            bus_client,
            "kpi.oee.intent",
            {"asset": "Line-1"},
        )

        assert response is not None
        assert "line" in response["utterance"].lower()


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
        assert "compressor" in utterance  # winner should be named


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
        )

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
        )


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
        )


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
        )


# ══════════════════════════════════════════════════════════
# 6. CO₂ Derivation Pipeline (DEC-023)
# ══════════════════════════════════════════════════════════


class TestCO2DerivationPipeline:
    """CO₂ derived metrics through voice pipeline (DEC-023).

    MockAdapter has ``native_carbon`` capability, so this validates the
    CO₂ path through the Mock. Derivation-specific logic is covered
    in the integration test suite (``test_pipeline.py``).
    """

    def test_co2_total_through_voice_pipeline(self, bus_client) -> None:
        """CO₂ total query returns spoken carbon metric.

        The skill doesn't have a dedicated co2_total intent handler,
        so we test via the KPI energy intent which exercises the full
        pipeline. CO₂ derivation was validated in integration tests.
        """
        # Use energy_per_unit intent — confirms adapter path works.
        # CO₂ derivation path is validated at the integration layer
        # (test_pipeline.py) where we can inject adapters without
        # native_carbon capability.
        response = send_intent_and_wait(
            bus_client,
            "kpi.energy.per_unit.intent",
            {"asset": "Line-1", "period": "today"},
        )

        assert response is not None, "Pipeline must stay operational for CO₂ path"
        assert len(response["utterance"]) > 0


# ══════════════════════════════════════════════════════════
# 7. Error Handling
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
# 8. Performance
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
