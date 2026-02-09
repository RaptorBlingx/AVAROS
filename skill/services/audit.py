"""
AuditLogger - GDPR-Compliant Audit Trail Service

Maintains immutable audit logs for all manufacturing queries and recommendations.
Required for GDPR compliance and trustworthy AI practices.

Features:
    - Immutable audit records stored in database
    - No personal data logged (only user roles)
    - Automatic retention policy (90 days operational, 1 year audit)
    - Query traceability via unique IDs

URL resolution order:
    1. Explicit ``database_url`` parameter
    2. ``AVAROS_DATABASE_URL`` environment variable
    3. ``sqlite:///:memory:`` (in-memory fallback for tests)

Usage:
    # Production (reads AVAROS_DATABASE_URL env var)
    audit = AuditLogger()

    # Explicit URL
    audit = AuditLogger(
        database_url="postgresql://avaros:avaros@localhost:5432/avaros"
    )

    audit.log_query(
        query_id="q-abc123",
        user_role="operator",
        query_type="get_kpi",
        metric="energy_per_unit",
        asset_id="Line-1",
        recommendation_id="rec-xyz789"
    )
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, Column, String, DateTime, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session


logger = logging.getLogger(__name__)

Base = declarative_base()


class AuditLogModel(Base):
    """
    SQLAlchemy model for audit logs.
    
    Immutable records of all queries and recommendations.
    """
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    query_id = Column(String(50), nullable=False, index=True, unique=True)
    user_role = Column(String(50), nullable=False)  # NOT personal identifier
    query_type = Column(String(50), nullable=False, index=True)
    metric = Column(String(100), nullable=False)
    asset_id = Column(String(100), nullable=False, index=True)
    recommendation_id = Column(String(50), nullable=True)
    response_summary = Column(String(500), nullable=True)
    query_metadata = Column(JSON, nullable=True)  # Renamed from 'metadata' (SQLAlchemy reserved)
    
    def __repr__(self) -> str:
        return f"<AuditLog(query_id={self.query_id}, type={self.query_type})>"


@dataclass(frozen=True)
class AuditLogEntry:
    """
    Immutable audit log entry.
    
    Attributes:
        timestamp: When the query was executed
        query_id: Unique identifier for traceability
        user_role: User role (NOT personal identifier)
        query_type: Type of query (get_kpi, compare, etc.)
        metric: Canonical metric queried
        asset_id: Asset identifier
        recommendation_id: ID linking to recommendation
        response_summary: Brief summary of response
        metadata: Additional context (optional)
    """
    
    timestamp: datetime
    query_id: str
    user_role: str
    query_type: str
    metric: str
    asset_id: str
    recommendation_id: str | None = None
    response_summary: str | None = None
    metadata: dict[str, Any] | None = None


class AuditLogger:
    """
    GDPR-compliant audit logging service.
    
    Maintains immutable records of all manufacturing queries for:
    - Compliance (GDPR Article 30)
    - Trustworthy AI traceability
    - Security auditing
    - Performance analysis
    
    Data Minimization:
        - NO personal user identifiers
        - Only user roles logged (operator, engineer, planner)
        - Pseudonymized query IDs
    
    Retention:
        - Operational logs: 90 days
        - Audit logs: 1 year minimum
    
    Example:
        audit = AuditLogger()  # reads AVAROS_DATABASE_URL
        
        audit.log_query(
            query_id="q-abc123",
            user_role="operator",
            query_type="get_kpi",
            metric="oee",
            asset_id="Line-1",
            recommendation_id="rec-xyz"
        )
        
        # Retrieve audit trail
        logs = audit.get_logs_for_asset("Line-1", days=7)
    """
    
    def __init__(self, database_url: str | None = None) -> None:
        """
        Initialize audit logger.
        
        Args:
            database_url: SQLAlchemy database URL.  Falls back to
                ``AVAROS_DATABASE_URL`` env var, then
                ``sqlite:///:memory:`` for tests.
        """
        self._database_url = self._resolve_database_url(database_url)
        self._engine = None
        self._session_factory = None
        self._initialized = False
    
    @staticmethod
    def _resolve_database_url(explicit_url: str | None) -> str:
        """Determine the database URL from explicit value, env, or default.

        Args:
            explicit_url: URL passed directly to the constructor.

        Returns:
            Resolved SQLAlchemy database URL.
        """
        if explicit_url:
            return explicit_url
        return os.environ.get(
            "AVAROS_DATABASE_URL", "sqlite:///:memory:"
        )

    def initialize(self) -> None:
        """
        Initialize the audit log database.
        
        Creates tables if they don't exist.
        Called automatically on first access.
        """
        if self._initialized:
            return
        
        self._engine = create_engine(
            self._database_url, echo=False, future=True,
        )
        self._session_factory = sessionmaker(
            bind=self._engine, expire_on_commit=False,
        )
        
        # Create tables
        Base.metadata.create_all(self._engine)
        
        self._initialized = True
        logger.info("AuditLogger initialized (db=%s)", self._database_url)
    
    def log_query(
        self,
        query_id: str,
        user_role: str,
        query_type: str,
        metric: str,
        asset_id: str,
        recommendation_id: str | None = None,
        response_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a manufacturing query.
        
        Args:
            query_id: Unique query identifier
            user_role: User role (operator, engineer, planner, admin)
            query_type: Query type (get_kpi, compare, get_trend, etc.)
            metric: Canonical metric name
            asset_id: Asset identifier
            recommendation_id: Optional recommendation ID
            response_summary: Brief response summary
            metadata: Additional context
            
        Note:
            This creates an IMMUTABLE record that cannot be modified.
        """
        self._ensure_initialized()
        
        with self._get_session() as session:
            log_entry = AuditLogModel(
                timestamp=datetime.utcnow(),
                query_id=query_id,
                user_role=user_role,
                query_type=query_type,
                metric=metric,
                asset_id=asset_id,
                recommendation_id=recommendation_id,
                response_summary=response_summary,
                query_metadata=metadata,
            )
            
            session.add(log_entry)
            session.commit()
        
        logger.debug(
            "AUDIT: query_id=%s, type=%s, metric=%s, asset=%s",
            query_id, query_type, metric, asset_id
        )
    
    def get_logs_for_asset(
        self,
        asset_id: str,
        days: int = 7,
        query_type: str | None = None,
    ) -> list[AuditLogEntry]:
        """
        Retrieve audit logs for a specific asset.
        
        Args:
            asset_id: Asset identifier
            days: Number of days to look back
            query_type: Optional filter by query type
            
        Returns:
            List of audit log entries
        """
        self._ensure_initialized()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with self._get_session() as session:
            query = session.query(AuditLogModel).filter(
                AuditLogModel.asset_id == asset_id,
                AuditLogModel.timestamp >= cutoff_date
            )
            
            if query_type:
                query = query.filter(AuditLogModel.query_type == query_type)
            
            logs = query.order_by(AuditLogModel.timestamp.desc()).all()
            
            return [
                AuditLogEntry(
                    timestamp=log.timestamp,
                    query_id=log.query_id,
                    user_role=log.user_role,
                    query_type=log.query_type,
                    metric=log.metric,
                    asset_id=log.asset_id,
                    recommendation_id=log.recommendation_id,
                    response_summary=log.response_summary,
                    metadata=log.query_metadata,
                )
                for log in logs
            ]
    
    def get_log_by_query_id(self, query_id: str) -> AuditLogEntry | None:
        """
        Retrieve a specific audit log by query ID.
        
        Args:
            query_id: Unique query identifier
            
        Returns:
            Audit log entry or None if not found
        """
        self._ensure_initialized()
        
        with self._get_session() as session:
            log = session.query(AuditLogModel).filter_by(query_id=query_id).first()
            
            if not log:
                return None
            
            return AuditLogEntry(
                timestamp=log.timestamp,
                query_id=log.query_id,
                user_role=log.user_role,
                query_type=log.query_type,
                metric=log.metric,
                asset_id=log.asset_id,
                recommendation_id=log.recommendation_id,
                response_summary=log.response_summary,
                metadata=log.query_metadata,
            )
    
    def get_recent_logs(self, limit: int = 100) -> list[AuditLogEntry]:
        """
        Retrieve most recent audit logs.
        
        Args:
            limit: Maximum number of logs to return
            
        Returns:
            List of audit log entries
        """
        self._ensure_initialized()
        
        with self._get_session() as session:
            logs = (
                session.query(AuditLogModel)
                .order_by(AuditLogModel.timestamp.desc())
                .limit(limit)
                .all()
            )
            
            return [
                AuditLogEntry(
                    timestamp=log.timestamp,
                    query_id=log.query_id,
                    user_role=log.user_role,
                    query_type=log.query_type,
                    metric=log.metric,
                    asset_id=log.asset_id,
                    recommendation_id=log.recommendation_id,
                    response_summary=log.response_summary,
                    metadata=log.query_metadata,
                )
                for log in logs
            ]
    
    def cleanup_old_logs(self, retention_days: int = 365) -> int:
        """
        Remove audit logs older than retention period.
        
        Args:
            retention_days: Number of days to retain logs (default: 1 year)
            
        Returns:
            Number of logs deleted
        """
        self._ensure_initialized()
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        with self._get_session() as session:
            deleted_count = (
                session.query(AuditLogModel)
                .filter(AuditLogModel.timestamp < cutoff_date)
                .delete()
            )
            session.commit()
        
        logger.info("Cleaned up %d old audit logs (retention: %d days)", 
                   deleted_count, retention_days)
        return deleted_count
    
    def get_statistics(self, days: int = 30) -> dict[str, Any]:
        """
        Get usage statistics from audit logs.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with statistics (query counts, top assets, etc.)
        """
        self._ensure_initialized()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with self._get_session() as session:
            from sqlalchemy import func
            
            total_queries = (
                session.query(func.count(AuditLogModel.id))
                .filter(AuditLogModel.timestamp >= cutoff_date)
                .scalar()
            )
            
            queries_by_type = (
                session.query(
                    AuditLogModel.query_type,
                    func.count(AuditLogModel.id).label('count')
                )
                .filter(AuditLogModel.timestamp >= cutoff_date)
                .group_by(AuditLogModel.query_type)
                .all()
            )
            
            top_assets = (
                session.query(
                    AuditLogModel.asset_id,
                    func.count(AuditLogModel.id).label('count')
                )
                .filter(AuditLogModel.timestamp >= cutoff_date)
                .group_by(AuditLogModel.asset_id)
                .order_by(func.count(AuditLogModel.id).desc())
                .limit(10)
                .all()
            )
            
            return {
                "period_days": days,
                "total_queries": total_queries or 0,
                "queries_by_type": {qt: count for qt, count in queries_by_type},
                "top_assets": {asset: count for asset, count in top_assets},
            }
    
    def _get_session(self) -> Session:
        """Get a new database session."""
        return self._session_factory()
    
    def _ensure_initialized(self) -> None:
        """Ensure database is initialized before access."""
        if not self._initialized:
            self.initialize()
    
    def close(self) -> None:
        """Close database connections."""
        if self._engine:
            self._engine.dispose()
            self._initialized = False
            logger.info("AuditLogger closed")
