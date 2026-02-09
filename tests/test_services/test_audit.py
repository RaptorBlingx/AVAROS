"""
AuditLogger Test Suite

Covers all public methods of AuditLogger:
    - Initialization (in-memory, with path, idempotent)
    - log_query (full fields, minimal fields)
    - get_logs_for_asset (filters by asset, days, query_type)
    - get_log_by_query_id (found, not found)
    - get_recent_logs (ordering, limit)
    - cleanup_old_logs (retention period)
    - get_statistics (structure, counts)
    - close (no errors)
    - AuditLogEntry immutability

All tests use in-memory SQLite — no file I/O.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from skill.services.audit import AuditLogger, AuditLogEntry, AuditLogModel


# ── Fixtures ────────────────────────────────────────────


@pytest.fixture
def logger() -> AuditLogger:
    """In-memory AuditLogger, initialized and ready."""
    audit = AuditLogger()
    audit.initialize()
    yield audit
    audit.close()


@pytest.fixture
def uninitialized_logger() -> AuditLogger:
    """AuditLogger before initialize() is called."""
    return AuditLogger()


def _insert_old_log(
    audit: AuditLogger,
    query_id: str,
    timestamp: datetime,
    asset_id: str = "Line-1",
    query_type: str = "get_kpi",
    metric: str = "oee",
    user_role: str = "operator",
) -> None:
    """Insert a log entry with a specific timestamp (bypasses utcnow)."""
    with audit._get_session() as session:
        entry = AuditLogModel(
            timestamp=timestamp,
            query_id=query_id,
            user_role=user_role,
            query_type=query_type,
            metric=metric,
            asset_id=asset_id,
        )
        session.add(entry)
        session.commit()


# ══════════════════════════════════════════════════════════
# 1. Initialization & Lifecycle
# ══════════════════════════════════════════════════════════


class TestAuditLoggerInit:
    """Tests for __init__(), initialize(), and close()."""

    def test_init_default_sets_in_memory(self) -> None:
        """Default construction uses in-memory database."""
        audit = AuditLogger()
        assert audit._database_url == "sqlite:///:memory:"
        assert audit._initialized is False

    def test_init_with_database_url_stores_url(self) -> None:
        """Construction with database_url stores the URL."""
        url = "postgresql://avaros:avaros@localhost:5432/avaros"
        audit = AuditLogger(database_url=url)
        assert audit._database_url == url

    def test_initialize_creates_tables(self, logger: AuditLogger) -> None:
        """initialize() puts logger into ready state."""
        assert logger._initialized is True
        assert logger._engine is not None
        assert logger._session_factory is not None

    def test_initialize_idempotent(self, logger: AuditLogger) -> None:
        """Calling initialize() twice does not recreate engine."""
        engine_before = logger._engine
        logger.initialize()
        assert logger._engine is engine_before

    def test_initialize_with_database_url(self) -> None:
        """initialize() with an explicit SQLite URL creates the engine."""
        audit = AuditLogger(database_url="sqlite:///:memory:")
        audit.initialize()
        assert audit._initialized is True
        assert audit._engine is not None
        audit.close()

    def test_init_reads_env_var_fallback(self, monkeypatch) -> None:
        """When no explicit URL, reads AVAROS_DATABASE_URL env var."""
        monkeypatch.setenv(
            "AVAROS_DATABASE_URL",
            "postgresql://u:p@host:5432/db",
        )
        audit = AuditLogger()
        assert audit._database_url == "postgresql://u:p@host:5432/db"

    def test_init_explicit_url_overrides_env_var(self, monkeypatch) -> None:
        """Explicit database_url takes precedence over env var."""
        monkeypatch.setenv(
            "AVAROS_DATABASE_URL",
            "postgresql://u:p@host:5432/db",
        )
        audit = AuditLogger(database_url="sqlite:///:memory:")
        assert audit._database_url == "sqlite:///:memory:"

    def test_close_resets_initialized_flag(self, logger: AuditLogger) -> None:
        """close() disposes engine and resets state."""
        logger.close()
        assert logger._initialized is False

    def test_close_on_uninitialized_no_error(
        self, uninitialized_logger: AuditLogger
    ) -> None:
        """close() on an uninitialized logger does not raise."""
        uninitialized_logger.close()  # should not raise


# ══════════════════════════════════════════════════════════
# 2. log_query
# ══════════════════════════════════════════════════════════


class TestLogQuery:
    """Tests for log_query()."""

    def test_log_query_all_fields_roundtrip(self, logger: AuditLogger) -> None:
        """Log with all fields stores and retrieves correctly."""
        logger.log_query(
            query_id="q-001",
            user_role="engineer",
            query_type="get_kpi",
            metric="energy_per_unit",
            asset_id="Line-1",
            recommendation_id="rec-100",
            response_summary="Energy is 2.3 kWh",
            metadata={"source": "mock"},
        )

        entry = logger.get_log_by_query_id("q-001")
        assert entry is not None
        assert entry.query_id == "q-001"
        assert entry.user_role == "engineer"
        assert entry.query_type == "get_kpi"
        assert entry.metric == "energy_per_unit"
        assert entry.asset_id == "Line-1"
        assert entry.recommendation_id == "rec-100"
        assert entry.response_summary == "Energy is 2.3 kWh"
        assert entry.metadata == {"source": "mock"}
        assert isinstance(entry.timestamp, datetime)

    def test_log_query_minimal_fields_stores_none(
        self, logger: AuditLogger
    ) -> None:
        """Log with only required fields stores None for optional ones."""
        logger.log_query(
            query_id="q-002",
            user_role="operator",
            query_type="compare",
            metric="oee",
            asset_id="Line-2",
        )

        entry = logger.get_log_by_query_id("q-002")
        assert entry is not None
        assert entry.recommendation_id is None
        assert entry.response_summary is None
        assert entry.metadata is None

    def test_log_query_auto_initializes(
        self, uninitialized_logger: AuditLogger
    ) -> None:
        """log_query on uninitialized logger triggers auto-init."""
        uninitialized_logger.log_query(
            query_id="q-auto",
            user_role="admin",
            query_type="get_kpi",
            metric="scrap_rate",
            asset_id="Line-1",
        )

        entry = uninitialized_logger.get_log_by_query_id("q-auto")
        assert entry is not None
        assert uninitialized_logger._initialized is True
        uninitialized_logger.close()

    def test_log_query_multiple_entries_stored(
        self, logger: AuditLogger
    ) -> None:
        """Multiple calls store independent records."""
        for i in range(5):
            logger.log_query(
                query_id=f"q-multi-{i}",
                user_role="operator",
                query_type="get_kpi",
                metric="oee",
                asset_id="Line-1",
            )

        logs = logger.get_recent_logs(limit=10)
        assert len(logs) == 5


# ══════════════════════════════════════════════════════════
# 3. get_logs_for_asset
# ══════════════════════════════════════════════════════════


class TestGetLogsForAsset:
    """Tests for get_logs_for_asset()."""

    def test_get_logs_for_asset_returns_matching(
        self, logger: AuditLogger
    ) -> None:
        """Returns only logs for the requested asset."""
        logger.log_query(
            query_id="q-a1",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )
        logger.log_query(
            query_id="q-a2",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-2",
        )

        logs = logger.get_logs_for_asset("Line-1")
        assert len(logs) == 1
        assert logs[0].asset_id == "Line-1"

    def test_get_logs_for_asset_empty_when_no_match(
        self, logger: AuditLogger
    ) -> None:
        """Returns empty list when asset has no logs."""
        logger.log_query(
            query_id="q-nm",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )

        logs = logger.get_logs_for_asset("NONEXISTENT")
        assert logs == []

    def test_get_logs_for_asset_respects_days_filter(
        self, logger: AuditLogger
    ) -> None:
        """Only returns logs within the days window."""
        # Insert recent log (now)
        logger.log_query(
            query_id="q-recent",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )
        # Insert old log (15 days ago)
        _insert_old_log(
            logger,
            query_id="q-old",
            timestamp=datetime.utcnow() - timedelta(days=15),
            asset_id="Line-1",
        )

        # 7-day window should only get the recent one
        logs = logger.get_logs_for_asset("Line-1", days=7)
        assert len(logs) == 1
        assert logs[0].query_id == "q-recent"

        # 30-day window should get both
        logs_wide = logger.get_logs_for_asset("Line-1", days=30)
        assert len(logs_wide) == 2

    def test_get_logs_for_asset_filters_by_query_type(
        self, logger: AuditLogger
    ) -> None:
        """Filters logs by query_type when provided."""
        logger.log_query(
            query_id="q-kpi",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )
        logger.log_query(
            query_id="q-cmp",
            user_role="op",
            query_type="compare",
            metric="oee",
            asset_id="Line-1",
        )

        logs = logger.get_logs_for_asset(
            "Line-1", query_type="compare"
        )
        assert len(logs) == 1
        assert logs[0].query_type == "compare"

    def test_get_logs_for_asset_descending_order(
        self, logger: AuditLogger
    ) -> None:
        """Logs are returned newest first."""
        _insert_old_log(
            logger,
            query_id="q-older",
            timestamp=datetime.utcnow() - timedelta(hours=2),
            asset_id="Line-1",
        )
        _insert_old_log(
            logger,
            query_id="q-newer",
            timestamp=datetime.utcnow() - timedelta(hours=1),
            asset_id="Line-1",
        )

        logs = logger.get_logs_for_asset("Line-1")
        assert logs[0].query_id == "q-newer"
        assert logs[1].query_id == "q-older"


# ══════════════════════════════════════════════════════════
# 4. get_log_by_query_id
# ══════════════════════════════════════════════════════════


class TestGetLogByQueryId:
    """Tests for get_log_by_query_id()."""

    def test_get_log_by_query_id_found(self, logger: AuditLogger) -> None:
        """Returns the matching AuditLogEntry."""
        logger.log_query(
            query_id="q-find-me",
            user_role="planner",
            query_type="get_trend",
            metric="scrap_rate",
            asset_id="Line-3",
        )

        entry = logger.get_log_by_query_id("q-find-me")
        assert entry is not None
        assert entry.query_id == "q-find-me"
        assert entry.user_role == "planner"
        assert entry.query_type == "get_trend"

    def test_get_log_by_query_id_not_found_returns_none(
        self, logger: AuditLogger
    ) -> None:
        """Returns None when query_id does not exist."""
        entry = logger.get_log_by_query_id("nonexistent-id")
        assert entry is None


# ══════════════════════════════════════════════════════════
# 5. get_recent_logs
# ══════════════════════════════════════════════════════════


class TestGetRecentLogs:
    """Tests for get_recent_logs()."""

    def test_get_recent_logs_returns_all_within_limit(
        self, logger: AuditLogger
    ) -> None:
        """Returns up to `limit` logs."""
        for i in range(5):
            logger.log_query(
                query_id=f"q-rl-{i}",
                user_role="op",
                query_type="get_kpi",
                metric="oee",
                asset_id="Line-1",
            )

        logs = logger.get_recent_logs(limit=3)
        assert len(logs) == 3

    def test_get_recent_logs_fewer_than_limit(
        self, logger: AuditLogger
    ) -> None:
        """Returns all records when fewer than limit exist."""
        logger.log_query(
            query_id="q-only",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )

        logs = logger.get_recent_logs(limit=100)
        assert len(logs) == 1

    def test_get_recent_logs_descending_order(
        self, logger: AuditLogger
    ) -> None:
        """Newest log appears first."""
        _insert_old_log(
            logger,
            query_id="q-first",
            timestamp=datetime.utcnow() - timedelta(hours=2),
        )
        _insert_old_log(
            logger,
            query_id="q-second",
            timestamp=datetime.utcnow() - timedelta(hours=1),
        )

        logs = logger.get_recent_logs(limit=10)
        assert logs[0].query_id == "q-second"
        assert logs[1].query_id == "q-first"

    def test_get_recent_logs_empty_database(
        self, logger: AuditLogger
    ) -> None:
        """Returns empty list when no logs exist."""
        logs = logger.get_recent_logs()
        assert logs == []


# ══════════════════════════════════════════════════════════
# 6. cleanup_old_logs
# ══════════════════════════════════════════════════════════


class TestCleanupOldLogs:
    """Tests for cleanup_old_logs()."""

    def test_cleanup_removes_old_logs_returns_count(
        self, logger: AuditLogger
    ) -> None:
        """Deletes logs older than retention period and returns count."""
        # Insert a log 400 days ago
        _insert_old_log(
            logger,
            query_id="q-ancient",
            timestamp=datetime.utcnow() - timedelta(days=400),
        )
        # Insert a recent log
        logger.log_query(
            query_id="q-fresh",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )

        deleted = logger.cleanup_old_logs(retention_days=365)
        assert deleted == 1

        # Only the fresh one remains
        logs = logger.get_recent_logs()
        assert len(logs) == 1
        assert logs[0].query_id == "q-fresh"

    def test_cleanup_no_old_logs_returns_zero(
        self, logger: AuditLogger
    ) -> None:
        """Returns 0 when nothing to clean up."""
        logger.log_query(
            query_id="q-new",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )

        deleted = logger.cleanup_old_logs(retention_days=365)
        assert deleted == 0

    def test_cleanup_respects_custom_retention(
        self, logger: AuditLogger
    ) -> None:
        """Custom retention_days value is honored."""
        # Insert log 10 days ago
        _insert_old_log(
            logger,
            query_id="q-ten-days",
            timestamp=datetime.utcnow() - timedelta(days=10),
        )

        # 30-day retention → should NOT delete
        deleted_30 = logger.cleanup_old_logs(retention_days=30)
        assert deleted_30 == 0

        # 5-day retention → SHOULD delete
        deleted_5 = logger.cleanup_old_logs(retention_days=5)
        assert deleted_5 == 1


# ══════════════════════════════════════════════════════════
# 7. get_statistics
# ══════════════════════════════════════════════════════════


class TestGetStatistics:
    """Tests for get_statistics()."""

    def test_get_statistics_structure(self, logger: AuditLogger) -> None:
        """Returns dict with expected keys."""
        stats = logger.get_statistics()
        assert "period_days" in stats
        assert "total_queries" in stats
        assert "queries_by_type" in stats
        assert "top_assets" in stats

    def test_get_statistics_empty_database(
        self, logger: AuditLogger
    ) -> None:
        """Empty database returns zero counts."""
        stats = logger.get_statistics()
        assert stats["total_queries"] == 0
        assert stats["queries_by_type"] == {}
        assert stats["top_assets"] == {}

    def test_get_statistics_correct_counts(
        self, logger: AuditLogger
    ) -> None:
        """Counts match the number of logged queries."""
        logger.log_query(
            query_id="q-s1",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )
        logger.log_query(
            query_id="q-s2",
            user_role="op",
            query_type="get_kpi",
            metric="energy_per_unit",
            asset_id="Line-1",
        )
        logger.log_query(
            query_id="q-s3",
            user_role="eng",
            query_type="compare",
            metric="oee",
            asset_id="Line-2",
        )

        stats = logger.get_statistics(days=30)
        assert stats["total_queries"] == 3
        assert stats["queries_by_type"]["get_kpi"] == 2
        assert stats["queries_by_type"]["compare"] == 1
        assert stats["top_assets"]["Line-1"] == 2
        assert stats["top_assets"]["Line-2"] == 1

    def test_get_statistics_respects_days_window(
        self, logger: AuditLogger
    ) -> None:
        """Only counts logs within the specified days window."""
        logger.log_query(
            query_id="q-recent-stat",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )
        _insert_old_log(
            logger,
            query_id="q-old-stat",
            timestamp=datetime.utcnow() - timedelta(days=60),
        )

        stats = logger.get_statistics(days=30)
        assert stats["total_queries"] == 1
        assert stats["period_days"] == 30


# ══════════════════════════════════════════════════════════
# 8. AuditLogEntry Immutability
# ══════════════════════════════════════════════════════════


class TestAuditLogEntry:
    """Tests for the AuditLogEntry frozen dataclass."""

    def test_audit_log_entry_creation(self) -> None:
        """AuditLogEntry can be created with all fields."""
        now = datetime.utcnow()
        entry = AuditLogEntry(
            timestamp=now,
            query_id="q-test",
            user_role="operator",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
            recommendation_id="rec-1",
            response_summary="OEE is 85%",
            metadata={"key": "val"},
        )
        assert entry.query_id == "q-test"
        assert entry.timestamp == now

    def test_audit_log_entry_defaults(self) -> None:
        """Optional fields default to None."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow(),
            query_id="q-def",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )
        assert entry.recommendation_id is None
        assert entry.response_summary is None
        assert entry.metadata is None

    def test_audit_log_entry_immutable(self) -> None:
        """Frozen dataclass rejects attribute mutation."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow(),
            query_id="q-imm",
            user_role="op",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
        )
        with pytest.raises(FrozenInstanceError):
            entry.query_id = "changed"  # type: ignore[misc]
