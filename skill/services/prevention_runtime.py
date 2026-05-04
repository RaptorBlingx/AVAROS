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
    auth_mode: str
    keycloak_token_url: str
    keycloak_client_id: str
    keycloak_client_secret: str
    keycloak_scope: str
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
    analytics_goals: tuple[str, ...] = ()
    analytics_types: tuple[str, ...] = ()
    descriptive_state: str = "unknown"
    predictive_state: str = "unknown"
    prescriptive_state: str = "not_available"


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
    keycloak_token_url = _read_prevention_auth_setting(
        settings_service,
        env_key="PREVENTION_KEYCLOAK_TOKEN_URL",
        setting_key="prevention_keycloak_token_url",
    )
    keycloak_client_id = _read_prevention_auth_setting(
        settings_service,
        env_key="PREVENTION_KEYCLOAK_CLIENT_ID",
        setting_key="prevention_keycloak_client_id",
    )
    keycloak_client_secret = _read_prevention_auth_setting(
        settings_service,
        env_key="PREVENTION_KEYCLOAK_CLIENT_SECRET",
        setting_key="prevention_keycloak_client_secret",
    )
    keycloak_scope = _read_prevention_auth_setting(
        settings_service,
        env_key="PREVENTION_KEYCLOAK_SCOPE",
        setting_key="prevention_keycloak_scope",
    )
    auth_mode = _resolve_prevention_auth_mode(
        settings_service,
        auth_token=auth_token,
        keycloak_token_url=keycloak_token_url,
        keycloak_client_id=keycloak_client_id,
        keycloak_client_secret=keycloak_client_secret,
    )

    if env_url:
        return PreventionConfig(
            url=env_url,
            auth_token=auth_token,
            auth_mode=auth_mode,
            keycloak_token_url=keycloak_token_url,
            keycloak_client_id=keycloak_client_id,
            keycloak_client_secret=keycloak_client_secret,
            keycloak_scope=keycloak_scope,
            mode="http",
            mode_reason="env_prevention_url",
            endpoint_source="env",
        )

    if settings_url:
        return PreventionConfig(
            url=settings_url,
            auth_token=auth_token,
            auth_mode=auth_mode,
            keycloak_token_url=keycloak_token_url,
            keycloak_client_id=keycloak_client_id,
            keycloak_client_secret=keycloak_client_secret,
            keycloak_scope=keycloak_scope,
            mode="http",
            mode_reason="settings_prevention_url",
            endpoint_source="settings",
        )

    return PreventionConfig(
        url="",
        auth_token=auth_token,
        auth_mode=auth_mode,
        keycloak_token_url=keycloak_token_url,
        keycloak_client_id=keycloak_client_id,
        keycloak_client_secret=keycloak_client_secret,
        keycloak_scope=keycloak_scope,
        mode="disabled",
        mode_reason="prevention_url_missing",
        endpoint_source="none",
    )


def _read_prevention_auth_setting(
    settings_service: SettingsService | None,
    *,
    env_key: str,
    setting_key: str,
) -> str:
    """Read a PREVENTION auth setting, with env taking precedence."""
    env_value = os.environ.get(env_key, "").strip()
    if env_value:
        return env_value
    return str(_read_setting(settings_service, setting_key, "")).strip()


