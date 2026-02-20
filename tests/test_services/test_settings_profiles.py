"""
SettingsService Profile CRUD Tests (DEC-028)

Tests for the named-profile system: list, get, create, update, delete,
active profile switching, legacy migration, and backward compatibility.

All tests use in-memory SQLite — no file I/O.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from skill.domain.exceptions import ValidationError
from skill.services.database import Base, SettingModel
from skill.services.settings import PlatformConfig, SettingsService


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
        api_key="secret-key-123",
        extra_settings={"auth_type": "cookie"},
    )


@pytest.fixture
def sap_config() -> PlatformConfig:
    """A sample SAP platform config."""
    return PlatformConfig(
        platform_type="sap",
        api_url="https://sap.example.com/api",
        api_key="sap-token-456",
    )


# ══════════════════════════════════════════════════════════
# list_profiles()
# ══════════════════════════════════════════════════════════


class TestListProfiles:
    """Tests for list_profiles()."""

    def test_list_profiles_empty_returns_only_mock(
        self, service: SettingsService,
    ) -> None:
        """With no custom profiles, only mock is returned."""
        profiles = service.list_profiles()

        assert len(profiles) == 1
        assert profiles[0]["name"] == "mock"
        assert profiles[0]["platform_type"] == "mock"
        assert profiles[0]["is_builtin"] is True
        assert profiles[0]["is_active"] is True

    def test_list_profiles_with_custom_profiles(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
        sap_config: PlatformConfig,
    ) -> None:
        """Custom profiles are listed after mock."""
        service.create_profile("reneryo", reneryo_config)
        service.create_profile("sap-prod", sap_config)

        profiles = service.list_profiles()

        assert len(profiles) == 3
        names = [p["name"] for p in profiles]
        assert names == ["mock", "reneryo", "sap-prod"]

    def test_list_profiles_mock_always_first(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Mock profile must always be the first item."""
        service.create_profile("alpha", reneryo_config)
        service.create_profile("zulu", reneryo_config)

        profiles = service.list_profiles()

        assert profiles[0]["name"] == "mock"
        assert profiles[0]["is_builtin"] is True

    def test_list_profiles_shows_active_flag(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """is_active reflects the currently active profile."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")

        profiles = service.list_profiles()

        mock_profile = profiles[0]
        reneryo_profile = profiles[1]
        assert mock_profile["is_active"] is False
        assert reneryo_profile["is_active"] is True


# ══════════════════════════════════════════════════════════
# get_profile()
# ══════════════════════════════════════════════════════════


class TestGetProfile:
    """Tests for get_profile()."""

    def test_get_profile_mock_returns_default_config(
        self, service: SettingsService,
    ) -> None:
        """Mock profile returns PlatformConfig(platform_type='mock')."""
        config = service.get_profile("mock")

        assert config is not None
        assert config.platform_type == "mock"
        assert config.api_url == ""
        assert config.api_key == ""

    def test_get_profile_custom_returns_stored_config(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Custom profile returns the config that was stored."""
        service.create_profile("reneryo", reneryo_config)

        config = service.get_profile("reneryo")

        assert config is not None
        assert config.platform_type == "reneryo"
        assert config.api_url == "https://api.reneryo.example.com"
        assert config.api_key == "secret-key-123"

    def test_get_profile_nonexistent_returns_none(
        self, service: SettingsService,
    ) -> None:
        """Non-existent profile returns None."""
        result = service.get_profile("nonexistent")

        assert result is None

    def test_get_profile_decrypts_api_key(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """API key is decrypted on read."""
        service.create_profile("reneryo", reneryo_config)

        config = service.get_profile("reneryo")

        assert config is not None
        assert config.api_key == "secret-key-123"


# ══════════════════════════════════════════════════════════
# create_profile()
# ══════════════════════════════════════════════════════════


class TestCreateProfile:
    """Tests for create_profile()."""

    def test_create_profile_success(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Creating a valid profile stores it."""
        service.create_profile("reneryo", reneryo_config)

        config = service.get_profile("reneryo")
        assert config is not None
        assert config.platform_type == "reneryo"

    def test_create_profile_duplicate_raises_validation_error(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Duplicate profile name raises ValidationError."""
        service.create_profile("reneryo", reneryo_config)

        with pytest.raises(ValidationError, match="already exists"):
            service.create_profile("reneryo", reneryo_config)

    def test_create_profile_mock_name_raises_validation_error(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Cannot create a profile named 'mock'."""
        with pytest.raises(ValidationError, match="built-in profile"):
            service.create_profile("mock", reneryo_config)

    @pytest.mark.parametrize(
        "name,reason",
        [
            ("A", "too short / uppercase"),
            ("a", "single char (< 2)"),
            ("UPPER", "uppercase letters"),
            ("has spaces", "contains spaces"),
            ("has_underscore", "contains underscore"),
            ("-leading", "leading hyphen"),
            ("trailing-", "trailing hyphen"),
            ("a" * 51, "too long (> 50 chars)"),
            ("special!chars", "special characters"),
            ("with.dot", "contains dot"),
        ],
    )
    def test_create_profile_invalid_name_raises_validation_error(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
        name: str,
        reason: str,
    ) -> None:
        """Invalid profile names are rejected."""
        with pytest.raises(ValidationError, match="Invalid profile name"):
            service.create_profile(name, reneryo_config)

    @pytest.mark.parametrize(
        "name",
        [
            "ab",              # min length
            "reneryo",
            "sap-prod",
            "my-staging-env",
            "a" * 50,          # max length
            "a1",              # alphanumeric mix
            "test-123-env",
        ],
    )
    def test_create_profile_valid_names_succeed(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
        name: str,
    ) -> None:
        """Valid profile names are accepted."""
        service.create_profile(name, reneryo_config)

        assert service.get_profile(name) is not None


# ══════════════════════════════════════════════════════════
# update_profile()
# ══════════════════════════════════════════════════════════


class TestUpdateProfile:
    """Tests for update_profile()."""

    def test_update_profile_success(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Updating an existing profile persists new values."""
        service.create_profile("reneryo", reneryo_config)

        updated = PlatformConfig(
            platform_type="reneryo",
            api_url="https://new-api.example.com",
            api_key="new-key",
        )
        service.update_profile("reneryo", updated)

        config = service.get_profile("reneryo")
        assert config is not None
        assert config.api_url == "https://new-api.example.com"
        assert config.api_key == "new-key"

    def test_update_profile_mock_raises_validation_error(
        self, service: SettingsService,
    ) -> None:
        """Cannot modify the built-in mock profile."""
        with pytest.raises(ValidationError, match="built-in mock"):
            service.update_profile(
                "mock",
                PlatformConfig(platform_type="mock"),
            )

    def test_update_profile_nonexistent_raises_validation_error(
        self, service: SettingsService,
    ) -> None:
        """Updating a non-existent profile raises ValidationError."""
        with pytest.raises(ValidationError, match="not found"):
            service.update_profile(
                "nonexistent",
                PlatformConfig(platform_type="reneryo"),
            )


# ══════════════════════════════════════════════════════════
# delete_profile()
# ══════════════════════════════════════════════════════════


class TestDeleteProfile:
    """Tests for delete_profile()."""

    def test_delete_profile_success(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Deleting an existing profile removes it."""
        service.create_profile("reneryo", reneryo_config)

        result = service.delete_profile("reneryo")

        assert result is True
        assert service.get_profile("reneryo") is None

    def test_delete_profile_mock_raises_validation_error(
        self, service: SettingsService,
    ) -> None:
        """Cannot delete the built-in mock profile."""
        with pytest.raises(ValidationError, match="built-in mock"):
            service.delete_profile("mock")

    def test_delete_profile_active_resets_to_mock(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Deleting the active profile resets active to mock."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        assert service.get_active_profile_name() == "reneryo"

        service.delete_profile("reneryo")

        assert service.get_active_profile_name() == "mock"

    def test_delete_profile_nonexistent_returns_false(
        self, service: SettingsService,
    ) -> None:
        """Deleting a non-existent profile returns False."""
        result = service.delete_profile("nonexistent")

        assert result is False


# ══════════════════════════════════════════════════════════
# get_active_profile_name() / set_active_profile()
# ══════════════════════════════════════════════════════════


class TestActiveProfile:
    """Tests for get/set active profile."""

    def test_get_active_profile_name_default_is_mock(
        self, service: SettingsService,
    ) -> None:
        """Default active profile is 'mock' when nothing is set."""
        assert service.get_active_profile_name() == "mock"

    def test_get_active_profile_name_returns_stored(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """After setting an active profile, it is returned."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")

        assert service.get_active_profile_name() == "reneryo"

    def test_set_active_profile_mock_clears_key(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Setting active to 'mock' clears the stored key."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")
        assert service.get_active_profile_name() == "reneryo"

        service.set_active_profile("mock")

        assert service.get_active_profile_name() == "mock"
        # Verify key is truly gone (not stored as "mock")
        raw = service.get_setting(
            service.ACTIVE_PROFILE_KEY, default=None,
        )
        assert raw is None

    def test_set_active_profile_custom_stores_key(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """Setting a custom profile stores the name."""
        service.create_profile("reneryo", reneryo_config)

        service.set_active_profile("reneryo")

        raw = service.get_setting(service.ACTIVE_PROFILE_KEY)
        assert raw == "reneryo"

    def test_set_active_profile_nonexistent_raises_validation_error(
        self, service: SettingsService,
    ) -> None:
        """Cannot activate a profile that doesn't exist."""
        with pytest.raises(ValidationError, match="not found"):
            service.set_active_profile("nonexistent")


# ══════════════════════════════════════════════════════════
# _migrate_legacy_config()
# ══════════════════════════════════════════════════════════


class TestMigrateLegacyConfig:
    """Tests for legacy migration."""

    def test_migrate_legacy_config_reneryo(self) -> None:
        """Legacy 'platform_config' is migrated to a named profile."""
        svc = SettingsService()
        # Manually initialize without triggering migration
        svc._engine = create_engine(
            "sqlite:///:memory:", echo=False, future=True,
        )
        svc._session_factory = sessionmaker(
            bind=svc._engine, expire_on_commit=False,
        )
        Base.metadata.create_all(svc._engine)
        svc._initialized = True

        # Seed legacy key
        config = PlatformConfig(
            platform_type="reneryo",
            api_url="https://old.api.com",
            api_key="old-key",
        )
        config_data = config.to_dict()
        config_data["api_key"] = svc._encrypt(config_data["api_key"])
        svc.set_setting("platform_config", config_data)
        # Manually set encrypted flag
        with svc._get_session() as session:
            setting = session.query(SettingModel).filter_by(
                key="platform_config",
            ).first()
            setting.encrypted = True
            setting.value = json.dumps(config_data)
            session.commit()

        # Run migration
        svc._migrate_legacy_config()

        # Legacy key should be gone
        assert svc.get_setting("platform_config", default=None) is None
        # Profile should exist
        migrated = svc.get_profile("reneryo")
        assert migrated is not None
        assert migrated.api_url == "https://old.api.com"
        assert migrated.api_key == "old-key"
        # Active profile should be reneryo
        assert svc.get_active_profile_name() == "reneryo"

    def test_migrate_legacy_config_mock_just_deletes(self) -> None:
        """Legacy mock config is deleted without creating a profile."""
        svc = SettingsService()
        svc._engine = create_engine(
            "sqlite:///:memory:", echo=False, future=True,
        )
        svc._session_factory = sessionmaker(
            bind=svc._engine, expire_on_commit=False,
        )
        Base.metadata.create_all(svc._engine)
        svc._initialized = True

        # Seed legacy mock config
        config = PlatformConfig(platform_type="mock")
        svc.set_setting("platform_config", config.to_dict())

        svc._migrate_legacy_config()

        assert svc.get_setting("platform_config", default=None) is None
        assert svc.get_active_profile_name() == "mock"

    def test_migrate_legacy_config_no_legacy_is_noop(
        self, service: SettingsService,
    ) -> None:
        """No legacy key → no-op, no errors."""
        # initialize() already ran migration; calling again is safe
        service._migrate_legacy_config()

        assert service.get_active_profile_name() == "mock"

    def test_migrate_legacy_config_idempotent(self) -> None:
        """Running migration multiple times does not duplicate profiles."""
        svc = SettingsService()
        svc._engine = create_engine(
            "sqlite:///:memory:", echo=False, future=True,
        )
        svc._session_factory = sessionmaker(
            bind=svc._engine, expire_on_commit=False,
        )
        Base.metadata.create_all(svc._engine)
        svc._initialized = True

        config = PlatformConfig(
            platform_type="reneryo",
            api_url="https://old.api.com",
            api_key="key",
        )
        svc.set_setting("platform_config", config.to_dict())

        svc._migrate_legacy_config()
        # First run migrates — second run is no-op
        svc._migrate_legacy_config()

        profiles = svc.list_profiles()
        reneryo_profiles = [
            p for p in profiles if p["name"] == "reneryo"
        ]
        assert len(reneryo_profiles) == 1

    def test_migration_runs_on_initialize(self, tmp_path) -> None:
        """initialize() triggers migration automatically."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"
        svc = SettingsService(database_url=db_url)
        svc.initialize()

        # Seed a legacy key using the old flat key
        config = PlatformConfig(
            platform_type="reneryo",
            api_url="https://init-test.com",
            api_key="init-key",
        )
        svc.set_setting("platform_config", config.to_dict())

        # Reset and re-initialize — should trigger migration
        svc._initialized = False
        svc.initialize()

        assert svc.get_setting("platform_config", default=None) is None
        assert svc.get_active_profile_name() == "reneryo"


# ══════════════════════════════════════════════════════════
# Backward Compatibility
# ══════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """Tests for get_platform_config / update_platform_config delegates."""

    def test_get_platform_config_delegates_to_active_profile(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """get_platform_config reads the active profile."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")

        config = service.get_platform_config()

        assert config.platform_type == "reneryo"
        assert config.api_url == "https://api.reneryo.example.com"

    def test_get_platform_config_defaults_to_mock(
        self, service: SettingsService,
    ) -> None:
        """When no profile is active, returns mock config."""
        config = service.get_platform_config()

        assert config.platform_type == "mock"

    def test_update_platform_config_delegates_to_active_profile(
        self,
        service: SettingsService,
        reneryo_config: PlatformConfig,
    ) -> None:
        """update_platform_config writes to the active profile."""
        service.create_profile("reneryo", reneryo_config)
        service.set_active_profile("reneryo")

        updated = PlatformConfig(
            platform_type="reneryo",
            api_url="https://updated.example.com",
            api_key="updated-key",
        )
        service.update_platform_config(updated)

        config = service.get_profile("reneryo")
        assert config is not None
        assert config.api_url == "https://updated.example.com"

    def test_update_platform_config_auto_creates_profile(
        self, service: SettingsService,
    ) -> None:
        """update_platform_config auto-creates when active is mock."""
        new_config = PlatformConfig(
            platform_type="reneryo",
            api_url="https://auto.example.com",
            api_key="auto-key",
        )

        service.update_platform_config(new_config)

        assert service.get_active_profile_name() == "reneryo"
        config = service.get_profile("reneryo")
        assert config is not None
        assert config.api_url == "https://auto.example.com"

    def test_update_platform_config_mock_is_noop(
        self, service: SettingsService,
    ) -> None:
        """Updating with mock config when active is mock is a no-op."""
        service.update_platform_config(
            PlatformConfig(platform_type="mock"),
        )

        assert service.get_active_profile_name() == "mock"
        # Only built-in mock (and optionally bootstrap demo profile) should exist
        profiles = service.list_profiles()
        assert profiles[0]["name"] == "mock"
        assert profiles[0]["is_builtin"] is True

    def test_backward_compatibility_create_via_old_api_then_read_via_new(
        self, service: SettingsService,
    ) -> None:
        """Old API creates config, new API reads it as a profile."""
        service.update_platform_config(
            PlatformConfig(
                platform_type="reneryo",
                api_url="https://compat.example.com",
                api_key="compat-key",
            ),
        )

        # Read via new API
        config = service.get_profile("reneryo")
        assert config is not None
        assert config.api_url == "https://compat.example.com"

        # Read via old API
        old_config = service.get_platform_config()
        assert old_config.platform_type == "reneryo"


class TestDemoProfileBootstrap:
    """Optional demo profile bootstrap behavior via environment flags."""

    def test_bootstrap_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without env flag, service should not auto-create demo profile."""
        monkeypatch.delenv("AVAROS_BOOTSTRAP_DEMO_PROFILE", raising=False)
        service = SettingsService(database_url="sqlite:///:memory:")
        service.initialize()

        names = [item["name"] for item in service.list_profiles()]
        assert names == ["mock"]

    def test_bootstrap_creates_demo_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With env flag, service should create a reneryo-mock profile."""
        monkeypatch.setenv("AVAROS_BOOTSTRAP_DEMO_PROFILE", "true")
        monkeypatch.setenv("AVAROS_DEMO_PROFILE_NAME", "reneryo-mock")
        monkeypatch.setenv("AVAROS_DEMO_RENERYO_URL", "http://reneryo-mock:8090")
        monkeypatch.setenv("AVAROS_DEMO_RENERYO_API_KEY", "demo-token")

        service = SettingsService(database_url="sqlite:///:memory:")
        service.initialize()

        profile = service.get_profile("reneryo-mock")
        assert profile is not None
        assert profile.platform_type == "reneryo"
        assert profile.api_url == "http://reneryo-mock:8090"
        assert profile.api_key == "demo-token"
