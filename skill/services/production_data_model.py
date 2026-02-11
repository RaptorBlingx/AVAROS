"""
ProductionDataModel — ORM and Mapping Helpers

SQLAlchemy ORM model for supplementary production data, plus
stateless conversion helpers between ORM rows and domain objects.

Split from ``production_data.py`` to keep each file under 300 lines.
The service class lives in ``production_data.py``; this module holds
the table definition and mapping utilities.
"""

from __future__ import annotations

import os
from datetime import date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Query

from skill.domain.production import ProductionRecord
from skill.services.database import Base


# ── ORM Model ───────────────────────────────────────────


class ProductionDataModel(Base):
    """ORM model for supplementary production data."""

    __tablename__ = "production_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_date = Column(Date, nullable=False, index=True)
    asset_id = Column(String(100), nullable=False, index=True)
    production_count = Column(Integer, nullable=False, default=0)
    good_count = Column(Integer, nullable=False, default=0)
    material_consumed_kg = Column(Float, nullable=False, default=0.0)
    shift = Column(String(50), nullable=False, default="")
    batch_id = Column(String(100), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("ix_prod_date_asset", "record_date", "asset_id"),
    )

    def __repr__(self) -> str:
        """Return readable representation."""
        return (
            f"<ProductionData(id={self.id}, date={self.record_date}, "
            f"asset={self.asset_id}, count={self.production_count})>"
        )


# ── Stateless mapping helpers ────────────────────────────


def resolve_database_url(explicit_url: str | None) -> str:
    """Determine database URL from explicit value, env, or default.

    Args:
        explicit_url: URL passed directly to the constructor.

    Returns:
        Resolved SQLAlchemy database URL.
    """
    if explicit_url:
        return explicit_url
    return os.environ.get(
        "AVAROS_DATABASE_URL", "sqlite:///:memory:",
    )


def domain_to_orm(record: ProductionRecord) -> ProductionDataModel:
    """Convert a domain ProductionRecord to an ORM row.

    Args:
        record: Domain production record.

    Returns:
        SQLAlchemy ORM instance (not yet committed).
    """
    return ProductionDataModel(
        record_date=record.record_date,
        asset_id=record.asset_id,
        production_count=record.production_count,
        good_count=record.good_count,
        material_consumed_kg=record.material_consumed_kg,
        shift=record.shift,
        batch_id=record.batch_id,
        notes=record.notes,
    )


def orm_to_domain(row: ProductionDataModel) -> ProductionRecord:
    """Convert an ORM row to a domain ProductionRecord.

    Args:
        row: SQLAlchemy ORM instance.

    Returns:
        Immutable domain ProductionRecord.
    """
    return ProductionRecord(
        record_date=row.record_date,
        asset_id=row.asset_id,
        production_count=row.production_count,
        good_count=row.good_count,
        material_consumed_kg=row.material_consumed_kg,
        shift=row.shift or "",
        batch_id=row.batch_id or "",
        notes=row.notes or "",
    )


def apply_filters(
    query: Query,  # type: ignore[type-arg]
    asset_id: str | None,
    start_date: date | None,
    end_date: date | None,
) -> Query:  # type: ignore[type-arg]
    """Apply optional filters to a SQLAlchemy query.

    Args:
        query: Base query on ProductionDataModel.
        asset_id: Optional asset filter.
        start_date: Optional start date filter.
        end_date: Optional end date filter.

    Returns:
        Filtered query.
    """
    if asset_id is not None:
        query = query.filter(ProductionDataModel.asset_id == asset_id)
    if start_date is not None:
        query = query.filter(
            ProductionDataModel.record_date >= start_date,
        )
    if end_date is not None:
        query = query.filter(
            ProductionDataModel.record_date <= end_date,
        )
    return query