def _resolve_prevention_auth_mode(
    settings_service: SettingsService | None,
    *,
    auth_token: str,
    keycloak_token_url: str,
    keycloak_client_id: str,
    keycloak_client_secret: str,
) -> str:
    """Resolve PREVENTION auth mode without requiring auth for local dev."""
    raw_mode = os.environ.get("PREVENTION_AUTH_MODE", "").strip().lower()
    if not raw_mode:
        raw_mode = str(
            _read_setting(settings_service, "prevention_auth_mode", ""),
        ).strip().lower()

    if raw_mode in {"none", "bearer", "keycloak_client_credentials"}:
        return raw_mode

    if keycloak_token_url and keycloak_client_id and keycloak_client_secret:
        return "keycloak_client_credentials"
    if auth_token:
        return "bearer"
    return "none"


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
            descriptive_state="disabled",
            predictive_state="disabled",
        )

    if not config.url.startswith(("http://", "https://")):
        return PreventionProbeStatus(
            state="misconfigured",
            verified=False,
            message="PREVENTION URL must start with http:// or https://.",
            checked_at=checked_at,
            descriptive_state="unknown",
            predictive_state="unknown",
        )

    if config.auth_mode == "keycloak_client_credentials" and not (
        config.keycloak_token_url
        and config.keycloak_client_id
        and config.keycloak_client_secret
    ):
        return PreventionProbeStatus(
            state="misconfigured",
            verified=False,
            message=(
                "Keycloak auth requires token URL, client ID, and client secret."
            ),
            checked_at=checked_at,
            descriptive_state="unknown",
            predictive_state="unknown",
        )

    client = HttpPreventionClient(
        url=config.url,
        auth_token=config.auth_token if config.auth_mode == "bearer" else "",
        keycloak_token_url=(
            config.keycloak_token_url
            if config.auth_mode == "keycloak_client_credentials"
            else ""
        ),
        keycloak_client_id=(
            config.keycloak_client_id
            if config.auth_mode == "keycloak_client_credentials"
            else ""
        ),
        keycloak_client_secret=(
            config.keycloak_client_secret
            if config.auth_mode == "keycloak_client_credentials"
            else ""
        ),
        keycloak_scope=(
            config.keycloak_scope
            if config.auth_mode == "keycloak_client_credentials"
            else ""
        ),
    )
    try:
        await client.initialize()
        if client.is_connected:
            analytics = await client.list_analytics()
            capability = _summarize_prevention_capabilities(analytics)
            return PreventionProbeStatus(
                state="healthy",
                verified=True,
                message="PREVENTION endpoint is reachable and analytics are loaded.",
                checked_at=checked_at,
                analytics_goals=capability["goals"],
                analytics_types=capability["types"],
                descriptive_state=capability["descriptive_state"],
                predictive_state=capability["predictive_state"],
                prescriptive_state="not_available",
            )
        return PreventionProbeStatus(
            state="unreachable",
            verified=False,
            message="PREVENTION endpoint is configured but did not pass health checks.",
            checked_at=checked_at,
            descriptive_state="unknown",
            predictive_state="unknown",
        )
    except Exception as exc:
        return PreventionProbeStatus(
            state="unreachable",
            verified=False,
            message=str(exc),
            checked_at=checked_at,
            descriptive_state="unknown",
            predictive_state="unknown",
        )
    finally:
        await client.shutdown()


def _summarize_prevention_capabilities(
    analytics: list[dict[str, str]],
) -> dict[str, tuple[str, ...] | str]:
    """Summarize PREVENTION analytics capability states from allAnalysis."""
    goals = tuple(
        sorted({
            str(item.get("analytics_goal", "")).strip()
            for item in analytics
            if str(item.get("analytics_goal", "")).strip()
        }),
    )
    types = tuple(
        sorted({
            str(item.get("analytics_type", "")).strip().upper()
            for item in analytics
            if str(item.get("analytics_type", "")).strip()
        }),
    )
    descriptive_goals = {
        "ENERGY_ANOMALY_CHECK",
        "PRODUCTION_ANOMALY_CHECK",
        "MATERIAL_ANOMALY_CHECK",
        "CO2_ANOMALY_CHECK",
        "SUPPLIER_ANOMALY_CHECK",
        "ENERGY_DRIFT_CHECK",
        "PRODUCTION_DRIFT_CHECK",
        "MATERIAL_DRIFT_CHECK",
        "CO2_DRIFT_CHECK",
        "SUPPLIER_DRIFT_CHECK",
    }
    predictive_goals = {
        "ENERGY_FORECAST",
        "PRODUCTION_FORECAST",
        "MATERIAL_FORECAST",
        "CO2_FORECAST",
        "SUPPLIER_FORECAST",
    }
    return {
        "goals": goals,
        "types": types,
        "descriptive_state": (
            "active" if descriptive_goals.intersection(goals) else "not_configured"
        ),
        "predictive_state": (
            "active" if predictive_goals.intersection(goals) else "not_configured"
        ),
    }


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
