"""
Tests for DocumentResult/DocumentPassage models and helper functions.

Covers:
    - Domain model immutability (DEC-004)
    - Helper functions (category detection, confidence computation)
    - Metric explanation via MockDocuBotClient
"""

from __future__ import annotations

import pytest

from skill.clients.docubot import (
    MockDocuBotClient,
    _compute_confidence,
    _detect_query_category,
    _get_category_for_metric,
)
from skill.domain.document_models import DocumentPassage, DocumentResult
from skill.domain.models import CanonicalMetric


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_client() -> MockDocuBotClient:
    """Create a fresh MockDocuBotClient for each test."""
    return MockDocuBotClient()


# =========================================================================
# Metric Explanation Tests
# =========================================================================


class TestMockDocuBotExplanation:
    """Test get_explanation() method."""

    @pytest.mark.asyncio
    async def test_explanation_returns_string(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """get_explanation() must return a non-empty string."""
        result = await mock_client.get_explanation(
            CanonicalMetric.ENERGY_PER_UNIT,
            "after temperature reduction",
        )
        assert isinstance(result, str)
        assert len(result) > 20

    @pytest.mark.asyncio
    async def test_explanation_includes_context(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Explanation must include the provided context."""
        context = "after reducing compressor load by 10%"
        result = await mock_client.get_explanation(
            CanonicalMetric.ENERGY_PER_UNIT,
            context,
        )
        assert context in result

    @pytest.mark.asyncio
    async def test_explanation_energy_metric(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Energy metrics should reference energy-related content."""
        result = await mock_client.get_explanation(
            CanonicalMetric.ENERGY_PER_UNIT,
            "test context",
        )
        assert "energy" in result.lower()

    @pytest.mark.asyncio
    async def test_explanation_scrap_metric(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Material metrics should reference material-related content."""
        result = await mock_client.get_explanation(
            CanonicalMetric.SCRAP_RATE,
            "test context",
        )
        assert "scrap" in result.lower()

    @pytest.mark.asyncio
    async def test_explanation_carbon_metric(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Carbon metrics should reference carbon-related content."""
        result = await mock_client.get_explanation(
            CanonicalMetric.CO2_PER_UNIT,
            "test context",
        )
        assert "emission" in result.lower() or "scope" in result.lower()

    @pytest.mark.asyncio
    async def test_explanation_production_metric(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Production metrics should reference production content."""
        result = await mock_client.get_explanation(
            CanonicalMetric.OEE,
            "test context",
        )
        assert "oee" in result.lower()

    @pytest.mark.asyncio
    async def test_explanation_supplier_metric(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Supplier metrics should reference supply chain content."""
        result = await mock_client.get_explanation(
            CanonicalMetric.SUPPLIER_LEAD_TIME,
            "test context",
        )
        assert "lead time" in result.lower() or "supplier" in result.lower()

    @pytest.mark.asyncio
    async def test_explanation_all_metrics_produce_output(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Every canonical metric should produce a non-empty explanation."""
        for metric in CanonicalMetric:
            result = await mock_client.get_explanation(metric, "test")
            assert isinstance(result, str)
            assert len(result) > 10, f"Empty explanation for {metric.value}"


# =========================================================================
# Domain Model Immutability Tests (DEC-004)
# =========================================================================


class TestDocumentModelImmutability:
    """Verify frozen=True enforcement on domain models."""

    def test_document_passage_frozen(self) -> None:
        """DocumentPassage must be immutable."""
        passage = DocumentPassage(
            text="Test passage",
            source="test.pdf",
            page=1,
            relevance_score=0.9,
        )
        with pytest.raises(AttributeError):
            passage.text = "modified"  # type: ignore[misc]

    def test_document_result_frozen(self) -> None:
        """DocumentResult must be immutable."""
        result = DocumentResult(
            query="test",
            passages=[],
            confidence=0.5,
            source_documents=[],
        )
        with pytest.raises(AttributeError):
            result.query = "modified"  # type: ignore[misc]

    def test_document_result_passages_are_tuple(self) -> None:
        """DocumentResult.passages must be a tuple (not list)."""
        result = DocumentResult(
            query="test",
            passages=[
                DocumentPassage("t", "s", 1, 0.9),
            ],
            confidence=0.5,
            source_documents=["s"],
        )
        assert isinstance(result.passages, tuple)

    def test_document_result_source_documents_are_tuple(self) -> None:
        """DocumentResult.source_documents must be a tuple (not list)."""
        result = DocumentResult(
            query="test",
            passages=[],
            confidence=0.5,
            source_documents=["doc.pdf"],
        )
        assert isinstance(result.source_documents, tuple)

    def test_document_result_accepts_lists(self) -> None:
        """DocumentResult __init__ should accept lists and convert."""
        passages = [DocumentPassage("t", "s", 1, 0.9)]
        docs = ["doc.pdf"]
        result = DocumentResult(
            query="test",
            passages=passages,
            confidence=0.5,
            source_documents=docs,
        )
        assert isinstance(result.passages, tuple)
        assert isinstance(result.source_documents, tuple)
        assert result.passage_count == 1

    def test_document_result_top_passage_empty(self) -> None:
        """top_passage returns None when no passages."""
        result = DocumentResult(
            query="test",
            passages=[],
            confidence=0.0,
            source_documents=[],
        )
        assert result.top_passage is None


# =========================================================================
# Helper Function Tests
# =========================================================================


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_detect_query_category_energy(self) -> None:
        """Energy keywords should map to energy category."""
        assert _detect_query_category("electricity consumption") == "energy"
        assert _detect_query_category("power demand") == "energy"

    def test_detect_query_category_material(self) -> None:
        """Material keywords should map to material category."""
        assert _detect_query_category("scrap reduction") == "material"
        assert _detect_query_category("waste management") == "material"

    def test_detect_query_category_carbon(self) -> None:
        """Carbon keywords should map to carbon category."""
        assert _detect_query_category("carbon footprint") == "carbon"
        assert _detect_query_category("CO2 emissions") == "carbon"

    def test_detect_query_category_supplier(self) -> None:
        """Supplier keywords should map to supplier category."""
        assert _detect_query_category("supplier quality") == "supplier"
        assert _detect_query_category("delivery performance") == "supplier"

    def test_detect_query_category_production(self) -> None:
        """Production keywords should map to production category."""
        assert _detect_query_category("throughput optimization") == "production"
        assert _detect_query_category("cycle time") == "production"

    def test_detect_query_category_default(self) -> None:
        """Unknown queries default to production."""
        assert _detect_query_category("xyzzy gibberish") == "production"

    def test_get_category_for_all_metrics(self) -> None:
        """Every canonical metric must map to a valid category."""
        valid_categories = {"energy", "material", "carbon", "production", "supplier"}
        for metric in CanonicalMetric:
            category = _get_category_for_metric(metric)
            assert category in valid_categories, (
                f"{metric.value} mapped to invalid category: {category}"
            )

    def test_compute_confidence_empty(self) -> None:
        """Empty passage list should return 0.0 confidence."""
        assert _compute_confidence([]) == 0.0

    def test_compute_confidence_capped(self) -> None:
        """Confidence should be capped at 0.95."""
        passages = [
            DocumentPassage("t", "s", 1, 0.99),
            DocumentPassage("t", "s", 2, 0.98),
        ]
        result = _compute_confidence(passages)
        assert result <= 0.95

    def test_compute_confidence_average(self) -> None:
        """Confidence is the average of passage relevance scores."""
        passages = [
            DocumentPassage("t", "s", 1, 0.80),
            DocumentPassage("t", "s", 2, 0.60),
        ]
        result = _compute_confidence(passages)
        assert result == 0.70
