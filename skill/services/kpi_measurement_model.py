"""
KPIMeasurementModel — ORM and Mapping Helpers

SQLAlchemy ORM models for KPI baselines and snapshots, plus
stateless conversion helpers between ORM rows and domain objects.

Split from ``kpi_measurement.py`` to keep each file under 300 lines.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from skill.domain.kpi_baseline import KPIBaseline, KPISnapshot
from skill.services.database import Base


# ── ORM Models ──────────────────────────────────────────


class KPIBaselineModel(Base):
    """ORM model for KPI baselines."""

    __tablename__ = "kpi_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String(100), nullable=False)
    site_id = Column(String(100), nullable=False)
    baseline_value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    recorded_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    notes = Column(Text, nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("metric", "site_id", name="uq_baseline_metric_site"),
    )

    def __repr__(self) -> str:
        """Return readable representation."""
        return (
            f"<KPIBaseline(id={self.id}, metric={self.metric}, "
            f"site={self.site_id}, value={self.baseline_value})>"
        )


class KPISnapshotModel(Base):
    """ORM model for KPI snapshots."""

    __tablename__ = "kpi_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric = Column(String(100), nullable=False)
    site_id = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    measured_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    __table_args__ = (
        Index("ix_snapshot_metric_site_date", "metric", "site_id", "measured_at"),
    )

    def __repr__(self) -> str:
        """Return readable representation."""
        return (
            f"<KPISnapshot(id={self.id}, metric={self.metric}, "
            f"site={self.site_id}, value={self.value})>"
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


def baseline_orm_to_domain(row: KPIBaselineModel) -> KPIBaseline:
    """Convert a KPIBaselineModel ORM row to a domain object.

    Args:
        row: SQLAlchemy ORM instance.

    Returns:
        Immutable KPIBaseline domain object.
    """
    return KPIBaseline(
        metric=row.metric,
        site_id=row.site_id,
        baseline_value=row.baseline_value,
        unit=row.unit,
        recorded_at=row.recorded_at,
        period_start=row.period_start,
        period_end=row.period_end,
        notes=row.notes or "",
    )


def snapshot_orm_to_domain(row: KPISnapshotModel) -> KPISnapshot:
    """Convert a KPISnapshotModel ORM row to a domain object.

    Args:
        row: SQLAlchemy ORM instance.

    Returns:
        Immutable KPISnapshot domain object.
    """
    return KPISnapshot(
        metric=row.metric,
        site_id=row.site_id,
        value=row.value,
        unit=row.unit,
        measured_at=row.measured_at,
        period_start=row.period_start,
        period_end=row.period_end,
    )


def baseline_domain_to_orm(baseline: KPIBaseline) -> KPIBaselineModel:
    """Convert a domain KPIBaseline to an ORM row.

    Args:
        baseline: Domain KPI baseline.

    Returns:
        SQLAlchemy ORM instance (not yet committed).
    """
    return KPIBaselineModel(
        metric=baseline.metric,
        site_id=baseline.site_id,
        baseline_value=baseline.baseline_value,
        unit=baseline.unit,
        recorded_at=baseline.recorded_at,
        period_start=baseline.period_start,
        period_end=baseline.period_end,
        notes=baseline.notes,
    )


def snapshot_domain_to_orm(snapshot: KPISnapshot) -> KPISnapshotModel:
    """Convert a domain KPISnapshot to an ORM row.

    Args:
        snapshot: Domain KPI snapshot.

    Returns:
        SQLAlchemy ORM instance (not yet committed).
    """
    return KPISnapshotModel(
        metric=snapshot.metric,
        site_id=snapshot.site_id,
        value=snapshot.value,
        unit=snapshot.unit,
        measured_at=snapshot.measured_at,
        period_start=snapshot.period_start,
        period_end=snapshot.period_end,
    )
