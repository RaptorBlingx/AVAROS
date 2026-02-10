"""
DocuBotClient — Document-Grounded Q&A Client

Provides document search and metric explanation capabilities
for AVAROS's document-grounded Q&A feature. DocuBoT is a WASABI
consortium component that indexes uploaded documents (manuals,
datasheets, compliance docs) and provides natural-language answers.

Architecture (DEC-018):
    - REST API client (HTTP) — DocuBoT runs as a separate Docker container
    - Connection via internal Docker DNS: http://docubot:8000/api/v1/...
    - Connection details stored in SettingsService (DEC-006)
    - Graceful degradation when unavailable (DEC-005)

Design Principles:
    - Platform-agnostic interface names (DEC-001): "document search" not
      "DocuBoT index"
    - Domain models in skill.domain (DEC-003)
    - Client fetches data only; intelligence in QueryDispatcher (DEC-007)
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from skill.clients._docubot_demo_data import (
    CATEGORY_KEYWORDS,
    DEMO_PASSAGES,
    EXPLANATION_TEMPLATES,
    METRIC_CATEGORY_MAP,
)
from skill.clients.base import ExternalServiceClient
from skill.domain.document_models import DocumentPassage, DocumentResult

if TYPE_CHECKING:
    from skill.domain.models import CanonicalMetric

logger = logging.getLogger(__name__)


class DocuBotClient(ExternalServiceClient):
    """
    Client interface for document-grounded Q&A service.

    Provides two core capabilities:
        1. Document search — retrieve relevant passages for a query
        2. Metric explanation — get contextual explanations grounded
           in uploaded documents

    Implementing Classes:
        - MockDocuBotClient: Demo data (zero-config, DEC-005)
        - Future: HttpDocuBotClient (real REST API integration)
    """

    @abstractmethod
    async def search_documents(
        self,
        query: str,
        max_results: int = 5,
    ) -> DocumentResult:
        """
        Search indexed documents for relevant passages.

        Args:
            query: Natural language search query
            max_results: Maximum number of passages to return

        Returns:
            DocumentResult with matching passages and confidence

        Raises:
            ConnectionError: If the document service is unavailable
        """

    @abstractmethod
    async def get_explanation(
        self,
        metric: CanonicalMetric,
        context: str,
    ) -> str:
        """
        Get a document-grounded explanation for a metric.

        Used by QueryDispatcher to enrich what-if simulation results
        with contextual explanations from uploaded documents.

        Args:
            metric: The canonical metric to explain
            context: Situational context (e.g., "after temperature reduction")

        Returns:
            Human-readable explanation grounded in document content

        Raises:
            ConnectionError: If the document service is unavailable
        """


# =========================================================================
# Helper Functions
# =========================================================================


def _get_category_for_metric(metric: CanonicalMetric) -> str:
    """
    Map a canonical metric to its document category.

    Args:
        metric: The canonical metric to categorize

    Returns:
        Category string (energy, material, carbon, production, supplier)
    """
    return METRIC_CATEGORY_MAP.get(metric.value, "production")


def _build_passages(
    raw_passages: list[dict],
    max_results: int,
) -> list[DocumentPassage]:
    """
    Convert raw demo passage dicts to DocumentPassage models.

    Args:
        raw_passages: List of passage dictionaries
        max_results: Maximum passages to return

    Returns:
        List of DocumentPassage instances
    """
    return [
        DocumentPassage(
            text=p["text"],
            source=p["source"],
            page=p["page"],
            relevance_score=p["relevance"],
        )
        for p in raw_passages[:max_results]
    ]


def _detect_query_category(query: str) -> str:
    """
    Detect which document category a query relates to.

    Uses keyword matching against known manufacturing terms.

    Args:
        query: The search query text

    Returns:
        Category string (defaults to "production")
    """
    query_lower = query.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            return category

    return "production"


class MockDocuBotClient(DocuBotClient):
    """
    Demo implementation of document-grounded Q&A client.

    Returns realistic manufacturing document passages without an external
    service. Enables zero-config deployment (DEC-005). Covers energy,
    material, carbon, production, and supplier categories.
    """

    def __init__(self) -> None:
        """Initialize the mock client."""
        self._initialized: bool = False

    # =====================================================================
    # Lifecycle Methods (ExternalServiceClient)
    # =====================================================================

    async def initialize(self) -> None:
        """Initialize mock client (no-op, always succeeds)."""
        self._initialized = True
        logger.info("MockDocuBotClient initialized (demo mode)")

    async def shutdown(self) -> None:
        """Shut down mock client (no-op, safe to call multiple times)."""
        self._initialized = False
        logger.info("MockDocuBotClient shut down")

    async def health_check(self) -> bool:
        """
        Check service health.

        Returns:
            Always True for mock implementation
        """
        return True

    @property
    def service_name(self) -> str:
        """
        Human-readable service name.

        Returns:
            Service display name
        """
        return "Document Q&A"

    @property
    def is_connected(self) -> bool:
        """
        Whether the client is connected.

        Returns:
            True after initialize() has been called
        """
        return self._initialized

    # =====================================================================
    # DocuBotClient Methods
    # =====================================================================

    async def search_documents(
        self,
        query: str,
        max_results: int = 5,
    ) -> DocumentResult:
        """
        Search demo documents for relevant passages.

        Matches the query against predefined demo passages using
        keyword-based category detection.

        Args:
            query: Natural language search query
            max_results: Maximum passages to return (1–10)

        Returns:
            DocumentResult with matching demo passages
        """
        category = _detect_query_category(query)
        raw_passages = DEMO_PASSAGES.get(category, DEMO_PASSAGES["production"])

        passages = _build_passages(raw_passages, max_results)
        source_docs = list({p.source for p in passages})

        confidence = _compute_confidence(passages)

        return DocumentResult(
            query=query,
            passages=passages,
            confidence=confidence,
            source_documents=source_docs,
        )

    async def get_explanation(
        self,
        metric: CanonicalMetric,
        context: str,
    ) -> str:
        """
        Get a template-based explanation for a metric.

        Uses the metric's category to select an appropriate
        explanation template, then fills in the context.

        Args:
            metric: The canonical metric to explain
            context: Situational context string

        Returns:
            Human-readable explanation string
        """
        category = _get_category_for_metric(metric)
        template = EXPLANATION_TEMPLATES.get(
            category,
            EXPLANATION_TEMPLATES["production"],
        )
        return template.format(context=context)


def _compute_confidence(passages: list[DocumentPassage]) -> float:
    """
    Compute overall confidence from passage relevance scores.

    Uses weighted average of top passages, capped at 0.95.

    Args:
        passages: List of document passages with relevance scores

    Returns:
        Confidence score between 0.0 and 0.95
    """
    if not passages:
        return 0.0
    avg = sum(p.relevance_score for p in passages) / len(passages)
    return min(round(avg, 2), 0.95)
