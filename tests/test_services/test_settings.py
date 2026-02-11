"""
SettingsService Test Suite

Covers existing functionality (platform config, generic settings, encryption,
lifecycle) AND new metric mapping CRUD methods.

All tests use in-memory SQLite — no file I/O.
"""

from __future__ import annotations

import pytest
from typing import Any

from skill.services.settings import SettingsService, PlatformConfig
from skill.domain.exceptions import ValidationError
from skill.domain.models import CanonicalMetric


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def service() -> SettingsService:
    """In-memory SettingsService, initialized and ready."""
    svc = SettingsService()
    svc.initialize()
    return svc


@pytest.fixture
def uninitialized_service() -> SettingsService:
    """SettingsService before initialize() is called."""
    return SettingsService()


@pytest.fixture
def sample_mapping() -> dict[str, Any]:
    """A valid metric mapping payload."""
    return {
        "canonical_metric": "energy_per_unit",
        "endpoint": "/api/v1/kpis/energy",
        "json_path": "$.data.value",
        "unit": "kWh/unit",
        "transform": None,
    }


@pytest.fixture
def sample_mapping_scrap() -> dict[str, Any]:
    """A second valid metric mapping payload."""
    return {
        "canonical_metric": "scrap_rate",
        "endpoint": "/api/v1/kpis/scrap",
        "json_path": "$.data.rate",
        "unit": "%",
        "transform": None,
    }


@pytest.fixture
def sample_mapping_co2() -> dict[str, Any]:
    """A third valid metric mapping payload."""
    return {
        "canonical_metric": "co2_per_unit",
        "endpoint": "/api/v1/kpis/co2",
        "json_path": "$.emissions.value",
        "unit": "kgCO2/unit",
        "transform": "multiply_by_1000",
    }


# ══════════════════════════════════════════════════════════
# 1. SettingsService Initialization & Lifecycle
# ══════════════════════════════════════════════════════════


