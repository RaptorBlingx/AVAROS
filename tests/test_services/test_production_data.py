"""
ProductionDataService Test Suite

Covers:
    - CRUD: add, get, delete single records
    - Bulk insert from parsed CSV
    - Query with filters (asset_id, date range)
    - Aggregation: get_production_summary correct math
    - Empty results (no data for period)
    - SQLite in-memory for test isolation
"""

from __future__ import annotations

from datetime import date

import pytest

from skill.domain.production import ProductionRecord, ProductionSummary
from skill.services.production_data import ProductionDataService


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def service() -> ProductionDataService:
    """In-memory ProductionDataService, initialized and ready."""
    svc = ProductionDataService(database_url="sqlite:///:memory:")
    svc.initialize()
    yield svc
    svc.close()


@pytest.fixture
def sample_record() -> ProductionRecord:
    """Standard test record."""
    return ProductionRecord(
        record_date=date(2026, 1, 15),
        asset_id="Line-1",
        production_count=500,
        good_count=485,
        material_consumed_kg=120.5,
        shift="morning",
        batch_id="B-2026-001",
        notes="Normal operation",
    )


@pytest.fixture
def sample_records() -> list[ProductionRecord]:
    """Multiple test records for bulk/filter tests."""
    return [
        ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-1",
            production_count=500,
            good_count=485,
            material_consumed_kg=120.5,
            shift="morning",
        ),
        ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-1",
            production_count=480,
            good_count=470,
            material_consumed_kg=115.0,
            shift="afternoon",
        ),
        ProductionRecord(
            record_date=date(2026, 1, 16),
            asset_id="Line-1",
            production_count=520,
            good_count=510,
            material_consumed_kg=125.0,
            shift="morning",
        ),
        ProductionRecord(
            record_date=date(2026, 1, 15),
            asset_id="Line-2",
            production_count=600,
            good_count=590,
            material_consumed_kg=140.0,
            shift="morning",
        ),
    ]


# ══════════════════════════════════════════════════════════
# Single Record CRUD
# ══════════════════════════════════════════════════════════


class TestSingleRecordCrud:
    """Add, get, delete individual records."""

    def test_add_record_returns_id(
        self, service: ProductionDataService, sample_record: ProductionRecord,
    ) -> None:
        """add_record returns positive integer ID."""
        record_id = service.add_record(sample_record)
        assert isinstance(record_id, int)
        assert record_id > 0

    def test_get_records_after_add(
        self, service: ProductionDataService, sample_record: ProductionRecord,
    ) -> None:
        """Added record appears in get_records result."""
        service.add_record(sample_record)
        records = service.get_records()
        assert len(records) == 1
        assert records[0].asset_id == "Line-1"
        assert records[0].production_count == 500

    def test_delete_record_success(
        self, service: ProductionDataService, sample_record: ProductionRecord,
    ) -> None:
        """delete_record returns True and removes record."""
        record_id = service.add_record(sample_record)
        assert service.delete_record(record_id) is True
        assert service.get_records() == []

    def test_delete_record_not_found(
        self, service: ProductionDataService,
    ) -> None:
        """delete_record returns False when ID doesn't exist."""
        assert service.delete_record(9999) is False

    def test_preserves_all_fields(
        self, service: ProductionDataService, sample_record: ProductionRecord,
    ) -> None:
        """All domain fields round-trip through DB correctly."""
        service.add_record(sample_record)
        records = service.get_records()
        r = records[0]
        assert r.record_date == date(2026, 1, 15)
        assert r.shift == "morning"
        assert r.batch_id == "B-2026-001"
        assert r.notes == "Normal operation"
        assert r.material_consumed_kg == pytest.approx(120.5)


# ══════════════════════════════════════════════════════════
# Bulk Insert
# ══════════════════════════════════════════════════════════


