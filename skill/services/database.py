"""Shared SQLAlchemy base and ORM models for AVAROS settings.

Both ``SettingModel`` (settings table) and ``ProductionDataModel``
(production_data table) share the same ``Base`` so that a single
``Base.metadata.create_all(engine)`` call creates all tables.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _utcnow() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class SettingModel(Base):
    """SQLAlchemy model for key-value settings storage.

    Stores settings with metadata including encryption status
    and creation/update timestamps.
    """

    __tablename__ = "settings"

    key = Column(String(255), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    encrypted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<Setting(key={self.key}, encrypted={self.encrypted})>"
