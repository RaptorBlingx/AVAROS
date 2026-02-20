"""Request and response schemas for non-metric intent bindings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, RootModel

from skill.services.settings import NON_METRIC_INTENTS


NON_METRIC_INTENT_VALUES = NON_METRIC_INTENTS
NonMetricIntentName = Literal[*NON_METRIC_INTENT_VALUES]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class IntentBindingRequest(BaseModel):
    """Payload for creating/updating an intent binding."""

    intent_name: NonMetricIntentName = Field(
        ...,
        description="Non-metric intent identifier.",
    )
    endpoint: str = Field(
        ...,
        min_length=1,
        description="Platform API endpoint path for the intent.",
    )
    method: HttpMethod = Field(
        ...,
        description="HTTP method for this intent binding.",
    )
    json_path: str = Field(
        ...,
        min_length=1,
        description="JSONPath used to extract display payload.",
    )
    success_path: str | None = Field(
        default=None,
        description="Optional JSONPath used to determine action success.",
    )
    transform: str | None = Field(
        default=None,
        description="Optional transform instruction (future use).",
    )


class IntentBindingResponse(BaseModel):
    """Intent binding response object."""

    intent_name: NonMetricIntentName = Field(
        ...,
        description="Non-metric intent identifier.",
    )
    endpoint: str = Field(
        ...,
        description="Bound platform endpoint path.",
    )
    method: HttpMethod = Field(
        ...,
        description="Configured HTTP method.",
    )
    json_path: str = Field(
        ...,
        description="Configured JSONPath for response extraction.",
    )
    success_path: str | None = Field(
        default=None,
        description="Optional success JSONPath.",
    )
    transform: str | None = Field(
        default=None,
        description="Optional transform instruction.",
    )


class IntentBindingListResponse(RootModel[list[IntentBindingResponse]]):
    """Array response wrapper for intent bindings list."""
