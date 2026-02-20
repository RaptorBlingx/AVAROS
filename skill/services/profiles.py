"""Profile CRUD mixin for SettingsService (DEC-028).

Named adapter profiles allow multiple platform configurations
to be stored, switched instantly, and survive restarts.
The built-in ``"mock"`` profile is always available (virtual,
never stored in DB).

This module is a mixin — ``SettingsService`` inherits from
``ProfileMixin`` to gain profile methods without growing
``settings.py`` beyond the 300-line file limit.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from skill.domain.exceptions import ValidationError
from skill.services.database import SettingModel
from skill.services.models import PlatformConfig

logger = logging.getLogger(__name__)

_PROFILE_NAME_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9\-]{0,48}[a-z0-9]$",
)


class ProfileMixin:
    """Mixin providing profile CRUD for SettingsService.

    Requires host class to provide: ``_ensure_initialized``,
    ``_get_session``, ``_encrypt``, ``_decrypt``,
    ``get_setting``, ``set_setting``, ``delete_setting``,
    ``list_settings``.
    """

    PROFILE_PREFIX = "platform_config:"
    ACTIVE_PROFILE_KEY = "active_profile"
    BUILTIN_MOCK_PROFILE = "mock"

    # ── Public API ──────────────────────────────────────

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all profiles with the built-in mock first.

        Returns:
            List of profile dicts with name, platform_type,
            is_builtin, is_active keys.
        """
        self._ensure_initialized()
        active = self.get_active_profile_name()
        profiles: list[dict[str, Any]] = [
            _mock_profile_summary(active),
        ]
        for name in self._sorted_custom_names():
            config = self.get_profile(name)
            ptype = config.platform_type if config else "unknown"
            profiles.append({
                "name": name,
                "platform_type": ptype,
                "is_builtin": False,
                "is_active": active == name,
            })
        return profiles

    def get_profile(self, name: str) -> PlatformConfig | None:
        """Get a profile's platform configuration.

        The built-in mock profile returns a default
        ``PlatformConfig`` without touching the database.

        Args:
            name: Profile name (e.g. ``"reneryo"``).

        Returns:
            PlatformConfig or None if profile does not exist.
        """
        if name == self.BUILTIN_MOCK_PROFILE:
            return PlatformConfig()
        self._ensure_initialized()
        return self._load_profile(name)

    def create_profile(
        self, name: str, config: PlatformConfig,
    ) -> None:
        """Create a new named profile.

        Args:
            name: 2-50 chars, lowercase alphanumeric + hyphens.
            config: Platform configuration to store.

        Raises:
            ValidationError: If name invalid, reserved, or duplicate.
        """
        _validate_profile_name(name)
        self._ensure_initialized()
        self._assert_not_exists(name)
        self._store_profile(name, config)
        logger.info(
            "Created profile '%s' (type=%s)",
            name, config.platform_type,
        )

    def update_profile(
        self, name: str, config: PlatformConfig,
    ) -> None:
        """Update an existing named profile.

        Args:
            name: Profile name to update.
            config: New platform configuration.

        Raises:
            ValidationError: If mock or profile not found.
        """
        _reject_mock_mutation(name, "modify")
        self._ensure_initialized()
        self._assert_exists(name)
        self._store_profile(name, config)
        logger.info("Updated profile '%s'", name)

    def delete_profile(self, name: str) -> bool:
        """Delete a named profile.

        If deleted was active, falls back to mock (DEC-005).

        Args:
            name: Profile name to delete.

        Returns:
            True if deleted, False if not found.

        Raises:
            ValidationError: If name is ``"mock"``.
        """
        _reject_mock_mutation(name, "delete")
        key = f"{self.PROFILE_PREFIX}{name}"
        deleted = self.delete_setting(key)
        if deleted:
            self._delete_scoped_settings_for_profile(name)
        if deleted and self.get_active_profile_name() == name:
            self.delete_setting(self.ACTIVE_PROFILE_KEY)
            logger.info(
                "Active profile '%s' deleted — reset to mock", name,
            )
        return deleted

    def get_active_profile_name(self) -> str:
        """Return name of the currently active profile.

        Returns ``"mock"`` when none is set.

        Returns:
            Profile name string.
        """
        value = self.get_setting(
            self.ACTIVE_PROFILE_KEY, default=None,
        )
        return str(value) if value else self.BUILTIN_MOCK_PROFILE

    def set_active_profile(self, name: str) -> None:
        """Switch the active profile.

        Setting ``"mock"`` clears the stored key.

        Args:
            name: Profile to activate.

        Raises:
            ValidationError: If profile does not exist.
        """
        if name == self.BUILTIN_MOCK_PROFILE:
            self.delete_setting(self.ACTIVE_PROFILE_KEY)
            return
        self._ensure_initialized()
        self._assert_exists(name)
        self.set_setting(self.ACTIVE_PROFILE_KEY, name)

    # ── Backward Compatibility (DEC-028) ────────────────

    def get_platform_config(self) -> PlatformConfig:
        """Get the active profile's platform configuration.

        Backward-compatible delegate to the profile system.

        Returns:
            PlatformConfig (API key decrypted).
        """
        self._ensure_initialized()
        name = self.get_active_profile_name()
        config = self.get_profile(name)
        return config if config is not None else PlatformConfig()

    def update_platform_config(
        self, config: PlatformConfig,
    ) -> None:
        """Update the active profile's platform configuration.

        Auto-creates a profile when active is mock.

        Args:
            config: New platform configuration.
        """
        self._ensure_initialized()
        name = self.get_active_profile_name()
        if name == self.BUILTIN_MOCK_PROFILE:
            self._auto_create_from_config(config)
        else:
            self.update_profile(name, config)
        _log_config_update(config)

    # ── Migration ───────────────────────────────────────

    def _migrate_legacy_config(self) -> None:
        """Migrate legacy ``platform_config`` to a named profile.

        Runs on ``initialize()``.  Idempotent — safe to repeat.
        """
        result = self._read_legacy_config()
        if result is None:
            return
        config, profile_name = result
        if profile_name == self.BUILTIN_MOCK_PROFILE:
            self.delete_setting("platform_config")
            logger.info("Removed legacy mock platform_config")
            return
        self._store_profile(profile_name, config)
        self.set_setting(self.ACTIVE_PROFILE_KEY, profile_name)
        self.delete_setting("platform_config")
        logger.info(
            "Migrated legacy platform_config → '%s'", profile_name,
        )

    def _migrate_global_settings_to_profile(self) -> None:
        """Migrate global metric/emission/intent keys to active profile.

        Runs once on ``initialize()`` after ``_migrate_legacy_config()``.
        Idempotent — if scoped keys exist or no global keys found, skips.
        """
        active = self.get_active_profile_name()
        if active == self.BUILTIN_MOCK_PROFILE:
            return

        migrated = 0
        for old_prefix, new_prefix in [
            ("metric_mapping:", f"metric_mapping:{active}:"),
            ("intent_binding:", f"intent_binding:{active}:"),
            ("emission_factor:", f"emission_factor:{active}:"),
            ("intent_active:", f"intent_active:{active}:"),
        ]:
            for key in self.list_settings():
                if not key.startswith(old_prefix):
                    continue
                item = key[len(old_prefix):]
                if ":" in item:
                    continue
                new_key = f"{new_prefix}{item}"
                if self.get_setting(new_key, default=None) is not None:
                    self.delete_setting(key)
                    continue
                value = self.get_setting(key)
                if isinstance(value, bool):
                    value = str(value).lower()
                self.set_setting(key=new_key, value=value)
                self.delete_setting(key)
                migrated += 1

        if migrated > 0:
            logger.info(
                "Migrated %d global settings to profile '%s'",
                migrated, active,
            )

    # ── Scoped Key Helpers ──────────────────────────────

    def _scoped_key(self, prefix: str, item: str) -> str:
        """Build a profile-scoped DB key for the active profile.

        Args:
            prefix: Domain prefix (e.g. ``"metric_mapping:"``).
            item: Item identifier (e.g. ``"energy_per_unit"``).

        Returns:
            Key like ``metric_mapping:reneryo:energy_per_unit``.

        Raises:
            ValidationError: If active profile is mock.
        """
        profile = self.get_active_profile_name()
        if profile == self.BUILTIN_MOCK_PROFILE:
            raise ValidationError(
                message="Cannot write settings for built-in mock profile",
                field="profile",
                value=profile,
            )
        return f"{prefix}{profile}:{item}"

    def _scoped_key_for(
        self, prefix: str, profile: str, item: str,
    ) -> str:
        """Build a profile-scoped DB key for a specific profile.

        Args:
            prefix: Domain prefix (e.g. ``"intent_active:"``).
            profile: Profile name (e.g. ``"reneryo"``).
            item: Item identifier.

        Returns:
            Key like ``intent_active:reneryo:kpi.energy.per_unit``.
        """
        return f"{prefix}{profile}:{item}"

    # ── Private Helpers ─────────────────────────────────

    def _read_legacy_config(
        self,
    ) -> tuple[PlatformConfig, str] | None:
        """Read the legacy ``platform_config`` key if it exists.

        All ORM access happens inside the session block.

        Returns:
            ``(config, profile_name)`` or None.
        """
        with self._get_session() as session:
            legacy = (
                session.query(SettingModel)
                .filter_by(key="platform_config")
                .first()
            )
            if not legacy:
                return None
            data = json.loads(legacy.value)
            if data.get("api_key") and legacy.encrypted:
                data["api_key"] = self._decrypt(data["api_key"])
            config = PlatformConfig.from_dict(data)
            return config, config.platform_type.lower()

    def _load_profile(self, name: str) -> PlatformConfig | None:
        """Read a non-mock profile from the database.

        Args:
            name: Profile name.

        Returns:
            PlatformConfig or None.
        """
        key = f"{self.PROFILE_PREFIX}{name}"
        with self._get_session() as session:
            setting = (
                session.query(SettingModel)
                .filter_by(key=key)
                .first()
            )
            if not setting:
                return None
            data = json.loads(setting.value)
            if data.get("api_key") and setting.encrypted:
                data["api_key"] = self._decrypt(data["api_key"])
            return PlatformConfig.from_dict(data)

    def _store_profile(
        self, name: str, config: PlatformConfig,
    ) -> None:
        """Serialize, encrypt, and persist a profile.

        Args:
            name: Profile name (key suffix).
            config: Configuration to store.
        """
        serialized, encrypted = _serialize_config(
            config, self._encrypt,
        )
        self._upsert_profile(
            f"{self.PROFILE_PREFIX}{name}", serialized, encrypted,
        )

    def _upsert_profile(
        self, key: str, value: str, encrypted: bool,
    ) -> None:
        """Insert or update a raw profile setting row.

        Args:
            key: Setting key.
            value: Serialized JSON string.
            encrypted: Whether value contains encrypted data.
        """
        with self._get_session() as session:
            setting = (
                session.query(SettingModel)
                .filter_by(key=key)
                .first()
            )
            if setting:
                setting.value = value
                setting.encrypted = encrypted
                setting.updated_at = datetime.now(timezone.utc)
            else:
                session.add(SettingModel(
                    key=key, value=value, encrypted=encrypted,
                ))
            session.commit()

    def _assert_exists(self, name: str) -> None:
        """Raise ValidationError if profile not in DB."""
        key = f"{self.PROFILE_PREFIX}{name}"
        with self._get_session() as session:
            if not session.query(SettingModel).filter_by(
                key=key,
            ).first():
                raise ValidationError(
                    message=f"Profile '{name}' not found",
                    field="name",
                    value=name,
                )

    def _assert_not_exists(self, name: str) -> None:
        """Raise ValidationError if profile already in DB."""
        key = f"{self.PROFILE_PREFIX}{name}"
        with self._get_session() as session:
            if session.query(SettingModel).filter_by(
                key=key,
            ).first():
                raise ValidationError(
                    message=f"Profile '{name}' already exists",
                    field="name",
                    value=name,
                )

    def _sorted_custom_names(self) -> list[str]:
        """Return sorted names of stored custom profiles."""
        prefix = self.PROFILE_PREFIX
        return sorted(
            k[len(prefix):]
            for k in self.list_settings()
            if k.startswith(prefix)
        )

    def _delete_scoped_settings_for_profile(self, profile: str) -> None:
        """Delete all profile-scoped settings for a given profile.

        Args:
            profile: Profile name whose scoped settings should be removed.
        """
        prefixes = (
            f"metric_mapping:{profile}:",
            f"emission_factor:{profile}:",
            f"intent_active:{profile}:",
        )
        for key in self.list_settings():
            if key.startswith(prefixes):
                self.delete_setting(key)

    def _auto_create_from_config(
        self, config: PlatformConfig,
    ) -> None:
        """Auto-create profile from platform_type when active is mock.

        Args:
            config: Platform config with type as name source.
        """
        name = config.platform_type.lower()
        if name == self.BUILTIN_MOCK_PROFILE:
            return
        if self.get_profile(name) is None:
            self.create_profile(name, config)
        else:
            self.update_profile(name, config)
        self.set_active_profile(name)


