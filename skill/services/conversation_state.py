"""Bounded, in-memory DIA context with no conversation-text persistence."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any

from skill.domain.models import CanonicalMetric, TimePeriod


@dataclass
class DialogueState:
    """Minimal entities and evidence required for deterministic follow-ups."""

    metrics: tuple[CanonicalMetric, ...] = ()
    asset_ids: tuple[str, ...] = ()
    period: TimePeriod | None = None
    operation: str = ""
    answer_evidence: tuple[dict[str, Any], ...] = ()
    pending_clarification: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DialogueStateStore:
    """Thread-safe TTL/LRU store; utterance text is deliberately never stored."""

    def __init__(self, *, ttl_minutes: int = 15, max_sessions: int = 256) -> None:
        self._ttl = timedelta(minutes=max(1, ttl_minutes))
        self._max_sessions = max(1, max_sessions)
        self._items: OrderedDict[str, DialogueState] = OrderedDict()
        self._lock = RLock()

    def get(self, session_id: str) -> DialogueState | None:
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge(now)
            state = self._items.pop(session_id, None)
            if state is None:
                return None
            self._items[session_id] = state
            return state

    def put(self, session_id: str, state: DialogueState) -> None:
        if not session_id:
            return
        with self._lock:
            self._purge(datetime.now(timezone.utc))
            state.updated_at = datetime.now(timezone.utc)
            self._items.pop(session_id, None)
            self._items[session_id] = state
            while len(self._items) > self._max_sessions:
                self._items.popitem(last=False)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._items.pop(session_id, None)

    def _purge(self, now: datetime) -> None:
        expired = [
            key for key, state in self._items.items()
            if now - state.updated_at > self._ttl
        ]
        for key in expired:
            self._items.pop(key, None)


def message_session_id(message) -> str:
    """Resolve a stable browser/bus session identifier without storing text."""
    context = getattr(message, "context", {}) or {}
    data = getattr(message, "data", {}) or {}
    session = context.get("session")
    if isinstance(session, dict):
        nested = str(session.get("session_id", "") or "").strip()
        if nested:
            return nested
    for container in (context, data):
        for key in ("session", "session_id", "client_name", "source"):
            value = str(container.get(key, "") or "").strip()
            if value:
                return value
    return "shared-bus"
