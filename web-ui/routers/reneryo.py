"""Server-to-server entry points for the embedded Reneryo assistant."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from services.reneryo_sessions import issue_session

router = APIRouter(prefix="/integrations/reneryo", tags=["reneryo-integration"])


class WidgetSessionRequest(BaseModel):
    organization_id: str = Field(min_length=1)
    finding_id: str = ""
    entity_id: str = ""
    metric_name: str = ""
    language: str = "en-US"
    origin: str = Field(min_length=1)


@router.post("/widget-sessions")
def create_widget_session(
    body: WidgetSessionRequest,
    request: Request,
    authorization: str = Header(default=""),
) -> dict[str, str | int]:
    expected = os.environ.get("AVAROS_RENERYO_SERVICE_TOKEN", "")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid service credential")
    allowed = {
        item.strip().rstrip("/")
        for item in os.environ.get("AVAROS_RENERYO_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    origin = body.origin.rstrip("/")
    if not allowed or origin not in allowed:
        raise HTTPException(status_code=403, detail="Origin is not allowed")
    token, expires_at = issue_session(
        {
            "organization_id": body.organization_id,
            "finding_id": body.finding_id,
            "entity_id": body.entity_id,
            "metric_name": body.metric_name,
            "language": body.language,
            "origin": origin,
        }
    )
    base_url = str(request.base_url).rstrip("/")
    return {
        "sessionToken": token,
        "expiresAt": expires_at,
        "widgetScriptUrl": f"{base_url}/avaros-widget.js",
        "websocketUrl": f"{base_url}/hivemind/",
    }
