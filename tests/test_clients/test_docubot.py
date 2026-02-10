"""
Tests for DocuBotClient interface and MockDocuBotClient implementation.

Covers:
    - ExternalServiceClient lifecycle (initialize, shutdown, health_check)
    - Interface compliance
    - Document search with category detection
    - Search result data quality

Model immutability, explanation, and helper tests in test_docubot_models.py.
"""

from __future__ import annotations

import pytest

from skill.clients.base import ExternalServiceClient
from skill.clients.docubot import (
    DocuBotClient,
    MockDocuBotClient,
)
from skill.domain.document_models import DocumentResult


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_client() -> MockDocuBotClient:
    """Create a fresh MockDocuBotClient for each test."""
    return MockDocuBotClient()


# =========================================================================
# Interface Compliance
# =========================================================================


class TestDocuBotClientInterface:
    """Verify MockDocuBotClient implements required interfaces."""

    def test_is_external_service_client(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """MockDocuBotClient must be an ExternalServiceClient."""
        assert isinstance(mock_client, ExternalServiceClient)

    def test_is_docubot_client(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """MockDocuBotClient must be a DocuBotClient."""
        assert isinstance(mock_client, DocuBotClient)


# =========================================================================
# Lifecycle Tests
# =========================================================================


class TestMockDocuBotLifecycle:
    """Test initialize/shutdown/health_check/is_connected lifecycle."""

    @pytest.mark.asyncio
    async def test_initialize_sets_connected(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """After initialize(), is_connected should be True."""
        assert not mock_client.is_connected
        await mock_client.initialize()
        assert mock_client.is_connected

    @pytest.mark.asyncio
    async def test_shutdown_clears_connected(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """After shutdown(), is_connected should be False."""
        await mock_client.initialize()
        await mock_client.shutdown()
        assert not mock_client.is_connected

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Calling shutdown() multiple times should not raise."""
        await mock_client.initialize()
        await mock_client.shutdown()
        await mock_client.shutdown()  # Should not raise
        assert not mock_client.is_connected

    @pytest.mark.asyncio
    async def test_health_check_returns_true(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Mock health_check always returns True."""
        result = await mock_client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_without_initialize(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Health check works even without initialization."""
        result = await mock_client.health_check()
        assert result is True

    def test_service_name(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Service name should be human-readable."""
        assert mock_client.service_name == "Document Q&A"

    def test_initial_state_not_connected(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Fresh client should not be connected."""
        assert not mock_client.is_connected


# =========================================================================
# Document Search Tests
# =========================================================================


class TestMockDocuBotSearch:
    """Test search_documents() method."""

    @pytest.mark.asyncio
    async def test_search_returns_document_result(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """search_documents() must return a DocumentResult."""
        result = await mock_client.search_documents("energy consumption")
        assert isinstance(result, DocumentResult)

    @pytest.mark.asyncio
    async def test_search_energy_query(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Energy-related queries return energy passages."""
        result = await mock_client.search_documents("energy consumption")
        assert result.passage_count >= 2
        assert any("energy" in p.text.lower() for p in result.passages)

    @pytest.mark.asyncio
    async def test_search_material_query(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Material-related queries return material passages."""
        result = await mock_client.search_documents("scrap rate reduction")
        assert result.passage_count >= 1
        assert any("scrap" in p.text.lower() for p in result.passages)

    @pytest.mark.asyncio
    async def test_search_carbon_query(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Carbon-related queries return carbon passages."""
        result = await mock_client.search_documents("carbon footprint")
        assert result.passage_count >= 1
        assert any("co₂" in p.text.lower() or "carbon" in p.text.lower() for p in result.passages)

    @pytest.mark.asyncio
    async def test_search_supplier_query(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Supplier-related queries return supplier passages."""
        result = await mock_client.search_documents("supplier lead time")
        assert result.passage_count >= 1
        assert any("supplier" in p.text.lower() for p in result.passages)

    @pytest.mark.asyncio
    async def test_search_production_query(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Production-related queries return production passages."""
        result = await mock_client.search_documents("OEE improvement")
        assert result.passage_count >= 1
        assert any("oee" in p.text.lower() for p in result.passages)

    @pytest.mark.asyncio
    async def test_search_unknown_query_defaults_to_production(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Unknown queries should fall back to production category."""
        result = await mock_client.search_documents("xyz unknown topic")
        assert result.passage_count >= 1

    @pytest.mark.asyncio
    async def test_search_max_results_limits_passages(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """max_results parameter limits the number of passages."""
        result = await mock_client.search_documents("energy", max_results=1)
        assert result.passage_count == 1

    @pytest.mark.asyncio
    async def test_search_preserves_query(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """DocumentResult.query matches the input query."""
        query = "energy reduction procedures"
        result = await mock_client.search_documents(query)
        assert result.query == query

    @pytest.mark.asyncio
    async def test_search_has_source_documents(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Results should include source document identifiers."""
        result = await mock_client.search_documents("energy")
        assert len(result.source_documents) >= 1
        assert all(isinstance(s, str) for s in result.source_documents)

    @pytest.mark.asyncio
    async def test_search_confidence_in_range(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """Confidence score must be between 0.0 and 1.0."""
        result = await mock_client.search_documents("energy")
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_search_passages_have_valid_scores(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """All passage relevance scores must be between 0.0 and 1.0."""
        result = await mock_client.search_documents("carbon footprint")
        for passage in result.passages:
            assert 0.0 <= passage.relevance_score <= 1.0

    @pytest.mark.asyncio
    async def test_search_passages_have_sources(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """All passages must have non-empty source attributes."""
        result = await mock_client.search_documents("energy")
        for passage in result.passages:
            assert passage.source
            assert isinstance(passage.source, str)

    @pytest.mark.asyncio
    async def test_search_passages_have_text(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """All passages must have non-empty text content."""
        result = await mock_client.search_documents("material efficiency")
        for passage in result.passages:
            assert passage.text
            assert len(passage.text) > 20  # Meaningful content

    @pytest.mark.asyncio
    async def test_search_top_passage_helper(
        self, mock_client: MockDocuBotClient,
    ) -> None:
        """DocumentResult.top_passage returns highest relevance passage."""
        result = await mock_client.search_documents("energy")
        top = result.top_passage
        assert top is not None
        for passage in result.passages:
            assert top.relevance_score >= passage.relevance_score
