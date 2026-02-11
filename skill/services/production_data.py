"""
ProductionDataService — Supplementary Manufacturing Data

CRUD + aggregation service for production data that platforms like
RENERYO cannot provide: production counts, material consumption,
and quality data.

This data enables the 3 WASABI KPIs:
    - energy_per_unit = energy_total / production_count
    - material_efficiency = good / produced × 100
    - co2_per_unit = (energy × factor) / production_count

Database URL resolution (same as SettingsService):
    1. Explicit ``database_url`` parameter
    2. ``AVAROS_DATABASE_URL`` environment variable
    3. ``sqlite:///:memory:`` (in-memory fallback for tests)

ORM model and helpers live in ``production_data_model.py``.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from skill.domain.production import ProductionRecord, ProductionSummary
from skill.services.database import Base
from skill.services.production_data_model import (
    ProductionDataModel,
    apply_filters,
    domain_to_orm,
    orm_to_domain,
    resolve_database_url,
)


logger = logging.getLogger(__name__)


class ProductionDataService:
    """Manages supplementary production data for WASABI KPIs.

    Attributes:
        _database_url: SQLAlchemy connection URL.
        _engine: SQLAlchemy engine.
        _session_factory: Session factory.
    """

    def __init__(self, database_url: str | None = None) -> None:
        """Initialize with database URL resolution.

        Args:
            database_url: Explicit DB URL. Falls back to
                ``AVAROS_DATABASE_URL`` env, then ``sqlite:///:memory:``.
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
        logger.info(
            "ProductionDataService initialized (db=%s)",
            self._database_url,
        )

    # ── CRUD ─────────────────────────────────────────────

    def add_record(self, record: ProductionRecord) -> int:
        """Insert one production record.

        Args:
            record: Validated ProductionRecord domain object.

        Returns:
            Database ID of the inserted record.
        """
        self._ensure_initialized()
        row = domain_to_orm(record)
        with self._get_session() as session:
            session.add(row)
            session.commit()
            return row.id

    def add_records_bulk(
        self, records: list[ProductionRecord],
    ) -> int:
        """Bulk insert multiple records (e.g. from CSV).

        Args:
            records: List of validated ProductionRecord objects.

        Returns:
            Number of records inserted.
        """
        self._ensure_initialized()
        if not records:
            return 0
        rows = [domain_to_orm(r) for r in records]
        with self._get_session() as session:
            session.add_all(rows)
            session.commit()
            return len(rows)

    def get_records(
        self,
        asset_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ProductionRecord]:
        """Query records with optional filters.

        Args:
            asset_id: Filter by asset (exact match).
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of ProductionRecord domain objects.
        """
        self._ensure_initialized()
        with self._get_session() as session:
            query = session.query(ProductionDataModel)
            query = apply_filters(query, asset_id, start_date, end_date)
            query = query.order_by(
                ProductionDataModel.record_date,
                ProductionDataModel.asset_id,
            )
            return [orm_to_domain(row) for row in query.all()]

    def get_records_with_ids(
        self,
        asset_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[tuple[int, ProductionRecord]]:
        """Query records with optional filters, including DB IDs.

        Same as ``get_records`` but returns ``(id, record)`` tuples
        so callers (e.g. the REST API) can reference row IDs without
        accessing ORM internals.

        Args:
            asset_id: Filter by asset (exact match).
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            List of (row_id, ProductionRecord) tuples, ordered by
            date then asset.
        """
        self._ensure_initialized()
        with self._get_session() as session:
            query = session.query(ProductionDataModel)
            query = apply_filters(query, asset_id, start_date, end_date)
            query = query.order_by(
                ProductionDataModel.record_date,
                ProductionDataModel.asset_id,
            )
            return [
                (row.id, orm_to_domain(row)) for row in query.all()
            ]

    def delete_record(self, record_id: int) -> bool:
        """Delete a single record by ID.

        Args:
            record_id: Database row ID.

        Returns:
            True if deleted, False if not found.
        """
        self._ensure_initialized()
        with self._get_session() as session:
            row = session.get(ProductionDataModel, record_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def delete_records_by_date_range(
        self,
        asset_id: str,
        start_date: date,
        end_date: date,
    ) -> int:
        """Delete records in a date range for an asset.

        Args:
            asset_id: Asset identifier.
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            Number of records deleted.
        """
        self._ensure_initialized()
        with self._get_session() as session:
            count = (
                session.query(ProductionDataModel)
                .filter(ProductionDataModel.asset_id == asset_id)
                .filter(ProductionDataModel.record_date >= start_date)
                .filter(ProductionDataModel.record_date <= end_date)
                .delete(synchronize_session="fetch")
            )
            session.commit()
            return count

    # ── Aggregation ──────────────────────────────────────

    def get_production_summary(
        self,
        asset_id: str,
        start_date: date,
        end_date: date,
    ) -> ProductionSummary:
        """Aggregate production data for a period.

        Args:
            asset_id: Asset identifier.
            start_date: Inclusive start date.
            end_date: Inclusive end date.

        Returns:
            ProductionSummary with totals and record count.
        """
        self._ensure_initialized()
        with self._get_session() as session:
            row = (
                session.query(
                    func.coalesce(
                        func.sum(ProductionDataModel.production_count), 0,
                    ).label("total_produced"),
                    func.coalesce(
                        func.sum(ProductionDataModel.good_count), 0,
                    ).label("total_good"),
                    func.coalesce(
                        func.sum(ProductionDataModel.material_consumed_kg),
                        0.0,
                    ).label("total_material_kg"),
                    func.count(ProductionDataModel.id).label("record_count"),
                )
                .filter(ProductionDataModel.asset_id == asset_id)
                .filter(ProductionDataModel.record_date >= start_date)
                .filter(ProductionDataModel.record_date <= end_date)
                .one()
            )
            return ProductionSummary(
                total_produced=int(row.total_produced),
                total_good=int(row.total_good),
                total_material_kg=float(row.total_material_kg),
                record_count=int(row.record_count),
            )

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
            logger.info("ProductionDataService closed")
