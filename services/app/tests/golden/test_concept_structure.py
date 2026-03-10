"""Golden tests for knowledge graph response structures.

Validates that concept/graph-related data conforms to expected schemas:
- Concept node: required fields and types
- Concept edge: required fields and types
- Graph response: nodes + edges structure
- Concept detail: relations, metadata
- Similar concept: similarity score
- Extraction result: counts
- Valid categories and relation types
"""

import pytest

# ── Sample data fixtures ────────────────────────────────────────────


@pytest.fixture
def sample_concept_node():
    """A realistic concept node."""
    return {
        "id": "c-001",
        "name": "Binary Search",
        "description": "Efficient search algorithm for sorted arrays with O(log n) time complexity.",
        "category": "algorithm",
        "mention_count": 3,
        "source_weeks": [1, 2],
        "course_id": "course-001",
        "created_at": "2026-03-05T10:00:00",
    }


@pytest.fixture
def sample_concept_edge():
    """A realistic concept edge."""
    return {
        "id": "r-001",
        "source": "c-001",
        "target": "c-002",
        "relation_type": "uses",
        "confidence": 0.9,
    }


@pytest.fixture
def sample_concept_graph(sample_concept_node, sample_concept_edge):
    """A realistic concept graph."""
    return {
        "nodes": [sample_concept_node],
        "edges": [sample_concept_edge],
    }


@pytest.fixture
def sample_concept_detail():
    """A realistic concept detail response."""
    return {
        "id": "c-001",
        "name": "Binary Search",
        "description": "Efficient search algorithm for sorted arrays with O(log n) time complexity.",
        "category": "algorithm",
        "mention_count": 3,
        "source_artifact_ids": ["art-001", "art-002"],
        "source_weeks": [1, 2],
        "course_id": "course-001",
        "outgoing_relations": [
            {
                "id": "r-001",
                "concept_id": "c-002",
                "concept_name": "Sorted Array",
                "relation_type": "uses",
                "confidence": 0.9,
            },
        ],
        "incoming_relations": [
            {
                "id": "r-002",
                "concept_id": "c-003",
                "concept_name": "Divide and Conquer",
                "relation_type": "extends",
                "confidence": 0.85,
            },
        ],
        "created_at": "2026-03-05T10:00:00",
        "updated_at": "2026-03-05T12:00:00",
    }


@pytest.fixture
def sample_similar_concept():
    """A similar concept result."""
    return {
        "id": "c-004",
        "name": "Linear Search",
        "description": "Sequential search through all elements.",
        "category": "algorithm",
        "course_id": "course-001",
        "similarity": 0.82,
    }


@pytest.fixture
def sample_extraction_result():
    """A concept extraction result."""
    return {
        "artifact_id": "art-001",
        "concept_count": 5,
        "relation_count": 3,
    }


# ── Concept Node Structure ──────────────────────────────────────────


class TestConceptNodeStructure:
    """Verify concept node has required fields."""

    REQUIRED_FIELDS = {
        "id",
        "name",
        "description",
        "category",
        "mention_count",
        "source_weeks",
        "course_id",
    }

    def test_has_all_required_fields(self, sample_concept_node):
        """Node has all required fields."""
        assert self.REQUIRED_FIELDS.issubset(set(sample_concept_node.keys()))

    def test_id_is_string(self, sample_concept_node):
        assert isinstance(sample_concept_node["id"], str)

    def test_name_is_string(self, sample_concept_node):
        assert isinstance(sample_concept_node["name"], str)

    def test_description_is_string(self, sample_concept_node):
        assert isinstance(sample_concept_node["description"], str)

    def test_category_is_valid(self, sample_concept_node):
        valid = {
            "theory",
            "algorithm",
            "data_structure",
            "pattern",
            "tool",
            "language",
            "protocol",
            "principle",
            "method",
            "general",
        }
        assert sample_concept_node["category"] in valid

    def test_mention_count_is_positive_int(self, sample_concept_node):
        assert isinstance(sample_concept_node["mention_count"], int)
        assert sample_concept_node["mention_count"] >= 1

    def test_source_weeks_is_list(self, sample_concept_node):
        assert isinstance(sample_concept_node["source_weeks"], list)


