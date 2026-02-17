"""
SettingsService - Database-Backed Configuration

Manages AVAROS configuration stored in PostgreSQL (production) or
SQLite (testing/development).  Supports hot-reload without container
restart.

Zero-Config Philosophy:
    - On first run, no configuration required (MockAdapter used)
    - Users configure via Web UI, not YAML files
    - Settings persisted to database for reliability

URL resolution order:
    1. Explicit ``database_url`` parameter
    2. ``AVAROS_DATABASE_URL`` environment variable
    3. ``sqlite:///:memory:`` (in-memory fallback for tests)

Usage:
    # Production (reads AVAROS_DATABASE_URL env var)
    settings = SettingsService()

    # Explicit URL
    settings = SettingsService(
        database_url="postgresql://avaros:avaros@localhost:5432/avaros"
    )
    
    # Check if configured
    if not settings.is_configured():
        # Redirect to setup wizard
        ...
    
    # Get platform config
    config = settings.get_platform_config()
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from skill.domain.emission_factors import DEFAULT_EMISSION_FACTORS, EmissionFactor
from skill.domain.exceptions import ValidationError
from skill.domain.models import CanonicalMetric
from skill.services.database import Base, SettingModel
from skill.services.models import PlatformConfig, VoiceConfig  # re-export
from skill.services.profiles import ProfileMixin


logger = logging.getLogger(__name__)


# ── Intent-Metric Dependency Map (DEC-021) ──────────────

#: The 8 intents and the canonical metrics each requires.
#: Used by ``SettingsService.get_intent_metric_requirements()`` and
#: the Web UI to show which metrics must be mapped for each intent.
KNOWN_INTENTS: tuple[str, ...] = (
    "kpi.energy.per_unit",
    "kpi.oee",
    "kpi.scrap_rate",
    "compare.energy",
    "trend.scrap",
    "trend.energy",
    "anomaly.production.check",
    "whatif.temperature",
)

INTENT_METRIC_REQUIREMENTS: dict[str, list[CanonicalMetric]] = {
    "kpi.energy.per_unit": [CanonicalMetric.ENERGY_PER_UNIT],
    "kpi.oee": [CanonicalMetric.OEE],
    "kpi.scrap_rate": [CanonicalMetric.SCRAP_RATE],
    "compare.energy": [CanonicalMetric.ENERGY_PER_UNIT],
    "trend.scrap": [CanonicalMetric.SCRAP_RATE],
    "trend.energy": [CanonicalMetric.ENERGY_PER_UNIT],
    "anomaly.production.check": [CanonicalMetric.OEE],
    "whatif.temperature": [CanonicalMetric.ENERGY_PER_UNIT],
}


# SettingModel re-exported from database for backward compatibility
# PlatformConfig, VoiceConfig re-exported from models
# ProfileMixin provides profile CRUD (DEC-028)


class SettingsService(ProfileMixin):
    """
    Database-backed settings management.
    
    Stores all configuration in PostgreSQL (production) or SQLite
    (testing) for persistence across restarts.  Provides hot-reload
    capability for configuration changes.  Encrypts sensitive data
    (API keys) at rest.
    
    Attributes:
        _database_url: SQLAlchemy connection URL
        _engine: SQLAlchemy engine
        _session_factory: Session factory
        _encryption_key: Fernet encryption key for sensitive data
    
    Example:
        service = SettingsService()  # reads AVAROS_DATABASE_URL
        
        # First run - not configured
        assert not service.is_configured()
        
        # User configures via Web UI
        service.update_platform_config(PlatformConfig(
            platform_type="reneryo",
            api_url="https://api.reneryo.com",
            api_key="secret-key"  # Will be encrypted
        ))
        
        # Now configured
        assert service.is_configured()
    """
    
    def __init__(
        self,
        database_url: str | None = None,
        encryption_key: str | None = None,
    ) -> None:
        """
        Initialize settings service.
        
        Args:
            database_url: SQLAlchemy database URL.  Falls back to
                ``AVAROS_DATABASE_URL`` env var, then
                ``sqlite:///:memory:`` for tests.
            encryption_key: Base64-encoded Fernet key. If None,
                generates a new key.
        """
        self._database_url = self._resolve_database_url(database_url)
        self._engine = None
        self._session_factory = None
        self._initialized = False
        
        # Initialize encryption
        if encryption_key:
            self._encryption_key = encryption_key.encode()
        else:
            # Derive deterministic key from database URL
            seed = self._database_url.encode()
            key_material = hashlib.sha256(seed).digest()
            self._encryption_key = base64.urlsafe_b64encode(key_material)
        
        self._cipher = Fernet(self._encryption_key)
    
    @staticmethod
    def _resolve_database_url(explicit_url: str | None) -> str:
        """Determine the database URL from explicit value, env, or default.

        Args:
            explicit_url: URL passed directly to the constructor.

        Returns:
            Resolved SQLAlchemy database URL.
        """
        if explicit_url:
            return explicit_url
        return os.environ.get(
            "AVAROS_DATABASE_URL", "sqlite:///:memory:"
        )

    def initialize(self) -> None:
        """
        Initialize the settings database.
        
        Creates tables if they don't exist.
        Called automatically on first access.
        """
        if self._initialized:
            return
        
        self._engine = create_engine(
            self._database_url, echo=False, future=True,
        )
        self._session_factory = sessionmaker(
            bind=self._engine, expire_on_commit=False,
        )
        
        # Create tables
        Base.metadata.create_all(self._engine)
        
        self._initialized = True
        logger.info("SettingsService initialized (db=%s)", self._database_url)

        # Auto-migrate legacy platform_config → named profile (DEC-028)
        self._migrate_legacy_config()
        # Migrate global settings → profile-scoped keys (DEC-029)
        self._migrate_global_settings_to_profile()
    
    def is_configured(self) -> bool:
        """
        Check if AVAROS has been configured with a real platform.
        
        Returns:
            True if a platform other than mock is configured
        """
        self._ensure_initialized()
        config = self.get_platform_config()
        return config.is_configured
    
    # get_platform_config / update_platform_config → ProfileMixin

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a generic setting value.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default (decrypted if encrypted)
        """
        self._ensure_initialized()
        
        with self._get_session() as session:
            setting = session.query(SettingModel).filter_by(key=key).first()
            
            if not setting:
                return default
            
            # Try to parse as JSON
            try:
                value = json.loads(setting.value)
            except json.JSONDecodeError:
                value = setting.value
            
            # Decrypt if needed
            if setting.encrypted and isinstance(value, str):
                value = self._decrypt(value)
            
            return value
    
    def set_setting(self, key: str, value: Any, encrypt: bool = False) -> None:
        """
        Set a generic setting value.
        
        Args:
            key: Setting key
            value: Setting value (will be JSON-serialized)
            encrypt: Whether to encrypt the value
        """
        self._ensure_initialized()
        
        # Serialize value
        if isinstance(value, (dict, list)):
            serialized = json.dumps(value)
        else:
            serialized = str(value)
        
        # Encrypt if requested
        if encrypt:
            serialized = self._encrypt(serialized)
        
        # Store in database
        with self._get_session() as session:
            setting = session.query(SettingModel).filter_by(key=key).first()
            
            if setting:
                setting.value = serialized
                setting.encrypted = encrypt
                setting.updated_at = datetime.now(timezone.utc)
            else:
                setting = SettingModel(
                    key=key,
                    value=serialized,
                    encrypted=encrypt,
                )
                session.add(setting)
            
            session.commit()
    
    def delete_setting(self, key: str) -> bool:
        """
        Delete a setting.
        
        Args:
            key: Setting key
            
        Returns:
            True if setting was deleted, False if not found
        """
        self._ensure_initialized()
        
        with self._get_session() as session:
            setting = session.query(SettingModel).filter_by(key=key).first()
            
            if setting:
                session.delete(setting)
                session.commit()
                return True
            
            return False
    
    def list_settings(self) -> list[str]:
        """
        List all setting keys.
        
        Returns:
            List of setting keys
        """
        self._ensure_initialized()
        
        with self._get_session() as session:
            settings = session.query(SettingModel.key).all()
            return [s.key for s in settings]

    # ── Intent Activation CRUD (DEC-021) ──────────────────

    INTENT_ACTIVE_PREFIX = "intent_active:"

    def set_intent_active(self, intent_name: str, active: bool) -> None:
        """Store intent activation state (profile-scoped, DEC-029).

        Args:
            intent_name: Intent identifier (e.g. ``kpi.energy.per_unit``)
            active: Whether the intent is active

        Raises:
            ValidationError: If intent_name unknown or profile is mock
        """
        self._validate_intent_name(intent_name)
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            raise ValidationError(
                message="Cannot modify intent state for mock profile",
                field="profile",
                value="mock",
            )
        key = f"{self.INTENT_ACTIVE_PREFIX}{profile}:{intent_name}"
        self.set_setting(key, str(active).lower())

    def is_intent_active(self, intent_name: str) -> bool:
        """Read intent activation state (profile-scoped, DEC-029).

        Mock profile always returns ``True``. Custom profiles
        return stored state or ``True`` by default (DEC-005).

        Args:
            intent_name: Intent identifier

        Returns:
            True if the intent is active (or not yet configured)
        """
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            return True
        key = f"{self.INTENT_ACTIVE_PREFIX}{profile}:{intent_name}"
        value = self.get_setting(key, default=None)
        if value is None:
            return True
        return str(value).lower() == "true"

    def list_intent_states(self) -> dict[str, bool]:
        """
        Return all known intents with their current activation state.

        Intents with no stored state default to ``True``.

        Returns:
            Dict mapping intent name → active boolean
        """
        return {
            intent: self.is_intent_active(intent)
            for intent in KNOWN_INTENTS
        }

    @staticmethod
    def get_intent_metric_requirements() -> dict[str, list[str]]:
        """
        Return the static intent-to-metric dependency map.

        Each value is a list of canonical metric name strings.

        Returns:
            Dict mapping intent name → list of metric name strings
        """
        return {
            intent: [m.value for m in metrics]
            for intent, metrics in INTENT_METRIC_REQUIREMENTS.items()
        }

    # ── Emission Factor CRUD (DEC-023) ──────────────────

    EMISSION_FACTOR_PREFIX = "emission_factor:"

    def set_emission_factor(
        self,
        energy_source: str,
        factor: float,
        country: str = "",
        source: str = "",
        year: int = 2024,
    ) -> None:
        """Store an emission factor (profile-scoped, DEC-029).

        Args:
            energy_source: "electricity", "gas", or "water"
            factor: CO₂ emission factor value (must be > 0)
            country: Country code (e.g. "TR", "DE")
            source: Citation for the factor
            year: Reference year

        Raises:
            ValidationError: If invalid input or profile is mock
        """
        self._validate_energy_source(energy_source)
        self._validate_positive_factor(factor)
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            raise ValidationError(
                message="Cannot modify emission factors for mock profile",
                field="profile",
                value="mock",
            )
        key = f"{self.EMISSION_FACTOR_PREFIX}{profile}:{energy_source}"
        data = self._build_emission_data(
            energy_source, factor, country, source, year,
        )
        self.set_setting(key, data)

    @staticmethod
    def _validate_positive_factor(factor: float) -> None:
        """Raise if emission factor is not positive.

        Args:
            factor: Value to validate.

        Raises:
            ValidationError: If factor <= 0.
        """
        if factor <= 0:
            raise ValidationError(
                message=f"Emission factor must be positive, got {factor}",
                field="factor",
                value=str(factor),
            )

    @staticmethod
    def _build_emission_data(
        energy_source: str,
        factor: float,
        country: str,
        source: str,
        year: int,
    ) -> dict[str, Any]:
        """Build the emission factor storage dict.

        Args:
            energy_source: Energy source identifier.
            factor: CO₂ emission factor value.
            country: Country code.
            source: Citation string.
            year: Reference year.

        Returns:
            Dict ready for persistence.
        """
        return {
            "energy_source": energy_source,
            "factor": factor,
            "country": country,
            "source": source,
            "year": year,
        }

    def get_emission_factor(self, energy_source: str) -> EmissionFactor | None:
        """Get an emission factor (profile-scoped, DEC-029).

        Mock profile returns Türkiye defaults. Custom profiles
        read from profile-scoped storage.

        Args:
            energy_source: "electricity", "gas", or "water"

        Returns:
            EmissionFactor instance or None if not configured
        """
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            turkey = DEFAULT_EMISSION_FACTORS.get("TR", {})
            return turkey.get(energy_source)
        key = f"{self.EMISSION_FACTOR_PREFIX}{profile}:{energy_source}"
        data = self.get_setting(key, default=None)
        if data is None:
            return None
        return EmissionFactor(
            energy_source=data["energy_source"],
            factor=data["factor"],
            country=data.get("country", ""),
            source=data.get("source", ""),
            year=data.get("year", 2024),
        )

    def list_emission_factors(self) -> dict[str, EmissionFactor]:
        """List emission factors (profile-scoped, DEC-029).

        Mock returns Türkiye defaults. Custom profiles return
        only that profile's stored factors.

        Returns:
            Dict mapping energy_source to EmissionFactor
        """
        self._ensure_initialized()
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            return dict(DEFAULT_EMISSION_FACTORS.get("TR", {}))
        prefix = f"{self.EMISSION_FACTOR_PREFIX}{profile}:"
        result: dict[str, EmissionFactor] = {}
        for key in self.list_settings():
            if not key.startswith(prefix):
                continue
            source = key[len(prefix):]
            ef = self.get_emission_factor(source)
            if ef is not None:
                result[source] = ef
        return result

    def delete_emission_factor(self, energy_source: str) -> bool:
        """Delete a stored emission factor (profile-scoped, DEC-029).

        Returns ``False`` for mock profile (nothing to delete).

        Args:
            energy_source: "electricity", "gas", or "water"

        Returns:
            True if deleted, False if not found
        """
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            return False
        key = f"{self.EMISSION_FACTOR_PREFIX}{profile}:{energy_source}"
        return self.delete_setting(key)

    def get_effective_emission_factor(self, energy_source: str) -> float:
        """Get the effective emission factor, with fallback to defaults.

        Priority: stored custom factor → Türkiye default (pilot site) → 0.0

        Args:
            energy_source: "electricity", "gas", or "water"

        Returns:
            Emission factor in kg CO₂/kWh (or equivalent)
        """
        stored = self.get_emission_factor(energy_source)
        if stored is not None:
            return stored.factor

        # Fallback to Türkiye defaults (primary pilot site)
        turkey_defaults = DEFAULT_EMISSION_FACTORS.get("TR", {})
        if energy_source in turkey_defaults:
            return turkey_defaults[energy_source].factor

        return 0.0

    @staticmethod
    def _validate_energy_source(energy_source: str) -> None:
        """Validate energy source name.

        Args:
            energy_source: Must be one of "electricity", "gas", "water"

        Raises:
            ValidationError: If not a valid energy source
        """
        valid = {"electricity", "gas", "water"}
        if energy_source not in valid:
            raise ValidationError(
                message=(
                    f"Invalid energy source: '{energy_source}'. "
                    f"Must be one of: {', '.join(sorted(valid))}"
                ),
                field="energy_source",
                value=energy_source,
            )

    # ── Metric Mapping CRUD ─────────────────────────────

    METRIC_MAPPING_PREFIX = "metric_mapping:"
    VOICE_WS_URL_KEY = "voice:hivemind_ws_url"
    VOICE_CLIENT_NAME = "voice:hivemind_client_name"
    VOICE_CLIENT_KEY = "voice:hivemind_client_key"
    VOICE_CLIENT_SECRET = "voice:hivemind_client_secret"

    def set_metric_mapping(self, metric_name: str, mapping: dict[str, Any]) -> None:
        """Store a metric mapping (profile-scoped, DEC-029).

        Args:
            metric_name: Canonical metric name (e.g. ``energy_per_unit``)
            mapping: Mapping data (endpoint, json_path, unit, etc.)

        Raises:
            ValidationError: If metric_name invalid or profile is mock
        """
        self._validate_metric_name(metric_name)
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            raise ValidationError(
                message="Cannot modify metric mappings for mock profile",
                field="profile",
                value="mock",
            )
        key = f"{self.METRIC_MAPPING_PREFIX}{profile}:{metric_name}"
        self.set_setting(key, mapping)

    # ── Voice Config CRUD (DEC-006) ─────────────────────

    def get_voice_config(self) -> VoiceConfig:
        """Return HiveMind browser-client configuration.

        Configuration source priority:
        1. Values persisted in SettingsService storage
        2. Environment defaults (for backwards-compatible bootstrap)
        3. Hardcoded safe defaults

        Returns:
            VoiceConfig containing HiveMind URL, key and secret.
        """
        self._ensure_initialized()

        env_url = os.environ.get("HIVEMIND_WS_URL", "ws://localhost:5678")
        env_name = os.environ.get("HIVEMIND_CLIENT_NAME", "avaros-web-client")
        env_key = os.environ.get("HIVEMIND_CLIENT_KEY", "")
        env_secret = os.environ.get("HIVEMIND_CLIENT_SECRET", "")

        hivemind_url = self.get_setting(
            self.VOICE_WS_URL_KEY,
            default=env_url,
        )
        hivemind_name = self.get_setting(
            self.VOICE_CLIENT_NAME,
            default=env_name,
        )
        hivemind_key = self.get_setting(
            self.VOICE_CLIENT_KEY,
            default=env_key,
        )
        hivemind_secret = self.get_setting(
            self.VOICE_CLIENT_SECRET,
            default=env_secret,
        )

        # If persisted values are empty strings, fall back to environment
        # bootstrap defaults to keep voice bridge operable.
        hivemind_url = str(hivemind_url or env_url)
        hivemind_name = str(hivemind_name or env_name)
        hivemind_key = str(hivemind_key or env_key)
        hivemind_secret = str(hivemind_secret or env_secret)

        return VoiceConfig(
            hivemind_url=hivemind_url,
            hivemind_name=hivemind_name,
            hivemind_key=hivemind_key,
            hivemind_secret=hivemind_secret,
        )

    def update_voice_config(self, config: VoiceConfig) -> None:
        """Persist HiveMind browser-client configuration.

        Args:
            config: New voice configuration values.
        """
        self._ensure_initialized()
        self.set_setting(self.VOICE_WS_URL_KEY, config.hivemind_url)
        self.set_setting(self.VOICE_CLIENT_NAME, config.hivemind_name)
        self.set_setting(self.VOICE_CLIENT_KEY, config.hivemind_key)
        # Keep existing secret if UI submits an empty value.
        if config.hivemind_secret:
            self.set_setting(
                self.VOICE_CLIENT_SECRET,
                config.hivemind_secret,
                encrypt=True,
            )

    def get_metric_mapping(self, metric_name: str) -> dict[str, Any] | None:
        """Get a metric mapping (profile-scoped, DEC-029).

        Mock profile returns ``None`` (MockAdapter generates data).

        Args:
            metric_name: Canonical metric name

        Returns:
            Mapping data dictionary, or None if not found
        """
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            return None
        key = f"{self.METRIC_MAPPING_PREFIX}{profile}:{metric_name}"
        return self.get_setting(key, default=None)

    def list_metric_mappings(self) -> dict[str, dict[str, Any]]:
        """List metric mappings (profile-scoped, DEC-029).

        Mock returns ``{}``. Custom profiles return only that
        profile's stored mappings.

        Returns:
            Dictionary mapping canonical metric names to their mapping data
        """
        self._ensure_initialized()
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            return {}
        prefix = f"{self.METRIC_MAPPING_PREFIX}{profile}:"
        result: dict[str, dict[str, Any]] = {}
        for key in self.list_settings():
            if not key.startswith(prefix):
                continue
            name = key[len(prefix):]
            result[name] = self.get_setting(key)
        return result

    def delete_metric_mapping(self, metric_name: str) -> bool:
        """Delete a metric mapping (profile-scoped, DEC-029).

        Returns ``False`` for mock profile (nothing to delete).

        Args:
            metric_name: Canonical metric name

        Returns:
            True if mapping was deleted, False if not found
        """
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            return False
        key = f"{self.METRIC_MAPPING_PREFIX}{profile}:{metric_name}"
        return self.delete_setting(key)

    # ── Private Helpers ─────────────────────────────────

    @staticmethod
    def _validate_metric_name(metric_name: str) -> None:
        """
        Validate that a metric name matches a CanonicalMetric.

        Args:
            metric_name: Name to validate

        Raises:
            ValidationError: If not a valid canonical metric name
        """
        valid_names = {m.value for m in CanonicalMetric}
        if metric_name not in valid_names:
            raise ValidationError(
                message=f"Invalid metric name: '{metric_name}'",
                field="metric_name",
                value=metric_name,
            )

    @staticmethod
    def _validate_intent_name(intent_name: str) -> None:
        """
        Validate that an intent name is in KNOWN_INTENTS.

        Args:
            intent_name: Name to validate

        Raises:
            ValidationError: If not a recognised intent name
        """
        if intent_name not in KNOWN_INTENTS:
            raise ValidationError(
                message=f"Unknown intent: '{intent_name}'",
                field="intent_name",
                value=intent_name,
            )

    def _get_session(self) -> Session:
        """Get a new database session."""
        return self._session_factory()
    
    def _encrypt(self, plaintext: str) -> str:
        """Encrypt a string value."""
        encrypted_bytes = self._cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode('ascii')
    
    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a string value."""
        decrypted_bytes = self._cipher.decrypt(ciphertext.encode('ascii'))
        return decrypted_bytes.decode()
    
    def _ensure_initialized(self) -> None:
        """Ensure database is initialized before access."""
        if not self._initialized:
            self.initialize()
    
    def close(self) -> None:
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            self._initialized = False
            logger.info("SettingsService closed")
