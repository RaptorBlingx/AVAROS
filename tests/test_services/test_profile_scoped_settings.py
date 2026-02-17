"""
Profile-Scoped Settings Tests (DEC-029)

Validates that metric mappings, emission factors, and intent states
are stored per-profile and isolated across profile switches.

All tests use in-memory SQLite — no file I/O.
"""

from __future__ import annotations

from typing import Any

import pytest

from skill.domain.emission_factors import DEFAULT_EMISSION_FACTORS
from skill.domain.exceptions import ValidationError
from skill.services.settings import KNOWN_INTENTS, PlatformConfig, SettingsService


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def service() -> SettingsService:
    """In-memory SettingsService, initialized and ready."""
    svc = SettingsService()
    svc.initialize()
    return svc


@pytest.fixture
def reneryo_config() -> PlatformConfig:
    """A sample RENERYO platform config."""
    return PlatformConfig(
        platform_type="reneryo",
        api_url="https://api.reneryo.example.com",
    )


@pytest.fixture
def sap_config() -> PlatformConfig:
    """A sample SAP platform config."""
    return PlatformConfig(
        platform_type="sap",
        api_url="https://sap.example.com/api",
    )


@pytest.fixture
def sample_mapping() -> dict[str, Any]:
    """A valid metric mapping payload."""
    return {
        "endpoint": "/api/v1/kpis/energy",
        "json_path": "$.data.value",
        "unit": "kWh/unit",
    }


@pytest.fixture
def sap_mapping() -> dict[str, Any]:
    """A second valid metric mapping payload for SAP."""
    return {
        "endpoint": "/sap/energy",
        "json_path": "$.result",
        "unit": "MWh",
    }


# ══════════════════════════════════════════════════════════
# 1. Profile-Scoped Metric Mapping CRUD
# ══════════════════════════════════════════════════════════


class TestProfileScopedMetricMapping:
    """Metric mapping keys include active profile name."""

    def test_set_metric_mapping_uses_active_profile_key(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
        sample_mapping: dict[str, Any],
    ) -> None:
        """DB key includes profile: metric_mapping:reneryo:energy_per_unit."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        service.set_metric_mapping("energy_per_unit", sample_mapping)

        # Verify scoped key exists in raw settings
        keys = service.list_settings()
        assert "metric_mapping:reneryo:energy_per_unit" in keys

    def test_get_metric_mapping_reads_from_active_profile(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Set on reneryo, switch to mock → mock returns None."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        service.set_metric_mapping("energy_per_unit", sample_mapping)

        # Switch to mock
        service.set_active_profile("mock")
        assert service.get_metric_mapping("energy_per_unit") is None

    def test_list_metric_mappings_returns_only_active_profile(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
        sap_config: PlatformConfig,
        sample_mapping: dict[str, Any],
        sap_mapping: dict[str, Any],
    ) -> None:
        """Two profiles with different mappings; list returns only active."""
        service.create_profile("reneryo", reneryo_config)
        service.create_profile("sap-prod", sap_config)

        service.set_active_profile("reneryo")
        service.set_metric_mapping("energy_per_unit", sample_mapping)

        service.set_active_profile("sap-prod")
        service.set_metric_mapping("oee", sap_mapping)

        # Active is sap-prod — only oee visible
        result = service.list_metric_mappings()
        assert len(result) == 1
        assert "oee" in result
        assert "energy_per_unit" not in result

    def test_set_metric_mapping_on_mock_raises_validation_error(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Writing metrics on mock profile raises ValidationError."""
        # Active is mock (default)
        with pytest.raises(ValidationError) as exc_info:
            service.set_metric_mapping("energy_per_unit", sample_mapping)
        assert exc_info.value.field == "profile"


# ══════════════════════════════════════════════════════════
# 2. Profile-Scoped Emission Factor CRUD
# ══════════════════════════════════════════════════════════


