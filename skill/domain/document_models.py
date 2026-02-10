"""
Document-Grounded Q&A Domain Models

Immutable data models for document search and retrieval results.
Used by external service clients (DocuBoT, future document engines)
to return structured document passages and search results.

These models are platform-agnostic (DEC-001) — no service-specific
terminology in model names or field names.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentPassage:
    """
    A single passage retrieved from a document search.

    Represents a relevant text excerpt with source attribution
    and relevance scoring.

    Attributes:
        text: The passage content
        source: Document name or identifier
        page: Page number (None if not applicable)
        relevance_score: Relevance to the query (0.0 to 1.0)
    """

    text: str
    source: str
    page: int | None
    relevance_score: float


@dataclass(frozen=True)
class DocumentResult:
    """
    Result from a document search query.

    Contains the original query, retrieved passages, overall confidence,
    and a list of source documents that contributed to the result.

    Attributes:
        query: The original search query
        passages: Retrieved document passages
        confidence: Overall confidence score (0.0 to 1.0)
        source_documents: List of source document identifiers

    Example:
        DocumentResult(
            query="energy reduction procedures",
            passages=(DocumentPassage(...), ...),
            confidence=0.85,
            source_documents=("maintenance_manual_v3.pdf",)
        )
    """

    query: str
    passages: tuple[DocumentPassage, ...]
    confidence: float
    source_documents: tuple[str, ...]

    def __init__(
        self,
        query: str,
        passages: list[DocumentPassage] | tuple[DocumentPassage, ...],
        confidence: float,
        source_documents: list[str] | tuple[str, ...],
    ) -> None:
        """Initialize with sequences converted to tuples for immutability."""
        object.__setattr__(self, "query", query)
        object.__setattr__(self, "passages", tuple(passages))
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "source_documents", tuple(source_documents))

    @property
    def passage_count(self) -> int:
        """Number of passages retrieved."""
        return len(self.passages)

    @property
    def top_passage(self) -> DocumentPassage | None:
        """Highest-relevance passage, or None if empty."""
        if not self.passages:
            return None
        return max(self.passages, key=lambda p: p.relevance_score)
