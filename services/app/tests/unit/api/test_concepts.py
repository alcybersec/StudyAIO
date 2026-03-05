"""Tests for knowledge graph / concept API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGetConceptGraph:
    """Tests for GET /api/concepts/graph."""

    @pytest.mark.asyncio
    @patch("app.api.concepts.concept_service")
    async def test_returns_graph(self, mock_service, async_client):
        """Returns nodes and edges."""
        mock_service.get_concept_graph = AsyncMock(return_value={
            "nodes": [
                {
                    "id": "c-001",
                    "name": "Binary Search",
                    "description": "Search algorithm",
                    "category": "algorithm",
                    "mention_count": 3,
                    "source_weeks": [1, 2],
                    "course_id": "course-001",
                },
            ],
            "edges": [
                {
                    "id": "r-001",
                    "source": "c-001",
                    "target": "c-002",
                    "relation_type": "uses",
                    "confidence": 0.9,
                },
            ],
        })

        resp = await async_client.get("/api/concepts/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert data["nodes"][0]["name"] == "Binary Search"

    @pytest.mark.asyncio
    @patch("app.api.concepts.concept_service")
    async def test_empty_graph(self, mock_service, async_client):
        """Returns empty graph when no concepts."""
        mock_service.get_concept_graph = AsyncMock(return_value={
            "nodes": [],
            "edges": [],
        })

        resp = await async_client.get("/api/concepts/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []

    @pytest.mark.asyncio
    @patch("app.api.concepts._resolve_course_id", new_callable=AsyncMock, return_value="course-001")
    @patch("app.api.concepts.concept_service")
    async def test_filters_by_course(self, mock_service, mock_resolve, async_client):
        """Accepts course_code query parameter."""
        mock_service.get_concept_graph = AsyncMock(return_value={"nodes": [], "edges": []})

        resp = await async_client.get("/api/concepts/graph?course_code=CSIT302")
        assert resp.status_code == 200


class TestListConcepts:
    """Tests for GET /api/concepts."""

    @pytest.mark.asyncio
    @patch("app.api.concepts.concept_service")
    async def test_returns_concept_list(self, mock_service, async_client):
        """Returns list of concepts."""
        mock_service.get_concepts = AsyncMock(return_value=[
            {
                "id": "c-001",
                "name": "Binary Search",
                "description": "Search algorithm",
                "category": "algorithm",
                "mention_count": 3,
                "source_weeks": [1],
                "course_id": "course-001",
                "created_at": "2026-03-05T10:00:00",
            },
        ])

        resp = await async_client.get("/api/concepts")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Binary Search"


class TestGetConceptDetail:
    """Tests for GET /api/concepts/{concept_id}."""

    @pytest.mark.asyncio
    @patch("app.api.concepts.concept_service")
    async def test_returns_detail(self, mock_service, async_client):
        """Returns concept detail with relations."""
        mock_service.get_concept_detail = AsyncMock(return_value={
            "id": "c-001",
            "name": "Binary Search",
            "description": "Search algorithm",
            "category": "algorithm",
            "mention_count": 2,
            "source_artifact_ids": ["art-001"],
            "source_weeks": [1],
            "course_id": "course-001",
            "outgoing_relations": [
                {
                    "id": "r-001",
                    "target_id": "c-002",
                    "target_name": "Arrays",
                    "relation_type": "uses",
                    "confidence": 0.9,
                },
            ],
            "incoming_relations": [],
            "created_at": "2026-03-05T10:00:00",
            "updated_at": "2026-03-05T10:00:00",
        })

        resp = await async_client.get("/api/concepts/c-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Binary Search"
        assert len(data["outgoing_relations"]) == 1
        assert data["outgoing_relations"][0]["concept_name"] == "Arrays"

    @pytest.mark.asyncio
    @patch("app.api.concepts.concept_service")
    async def test_returns_404_when_not_found(self, mock_service, async_client):
        """Returns 404 for nonexistent concept."""
        mock_service.get_concept_detail = AsyncMock(return_value=None)

        resp = await async_client.get("/api/concepts/nonexistent")
        assert resp.status_code == 404


class TestFindRelatedConcepts:
    """Tests for GET /api/concepts/{concept_id}/related."""

    @pytest.mark.asyncio
    @patch("app.api.concepts.concept_service")
    async def test_returns_similar_concepts(self, mock_service, async_client):
        """Returns semantically similar concepts."""
        mock_service.find_related_concepts = AsyncMock(return_value=[
            {
                "id": "c-002",
                "name": "Linear Search",
                "description": "Sequential search",
                "category": "algorithm",
                "course_id": "course-001",
                "similarity": 0.85,
            },
        ])

        resp = await async_client.get("/api/concepts/c-001/related")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["similarity"] == 0.85


class TestExtractConcepts:
    """Tests for POST /api/concepts/extract/{artifact_id}."""

    @pytest.mark.asyncio
    @patch("app.api.concepts.concept_service")
    async def test_returns_404_when_artifact_not_found(
        self, mock_service, async_client, mock_session
    ):
        """Returns 404 when artifact doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        resp = await async_client.post("/api/concepts/extract/nonexistent")
        assert resp.status_code == 404
