"""Non-metric intent binding CRUD API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from dependencies import get_settings_service
from schemas.intent_bindings import (
    IntentBindingListResponse,
    IntentBindingRequest,
    IntentBindingResponse,
    NON_METRIC_INTENT_VALUES,
)
from skill.domain.exceptions import ValidationError
from skill.services.settings import SettingsService


router = APIRouter(prefix="/api/v1/config", tags=["intent-bindings"])


def _ensure_valid_intent_name(intent_name: str) -> None:
    """Validate intent_name against supported non-metric intents."""
    if intent_name not in NON_METRIC_INTENT_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid non-metric intent: {intent_name}",
        )


def _binding_data(payload: IntentBindingRequest) -> dict[str, str | None]:
    """Extract storage payload for SettingsService binding methods."""
    return {
        "endpoint": payload.endpoint,
        "method": payload.method,
        "json_path": payload.json_path,
        "success_path": payload.success_path,
        "transform": payload.transform,
    }


def _to_response(intent_name: str, binding: dict) -> IntentBindingResponse:
    """Convert stored binding dict to API response model."""
    return IntentBindingResponse(
        intent_name=intent_name,
        endpoint=str(binding.get("endpoint", "")),
        method=str(binding.get("method", "GET")),
        json_path=str(binding.get("json_path", "")),
        success_path=(
            str(binding.get("success_path"))
            if binding.get("success_path") is not None
            else None
        ),
        transform=binding.get("transform"),
    )


@router.post(
    "/intent-bindings",
    response_model=IntentBindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_intent_binding(
    payload: IntentBindingRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> IntentBindingResponse:
    """Create a new non-metric intent binding."""
    try:
        settings_service.set_intent_binding(
            payload.intent_name,
            _binding_data(payload),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

    saved = settings_service.get_intent_binding(payload.intent_name) or {}
    return _to_response(payload.intent_name, saved)


@router.get("/intent-bindings", response_model=IntentBindingListResponse)
def list_intent_bindings(
    settings_service: SettingsService = Depends(get_settings_service),
) -> IntentBindingListResponse:
    """Return all configured non-metric intent bindings as an array."""
    data = settings_service.list_intent_bindings()
    items = [
        _to_response(intent_name, binding)
        for intent_name, binding in data.items()
    ]
    return IntentBindingListResponse(root=items)


@router.put(
    "/intent-bindings/{intent_name}",
    response_model=IntentBindingResponse,
)
def update_intent_binding(
    intent_name: str,
    payload: IntentBindingRequest,
    settings_service: SettingsService = Depends(get_settings_service),
) -> IntentBindingResponse:
    """Update an existing non-metric intent binding."""
    _ensure_valid_intent_name(intent_name)

    if payload.intent_name != intent_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="intent_name in body must match intent_name path parameter",
        )

    existing = settings_service.get_intent_binding(intent_name)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent binding not found: {intent_name}",
        )

    try:
        settings_service.set_intent_binding(intent_name, _binding_data(payload))
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

    saved = settings_service.get_intent_binding(intent_name) or {}
    return _to_response(intent_name, saved)


@router.delete(
    "/intent-bindings/{intent_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_intent_binding(
    intent_name: str,
    settings_service: SettingsService = Depends(get_settings_service),
) -> Response:
    """Delete a non-metric intent binding."""
    _ensure_valid_intent_name(intent_name)

    deleted = settings_service.delete_intent_binding(intent_name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent binding not found: {intent_name}",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
