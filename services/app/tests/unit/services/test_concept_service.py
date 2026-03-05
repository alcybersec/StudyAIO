"""Tests for concept service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ConceptData, ConceptExtractionResult, ConceptRelationData


class TestExtractAndSaveConcepts:
    """Tests for extract_and_save_concepts."""

    @pytest.mark.asyncio
    @patch("app.agents.embeddings.get_embedding_provider")
    @patch("app.agents.factory.get_agent")
    async def test_creates_new_concepts(self, mock_get_agent, mock_embed, mock_session):
        """New concepts are created with correct fields."""
        from app.services.concept_service import extract_and_save_concepts

        mock_agent = MagicMock()
        mock_agent.extract_concepts = AsyncMock(return_value=ConceptExtractionResult(
            concepts=[
                ConceptData(name="Binary Search", description="Search algorithm", category="algorithm"),
                ConceptData(name="Sorting", description="Ordering elements", category="algorithm"),
            ],
            relations=[],
        ))
        mock_get_agent.return_value = mock_agent

        mock_provider = MagicMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 384)
        mock_embed.return_value = mock_provider

        # Mock empty existing concepts
        mock_session.execute = AsyncMock(return_value=MagicMock(
            all=MagicMock(return_value=[]),
            scalar_one_or_none=MagicMock(return_value=None),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        ))
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        result = await extract_and_save_concepts(
            session=mock_session,
            artifact_id="art-001",
            user_id="user-001",
            course_id="course-001",
            week=1,
            extraction_text="Binary search works on sorted arrays...",
        )

        assert result["concept_count"] == 2
        assert result["relation_count"] == 0
        mock_agent.extract_concepts.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.embeddings.get_embedding_provider")
    @patch("app.agents.factory.get_agent")
    async def test_passes_existing_concepts_to_agent(self, mock_get_agent, mock_embed, mock_session):
        """Existing concept names are passed to the agent."""
        from app.services.concept_service import extract_and_save_concepts

        mock_agent = MagicMock()
        mock_agent.extract_concepts = AsyncMock(return_value=ConceptExtractionResult(
            concepts=[], relations=[],
        ))
        mock_get_agent.return_value = mock_agent

        mock_provider = MagicMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 384)
        mock_embed.return_value = mock_provider

        # Return some existing names
        existing_rows = MagicMock()
        existing_rows.all.return_value = [("Binary Search",), ("Arrays",)]

        mock_session.execute = AsyncMock(return_value=existing_rows)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        await extract_and_save_concepts(
            session=mock_session,
            artifact_id="art-002",
            user_id="user-001",
            course_id="course-001",
            week=2,
            extraction_text="Some text",
        )

        call_args = mock_agent.extract_concepts.call_args
        assert call_args[1]["existing_concepts"] == ["Binary Search", "Arrays"]

    @pytest.mark.asyncio
    @patch("app.agents.embeddings.get_embedding_provider")
    @patch("app.agents.factory.get_agent")
    async def test_empty_extraction_returns_zeros(self, mock_get_agent, mock_embed, mock_session):
        """Empty AI response returns zero counts."""
        from app.services.concept_service import extract_and_save_concepts

        mock_agent = MagicMock()
        mock_agent.extract_concepts = AsyncMock(return_value=ConceptExtractionResult())
        mock_get_agent.return_value = mock_agent

        mock_session.execute = AsyncMock(return_value=MagicMock(
            all=MagicMock(return_value=[]),
        ))
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        result = await extract_and_save_concepts(
            session=mock_session,
            artifact_id="art-003",
            user_id="user-001",
            course_id="course-001",
            week=1,
            extraction_text="Empty",
        )

        assert result["concept_count"] == 0
        assert result["relation_count"] == 0


class TestGetConcepts:
    """Tests for get_concepts."""

    @pytest.mark.asyncio
    async def test_returns_formatted_list(self, mock_session):
        """Returns properly formatted concept dicts."""
        from datetime import datetime
        from app.services.concept_service import get_concepts

        mock_concept = MagicMock()
        mock_concept.id = "c-001"
        mock_concept.name = "Binary Search"
        mock_concept.description = "Search algorithm"
        mock_concept.category = "algorithm"
        mock_concept.mention_count = 3
        mock_concept.source_weeks = [1, 2]
        mock_concept.course_id = "course-001"
        mock_concept.created_at = datetime(2026, 3, 5)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_concept]
        mock_session.execute = AsyncMock(return_value=mock_result)

        concepts = await get_concepts(mock_session, "user-001")

        assert len(concepts) == 1
        assert concepts[0]["id"] == "c-001"
        assert concepts[0]["name"] == "Binary Search"
        assert concepts[0]["category"] == "algorithm"
        assert concepts[0]["mention_count"] == 3

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_session):
        """Returns empty list when no concepts."""
        from app.services.concept_service import get_concepts

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        concepts = await get_concepts(mock_session, "user-001")
        assert concepts == []


class TestGetConceptGraph:
    """Tests for get_concept_graph."""

    @pytest.mark.asyncio
    async def test_returns_nodes_and_edges(self, mock_session):
        """Returns graph with nodes and edges."""
        from app.services.concept_service import get_concept_graph

        mock_concept = MagicMock()
        mock_concept.id = "c-001"
        mock_concept.name = "Binary Search"
        mock_concept.description = "Search"
        mock_concept.category = "algorithm"
        mock_concept.mention_count = 1
        mock_concept.source_weeks = [1]
        mock_concept.course_id = "course-001"

        mock_rel = MagicMock()
        mock_rel.id = "r-001"
        mock_rel.source_concept_id = "c-001"
        mock_rel.target_concept_id = "c-002"
        mock_rel.relation_type = "uses"
        mock_rel.confidence = 0.9

        # First call returns concepts, second call returns relations
        concepts_result = MagicMock()
        concepts_result.scalars.return_value.all.return_value = [mock_concept]

        rels_result = MagicMock()
        rels_result.scalars.return_value.all.return_value = [mock_rel]

        mock_session.execute = AsyncMock(side_effect=[concepts_result, rels_result])

        graph = await get_concept_graph(mock_session, "user-001")

        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["name"] == "Binary Search"

    @pytest.mark.asyncio
    async def test_empty_graph(self, mock_session):
        """Returns empty graph when no concepts."""
        from app.services.concept_service import get_concept_graph

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        graph = await get_concept_graph(mock_session, "user-001")
        assert graph["nodes"] == []
        assert graph["edges"] == []


class TestGetConceptDetail:
    """Tests for get_concept_detail."""

    @pytest.mark.asyncio
    async def test_returns_detail_with_relations(self, mock_session):
        """Returns concept detail with outgoing/incoming."""
        from datetime import datetime
        from app.services.concept_service import get_concept_detail

        mock_rel_out = MagicMock()
        mock_rel_out.id = "r-001"
        mock_rel_out.target_concept_id = "c-002"
        mock_rel_out.relation_type = "uses"
        mock_rel_out.confidence = 0.9

        mock_concept = MagicMock()
        mock_concept.id = "c-001"
        mock_concept.name = "Binary Search"
        mock_concept.description = "Search algorithm"
        mock_concept.category = "algorithm"
        mock_concept.mention_count = 2
        mock_concept.source_artifact_ids = ["art-001"]
        mock_concept.source_weeks = [1]
        mock_concept.course_id = "course-001"
        mock_concept.outgoing_relations = [mock_rel_out]
        mock_concept.incoming_relations = []
        mock_concept.created_at = datetime(2026, 3, 5)
        mock_concept.updated_at = datetime(2026, 3, 5)

        # First call: concept with relations
        concept_result = MagicMock()
        concept_result.unique.return_value.scalar_one_or_none.return_value = mock_concept

        # Second call: related names
        names_result = MagicMock()
        names_result.all.return_value = [("c-002", "Arrays")]

        mock_session.execute = AsyncMock(side_effect=[concept_result, names_result])

        detail = await get_concept_detail(mock_session, "c-001", "user-001")

        assert detail is not None
        assert detail["name"] == "Binary Search"
        assert len(detail["outgoing_relations"]) == 1
        assert detail["outgoing_relations"][0]["target_name"] == "Arrays"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session):
        """Returns None for nonexistent concept."""
        from app.services.concept_service import get_concept_detail

        mock_result = MagicMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        detail = await get_concept_detail(mock_session, "nonexistent", "user-001")
        assert detail is None


class TestFindRelatedConcepts:
    """Tests for find_related_concepts."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_embedding(self, mock_session):
        """Returns empty list when source concept has no embedding."""
        from app.services.concept_service import find_related_concepts

        mock_concept = MagicMock()
        mock_concept.embedding = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_concept
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await find_related_concepts(mock_session, "c-001", "user-001")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_concept_not_found(self, mock_session):
        """Returns empty list when concept doesn't exist."""
        from app.services.concept_service import find_related_concepts

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await find_related_concepts(mock_session, "nonexistent", "user-001")
        assert result == []