class TestProfileScopedEmissionFactor:
    """Emission factors are stored per-profile."""

    def test_set_emission_factor_uses_active_profile_key(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """DB key: emission_factor:reneryo:electricity."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        service.set_emission_factor("electricity", 0.48, country="TR")

        keys = service.list_settings()
        assert "emission_factor:reneryo:electricity" in keys

    def test_get_emission_factor_mock_returns_turkey_default(
        self,
        service: SettingsService,
    ) -> None:
        """Mock profile returns Türkiye defaults for known sources."""
        ef = service.get_emission_factor("electricity")
        assert ef is not None
        assert ef.factor == 0.48
        assert ef.country == "TR"

    def test_list_emission_factors_mock_returns_turkey_defaults(
        self,
        service: SettingsService,
    ) -> None:
        """Mock profile returns all Türkiye defaults."""
        factors = service.list_emission_factors()
        turkey = DEFAULT_EMISSION_FACTORS.get("TR", {})
        assert len(factors) == len(turkey)
        assert "electricity" in factors
        assert factors["electricity"].factor == 0.48

    def test_set_emission_factor_on_mock_raises_validation_error(
        self,
        service: SettingsService,
    ) -> None:
        """Writing emission factor on mock raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.set_emission_factor("electricity", 0.50)
        assert exc_info.value.field == "profile"


# ══════════════════════════════════════════════════════════
# 3. Profile-Scoped Intent Activation
# ══════════════════════════════════════════════════════════


class TestProfileScopedIntentActivation:
    """Intent states are stored per-profile."""

    def test_set_intent_active_uses_active_profile_key(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """DB key: intent_active:reneryo:kpi.oee."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        service.set_intent_active("kpi.oee", False)

        keys = service.list_settings()
        assert "intent_active:reneryo:kpi.oee" in keys

    def test_is_intent_active_mock_returns_true(
        self,
        service: SettingsService,
    ) -> None:
        """Mock profile always returns True for any intent."""
        assert service.is_intent_active("kpi.oee") is True

    def test_list_intent_states_mock_all_true(
        self,
        service: SettingsService,
    ) -> None:
        """Mock profile returns all 8 intents as True."""
        states = service.list_intent_states()
        assert len(states) == 8
        assert all(states.values())

    def test_set_intent_active_on_mock_raises_validation_error(
        self,
        service: SettingsService,
    ) -> None:
        """Writing intent state on mock raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.set_intent_active("kpi.oee", False)
        assert exc_info.value.field == "profile"


# ══════════════════════════════════════════════════════════
# 4. Multi-Profile Isolation
# ══════════════════════════════════════════════════════════


class TestMultiProfileIsolation:
    """Settings are fully isolated across profiles."""

    def test_switch_profile_shows_different_metric_mappings(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
        sap_config: PlatformConfig,
    ) -> None:
        """Reneryo has 3 mappings, SAP has 1 — isolated correctly."""
        service.create_profile("reneryo", reneryo_config)
        service.create_profile("sap-prod", sap_config)

        # Configure reneryo with 3 mappings
        service.set_active_profile("reneryo")
        for metric in ("energy_per_unit", "oee", "scrap_rate"):
            service.set_metric_mapping(metric, {"endpoint": f"/{metric}"})

        # Configure sap with 1 mapping
        service.set_active_profile("sap-prod")
        service.set_metric_mapping("oee", {"endpoint": "/sap/oee"})

        # Switch back to reneryo — 3 mappings
        service.set_active_profile("reneryo")
        assert len(service.list_metric_mappings()) == 3

        # Switch to sap — 1 mapping
        service.set_active_profile("sap-prod")
        assert len(service.list_metric_mappings()) == 1

    def test_switch_profile_preserves_emission_factors(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """EF on reneryo, switch to mock (defaults), back (restored)."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        service.set_emission_factor("electricity", 0.55, country="TR")

        # Switch to mock — Turkey defaults
        service.set_active_profile("mock")
        factors = service.list_emission_factors()
        assert factors["electricity"].factor == 0.48  # default

        # Switch back — custom factor restored
        service.set_active_profile("reneryo")
        ef = service.get_emission_factor("electricity")
        assert ef is not None
        assert ef.factor == 0.55

    def test_switch_profile_preserves_intent_states(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Disable 2 intents on reneryo, mock has all True, back restores."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        service.set_intent_active("kpi.oee", False)
        service.set_intent_active("trend.scrap", False)

        # Switch to mock — all True
        service.set_active_profile("mock")
        states = service.list_intent_states()
        assert all(states.values())

        # Switch back — 2 still disabled
        service.set_active_profile("reneryo")
        assert service.is_intent_active("kpi.oee") is False
        assert service.is_intent_active("trend.scrap") is False
        assert service.is_intent_active("kpi.energy.per_unit") is True


# ══════════════════════════════════════════════════════════
# 5. Voice Config Unaffected
# ══════════════════════════════════════════════════════════


class TestVoiceConfigUnaffected:
    """Voice keys are global — profile switching must not affect them."""

    def test_voice_config_same_across_profiles(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """voice:* keys are not profile-scoped."""
        from skill.services.models import VoiceConfig

        vc = VoiceConfig(
            hivemind_url="ws://localhost:5678",
            hivemind_name="avaros-web",
            hivemind_key="key123",
            hivemind_secret="secret456",
        )
        service.update_voice_config(vc)

        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        retrieved = service.get_voice_config()

        assert retrieved.hivemind_url == "ws://localhost:5678"
        assert retrieved.hivemind_key == "key123"
