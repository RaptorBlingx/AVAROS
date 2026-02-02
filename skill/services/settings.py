"""
SettingsService - Database-Backed Configuration

Manages AVAROS configuration stored in SQLite database.
Supports hot-reload without container restart.

Zero-Config Philosophy:
    - On first run, no configuration required (MockAdapter used)
    - Users configure via Web UI, not YAML files
    - Settings persisted to database for reliability

Usage:
    settings = SettingsService(db_path="/data/avaros.db")
    
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
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, Column, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from cryptography.fernet import Fernet
import base64
import hashlib


logger = logging.getLogger(__name__)

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
    
    Stores all configuration in SQLite for persistence across restarts.
    Provides hot-reload capability for configuration changes.
    Encrypts sensitive data (API keys) at rest.
    
    Attributes:
        db_path: Path to SQLite database file
        _engine: SQLAlchemy engine
        _session_factory: Session factory
        _encryption_key: Fernet encryption key for sensitive data
    
    Example:
        service = SettingsService("/data/avaros.db")
        
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
    
    def __init__(self, db_path: str | Path | None = None, encryption_key: str | None = None):
        """
        Initialize settings service.
        
        Args:
            db_path: Path to SQLite database. Defaults to in-memory.
            encryption_key: Base64-encoded Fernet key. If None, generates new key.
        """
        self._db_path = Path(db_path) if db_path else None
        self._engine = None
        self._session_factory = None
        self._initialized = False
        
        # Initialize encryption
        if encryption_key:
            self._encryption_key = encryption_key.encode()
        else:
            # Generate encryption key from db_path (deterministic but unique)
            if self._db_path:
                seed = str(self._db_path).encode()
                key_material = hashlib.sha256(seed).digest()
                self._encryption_key = base64.urlsafe_b64encode(key_material)
            else:
                # In-memory: generate random key
                self._encryption_key = Fernet.generate_key()
        
        self._cipher = Fernet(self._encryption_key)
    
    def initialize(self) -> None:
        """
        Initialize the settings database.
        
        Creates tables if they don't exist.
        Called automatically on first access.
        """
        if self._initialized:
            return
        
        # Create database connection
        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{self._db_path}"
        else:
            db_url = "sqlite:///:memory:"
        
        self._engine = create_engine(db_url, echo=False, future=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)
        
        # Create tables
        Base.metadata.create_all(self._engine)
        
        self._initialized = True
        logger.info("SettingsService initialized (db=%s)", db_url)
    
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