# ── Concept Edge Structure ──────────────────────────────────────────


class TestConceptEdgeStructure:
    """Verify concept edge has required fields."""

    REQUIRED_FIELDS = {"id", "source", "target", "relation_type", "confidence"}

    def test_has_all_required_fields(self, sample_concept_edge):
        assert self.REQUIRED_FIELDS.issubset(set(sample_concept_edge.keys()))

    def test_relation_type_is_valid(self, sample_concept_edge):
        valid = {"prerequisite", "extends", "uses", "related_to", "part_of"}
        assert sample_concept_edge["relation_type"] in valid

    def test_confidence_is_float_in_range(self, sample_concept_edge):
        conf = sample_concept_edge["confidence"]
        assert isinstance(conf, (int, float))
        assert 0.0 <= conf <= 1.0

    def test_source_and_target_are_strings(self, sample_concept_edge):
        assert isinstance(sample_concept_edge["source"], str)
        assert isinstance(sample_concept_edge["target"], str)


# ── Graph Response Structure ──────────────────────────────────────────


class TestConceptGraphStructure:
    """Verify graph response has nodes and edges."""

    def test_has_nodes_and_edges(self, sample_concept_graph):
        assert "nodes" in sample_concept_graph
        assert "edges" in sample_concept_graph

    def test_nodes_is_list(self, sample_concept_graph):
        assert isinstance(sample_concept_graph["nodes"], list)

    def test_edges_is_list(self, sample_concept_graph):
        assert isinstance(sample_concept_graph["edges"], list)


# ── Concept Detail Structure ──────────────────────────────────────────


class TestConceptDetailStructure:
    """Verify concept detail has required fields."""

    REQUIRED_FIELDS = {
        "id",
        "name",
        "description",
        "category",
        "mention_count",
        "source_artifact_ids",
        "source_weeks",
        "course_id",
        "outgoing_relations",
        "incoming_relations",
    }

    def test_has_all_required_fields(self, sample_concept_detail):
        assert self.REQUIRED_FIELDS.issubset(set(sample_concept_detail.keys()))

    def test_source_artifact_ids_is_list(self, sample_concept_detail):
        assert isinstance(sample_concept_detail["source_artifact_ids"], list)

    def test_outgoing_relations_is_list(self, sample_concept_detail):
        assert isinstance(sample_concept_detail["outgoing_relations"], list)

    def test_incoming_relations_is_list(self, sample_concept_detail):
        assert isinstance(sample_concept_detail["incoming_relations"], list)

    def test_relation_item_has_required_fields(self, sample_concept_detail):
        for rel in sample_concept_detail["outgoing_relations"]:
            assert "id" in rel
            assert "concept_id" in rel
            assert "concept_name" in rel
            assert "relation_type" in rel
            assert "confidence" in rel


# ── Similar Concept Structure ──────────────────────────────────────────


class TestSimilarConceptStructure:
    """Verify similar concept has required fields."""

    REQUIRED_FIELDS = {"id", "name", "description", "category", "course_id", "similarity"}

    def test_has_all_required_fields(self, sample_similar_concept):
        assert self.REQUIRED_FIELDS.issubset(set(sample_similar_concept.keys()))

    def test_similarity_in_range(self, sample_similar_concept):
        sim = sample_similar_concept["similarity"]
        assert 0.0 <= sim <= 1.0


# ── Extraction Result Structure ──────────────────────────────────────────


class TestExtractionResultStructure:
    """Verify extraction result has required fields."""

    REQUIRED_FIELDS = {"artifact_id", "concept_count", "relation_count"}

    def test_has_all_required_fields(self, sample_extraction_result):
        assert self.REQUIRED_FIELDS.issubset(set(sample_extraction_result.keys()))

    def test_counts_are_non_negative(self, sample_extraction_result):
        assert sample_extraction_result["concept_count"] >= 0
        assert sample_extraction_result["relation_count"] >= 0
