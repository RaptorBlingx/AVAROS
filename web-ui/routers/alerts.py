"""Proactive alert configuration endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from dependencies import get_settings_service
from schemas.alerts import AlertConfigSchema, MonitoredPairSchema
from skill.domain.alert_models import AlertConfig, MonitoredPair
from skill.domain.models import CanonicalMetric
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["config"])
logger = logging.getLogger(__name__)


def _domain_to_schema(
    config: AlertConfig,
    query_threshold: float,
) -> AlertConfigSchema:
    """Convert domain AlertConfig to API response schema."""
    return AlertConfigSchema(
        enabled=config.enabled,
        interval_seconds=config.interval_seconds,
        severity_threshold=config.severity_threshold,
        cooldown_minutes=config.cooldown_minutes,
        monitored_pairs=[
            MonitoredPairSchema(metric=p.metric.value, asset_id=p.asset_id)
            for p in config.monitored_pairs
        ],
        z_score_threshold=config.z_score_threshold,
        query_z_score_threshold=query_threshold,
    )


def _schema_to_domain(schema: AlertConfigSchema) -> AlertConfig:
    """Convert API request schema to domain AlertConfig."""
    pairs: list[MonitoredPair] = []
    for p in schema.monitored_pairs:
        try:
            metric = CanonicalMetric(p.metric)
        except ValueError:
            continue
        pairs.append(MonitoredPair(metric=metric, asset_id=p.asset_id))

    return AlertConfig(
        enabled=schema.enabled,
        interval_seconds=schema.interval_seconds,
        severity_threshold=schema.severity_threshold,
        cooldown_minutes=schema.cooldown_minutes,
        monitored_pairs=tuple(pairs),
        z_score_threshold=schema.z_score_threshold,
    )


@router.get("/alert-config", response_model=AlertConfigSchema)
def get_alert_config(
    settings_service: SettingsService = Depends(get_settings_service),
) -> AlertConfigSchema:
    """Return current proactive alert configuration."""
    config = settings_service.get_alert_config()
    query_threshold = settings_service.get_query_anomaly_threshold()
    return _domain_to_schema(config, query_threshold)


@router.put("/alert-config", response_model=AlertConfigSchema)
def save_alert_config(
    payload: AlertConfigSchema,
    settings_service: SettingsService = Depends(get_settings_service),
) -> AlertConfigSchema:
    """Update proactive alert configuration."""
    config = _schema_to_domain(payload)
    settings_service.save_alert_config(config)
    settings_service.set_query_anomaly_threshold(
        payload.query_z_score_threshold,
    )
    logger.info(
        "Alert config updated: enabled=%s interval=%ds threshold=%s",
        config.enabled, config.interval_seconds, config.severity_threshold,
    )
    return _domain_to_schema(config, payload.query_z_score_threshold)
