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

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from cryptography.fernet import Fernet
import base64
import hashlib

from skill.domain.emission_factors import DEFAULT_EMISSION_FACTORS, EmissionFactor
from skill.domain.exceptions import ValidationError
from skill.domain.models import CanonicalMetric


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

Base = declarative_base()


class SettingModel(Base):
    """
    SQLAlchemy model for settings storage.
    
    Stores key-value settings with metadata.
    """
    
    __tablename__ = "settings"
    
    key = Column(String(255), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    encrypted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Setting(key={self.key}, encrypted={self.encrypted})>"


@dataclass
class PlatformConfig:
    """
    Platform connection configuration.
    
    Attributes:
        platform_type: Adapter type ("mock", "reneryo", etc.)
        api_url: Platform API endpoint
        api_key: Authentication key (encrypted at rest)
        extra_settings: Platform-specific settings
    """
    
    platform_type: str = "mock"
    api_url: str = ""
    api_key: str = ""
    extra_settings: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_configured(self) -> bool:
        """Check if a real platform is configured (not mock)."""
        return self.platform_type != "mock" and bool(self.api_url)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlatformConfig:
        """Create from dictionary."""
        return cls(
            platform_type=data.get("platform_type", "mock"),
            api_url=data.get("api_url", ""),
            api_key=data.get("api_key", ""),
            extra_settings=data.get("extra_settings", {}),
        )


class SettingsService:
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
    
    def is_configured(self) -> bool:
        """
        Check if AVAROS has been configured with a real platform.
        
        Returns:
            True if a platform other than mock is configured
        """
        self._ensure_initialized()
        config = self.get_platform_config()
        return config.is_configured
    
    def get_platform_config(self) -> PlatformConfig:
        """
        Get current platform configuration.
        
        Returns:
            PlatformConfig with current settings (API key decrypted)
        """
        self._ensure_initialized()
        
        with self._get_session() as session:
            setting = session.query(SettingModel).filter_by(key="platform_config").first()
            
            if not setting:
                # First run - return default mock config
                return PlatformConfig()
            
            # Deserialize from JSON
            config_data = json.loads(setting.value)
            
            # Decrypt API key if it was encrypted
            if config_data.get("api_key") and setting.encrypted:
                config_data["api_key"] = self._decrypt(config_data["api_key"])
            
            return PlatformConfig.from_dict(config_data)
    
    def update_platform_config(self, config: PlatformConfig) -> None:
        """
        Update platform configuration.
        
        Args:
            config: New platform configuration
            
        Note:
            API key is encrypted before storage.
            This triggers adapter hot-reload via AdapterFactory.
        """
        self._ensure_initialized()
        
        # Prepare config data
        config_data = config.to_dict()
        
        # Encrypt API key
        if config_data.get("api_key"):
            config_data["api_key"] = self._encrypt(config_data["api_key"])
            encrypted = True
        else:
            encrypted = False
        
        # Store in database
        with self._get_session() as session:
            setting = session.query(SettingModel).filter_by(key="platform_config").first()
            
            if setting:
                # Update existing
                setting.value = json.dumps(config_data)
                setting.encrypted = encrypted
                setting.updated_at = datetime.utcnow()
            else:
                # Create new
                setting = SettingModel(
                    key="platform_config",
                    value=json.dumps(config_data),
                    encrypted=encrypted,
                )
                session.add(setting)
            
            session.commit()
        
        logger.info(
            "Platform config updated: type=%s, url=%s",
            config.platform_type,
            config.api_url[:30] + "..." if len(config.api_url) > 30 else config.api_url,
        )
    
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
                setting.updated_at = datetime.utcnow()
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
        """
        Store intent activation state.

        Args:
            intent_name: Intent identifier (e.g. ``kpi.energy.per_unit``)
            active: Whether the intent is active

        Raises:
            ValidationError: If intent_name is not in KNOWN_INTENTS
        """
        self._validate_intent_name(intent_name)
        key = f"{self.INTENT_ACTIVE_PREFIX}{intent_name}"
        self.set_setting(key, str(active).lower())

    def is_intent_active(self, intent_name: str) -> bool:
        """
        Read intent activation state.

        Returns ``True`` by default (DEC-005: zero-config).

        Args:
            intent_name: Intent identifier

        Returns:
            True if the intent is active (or not yet configured)
        """
        key = f"{self.INTENT_ACTIVE_PREFIX}{intent_name}"
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
        """Store an emission factor for an energy source.

        Validates energy_source against allowed values. The factor is
        the kg CO₂-eq per kWh (or per m³ for gas).

        Args:
            energy_source: "electricity", "gas", or "water"
            factor: CO₂ emission factor value (must be > 0)
            country: Country code (e.g. "TR", "DE")
            source: Citation for the factor
            year: Reference year

        Raises:
            ValidationError: If energy_source is invalid or factor <= 0
        """
        self._validate_energy_source(energy_source)
        if factor <= 0:
            raise ValidationError(
                message=f"Emission factor must be positive, got {factor}",
                field="factor",
                value=str(factor),
            )
        key = f"{self.EMISSION_FACTOR_PREFIX}{energy_source}"
        data = {
            "energy_source": energy_source,
            "factor": factor,
            "country": country,
            "source": source,
            "year": year,
        }
        self.set_setting(key, data)

    def get_emission_factor(self, energy_source: str) -> EmissionFactor | None:
        """Get a stored emission factor for an energy source.

        Args:
            energy_source: "electricity", "gas", or "water"

        Returns:
            EmissionFactor instance or None if not configured
        """
        key = f"{self.EMISSION_FACTOR_PREFIX}{energy_source}"
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
        """List all stored emission factors.

        Returns:
            Dict mapping energy_source to EmissionFactor
        """
        self._ensure_initialized()
        all_keys = self.list_settings()
        result: dict[str, EmissionFactor] = {}
        for key in all_keys:
            if key.startswith(self.EMISSION_FACTOR_PREFIX):
                name = key[len(self.EMISSION_FACTOR_PREFIX):]
                ef = self.get_emission_factor(name)
                if ef is not None:
                    result[name] = ef
        return result

    def delete_emission_factor(self, energy_source: str) -> bool:
        """Delete a stored emission factor.

        Args:
            energy_source: "electricity", "gas", or "water"

        Returns:
            True if deleted, False if not found
        """
        key = f"{self.EMISSION_FACTOR_PREFIX}{energy_source}"
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

    def set_metric_mapping(self, metric_name: str, mapping: dict[str, Any]) -> None:
        """
        Store a metric mapping.

        Validates the metric name against CanonicalMetric, then persists
        the mapping data using the ``metric_mapping:{name}`` key prefix.

        Args:
            metric_name: Canonical metric name (e.g. ``energy_per_unit``)
            mapping: Mapping data (endpoint, json_path, unit, etc.)

        Raises:
            ValidationError: If metric_name is not a valid CanonicalMetric
        """
        self._validate_metric_name(metric_name)
        key = f"{self.METRIC_MAPPING_PREFIX}{metric_name}"
        self.set_setting(key, mapping)

    def get_metric_mapping(self, metric_name: str) -> dict[str, Any] | None:
        """
        Get a single metric mapping by canonical name.

        Args:
            metric_name: Canonical metric name

        Returns:
            Mapping data dictionary, or None if not found
        """
        key = f"{self.METRIC_MAPPING_PREFIX}{metric_name}"
        return self.get_setting(key, default=None)

    def list_metric_mappings(self) -> dict[str, dict[str, Any]]:
        """
        List all stored metric mappings.

        Returns:
            Dictionary mapping canonical metric names to their mapping data
        """
        self._ensure_initialized()
        all_keys = self.list_settings()
        result: dict[str, dict[str, Any]] = {}
        for key in all_keys:
            if key.startswith(self.METRIC_MAPPING_PREFIX):
                name = key[len(self.METRIC_MAPPING_PREFIX):]
                result[name] = self.get_setting(key)
        return result

    def delete_metric_mapping(self, metric_name: str) -> bool:
        """
        Delete a metric mapping.

        Args:
            metric_name: Canonical metric name

        Returns:
            True if mapping was deleted, False if not found
        """
        key = f"{self.METRIC_MAPPING_PREFIX}{metric_name}"
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