class TestSettingsServiceInit:
    """Tests for __init__ and initialize()."""

    def test_init_in_memory_default_creates_service(self) -> None:
        """In-memory construction succeeds without arguments."""
        svc = SettingsService()
        assert svc._database_url == "sqlite:///:memory:"
        assert svc._initialized is False

    def test_init_with_database_url_stores_url(self) -> None:
        """Construction with database_url stores the URL."""
        url = "postgresql://avaros:avaros@localhost:5432/avaros"
        svc = SettingsService(database_url=url)
        assert svc._database_url == url

    def test_init_with_custom_encryption_key(self) -> None:
        """Custom encryption key is accepted."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        svc = SettingsService(encryption_key=key)
        svc.initialize()
        # Should be usable — store & retrieve encrypted value
        svc.set_setting("secret", "my_value", encrypt=True)
        assert svc.get_setting("secret") == "my_value"

    def test_init_reads_env_var_fallback(self, monkeypatch) -> None:
        """When no explicit URL, reads AVAROS_DATABASE_URL env var."""
        monkeypatch.setenv(
            "AVAROS_DATABASE_URL",
            "postgresql://u:p@host:5432/db",
        )
        svc = SettingsService()
        assert svc._database_url == "postgresql://u:p@host:5432/db"

    def test_init_explicit_url_overrides_env_var(self, monkeypatch) -> None:
        """Explicit database_url takes precedence over env var."""
        monkeypatch.setenv(
            "AVAROS_DATABASE_URL",
            "postgresql://u:p@host:5432/db",
        )
        svc = SettingsService(database_url="sqlite:///:memory:")
        assert svc._database_url == "sqlite:///:memory:"

    def test_initialize_creates_tables(self, service: SettingsService) -> None:
        """initialize() creates the settings table."""
        assert service._initialized is True
        assert service._engine is not None

    def test_initialize_idempotent_no_error(self, service: SettingsService) -> None:
        """Calling initialize() twice does not raise."""
        service.initialize()
        service.initialize()
        assert service._initialized is True

    def test_close_disposes_engine(self, service: SettingsService) -> None:
        """close() disposes the engine and resets initialized flag."""
        service.close()
        assert service._initialized is False

    def test_close_on_uninitialized_no_error(
        self, uninitialized_service: SettingsService
    ) -> None:
        """close() on an uninitialized service does not raise."""
        uninitialized_service.close()


# ══════════════════════════════════════════════════════════
# 2. Auto-Initialize (lazy init)
# ══════════════════════════════════════════════════════════


class TestAutoInitialize:
    """Methods must auto-initialize if not already done."""

    def test_is_configured_auto_initializes(
        self, uninitialized_service: SettingsService
    ) -> None:
        """is_configured() triggers auto-initialization."""
        assert uninitialized_service._initialized is False
        uninitialized_service.is_configured()
        assert uninitialized_service._initialized is True

    def test_get_setting_auto_initializes(
        self, uninitialized_service: SettingsService
    ) -> None:
        """get_setting() triggers auto-initialization."""
        uninitialized_service.get_setting("key")
        assert uninitialized_service._initialized is True


# ══════════════════════════════════════════════════════════
# 3. Platform Configuration
# ══════════════════════════════════════════════════════════


class TestPlatformConfig:
    """Tests for PlatformConfig dataclass."""

    def test_default_config_is_mock(self) -> None:
        """Default PlatformConfig uses mock adapter."""
        config = PlatformConfig()
        assert config.platform_type == "mock"
        assert config.api_url == ""
        assert config.api_key == ""

    def test_is_configured_mock_returns_false(self) -> None:
        """Mock config is not considered 'configured'."""
        assert PlatformConfig().is_configured is False

    def test_is_configured_reneryo_with_url_returns_true(self) -> None:
        """Real platform with URL is configured."""
        config = PlatformConfig(
            platform_type="reneryo",
            api_url="https://api.reneryo.com",
        )
        assert config.is_configured is True

    def test_is_configured_non_mock_without_url_returns_false(self) -> None:
        """Non-mock but without URL is not configured."""
        config = PlatformConfig(platform_type="reneryo")
        assert config.is_configured is False

    def test_to_dict_round_trip(self) -> None:
        """to_dict() and from_dict() produce identical configs."""
        original = PlatformConfig(
            platform_type="reneryo",
            api_url="https://example.com",
            api_key="secret",
            extra_settings={"timeout": 30},
        )
        restored = PlatformConfig.from_dict(original.to_dict())
        assert restored.platform_type == original.platform_type
        assert restored.api_url == original.api_url
        assert restored.api_key == original.api_key
        assert restored.extra_settings == original.extra_settings

    def test_from_dict_missing_keys_uses_defaults(self) -> None:
        """from_dict() with empty dict uses default values."""
        config = PlatformConfig.from_dict({})
        assert config.platform_type == "mock"
        assert config.api_url == ""


class TestPlatformConfigService:
    """Tests for platform config via SettingsService."""

    def test_get_platform_config_first_run_returns_default(
        self, service: SettingsService
    ) -> None:
        """First run returns default mock config."""
        config = service.get_platform_config()
        assert config.platform_type == "mock"
        assert config.is_configured is False

    def test_is_configured_first_run_returns_false(
        self, service: SettingsService
    ) -> None:
        """is_configured() returns False on fresh database."""
        assert service.is_configured() is False

    def test_update_platform_config_saves_and_retrieves(
        self, service: SettingsService
    ) -> None:
        """update_platform_config() persists and can be retrieved."""
        config = PlatformConfig(
            platform_type="reneryo",
            api_url="https://api.reneryo.com",
            api_key="my-secret-key",
        )
        service.update_platform_config(config)

        retrieved = service.get_platform_config()
        assert retrieved.platform_type == "reneryo"
        assert retrieved.api_url == "https://api.reneryo.com"
        assert retrieved.api_key == "my-secret-key"

    def test_update_platform_config_api_key_encrypted(
        self, service: SettingsService
    ) -> None:
        """API key is encrypted at rest in the database."""
        config = PlatformConfig(
            platform_type="reneryo",
            api_url="https://api.reneryo.com",
            api_key="super-secret",
        )
        service.update_platform_config(config)

        # Read raw value from DB — should not contain plaintext
        raw = service.get_setting("platform_config")
        assert isinstance(raw, dict)
        assert raw["api_key"] != "super-secret"

    def test_update_platform_config_is_configured_returns_true(
        self, service: SettingsService
    ) -> None:
        """After saving real config, is_configured() returns True."""
        service.update_platform_config(
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.com",
            )
        )
        assert service.is_configured() is True

    def test_update_platform_config_overwrite(
        self, service: SettingsService
    ) -> None:
        """Updating config twice overwrites the first."""
        service.update_platform_config(
            PlatformConfig(platform_type="reneryo", api_url="https://v1.com")
        )
        service.update_platform_config(
            PlatformConfig(platform_type="reneryo", api_url="https://v2.com")
        )
        assert service.get_platform_config().api_url == "https://v2.com"


# ══════════════════════════════════════════════════════════
# 4. Generic Settings CRUD
# ══════════════════════════════════════════════════════════


class TestGenericSettings:
    """Tests for get_setting / set_setting / delete_setting / list_settings."""

    def test_get_setting_missing_returns_default(
        self, service: SettingsService
    ) -> None:
        """get_setting() returns default when key not found."""
        assert service.get_setting("nonexistent") is None
        assert service.get_setting("nonexistent", "fallback") == "fallback"

    def test_set_and_get_string_value(self, service: SettingsService) -> None:
        """Simple string round-trip."""
        service.set_setting("language", "en-us")
        assert service.get_setting("language") == "en-us"

    def test_set_and_get_dict_value(self, service: SettingsService) -> None:
        """Dict value is JSON-serialized and deserialized."""
        data = {"key": "value", "nested": {"a": 1}}
        service.set_setting("complex", data)
        assert service.get_setting("complex") == data

    def test_set_and_get_list_value(self, service: SettingsService) -> None:
        """List value round-trip."""
        data = [1, 2, 3]
        service.set_setting("numbers", data)
        assert service.get_setting("numbers") == data

    def test_set_setting_encrypted_round_trip(
        self, service: SettingsService
    ) -> None:
        """Encrypted setting can be stored and retrieved."""
        service.set_setting("api_token", "secret-token", encrypt=True)
        assert service.get_setting("api_token") == "secret-token"

    def test_set_setting_overwrite(self, service: SettingsService) -> None:
        """Setting the same key twice overwrites."""
        service.set_setting("key", "first")
        service.set_setting("key", "second")
        assert service.get_setting("key") == "second"

    def test_delete_setting_existing_returns_true(
        self, service: SettingsService
    ) -> None:
        """delete_setting() returns True for existing key."""
        service.set_setting("to_delete", "value")
        assert service.delete_setting("to_delete") is True
        assert service.get_setting("to_delete") is None

    def test_delete_setting_missing_returns_false(
        self, service: SettingsService
    ) -> None:
        """delete_setting() returns False for missing key."""
        assert service.delete_setting("nonexistent") is False

    def test_list_settings_empty(self, service: SettingsService) -> None:
        """list_settings() returns empty list on fresh DB."""
        assert service.list_settings() == []

    def test_list_settings_returns_all_keys(
        self, service: SettingsService
    ) -> None:
        """list_settings() returns all stored keys."""
        service.set_setting("a", 1)
        service.set_setting("b", 2)
        keys = service.list_settings()
        assert sorted(keys) == ["a", "b"]


# ══════════════════════════════════════════════════════════
# 5. Metric Mapping — set_metric_mapping
# ══════════════════════════════════════════════════════════


class TestSetMetricMapping:
    """Tests for set_metric_mapping()."""

    def test_set_metric_mapping_stores_successfully(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Valid metric mapping is persisted."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        result = service.get_metric_mapping("energy_per_unit")
        assert result == sample_mapping

    def test_set_metric_mapping_invalid_name_raises_validation_error(
        self, service: SettingsService
    ) -> None:
        """Invalid metric name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.set_metric_mapping("bogus_metric", {"endpoint": "/x"})
        assert exc_info.value.field == "metric_name"
        assert "bogus_metric" in exc_info.value.message

    def test_set_metric_mapping_overwrite_updates_value(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Calling set_metric_mapping twice with same name overwrites."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        updated = {**sample_mapping, "unit": "MWh/unit"}
        service.set_metric_mapping("energy_per_unit", updated)
        assert service.get_metric_mapping("energy_per_unit")["unit"] == "MWh/unit"

    @pytest.mark.parametrize(
        "metric",
        [m.value for m in CanonicalMetric],
        ids=[m.name for m in CanonicalMetric],
    )
    def test_set_metric_mapping_accepts_all_canonical_metrics(
        self, service: SettingsService, metric: str
    ) -> None:
        """Every CanonicalMetric value is accepted without error."""
        service.set_metric_mapping(metric, {"endpoint": f"/api/{metric}"})
        assert service.get_metric_mapping(metric) is not None


# ══════════════════════════════════════════════════════════
# 6. Metric Mapping — get_metric_mapping
# ══════════════════════════════════════════════════════════


class TestGetMetricMapping:
    """Tests for get_metric_mapping()."""

    def test_get_metric_mapping_returns_stored_data(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Retrieves the exact mapping data that was stored."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        assert service.get_metric_mapping("energy_per_unit") == sample_mapping

    def test_get_metric_mapping_nonexistent_returns_none(
        self, service: SettingsService
    ) -> None:
        """Returns None for a metric that has no mapping."""
        assert service.get_metric_mapping("energy_per_unit") is None

    def test_get_metric_mapping_after_delete_returns_none(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """After deletion, get returns None."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        service.delete_metric_mapping("energy_per_unit")
        assert service.get_metric_mapping("energy_per_unit") is None


# ══════════════════════════════════════════════════════════
# 7. Metric Mapping — list_metric_mappings
# ══════════════════════════════════════════════════════════


class TestListMetricMappings:
    """Tests for list_metric_mappings()."""

    def test_list_metric_mappings_empty_returns_empty_dict(
        self, service: SettingsService
    ) -> None:
        """No mappings → empty dict."""
        assert service.list_metric_mappings() == {}

    def test_list_metric_mappings_single(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """One mapping → dict with one entry."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        result = service.list_metric_mappings()
        assert len(result) == 1
        assert "energy_per_unit" in result
        assert result["energy_per_unit"] == sample_mapping

    def test_list_metric_mappings_multiple(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
        sample_mapping_scrap: dict[str, Any],
        sample_mapping_co2: dict[str, Any],
    ) -> None:
        """Three mappings → dict with three entries."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        service.set_metric_mapping("scrap_rate", sample_mapping_scrap)
        service.set_metric_mapping("co2_per_unit", sample_mapping_co2)

        result = service.list_metric_mappings()
        assert len(result) == 3
        assert set(result.keys()) == {
            "energy_per_unit",
            "scrap_rate",
            "co2_per_unit",
        }

    def test_list_metric_mappings_excludes_non_mapping_settings(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Generic settings and platform_config are NOT included."""
        service.set_setting("language", "en-us")
        service.update_platform_config(
            PlatformConfig(platform_type="reneryo", api_url="https://x.com")
        )
        service.set_metric_mapping("energy_per_unit", sample_mapping)

        result = service.list_metric_mappings()
        assert len(result) == 1
        assert "energy_per_unit" in result


# ══════════════════════════════════════════════════════════
# 8. Metric Mapping — delete_metric_mapping
# ══════════════════════════════════════════════════════════


class TestDeleteMetricMapping:
    """Tests for delete_metric_mapping()."""

    def test_delete_metric_mapping_existing_returns_true(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Deleting an existing mapping returns True."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        assert service.delete_metric_mapping("energy_per_unit") is True

    def test_delete_metric_mapping_nonexistent_returns_false(
        self, service: SettingsService
    ) -> None:
        """Deleting a nonexistent mapping returns False."""
        assert service.delete_metric_mapping("energy_per_unit") is False

    def test_delete_metric_mapping_removes_from_list(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
        sample_mapping_scrap: dict[str, Any],
    ) -> None:
        """After deletion, mapping is gone from list_metric_mappings."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        service.set_metric_mapping("scrap_rate", sample_mapping_scrap)
        service.delete_metric_mapping("energy_per_unit")

        result = service.list_metric_mappings()
        assert len(result) == 1
        assert "scrap_rate" in result
        assert "energy_per_unit" not in result


# ══════════════════════════════════════════════════════════
# 9. Metric Mapping — Isolation
# ══════════════════════════════════════════════════════════


class TestMetricMappingIsolation:
    """Metric mappings must not interfere with other settings."""

    def test_metric_mapping_does_not_affect_platform_config(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Storing a mapping does not corrupt platform config."""
        service.update_platform_config(
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.com",
                api_key="secret",
            )
        )
        service.set_metric_mapping("energy_per_unit", sample_mapping)

        config = service.get_platform_config()
        assert config.platform_type == "reneryo"
        assert config.api_key == "secret"

    def test_platform_config_does_not_affect_metric_mappings(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Updating platform config does not corrupt metric mappings."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        service.update_platform_config(
            PlatformConfig(platform_type="mock")
        )

        assert service.get_metric_mapping("energy_per_unit") == sample_mapping

    def test_generic_setting_does_not_appear_as_metric_mapping(
        self, service: SettingsService
    ) -> None:
        """A setting with metric_mapping-like key but set via set_setting
        does appear in list_metric_mappings (since it uses same storage).
        But generic settings WITHOUT the prefix do not."""
        service.set_setting("unrelated_key", {"data": 1})
        assert service.list_metric_mappings() == {}


# ══════════════════════════════════════════════════════════
# 10. Metric Mapping — Validation Edge Cases
# ══════════════════════════════════════════════════════════


class TestMetricMappingValidation:
    """Edge cases for metric name validation."""

    def test_empty_string_raises_validation_error(
        self, service: SettingsService
    ) -> None:
        """Empty string is not a valid metric name."""
        with pytest.raises(ValidationError):
            service.set_metric_mapping("", {"endpoint": "/x"})

    def test_uppercase_name_raises_validation_error(
        self, service: SettingsService
    ) -> None:
        """CanonicalMetric values are lowercase; uppercase is invalid."""
        with pytest.raises(ValidationError):
            service.set_metric_mapping("ENERGY_PER_UNIT", {"endpoint": "/x"})

    def test_partial_name_raises_validation_error(
        self, service: SettingsService
    ) -> None:
        """Partial metric name is not valid."""
        with pytest.raises(ValidationError):
            service.set_metric_mapping("energy", {"endpoint": "/x"})

    def test_platform_specific_name_raises_validation_error(
        self, service: SettingsService
    ) -> None:
        """Platform-specific names (DEC-002 violation) are rejected."""
        with pytest.raises(ValidationError):
            service.set_metric_mapping("seu", {"endpoint": "/x"})

    def test_validation_error_contains_field_and_value(
        self, service: SettingsService
    ) -> None:
        """ValidationError includes field='metric_name' and the bad value."""
        with pytest.raises(ValidationError) as exc_info:
            service.set_metric_mapping("invalid_metric", {"endpoint": "/x"})
        err = exc_info.value
        assert err.field == "metric_name"
        assert err.value == "invalid_metric"
        assert err.code == "VALIDATION_ERROR"


# ══════════════════════════════════════════════════════════
# 11. Encryption
# ══════════════════════════════════════════════════════════


class TestEncryption:
    """Encryption round-trip tests."""

    def test_encrypt_decrypt_round_trip(self, service: SettingsService) -> None:
        """Encrypting then decrypting returns original value."""
        original = "my-secret-api-key-12345"
        encrypted = service._encrypt(original)
        assert encrypted != original
        assert service._decrypt(encrypted) == original

    def test_different_services_same_key_can_decrypt(self) -> None:
        """Two services with the same encryption key share ciphertext."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        svc1 = SettingsService(encryption_key=key)
        svc2 = SettingsService(encryption_key=key)
        encrypted = svc1._encrypt("secret")
        assert svc2._decrypt(encrypted) == "secret"


# ══════════════════════════════════════════════════════════
# 12. Intent Activation — set_intent_active
# ══════════════════════════════════════════════════════════


class TestSetIntentActive:
    """Tests for set_intent_active()."""

    def test_set_intent_active_true_stores_state(
        self, service: SettingsService
    ) -> None:
        """Activating a known intent persists 'true'."""
        service.set_intent_active("kpi.oee", True)
        assert service.is_intent_active("kpi.oee") is True

    def test_set_intent_active_false_stores_state(
        self, service: SettingsService
    ) -> None:
        """Deactivating a known intent persists 'false'."""
        service.set_intent_active("kpi.oee", False)
        assert service.is_intent_active("kpi.oee") is False

    def test_set_intent_active_invalid_name_raises(
        self, service: SettingsService
    ) -> None:
        """Unknown intent name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.set_intent_active("bogus.intent", True)
        assert exc_info.value.field == "intent_name"
        assert "bogus.intent" in exc_info.value.message

    def test_set_intent_active_overwrite(
        self, service: SettingsService
    ) -> None:
        """Setting active twice overwrites the first value."""
        service.set_intent_active("kpi.oee", False)
        service.set_intent_active("kpi.oee", True)
        assert service.is_intent_active("kpi.oee") is True

    @pytest.mark.parametrize(
        "intent_name",
        [
            "kpi.energy.per_unit",
            "kpi.oee",
            "kpi.scrap_rate",
            "compare.energy",
            "trend.scrap",
            "trend.energy",
            "anomaly.production.check",
            "whatif.temperature",
        ],
    )
    def test_set_intent_active_accepts_all_known_intents(
        self, service: SettingsService, intent_name: str
    ) -> None:
        """Every known intent is accepted without error."""
        service.set_intent_active(intent_name, True)
        assert service.is_intent_active(intent_name) is True


# ══════════════════════════════════════════════════════════
# 13. Intent Activation — is_intent_active
# ══════════════════════════════════════════════════════════


class TestIsIntentActive:
    """Tests for is_intent_active()."""

    def test_is_intent_active_default_true(
        self, service: SettingsService
    ) -> None:
        """Unconfigured intent defaults to True (DEC-005)."""
        assert service.is_intent_active("kpi.oee") is True

    def test_is_intent_active_after_deactivation(
        self, service: SettingsService
    ) -> None:
        """Returns False after explicit deactivation."""
        service.set_intent_active("kpi.oee", False)
        assert service.is_intent_active("kpi.oee") is False

    def test_is_intent_active_after_reactivation(
        self, service: SettingsService
    ) -> None:
        """Returns True after deactivation then reactivation."""
        service.set_intent_active("kpi.oee", False)
        service.set_intent_active("kpi.oee", True)
        assert service.is_intent_active("kpi.oee") is True


# ══════════════════════════════════════════════════════════
# 14. Intent Activation — list_intent_states
# ══════════════════════════════════════════════════════════


class TestListIntentStates:
    """Tests for list_intent_states()."""

    def test_list_intent_states_returns_all_eight(
        self, service: SettingsService
    ) -> None:
        """Returns all 8 known intents."""
        states = service.list_intent_states()
        assert len(states) == 8

    def test_list_intent_states_default_all_true(
        self, service: SettingsService
    ) -> None:
        """All intents default to True on fresh database."""
        states = service.list_intent_states()
        assert all(active for active in states.values())

    def test_list_intent_states_reflects_changes(
        self, service: SettingsService
    ) -> None:
        """Toggling one intent is reflected in list."""
        service.set_intent_active("kpi.oee", False)
        states = service.list_intent_states()
        assert states["kpi.oee"] is False
        assert states["kpi.energy.per_unit"] is True

    def test_list_intent_states_keys_match_known_intents(
        self, service: SettingsService
    ) -> None:
        """Keys in the returned dict match KNOWN_INTENTS."""
        from skill.services.settings import KNOWN_INTENTS

        states = service.list_intent_states()
        assert set(states.keys()) == set(KNOWN_INTENTS)


# ══════════════════════════════════════════════════════════
# 15. Intent Activation — get_intent_metric_requirements
# ══════════════════════════════════════════════════════════


class TestGetIntentMetricRequirements:
    """Tests for get_intent_metric_requirements()."""

    def test_returns_dict_of_string_lists(self) -> None:
        """Return type is dict[str, list[str]]."""
        result = SettingsService.get_intent_metric_requirements()
        assert isinstance(result, dict)
        for key, val in result.items():
            assert isinstance(key, str)
            assert isinstance(val, list)
            for item in val:
                assert isinstance(item, str)

    def test_all_known_intents_present(self) -> None:
        """Every known intent appears in the requirements map."""
        from skill.services.settings import KNOWN_INTENTS

        result = SettingsService.get_intent_metric_requirements()
        for intent in KNOWN_INTENTS:
            assert intent in result

    def test_metric_values_are_canonical(self) -> None:
        """All metric names are valid CanonicalMetric values."""
        valid = {m.value for m in CanonicalMetric}
        result = SettingsService.get_intent_metric_requirements()
        for metrics in result.values():
            for m in metrics:
                assert m in valid, f"{m} is not a CanonicalMetric"

    def test_kpi_energy_requires_energy_per_unit(self) -> None:
        """Spot-check: kpi.energy.per_unit → [energy_per_unit]."""
        result = SettingsService.get_intent_metric_requirements()
        assert result["kpi.energy.per_unit"] == ["energy_per_unit"]

    def test_anomaly_requires_oee(self) -> None:
        """Spot-check: anomaly.production.check → [oee]."""
        result = SettingsService.get_intent_metric_requirements()
        assert result["anomaly.production.check"] == ["oee"]


# ══════════════════════════════════════════════════════════
# 16. Intent Activation — Isolation from Other Settings
# ══════════════════════════════════════════════════════════


class TestIntentActivationIsolation:
    """Intent state must not interfere with other settings."""

    def test_intent_state_not_in_metric_mappings(
        self, service: SettingsService
    ) -> None:
        """Intent keys do not appear in list_metric_mappings."""
        service.set_intent_active("kpi.oee", False)
        assert service.list_metric_mappings() == {}

    def test_intent_state_does_not_corrupt_platform_config(
        self, service: SettingsService
    ) -> None:
        """Toggling intents does not affect platform config."""
        service.update_platform_config(
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://api.reneryo.com",
            )
        )
        service.set_intent_active("kpi.oee", False)
        config = service.get_platform_config()
        assert config.platform_type == "reneryo"

    def test_metric_mapping_does_not_affect_intent_state(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Storing a metric mapping does not change intent states."""
        service.set_intent_active("kpi.oee", False)
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        assert service.is_intent_active("kpi.oee") is False


# ══════════════════════════════════════════════════════════
# 17. Emission Factor CRUD (DEC-023)
# ══════════════════════════════════════════════════════════


class TestEmissionFactorCRUD:
    """Tests for emission factor CRUD operations."""

    def test_set_and_get_factor(self, service: SettingsService) -> None:
        """Round-trip: set then get returns same factor."""
        service.set_emission_factor(
            energy_source="electricity", factor=0.48,
            country="TR", source="IEA", year=2024,
        )
        result = service.get_emission_factor("electricity")
        assert result is not None
        assert result["factor"] == 0.48
        assert result["country"] == "TR"

    def test_get_nonexistent_factor(self, service: SettingsService) -> None:
        """get_emission_factor for unknown source returns None."""
        assert service.get_emission_factor("electricity") is None

    def test_list_empty(self, service: SettingsService) -> None:
        """list_emission_factors on fresh DB returns empty dict."""
        assert service.list_emission_factors() == {}

    def test_list_after_set(self, service: SettingsService) -> None:
        """list_emission_factors returns all stored factors."""
        service.set_emission_factor("electricity", 0.48)
        service.set_emission_factor("gas", 0.20)
        result = service.list_emission_factors()
        assert len(result) == 2
        assert "electricity" in result
        assert "gas" in result

    def test_delete_factor(self, service: SettingsService) -> None:
        """delete_emission_factor removes the entry."""
        service.set_emission_factor("electricity", 0.48)
        assert service.delete_emission_factor("electricity") is True
        assert service.get_emission_factor("electricity") is None

    def test_delete_nonexistent(self, service: SettingsService) -> None:
        """delete_emission_factor for missing key returns False."""
        assert service.delete_emission_factor("electricity") is False

    def test_invalid_energy_source(self, service: SettingsService) -> None:
        """set_emission_factor with bad source raises ValidationError."""
        with pytest.raises(ValidationError):
            service.set_emission_factor("nuclear", 0.01)

    def test_negative_factor(self, service: SettingsService) -> None:
        """set_emission_factor with factor < 0 raises ValidationError."""
        with pytest.raises(ValidationError):
            service.set_emission_factor("electricity", -0.5)

    def test_zero_factor(self, service: SettingsService) -> None:
        """set_emission_factor with factor=0 raises ValidationError."""
        with pytest.raises(ValidationError):
            service.set_emission_factor("electricity", 0.0)

    def test_get_effective_factor_stored(
        self, service: SettingsService,
    ) -> None:
        """get_effective_emission_factor returns stored value if present."""
        service.set_emission_factor("electricity", 0.55)
        assert service.get_effective_emission_factor("electricity") == 0.55

    def test_get_effective_factor_fallback(
        self, service: SettingsService,
    ) -> None:
        """get_effective_emission_factor falls back to TR default."""
        result = service.get_effective_emission_factor("electricity")
        assert result == 0.48  # TR default

    def test_get_effective_factor_unknown_source(
        self, service: SettingsService,
    ) -> None:
        """get_effective_emission_factor returns 0.0 for unknown source."""
        assert service.get_effective_emission_factor("solar") == 0.0

    def test_update_existing_factor(
        self, service: SettingsService,
    ) -> None:
        """Calling set_emission_factor twice overwrites previous value."""
        service.set_emission_factor("electricity", 0.48)
        service.set_emission_factor("electricity", 0.40)
        result = service.get_emission_factor("electricity")
        assert result["factor"] == 0.40


# ══════════════════════════════════════════════════════════
# 18. Emission Factor Isolation
# ══════════════════════════════════════════════════════════


class TestEmissionFactorIsolation:
    """Emission factors must not interfere with other settings."""

    def test_emission_factor_not_in_metric_mappings(
        self, service: SettingsService,
    ) -> None:
        """Emission factor keys do not appear in list_metric_mappings."""
        service.set_emission_factor("electricity", 0.48)
        assert service.list_metric_mappings() == {}

    def test_metric_mapping_not_in_emission_factors(
        self,
        service: SettingsService,
        sample_mapping: dict[str, Any],
    ) -> None:
        """Metric mapping keys do not appear in list_emission_factors."""
        service.set_metric_mapping("energy_per_unit", sample_mapping)
        assert service.list_emission_factors() == {}
