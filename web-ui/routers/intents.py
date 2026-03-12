"""Intent activation API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import get_settings_service
from schemas.intents import (
    IntentListResponse,
    IntentStateResponse,
    IntentToggleRequest,
)
from skill.domain.exceptions import ValidationError
from skill.services.settings import INTENT_CATEGORIES, KNOWN_INTENTS, SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["intents"])


def _build_intent_state(
    intent_name: str,
    settings_service: SettingsService,
    mapped_metrics: set[str],
) -> IntentStateResponse:
    """Build a single IntentStateResponse.

    Args:
        intent_name: Canonical intent identifier.
        settings_service: SettingsService for state look-ups.
        mapped_metrics: Set of metric names that have stored mappings.

    Returns:
        Fully populated IntentStateResponse.
    """
    requirements = settings_service.get_intent_metric_requirements()
    required = requirements.get(intent_name, [])
    all_mapped = all(m in mapped_metrics for m in required)

    return IntentStateResponse(
        intent_name=intent_name,
        active=settings_service.is_intent_active(intent_name),
        required_metrics=required,
        metrics_mapped=all_mapped,
        category=INTENT_CATEGORIES.get(intent_name, "kpi"),
    )


@router.get("/intents", response_model=IntentListResponse)
def list_intents(
    settings_service: SettingsService = Depends(get_settings_service),
) -> IntentListResponse:
    """List all intents with activation state and metric dependencies."""
    mapped_metrics = set(settings_service.list_metric_mappings().keys())
    items = [
        _build_intent_state(name, settings_service, mapped_metrics)
        for name in KNOWN_INTENTS
    ]
    active_count = sum(1 for i in items if i.active)
    return IntentListResponse(
        intents=items,
        total=len(items),
        active_count=active_count,
    )


@router.put("/intents/{intent_name}", response_model=IntentStateResponse)
def toggle_intent(
    intent_name: str,
    payload: IntentToggleRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> IntentStateResponse:
    """Toggle an intent's activation state."""
    try:
        settings_service.set_intent_active(intent_name, payload.active)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.message,
        ) from exc

    mapped_metrics = set(settings_service.list_metric_mappings().keys())
    return _build_intent_state(intent_name, settings_service, mapped_metrics)
