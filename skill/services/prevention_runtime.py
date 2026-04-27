"""Helpers for PREVENTION runtime configuration, probing, and data freshness."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from skill.clients.prevention_http import HttpPreventionClient

if TYPE_CHECKING:
    from skill.services.settings import SettingsService


_DEFAULT_EXPORT_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "prevention-addon"
    / "data"
    / "export_manifest.json"
)
_EXPORT_MANIFEST_ENV_VAR = "PREVENTION_EXPORT_MANIFEST_PATH"
_DEFAULT_MAX_AGE_MINUTES = 24 * 60


@dataclass(frozen=True)
class PreventionConfig:
    """Resolved PREVENTION configuration across env and persistent settings."""

    url: str
    auth_token: str
    mode: str
    mode_reason: str
    endpoint_source: str


@dataclass(frozen=True)
class PreventionProbeStatus:
    """Live PREVENTION health probe result."""

    state: str
    verified: bool
    message: str
    checked_at: str | None


@dataclass(frozen=True)
class PreventionDataStatus:
    """Freshness state for exported PREVENTION input data."""

    state: str
    message: str
    updated_at: str | None
    record_count: int | None


def _read_setting(
    settings_service: SettingsService | None,
    key: str,
    default: Any = "",
) -> Any:
    """Read a setting defensively from SettingsService."""
    if settings_service is None:
        return default
    try:
        return settings_service.get_setting(key, default)
    except Exception:
        return default


def resolve_prevention_config(
    settings_service: SettingsService | None,
) -> PreventionConfig:
    """Resolve PREVENTION endpoint and auth config."""
    env_url = os.environ.get("PREVENTION_URL", "").strip()
    settings_url = str(
        _read_setting(settings_service, "prevention_url", ""),
    ).strip()
    auth_token = os.environ.get("PREVENTION_AUTH_TOKEN", "").strip()
    if not auth_token:
        auth_token = str(
            _read_setting(settings_service, "prevention_auth_token", ""),
        ).strip()

    if env_url:
        return PreventionConfig(
            url=env_url,
            auth_token=auth_token,
            mode="http",
            mode_reason="env_prevention_url",
            endpoint_source="env",
        )

    if settings_url:
        return PreventionConfig(
            url=settings_url,
            auth_token=auth_token,
            mode="http",
            mode_reason="settings_prevention_url",
            endpoint_source="settings",
        )

    return PreventionConfig(
        url="",
        auth_token=auth_token,
        mode="disabled",
        mode_reason="prevention_url_missing",
        endpoint_source="none",
    )


async def probe_prevention_status(
    config: PreventionConfig,
) -> PreventionProbeStatus:
    """Probe the configured PREVENTION endpoint for live health."""
    checked_at = datetime.now(tz=timezone.utc).isoformat()

    if config.mode != "http" or not config.url:
        return PreventionProbeStatus(
            state="disabled",
            verified=False,
            message="PREVENTION is disabled until a URL is configured.",
            checked_at=None,
        )

    if not config.url.startswith(("http://", "https://")):
        return PreventionProbeStatus(
            state="misconfigured",
            verified=False,
            message="PREVENTION URL must start with http:// or https://.",
            checked_at=checked_at,
        )

    client = HttpPreventionClient(
        url=config.url,
        auth_token=config.auth_token,
    )
    try:
        await client.initialize()
        if client.is_connected:
            return PreventionProbeStatus(
                state="healthy",
                verified=True,
                message="PREVENTION endpoint is reachable and analytics are loaded.",
                checked_at=checked_at,
            )
        return PreventionProbeStatus(
            state="unreachable",
            verified=False,
            message="PREVENTION endpoint is configured but did not pass health checks.",
            checked_at=checked_at,
        )
    except Exception as exc:
        return PreventionProbeStatus(
            state="unreachable",
            verified=False,
            message=str(exc),
            checked_at=checked_at,
        )
    finally:
        await client.shutdown()


def resolve_prevention_data_max_age_minutes(
    settings_service: SettingsService | None,
) -> int:
    """Resolve freshness threshold for exported PREVENTION data."""
    raw_value = os.environ.get("PREVENTION_DATA_MAX_AGE_MINUTES", "").strip()
    if not raw_value:
        raw_value = str(
            _read_setting(
                settings_service,
                "prevention_data_max_age_minutes",
                _DEFAULT_MAX_AGE_MINUTES,
            ),
        ).strip()

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_AGE_MINUTES

    return max(value, 1)


def _parse_iso_timestamp(raw_value: Any) -> datetime | None:
    """Parse an ISO timestamp into UTC."""
    normalized = str(raw_value or "").strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_prevention_data_status(
    settings_service: SettingsService | None,
    manifest_path: Path | None = None,
) -> PreventionDataStatus:
    """Resolve freshness state for the exported PREVENTION input data."""
    path = manifest_path or _resolve_export_manifest_path()
    if not path.exists():
        return PreventionDataStatus(
            state="missing",
            message="No PREVENTION export manifest has been generated yet.",
            updated_at=None,
            record_count=None,
        )

    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return PreventionDataStatus(
            state="invalid",
            message="PREVENTION export manifest could not be parsed.",
            updated_at=None,
            record_count=None,
        )

    updated_at = _parse_iso_timestamp(payload.get("exported_at"))
    if updated_at is None:
        return PreventionDataStatus(
            state="invalid",
            message="PREVENTION export manifest is missing a valid exported_at timestamp.",
            updated_at=None,
            record_count=None,
        )

    try:
        record_count = int(payload.get("total_records", 0))
    except (TypeError, ValueError):
        record_count = None

    max_age_minutes = resolve_prevention_data_max_age_minutes(settings_service)
    age_minutes = (
        datetime.now(tz=timezone.utc) - updated_at
    ).total_seconds() / 60.0
    is_stale = age_minutes > max_age_minutes
    state = "stale" if is_stale else "fresh"
    freshness = f"{int(age_minutes)} minutes old"
    if record_count is None:
        message = f"Latest PREVENTION export is {freshness}."
    else:
        message = (
            f"Latest PREVENTION export is {freshness} with {record_count} records."
        )

    return PreventionDataStatus(
        state=state,
        message=message,
        updated_at=updated_at.isoformat(),
        record_count=record_count,
    )


def _resolve_export_manifest_path() -> Path:
    """Resolve the PREVENTION export manifest path across host and containers."""
    raw_path = os.environ.get(_EXPORT_MANIFEST_ENV_VAR, "").strip()
    if raw_path:
        return Path(raw_path)
    return _DEFAULT_EXPORT_MANIFEST