"""
KPIMeasurementService — KPI Baseline & Progress Tracking

Records baselines, snapshots, and computes KPI progress.
WASABI targets: energy ≥8% reduction, material ≥5% improvement,
CO₂ ≥10% reduction.

ORM models and mapping helpers live in ``kpi_measurement_model.py``.
Progress computation helpers live in ``kpi_progress_calc.py``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from skill.domain.exceptions import ConfigurationError
from skill.domain.kpi_baseline import KPIBaseline, KPIProgress, KPISnapshot
from skill.services.database import Base
from skill.services.kpi_measurement_model import (
    KPIBaselineModel,
    KPISnapshotModel,
    baseline_domain_to_orm,
    baseline_orm_to_domain,
    resolve_database_url,
    snapshot_domain_to_orm,
    snapshot_orm_to_domain,
)
from skill.services.kpi_progress_calc import (
    build_progress,
    baseline_to_export_row,
)


logger = logging.getLogger(__name__)


class KPIMeasurementService:
    """Manages KPI baselines, snapshots, and progress computation."""

    def __init__(self, database_url: str | None = None) -> None:
        """Initialize with database URL resolution.

        Args:
            database_url: Explicit DB URL. Falls back to env/memory.
        """
        self._database_url = resolve_database_url(database_url)
        self._engine = None
        self._session_factory = None
        self._initialized = False

    def initialize(self) -> None:
        """Create engine, session factory, and tables."""
        if self._initialized:
            return
        self._engine = create_engine(
            self._database_url, echo=False, future=True,
        )
        self._session_factory = sessionmaker(
            bind=self._engine, expire_on_commit=False,
        )
        Base.metadata.create_all(self._engine)
        self._initialized = True
        logger.info("KPIMeasurementService initialized")

    # ── Baseline CRUD ────────────────────────────────────

    def record_baseline(self, baseline: KPIBaseline) -> int:
        """Upsert a KPI baseline (one per metric+site). Returns row ID."""
        self._ensure_initialized()
        with self._get_session() as session:
            return _upsert_baseline(session, baseline)

    def get_baseline(
        self, metric: str, site_id: str,
    ) -> KPIBaseline | None:
        """Retrieve a single baseline, or None if not found."""
        self._ensure_initialized()
        with self._get_session() as session:
            row = _find_baseline(session, metric, site_id)
            return baseline_orm_to_domain(row) if row else None

    def get_all_baselines(self, site_id: str) -> list[KPIBaseline]:
        """Retrieve all baselines for a site."""
        self._ensure_initialized()
        with self._get_session() as session:
            rows = (
                session.query(KPIBaselineModel)
                .filter(KPIBaselineModel.site_id == site_id)
                .order_by(KPIBaselineModel.metric)
                .all()
            )
            return [baseline_orm_to_domain(r) for r in rows]

    def delete_baseline(self, metric: str, site_id: str) -> bool:
        """Delete a baseline. Returns True if deleted, False if not found."""
        self._ensure_initialized()
        with self._get_session() as session:
            row = _find_baseline(session, metric, site_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    # ── Snapshot CRUD ────────────────────────────────────

    def record_snapshot(self, snapshot: KPISnapshot) -> int:
        """Record a KPI measurement snapshot. Returns row ID."""
        self._ensure_initialized()
        orm_row = snapshot_domain_to_orm(snapshot)
        with self._get_session() as session:
            session.add(orm_row)
            session.commit()
            return orm_row.id

    def get_snapshots(
        self,
        metric: str,
        site_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[KPISnapshot]:
        """Retrieve snapshots in chronological order."""
        self._ensure_initialized()
        with self._get_session() as session:
            return _query_snapshots(
                session, metric, site_id, start_date, end_date,
            )

    def clear_site_data(self, site_id: str) -> tuple[int, int]:
        """Delete all KPI baselines and snapshots for a site.

        Returns:
            Tuple ``(deleted_baselines, deleted_snapshots)``.
        """
        self._ensure_initialized()
        with self._get_session() as session:
            deleted_baselines = (
                session.query(KPIBaselineModel)
                .filter(KPIBaselineModel.site_id == site_id)
                .delete(synchronize_session=False)
            )
            deleted_snapshots = (
                session.query(KPISnapshotModel)
                .filter(KPISnapshotModel.site_id == site_id)
                .delete(synchronize_session=False)
            )
            session.commit()
            logger.info(
                "Cleared KPI data for site=%s (baselines=%d, snapshots=%d)",
                site_id,
                deleted_baselines,
                deleted_snapshots,
            )
            return int(deleted_baselines), int(deleted_snapshots)

    # ── Progress computation ─────────────────────────────

    def compute_progress(
        self, metric: str, site_id: str,
        current_value: float, current_unit: str,
    ) -> KPIProgress:
        """Compute improvement vs baseline. Raises ConfigurationError if none."""
        self._ensure_initialized()
        baseline = self.get_baseline(metric, site_id)
        if baseline is None:
            raise ConfigurationError(
                message=f"No baseline for {metric} at site {site_id}",
                setting=f"baseline.{metric}.{site_id}",
            )
        return build_progress(baseline, current_value, current_unit)

    def get_all_progress(
        self, site_id: str,
        current_values: dict[str, tuple[float, str]],
    ) -> list[KPIProgress]:
        """Compute progress for all baselined metrics at a site."""
        baselines = self.get_all_baselines(site_id)
        return [
            build_progress(bl, *current_values[bl.metric])
            for bl in baselines if bl.metric in current_values
        ]

    # ── Export ────────────────────────────────────────────

    def export_kpi_dataset(self, site_id: str) -> list[dict]:
        """Export anonymized KPI data for WASABI D3.2."""
        baselines = self.get_all_baselines(site_id)
        site_label = "site_1"
        return [
            baseline_to_export_row(bl, site_label=site_label)
            for bl in baselines
        ]

    # ── Private ──────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        """Initialize if not yet done."""
        if not self._initialized:
            self.initialize()

    def _get_session(self) -> Session:
        """Create a new database session."""
        return self._session_factory()

    def close(self) -> None:
        """Dispose engine and reset state."""
        if self._engine:
            self._engine.dispose()
            self._initialized = False
            logger.info("KPIMeasurementService closed")


# ── Module-level DB helpers (stateless) ──────────────────


def _find_baseline(
    session: Session, metric: str, site_id: str,
) -> KPIBaselineModel | None:
    """Find a baseline row by metric and site."""
    return (
        session.query(KPIBaselineModel)
        .filter(KPIBaselineModel.metric == metric)
        .filter(KPIBaselineModel.site_id == site_id)
        .first()
    )


def _upsert_baseline(
    session: Session, baseline: KPIBaseline,
) -> int:
    """Insert or update a baseline row."""
    existing = _find_baseline(session, baseline.metric, baseline.site_id)
    if existing:
        return _update_baseline_row(existing, baseline, session)
    orm_row = baseline_domain_to_orm(baseline)
    session.add(orm_row)
    session.commit()
    return orm_row.id


def _update_baseline_row(
    row: KPIBaselineModel, baseline: KPIBaseline, session: Session,
) -> int:
    """Update existing ORM baseline fields in-place."""
    row.baseline_value = baseline.baseline_value
    row.unit = baseline.unit
    row.recorded_at = baseline.recorded_at
    row.period_start = baseline.period_start
    row.period_end = baseline.period_end
    row.notes = baseline.notes
    session.commit()
    return row.id


def _query_snapshots(
    session: Session, metric: str, site_id: str,
    start_date: date | None, end_date: date | None,
) -> list[KPISnapshot]:
    """Query snapshots with optional date filters."""
    query = (
        session.query(KPISnapshotModel)
        .filter(KPISnapshotModel.metric == metric)
        .filter(KPISnapshotModel.site_id == site_id)
    )
    if start_date is not None:
        query = query.filter(
            KPISnapshotModel.measured_at >= datetime.combine(
                start_date, datetime.min.time(),
            ),
        )
    if end_date is not None:
        query = query.filter(
            KPISnapshotModel.measured_at <= datetime.combine(
                end_date, datetime.max.time(),
            ),
        )
    query = query.order_by(KPISnapshotModel.measured_at)
    return [snapshot_orm_to_domain(r) for r in query.all()]
