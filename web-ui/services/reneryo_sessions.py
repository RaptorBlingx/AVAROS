"""Short-lived, origin-bound Reneryo widget sessions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReneryoSession:
    organization_id: str
    finding_id: str
    entity_id: str
    metric_name: str
    language: str
    origin: str
    expires_at: int


def issue_session(payload: dict[str, Any], ttl_seconds: int = 300) -> tuple[str, int]:
    now = int(time.time())
    claims = {**payload, "iat": now, "exp": now + min(max(ttl_seconds, 60), 600)}
    encoded = _b64(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64(hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}", claims["exp"]


def validate_session(token: str, origin: str) -> ReneryoSession:
    try:
        encoded, signature = token.split(".", 1)
        expected = _b64(hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        claims = json.loads(_unb64(encoded))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid widget session") from exc
    if int(claims.get("exp", 0)) <= int(time.time()):
        raise ValueError("Expired widget session")
    expected_origin = str(claims.get("origin", "")).rstrip("/")
    if not origin or origin.rstrip("/") != expected_origin:
        raise ValueError("Widget session origin mismatch")
    organization_id = str(claims.get("organization_id", "")).strip()
    if not organization_id:
        raise ValueError("Widget session has no organization")
    return ReneryoSession(
        organization_id=organization_id,
        finding_id=str(claims.get("finding_id", "")),
        entity_id=str(claims.get("entity_id", "")),
        metric_name=str(claims.get("metric_name", "")),
        language=str(claims.get("language", "en-US")),
        origin=expected_origin,
        expires_at=int(claims["exp"]),
    )


def _secret() -> bytes:
    value = os.environ.get("AVAROS_WIDGET_SESSION_SECRET", "").encode()
    if len(value) < 32:
        raise ValueError("AVAROS_WIDGET_SESSION_SECRET must be at least 32 bytes")
    return value


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
