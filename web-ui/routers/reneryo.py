"""Server-to-server entry points for the embedded Reneryo assistant."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from services.reneryo_sessions import issue_session

router = APIRouter(prefix="/integrations/reneryo", tags=["reneryo-integration"])


def _first_header_value(value: str | None) -> str:
    return (value or "").split(",", maxsplit=1)[0].strip()


def _public_urls(request: Request) -> tuple[str, str]:
    """Build browser URLs from the TLS terminator's forwarded request."""
    forwarded_proto = _first_header_value(request.headers.get("x-forwarded-proto"))
    forwarded_host = _first_header_value(request.headers.get("x-forwarded-host"))
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    scheme = forwarded_proto or request.url.scheme
    websocket_scheme = "wss" if scheme in {"https", "wss"} else "ws"
    return f"{scheme}://{host}/avaros-widget.js", f"{websocket_scheme}://{host}/hivemind/"


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
    widget_script_url, websocket_url = _public_urls(request)
    return {
        "sessionToken": token,
        "expiresAt": expires_at,
        "widgetScriptUrl": widget_script_url,
        "websocketUrl": websocket_url,
    }