class TestBulkInsert:
    """Bulk insert operations."""

    def test_bulk_insert_count(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Bulk insert returns correct count."""
        count = service.add_records_bulk(sample_records)
        assert count == 4

    def test_bulk_insert_empty_list(
        self, service: ProductionDataService,
    ) -> None:
        """Empty list inserts nothing."""
        assert service.add_records_bulk([]) == 0

    def test_bulk_insert_all_persisted(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """All bulk-inserted records are retrievable."""
        service.add_records_bulk(sample_records)
        records = service.get_records()
        assert len(records) == 4


# ══════════════════════════════════════════════════════════
# Filtered Queries
# ══════════════════════════════════════════════════════════


class TestFilteredQueries:
    """Query with asset_id and date range filters."""

    def test_filter_by_asset_id(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Filter by asset returns only matching records."""
        service.add_records_bulk(sample_records)
        records = service.get_records(asset_id="Line-2")
        assert len(records) == 1
        assert records[0].asset_id == "Line-2"

    def test_filter_by_date_range(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Date range filter inclusive on both ends."""
        service.add_records_bulk(sample_records)
        records = service.get_records(
            start_date=date(2026, 1, 16),
            end_date=date(2026, 1, 16),
        )
        assert len(records) == 1
        assert records[0].record_date == date(2026, 1, 16)

    def test_filter_combined(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Combined asset + date filter."""
        service.add_records_bulk(sample_records)
        records = service.get_records(
            asset_id="Line-1",
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 15),
        )
        assert len(records) == 2
        assert all(r.asset_id == "Line-1" for r in records)

    def test_no_results(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Filters returning no matches yield empty list."""
        service.add_records_bulk(sample_records)
        records = service.get_records(asset_id="Nonexistent")
        assert records == []


# ══════════════════════════════════════════════════════════
# Delete by Date Range
# ══════════════════════════════════════════════════════════


class TestDeleteByDateRange:
    """Delete records in a date range for an asset."""

    def test_delete_by_date_range(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Delete removes matching records and returns count."""
        service.add_records_bulk(sample_records)
        count = service.delete_records_by_date_range(
            asset_id="Line-1",
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 15),
        )
        assert count == 2
        remaining = service.get_records()
        assert len(remaining) == 2

    def test_delete_no_match(
        self, service: ProductionDataService,
    ) -> None:
        """Delete with no matching records returns 0."""
        count = service.delete_records_by_date_range(
            asset_id="Line-1",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
        )
        assert count == 0


# ══════════════════════════════════════════════════════════
# Aggregation
# ══════════════════════════════════════════════════════════


class TestAggregation:
    """get_production_summary aggregation tests."""

    def test_summary_single_record(
        self, service: ProductionDataService, sample_record: ProductionRecord,
    ) -> None:
        """Summary for one record matches its values."""
        service.add_record(sample_record)
        summary = service.get_production_summary(
            asset_id="Line-1",
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 15),
        )
        assert summary.total_produced == 500
        assert summary.total_good == 485
        assert summary.total_material_kg == pytest.approx(120.5)
        assert summary.record_count == 1

    def test_summary_multiple_records(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Summary aggregates across multiple records."""
        service.add_records_bulk(sample_records)
        summary = service.get_production_summary(
            asset_id="Line-1",
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 16),
        )
        # 500 + 480 + 520 = 1500
        assert summary.total_produced == 1500
        # 485 + 470 + 510 = 1465
        assert summary.total_good == 1465
        # 120.5 + 115.0 + 125.0 = 360.5
        assert summary.total_material_kg == pytest.approx(360.5)
        assert summary.record_count == 3

    def test_summary_empty_period(
        self, service: ProductionDataService,
    ) -> None:
        """No data for period returns zero summary."""
        summary = service.get_production_summary(
            asset_id="Line-1",
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
        )
        assert summary.total_produced == 0
        assert summary.total_good == 0
        assert summary.total_material_kg == pytest.approx(0.0)
        assert summary.record_count == 0

    def test_summary_filters_by_asset(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Summary only includes the specified asset."""
        service.add_records_bulk(sample_records)
        summary = service.get_production_summary(
            asset_id="Line-2",
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 16),
        )
        assert summary.total_produced == 600
        assert summary.record_count == 1

    def test_summary_material_efficiency(
        self, service: ProductionDataService,
        sample_records: list[ProductionRecord],
    ) -> None:
        """Material efficiency computed via the summary property."""
        service.add_records_bulk(sample_records)
        summary = service.get_production_summary(
            asset_id="Line-1",
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 16),
        )
        # 1465 / 1500 * 100 = 97.666... → 97.7
        assert summary.material_efficiency == pytest.approx(97.7, abs=0.1)


# ══════════════════════════════════════════════════════════
# Initialization
# ══════════════════════════════════════════════════════════


class TestInitialization:
    """Service initialization and lifecycle."""

    def test_auto_initialize(self) -> None:
        """Service auto-initializes on first operation."""
        svc = ProductionDataService(database_url="sqlite:///:memory:")
        # No manual initialize() call
        records = svc.get_records()
        assert records == []

    def test_idempotent_initialize(
        self, service: ProductionDataService,
    ) -> None:
        """Calling initialize() twice doesn't error."""
        service.initialize()  # already initialized in fixture
        records = service.get_records()
        assert records == []

    def test_close_and_reopen(self) -> None:
        """Service can be closed and re-initialized."""
        svc = ProductionDataService(database_url="sqlite:///:memory:")
        svc.initialize()
        svc.close()
        # Re-initialize after close
        svc.initialize()
        records = svc.get_records()
        assert records == []
