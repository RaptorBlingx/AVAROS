"""Shared SQLAlchemy declarative base for all ORM models.

Both ``SettingModel`` (settings table) and ``ProductionDataModel``
(production_data table) import this base so that a single
``Base.metadata.create_all(engine)`` call creates all tables.
"""

from __future__ import annotations

from sqlalchemy.orm import declarative_base

Base = declarative_base()
