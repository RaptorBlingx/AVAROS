"""Shared cookie normalization helpers for adapter/auth flows."""

from __future__ import annotations

import re
from urllib.parse import unquote

_UUID_TOKEN_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
)


def normalize_cookie_header_value(raw_cookie: str, *, decode: bool = False) -> str:
    """Normalize raw cookie input into a valid Cookie header value."""
    cookie_value = (raw_cookie or "").strip()
    if cookie_value.lower().startswith("cookie:"):
        cookie_value = cookie_value.split(":", 1)[1].strip()

    if decode:
        cookie_value = unquote(cookie_value)

    # Forward explicit cookie pairs/lists as-is.
    if cookie_value.startswith("S=") or ";" in cookie_value:
        return cookie_value

    # Accept common single cookie-pair values like "JSESSIONID=...".
    if "=" in cookie_value:
        cookie_name = cookie_value.split("=", 1)[0].strip()
        if (
            cookie_name
            and cookie_name[0].isalpha()
            and len(cookie_name) <= 32
            and all(ch.isalnum() or ch in "_-.$" for ch in cookie_name)
        ):
            return cookie_value

    # Bare UUID token: send both common variants.
    if _UUID_TOKEN_PATTERN.fullmatch(cookie_value):
        return f"JSESSIONID={cookie_value}; S={cookie_value}"

    return f"S={cookie_value}"