# ── Module-level helpers ────────────────────────────────


def _validate_profile_name(name: str) -> None:
    """Validate a profile name.

    Rules: 2-50 chars, lowercase alphanumeric + hyphens,
    no leading/trailing hyphen, cannot be ``"mock"``.

    Args:
        name: Profile name to validate.

    Raises:
        ValidationError: If name is invalid.
    """
    if name == ProfileMixin.BUILTIN_MOCK_PROFILE:
        raise ValidationError(
            message=(
                "Cannot create profile named 'mock' "
                "— it is a built-in profile"
            ),
            field="name",
            value=name,
        )
    if not _PROFILE_NAME_PATTERN.match(name):
        raise ValidationError(
            message=(
                f"Invalid profile name: '{name}'. "
                "Must be 2-50 chars, lowercase alphanumeric "
                "+ hyphens, no leading/trailing hyphen."
            ),
            field="name",
            value=name,
        )


def _reject_mock_mutation(name: str, action: str) -> None:
    """Raise ValidationError if name is the built-in mock profile.

    Args:
        name: Profile name to check.
        action: Verb for error message ("modify" or "delete").

    Raises:
        ValidationError: If name is ``"mock"``.
    """
    if name == ProfileMixin.BUILTIN_MOCK_PROFILE:
        raise ValidationError(
            message=f"Cannot {action} built-in mock profile",
            field="name",
            value=name,
        )


def _mock_profile_summary(active: str) -> dict[str, Any]:
    """Build the virtual mock profile summary dict."""
    return {
        "name": ProfileMixin.BUILTIN_MOCK_PROFILE,
        "platform_type": "mock",
        "is_builtin": True,
        "is_active": active == ProfileMixin.BUILTIN_MOCK_PROFILE,
    }


def _serialize_config(
    config: PlatformConfig,
    encrypt_fn: Any,
) -> tuple[str, bool]:
    """Serialize config to JSON, encrypting api_key.

    Args:
        config: Platform configuration.
        encrypt_fn: Encryption callable for the api_key.

    Returns:
        ``(json_string, is_encrypted)`` tuple.
    """
    data = config.to_dict()
    encrypted = bool(data.get("api_key"))
    if encrypted:
        data["api_key"] = encrypt_fn(data["api_key"])
    return json.dumps(data), encrypted


def _log_config_update(config: PlatformConfig) -> None:
    """Log a platform config update."""
    url = config.api_url
    truncated = url[:30] + "..." if len(url) > 30 else url
    logger.info(
        "Platform config updated: type=%s, url=%s",
        config.platform_type, truncated,
    )
